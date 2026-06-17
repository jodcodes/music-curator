import os
import sys
from pathlib import Path

import pytest

# Ensure package root is in path so imports work when running under pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sync_playlists import SpotifyManager, PlaylistSync, PlaylistSyncError
from apple2spfy.config import Config


class FakeSpotify:
    def __init__(self, playlist_id, playlists, snapshot_id, total_tracks):
        self._playlist_id = playlist_id
        self._playlists = playlists
        self._snapshot_id = snapshot_id
        self._total = total_tracks
        self.add_calls = []
        self.rem_calls = []

    def me(self):
        return {"id": "user123", "display_name": "testuser"}

    def current_user_playlists(self, limit=50, offset=0):
        return {"items": self._playlists}

    def playlist(self, playlist_id, fields=None):
        return {"id": playlist_id, "name": "TestPlaylist", "snapshot_id": self._snapshot_id, "tracks": {"total": self._total}}

    def playlist_items(self, playlist_id, fields=None, limit=None, offset=None, additional_types=None):
        return {"items": []}

    def playlist_add_items(self, playlist_id, items):
        self.add_calls.append((playlist_id, items))
        return None

    def playlist_remove_all_occurrences_of_items(self, playlist_id, items):
        self.rem_calls.append((playlist_id, items))
        return None


def test_skip_sync_when_snapshot_matches(tmp_path, monkeypatch):
    """sync_playlist should skip API writes when AM state and Spotify snapshot are both unchanged."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(Config, "SQLITE_DB_PATH", str(db_file))

    playlist_id = "pl1"
    snapshot_id = "snap-1"
    spotify_playlists = [{"name": "TestPlaylist", "id": playlist_id}]
    fake_sp = FakeSpotify(playlist_id, spotify_playlists, snapshot_id=snapshot_id, total_tracks=5)

    monkeypatch.setattr(SpotifyManager, "_authenticate", lambda self: setattr(self, "sp", fake_sp))

    mgr = SpotifyManager()

    tracks = [{"title": f"Song{i}", "artist": "Artist"} for i in range(5)]

    # Resolve each track to a fake Spotify ID and pre-populate the track cache
    for i, t in enumerate(tracks):
        key = mgr._track_cache_key(t["title"], t["artist"], None)
        sig = "|".join(str(x) for x in key)
        mgr.cache_manager.save_track(sig, f"spotify:track:{i}", t["title"], t["artist"], None)

    # Seed the apple playlist state ("what we synced last time")
    resolved = []
    for i, t in enumerate(tracks):
        key = mgr._track_cache_key(t["title"], t["artist"], None)
        sig = "|".join(str(x) for x in key)
        resolved.append({"signature": sig, "spotify_track_id": f"spotify:track:{i}"})
    mgr.cache_manager.update_apple_playlist_state("TestPlaylist", resolved)

    # Seed the Spotify playlist metadata with the same snapshot
    mgr.cache_manager.save_playlist_metadata(playlist_id, snapshot_id, len(tracks), "TestPlaylist")
    # Seed the playlist mapping so find_or_create_playlist hits the fast path
    mgr.cache_manager.save_playlist_mapping("TestPlaylist", playlist_id, "TestPlaylist")

    added, removed = mgr.sync_playlist("TestPlaylist", tracks, clean_sync=True)
    assert added == 0 and removed == 0
    assert fake_sp.add_calls == []
    assert fake_sp.rem_calls == []
