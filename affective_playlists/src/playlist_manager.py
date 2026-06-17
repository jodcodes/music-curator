"""
Playlist Manager for Apple Music Integration

Handles creation of playlist folders and moving playlists between folders.
Integrates with AppleScript for actual Apple Music operations.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.apple_music import AppleMusicInterface
from src.logger import setup_logger

logger = setup_logger(__name__)


class PlaylistManager:
    """
    Manager for Apple Music playlist operations including folder creation and playlist moving.
    """

    def __init__(self, dry_run: bool = False, scripts_dir: str = "scripts"):
        """
        Initialize playlist manager.

        Args:
            dry_run: If True, only log operations without executing them
            scripts_dir: Directory containing AppleScript files
        """
        self.dry_run = dry_run
        self.scripts_dir = Path(scripts_dir) if isinstance(scripts_dir, str) else scripts_dir
        self.apple_music = AppleMusicInterface(str(self.scripts_dir))

        # Cache for folder information
        self._folder_cache: Dict[str, str] = {}
        self._playlist_cache: Dict[str, Dict[str, str]] = {}

        logger.info(f"Initialized PlaylistManager (dry_run: {dry_run})")

    def _run_applescript_file(
        self, script_name: str, args: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Run an AppleScript file with arguments.

        Args:
            script_name: Name of the script file (without .applescript extension)
            args: List of arguments to pass to the script

        Returns:
            Tuple of (success, output/error_message)
        """
        script_path = self.scripts_dir / f"{script_name}.applescript"

        if not script_path.exists():
            return False, f"Script not found: {script_path}"

        try:
            cmd = ["osascript", str(script_path)]
            if args:
                cmd.extend(args)

            if self.dry_run:
                logger.info(f"[DRY-RUN] Would execute: {' '.join(cmd)}")
                return True, "DRY-RUN: Command not executed"

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "Script execution timed out"
        except Exception as e:
            return False, f"Script execution failed: {str(e)}"

    def _run_applescript_inline(self, script_content: str) -> Tuple[bool, str]:
        """
        Run inline AppleScript content.

        Args:
            script_content: AppleScript code to execute

        Returns:
            Tuple of (success, output/error_message)
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would execute inline script")
                return True, "DRY-RUN: Script not executed"

            process = subprocess.Popen(
                ["osascript", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(input=script_content, timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                return False, "Script execution timed out"

            if process.returncode == 0:
                return True, stdout.strip()
            else:
                return False, stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "Script execution timed out"
        except Exception as e:
            return False, f"Script execution failed: {str(e)}"

    def get_existing_folders(self) -> Dict[str, str]:
        """
        Get existing playlist folders in Apple Music.

        Returns:
            Dictionary mapping folder names to persistent IDs
        """
        if self._folder_cache:
            return self._folder_cache

        script = """
tell application "Music"
    set folderInfo to {}
    try
        repeat with fld in folders
            set folderName to name of fld
            set folderID to persistent ID of fld
            set end of folderInfo to folderName & "|||" & folderID
        end repeat
    end try
    return folderInfo
end tell
"""

        success, output = self._run_applescript_inline(script)

        if not success:
            logger.error(f"Failed to get existing folders: {output}")
            return {}

        folders = {}
        if output and output != "DRY-RUN: Script not executed":
            try:
                # Parse the folder information
                folder_lines = output.split(",") if output else []
                for line in folder_lines:
                    line = line.strip()
                    if "|||" in line:
                        name, folder_id = line.split("|||", 1)
                        folders[name.strip()] = folder_id.strip()
            except Exception as e:
                logger.error(f"Failed to parse folder information: {e}")

        self._folder_cache = folders
        logger.info(f"Found {len(folders)} existing playlist folders")
        return folders

    def create_folder(self, folder_name: str) -> Tuple[bool, Optional[str]]:
        """
        Create a new playlist folder in Apple Music.

        Args:
            folder_name: Name of the folder to create

        Returns:
            Tuple of (success, folder_persistent_id)
        """
        logger.info(f"Creating playlist folder: {folder_name}")

        # Check if folder already exists
        existing_folders = self.get_existing_folders()
        if folder_name in existing_folders:
            logger.info(f"Folder '{folder_name}' already exists")
            return True, existing_folders[folder_name]

        script = f"""
