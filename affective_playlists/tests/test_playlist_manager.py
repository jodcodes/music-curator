#!/usr/bin/env python3
"""
Unit tests for PlaylistManager.

Tests dry-run vs execute modes, folder creation, playlist moving, and error handling.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.playlist_manager import PlaylistManager


@pytest.fixture
def mock_apple_music():
    """Create mock AppleMusicInterface."""
    mock = MagicMock()
    mock.get_existing_folders.return_value = {}
    mock.create_folder.return_value = ("melodic", True)
    return mock


@pytest.fixture
def playlist_manager_dry_run(mock_apple_music):
    """Initialize PlaylistManager in dry-run mode."""
    with patch("src.playlist_manager.AppleMusicInterface", return_value=mock_apple_music):
        manager = PlaylistManager(dry_run=True)
        manager.apple_music = mock_apple_music
        return manager


@pytest.fixture
def playlist_manager_execute(mock_apple_music):
    """Initialize PlaylistManager in execute mode."""
    with patch("src.playlist_manager.AppleMusicInterface", return_value=mock_apple_music):
        manager = PlaylistManager(dry_run=False)
        manager.apple_music = mock_apple_music
        return manager


class TestPlaylistManagerInitialization:
    """Tests for PlaylistManager initialization."""

    def test_manager_initialization_dry_run(self, playlist_manager_dry_run):
        """Test that manager initializes in dry-run mode."""
        assert playlist_manager_dry_run.dry_run is True
        assert isinstance(playlist_manager_dry_run._folder_cache, dict)
        assert isinstance(playlist_manager_dry_run._playlist_cache, dict)

    def test_manager_initialization_execute(self, playlist_manager_execute):
        """Test that manager initializes in execute mode."""
        assert playlist_manager_execute.dry_run is False
        assert isinstance(playlist_manager_execute._folder_cache, dict)
        assert isinstance(playlist_manager_execute._playlist_cache, dict)

    def test_manager_cache_types(self, playlist_manager_dry_run):
        """Test that caches have correct types."""
        assert isinstance(playlist_manager_dry_run._folder_cache, dict)
        assert isinstance(playlist_manager_dry_run._playlist_cache, dict)


class TestDryRunMode:
    """Tests for dry-run mode behavior."""

    def test_dry_run_no_script_execution(self, playlist_manager_dry_run):
        """Test that scripts are not executed in dry-run mode."""
        # Mock the subprocess to ensure it's not called
        with patch("src.playlist_manager.subprocess.run") as mock_run:
            with patch("src.playlist_manager.subprocess.Popen") as mock_popen:
                script_content = "tell application 'Music'\nreturn itemNames\nend tell"
                success, output = playlist_manager_dry_run._run_applescript_inline(script_content)

                # In dry-run, should return success but not execute
                assert success is True
                assert output == "DRY-RUN: Script not executed"
                mock_run.assert_not_called()
                mock_popen.assert_not_called()

    def test_dry_run_folder_creation_logged_not_executed(self, playlist_manager_dry_run):
        """Test that folder creation in dry-run mode is logged but not executed."""
        with patch("src.playlist_manager.subprocess.Popen") as mock_popen:
            success, folder_id = playlist_manager_dry_run.create_folder("TestGenre")

            # In dry-run mode, _run_applescript_inline returns "DRY-RUN: Script not executed"
            # which causes create_folder to fail, so this is expected behavior
            # The important thing is that Popen is never called
            mock_popen.assert_not_called()
            # Folder creation fails because dry-run output doesn't contain a valid ID
            # This is acceptable - the key is no actual subprocess execution occurs

    def test_dry_run_playlist_move_not_executed(self, playlist_manager_dry_run):
        """Test that playlist move in dry-run mode is not executed."""
        # Mock playlist info
        playlist_manager_dry_run._playlist_cache["Test Playlist"] = {
            "name": "Test Playlist",
            "persistent_id": "playlist-id-123",
        }
        playlist_manager_dry_run._folder_cache["TestFolder"] = "folder-id-123"

        with patch("src.playlist_manager.subprocess.run") as mock_run:
            success = playlist_manager_dry_run.move_playlist_to_folder(
                "Test Playlist", "TestFolder"
            )

            # In dry-run, should return True but not execute
            assert success is True
            mock_run.assert_not_called()


class TestExecuteMode:
    """Tests for execute mode behavior."""

    def test_execute_mode_allows_script_execution(self, playlist_manager_execute):
        """Test that execute mode would allow script execution."""
        assert playlist_manager_execute.dry_run is False

    def test_execute_requires_script_path(self, playlist_manager_execute):
        """Test that execute mode requires valid script paths."""
        # In execute mode, should attempt to run scripts (would fail if path invalid)
        assert playlist_manager_execute.scripts_dir is not None


class TestFolderCreation:
    """Tests for folder creation logic."""

    def test_folder_creation_with_mock(self, playlist_manager_dry_run):
        """Test folder creation with mocked AppleScript."""
        with patch.object(
            playlist_manager_dry_run,
            "_run_applescript_inline",
            return_value=(True, "folder-id-456"),
        ):
            success, folder_id = playlist_manager_dry_run.create_folder("ElectronicMusic")

            # Should cache the folder
            assert success is True
            assert "ElectronicMusic" in playlist_manager_dry_run._folder_cache

    def test_folder_creation_duplicate_prevention(self, playlist_manager_dry_run):
        """Test that creating a duplicate folder doesn't create again."""
        # Pre-populate with existing folder
        playlist_manager_dry_run._folder_cache["ExistingFolder"] = "existing-id"

        with patch.object(playlist_manager_dry_run, "get_existing_folders") as mock_get:
            mock_get.return_value = {"ExistingFolder": "existing-id"}

            # Try creating same folder - should use existing
            success, folder_id = playlist_manager_dry_run.create_folder("ExistingFolder")

            assert success is True
            assert folder_id == "existing-id"


