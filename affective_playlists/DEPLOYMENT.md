# 🚀 Local Development & Deployment Guide

Complete setup for running **affective_playlists** with all production-ready features locally.

## ✨ Features Included

- ✅ **Database Persistence** (SQLAlchemy ORM + SQLite/PostgreSQL)
- ✅ **Background Jobs** (Celery task queue)
- ✅ **Rate Limiting** (Token bucket algorithm + quotas)
- ✅ **Real-Time Updates** (WebSocket + Server-Sent Events)
- ✅ **409 Passing Tests** (172 new + 237 existing)

---

## 📋 Prerequisites

### Required
- Python 3.10+
- pip/pip3

### Recommended
- Redis 6+ (for Celery broker) - [Install Guide](#redis-installation)
- Git

### Optional (for Database)
- PostgreSQL 12+ (default is SQLite which works out of box)

---

## 🚀 Quick Start (5 minutes)

### 1. Install Dependencies

```bash
# Clone/navigate to project
cd affective_playlists

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Install & Start Redis (One Time)

**macOS:**
```bash
brew install redis
redis-server
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install redis-server
redis-server
```

**Windows (WSL2) or Docker:**
```bash
docker run -d -p 6379:6379 redis:7
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

### 3. Initialize Database

```bash
python run_local.py
# Select: 3 (Database initialization)
```

### 4. Start the Application

**Option A - Web Server Only (no background jobs):**
```bash
python run_local.py
# Select: 1 (Flask)
# Open: http://127.0.0.1:4000
```

**Option B - Web Server + Worker (full stack):**

Terminal 1:
```bash
python run_local.py
# Select: 1 (Flask web server)
```

Terminal 2:
```bash
python run_local.py
# Select: 2 (Celery worker)
```

**Option C - Advanced (Direct Commands):**

Terminal 1 - Web Server:
```bash
python -m src.web_server
```

Terminal 2 - Celery Worker:
```bash
celery -A src.celery_app worker -l info
```

Terminal 3 (Optional) - Celery Events Monitoring:
```bash
celery -A src.celery_app events
```

---

## 🧪 Running Tests

```bash
# Run all tests (409 passing)
python run_local.py
# Select: 4 (Run tests)

# OR with pytest directly
pytest tests/ -v --tb=short

# Skip Celery import tests (if Redis unavailable)
pytest tests/ -k "not (test_celery_initialized or test_job_id_format_enrichment)" -v
```

**Expected Results:**
```
✓ 409 passed (excluding 2 Celery import dependencies)
✓ All database tests passing
✓ All rate limiting tests passing
✓ All real-time tests passing
✓ All existing feature tests passing
```

---

## 🌐 API Endpoints

### Job Management
```
POST /api/enrichment/start          # Create enrichment job → 202 ACCEPTED
GET  /api/enrichment/status?job_id  # Job progress
GET  /api/jobs/{job_id}             # Job details
GET  /api/jobs                      # List all jobs (paginated)
GET  /api/jobs/{job_id}/stream      # SSE stream for real-time updates
```

### Example Requests

**Start enrichment job:**
```bash
curl -X POST http://127.0.0.1:4000/api/enrichment/start \
  -H "Content-Type: application/json" \
  -d '{"playlist_ids": ["pl-1", "pl-2"], "sources": ["spotify"]}'

# Response:
{
  "job_id": "enrichment-1741608660-abc123",
  "status": "queued",
  "total_tracks": 20,
  "success": true
}
```

**Check job status:**
```bash
curl http://127.0.0.1:4000/api/jobs/enrichment-1741608660-abc123

# Response:
{
  "id": "enrichment-1741608660-abc123",
  "type": "enrichment",
  "status": "running",
  "progress": 45,
  "current_track": 9,
  "total_tracks": 20,
  ...
}
```

**Stream real-time updates:**
```bash
curl -N http://127.0.0.1:4000/api/jobs/enrichment-1741608660-abc123/stream

# Receives Server-Sent Events (SSE):
# data: {"event": "job:progress", "progress": 50, ...}
```

---

## 📊 Database

### SQLite (Default)

Automatically created at project root:
```
affective_playlists/
  jobs.db  ← Database file
```

Access via Python:
```python
from src.db import init_db, Job
from src.job_store import get_job_store

# Query jobs
job_store = get_job_store()
total, jobs = job_store.list_jobs(page=1, limit=10)

for job in jobs:
    print(f"{job.id}: {job.status} ({job.progress}%)")
```

Access via CLI:
```bash
sqlite3 jobs.db
sqlite> SELECT id, status, progress FROM jobs;
```

### PostgreSQL (Production)

```bash
# Set environment variable
export DATABASE_URL=postgresql://user:password@localhost/affective_playlists

# Restart Flask server
python run_local.py
```

### Database Tables

- **jobs** - Job metadata and status
- **job_results** - Completed operation results
- **job_events** - Audit trail of all state changes
- **job_statistics** - Aggregated metrics

---

## 🎯 Celery Background Tasks

### Available Tasks

```python
from src.tasks import enrich_metadata, analyze_mood, organize_playlists

# Enrich playlist metadata
enrich_metadata.apply_async(
    args=[job_id, playlist_ids, sources],
    task_id=job_id
)

# Analyze mood/temperament
analyze_mood.apply_async(
    args=[job_id, track_ids, playlist_id],
    task_id=job_id
)

# Organize playlists
organize_playlists.apply_async(
    args=[job_id, playlist_ids, organization_rules],
    task_id=job_id
)
```

### Configuration

```python
# Environment Variables (.env or export)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_WORKER_CONCURRENCY=2
CELERY_TASK_TIMEOUT=3600  # 1 hour
```

### Monitor Tasks

```bash
# See task events in real-time
celery -A src.celery_app events

# Get worker stats
celery -A src.celery_app inspect active
celery -A src.celery_app inspect registered
```

---

## 🔐 Rate Limiting

### Limits Applied

- **Default API**: 100 requests/minute
- **Job submission**: 5 jobs/minute, 100 jobs/day
- **Status polling**: 300 requests/minute
- **Job listing**: 200 requests/minute

### Headers Included

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1741608660
```

### Rate Limit Response (429)

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 47,
  "limit": "100"
}
```

---

## 🔄 Real-Time Updates

### WebSocket Support (SSE Fallback)

The system uses Server-Sent Events (SSE) for real-time updates, with WebSocket-ready architecture.

**Browser Example:**
```javascript
// Connect to stream
const eventSource = new EventSource('/api/jobs/{job_id}/stream');

eventSource.addEventListener('job:progress', (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress}%`);
});