tell application "Music"
    try
        set newFolder to make new playlist with properties {{name:"{folder_name}"}}
        set folderID to persistent ID of newFolder
        return folderID
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
"""

        success, output = self._run_applescript_inline(script)

        if success and not output.startswith("ERROR:") and output != "DRY-RUN: Script not executed":
            folder_id = output.strip()
            # Update cache
            self._folder_cache[folder_name] = folder_id
            logger.info(f"Successfully created folder '{folder_name}' with ID: {folder_id}")
            return True, folder_id
        else:
            error_msg = (
                output if output.startswith("ERROR:") else f"Failed to create folder: {output}"
            )
            logger.error(error_msg)
            return False, None

    def get_playlist_info(self, playlist_name: str) -> Optional[Dict[str, str]]:
        """
        Get information about a specific playlist.

        Args:
            playlist_name: Name of the playlist

        Returns:
            Dictionary with playlist info (name, persistent_id) or None
        """
        if playlist_name in self._playlist_cache:
            return self._playlist_cache[playlist_name]

        script = f"""
tell application "Music"
    try
        set pl to first playlist whose name is "{playlist_name}"
        set plID to persistent ID of pl
        set plName to name of pl
        return plName & "|||" & plID
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
"""

        success, output = self._run_applescript_inline(script)

        if success and not output.startswith("ERROR:") and "|||" in output:
            name, playlist_id = output.split("|||", 1)
            playlist_info = {"name": name.strip(), "persistent_id": playlist_id.strip()}
            self._playlist_cache[playlist_name] = playlist_info
            return playlist_info
        else:
            logger.warning(f"Could not find playlist: {playlist_name}")
            return None

    def move_playlist_to_folder(self, playlist_name: str, folder_name: str) -> bool:
        """
        Move a playlist to a specific folder.

        Args:
            playlist_name: Name of the playlist to move
            folder_name: Name of the target folder

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Moving playlist '{playlist_name}' to folder '{folder_name}'")

        # Get playlist information
        playlist_info = self.get_playlist_info(playlist_name)
        if not playlist_info:
            logger.error(f"Playlist not found: {playlist_name}")
            return False

        # Get or create target folder
        existing_folders = self.get_existing_folders()

        if folder_name not in existing_folders:
            logger.info(f"Folder '{folder_name}' doesn't exist, creating it...")
            success, folder_id = self.create_folder(folder_name)
            if not success or folder_id is None:
                logger.error(f"Failed to create folder: {folder_name}")
                return False
        else:
            folder_id = existing_folders[folder_name]

        # Move playlist using the move script
        playlist_id = playlist_info["persistent_id"]

        if self.dry_run:
            logger.info(
                f"[DRY-RUN] Would move playlist '{playlist_name}' (ID: {playlist_id}) "
                f"to folder '{folder_name}' (ID: {folder_id})"
            )
            return True

        success, output = self._run_applescript_file(
            "move_playlist_to_folder", [playlist_id, folder_id]
        )

        if success and "SUCCESS" in output:
            logger.info(f"Successfully moved playlist '{playlist_name}' to folder '{folder_name}'")
            return True
        else:
            logger.error(f"Failed to move playlist: {output}")
            return False

    def ensure_genre_folders_exist(self, target_genres: List[str]) -> Dict[str, bool]:
        """
        Ensure all target genre folders exist in Apple Music.

        Args:
            target_genres: List of genre folder names to create

        Returns:
            Dictionary mapping genre names to creation success status
        """
        logger.info(f"Ensuring {len(target_genres)} genre folders exist")

        results = {}
        existing_folders = self.get_existing_folders()

        for genre in target_genres:
            if genre in existing_folders:
                logger.info(f"Genre folder '{genre}' already exists")
                results[genre] = True
            else:
                logger.info(f"Creating genre folder: {genre}")
                success, _ = self.create_folder(genre)
                results[genre] = success

        return results

    def organize_playlists(self, playlist_assignments: Dict[str, str]) -> Dict[str, bool]:
        """
        Organize multiple playlists into their assigned folders.

        Args:
            playlist_assignments: Dictionary mapping playlist names to target folder names

        Returns:
            Dictionary mapping playlist names to move success status
        """
        logger.info(f"Organizing {len(playlist_assignments)} playlists")

        results = {}

        # Get all target folders
        target_folders = set(playlist_assignments.values())

        # Ensure all target folders exist
        folder_results = self.ensure_genre_folders_exist(list(target_folders))

        # Move playlists
        for playlist_name, folder_name in playlist_assignments.items():
            if not folder_results.get(folder_name, False):
                logger.error(
                    f"Cannot move playlist '{playlist_name}' - target folder '{folder_name}' unavailable"
                )
                results[playlist_name] = False
                continue

            success = self.move_playlist_to_folder(playlist_name, folder_name)
            results[playlist_name] = success

        # Summary
        successful_moves = sum(1 for success in results.values() if success)
        logger.info(
            f"Playlist organization complete: {successful_moves}/{len(playlist_assignments)} successful"
        )

        return results

    def _make_playlist_id(self, playlist_name: str) -> str:
        """Create a stable API-safe ID when Music persistent IDs are unavailable."""
        normalized = playlist_name.strip().lower().replace(" ", "-")
        normalized = "".join(ch for ch in normalized if ch.isalnum() or ch in {"-", "_"})
        return normalized or "unknown"

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """Return playlists in a shape expected by the web frontend API."""
        playlist_rows = self.apple_music.get_user_playlists_with_counts() or []
        playlist_ids = self.apple_music.get_playlist_ids() or {}
        playlists: List[Dict[str, Any]] = []
        excluded_names = {
            "music",
            "music videos",
            "favourite songs",
            "favorite songs",
        }

        # Fallback for older interface behavior: names without precomputed counts.
        if not playlist_rows:
            playlist_rows = [
                {"name": name, "track_count": 0}
                for name in (self.apple_music.get_user_playlist_names() or [])
            ]

        for row in playlist_rows:
            playlist_name = str(row.get("name", "")).strip()
            if not playlist_name:
                continue
            if playlist_name.lower() in excluded_names:
                continue
            track_count = int(row.get("track_count", 0) or 0)

            playlists.append(
                {
                    # Prefer persistent IDs from AppleScript files for stable identity.
                    "id": playlist_ids.get(playlist_name, self._make_playlist_id(playlist_name)),
                    "name": playlist_name,
                    "track_count": track_count,
                    "genre": None,
                    "created_date": None,
                }
            )

        return playlists

    def get_playlist_details(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Return detailed playlist data for a frontend playlist ID."""
        all_playlists = self.get_all_playlists()
        target = next((p for p in all_playlists if p.get("id") == playlist_id), None)

        if not target:
            return None

        playlist_name = str(target.get("name", "")).strip()
        tracks = self.apple_music.get_playlist_tracks(playlist_name) or []

        normalized_tracks = []
        for idx, track in enumerate(tracks, start=1):
            if not isinstance(track, dict):
                continue
            normalized_tracks.append(
                {
                    "id": f"{playlist_id}-track-{idx}",
                    "name": track.get("title") or track.get("name") or "Unknown Track",
                    "artist": track.get("artist") or "Unknown Artist",
                    "metadata": {
                        "album": track.get("album"),
                        "genre": track.get("genre"),
                        "bpm": track.get("bpm"),
                        "year": track.get("year"),
                        "composer": track.get("composer"),
                        "duration": track.get("duration"),
                    },
                }
            )

        return {
            "id": playlist_id,
            "name": playlist_name,
            "track_count": len(normalized_tracks),
            "genre": target.get("genre"),
            "tracks": normalized_tracks,
        }

    def clear_cache(self):
        """Clear internal caches for folders and playlists."""
        self._folder_cache.clear()
        self._playlist_cache.clear()
        logger.debug("Cleared playlist and folder caches")
