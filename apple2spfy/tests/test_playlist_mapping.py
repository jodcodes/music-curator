import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Ensure project root is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apple2spfy.cache_manager import CacheManager
from sync_playlists import SpotifyManager, PlaylistSyncError
from apple2spfy.config import Config


class FakeSpotify:
    """Mock Spotify client for testing."""
    
    def __init__(self):
        self.playlists = {}  # {playlist_id: {"name": str, "snapshot_id": str}}
        self.next_playlist_id = 1
        self.name_change_calls = []
        self.description_change_calls = []
        
    def me(self):
        return {"id": "test_user", "display_name": "Test User"}
    
    def current_user_playlists(self, limit=50, offset=0):
        items = list(self.playlists.values())[offset:offset+limit]
        return {"items": items}
    
    def playlist(self, playlist_id, fields=None):
        if playlist_id not in self.playlists:
            raise Exception(f"Playlist {playlist_id} not found")
        pl = self.playlists[playlist_id]
        return {
            "id": playlist_id,
            "name": pl["name"],
            "description": pl.get("description", ""),
            "snapshot_id": pl.get("snapshot_id", "snap-1"),
            "tracks": {"total": 0}
        }
    
    def user_playlist_create(self, user, name, public=False, description=""):
        playlist_id = f"pl{self.next_playlist_id}"
        self.next_playlist_id += 1
        self.playlists[playlist_id] = {
            "id": playlist_id,
            "name": name,
            "description": description,
            "snapshot_id": f"snap-{playlist_id}"
        }
        return {"id": playlist_id, "name": name}
    
    def playlist_change_details(self, playlist_id, name=None, public=None, collaborative=None, description=None):
        if playlist_id not in self.playlists:
            raise Exception(f"Playlist {playlist_id} not found")
        if name is not None:
            self.playlists[playlist_id]["name"] = name
            self.name_change_calls.append((playlist_id, name))
        if description is not None:
            self.playlists[playlist_id]["description"] = description
            self.description_change_calls.append((playlist_id, description))
        return None


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Create a temporary cache directory for testing."""
    cache_dir = tmp_path / "spotify_cache"
    cache_dir.mkdir()
    monkeypatch.setattr(Config, "get_cache_dir", classmethod(lambda cls: str(cache_dir)))
    monkeypatch.setattr(Config, "SQLITE_DB_PATH", str(cache_dir / "cache.db"))
    return cache_dir


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create a CacheManager instance with temp database."""
    return CacheManager()


@pytest.fixture
def spotify_manager(temp_cache_dir, monkeypatch):
    """Create a SpotifyManager instance with mocked Spotify client."""
    fake_sp = FakeSpotify()
    
    def fake_auth(self):
        self.sp = fake_sp
    
    monkeypatch.setattr(SpotifyManager, "_authenticate", fake_auth)
    manager = SpotifyManager(minimal=True)
    manager.fake_sp = fake_sp  # Store reference for test access
    return manager


def test_mapping_table_schema(cache_manager):
    """Test that the apple_playlist_mapping table exists with correct schema."""
    conn = cache_manager.get_connection()
    cursor = conn.cursor()
    
    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apple_playlist_mapping'")
    assert cursor.fetchone() is not None
    
    # Check columns
    cursor.execute("PRAGMA table_info(apple_playlist_mapping)")
    columns = {row[1] for row in cursor.fetchall()}
    expected_columns = {"apple_playlist_name", "spotify_playlist_id", "spotify_playlist_name", "last_synced", "created_at"}
    assert columns == expected_columns
    
    conn.close()


def test_new_playlist_creates_mapping(spotify_manager, cache_manager):
    """Test that creating a new playlist also creates a mapping."""
    apple_name = "Test Playlist"
    
    # Create playlist
    playlist_id = spotify_manager.find_or_create_playlist(apple_name)
    
    # Verify playlist was created
    assert playlist_id.startswith("pl")
    
    # Verify mapping was created
    mapped_id = cache_manager.get_playlist_mapping(apple_name)
    assert mapped_id == playlist_id