eventSource.addEventListener('job:completed', (event) => {
  console.log('Job finished!');
  eventSource.close();
});

eventSource.addEventListener('job:failed', (event) => {
  console.error('Job failed:', event.data);
});
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=sqlite:///jobs.db
# DATABASE_URL=postgresql://user:pass@localhost/db

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_WORKER_CONCURRENCY=2

# Web Server
WEB_HOST=127.0.0.1
WEB_PORT=4000
WEB_DEBUG=false

# Rate Limiting
RATE_LIMIT_DEFAULT=100
JOB_SUBMISSION_LIMIT_MINUTE=5
JOB_SUBMISSION_LIMIT_DAILY=100
```

### Load from .env

```bash
export $(cat .env | xargs)
python run_local.py
```

---

## 🐛 Troubleshooting

### Issue: "Redis connection refused"

**Solution:**
```bash
# Make sure Redis is running
redis-cli ping
# Should return: PONG

# If not, start Redis:
redis-server

# Or with Docker:
docker run -d -p 6379:6379 redis:7
```

### Issue: "ModuleNotFoundError: No module named 'celery'"

**Solution:**
```bash
pip install celery redis
```

### Issue: "Database locked"

**Solution:**
```bash
# SQLite has concurrent write limits
# Use PostgreSQL for production
export DATABASE_URL=postgresql://user:pass@localhost/db
```

### Issue: "Port 5000 already in use"

**Solution:**
```bash
# Use different port
export WEB_PORT=5001
python run_local.py
```

### Issue: Tests fail with "ImportError"

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Clear Python cache
find . -type d -name '__pycache__' -exec rm -r {} +
```

---

## 🎓 Project Structure

```
affective_playlists/
├── src/
│   ├── web_server.py          # Flask app
│   ├── celery_app.py          # Celery configuration
│   ├── tasks.py               # Background tasks
│   ├── db.py                  # SQLAlchemy ORM
│   ├── job_store.py           # Job CRUD operations
│   ├── rate_limiter.py        # Token bucket limiting
│   ├── realtime.py            # WebSocket/SSE events
│   └── ...
├── tests/
│   ├── test_job_persistence.py   # 48 database tests
│   ├── test_background_jobs.py   # 42 Celery tests
│   ├── test_rate_limiting.py     # 45 rate limit tests
│   ├── test_realtime.py          # 37 WebSocket tests
│   ├── test_web_server.py        # 51 API tests
│   └── ...
├── openspec/specs/
│   ├── job-persistence/
│   ├── background-jobs/
│   ├── api-resilience/
│   └── realtime/
├── docs/TDD_PHASE1_SUMMARY.md    # Implementation summary
├── jobs.db                       # SQLite database (created on init)
├── run_local.py                  # Local deployment script
└── requirements.txt
```

---

## 📈 Next Steps

### Phase 3: Refactoring (Optional)

```
- Add caching layer (Redis caching)
- Distributed rate limiting
- Monitoring/metrics dashboards
- Enhanced error messages
- Documentation expansion
- Performance optimization
```

### Production Deployment

```bash
# Use appropriate WSGI server
gunicorn -w 4 src.web_server:app

# Scale Celery workers
celery -A src.celery_app worker -c 8 -l info -Q enrichment

# Setup monitoring
pip install flower
celery -A src.celery_app flower
# Open: http://localhost:5555
```

---

## 📞 Support

For issues or questions:
1. Check logs in terminal where Flask/Celery is running
2. Review test files for usage examples
3. Check OpenSpec documentation in `openspec/specs/`

---

**Happy deploying! 🚀**
