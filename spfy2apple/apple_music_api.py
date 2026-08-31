#!/usr/bin/env python3
"""
Apple Music catalog search and playlist management — free approach.

Uses the public iTunes Search API (no auth, no developer account) to find
tracks in the Apple Music catalog, and AppleScript to manage playlists.

For tracks NOT in the user's library, an optional macOS Shortcut
"spfy2apple Add Track" can be used to add catalog tracks to playlists.
Without the shortcut, missing tracks are reported with their Apple Music URLs.

No Apple Developer Program membership required.
"""

from __future__ import annotations

import json
import subprocess
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from spfy2apple.config import Config
from spfy2apple.logger import setup_logger

logger = setup_logger("spfy2apple.catalog")


# ──────────────────────────────────────────────────────────────────────
# iTunes Search API (free, no auth)
# ──────────────────────────────────────────────────────────────────────


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def search_itunes(term: str, limit: int = 5, entity: str = "song") -> List[Dict]:
    """Search the iTunes/Apple Music catalog via the free public API.

    Returns list of dicts with: trackId, trackName, artistName, collectionId, trackViewUrl.
    """
    try:
        resp = requests.get(
            ITUNES_SEARCH_URL,
            params={"term": term, "entity": entity, "limit": str(limit), "country": "US"},
            timeout=10,
        )
        if not resp.ok:
            return []
        data = resp.json()
        return data.get("results", [])
    except Exception as exc:
        logger.debug(f"iTunes search failed for '{term}': {exc}")
        return []


def find_track_in_catalog(title: str, artist: str) -> Optional[Dict]:
    """Search the Apple Music catalog for a track.

    Returns a dict with trackId, trackName, artistName, trackViewUrl, or None.
    """
    # Strategy 1: "title artist"
    results = search_itunes(f"{title} {artist}", limit=5)
    if results:
        match = _best_match(results, title, artist)
        if match:
            return match

    # Strategy 2: title only
    results = search_itunes(title, limit=5)
    if results:
        match = _best_match(results, title, artist)
        if match:
            return match

    # Strategy 3: cleaned title
    cleaned = _clean_title(title)
    if cleaned != title:
        results = search_itunes(f"{cleaned} {artist}", limit=5)
        if results:
            match = _best_match(results, title, artist)
            if match:
                return match

    return None


def _clean_title(title: str) -> str:
    """Remove common suffixes that differ between Spotify and Apple Music."""
    suffixes = [
        " (remix)", " (remix version)", " (extended)", " (extended version)",
        " (radio edit)", " (clean)", " (explicit)", " (live)", " (live version)",
        " (acoustic)", " (acoustic version)", " (instrumental)",
        " (original mix)", " (club mix)", " (album version)",
        " (single version)", " (radio version)", " (official video)",
        " (official)", " (feat.", " (ft.", " (featuring",
    ]
    title_lower = title.lower()
    for suffix in suffixes:
        if title_lower.endswith(suffix):
            return title[: len(title) - len(suffix)].strip()
    return title


def _best_match(results: List[Dict], title: str, artist: str) -> Optional[Dict]:
    """Pick the best matching track from iTunes search results."""
    title_lower = title.lower().strip()
    artist_lower = artist.lower().strip()

    # Filter to streamable songs only
    songs = [r for r in results if r.get("kind") == "song" and r.get("isStreamable", False)]
    if not songs:
        songs = [r for r in results if r.get("kind") == "song"]
    if not songs:
        songs = results

    # 1. Exact title + exact artist
    for r in songs:
        if (r.get("trackName", "").lower().strip() == title_lower
                and r.get("artistName", "").lower().strip() == artist_lower):
            return _normalize_result(r)

    # 2. Exact title + artist contains (handles "Artist A & Artist B" → "Artist A")
    for r in songs:
        r_artist = r.get("artistName", "").lower()
        artist_match = (
            artist_lower in r_artist
            or r_artist.strip() in artist_lower
        )
        if r.get("trackName", "").lower().strip() == title_lower and artist_match:
            return _normalize_result(r)

    # 3. Title partial + exact artist (handles "Song (feat. X)" ↔ "Song")
    for r in songs:
        r_title = r.get("trackName", "").lower().strip()
        title_match = title_lower in r_title or r_title in title_lower
        if title_match and r.get("artistName", "").lower().strip() == artist_lower:
            return _normalize_result(r)

    # No match — both title and artist must be present
    return None


