"""
AppleScript interface for Apple Music integration.

Handles reading playlists, extracting track metadata, and moving playlists.
Supports both regular playlists and playlist folders.
Used by: plsort, metad_enr, 4tempers

NOTE: Whitelist filtering is handled by the calling code using shared.config module.
This interface just returns all playlists; the caller decides which to process.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.logger import setup_logger

logger = setup_logger(__name__)


class AppleMusicInterface:
    """Interface to Apple Music via AppleScript."""

    def __init__(self, scripts_dir: str = "scripts"):
        """
        Initialize Apple Music interface.

        Args:
            scripts_dir: Directory containing AppleScript templates

        Note: Whitelist filtering is handled externally via shared.config module
        """
        # Resolve scripts directory robustly across entrypoints/cwds.
        requested = Path(scripts_dir)
        candidates = [
            requested,
            Path.cwd() / requested,
            Path.cwd() / "src" / "scripts",
            Path(__file__).resolve().parent / "scripts",
        ]

        resolved = next((p for p in candidates if p.exists() and p.is_dir()), requested)
        self.scripts_dir = str(resolved)

    def _run_applescript(self, script: str) -> Tuple[bool, str]:
        """
        Run AppleScript and return result.

        Returns:
            (success: bool, output: str)
        """
        try:
            process = subprocess.Popen(
                ["osascript", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = process.communicate(input=script, timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                return False, "AppleScript execution timed out after 120s"

            if process.returncode != 0:
                return False, stderr

            return True, stdout.strip()
        except Exception as e:
            return False, str(e)

    def _load_script_template(self, template_name: str) -> str:
        """Load AppleScript template from file."""
        script_path = os.path.join(self.scripts_dir, f"{template_name}.applescript")
        try:
            with open(script_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"AppleScript template not found: {script_path}")

    def get_playlist_names(self) -> Optional[List[str]]:
        """
        Get list of all playlist names AND folder names in Apple Music.

        Includes both regular playlists and playlist folders.

        Returns:
            List of playlist/folder names or empty list if failed
        """
        script = """
tell application "Music"
    set itemNames to {}
    
    -- Get regular playlists from library
    try
        repeat with pl in playlists
            set end of itemNames to name of pl
        end repeat
    end try
    
    -- Get playlist folders
    try
        repeat with fld in folders
            set end of itemNames to name of fld
        end repeat
    end try
    
    return itemNames
end tell
"""
        success, output = self._run_applescript(script)
        if not success:
            # Fallback: just get playlists
            script_fallback = """
tell application "Music"
    set playlistNames to {}
    repeat with pl in playlists
        set end of playlistNames to name of pl
    end repeat
    return playlistNames
end tell
"""
            success, output = self._run_applescript(script_fallback)
            if not success:
                return []

        # Parse output (AppleScript returns items separated by commas)
        if not output:
            return []

        # Simple split on comma and clean up
        playlist_names = [name.strip() for name in output.split(",")]

        # Return all playlists without filtering
        # (whitelist filtering is handled by the caller via shared.config module)
        return playlist_names

    def get_user_playlist_names(self) -> Optional[List[str]]:
        """
        Get list of user playlists only (exclude system/library playlists and folders).

        Returns:
            List of user playlist names or empty list if failed
        """
        script = """
tell application "Music"
    set playlistNames to {}
    try
        repeat with pl in (every user playlist)
            set end of playlistNames to name of pl
        end repeat
        return playlistNames
    on error
        return {}
    end try
end tell
"""
        success, output = self._run_applescript(script)
        if not success or not output:
            return []

        return [name.strip() for name in output.split(",") if name.strip()]

    def get_user_playlists_with_counts(self) -> List[Dict[str, int | str]]:
        """
        Get user playlists with track counts using a single AppleScript call.

        Returns:
            List of dictionaries: {"name": <playlist_name>, "track_count": <int>}
        """
        script = """
tell application "Music"
    set outLines to {}
    try
        repeat with pl in (every user playlist)
            set plName to name of pl
            set trackCount to 0
            try
                set trackCount to count of tracks of pl
            end try
            set end of outLines to plName & "|||" & (trackCount as text)
        end repeat
        return outLines
    on error
        return {}
    end try
end tell
"""
        success, output = self._run_applescript(script)
        if not success or not output:
            return []

        results: List[Dict[str, int | str]] = []
        for item in output.split(","):
            entry = item.strip()
            if "|||" not in entry:
                continue
            name, count_text = entry.split("|||", 1)
            try:
                track_count = int(count_text.strip())
            except ValueError:
                track_count = 0
            results.append({"name": name.strip(), "track_count": track_count})

        return results

    def is_folder(self, item_name: str) -> bool:
        """Check if an item is a folder (True) or playlist (False)."""
        script = f"""
