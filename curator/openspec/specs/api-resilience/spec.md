# API Resilience (Rate Limiting & Quotas) Specifications

## Context & Implementation Guide

API Resilience provides rate limiting, quota enforcement, and abuse protection for the browser frontend API. This prevents resource exhaustion, ensures fair usage, and protects against malicious or runaway clients.

### Core Features

- **Rate Limiting**: Token bucket algorithm (configurable per endpoint)
- **User/IP-Based Limits**: Different limits for authenticated users vs anonymous
- **Endpoint-Specific Rules**: Different limits for different operation types
- **Quota Systems**: Monthly/daily limits on resource-heavy operations
- **Backpressure**: Return 429 Too Many Requests with Retry-After header
- **Burst Allowance**: Allow temporary spikes up to configured limit
- **Whitelist**: Bypass rate limits for trusted IPs
- **Metrics**: Track rate limit hits for monitoring
- **Graceful Degradation**: Don't reject, but queue with extended timeout

### Implementation Files

- `src/rate_limiter.py` - Rate limiting middleware and token bucket algorithm
- `src/quota_manager.py` - Quota tracking and enforcement
- `src/resilience.py` - Middleware for Flask integration
- `tests/test_rate_limiting.py` - Rate limit enforcement tests
- `requirements.txt` - Add: flask-limiter>=4.0.0, redis>=5.0.0

### Configuration

- Environment variables:
  - `RATE_LIMIT_ENABLED` - Enable rate limiting (default: true)
  - `RATE_LIMIT_STORAGE` - Redis or memory storage (default: redis)
  - `RATE_LIMIT_DEFAULT` - Default limit (default: 100 requests/minute)
  - `JOB_SUBMISSION_LIMIT` - Max jobs per minute (default: 5)
  - `JOB_SUBMISSION_DAILY` - Max jobs per day (default: 100)
  - `WHITELIST_IPS` - Comma-separated IPs to bypass limits (default: 127.0.0.1)
- Rate limit headers:
  - `X-RateLimit-Limit` - Maximum allowed requests
  - `X-RateLimit-Remaining` - Requests remaining in window
  - `X-RateLimit-Reset` - Unix timestamp when limit resets
  - `Retry-After` - Seconds to wait if rate limited

### Related Domains

- **Browser Frontend** - Client API
- **Background Jobs** - Protected from submission spam
- **Job Persistence** - Tracks quota usage

---

## Overview

API Resilience SHALL protect backend from excessive client requests with rate limiting, quotas, and graceful degradation.

### Requirement: Request Rate Limiting
System MUST enforce per-client rate limits.

#### Scenario: Normal usage within limits
- GIVEN rate limit is 60 requests/minute
- WHEN client makes 30 requests in 1 minute
- THEN system SHALL:
  - Accept all requests with 200/202 responses
  - Include headers:
    - `X-RateLimit-Limit: 60`
    - `X-RateLimit-Remaining: 30`
    - `X-RateLimit-Reset: {unix_timestamp}`
  - Log: normal usage, no action

#### Scenario: Client exceeds request limit
- GIVEN rate limit is 60 requests/minute
- WHEN client makes 61st request within same minute
- THEN system SHALL:
  - Reject request with **429 Too Many Requests**
  - Include header: `Retry-After: 47` (seconds until reset)
  - Return JSON: `{"error": "Rate limit exceeded", "retry_after": 47}`
  - Log: "Rate limit hit from {client_ip}"

#### Scenario: Burst allowance
- GIVEN normal limit is 100/minute, burst limit is 150
- WHEN client makes 120 requests in first 10 seconds
- THEN system SHALL:
  - Allow up to 150 requests in sliding window
  - Requests 1-100: normal rate
  - Requests 101-150: use burst allowance
  - Requests 151+: rejections with 429
  - After 1 minute window: reset to quota

#### Scenario: Per-client identification
- GIVEN multiple clients share same network
- WHEN clients make requests from same IP
- THEN system SHALL:
  - Identify by: IP + User-Agent hash
  - IP 192.168.1.1 with UA "Chrome" = client A
  - IP 192.168.1.1 with UA "Firefox" = client B
  - Separate rate limits for each

### Requirement: Job Submission Quotas
System MUST limit job submission rate.

#### Scenario: Job submission within quota
- GIVEN JOB_SUBMISSION_LIMIT=5/minute, JOB_SUBMISSION_DAILY=100/day
- WHEN user submits 3 enrichment jobs in 1 minute
- THEN system SHALL:
  - Accept all 3 jobs
  - Return: X-RateLimit-Remaining: 2 (for job endpoint)
  - Log quota usage

#### Scenario: Exceed per-minute job quota
- GIVEN JOB_SUBMISSION_LIMIT=5/minute
- WHEN user submits 6th job within same minute
- THEN system SHALL:
  - Reject with 429: "Job submission quota exceeded (5 per minute)"
  - Suggest: "Wait until {time} to submit more jobs"
  - Allow queue jobs to continue executing

#### Scenario: Exceed daily job quota
- GIVEN JOB_SUBMISSION_DAILY=100/day
- WHEN user submits 101st job in calendar day
- THEN system SHALL:
  - Reject with 429: "Daily job quota exceeded (100 per day)"
  - Message: "Quota resets at midnight UTC"
  - Do NOT queue the job

