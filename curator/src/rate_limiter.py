"""
Rate limiting and quota enforcement for API resilience.

Token bucket algorithm with per-client and per-endpoint limits.

References: openspec/specs/api-resilience/spec.md
"""

import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional, Tuple

from flask import jsonify, request

from src.logger import setup_logger

logger = setup_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter with per-client tracking."""

    def __init__(
        self,
        default_limit: int = 100,
        window_seconds: int = 60,
        burst_limit: Optional[int] = None,
    ):
        """Initialize rate limiter.

        Args:
            default_limit: Requests per window
            window_seconds: Time window in seconds
            burst_limit: Maximum burst allowance (default: 1.5x limit)
        """
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit or int(default_limit * 1.5)

        # Per-client state: {client_id: {tokens, last_refill}}
        self._state: Dict[str, Dict] = {}

    def _get_client_id(self) -> str:
        """Get unique client identifier from request."""
        user_agent = request.headers.get("User-Agent", "unknown")
        ip = request.remote_addr or "unknown"
        # Combine IP + User-Agent hash
        return f"{ip}:{hash(user_agent) % 100000}"

    def _get_bucket(self, client_id: str) -> Dict:
        """Get or create token bucket for client."""
        if client_id not in self._state:
            self._state[client_id] = {
                "tokens": self.burst_limit,
                "last_refill": time.time(),
            }
        return self._state[client_id]

    def _refill_tokens(self, bucket: Dict) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket["last_refill"]

        # Refill rate: tokens per second
        refill_rate = self.default_limit / self.window_seconds
        new_tokens = elapsed * refill_rate

        # Cap at burst limit
        bucket["tokens"] = min(self.burst_limit, bucket["tokens"] + new_tokens)
        bucket["last_refill"] = now

    def is_allowed(self, client_id: Optional[str] = None) -> Tuple[bool, Dict]:
        """Check if request is allowed.

        Args:
            client_id: Client identifier (auto-detect if None)

        Returns:
            Tuple of (allowed, headers_dict)
        """
        if client_id is None:
            client_id = self._get_client_id()

        bucket = self._get_bucket(client_id)
        self._refill_tokens(bucket)

        allowed = bucket["tokens"] >= 1.0
        if allowed:
            bucket["tokens"] -= 1.0

        # Calculate reset time
        now = time.time()
        reset_time = int(now + self.window_seconds)

        return allowed, {
            "X-RateLimit-Limit": str(self.default_limit),
            "X-RateLimit-Remaining": str(max(0, int(bucket["tokens"]))),
            "X-RateLimit-Reset": str(reset_time),
        }

    def cleanup_old_clients(self, max_age_hours: int = 24) -> None:
        """Remove old client entries to prevent memory leak."""
        now = time.time()
        max_age_seconds = max_age_hours * 3600

        clients_to_remove = [
            cid
            for cid, bucket in self._state.items()
            if now - bucket["last_refill"] > max_age_seconds
        ]

        for cid in clients_to_remove:
            del self._state[cid]

        if clients_to_remove:
            logger.debug(f"Cleaned up {len(clients_to_remove)} old rate limit buckets")


class QuotaManager:
    """Manage per-user quotas for resource-heavy operations."""

    def __init__(self):
        """Initialize quota manager."""
        # Per-user quota: {user_id: {daily: count, minute: count, reset_times}}
        self._quotas: Dict[str, Dict] = {}

        # Configuration
        self.job_limit_per_minute = 5
        self.job_limit_per_day = 100

    def _get_user_id(self) -> str:
        """Get user identifier (IP for now)."""
        return request.remote_addr or "unknown"

    def _get_quota_entry(self, user_id: str) -> Dict:
        """Get or create quota entry for user."""
        if user_id not in self._quotas:
            now = time.time()
            self._quotas[user_id] = {
                "daily_count": 0,
                "daily_reset": now + 86400,  # 24 hours
                "minute_count": 0,
                "minute_reset": now + 60,  # 1 minute
            }
        return self._quotas[user_id]

    def check_job_quota(self, user_id: Optional[str] = None) -> Tuple[bool, Dict]:
        """Check if user can submit a job.

        Args:
            user_id: User identifier (auto-detect if None)

        Returns:
            Tuple of (allowed, quota_dict)
        """
        if user_id is None:
            user_id = self._get_user_id()

        quota = self._get_quota_entry(user_id)
        now = time.time()

        # Reset counters if windows passed
        if now > quota["minute_reset"]:
            quota["minute_count"] = 0
            quota["minute_reset"] = now + 60

        if now > quota["daily_reset"]:
            quota["daily_count"] = 0
            quota["daily_reset"] = now + 86400

        # Check limits
        minute_ok = quota["minute_count"] < self.job_limit_per_minute
        daily_ok = quota["daily_count"] < self.job_limit_per_day

        allowed = minute_ok and daily_ok

        if allowed:
            quota["minute_count"] += 1
            quota["daily_count"] += 1

        return allowed, {
            "minute_limit": self.job_limit_per_minute,
            "minute_remaining": max(0, self.job_limit_per_minute - quota["minute_count"]),
            "minute_reset_at": datetime.fromtimestamp(quota["minute_reset"]).isoformat(),
            "daily_limit": self.job_limit_per_day,
            "daily_remaining": max(0, self.job_limit_per_day - quota["daily_count"]),
            "daily_reset_at": datetime.fromtimestamp(quota["daily_reset"]).isoformat(),
        }


# Global instances
_rate_limiters: Dict[str, RateLimiter] = {}
_quota_manager = QuotaManager()


def get_rate_limiter(endpoint: str, limit: int = 100) -> RateLimiter:
    """Get rate limiter for endpoint."""
    if endpoint not in _rate_limiters:
        _rate_limiters[endpoint] = RateLimiter(default_limit=limit)
    return _rate_limiters[endpoint]


def get_quota_manager() -> QuotaManager:
    """Get quota manager singleton."""
    return _quota_manager


def rate_limit(limit: int = 100, burst: Optional[int] = None):
    """Decorator for rate-limited endpoints.

    Args:
        limit: Requests per minute
        burst: Max burst limit (default: 1.5x limit)
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            limiter = get_rate_limiter(f.__name__, limit=limit)
            allowed, headers = limiter.is_allowed()

            if not allowed:
                # Calculate retry-after
                now = time.time()
                reset_time = int(headers["X-RateLimit-Reset"])
                retry_after = max(1, reset_time - int(now))

                response = jsonify(
                    {
                        "error": "Rate limit exceeded",
                        "retry_after": retry_after,
                        "limit": headers["X-RateLimit-Limit"],
                    }
                )
                response.status_code = 429
                response.headers.update({"Retry-After": str(retry_after)})
                response.headers.update(headers)
                return response

            # Add headers to response
            result = f(*args, **kwargs)
            if isinstance(result, tuple):
                response, status = result[0], result[1]
                if isinstance(response, dict):
                    response = jsonify(response)
            else:
                response = result
                status = 200

            if hasattr(response, "headers"):
                response.headers.update(headers)

            return (response, status) if isinstance(result, tuple) else response

        return decorated_function

    return decorator


def check_job_quota():
    """Decorator for job submission endpoints (stricter quota)."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            quota_manager = get_quota_manager()
            allowed, quota_info = quota_manager.check_job_quota()

            if not allowed:
                response = jsonify(
                    {
                        "error": "Job submission quota exceeded",
                        "quota": quota_info,
                    }
                )
                response.status_code = 429
                return response

            # Call the function (don't pass quota_info as it may not be expected)
            result = f(*args, **kwargs)
            return result

        return decorated_function

    return decorator