def _normalize_result(r: Dict) -> Dict:
    """Normalize an iTunes search result into a standard format."""
    return {
        "trackId": r.get("trackId", ""),
        "trackName": r.get("trackName", ""),
        "artistName": r.get("artistName", ""),
        "collectionId": r.get("collectionId", ""),
        "trackViewUrl": r.get("trackViewUrl", ""),
        "isStreamable": r.get("isStreamable", False),
    }


# ──────────────────────────────────────────────────────────────────────
# Apple Music library search + playlist management (AppleScript)
# ──────────────────────────────────────────────────────────────────────


class AppleMusicLibrary:
    """Handles Apple Music library operations via AppleScript.

    Searches the user's library (not the catalog) and manages playlists.
    For catalog tracks not in the library, use the Shortcut integration.
    """

    def __init__(self, folder_name: str = "curated by others"):
        self.folder_name = folder_name
        self.logger = setup_logger("spfy2apple.library")

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _run_applescript(script: str, timeout: int = 300) -> Tuple[bool, str]:
        try:
            proc = subprocess.Popen(
                ["osascript", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(input=script, timeout=timeout)
            if proc.returncode != 0:
                return False, stderr.strip()
            return True, stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "AppleScript timed out"
        except Exception as exc:
            return False, str(exc)

    # ── Playlist / folder management ───────────────────────────────

    def get_all_playlist_names(self) -> List[str]:
        """Return all playlist and folder names in Apple Music."""
        script = """
tell application "Music"
    set itemNames to {}
    try
        repeat with pl in playlists
            set end of itemNames to name of pl
        end repeat
    end try
    try
        repeat with fld in folder playlists
            set end of itemNames to name of fld
        end repeat
    end try
    return itemNames
end tell
"""
        ok, output = self._run_applescript(script)
        if not ok or not output:
            return []
        return [n.strip() for n in output.split(",") if n.strip()]

    def ensure_folder(self, folder_name: str) -> bool:
        escaped = self._escape(folder_name)
        script = f"""
tell application "Music"
    try
        set matches to every folder playlist whose name is "{escaped}"
        if (count of matches) > 0 then
            return true
        end if
        make new folder playlist with properties {{name:"{escaped}"}}
        return true
    on error errMsg
        return false
    end try
end tell
"""
        ok, output = self._run_applescript(script)
        return ok and "true" in output.lower()

    def create_playlist(self, name: str, description: str = "") -> bool:
        escaped = self._escape(name)
        escaped_desc = self._escape(description) if description else ""
        if description:
            script = f"""
tell application "Music"
    try
        make new playlist with properties {{name:"{escaped}", description:"{escaped_desc}"}}
        return true
    on error errMsg
        try
            make new playlist with properties {{name:"{escaped}"}}
            set description of playlist "{escaped}" to "{escaped_desc}"
            return true
        on error
            return false
        end try
    end try
end tell
"""
        else:
            script = f"""
tell application "Music"
    try
        make new playlist with properties {{name:"{escaped}"}}
        return true
    on error errMsg
        return false
    end try
end tell
"""
        ok, output = self._run_applescript(script)
        return ok and "true" in output.lower()

    def set_playlist_description(self, playlist_name: str, description: str) -> bool:
        escaped_pl = self._escape(playlist_name)
        escaped_desc = self._escape(description)
        script = f"""
tell application "Music"
    try
        set thePlaylist to playlist "{escaped_pl}"
        set description of thePlaylist to "{escaped_desc}"
        return true
    on error errMsg
        return false
    end try
end tell
"""
        ok, output = self._run_applescript(script)
        return ok and "true" in output.lower()

    def move_playlist_to_folder(self, playlist_name: str, folder_name: str) -> bool:
        escaped_pl = self._escape(playlist_name)
        escaped_fld = self._escape(folder_name)
        script = f"""
tell application "Music"
    try
        set targetPlaylist to playlist "{escaped_pl}"
        set matches to every folder playlist whose name is "{escaped_fld}"
        if (count of matches) is 0 then error "Folder not found"
        set targetFolder to item 1 of matches
        move targetPlaylist to targetFolder
        return true
    on error errMsg
        return false
    end try
end tell
"""
        ok, output = self._run_applescript(script)
        return ok and "true" in output.lower()

    def delete_all_tracks(self, playlist_name: str) -> int:
        escaped_pl = self._escape(playlist_name)
        script = f"""
tell application "Music"
    try
        set thePlaylist to playlist "{escaped_pl}"
        set trackCount to count of tracks of thePlaylist
        if trackCount > 0 then
            delete every track of thePlaylist
        end if
        return trackCount
    on error errMsg
        return 0
    end try
end tell
"""
        ok, output = self._run_applescript(script, timeout=120)
        if not ok:
            return 0
        try:
            return int(output.strip())
        except ValueError:
            return 0

    # ── Library search ──────────────────────────────────────────────

    def search_library(self, title: str, artist: str) -> Optional[str]:
        """Search the Apple Music library for a track.

        Returns the persistent ID of the best match, or None.
        """
        pid = self._do_search(f"{title} {artist}", title, artist)
        if pid:
            return pid

        pid = self._do_search(title, title, artist)
        if pid:
            return pid

        cleaned = _clean_title(title)
        if cleaned != title:
            pid = self._do_search(cleaned, title, artist)
            if pid:
                return pid

        return None

    def _do_search(self, search_term: str, orig_title: str, orig_artist: str) -> Optional[str]:
        if not search_term or len(search_term.strip()) < 2:
            return None

        escaped_term = self._escape(search_term.strip())
        max_results = Config.MAX_SEARCH_RESULTS

        script = f"""
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
    set libPlaylist to item 1 of library playlists
    set searchResults to (search libPlaylist for "{escaped_term}")
    set outputLines to {{}}
    set maxResults to {max_results}
    set counter to 0
    repeat with trk in searchResults
        set counter to counter + 1
        if counter > maxResults then exit repeat
        set trkName to my cleanText(name of trk)
        set trkArtist to my cleanText(artist of trk)
        set trkID to my cleanText(persistent ID of trk)
        set AppleScript's text item delimiters to tab
        set end of outputLines to (trkID & tab & trkName & tab & trkArtist) as text
        set AppleScript's text item delimiters to ""
    end repeat
    set AppleScript's text item delimiters to linefeed
    set outputText to outputLines as text
    set AppleScript's text item delimiters to ""
    return outputText
end tell
"""
        ok, output = self._run_applescript(script, timeout=60)
        if not ok or not output:
            return None

        results: List[Dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                results.append(
                    {"persistent_id": parts[0], "name": parts[1], "artist": parts[2]}
                )

        if not results:
            return None

        return self._best_match_library(results, orig_title, orig_artist)

    @staticmethod
    def _best_match_library(results: List[Dict[str, str]], title: str, artist: str) -> Optional[str]:
        title_lower = title.lower().strip()
        artist_lower = artist.lower().strip()
        artist_normalized = unicodedata.normalize("NFC", artist_lower)

        # 1. Exact title + exact artist
        for r in results:
            if r["name"].lower().strip() == title_lower and r["artist"].lower().strip() == artist_lower:
                return r["persistent_id"]

        # 2. Exact title + artist contains (handles "Artist A, Artist B" → "Artist A")
        for r in results:
            r_artist = r["artist"].lower()
            r_artist_norm = unicodedata.normalize("NFC", r_artist)
            artist_match = (
                artist_lower in r_artist
                or artist_normalized in r_artist_norm
                or r_artist.strip() in artist_lower  # AM artist is subset of Spotify
            )
            if r["name"].lower().strip() == title_lower and artist_match:
                return r["persistent_id"]

        # 3. Title partial + exact artist (handles "Song (feat. X)" ↔ "Song")
        for r in results:
            r_title = r["name"].lower().strip()
            title_match = title_lower in r_title or r_title in title_lower
            if title_match and r["artist"].lower().strip() == artist_lower:
                return r["persistent_id"]

        # No match — both title and artist must be present
        return None

    def get_playlist_tracks(self, playlist_name: str) -> List[Tuple[str, str]]:
        """Return (name, artist) tuples for all tracks in the playlist."""
        escaped_pl = self._escape(playlist_name)
        script = f"""
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
    try
        set thePlaylist to playlist "{escaped_pl}"
        set outputLines to {{}}
        repeat with trk in (tracks of thePlaylist)
            set trkName to my cleanText(name of trk)
            set trkArtist to my cleanText(artist of trk)
            set end of outputLines to (trkName & tab & trkArtist)
        end repeat
        set AppleScript's text item delimiters to linefeed
        set outputText to outputLines as text
        set AppleScript's text item delimiters to ""
        return outputText
    on error errMsg
        return ""
    end try
end tell
"""
        ok, output = self._run_applescript(script, timeout=60)
        if not ok or not output:
            return []
        result = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                result.append((parts[0], parts[1]))
        return result

    def remove_tracks_from_playlist(self, playlist_name: str, tracks: List[Tuple[str, str]]) -> int:
        """Remove specific tracks (by name+artist) from a playlist. Returns count removed."""
        if not tracks:
            return 0

        escaped_pl = self._escape(playlist_name)
        # Build AppleScript list of {name, artist} pairs
        pairs_script = ", ".join(
            f'{{"{self._escape(name)}", "{self._escape(artist)}"}}'
            for name, artist in tracks
        )

        script = f"""
tell application "Music"
    try
        set thePlaylist to playlist "{escaped_pl}"
        set removeList to {{{pairs_script}}}
        set tracksToDelete to {{}}
        repeat with trk in (tracks of thePlaylist)
            set trkName to (name of trk) as text
            set trkArtist to (artist of trk) as text
            repeat with pair in removeList
                set pairName to (item 1 of pair) as text
                set pairArtist to (item 2 of pair) as text
                if (trkName = pairName) and (trkArtist = pairArtist) then
                    set end of tracksToDelete to trk
                    exit repeat
                end if
            end repeat
        end repeat
        set removedCount to count of tracksToDelete
        repeat with trk in tracksToDelete
            delete trk
        end repeat
        return removedCount
    on error errMsg
        return 0
    end try
end tell
"""
        ok, output = self._run_applescript(script, timeout=120)
        if not ok:
            self.logger.warning(f"remove_tracks_from_playlist failed for '{playlist_name}': {output}")
            return 0
        try:
            return int(output.strip())
        except ValueError:
            return 0

    def add_tracks_to_playlist(self, playlist_name: str, track_ids: List[str]) -> int:
        if not track_ids:
            return 0

        escaped_pl = self._escape(playlist_name)
        batch_size = Config.BATCH_ADD_SIZE
        total_added = 0

        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i: i + batch_size]
            id_list = ", ".join(f'"{self._escape(tid)}"' for tid in batch)
            script = f"""
tell application "Music"
    set libPlaylist to item 1 of library playlists
    set thePlaylist to playlist "{escaped_pl}"
    set trackIDs to {{{id_list}}}
    set addedCount to 0
    repeat with trackID in trackIDs
        try
            set tID to trackID as text
            set theTrack to (first track of libPlaylist whose persistent ID is tID)
            duplicate theTrack to thePlaylist
            set addedCount to addedCount + 1
        end try
    end repeat
    return addedCount
end tell
"""
            ok, output = self._run_applescript(script, timeout=120)
            if not ok:
                self.logger.error(f"Failed to add batch to '{playlist_name}': {output}")
                continue
            try:
                total_added += int(output.strip())
            except ValueError:
                pass
            time.sleep(0.5)

        return total_added


# ──────────────────────────────────────────────────────────────────────
# Shortcut integration (optional, for catalog tracks not in library)
# ──────────────────────────────────────────────────────────────────────


SHORTCUT_NAME = "spfy2apple Add Track"


def shortcut_exists() -> bool:
    """Check if the 'spfy2apple Add Track' shortcut is installed."""
    try:
        result = subprocess.run(
            ["shortcuts", "list"],
            capture_output=True, text=True, timeout=10
        )
        return SHORTCUT_NAME in result.stdout
    except Exception:
        return False


def add_track_via_shortcut(track_name: str, artist: str, playlist_name: str) -> bool:
    """Add a catalog track to a playlist using the macOS Shortcut.

    Requires the 'spfy2apple Add Track' shortcut to be installed.
    See README for setup instructions.
    """
    if not shortcut_exists():
        return False

    # Pass structured input: "track_name|artist|playlist_name"
    inp = f"{track_name}|{artist}|{playlist_name}"
    try:
        proc = subprocess.Popen(
            ["shortcuts", "run", SHORTCUT_NAME, "-i", inp],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = proc.communicate(timeout=60)
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        logger.warning(f"Shortcut timed out for '{track_name}'")
        return False
    except Exception as exc:
        logger.warning(f"Shortcut failed for '{track_name}': {exc}")
        return False


# ──────────────────────────────────────────────────────────────────────
# Combined track finder (library + catalog)
# ──────────────────────────────────────────────────────────────────────


class TrackFinder:
    """Finds tracks in the Apple Music library or catalog.

    Strategy:
    1. Search the user's library (AppleScript) — fast, works for tracks already added
    2. If not in library, search the iTunes catalog (free API) — finds the track ID
    3. If found in catalog but not in library, optionally use a Shortcut to add it
    4. If no shortcut, return None and report the Apple Music URL
    """

    def __init__(self, library: AppleMusicLibrary, use_shortcut: bool = True):
        self.library = library
        self.use_shortcut = use_shortcut and shortcut_exists()
        self.logger = setup_logger("spfy2apple.finder")
        if use_shortcut and not self.use_shortcut:
            self.logger.info(
                f"ℹ️  Shortcut '{SHORTCUT_NAME}' not found — "
                f"catalog tracks won't be added automatically. See README."
            )

    def find_and_add(
        self,
        title: str,
        artist: str,
        playlist_name: str,
    ) -> Tuple[Optional[str], str]:
        """Find a track and return (persistent_id, source).

        source is one of: 'library', 'catalog+shortcut', 'catalog_only', 'not_found'
        """
        # 1. Search library
        pid = self.library.search_library(title, artist)
        if pid:
            return pid, "library"

        # 2. Search catalog (free iTunes API)
        catalog_match = find_track_in_catalog(title, artist)
        if not catalog_match:
            return None, "not_found"

        # 3. Try shortcut to add catalog track to library + playlist
        if self.use_shortcut:
            if add_track_via_shortcut(title, artist, playlist_name):
                # After adding via shortcut, search library again
                time.sleep(1)
                pid = self.library.search_library(title, artist)
                if pid:
                    return pid, "catalog+shortcut"

        # 4. Track exists in catalog but we can't add it automatically
        return None, "catalog_only"

    def find_all_tracks(
        self,
        tracks: List[Dict],
        playlist_name: str,
        workers: int = 4,
    ) -> Tuple[List[str], int, int, List[Dict]]:
        """Search for all tracks in parallel.

        Returns:
            (found_pids, count_found, count_not_found, catalog_only_tracks)
            catalog_only_tracks has dicts with: title, artist, url
        """
        total = len(tracks)
        workers = min(workers, total)
        results: Dict[int, Tuple[Optional[str], str]] = {}
        done_count = 0
        catalog_only: List[Dict] = []

        # Use fewer workers for AppleScript (each spawns osascript)
        # but more workers for catalog search (HTTP requests)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_idx = {
                pool.submit(
                    self.find_and_add, track["title"], track["artist"], playlist_name
                ): i
                for i, track in enumerate(tracks)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception:
                    results[idx] = (None, "not_found")
                done_count += 1
                if done_count % 25 == 0 or done_count == total:
                    self.logger.info(f"  Searching: {done_count}/{total}")

        # Collect in original order
        found_ids: List[str] = []
        not_found_count = 0
        for i in range(total):
            pid, source = results.get(i, (None, "not_found"))
            if pid:
                found_ids.append(pid)
            else:
                not_found_count += 1
                if source == "catalog_only":
                    track = tracks[i]
                    catalog_match = find_track_in_catalog(track["title"], track["artist"])
                    if catalog_match:
                        catalog_only.append({
                            "title": track["title"],
                            "artist": track["artist"],
                            "url": catalog_match.get("trackViewUrl", ""),
                        })

        # Deduplicate persistent IDs while preserving order
        seen: set[str] = set()
        deduped: List[str] = []
        for pid in found_ids:
            if pid not in seen:
                seen.add(pid)
                deduped.append(pid)

        return deduped, len(deduped), not_found_count, catalog_only
