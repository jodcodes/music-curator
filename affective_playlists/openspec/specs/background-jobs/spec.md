# Background Jobs (Task Queue) Specifications

## Context & Implementation Guide

Background Jobs provides asynchronous task processing for long-running operations (enrichment, analysis, organization) using a task queue system. This decouples request handling from operation execution, enables progress tracking, and prevents request timeouts.

### Core Features

- **Task Queue**: Celery-based distributed task processing with Redis/RabbitMQ broker
- **Job Tracking**: Unique job IDs for every long-running operation
- **Async Operations**: Non-blocking enrichment, analysis, and organization tasks
- **Priority Queues**: Separate queues for critical vs background operations
- **Retry Logic**: Automatic retries with exponential backoff for failed tasks
- **Worker Pool**: Scalable worker processes for parallel execution
- **Status Persistence**: Job state persisted to database throughout lifecycle
- **Cancellation**: Ability to cancel running jobs cleanly
- **Result Storage**: Results available after job completion

### Implementation Files

- `src/tasks.py` - Celery task definitions for enrichment, analysis, organization
- `src/celery_app.py` - Celery application configuration and initialization
- `src/celery_config.py` - Worker configuration, queue definitions, retry policies
- `tests/test_background_jobs.py` - Task queue tests including job lifecycle
- `requirements.txt` - Add: celery>=5.3.0, redis>=5.0.0 or kombu>=5.3.0

### Configuration

