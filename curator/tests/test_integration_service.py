"""
Integration tests: idempotency, concurrency, and state recovery.

These tests use an in-process SQLite DB and fake Apple Music data — no real
Apple Music or network access needed.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracks(n: int) -> List[Dict[str, Any]]:
    return [
        {
            "artist": f"Artist{i}",
            "name": f"Song{i}",
            "album": "Album",
            "filepath": f"/music/song{i}.mp3",
        }
        for i in range(n)
    ]


@pytest.fixture()
def tmp_db(tmp_path):
    """Isolate each test in its own SQLite database."""
    import src.db as db_module

    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine, SessionLocal = db_module.init_db(url)
    session = SessionLocal()

    original_get_session = db_module.get_session
    db_module.get_session = lambda: SessionLocal()
    yield session
    session.close()
    db_module.get_session = original_get_session


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------

class TestEnrichmentIdempotency:
    """Running enrichment twice on the same tracks should not double-count."""

    def _make_filler(self, tmp_db):
        from src.metadata_fill import MetadataFiller
        from src.library_state_store import LibraryStateStore

        store = LibraryStateStore(session=tmp_db)
        filler = MetadataFiller.__new__(MetadataFiller)
        filler.logger = MagicMock()
        filler.state_store = store
        filler._processed_track_cache = {}
        filler._processed_track_cache_lock = threading.Lock()

        filler._process_one_track = MagicMock(
            return_value={"processed": 1, "enriched": 1, "skipped": 0, "cover_art_embedded": 0}
        )
        return filler

    def test_second_run_skips_already_processed_tracks(self, tmp_db):
        filler = self._make_filler(tmp_db)
        tracks = _make_tracks(5)

        r1 = filler._process_tracks(tracks, force=False, scope="playlist:test")
        assert r1["processed"] == 5
        assert r1["skipped"] == 0

        # Reset in-memory cache to simulate new process
        filler._processed_track_cache = {}
        r2 = filler._process_tracks(tracks, force=False, scope="playlist:test")
        assert r2["skipped"] == 5, "all tracks should be skipped on second run"
        assert r2["processed"] == 0

    def test_force_flag_bypasses_dedupe(self, tmp_db):
        filler = self._make_filler(tmp_db)
        tracks = _make_tracks(3)

        filler._process_tracks(tracks, force=False, scope="playlist:force_test")
        filler._processed_track_cache = {}
        r2 = filler._process_tracks(tracks, force=True, scope="playlist:force_test")
        assert r2["processed"] == 3, "force=True must re-process all tracks"

    def test_duplicate_tracks_in_same_batch_deduplicated(self, tmp_db):
        filler = self._make_filler(tmp_db)
        t = _make_tracks(1)[0]
        tracks = [t, t, t]  # same track 3 times

        r = filler._process_tracks(tracks, force=False, scope="playlist:dup_test")
        assert r["processed"] == 1
        assert r["skipped"] == 2


# ---------------------------------------------------------------------------
# Concurrency tests
# ---------------------------------------------------------------------------

class TestConcurrentWorkers:
    """Parallel execution must not corrupt results."""

    def test_parallel_map_is_safe(self):
        from src.worker_pool import map_parallel

        results = []
        lock = threading.Lock()

        def work(x: int) -> int:
            with lock:
                results.append(x)
            return x * 2

        pairs = map_parallel(work, range(50), workers=8, label="ints")
        assert len(pairs) == 50
        values = [r for _, r in pairs if not isinstance(r, Exception)]
        assert sorted(values) == [i * 2 for i in range(50)]

    def test_worker_errors_dont_propagate(self):
        from src.worker_pool import map_parallel

        def boom(x: int) -> int:
            if x == 5:
                raise ValueError("bad item")
            return x

        pairs = map_parallel(boom, range(10), workers=4, label="boom_test")
        assert len(pairs) == 10
        errors = [(i, r) for i, r in pairs if isinstance(r, Exception)]
        assert len(errors) == 1
        assert errors[0][0] == 5

    def test_resolve_workers_caps_at_item_count(self):
        from src.worker_pool import resolve_workers

        assert resolve_workers(None, 0) == 1
        assert resolve_workers(None, 1) == 1
        assert resolve_workers(100, 3) == 3  # capped at item_count

    def test_resolve_workers_respects_global_cap(self, monkeypatch):
        import src.worker_pool as wp
        monkeypatch.setattr(wp, "_GLOBAL_MAX_WORKERS", 2)
        from src.worker_pool import resolve_workers
        assert resolve_workers(10, 100) <= 2


# ---------------------------------------------------------------------------
# State recovery tests
# ---------------------------------------------------------------------------

class TestStateRecovery:
    """Crashed runs should be visible and recoverable from the DB."""

    def test_unfinished_run_visible_in_list(self, tmp_db):
        from src.library_state_store import LibraryStateStore

        store = LibraryStateStore(session=tmp_db)
        run = store.create_run("enrich", target="library", payload={})
        assert run.status == "running"

        runs = store.list_runs(limit=10)
        assert any(r.id == run.id and r.status == "running" for r in runs)

    def test_finishing_run_updates_status(self, tmp_db):
        from src.library_state_store import LibraryStateStore

        store = LibraryStateStore(session=tmp_db)
        run = store.create_run("enrich", target="library", payload={})
        store.finish_run(run.id, status="completed", processed_items=42)

        runs = store.list_runs(limit=1, run_type="enrich")
        assert runs[0].status == "completed"
        assert runs[0].processed_items == 42

    def test_multiple_scopes_isolated(self, tmp_db):
        from src.library_state_store import LibraryStateStore
        from src.deduplication import build_track_key

        store = LibraryStateStore(session=tmp_db)
        key = build_track_key(artist="A", title="T")

        store.record_track(scope="playlist:X", track_key=key)
        assert store.has_track("playlist:X", key)
        assert not store.has_track("playlist:Y", key), "scopes must be isolated"

    def test_cache_put_and_get(self, tmp_db):
        from src.library_state_store import LibraryStateStore

        store = LibraryStateStore(session=tmp_db)
        store.put_cache("key:test", "query", {"artist": "A", "bpm": 120})
        entry = store.get_cache("key:test")
        assert entry is not None
        assert entry.cache_value["bpm"] == 120

    def test_cache_upsert_overwrites(self, tmp_db):
        from src.library_state_store import LibraryStateStore

        store = LibraryStateStore(session=tmp_db)
        store.put_cache("k", "t", {"v": 1})
        store.put_cache("k", "t", {"v": 2})
        entry = store.get_cache("k")
        assert entry.cache_value["v"] == 2
