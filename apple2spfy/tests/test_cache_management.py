import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

# Ensure project root is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apple2spfy.config import Config
from sync_playlists import SpotifyManager, PlaylistSync


def test_clear_cache(tmp_path, monkeypatch):
    """clear_all_cache() should delete all rows from the SQLite tracks and playlists tables."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(Config, "SQLITE_DB_PATH", str(db_file))

    mgr = SpotifyManager(minimal=True, authenticate=False)

    # Seed the cache with some data
    mgr.cache_manager.save_track("sig1", "spotify:track:1", "Song1", "Artist1", None)
    mgr.cache_manager.save_track("sig2", "spotify:track:2", "Song2", "Artist2", "Album")
    mgr.cache_manager.save_playlist_metadata("pl1", "snap-1", 2, "MyPlaylist")

    # Verify rows exist before clearing
    assert mgr.cache_manager.get_track("sig1") is not None
    assert mgr.cache_manager.get_playlist_metadata("pl1") is not None

    ok = mgr.clear_all_cache()
    assert ok

    # Rows should be gone
    assert mgr.cache_manager.get_track("sig1") is None
    assert mgr.cache_manager.get_track("sig2") is None
    assert mgr.cache_manager.get_playlist_metadata("pl1") is None


def test_cache_ttl_expiry(tmp_path, monkeypatch):
    """get_track() should ignore rows older than CACHE_TTL_DAYS."""
    import sqlite3

    db_file = tmp_path / "test.db"
    monkeypatch.setattr(Config, "SQLITE_DB_PATH", str(db_file))
    monkeypatch.setattr(Config, "CACHE_TTL_DAYS", 1)

    mgr = SpotifyManager(minimal=True, authenticate=False)

    old_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    new_ts = datetime.now(timezone.utc).isoformat()

    # Insert one fresh and one stale entry directly into SQLite
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute(
            "INSERT INTO tracks (signature, track_id, title, artist, album, last_updated) VALUES (?, ?, ?, ?, ?, ?)",
            ("old_sig", "spotify:track:old", "OldSong", "Artist", None, old_ts)
        )
        conn.execute(
            "INSERT INTO tracks (signature, track_id, title, artist, album, last_updated) VALUES (?, ?, ?, ?, ?, ?)",
            ("new_sig", "spotify:track:new", "NewSong", "Artist", None, new_ts)
        )
        conn.commit()

    # Stale entry should not be returned
    assert mgr.cache_manager.get_track("old_sig") is None
    # Fresh entry should be returned
    assert mgr.cache_manager.get_track("new_sig") == "spotify:track:new"


def test_dry_run_no_writes(tmp_path, monkeypatch):
    # Setup minimal cache dir
    cd = tmp_path / "cache"
    cd.mkdir()
    monkeypatch.setattr(Config, "get_cache_dir", classmethod(lambda cls: str(cd)))

    # Fake Spotify client
    class FakeSpotify:
        def __init__(self):
            self.add_calls = []
            self.rem_calls = []

        def me(self):
            return {"id": "user123", "display_name": "testuser"}

        def current_user_playlists(self, limit=50, offset=0):
            return {"items": [{"name": "TestPlaylist", "id": "pl1"}]}

        def playlist(self, playlist_id, fields=None):
            return {"snapshot_id": "snap-1", "tracks": {"total": 0}}

        def playlist_items(self, playlist_id, fields=None, limit=None, offset=None, additional_types=None):
            return {"items": []}

        def playlist_add_items(self, playlist_id, items):
            self.add_calls.append((playlist_id, items))

        def playlist_remove_all_occurrences_of_items(self, playlist_id, items):
            self.rem_calls.append((playlist_id, items))

        def search(self, q, type, limit):
            return {"tracks": {"items": [{"id": "tr1", "name": "Song", "artists": [{"name": "Artist"}]}]}}

    fake_sp = FakeSpotify()

    # Monkeypatch SpotifyManager._authenticate to avoid OAuth and set sp
    monkeypatch.setattr(SpotifyManager, "_authenticate", lambda self: setattr(self, "sp", fake_sp))

    # create manager and playlist sync
    mgr = SpotifyManager(minimal=True)
    sync = PlaylistSync(minimal_output=True, show_cache=False, dry_run=True)
    sync.spotify_manager = mgr

    # Create a fake Apple playlist
    apple_playlists = {"TestPlaylist": [{"title": "Song", "artist": "Artist"}]}

    # Monkeypatch AppleMusicExtractor.get_playlists to return our fake playlists
    monkeypatch.setattr(sync.apple_extractor, "get_playlists", lambda: apple_playlists)

    # Run sync with dry_run True
    stats = sync.sync_all_playlists(clean_sync=True, force_sync=False, dry_run=True)
    # In dry-run, stats show what would be added/removed, but no API calls should be made
    assert stats["TestPlaylist"]["tracks_added"] == 1
    assert stats["TestPlaylist"]["tracks_removed"] == 0
    # Ensure no additions/removals were sent to Spotify
    assert fake_sp.add_calls == []
    assert fake_sp.rem_calls == []
