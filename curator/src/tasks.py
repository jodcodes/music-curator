"""
Background task definitions for Celery.

References: openspec/specs/background-jobs/spec.md
"""

import time
from typing import Any, Dict, List, Optional

from src.celery_app import app
from src.curation_service import CurationService
from src.job_store import get_job_store
from src.logger import setup_logger

logger = setup_logger(__name__)


@app.task(
    bind=True,
    name="curator.tasks.curation:apply_curation",
    base=app.Task,
)
def apply_curation(
    self,
    job_id: str,
    scope: str = "fav_songs",
    max_tracks: Optional[int] = None,
) -> Dict[str, Any]:
    """Apply playlist curation changes through a persisted background job."""
    job_store = get_job_store()
    try:
        job = job_store.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        if scope != "fav_songs":
            raise ValueError(f"Unsupported curation scope: {scope}")

        job_store.update_job_status(job_id, "running")

        service = CurationService()
        if max_tracks is None:
            result = service.apply_fav_songs(confirmed=True)
        else:
            result = service.apply_fav_songs(confirmed=True, max_tracks=max_tracks)
        job_store.store_result(
            job_id,
            result,
            result_metadata={"format": "curation_apply", "version": 1},
        )

        if result.get("success") is True:
            job_store.update_job_status(job_id, "completed")
        else:
            job_store.update_job_status(
                job_id,
                "failed",
                error_message=str(result.get("error") or "Curation apply failed"),
                error_code="CURATION_APPLY_FAILED",
            )

        return result
    except Exception as e:
        logger.error(f"Curation apply job {job_id} failed: {e}")
        job_store.update_job_status(
            job_id,
            "failed",
            error_message=str(e),
            error_code="CURATION_APPLY_ERROR",
        )
        raise


@app.task(
    bind=True,
    name="curator.tasks.enrichment:enrich_metadata",
    base=app.Task,
)
def enrich_metadata(
    self,
    job_id: str,
    playlist_ids: List[str],
    sources: List[str],
) -> Dict[str, Any]:
    """
    Enrich metadata for playlists.

    Args:
        job_id: Job identifier from database
        playlist_ids: List of playlists to enrich
        sources: List of metadata sources (spotify, genius, etc.)

    Returns:
        Result dictionary with enrichment summary
    """
    try:
        job_store = get_job_store()
        job = job_store.get_job(job_id)

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Update status to running
        job_store.update_job_status(job_id, "running")

        # Mock enrichment process
        total_tracks = len(playlist_ids) * 10
        enriched_tracks = []
        fields_added = 0

        for i, playlist_id in enumerate(playlist_ids):
            # Simulate processing tracks in playlist
            for track_idx in range(10):
                track_num = i * 10 + track_idx + 1
                progress = int((track_num / total_tracks) * 100)

                # Update progress
                job_store.update_job_progress(
                    job_id,
                    progress=progress,
                    current_track=track_num,
                    total_tracks=total_tracks,
                    current_operation=f"Processing track {track_num}/{total_tracks}",
                )

                # Simulate metadata enrichment
                time.sleep(0.1)  # Simulate network delay
                enriched_tracks.append(
                    {
                        "track_id": f"track-{track_num}",
                        "fields_added": ["genre", "year", "bpm"],
                    }
                )
                fields_added += 3

        # Store results
        result = {
            "status": "completed",
            "tracks_enriched": total_tracks,
            "fields_added": fields_added,
            "enriched_tracks": enriched_tracks[:5],  # Return sample
            "sources_used": sources,
        }

        job_store.store_result(job_id, result)
        job_store.update_job_status(job_id, "completed")

        logger.info(f"Enrichment job {job_id} completed: {total_tracks} tracks enriched")

        return result
    except Exception as e:
        logger.error(f"Enrichment job {job_id} failed: {e}")
        job_store = get_job_store()
        job_store.update_job_status(
            job_id, "failed", error_message=str(e), error_code="ENRICHMENT_ERROR"
        )
        raise