#### Scenario: Quota display in API
- GIVEN user has submitted 45 jobs today
- WHEN GET /api/quotas
- THEN system SHALL return:
  ```json
  {
    "daily_limit": 100,
    "daily_usage": 45,
    "daily_remaining": 55,
    "daily_reset_at": "2026-03-10T00:00:00Z",
    "minute_limit": 5,
    "minute_usage": 2,
    "minute_remaining": 3,
    "minute_reset_at": "2026-03-09T15:31:00Z"
  }
  ```

### Requirement: Adaptive Backpressure
System MUST handle overload gracefully.

#### Scenario: Server under heavy load
- GIVEN job queue has 500+ pending tasks
- WHEN new job submission arrives
- THEN system SHALL:
  - NOT reject immediately (too harsh)
  - Queue the job with extended wait time
  - Set: expected_start_time = now + 2 hours (predicted)
  - Return: `{"status": "queued", "position": 487, "wait_minutes": 120}`
  - Include warning: "Server busy, expect delays"

#### Scenario: Graceful degradation
- GIVEN 95% of resources consumed
- WHEN new read request (GET) arrives
- THEN system SHALL:
  - Accept read requests (low cost)
  - Reject new job submissions (high cost) with 429
  - Current jobs continue executing normally

### Requirement: Token Bucket Algorithm
System MUST efficiently track per-client rates.

#### Scenario: Token bucket refill
- GIVEN token bucket with capacity=60, refill_rate=1 token/second
- WHEN 30 seconds elapse with no requests
- THEN tokens available = min(60, 0 + 30×1) = 30 tokens
- AND next request costs 1 token, leaving 29

#### Scenario: Burst within burst limit
- GIVEN tokens=150, burst_limit=150
- WHEN 100 requests arrive simultaneously
- THEN system SHALL:
  - Spend 100 tokens from bucket
  - Bucket refills at normal rate (1/sec)
  - Requests resume when tokens replenish

### Requirement: API Key & Authorization Limits
System MUST support different limits per user.

#### Scenario: Authenticated user higher quota
- GIVEN anonymous clients: 100 req/min, authenticated: 1000 req/min
- WHEN authenticated user makes request
- THEN system SHALL:
  - Check Authorization header
  - Apply higher limit (1000/min)
  - Include: `X-RateLimit-Limit: 1000` in response

#### Scenario: API key validation
- GIVEN API_KEY=secret-abc-123
- WHEN request includes: `Authorization: Bearer secret-abc-123`
- THEN system SHALL:
  - Validate key (check database/cache)
  - Mark as authenticated
  - Apply authenticated limits
  - Log request with user identity

### Requirement: WhiteList & Blacklist
System MUST support manual limits override.

#### Scenario: Whitelist trusted IP
- GIVEN WHITELIST_IPS=127.0.0.1, 192.168.1.100
- WHEN request from 192.168.1.100 arrives
- THEN system SHALL:
  - Skip rate limiting entirely
  - Accept unlimited requests
  - Log: "Whitelisted IP: {ip}"

#### Scenario: Temporarily block abusive client
- GIVEN client making 1000 requests/minute
- WHEN abuse is detected
- THEN system SHOULD:
  - Automatically add to temporary blacklist
  - Duration: 1 hour
  - Return 403 Forbidden for all requests
  - Admin can manually add/remove from blacklist

### Requirement: Rate Limit Headers
System MUST include standard rate limit headers.

#### Scenario: Standard rate limit response headers
- GIVEN request to any rate-limited endpoint
- WHEN response is generated
- THEN include headers:
  ```
  X-RateLimit-Limit: 60
  X-RateLimit-Remaining: 34
  X-RateLimit-Reset: 1741608660
  ```
- AND client parsing SHALL calculate: reset_time = Unix timestamp

#### Scenario: Retry-After header on 429
- GIVEN client exceeds rate limit
- WHEN 429 response is returned
- THEN include:
  ```
  HTTP/1.1 429 Too Many Requests
  Retry-After: 47
  Content-Type: application/json
  
  {"error": "Rate limit exceeded", "retry_after": 47}
  ```
- AND client SHALL wait ≥47 seconds before retrying

### Requirement: Monitoring & Alerts
System MUST track rate limiting metrics.

#### Scenario: Rate limit metrics logged
- GIVEN rate limiting is active
- WHEN requests are rate limited
- THEN system SHALL collect:
  - Total hits: 1247
  - Unique clients hit: 3
  - Top clients: 192.168.1.100 (450 hits), ...
  - Endpoints with most limits: /api/enrichment/start (89 hits)
  - Daily report in logs: "Rate limited 1247 requests from 3 clients"

#### Scenario: Alert on abuse pattern
- GIVEN 5000+ rate limit hits in 1 hour
- WHEN threshold exceeded
- THEN system SHALL:
  - Log ERROR level alert
  - Send notification: "Rate limit abuse detected"
  - Consider temporary IP blacklist
  - Admin review recommended

### Requirement: Distributed Rate Limiting
System MUST work across multiple servers.

#### Scenario: Multiple servers share rate limit state
- GIVEN 3 Flask servers behind load balancer
- WHEN requests are distributed across servers
- THEN rate limit store (Redis) MUST be shared:
  - All servers increment same counter for client
  - Server 1: 20 requests from 192.168.1.1
  - Server 2: 15 requests from same IP
  - Total: 35 (not per-server limit)
  - Redis key: `rate_limit:{client_id}:{endpoint}`

---

## Related Specifications

- **Background Jobs** - Job submission is rate limited
- **Job Persistence** - Quota usage tracked over time
- **Browser Frontend** - Client respects rate limit headers