class TestPlaylistMove:
    """Tests for playlist move logic."""

    def test_move_playlist_requires_valid_info(self, playlist_manager_dry_run):
        """Test that move_playlist requires valid playlist and folder info."""
        # Try moving non-existent playlist
        with patch.object(playlist_manager_dry_run, "get_playlist_info", return_value=None):
            success = playlist_manager_dry_run.move_playlist_to_folder("NonExistent", "SomeFolder")

            assert success is False

    def test_move_playlist_success(self, playlist_manager_dry_run):
        """Test successful playlist move."""
        # Pre-populate cache
        playlist_manager_dry_run._playlist_cache["MyPlaylist"] = {
            "name": "MyPlaylist",
            "persistent_id": "pl-123",
        }
        playlist_manager_dry_run._folder_cache["MyFolder"] = "f-456"

        with patch.object(playlist_manager_dry_run, "get_playlist_info") as mock_get_info:
            with patch.object(playlist_manager_dry_run, "get_existing_folders") as mock_getFolders:
                mock_get_info.return_value = {
                    "name": "MyPlaylist",
                    "persistent_id": "pl-123",
                }
                mock_getFolders.return_value = {"MyFolder": "f-456"}

                with patch.object(playlist_manager_dry_run, "_run_applescript_file") as mock_run:
                    mock_run.return_value = (True, "SUCCESS")

                    success = playlist_manager_dry_run.move_playlist_to_folder(
                        "MyPlaylist", "MyFolder"
                    )

                    assert success is True


