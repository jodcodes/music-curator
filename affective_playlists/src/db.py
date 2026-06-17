"""
Database initialization and ORM models for job persistence.

References: openspec/specs/job-persistence/spec.md
"""

import os
from datetime import datetime, timezone
from typing import Any, Optional, Type

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.logger import setup_logger

logger = setup_logger(__name__)

Base: Type[Any] = declarative_base()  # type: ignore[assignment]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Job(Base):
    """Job record - tracks a single submitted job."""

    __tablename__ = "jobs"

    # Primary key
    id = Column(String(128), primary_key=True, index=True)

    # Job metadata
    type = Column(String(50), nullable=False, index=True)  # enrichment, temperament, organization
    status = Column(
        String(20), nullable=False, index=True, default="queued"
    )  # queued, running, completed, failed, cancelled, timeout

    # Job content
    payload = Column(JSON, nullable=True)  # Input parameters

    # Timing
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete timestamp

    # Progress tracking
    progress = Column(Integer, default=0)  # 0-100
    current_track = Column(Integer, default=0)
    total_tracks = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    attempt_count = Column(Integer, default=0)

    # Client info
    user_agent = Column(String(512), nullable=True)
    client_ip = Column(String(45), nullable=True)

    # Extended retention
    retain_until = Column(DateTime, nullable=True)  # For manual retention override

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.type}, status={self.status})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "current_track": self.current_track,
            "total_tracks": self.total_tracks,
            "error_message": self.error_message,
            "error_code": self.error_code,
        }


class JobResult(Base):
    """Job result - stores completed results."""

    __tablename__ = "job_results"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(128), index=True, nullable=False)

    # Result data
    result_json = Column(JSON, nullable=True)  # Actual results
    result_metadata = Column(JSON, nullable=True)  # result format version, etc.

    # Storage tracking
    stored_at = Column(DateTime, nullable=False, default=utc_now)
    result_size_bytes = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<JobResult(job_id={self.job_id}, size={self.result_size_bytes})>"


class Playlist(Base):
    """Cached playlist metadata from Apple Music."""

    __tablename__ = "playlists"

    # Primary key - use persistent ID from Music.app
    persistent_id = Column(String(128), primary_key=True, index=True)

    # Playlist metadata
    name = Column(String(512), index=True, nullable=False)
    track_count = Column(Integer, default=0)
    genre = Column(String(128), nullable=True)
    created_date = Column(DateTime, nullable=True)

    # Status tracking
    classified = Column(String(50), nullable=True, default=None)  # genre classification result
    enriched = Column(String(50), default="pending")  # pending, in_progress, completed, failed
    last_synced = Column(
        DateTime, nullable=False, default=utc_now, onupdate=utc_now
    )
    last_modified = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Playlist(id={self.persistent_id}, name={self.name}, tracks={self.track_count})>"

    def to_dict(self):
        """Convert to frontend API format."""
        return {
            "id": self.persistent_id,
            "name": self.name,
            "track_count": self.track_count,
            "genre": self.genre,
            "classified": self.classified is not None,
            "created_date": self.created_date.isoformat() if self.created_date else None,
        }


class JobEvent(Base):
    """Job event - audit log of all state changes."""

    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(128), index=True, nullable=False)

    # Event tracking
    event_type = Column(String(50), nullable=False)  # status_change, progress_update, error, etc.
    timestamp = Column(DateTime, nullable=False, default=utc_now, index=True)
    details = Column(JSON, nullable=True)  # event-specific data

    def __repr__(self):
        return f"<JobEvent(job_id={self.job_id}, event={self.event_type})>"


class JobStatistics(Base):
    """Job statistics - aggregated metrics for deleted jobs."""

    __tablename__ = "job_statistics"

    id = Column(Integer, primary_key=True)
    job_type = Column(String(50), nullable=False, unique=True)  # enrichment, temperament, etc.

    # Aggregated metrics
    total_completed = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    total_cancelled = Column(Integer, default=0)
    total_timeout = Column(Integer, default=0)

    avg_duration_seconds = Column(Integer, nullable=True)
    min_duration_seconds = Column(Integer, nullable=True)
    max_duration_seconds = Column(Integer, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<JobStatistics(type={self.job_type}, completed={self.total_completed})>"


# Database initialization
def get_database_url() -> str:
    """Get database URL from environment or default."""
    default_url = "sqlite:///jobs.db"
    return os.getenv("DATABASE_URL", default_url)


def init_db(database_url: Optional[str] = None) -> tuple:
    """Initialize database and return engine and session factory.

    Args:
        database_url: Database connection string (uses env var or default if None)

    Returns:
        Tuple of (engine, SessionLocal)
    """
    if database_url is None:
        database_url = get_database_url()

    try:
        logger.info(f"Initializing database: {database_url}")

        # Create engine
        engine = create_engine(
            database_url,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            connect_args=({"check_same_thread": False} if "sqlite" in database_url else {}),
        )

        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        return engine, SessionLocal
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


# Global database connection
_engine = None
_SessionLocal = None


def get_session():
    """Get database session."""
    global _SessionLocal
    if _SessionLocal is None:
        _, _SessionLocal = init_db()
    return _SessionLocal()


def setup_database():
    """Setup database on application startup."""
    global _engine, _SessionLocal
    try:
        _engine, _SessionLocal = init_db()
        logger.info("Database setup completed")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        # Continue without database (fallback to in-memory)
