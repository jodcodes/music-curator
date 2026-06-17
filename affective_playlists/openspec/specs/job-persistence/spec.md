# Job Persistence Specifications

## Context & Implementation Guide

Job Persistence provides persistent storage of job metadata, progress, and results for historical tracking and audit trails. This enables job recovery after server restart and provides long-term job history.

### Core Features

- **SQLite/PostgreSQL Database**: Persistent job records with full lifecycle tracking
- **Job History**: Complete record of all submitted jobs with timestamps
- **Result Storage**: Results available for querying after job completion
- **Audit Trail**: Detailed logs of all job state transitions
- **Job Recovery**: Resume interrupted jobs on server restart
- **Indexing**: Fast queries by job_id, status, date range
- **Retention Policy**: Auto-cleanup of old jobs (configurable: 7-30 days)
- **Batch Operations**: Bulk queries for dashboards and reports
- **Transactions**: ACID guarantees for concurrent access

### Implementation Files

- `src/models.py` - SQLAlchemy models: Job, JobResult, JobEvent
- `src/database.py` - Database initialization and migrations
- `src/job_store.py` - Job persistence layer (create, update, query)
- `migrations/` - Alembic migration scripts
- `tests/test_job_persistence.py` - Database transaction tests
- `requirements.txt` - Add: sqlalchemy>=2.0.0, alembic>=1.12.0

### Configuration

