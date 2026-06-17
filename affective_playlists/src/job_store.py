"""
Job persistence layer - CRUD operations for job records.

References: openspec/specs/job-persistence/spec.md
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.db import Job, JobEvent, JobResult, JobStatistics, get_session, utc_now
from src.logger import setup_logger

logger = setup_logger(__name__)


class JobStore:
    """Repository for job persistence operations."""

    def __init__(self, session: Optional[Session] = None):
        """Initialize job store.

        Args:
            session: SQLAlchemy session (creates new if None)
        """
        self.session = session or get_session()

    def create_job(
        self,
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Job:
        """Create new job record.

        Args:
            job_id: Unique job identifier
            job_type: Type of job (enrichment, temperament, organization)
            payload: Input parameters as dictionary
            user_agent: Client user agent string
            client_ip: Client IP address

        Returns:
            Created Job record
        """
        try:
            job = Job(
                id=job_id,
                type=job_type,
                status="queued",
                payload=payload,
                user_agent=user_agent,
                client_ip=client_ip,
                created_at=utc_now(),
                updated_at=utc_now(),
            )

            self.session.add(job)
            self.session.commit()

            logger.info(f"Created job: {job_id}")

            # Log event
            self._log_event(job_id, "status_change", {"from": None, "to": "queued"})

            return job
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to create job {job_id}: {e}")
            raise

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job record or None if not found
        """
        return self.session.query(Job).filter(Job.id == job_id).first()

    def update_job_status(
        self,
        job_id: str,
        new_status: str,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> Optional[Job]:
        """Update job status.

        Args:
            job_id: Job identifier
            new_status: New status value
            error_message: Error message if failed
            error_code: Error code if failed

        Returns:
            Updated Job record or None
        """
        try:
            job = self.get_job(job_id)
            if not job:
                logger.warning(f"Job not found: {job_id}")
                return None

            old_status = job.status
            job.status = new_status
            job.updated_at = utc_now()

            if new_status == "running" and job.started_at is None:
                job.started_at = utc_now()
            elif new_status in ["completed", "failed", "cancelled", "timeout"]:
                job.completed_at = utc_now()

            if error_message:
                job.error_message = error_message
            if error_code:
                job.error_code = error_code

            self.session.commit()
            logger.info(f"Updated job {job_id} status: {old_status} → {new_status}")

            # Log event
            self._log_event(job_id, "status_change", {"from": old_status, "to": new_status})

            return job
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to update job status {job_id}: {e}")
            raise

    def update_job_progress(
        self,
        job_id: str,
        progress: int,
        current_track: int,
        total_tracks: int,
        current_operation: str = "",
    ) -> Optional[Job]:
        """Update job progress.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            current_track: Current track being processed
            total_tracks: Total tracks to process
            current_operation: Description of current operation

        Returns:
            Updated Job record or None
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return None

            job.progress = min(100, max(0, progress))
            job.current_track = current_track
            job.total_tracks = total_tracks
            job.updated_at = utc_now()

            self.session.commit()

            # Log event
            self._log_event(
                job_id,
                "progress_update",
                {
                    "progress": progress,
                    "current_track": current_track,
                    "total": total_tracks,
                    "operation": current_operation,
                },
            )

            return job
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to update progress for {job_id}: {e}")
            raise

    def store_result(
        self,
        job_id: str,
        result_json: Dict[str, Any],
        result_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[JobResult]:
        """Store job result.

        Args:
            job_id: Job identifier
            result_json: Result data
            result_metadata: Optional metadata (format version, etc.)

        Returns:
            Created JobResult record or None
        """
        try:
            import json

            result_obj = JobResult(
                job_id=job_id,
                result_json=result_json,
                result_metadata=result_metadata or {"format": "auto", "version": 1},
                stored_at=utc_now(),
                result_size_bytes=len(json.dumps(result_json)),
            )

            self.session.add(result_obj)
            self.session.commit()

            logger.info(f"Stored result for job {job_id}")

            return result_obj
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to store result for {job_id}: {e}")
            raise

    def get_result(self, job_id: str) -> Optional[JobResult]:
        """Get job result.

        Args:
            job_id: Job identifier

        Returns:
            JobResult or None if not found
        """
        return self.session.query(JobResult).filter(JobResult.job_id == job_id).first()

    def list_jobs(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> tuple:
        """List jobs with pagination and filtering.

        Args:
            page: Page number (1-indexed)
            limit: Results per page
            status: Filter by status
            job_type: Filter by job type
            date_from: Filter by created_at >= date_from
            date_to: Filter by created_at <= date_to

        Returns:
            Tuple of (total_count, jobs_list)
        """
        try:
            query = self.session.query(Job).filter(Job.deleted_at.is_(None))

            if status:
                query = query.filter(Job.status == status)
            if job_type:
                query = query.filter(Job.type == job_type)
            if date_from:
                query = query.filter(Job.created_at >= date_from)
            if date_to:
                query = query.filter(Job.created_at <= date_to)

            # Get total count
            total_count = query.count()

            # Get paginated results
            offset = (page - 1) * limit
            jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

            return total_count, jobs
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return 0, []

    def delete_job(self, job_id: str, soft_delete: bool = True) -> bool:
        """Delete job (soft or hard).

        Args:
            job_id: Job identifier
            soft_delete: If True, mark as deleted; if False, hard delete

        Returns:
            True if successful, False otherwise
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return False

            if soft_delete:
                job.deleted_at = utc_now()
                logger.info(f"Soft deleted job: {job_id}")
            else:
                self.session.delete(job)
                logger.info(f"Hard deleted job: {job_id}")

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def cleanup_old_jobs(self, retention_days: int = 7) -> int:
        """Soft delete jobs older than retention period.

        Args:
            retention_days: Keep jobs for N days (default: 7)

        Returns:
            Number of jobs archived
        """
        try:
            now = utc_now()
            cutoff_date = now - timedelta(days=retention_days)

            # Find old jobs without retain_until override
            old_jobs = (
                self.session.query(Job)
                .filter(
                    Job.created_at < cutoff_date,
                    Job.deleted_at.is_(None),
                    (Job.retain_until.is_(None) | (Job.retain_until < now)),
                )
                .all()
            )

            for job in old_jobs:
                job.deleted_at = utc_now()

            self.session.commit()
            logger.info(f"Archived {len(old_jobs)} jobs older than {retention_days} days")

            return len(old_jobs)
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0

    def set_retention(self, job_id: str, days: int) -> bool:
        """Set extended retention for job.

        Args:
            job_id: Job identifier
            days: Number of days to retain

        Returns:
            True if successful
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return False

            job.retain_until = utc_now() + timedelta(days=days)
            self.session.commit()
            logger.info(f"Set retention for {job_id} to {days} days")

            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to set retention for {job_id}: {e}")
            return False

    def _log_event(self, job_id: str, event_type: str, details: Optional[Dict] = None) -> None:
        """Log job event to audit trail.

        Args:
            job_id: Job identifier
            event_type: Type of event
            details: Event-specific details
        """
        try:
            event = JobEvent(
                job_id=job_id,
                event_type=event_type,
                timestamp=utc_now(),
                details=details,
            )
            self.session.add(event)
            self.session.commit()
        except Exception as e:
            logger.warning(f"Failed to log event for {job_id}: {e}")


# Singleton instance
_job_store = None


def get_job_store() -> JobStore:
    """Get job store singleton."""
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