def test_new_playlist_created_with_empty_description(spotify_manager):
    """Test that newly created Spotify playlists do not get sync attribution text."""
    apple_name = "Fresh Playlist"

    playlist_id = spotify_manager.find_or_create_playlist(apple_name)

    assert spotify_manager.fake_sp.playlists[playlist_id]["description"] == ""


def test_mapped_playlist_description_is_cleared(spotify_manager, cache_manager):
    """Test that existing mapped playlists have old sync attribution removed."""
    apple_name = "Mapped Playlist"
    playlist_id = "pl_existing"
    spotify_manager.fake_sp.playlists[playlist_id] = {
        "id": playlist_id,
        "name": apple_name,
        "description": "Synced from Apple Music",
        "snapshot_id": "snap-existing"
    }
    cache_manager.save_playlist_mapping(apple_name, playlist_id, apple_name)

    found_id = spotify_manager.find_or_create_playlist(apple_name)

    assert found_id == playlist_id
    assert spotify_manager.fake_sp.playlists[playlist_id]["description"] == ""
    assert (playlist_id, "") in spotify_manager.fake_sp.description_change_calls


def test_existing_playlist_description_is_cleared_when_mapping_created(spotify_manager, cache_manager):
    """Test that found existing playlists have old sync attribution removed."""
    apple_name = "Existing Playlist With Description"
    spotify_manager.fake_sp.playlists["pl999"] = {
        "id": "pl999",
        "name": apple_name,
        "description": "Synced from Apple Music",
        "snapshot_id": "snap-999"
    }

    playlist_id = spotify_manager.find_or_create_playlist(apple_name)

    assert playlist_id == "pl999"
    assert cache_manager.get_playlist_mapping(apple_name) == "pl999"
    assert spotify_manager.fake_sp.playlists[playlist_id]["description"] == ""
    assert (playlist_id, "") in spotify_manager.fake_sp.description_change_calls


def test_existing_playlist_migration(spotify_manager, cache_manager):
    """Test that finding an existing playlist creates a mapping."""
    apple_name = "Existing Playlist"
    
    # Create playlist directly in fake Spotify (simulating pre-existing playlist)
    spotify_manager.fake_sp.playlists["pl999"] = {
        "id": "pl999",
        "name": apple_name,
        "snapshot_id": "snap-999"
    }
    
    # Find the playlist (should create mapping)
    playlist_id = spotify_manager.find_or_create_playlist(apple_name)
    
    # Verify it found the existing playlist
    assert playlist_id == "pl999"
    
    # Verify mapping was created
    mapped_id = cache_manager.get_playlist_mapping(apple_name)
    assert mapped_id == "pl999"


def test_playlist_rename_updates_spotify_name(spotify_manager, cache_manager):
    """Test that renaming an Apple Music playlist updates the Spotify playlist name."""
    old_apple_name = "GlamArt"
    new_apple_name = "Proto GlamArt"
    
    # Step 1: Create playlist with old name
    playlist_id = spotify_manager.find_or_create_playlist(old_apple_name)
    
    # Verify initial state
    assert spotify_manager.fake_sp.playlists[playlist_id]["name"] == old_apple_name
    assert cache_manager.get_playlist_mapping(old_apple_name) == playlist_id
    
    # Step 2: Simulate Apple Music playlist rename by updating the mapping
    # In real usage, the Apple Music playlist name changes, so we need to:
    # 1. Update the mapping to use the new Apple name
    # 2. Call find_or_create_playlist with the new name
    
    # First, manually update the mapping key (simulating the rename in Apple Music)
    cache_manager.save_playlist_mapping(new_apple_name, playlist_id, old_apple_name)
    
    # Now call find_or_create_playlist with the new Apple name
    found_id = spotify_manager.find_or_create_playlist(new_apple_name)
    
    # Verify it found the same playlist
    assert found_id == playlist_id
    
    # Verify Spotify playlist name was updated
    assert spotify_manager.fake_sp.playlists[playlist_id]["name"] == new_apple_name
    
    # Verify the name change was called
    assert (playlist_id, new_apple_name) in spotify_manager.fake_sp.name_change_calls


