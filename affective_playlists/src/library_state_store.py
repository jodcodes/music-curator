"""
Persistent state store for library runs, dedupe history, and product cache.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.db import (
    LibraryRun,
    StateCacheEntry,
    TrackDedupHistory,
    get_session,
    utc_now,
)
from src.logger import setup_logger

logger = setup_logger(__name__)


class LibraryStateStore:
    """Repository for persistent library state."""

    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    @staticmethod
    def create_run_id(run_type: str) -> str:
        return f"{run_type}-{uuid.uuid4().hex[:12]}"

    def create_run(
        self,
        run_type: str,
        target: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LibraryRun:
        run = LibraryRun(
            id=self.create_run_id(run_type),
            run_type=run_type,
            target=target,
            payload=payload or {},
            status="running",
            created_at=utc_now(),
            started_at=utc_now(),
        )
        self.session.add(run)
        self.session.commit()
        return run

    def finish_run(
        self,
        run_id: str,
        status: str,
        processed_items: int = 0,
        skipped_items: int = 0,
        error_items: int = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[LibraryRun]:
        run = self.session.query(LibraryRun).filter(LibraryRun.id == run_id).first()
        if run is None:
            return None

        run.status = status
        run.processed_items = processed_items
        run.skipped_items = skipped_items
        run.error_items = error_items
        run.completed_at = utc_now()
        if details is not None:
            run.details = details
        self.session.commit()
        return run

    def list_runs(
        self, limit: int = 10, run_type: Optional[str] = None
    ) -> List[LibraryRun]:
        query = self.session.query(LibraryRun)
        if run_type:
            query = query.filter(LibraryRun.run_type == run_type)
        return query.order_by(LibraryRun.created_at.desc()).limit(limit).all()

    def has_track(self, scope: str, track_key: str) -> bool:
        return (
            self.session.query(TrackDedupHistory)
            .filter(
                TrackDedupHistory.scope == scope,
                TrackDedupHistory.track_key == track_key,
            )
            .first()
            is not None
        )

    def record_track(
        self,
        scope: str,
        track_key: str,
        artist: Optional[str] = None,
        title: Optional[str] = None,
        album: Optional[str] = None,
        filepath: Optional[str] = None,
        run_id: Optional[str] = None,
        skip_reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> TrackDedupHistory:
        existing = (
            self.session.query(TrackDedupHistory)
            .filter(
                TrackDedupHistory.scope == scope,
                TrackDedupHistory.track_key == track_key,
            )
            .first()
        )
        if existing is not None:
            existing.artist = artist or existing.artist
            existing.title = title or existing.title
            existing.album = album or existing.album
            existing.filepath = filepath or existing.filepath
            existing.run_id = run_id or existing.run_id
            existing.skip_reason = skip_reason or existing.skip_reason
            existing.source = source or existing.source
            existing.last_seen_at = utc_now()
            self.session.commit()
            return existing

        record = TrackDedupHistory(
            scope=scope,
            track_key=track_key,
            artist=artist,
            title=title,
            album=album,
            filepath=filepath,
            run_id=run_id,
            skip_reason=skip_reason,
            source=source,
            seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        self.session.add(record)
        self.session.commit()
        return record

    def list_tracks(
        self, scope: Optional[str] = None, limit: int = 20
    ) -> List[TrackDedupHistory]:
        query = self.session.query(TrackDedupHistory)
        if scope:
            query = query.filter(TrackDedupHistory.scope == scope)
        return query.order_by(TrackDedupHistory.last_seen_at.desc()).limit(limit).all()

    def put_cache(
        self,
        cache_key: str,
        cache_type: str,
        cache_value: Dict[str, Any],
        expires_at: Any = None,
    ) -> StateCacheEntry:
        existing = self.session.query(StateCacheEntry).filter(StateCacheEntry.cache_key == cache_key).first()
        if existing is not None:
            existing.cache_type = cache_type
            existing.cache_value = cache_value
            existing.expires_at = expires_at
            existing.updated_at = utc_now()
            self.session.commit()
            return existing

        record = StateCacheEntry(
            cache_key=cache_key,
            cache_type=cache_type,
            cache_value=cache_value,
            expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(record)
        self.session.commit()
        return record

    def get_cache(self, cache_key: str) -> Optional[StateCacheEntry]:
        return self.session.query(StateCacheEntry).filter(StateCacheEntry.cache_key == cache_key).first()
