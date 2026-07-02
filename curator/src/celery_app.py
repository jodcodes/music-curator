"""
Celery background task queue application.

Provides asynchronous task execution for long-running operations.

References: openspec/specs/background-jobs/spec.md
"""

import os

from celery import Celery
from kombu import Queue

from src.logger import setup_logger

logger = setup_logger(__name__)

# Initialize Celery app
app = Celery("curator")

# Configuration
app.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task configuration
    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIMEOUT", "3600")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_TIMEOUT", "3600")) - 60,
    task_default_queue="default",
    task_default_routing_key="default",
    # Retry configuration
    task_autoretry_for=(Exception,),
    task_max_retries=4,
    task_default_retry_delay=30,
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Concurrency
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "2")),
    # Task routing
    task_routes={
        "curator.tasks.curation:apply_curation": {"queue": "default"},
        "curator.tasks.enrichment:enrich_metadata": {"queue": "enrichment"},
        "curator.tasks.temperament:analyze_mood": {"queue": "mood"},
        "curator.tasks.organization:organize_playlists": {"queue": "organization"},
        "curator.tasks.cleanup:cleanup_old_jobs": {"queue": "background"},
    },
)

# Task queue definitions
app.conf.task_queues = (
    Queue("enrichment", routing_key="enrichment"),
    Queue("temperament", routing_key="temperament"),
    Queue("organization", routing_key="organization"),
    Queue("background", routing_key="background"),
    Queue("default", routing_key="default"),
)

if __name__ == "__main__":
    app.start()