- Environment variables:
  - `CELERY_BROKER_URL` - Task broker URL (default: redis://localhost:6379/0)
  - `CELERY_RESULT_BACKEND` - Result store URL (default: redis://localhost:6379/1)
  - `CELERY_WORKER_CONCURRENCY` - Number of parallel worker processes (default: 2)
  - `CELERY_TASK_TIMEOUT` - Task execution timeout in seconds (default: 3600)
- Celery task naming convention:
  - `affective_playlists.tasks.enrichment:enrich_metadata`
  - `affective_playlists.tasks.temperament:analyze_mood`
  - `affective_playlists.tasks.organization:organize_playlists`

### Related Domains

- **Browser Frontend** - Submits jobs and polls for status
- **Job Persistence** - Stores job history and results
- **Real-Time Updates** - Notifies frontend when jobs update

---

## Overview

Background Jobs SHALL provide asynchronous task execution for long-running operations with progress tracking, error handling, and result persistence.

### Requirement: Task Queue Initialization
The system MUST initialize task queue on startup with configured broker.

#### Scenario: Celery initialized with Redis broker
- GIVEN Redis broker is running on localhost:6379
- WHEN application starts
- THEN Celery SHALL connect to Redis broker
- AND worker pool SHALL be ready to process tasks
- AND status MUST be queryable via /api/health

#### Scenario: Broker connection fails
- GIVEN Redis broker is unavailable
- WHEN application startup is attempted
- THEN system SHALL log warning but continue
- AND API requests SHALL execute synchronously as fallback
- AND user SHALL see message: "Background tasks unavailable, running inline"

#### Scenario: Worker process started
- GIVEN `celery -A src.celery_app worker` is executed
- WHEN workers start
- THEN system SHALL display: "Celery worker started with N concurrency"
- AND worker SHALL poll for tasks from broker

### Requirement: Job Submission
The system MUST accept and queue long-running operations asynchronously.

#### Scenario: Submit enrichment task
- GIVEN user requests metadata enrichment
- WHEN /api/enrichment/start is called
- THEN system SHALL:
  - Create unique job_id (format: `enrichment-{timestamp}-{uuid}`)
  - Submit task to Celery queue: `affective_playlists.tasks.enrichment:enrich_metadata`
  - Return immediately with 202 ACCEPTED status
  - Return response: `{"job_id": "enrichment-123...", "status": "queued", "track_count": N}`
- AND database MUST persist job record with state="queued"

#### Scenario: Submit analysis task with payload
- GIVEN user clicks "Analyze Mood"
- WHEN POST /api/temperament/classify with `{"track_ids": [...], "playlist_id": "pl-1"}`
- THEN system SHALL:
  - Parse and validate inputs
  - Create job with metadata: playlist_id, track_count
  - Submit task: `affective_playlists.tasks.temperament:analyze_mood`
  - Return 202 ACCEPTED with job_id

#### Scenario: Task queue is full
- GIVEN task queue has 1000+ pending tasks
- WHEN new task submission is attempted
- THEN system SHALL accept task (queue is theoretically unlimited)
- AND return job_id with status="queued"
- AND task SHALL execute when worker becomes available

### Requirement: Task Execution
Worker processes MUST execute tasks and track progress.

#### Scenario: Enrichment task executes
- GIVEN enrichment task is dequeued by worker
- WHEN task starts executing
- THEN database job state MUST be updated to "running"
- AND task MUST update progress every 5-10 seconds
- AND task SHALL emit progress events: `{"progress": 25, "current_track": 5, "total": 20}`

#### Scenario: Task completes successfully
- GIVEN enrichment task finishes
- WHEN task executes final step
- THEN database MUST store:
  - status = "completed"
  - result = enrichment results JSON
  - duration_seconds = elapsed time
  - completion_time = ISO 8601 timestamp
- AND result MUST be queryable for 7 days

#### Scenario: Task fails with error
- GIVEN task encounters exception during execution
- WHEN error occurs
- THEN Celery SHALL:
  - Log error with full traceback
  - Update database: status="failed", error_message="..."
  - Retry task with exponential backoff (4 retries total)
  - Max retry delay: 5 minutes between attempts
- AND frontend MUST show error after 4 failures

#### Scenario: Task timeout occurs
- GIVEN task execution exceeds timeout (3600 seconds default)
- WHEN timeout triggers
- THEN Celery SHALL:
  - Kill running task
  - Update database: status="timeout"
  - NOT retry (timeout not retryable)
  - Return error to frontend

### Requirement: Job Cancellation
System MUST allow cancelling queued or running jobs.

#### Scenario: Cancel queued job
- GIVEN job is queued (status="queued")
- WHEN POST /api/jobs/{job_id}/cancel
- THEN system SHALL:
  - Revoke task from Celery queue
  - Update database: status="cancelled", cancelled_time=now
  - Return 200 OK: `{"status": "cancelled", "message": "Job cancelled successfully"}`

#### Scenario: Cancel running job
- GIVEN job is executing (status="running")
- WHEN POST /api/jobs/{job_id}/cancel
- THEN system SHALL:
  - Send SIGTERM to worker executing task
  - Set database flag: status="cancelling"
  - Within 5 seconds, update to status="cancelled"
  - Return 200 OK

#### Scenario: Cancel completed job
- GIVEN job is already complete
- WHEN POST /api/jobs/{job_id}/cancel
- THEN system SHALL return 400 BAD REQUEST:
  - `{"error": "Cannot cancel completed job", "status": "completed"}`

### Requirement: Task Retries
Failed tasks MUST retry with exponential backoff.

#### Scenario: Task fails and retries
- GIVEN task execution fails (e.g., API timeout)
- WHEN failure occurs
- THEN Celery SHALL:
  - Log failure with details
  - Wait: 30 seconds, then retry (attempt 2)
  - Wait: 60 seconds, then retry (attempt 3)
  - Wait: 120 seconds, then retry (attempt 4)
  - If all retries fail: status="failed"
- AND frontend MUST see "Retrying... (attempt 2/4)"

#### Scenario: Transient errors retry, hard errors don't
- GIVEN task fails due to different reasons
- WHEN failure occurs
- THEN system SHALL:
  - Retry on: network timeouts, rate limits, temporary service outages
  - NOT retry on: validation errors, missing data, permissions
  - Log classification: "TRANSIENT" vs "PERMANENT"

### Requirement: Worker Scalability
System MUST support running multiple workers.

#### Scenario: Multiple workers process tasks
- GIVEN 3 Celery worker processes running
- WHEN 10 tasks are submitted
- THEN workers SHALL distribute tasks among themselves
- AND tasks SHALL execute in parallel (up to 3 concurrently)
- AND status polling SHALL show correct per-task progress

#### Scenario: Worker dies
- GIVEN 2 workers are healthy, 1 worker crashes
- WHEN worker process terminates unexpectedly
- THEN system SHALL:
  - Log error: "Worker died unexpectedly"
  - Reassign pending tasks from dead worker to live workers
  - Remaining capacity: 2x worker concurrency
  - Frontend MUST NOT see interruption if task not started

---

## Related Specifications

- **Job Persistence** - Stores job state in database
- **Real-Time Updates** - Notifies frontend of job status changes
- **Browser Frontend** - Submits and monitors jobs
