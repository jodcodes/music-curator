import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apple2spfy.config import Config
import sync_playlists
from sync_playlists import SpotifyManager, PlaylistSync, PlaylistSyncError


def _sync_with_one_failing_playlist(tmp_path, monkeypatch):
    cd = tmp_path / "cache"
    cd.mkdir()
    monkeypatch.setattr(Config, "get_cache_dir", classmethod(lambda cls: str(cd)))
    monkeypatch.setattr(Config, "sync_state_path", classmethod(lambda cls: str(tmp_path / "sync_state.json")))
    # Per-playlist sync is faked below, so the pre-warm batch track lookup
    # (which would otherwise hit the real Spotify search + retry/backoff path) is
    # irrelevant here and only slows the test down.
    monkeypatch.setattr(Config, "ENABLE_BATCH_LOOKUP", False)

    class FakeSpotify:
        def me(self):
            return {"id": "user123", "display_name": "testuser"}

    monkeypatch.setattr(SpotifyManager, "_authenticate", lambda self: setattr(self, "sp", FakeSpotify()))

    mgr = SpotifyManager(minimal=True)
    sync = PlaylistSync(minimal_output=True, show_cache=False, dry_run=False)
    sync.spotify_manager = mgr

    apple_playlists = {
        "GoodPlaylist": [{"title": "Song A", "artist": "Artist A"}],
        "BadPlaylist": [{"title": "Song B", "artist": "Artist B"}],
    }
    monkeypatch.setattr(sync.apple_extractor, "get_playlists", lambda: apple_playlists)

    def fake_sync_playlist(playlist_name, tracks, clean_sync, force_sync, dry_run):
        if playlist_name == "BadPlaylist":
            raise PlaylistSyncError("boom: could not reach Spotify")
        return (1, 0)

    monkeypatch.setattr(mgr, "sync_playlist", fake_sync_playlist)
    return sync, mgr


def test_stats_report_error_for_failed_playlist(tmp_path, monkeypatch):
    sync, _mgr = _sync_with_one_failing_playlist(tmp_path, monkeypatch)

    stats = sync.sync_all_playlists(clean_sync=False, force_sync=False, dry_run=False)

    assert "error" in stats["BadPlaylist"]
    assert "error" not in stats["GoodPlaylist"]


def test_resume_state_is_not_cleared_when_a_playlist_fails(tmp_path, monkeypatch):
    sync, mgr = _sync_with_one_failing_playlist(tmp_path, monkeypatch)
    state_path = tmp_path / "sync_state.json"

    sync.sync_all_playlists(clean_sync=False, force_sync=False, dry_run=False)

    # GoodPlaylist succeeded and must stay marked-completed so a retry
    # only re-processes BadPlaylist, not everything from scratch.
    assert mgr.sync_state_manager.is_completed("GoodPlaylist") is True
    assert mgr.sync_state_manager.is_completed("BadPlaylist") is False


def test_resume_state_is_cleared_after_a_fully_successful_run(tmp_path, monkeypatch):
    cd = tmp_path / "cache"
    cd.mkdir()
    monkeypatch.setattr(Config, "get_cache_dir", classmethod(lambda cls: str(cd)))
    monkeypatch.setattr(Config, "sync_state_path", classmethod(lambda cls: str(tmp_path / "sync_state.json")))
    monkeypatch.setattr(Config, "ENABLE_BATCH_LOOKUP", False)

    class FakeSpotify:
        def me(self):
            return {"id": "user123", "display_name": "testuser"}

    monkeypatch.setattr(SpotifyManager, "_authenticate", lambda self: setattr(self, "sp", FakeSpotify()))

    mgr = SpotifyManager(minimal=True)
    sync = PlaylistSync(minimal_output=True, show_cache=False, dry_run=False)
    sync.spotify_manager = mgr

    apple_playlists = {"GoodPlaylist": [{"title": "Song A", "artist": "Artist A"}]}
    monkeypatch.setattr(sync.apple_extractor, "get_playlists", lambda: apple_playlists)
    monkeypatch.setattr(mgr, "sync_playlist", lambda *a, **k: (1, 0))

    sync.sync_all_playlists(clean_sync=False, force_sync=False, dry_run=False)

    assert mgr.sync_state_manager.is_completed("GoodPlaylist") is False  # cleared, not just unmarked


def test_main_returns_1_when_a_playlist_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_playlists.py"])

    class FakeSync:
        def __init__(self, *a, **k):
            pass

        def sync_all_playlists(self, **kwargs):
            return {
                "GoodPlaylist": {"tracks_added": 1, "tracks_removed": 0, "total_tracks": 1},
                "BadPlaylist": {"tracks_added": 0, "tracks_removed": 0, "total_tracks": 1, "error": "boom"},
            }

    monkeypatch.setattr(sync_playlists, "PlaylistSync", FakeSync)

    assert sync_playlists.main() == 1


def test_main_returns_0_when_all_playlists_succeed(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_playlists.py"])

    class FakeSync:
        def __init__(self, *a, **k):
            pass

        def sync_all_playlists(self, **kwargs):
            return {"GoodPlaylist": {"tracks_added": 1, "tracks_removed": 0, "total_tracks": 1}}

    monkeypatch.setattr(sync_playlists, "PlaylistSync", FakeSync)

    assert sync_playlists.main() == 0