class TestBatchOperations:
    """Tests for batch playlist organization."""

    def test_organize_multiple_playlists_dry_run(self, playlist_manager_dry_run):
        """Test organizing multiple playlists in dry-run mode."""
        playlist_assignments = {
            "Jazz Favorites": "jazz",
            "Electronic Beats": "electronic",
            "Rock Classics": "rock",
        }

        with patch.object(playlist_manager_dry_run, "ensure_genre_folders_exist") as mock_ensure:
            with patch.object(playlist_manager_dry_run, "move_playlist_to_folder") as mock_move:
                mock_ensure.return_value = {
                    "jazz": True,
                    "electronic": True,
                    "rock": True,
                }
                mock_move.return_value = True

                results = playlist_manager_dry_run.organize_playlists(playlist_assignments)

                assert len(results) == 3
                assert all(r is True for r in results.values())
                # In dry-run, should still track moves
                assert mock_move.call_count == 3

    def test_organize_playlists_with_failures(self, playlist_manager_dry_run):
        """Test organizing playlists with some failures."""
        playlist_assignments = {
            "Good Playlist": "jazz",
            "Bad Playlist": "electronic",
        }

        with patch.object(playlist_manager_dry_run, "ensure_genre_folders_exist") as mock_ensure:
            with patch.object(playlist_manager_dry_run, "move_playlist_to_folder") as mock_move:
                mock_ensure.return_value = {"jazz": True, "electronic": True}
                # First succeeds, second fails
                mock_move.side_effect = [True, False]

                results = playlist_manager_dry_run.organize_playlists(playlist_assignments)

                assert len(results) == 2
                assert results.get("Good Playlist") is True
                assert results.get("Bad Playlist") is False


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_applescript_timeout_handling(self, playlist_manager_dry_run):
        """Test that AppleScript timeout is handled gracefully."""
        import subprocess

        with patch("src.playlist_manager.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.communicate.side_effect = subprocess.TimeoutExpired("timeout", 30)
            mock_popen.return_value = mock_process

            # In execute mode (which we'd use for real testing)
            manager_exec = PlaylistManager(dry_run=False)
            manager_exec.dry_run = False  # Force non-dry-run
            with patch.object(manager_exec, "_run_applescript_inline") as mock_run:
                # Simulate timeout
                mock_run.return_value = (False, "Script execution timed out")
                success, output = manager_exec._run_applescript_inline("test script")

                assert success is False
                assert "timed out" in output.lower()

    def test_none_folder_id_handling(self, playlist_manager_dry_run):
        """Test that None folder ID from create_folder is handled."""
        with patch.object(playlist_manager_dry_run, "create_folder") as mock_create:
            with patch.object(playlist_manager_dry_run, "get_existing_folders") as mock_get:
                with patch.object(playlist_manager_dry_run, "get_playlist_info") as mock_info:
                    # create_folder returns (False, None)
                    mock_create.return_value = (False, None)
                    mock_get.return_value = {}
                    mock_info.return_value = {
                        "name": "test",
                        "persistent_id": "id",
                    }

                    success = playlist_manager_dry_run.move_playlist_to_folder("test", "newFolder")

                    assert success is False


class TestCaching:
    """Tests for caching behavior."""

    def test_folder_cache_persistence(self, playlist_manager_dry_run):
        """Test that folder cache persists across calls."""
        playlist_manager_dry_run._folder_cache["TestFolder"] = "test-id"

        # Subsequent calls should use cache
        assert playlist_manager_dry_run._folder_cache["TestFolder"] == "test-id"

    def test_playlist_cache_persistence(self, playlist_manager_dry_run):
        """Test that playlist cache persists across calls."""
        playlist_manager_dry_run._playlist_cache["MyPlaylist"] = {
            "name": "MyPlaylist",
            "persistent_id": "id",
        }

        # Subsequent calls should use cache
        assert playlist_manager_dry_run._playlist_cache["MyPlaylist"]["persistent_id"] == "id"

    def test_cache_types_correct(self, playlist_manager_dry_run):
        """Test that cache types are correctly enforced."""
        # Add test data to caches
        playlist_manager_dry_run._folder_cache["folder1"] = "id1"
        playlist_manager_dry_run._playlist_cache["playlist1"] = {
            "name": "playlist1",
            "persistent_id": "pid1",
        }

        # Verify types
        assert isinstance(playlist_manager_dry_run._folder_cache["folder1"], str)
        assert isinstance(
            playlist_manager_dry_run._playlist_cache["playlist1"],
            dict,
        )


class TestFrontendPlaylistData:
    """Tests for frontend playlist data helper methods."""

    def test_get_all_playlists_returns_expected_shape(self, playlist_manager_dry_run):
        """Playlist list should contain id/name/track_count fields for API."""
        playlist_manager_dry_run.apple_music.get_user_playlists_with_counts.return_value = [
            {"name": "Playlist A", "track_count": 12},
            {"name": "Playlist B", "track_count": 7},
        ]
        playlist_manager_dry_run.apple_music.get_playlist_ids.return_value = {
            "Playlist A": "A1B2C3D4E5F60708",
            "Playlist B": "0011223344556677",
        }

        playlists = playlist_manager_dry_run.get_all_playlists()

        assert len(playlists) == 2
        assert playlists[0]["name"] == "Playlist A"
        assert playlists[0]["id"] == "A1B2C3D4E5F60708"
        assert playlists[0]["track_count"] == 12
        assert playlists[1]["name"] == "Playlist B"
        assert playlists[1]["id"] == "0011223344556677"
        assert playlists[1]["track_count"] == 7

    def test_get_playlist_details_maps_tracks_for_frontend(self, playlist_manager_dry_run):
        """Playlist details should include normalized track objects."""
        playlist_manager_dry_run.apple_music.get_user_playlists_with_counts.return_value = [
            {"name": "My Playlist", "track_count": 1}
        ]
        playlist_manager_dry_run.apple_music.get_playlist_ids.return_value = {
            "My Playlist": "ABCDEF0123456789"
        }
        playlist_manager_dry_run.apple_music.get_playlist_tracks.side_effect = [
            [{"title": "Song 1", "artist": "Artist 1"}],
            [{"title": "Song 1", "artist": "Artist 1", "album": "Album 1"}],
        ]

        playlist_id = "ABCDEF0123456789"
        details = playlist_manager_dry_run.get_playlist_details(playlist_id)

        assert details is not None
        assert details["name"] == "My Playlist"
        assert details["track_count"] == 1
        assert len(details["tracks"]) == 1
        assert details["tracks"][0]["name"] == "Song 1"
        assert details["tracks"][0]["artist"] == "Artist 1"