@app.task(
    bind=True,
    name="curator.tasks.mood:analyze_mood",
    base=app.Task,
)
def analyze_mood(
    self,
    job_id: str,
    track_ids: List[str],
    playlist_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze mood/temperament for tracks.

    Args:
        job_id: Job identifier from database
        track_ids: List of tracks to analyze
        playlist_id: Optional: associate with specific playlist

    Returns:
        Result dictionary with mood classifications
    """
    try:
        job_store = get_job_store()
        job = job_store.get_job(job_id)

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Update status to running
        job_store.update_job_status(job_id, "running")

        # Mock temperament analysis
        temperaments = ["Woe", "Frolic", "Dread", "Malice"]
        analyzed_tracks = []

        for i, track_id in enumerate(track_ids):
            progress = int(((i + 1) / len(track_ids)) * 100)

            # Update progress
            job_store.update_job_progress(
                job_id,
                progress=progress,
                current_track=i + 1,
                total_tracks=len(track_ids),
                current_operation=f"Analyzing track {i + 1}/{len(track_ids)}",
            )

            # Simulate analysis (would call LLM in real implementation)
            time.sleep(0.05)  # Simulate processing
            analyzed_tracks.append(
                {
                    "track_id": track_id,
                    "temperament": temperaments[i % 4],
                    "confidence": 0.85 + (i % 15) / 100,
                }
            )

        # Store results
        result = {
            "status": "completed",
            "tracks_analyzed": len(track_ids),
            "playlist_id": playlist_id,
            "analyzed_tracks": analyzed_tracks,
            "temperament_distribution": {
                "Woe": len([t for t in analyzed_tracks if t["temperament"] == "Woe"]),
                "Frolic": len([t for t in analyzed_tracks if t["temperament"] == "Frolic"]),
                "Dread": len([t for t in analyzed_tracks if t["temperament"] == "Dread"]),
                "Malice": len([t for t in analyzed_tracks if t["temperament"] == "Malice"]),
            },
        }

        job_store.store_result(job_id, result)
        job_store.update_job_status(job_id, "completed")

        logger.info(
            f"Temperament analysis job {job_id} completed: {len(track_ids)} tracks analyzed"
        )

        return result
    except Exception as e:
        logger.error(f"Temperament analysis job {job_id} failed: {e}")
        job_store = get_job_store()
        job_store.update_job_status(
            job_id, "failed", error_message=str(e), error_code="ANALYSIS_ERROR"
        )
        raise


@app.task(
    bind=True,
    name="curator.tasks.organization:organize_playlists",
    base=app.Task,
)
def organize_playlists(
    self,
    job_id: str,
    playlist_ids: List[str],
    organization_rules: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Organize playlists according to rules.

    Args:
        job_id: Job identifier from database
        playlist_ids: Playlists to organize
        organization_rules: Rules for organization (temperament, genre, etc.)

    Returns:
        Result dictionary with organization summary
    """
    try:
        job_store = get_job_store()
        job = job_store.get_job(job_id)

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Update status to running
        job_store.update_job_status(job_id, "running")

        # Mock organization process
        total_playlists = len(playlist_ids)
        organized_items = []

        for i, playlist_id in enumerate(playlist_ids):
            progress = int(((i + 1) / total_playlists) * 100)

            # Update progress
            job_store.update_job_progress(
                job_id,
                progress=progress,
                current_track=i + 1,
                total_tracks=total_playlists,
                current_operation=f"Organizing playlist {i + 1}/{total_playlists}",
            )

            # Simulate organization (dry-run - no actual changes)
            time.sleep(0.2)
            organized_items.append(
                {
                    "playlist_id": playlist_id,
                    "moves_planned": min(5, (i + 1) % 7),
                    "destination_playlists": [f"organized-{i % 3}"],
                }
            )

        # Store results
        result = {
            "status": "completed",
            "playlists_processed": total_playlists,
            "total_moves_planned": sum(item["moves_planned"] for item in organized_items),
            "organized_items": organized_items,
            "rules_applied": organization_rules,
        }

        job_store.store_result(job_id, result)
        job_store.update_job_status(job_id, "completed")

        logger.info(f"Organization job {job_id} completed: {total_playlists} playlists organized")

        return result
    except Exception as e:
        logger.error(f"Organization job {job_id} failed: {e}")
        job_store = get_job_store()
        job_store.update_job_status(
            job_id, "failed", error_message=str(e), error_code="ORGANIZATION_ERROR"
        )
        raise


@app.task(name="curator.tasks.cleanup:cleanup_old_jobs")
def cleanup_old_jobs(retention_days: int = 7) -> Dict[str, Any]:
    """
    Clean up old jobs from database.

    Args:
        retention_days: Retain jobs for N days

    Returns:
        Cleanup summary
    """
    try:
        job_store = get_job_store()
        count = job_store.cleanup_old_jobs(retention_days=retention_days)

        logger.info(f"Cleanup job completed: archived {count} jobs")

        return {"status": "completed", "jobs_archived": count, "retention_days": retention_days}
    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")
        raise