def test_mapping_persists_across_syncs(spotify_manager, cache_manager):
    """Test that mappings persist and are reused across multiple syncs."""
    apple_name = "Persistent Playlist"
    
    # First sync - create playlist
    playlist_id_1 = spotify_manager.find_or_create_playlist(apple_name)
    
    # Second sync - should find existing playlist via mapping
    playlist_id_2 = spotify_manager.find_or_create_playlist(apple_name)
    
    # Should be the same playlist
    assert playlist_id_1 == playlist_id_2
    
    # Should only have created one playlist
    assert len([p for p in spotify_manager.fake_sp.playlists.values() if p["name"] == apple_name]) == 1


def test_get_all_mappings(cache_manager):
    """Test retrieving all playlist mappings."""
    # Create some mappings
    cache_manager.save_playlist_mapping("Playlist 1", "pl1", "Playlist 1")
    cache_manager.save_playlist_mapping("Playlist 2", "pl2", "Playlist 2")
    cache_manager.save_playlist_mapping("Playlist 3", "pl3", "Playlist 3")
    
    # Get all mappings
    mappings = cache_manager.get_all_playlist_mappings()
    
    # Verify count
    assert len(mappings) == 3
    
    # Verify structure
    apple_names = {m["apple_name"] for m in mappings}
    assert apple_names == {"Playlist 1", "Playlist 2", "Playlist 3"}


def test_delete_mapping(cache_manager):
    """Test deleting a playlist mapping."""
    apple_name = "To Be Deleted"
    
    # Create mapping
    cache_manager.save_playlist_mapping(apple_name, "pl123", "To Be Deleted")
    
    # Verify it exists
    assert cache_manager.get_playlist_mapping(apple_name) == "pl123"
    
    # Delete it
    result = cache_manager.delete_playlist_mapping(apple_name)
    assert result is True
    
    # Verify it's gone
    assert cache_manager.get_playlist_mapping(apple_name) is None


def test_clear_all_mappings(cache_manager):
    """Test clearing all playlist mappings."""
    # Create some mappings
    cache_manager.save_playlist_mapping("Playlist 1", "pl1", "Playlist 1")
    cache_manager.save_playlist_mapping("Playlist 2", "pl2", "Playlist 2")
    
    # Verify they exist
    assert len(cache_manager.get_all_playlist_mappings()) == 2
    
    # Clear all
    result = cache_manager.clear_all_playlist_mappings()
    assert result is True
    
    # Verify they're gone
    assert len(cache_manager.get_all_playlist_mappings()) == 0


def test_dry_run_no_mapping_created(spotify_manager, cache_manager):
    """Test that dry run doesn't create mappings."""
    apple_name = "Dry Run Playlist"
    
    # Dry run
    playlist_id = spotify_manager.find_or_create_playlist(apple_name, dry_run=True)
    
    # Should return synthetic ID
    assert playlist_id.startswith("dryrun:")
    
    # Should not create mapping
    assert cache_manager.get_playlist_mapping(apple_name) is None
    
    # Should not create actual playlist
    assert len(spotify_manager.fake_sp.playlists) == 0


def test_invalid_mapping_removed_and_recreated(spotify_manager, cache_manager):
    """Test that invalid mappings (deleted playlists) are removed and new playlists created."""
    apple_name = "Deleted Playlist"
    
    # Create a mapping to a non-existent playlist
    cache_manager.save_playlist_mapping(apple_name, "pl_deleted", "Deleted Playlist")
    
    # Try to find/create playlist
    new_playlist_id = spotify_manager.find_or_create_playlist(apple_name)
    
    # Should have created a new playlist (not pl_deleted)
    assert new_playlist_id != "pl_deleted"
    assert new_playlist_id.startswith("pl")
    
    # Mapping should be updated to new playlist
    assert cache_manager.get_playlist_mapping(apple_name) == new_playlist_id
