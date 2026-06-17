"""
Shared AppleScript utilities for music operations.
This package provides Python wrappers for AppleScript functions.
"""

import os
import subprocess
from typing import List, Optional, Tuple

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_applescript_function(
    script_file: str, args: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Run an AppleScript function from a file.

    Args:
        script_file: Name of the .applescript file (without extension)
        args: Optional list of arguments to pass to the script

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        script_path = os.path.join(SCRIPTS_DIR, f"{script_file}.applescript")

        if not os.path.exists(script_path):
            return False, f"Script not found: {script_path}"

        cmd = ["osascript", script_path]
        if args:
            cmd.extend(args)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return False, result.stderr.strip()

        return True, result.stdout.strip()

    except subprocess.TimeoutExpired:
        return False, "AppleScript execution timed out"
    except Exception as e:
        return False, str(e)


def check_music_app() -> bool:
    """Check if Music app is available."""
    success, output = run_applescript_function("music_app")
    return success and bool(output)


def get_playlists() -> List[str]:
    """Get all user playlists from Music.app."""
    success, output = run_applescript_function("playlist_reader")
    if not success:
        return []
    return [line.strip() for line in output.split("\n") if line.strip()]


def get_playlist_tracks(playlist_name: str) -> Optional[str]:
    """
    Get all tracks from a playlist.

    Returns pipe-separated values: persistentID|trackID|name|artist|album|genre|bpm|year|composer|duration
    """
    success, output = run_applescript_function("playlist_reader", [playlist_name])
    return output if success else None


def create_playlist_folder(folder_name: str) -> bool:
    """Create a playlist folder."""
    success, _ = run_applescript_function("playlist_manager", ["create_folder", folder_name])
    return success


def move_playlist_to_folder(playlist_name: str, folder_name: str) -> bool:
    """Move a playlist to a folder."""
    success, _ = run_applescript_function("playlist_manager", ["move", playlist_name, folder_name])
    return success


def create_playlist(playlist_name: str) -> bool:
    """Create a new playlist."""
    success, _ = run_applescript_function("playlist_manager", ["create_playlist", playlist_name])
    return success


def delete_playlist(playlist_name: str) -> bool:
    """Delete a playlist."""
    success, _ = run_applescript_function("playlist_manager", ["delete_playlist", playlist_name])
    return success