tell application "Music"
    try
        set targetFolder to folder "{item_name}"
        return true
    on error
        return false
    end try
end tell
"""
        success, output = self._run_applescript(script)
        return success and "true" in output.lower()

    def get_playlist_tracks(self, playlist_name: str) -> Optional[List[Dict]]:
        """
        Get all tracks from a playlist or folder with metadata.

        Automatically detects if item is a folder or playlist and gets tracks accordingly.

        Returns:
            List of track metadata dicts or empty list if failed
        """
        # Try both approaches: regular playlist first, then as folder

        # Approach 1: Try as regular playlist
        tracks = self._get_regular_playlist_tracks(playlist_name)
        if tracks:
            return tracks

        # Approach 2: Try as folder
        tracks = self._get_folder_all_tracks(playlist_name)
        if tracks:
            return tracks

        # If both failed
        return []

    def get_favourite_tracks(self) -> List[Dict]:
        """Return tracks from Apple Music's Favourite Songs playlist."""
        return [
            self._normalize_track_dict(track)
            for track in self._get_favourite_songs_tracks()
        ]

    def _get_favourite_songs_tracks(self) -> List[Dict]:
        """Get only the Favourite Songs fields needed for curation preview."""
        script = """
on cleanText(rawValue)
    try
        set textValue to rawValue as text
    on error
        set textValue to ""
    end try
    set textValue to my replaceText(tab, " ", textValue)
    set textValue to my replaceText(linefeed, " ", textValue)
    set textValue to my replaceText(return, " ", textValue)
    return textValue
end cleanText

on replaceText(findText, replaceTextValue, sourceText)
    set oldDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to findText
    set textItems to text items of sourceText
    set AppleScript's text item delimiters to replaceTextValue
    set sourceText to textItems as text
    set AppleScript's text item delimiters to oldDelimiters
    return sourceText
end replaceText

tell application "Music"
    set trackRows to {}
    set oldDelimiters to AppleScript's text item delimiters
    try
        set targetPlaylist to playlist "Favourite Songs"
        set trackTotal to count of tracks of targetPlaylist
        set trackIDs to persistent ID of every track of targetPlaylist
        set trackNames to name of every track of targetPlaylist
        set trackArtists to artist of every track of targetPlaylist
        set trackGenres to genre of every track of targetPlaylist
        repeat with trackIndex from 1 to trackTotal
            set trackPID to my cleanText(item trackIndex of trackIDs)
            set trackName to my cleanText(item trackIndex of trackNames)
            set trackArtist to my cleanText(item trackIndex of trackArtists)
            set trackGenre to my cleanText(item trackIndex of trackGenres)
            set AppleScript's text item delimiters to tab
            set end of trackRows to {trackPID, trackName, trackArtist, trackGenre} as text
        end repeat
        set AppleScript's text item delimiters to linefeed
        set outputText to trackRows as text
        set AppleScript's text item delimiters to oldDelimiters
        return outputText
    on error errMsg
        set AppleScript's text item delimiters to oldDelimiters
        error errMsg
    end try
end tell
"""
        success, output = self._run_applescript(script)
        if not success:
            raise RuntimeError(f"Failed to load Favourite Songs tracks: {output}")
        if not output:
            return []
        return self._parse_favourite_songs_output(output)

    def _parse_favourite_songs_output(self, output: str) -> List[Dict]:
        tracks: List[Dict] = []
        for row in output.splitlines():
            fields = row.split("\t")
            if len(fields) < 4:
                fields.extend([""] * (4 - len(fields)))
            persistent_id, name, artist, genre = fields[:4]
            tracks.append(
                {
                    "persistent_id": persistent_id,
                    "title": name,
                    "name": name,
                    "artist": artist,
                    "genre": genre,
                }
            )
        return tracks

    def _normalize_track_dict(self, track: Dict) -> Dict:
        """Normalize Apple Music track identity fields while preserving raw keys."""
        normalized = dict(track)

        name = normalized.get("name")
        title = normalized.get("title")
        if (name is None or str(name).strip() == "") and title is not None:
            normalized["name"] = title
        if (title is None or str(title).strip() == "") and name is not None:
            normalized["title"] = name

        persistent_id = (
            normalized.get("persistent_id")
            or normalized.get("persistent ID")
            or normalized.get("persistent id")
            or normalized.get("persistentId")
            or normalized.get("persistentID")
        )
        if persistent_id is not None and str(persistent_id).strip():
            normalized["persistent_id"] = str(persistent_id).strip()

        return normalized

    def _get_regular_playlist_tracks(self, playlist_name: str) -> Optional[List[Dict]]:
        """Get tracks from a regular (non-folder) playlist."""
        script = f"""
tell application "Music"
    set trackList to {{}}
    
    try
        set targetPlaylist to playlist "{playlist_name}"
        set trackCount to count of tracks of targetPlaylist
        if trackCount > 0 then
            repeat with trk in tracks of targetPlaylist
                set trackInfo to {{title:name of trk, name:name of trk, persistent_id:persistent ID of trk, artist:artist of trk, album:album of trk, genre:genre of trk, bpm:bpm of trk, year:year of trk, composer:composer of trk, duration:duration of trk}}
                set end of trackList to trackInfo
            end repeat
        end if
        return trackList
    on error errMsg
        return {{}}
    end try
end tell
"""
        success, output = self._run_applescript(script)
        if not success:
            raise RuntimeError(f"Failed to load playlist tracks: {output}")
        if not output:
            return None

        tracks = self._parse_applescript_dict_list(output)
        return tracks if tracks else None

    def _get_folder_all_tracks(self, folder_name: str) -> Optional[List[Dict]]:
        """
        Get all tracks from all playlists within a folder.
        """
        # Step 1: Get list of playlists in the folder
        script = f"""
tell application "Music"
    set playlistNames to {{}}
    try
        set targetFolder to folder "{folder_name}"
        set playlistCount to count of playlists in targetFolder
        if playlistCount > 0 then
            repeat with pl in playlists in targetFolder
                set end of playlistNames to name of pl
            end repeat
        end if
    on error
        return {{}}
    end try
    return playlistNames
end tell
"""
        success, output = self._run_applescript(script)
        if not success or not output:
            return None

        # Parse playlist names
        playlist_names = [name.strip() for name in output.split(",") if name.strip()]

        if not playlist_names:
            return None

        # Step 2: Get tracks from each playlist in folder
        all_tracks = []
        for pl_name in playlist_names:
            tracks = self._get_regular_playlist_tracks(pl_name)
            if tracks:
                all_tracks.extend(tracks)

        return all_tracks if all_tracks else None

    def create_playlist_folder(self, folder_name: str, parent_folder: Optional[str] = None) -> bool:
        """
        Create a playlist folder in Apple Music.

        Returns:
            True if successful, False otherwise
        """
        if parent_folder:
            script = f"""
tell application "Music"
    try
        make new folder in folder "{parent_folder}" with properties {{name:"{folder_name}"}}
        return true
    on error errMsg
        return false
    end try
end tell
"""
        else:
            script = f"""
tell application "Music"
    try
        make new folder with properties {{name:"{folder_name}"}}
        return true
    on error errMsg
        return false
    end try
end tell
"""
        success, output = self._run_applescript(script)
        return success and "true" in output.lower()

    def move_playlist_to_folder(self, playlist_name: str, folder_name: str) -> bool:
        """
        Move a playlist to a specific folder.

        Returns:
            True if successful, False otherwise
        """
        script = f"""
tell application "Music"
    try
        set targetPlaylist to playlist "{playlist_name}"
        set targetFolder to folder "{folder_name}"
        move targetPlaylist to targetFolder
        return true
    on error errMsg
        return false
    end try
end tell
"""
        success, output = self._run_applescript(script)
        return success and "true" in output.lower()

    def create_playlist_if_missing(self, playlist_name: str) -> bool:
        """
        Create a new playlist if it doesn't exist.

        Returns:
            True if successful or already exists, False otherwise
        """
        script = f"""
tell application "Music"
    try
        set existing to playlist "{playlist_name}"
        return true
    on error
        try
            make new playlist with properties {{name:"{playlist_name}"}}
            return true
        on error
            return false
        end try
    end try
end tell
"""
        success, output = self._run_applescript(script)
        return success and "true" in output.lower()

    def _parse_applescript_dict_list(self, output: str) -> Optional[List[Dict]]:
        """
        Parse AppleScript dictionary list output.

        AppleScript returns data in a format like: {key1:value1, key2:value2}, {key1:value1, ...}

        This is a simplified parser - production code might need more robust parsing.
        """
        if not output:
            return None

        tracks = []

        # Pattern to match dict-like structures: {key:value, key:value, ...}
        dict_pattern = r"\{([^}]+)\}"
        matches = re.findall(dict_pattern, output)

        for match in matches:
            track_dict = {}
            # Parse key:value pairs
            pairs = match.split(",")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    # Try to convert to int
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                    track_dict[key] = value

            if track_dict:
                tracks.append(self._normalize_track_dict(track_dict))

        return tracks if tracks else None

    def get_playlist_folder_structure(self) -> Optional[Dict]:
        """
        Get the current folder structure of playlists.

        Returns:
            Hierarchical dict or None if failed
        """
        script = """
tell application "Music"
    set outputLines to {}
    set oldTID to AppleScript's text item delimiters
    repeat with folderItem in folders
        set folderName to name of folderItem
        set playlistNames to {}
        repeat with playlistItem in playlists of folderItem
            set end of playlistNames to (name of playlistItem)
        end repeat

        set AppleScript's text item delimiters to "|||"
        set playlistText to playlistNames as text
        set AppleScript's text item delimiters to oldTID

        set end of outputLines to (folderName & "||" & playlistText)
    end repeat

    set AppleScript's text item delimiters to linefeed
    set outputText to outputLines as text
    set AppleScript's text item delimiters to oldTID
    return outputText
end tell
"""
        success, output = self._run_applescript(script)
        if not success:
            return None

        if output is None:
            return None

        output = output.strip()
        if not output:
            return {}

        folder_structure: Dict[str, List[str]] = {}
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            if "||" not in line:
                logger.warning(
                    f"event=folder_structure_parse_failed reason=missing_separator line={line}"
                )
                return None

            folder_name, playlists_raw = line.split("||", 1)
            folder_name = folder_name.strip()
            if not folder_name:
                logger.warning("event=folder_structure_parse_failed reason=empty_folder_name")
                return None

            playlist_names = []
            if playlists_raw:
                playlist_names = [p.strip() for p in playlists_raw.split("|||") if p.strip()]

            folder_structure[folder_name] = playlist_names

        return folder_structure

    def get_apple_music_version(self) -> Optional[str]:
        """Get the version of Apple Music/iTunes app."""
        script = """
tell application "Music"
    return version
end tell
"""
        success, output = self._run_applescript(script)
        return output if success else None

    def get_playlist_ids(self) -> Dict[str, str]:
        """Get all user playlists with their persistent hex IDs.

        Extracts the persistent unique identifiers (16 hex digits) for each playlist,
        which are used by Music.app and persist across sessions. Essential for
        reliable playlist identification.

        Returns:
            Dictionary mapping playlist names to their hex IDs

        Example:
            {'My Playlist': 'A1B2C3D4E5F6G7H8', 'Favorites': 'F1E2D3C4B5A6G7H8'}
        """
        try:
            script_path = os.path.join(self.scripts_dir, "get_ids_playlists.applescript")
            result = subprocess.run(
                ["osascript", script_path], capture_output=True, text=True, timeout=30
            )

            if not result.stdout:
                logger.error("Failed to get playlist IDs from AppleScript")
                return {}

            return self._parse_playlist_ids(result.stdout)

        except subprocess.TimeoutExpired:
            logger.error("AppleScript timeout while fetching playlist IDs")
            return {}
        except FileNotFoundError:
            logger.error(f"AppleScript template not found: get_ids_playlists.applescript")
            return {}
        except Exception as e:
            logger.error(f"Error getting playlist IDs: {e}")
            return {}

    @staticmethod
    def _parse_playlist_ids(output: str) -> Dict[str, str]:
        """Parse AppleScript output to extract playlist names and hex IDs.

        Args:
            output: Raw AppleScript output containing name:VALUE and id:HEXID patterns

        Returns:
            Dictionary mapping playlist names to hex IDs
        """
        playlists = {}

        # Find all hex IDs (16 hex digits - Music.app standard)
        id_pattern = r"([A-F0-9]{16})"
        id_matches = list(re.finditer(id_pattern, output, re.IGNORECASE))

        if not id_matches:
            logger.warning("No playlist IDs found in AppleScript output")
            return {}

        # For each ID found, work backward to find the corresponding name
        for id_match in id_matches:
            hex_id = id_match.group(1)
            pos = id_match.start()
            before_id = output[:pos]

            # Find the last "name:" label before this ID
            # Match: name:VALUE where VALUE can have spaces, hyphens, numbers, letters
            name_pattern = r"name:([^,]*?)(?:,\s*id:|$)"
            name_matches = list(re.finditer(name_pattern, before_id))

            if name_matches:
                # Get the last (most recent) name match
                last_name_match = name_matches[-1]
                name = last_name_match.group(1).strip()

                # Remove quotes if present
                if (name.startswith("'") and name.endswith("'")) or (
                    name.startswith('"') and name.endswith('"')
                ):
                    name = name[1:-1]

                if name:  # Only add if we got a valid name
                    playlists[name] = hex_id
                    logger.debug(f"Found playlist: {name} -> {hex_id}")

        if not playlists:
            logger.warning("No valid playlist name/ID pairs extracted from output")

        return playlists