- Environment variables:
  - `DATABASE_URL` - Database connection string (default: sqlite:///jobs.db)
  - `JOB_RETENTION_DAYS` - Keep jobs for N days (default: 7)
  - `JOB_CLEANUP_ENABLED` - Auto-cleanup old jobs (default: true)
- Database schema tables:
  - `jobs` - Job metadata (id, status, created_at, completed_at, etc.)
  - `job_results` - Result data (job_id, result_json, metadata)
  - `job_events` - Event log (job_id, event_type, timestamp, details)

### Related Domains

- **Background Jobs** - Creates and updates job records
- **Real-Time Updates** - Job state transitions trigger broadcasts
- **Browser Frontend** - Queries job history via GET /api/jobs

---

## Overview

Job Persistence SHALL provide persistent storage of job state, progress, and results with automatic retention and cleanup.

### Requirement: Database Initialization
System MUST create database schema on startup.

#### Scenario: SQLite database created
- GIVEN application starts with DATABASE_URL not existing
- WHEN Alembic migrations run
- THEN system SHALL:
  - Create jobs.db file in project root
  - Create tables: jobs, job_results, job_events
  - Create indexes on job_id, status, created_at
  - Initialize schema version tracking
- AND database MUST be queryable

#### Scenario: PostgreSQL migration
- GIVEN DATABASE_URL=postgresql://user:pass@host/jobdb
- WHEN application starts
- THEN system SHALL:
  - Connect to PostgreSQL server
  - Run Alembic migrations
  - Create tables in public schema
  - Test connection before marking ready

#### Scenario: Database connection failure
- GIVEN PostgreSQL server is down
- WHEN application startup occurs
- THEN system SHALL:
  - Log error: "Cannot connect to database"
  - Fall back to in-memory job store
  - Display warning: "Job history unavailable"
  - API continues functioning (jobs not persisted)

### Requirement: Job Record Creation
System MUST persist job on submission.

#### Scenario: Create job record on enrichment start
- GIVEN /api/enrichment/start is called
- WHEN job is submitted to queue
- THEN system SHALL INSERT into jobs table:
  ```sql
  INSERT INTO jobs (
    id, type, status, payload, created_at, updated_at, user_agent, client_ip
  ) VALUES (
    'enrichment-123...',
    'enrichment',
    'queued',
    '{"playlist_ids": [...], "sources": [...]}',
    now(),
    now(),
    'Mozilla/5.0...',
    '127.0.0.1'
  )
  ```
- AND job MUST be queryable immediately via GET /api/jobs/{job_id}

#### Scenario: Record metadata with job
- GIVEN job is created
- WHEN payload includes playlist_ids
- THEN system SHALL extract and store:
  - playlist_count: 3
  - track_estimate: 45 (3 playlists × ~15 tracks)
  - source_list: ["spotify", "genius"]
  - storage as JSON: job.payload

### Requirement: Job Status Transitions
System MUST track job state changes.

#### Scenario: Job moves through states
- GIVEN enrichment job is created
- WHEN task progresses
- THEN database MUST record transitions:
  - queued → running (transition saved with timestamp)
  - running → completed (final state with results)
- AND job_events table MUST log:
  ```
  (job_id, event_type, timestamp, details)
  ('enrichment-123', 'status_change', 2026-03-09T15:30:15Z, '{"from": "queued", "to": "running"}')
  ('enrichment-123', 'progress_update', 2026-03-09T15:30:20Z, '{"progress": 25, "current": 5, "total": 20}')
  ```

#### Scenario: Failed job transitions
- GIVEN job fails
- WHEN failure occurs
- THEN database MUST store:
  - status = 'failed'
  - error_message = 'API rate limited'
  - error_code = 'RATE_LIMIT'
  - failed_at = ISO 8601 timestamp
  - attempt_count = 4

### Requirement: Job Result Storage
System MUST persist completed results.

#### Scenario: Store enrichment results
- GIVEN enrichment completes
- WHEN task finishes
- THEN system SHALL INSERT into job_results:
  ```sql
  INSERT INTO job_results (
    job_id, result_json, metadata, stored_at, result_size_bytes
  ) VALUES (
    'enrichment-123...',
    '{"tracks_enriched": 20, "fields": [...], ...}',
    '{"format": "enrichment_v1", "version": 1}',
    now(),
    65536
  )
  ```
- AND result MUST be queryable via GET /api/jobs/{job_id}/results

#### Scenario: Retrieve results after completion
- GIVEN job is completed and results stored
- WHEN GET /api/jobs/{job_id}/results
- THEN system SHALL:
  - Query job_results table
  - Return: `{"job_id": "...", "status": "completed", "result": {...}, "stored_at": "..."}`
  - Include metadata about result
  - Return 200 OK

#### Scenario: Compare large result storage
- GIVEN enrichment completes with 10,000 results
- WHEN results are stored
- THEN system SHALL:
  - Store as compressed JSON
  - Estimate size: ~500KB for 10K tracks
  - Track storage in database: result_size_bytes
  - Alert if over threshold (default: 100MB per job)

### Requirement: Job Query API
System MUST provide queryable job history.

#### Scenario: List all jobs paginated
- GIVEN multiple jobs exist in database
- WHEN GET /api/jobs?page=1&limit=20
- THEN system SHALL return:
  ```json
  {
    "jobs": [
      {
        "job_id": "enrichment-123...",
        "type": "enrichment",
        "status": "completed",
        "created_at": "2026-03-09T15:30:00Z",
        "completed_at": "2026-03-09T15:35:45Z",
        "track_count": 20,
        "results_available": true
      },
      ...
    ],
    "total_count": 47,
    "page": 1,
    "pages": 3
  }
  ```

#### Scenario: Filter jobs by status and date
- GIVEN multiple jobs with different statuses
- WHEN GET /api/jobs?status=completed&date_from=2026-03-01&date_to=2026-03-09
- THEN system SHALL:
  - Filter by status='completed'
  - Filter by created_at BETWEEN dates
  - Return matching jobs ordered by created_at DESC
  - Database query MUST use indexes for performance (<100ms)

#### Scenario: Search jobs by job_id
- GIVEN exact job_id is known
- WHEN GET /api/jobs/{job_id}
- THEN system SHALL return complete job info:
  - Basic info: id, type, status, timestamps
  - Payload: input parameters
  - Progress: current_track, total_tracks (if running)
  - Results: link to results if completed

### Requirement: Job Cleanup & Retention
System MUST enforce retention policy.

#### Scenario: Auto-cleanup old jobs
- GIVEN JOB_RETENTION_DAYS=7
- WHEN daily maintenance job runs at 2 AM
- THEN system SHALL:
  - Query: SELECT * FROM jobs WHERE created_at < now() - 7 days
  - Find jobs older than 7 days
  - Soft-delete: Mark as archived (deleted_at = now)
  - Keep for 30 more days, then hard delete
  - Log: "Archived 3 jobs older than 7 days"

#### Scenario: Manual retention override
- GIVEN important job should be kept longer
- WHEN POST /api/jobs/{job_id}/retain?days=30
- THEN system SHALL:
  - Mark job: retain_until = now() + 30 days
  - Cleanup process MUST skip this job
  - Log: "Job marked for extended retention"

#### Scenario: Cleanup preserves job statistics
- GIVEN job is deleted
- WHEN permanent deletion occurs
- THEN system SHOULD preserve aggregated stats:
  - job_statistics table records: type, status, duration stats
  - Individual job details deleted, stats kept for analysis

### Requirement: Concurrent Access
System MUST handle concurrent job creation/updates safely.

#### Scenario: Multiple workers update same job
- GIVEN 3 workers processing same task
- WHEN all try to update progress simultaneously
- THEN database transactions SHALL:
  - Serialize updates using row-level locking
  - Last update wins (UTC timestamp ordering)
  - No data loss or corruption
  - Query MUST use: `SELECT ... FOR UPDATE` (locking)

#### Scenario: Job completion race condition
- GIVEN job is completing
- WHEN worker and timeout handler both try to finalize
- THEN system SHALL:
  - Use database transaction
  - Check status before updating
  - Only first updater succeeds: status remains 'completed'
  - Second attempt returns: 409 CONFLICT

### Requirement: Database Backups
System MUST support data preservation.

#### Scenario: SQLite backup
- GIVEN production SQLite database
- WHEN daily backup runs (optional cron job)
- THEN system SHALL:
  - Copy jobs.db to backup location
  - Name: `jobs-{date}.db.backup`
  - Keep 7 backups (rolling)
  - Backups include all job records

#### Scenario: PostgreSQL dump
- GIVEN PostgreSQL with production data
- WHEN backup script runs
- THEN system SHALL:
  - Execute: `pg_dump jobdb > backup-{date}.sql`
  - Compress: `gzip backup-{date}.sql`
  - Upload to external storage (optional)
  - Keep last 7 dumps

---

## Related Specifications

- **Background Jobs** - Submits and updates job records
- **Real-Time Updates** - Triggers notification on state changes
- **Browser Frontend** - Queries job history
