#!/usr/bin/env python3
"""
Spotify → Apple Music Playlist Sync

Syncs Spotify playlists that the user follows (but didn't create) to Apple Music.
Playlists are placed in an Apple Music playlist folder named "curated by others".

  - New playlists → created in Apple Music, moved to the folder
  - Existing synced playlists → updated when the Spotify version changes
    (tracks added/removed to mirror the current Spotify state)
  - Playlists already in Apple Music (not created by this tool) → skipped

Requirements:
  - Spotify API credentials (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET in .env)
  - macOS with Music.app running
  - No Apple Developer Program required — uses iTunes Search API + AppleScript

Usage:
  # Preview what would be synced (default — no changes made)
  python3 sync_from_spotify.py

  # Actually create / update playlists
  python3 sync_from_spotify.py --apply

  # Force re-sync of all tracked playlists (ignore snapshot cache)
  python3 sync_from_spotify.py --apply --force

  # Just list followed Spotify playlists
  python3 sync_from_spotify.py --list-only

  # Show sync state (which playlists are tracked)
  python3 sync_from_spotify.py --show-state

  # Custom folder name
  python3 sync_from_spotify.py --apply --folder-name "From Spotify"
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Ensure the spfy2apple package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from spfy2apple.config import Config
from spfy2apple.logger import setup_logger
from apple_music_api import AppleMusicLibrary, TrackFinder, find_track_in_catalog, shortcut_exists, SHORTCUT_NAME

logger = setup_logger("spfy2apple")


# ──────────────────────────────────────────────────────────────────────
# Playlist filter (allowlist of Spotify playlist names to sync)
# ──────────────────────────────────────────────────────────────────────


class PlaylistFilter:
    """Loads a text file of playlist names to sync. Empty/missing = sync all.

    Matching is case-insensitive and Unicode-normalised (NFC + casefold),
    so filter entries can be written in any case and still match Spotify names.
    Original (un-normalised) names are preserved for display.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or Config.PLAYLIST_FILTER_PATH)
        self.original_names: list[str] = []  # original text for display
        self.names: set[str] = self._load()  # normalised keys

    @staticmethod
    def _normalise(name: str) -> str:
        # Normalise Unicode, then collapse apostrophe variants to ASCII '
        text = unicodedata.normalize("NFC", name).casefold().strip()
        text = text.replace("\u2018", "'").replace("\u2019", "'")  # ‘ ’
        text = text.replace("\u201a", "'").replace("\u201b", "'")  # ‚ ‛
        return text

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            names: set[str] = set()
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    self.original_names.append(line)
                    names.add(self._normalise(line))
            return names
        except Exception:
            return set()

    def is_active(self) -> bool:
        """True if the filter has entries (i.e. is restricting which playlists to sync)."""
        return bool(self.names)

    def allows(self, name: str) -> bool:
        """True if this playlist name should be synced."""
        if not self.names:
            return True
        return self._normalise(name) in self.names

    def matched_count(self) -> int:
        return len(self.names)

    def unmatched_entries(self, matched_names: list[str]) -> list[str]:
        """Return original filter entries that didn't match any of the given playlist names."""
        matched_norm = {self._normalise(n) for n in matched_names}
        return [orig for orig in self.original_names if self._normalise(orig) not in matched_norm]


# ──────────────────────────────────────────────────────────────────────
# Sync state (tracks which playlists we've synced + snapshot IDs)
# ──────────────────────────────────────────────────────────────────────


class SyncState:
    """Persists sync state so we can detect Spotify changes and update existing playlists."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or Config.STATE_PATH)
        self.logger = setup_logger("spfy2apple.state")
        self.state: Dict = self._load()

    def _load(self) -> Dict:
        if not self.path.exists():
            return {"playlists": {}}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "playlists" not in data:
                return {"playlists": {}}
            return data
        except Exception as exc:
            self.logger.warning(f"Failed to load sync state: {exc}")
            return {"playlists": {}}

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.logger.warning(f"Failed to save sync state: {exc}")

    def get(self, spotify_id: str) -> Optional[Dict]:
        return self.state["playlists"].get(spotify_id)

    def is_synced(self, spotify_id: str) -> bool:
        return spotify_id in self.state["playlists"]

    def snapshot_unchanged(self, spotify_id: str, snapshot_id: str) -> bool:
        entry = self.get(spotify_id)
        return bool(entry and entry.get("spotify_snapshot_id") == snapshot_id)

    def record(
        self,
        spotify_id: str,
        name: str,
        snapshot_id: str,
        track_count: int,
        apple_music_id: str = "",
    ) -> None:
        self.state["playlists"][spotify_id] = {
            "name": name,
            "spotify_snapshot_id": snapshot_id,
            "track_count": track_count,
            "apple_music_id": apple_music_id,
            "last_synced": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def get_apple_music_id(self, spotify_id: str) -> str:
        """Return the stored Apple Music playlist ID, or empty string."""
        entry = self.get(spotify_id)
        return entry.get("apple_music_id", "") if entry else ""

    def remove(self, spotify_id: str) -> None:
        self.state["playlists"].pop(spotify_id, None)
        self.save()

    def all_entries(self) -> Dict[str, Dict]:
        return self.state.get("playlists", {})


# ──────────────────────────────────────────────────────────────────────
# Spotify reader
# ──────────────────────────────────────────────────────────────────────


def _clean_spotify_description(desc: str) -> str:
    """Clean a Spotify playlist description for use in Apple Music.

    Spotify descriptions may contain HTML entities and occasional tags.
    We unescape entities and strip any remaining HTML tags.
    """
    if not desc:
        return ""
    # Unescape HTML entities (e.g. &amp; → &)
    text = html.unescape(desc)
    # Remove any HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


class SpotifyReader:
    """Reads playlists from Spotify that the user follows but didn't create."""

    def __init__(self):
        self.logger = setup_logger("spfy2apple.spotify")
        self.sp: Optional[spotipy.Spotify] = None
        self.user_id: str = ""
        self._authenticate()

    def _authenticate(self):
        try:
            Config.validate()
            config = Config.get_spotify_config()
            config["cache_path"] = Config.token_cache_path()
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(**config))
            user = self.sp.me()
            self.user_id = user["id"]
            display = user.get("display_name", self.user_id)
            self.logger.info(f"Authenticated as Spotify user: {display}")
        except Exception as exc:
            raise RuntimeError(f"Spotify authentication failed: {exc}")

    def get_followed_playlists(self) -> List[Dict]:
        """Return playlists the user follows but doesn't own."""
        playlists: List[Dict] = []
        offset = 0
        limit = 50

        while True:
            results = self.sp.current_user_playlists(limit=limit, offset=offset)
            for pl in results["items"]:
                owner_id = pl.get("owner", {}).get("id", "")
                if owner_id and owner_id != self.user_id:
                    playlists.append(
                        {
                            "id": pl["id"],
                            "name": pl["name"],
                            "description": _clean_spotify_description(pl.get("description", "")),
                            "owner": pl.get("owner", {}).get("display_name", owner_id),
                            "owner_id": owner_id,
                            "tracks_total": pl["tracks"]["total"],
                            "snapshot_id": pl.get("snapshot_id", ""),
                        }
                    )

            if len(results["items"]) < limit:
                break
            offset += limit

        self.logger.info(f"Found {len(playlists)} followed playlists (not owned by you)")
        return playlists

    def get_playlist_tracks(self, playlist_id: str) -> Tuple[List[Dict], str]:
        """Return all tracks from a Spotify playlist plus the current snapshot ID.

        Returns:
            (tracks, snapshot_id)
        """
        tracks: List[Dict] = []
        offset = 0
        limit = 100
        snapshot_id = ""

        # First call gets us the snapshot_id
        first = self.sp.playlist(playlist_id, fields="snapshot_id")
        snapshot_id = first.get("snapshot_id", "")

        while True:
            results = self.sp.playlist_items(playlist_id, limit=limit, offset=offset)
            for item in results["items"]:
                track = item.get("track")
                if not track:
                    continue
                name = track.get("name", "")
                artists = track.get("artists", [])
                if not name or not artists:
                    continue
                tracks.append(
                    {
                        "title": name,
                        "artist": artists[0].get("name", ""),
                        "album": track.get("album", {}).get("name", ""),
                    }
                )

            if len(results["items"]) < limit:
                break
            offset += limit

        return tracks, snapshot_id


# ──────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────


class SpotifyToAppleSync:
    """Coordinates the sync from Spotify followed playlists to Apple Music."""

    def __init__(
        self,
        dry_run: bool = True,
        folder_name: str = "curated by others",
        force: bool = False,
        filter_path: Optional[str] = None,
    ):
        self.dry_run = dry_run
        self.folder_name = folder_name
        self.force = force
        self.logger = setup_logger("spfy2apple.sync")
        self.spotify = SpotifyReader()
        self.apple_music = AppleMusicLibrary(folder_name=folder_name)
        self.track_finder = TrackFinder(self.apple_music)
        self.state = SyncState()
        self.filter = PlaylistFilter(filter_path)

    def sync(self) -> Dict[str, Dict]:
        """Run the full sync. Returns per-playlist stats."""
        # 1. Read Spotify followed playlists
        self.logger.info("🎵 Reading Spotify playlists...")
        spotify_playlists = self.spotify.get_followed_playlists()

        if not spotify_playlists:
            self.logger.info("No followed playlists found on Spotify. Nothing to do.")
            return {}

        # 1b. Apply playlist filter if active
        if self.filter.is_active():
            before = len(spotify_playlists)
            spotify_playlists = [
                pl for pl in spotify_playlists if self.filter.allows(pl["name"])
            ]
            self.logger.info(
                f"📋 Filter active: {len(spotify_playlists)}/{before} playlists match "
                f"'{self.filter.path.name}'"
            )
            if not spotify_playlists:
                self.logger.info("No followed playlists match the filter. Nothing to do.")
                return {}

        # 2. Read existing Apple Music playlist names (via AppleScript)
        self.logger.info("🍎 Reading Apple Music playlists...")
        am_names = set(self.apple_music.get_all_playlist_names())

        # 3. Classify each Spotify playlist: create / update / skip
        to_create: List[Dict] = []
        to_update: List[Dict] = []
        skipped: List[Tuple[str, str]] = []

        for pl in spotify_playlists:
            sp_id = pl["id"]
            name = pl["name"]
            snapshot = pl.get("snapshot_id", "")

            if self.state.is_synced(sp_id):
                # We've synced this before — check for changes
                if not self.force and self.state.snapshot_unchanged(sp_id, snapshot):
                    skipped.append((name, "unchanged"))
                    self.logger.info(f"  ⏩ Skipping '{name}' (Spotify snapshot unchanged)")
                else:
                    to_update.append(pl)
                    self.logger.info(f"  🔄 Will update '{name}' (Spotify changed)")
            elif name in am_names:
                # Exists in Apple Music but not tracked by us → user-created, skip
                skipped.append((name, "exists in Apple Music (not created by this tool)"))
                self.logger.info(f"  ⏭️  Skipping '{name}' (exists in Apple Music, not ours)")
            else:
                to_create.append(pl)
                self.logger.info(f"  ➕ Will create '{name}'")

        self.logger.info(
            f"📋 {len(to_create)} new, {len(to_update)} to update, "
            f"{len(skipped)} skipped (of {len(spotify_playlists)} followed)"
        )

        if not to_create and not to_update:
            self.logger.info("Nothing to sync.")
            return {}

        # 4. Ensure the target folder exists (AppleScript)
        if not self.dry_run:
            self.logger.info(f"📁 Ensuring folder '{self.folder_name}' exists...")
            if not self.apple_music.ensure_folder(self.folder_name):
                self.logger.error(f"Failed to create folder '{self.folder_name}'")
                return {}

        # 5. Process new playlists
        stats: Dict[str, Dict] = {}
        for i, pl in enumerate(to_create, 1):
            name = pl["name"]
            self.logger.info(f"➕ [{i}/{len(to_create)}] Creating '{name}' by {pl['owner']}")
            try:
                stats[name] = self._create_playlist(pl)
            except Exception as exc:
                self.logger.error(f"  ❌ Failed: {exc}")
                stats[name] = {"error": str(exc), "tracks_total": pl["tracks_total"]}

        # 6. Process updates
        for i, pl in enumerate(to_update, 1):
            name = pl["name"]
            self.logger.info(f"🔄 [{i}/{len(to_update)}] Updating '{name}'")
            try:
                stats[name] = self._update_playlist(pl)
            except Exception as exc:
                self.logger.error(f"  ❌ Failed: {exc}")
                stats[name] = {"error": str(exc), "tracks_total": pl["tracks_total"]}

        return stats

    def _search_all_tracks(self, tracks: List[Dict], playlist_name: str) -> Tuple[List[str], int, int, List[Dict]]:
        """Search all Spotify tracks in Apple Music (library + catalog, parallel).

        Returns:
            (found_persistent_ids, count_found, count_not_found, catalog_only_tracks)
        """
        deduped, found_count, not_found_count, catalog_only = self.track_finder.find_all_tracks(
            tracks, playlist_name, workers=Config.SEARCH_WORKERS
        )
        return deduped, found_count, not_found_count, catalog_only

    def _create_playlist(self, pl: Dict) -> Dict:
        """Create a new playlist in Apple Music from a Spotify playlist."""
        name = pl["name"]
        sp_id = pl["id"]
        description = pl.get("description", "")
        tracks, snapshot_id = self.spotify.get_playlist_tracks(sp_id)

        if not tracks:
            self.logger.warning(f"  Playlist '{name}' has no playable tracks, skipping")
            return {"tracks_added": 0, "tracks_total": 0, "skipped": "no tracks"}

        if self.dry_run:
            desc_preview = f"  desc: \"{description[:80]}\"" if description else ""
            self.logger.info(f"  [DRY RUN] Would create '{name}' with {len(tracks)} tracks{desc_preview}")
            return {"dry_run": True, "tracks_total": len(tracks), "action": "create", "description": description}

        # Search all tracks (library + catalog, parallel)
        deduped, found_count, not_found_count, catalog_only = self._search_all_tracks(tracks, name)

        # Create the playlist via AppleScript (with description if available)
        if not self.apple_music.create_playlist(name, description=description):
            return {
                "error": "Failed to create playlist",
                "tracks_found": found_count,
                "tracks_total": len(tracks),
            }

        # Add tracks via AppleScript (uses playlist name, not ID)
        added = self.apple_music.add_tracks_to_playlist(name, deduped)

        # Move to folder (AppleScript)
        # Wait briefly for the playlist to appear in Music.app
        time.sleep(2)
        if not self.apple_music.move_playlist_to_folder(name, self.folder_name):
            self.logger.warning(
                f"  ⚠️  Created '{name}' but couldn't move to folder '{self.folder_name}'"
            )

        # Record state (no apple_music_id with AppleScript approach — use empty string)
        self.state.record(sp_id, name, snapshot_id, len(tracks), apple_music_id="")

        self.logger.info(
            f"  ✅ Created '{name}': {added} tracks added, "
            f"{not_found_count} not found in catalog"
        )

        result: Dict = {
            "tracks_added": added,
            "tracks_not_found": not_found_count,
            "tracks_total": len(tracks),
            "action": "created",
        }
        if catalog_only:
            result["catalog_only_tracks"] = len(catalog_only)
            self.logger.info(f"  📋 {len(catalog_only)} tracks found in catalog but not in library")
        return result

    def _update_playlist(self, pl: Dict) -> Dict:
        """Diff-update an Apple Music playlist to match the current Spotify state.

        Removes tracks no longer on Spotify, adds tracks new on Spotify.
        Tracks present on both sides are left untouched.
        """
        name = pl["name"]
        sp_id = pl["id"]
        description = pl.get("description", "")
        tracks, snapshot_id = self.spotify.get_playlist_tracks(sp_id)

        if not tracks:
            self.logger.warning(f"  Playlist '{name}' has no playable tracks, skipping")
            return {"tracks_added": 0, "tracks_total": 0, "skipped": "no tracks"}

        if self.dry_run:
            desc_preview = f"  desc: \"{description[:80]}\"" if description else ""
            self.logger.info(f"  [DRY RUN] Would update '{name}' with {len(tracks)} tracks{desc_preview}")
            return {"dry_run": True, "tracks_total": len(tracks), "action": "update", "description": description}

        am_names = set(self.apple_music.get_all_playlist_names())
        if name not in am_names:
            self.logger.error(f"  Could not find Apple Music playlist '{name}'")
            return {"error": "Apple Music playlist not found", "tracks_total": len(tracks)}

        # Compute diff between current AM playlist and Spotify
        am_tracks = self.apple_music.get_playlist_tracks(name)

        def _norm(s: str) -> str:
            return s.lower().strip()

        am_set = {(_norm(t[0]), _norm(t[1])) for t in am_tracks}
        sp_set = {(_norm(t["title"]), _norm(t["artist"])) for t in tracks}

        # Remove: in AM but not in Spotify
        to_remove_keys = am_set - sp_set
        to_remove = [
            (t[0], t[1]) for t in am_tracks
            if (_norm(t[0]), _norm(t[1])) in to_remove_keys
        ]

        # Add: in Spotify but not in AM
        to_add_sp = [
            t for t in tracks
            if (_norm(t["title"]), _norm(t["artist"])) not in am_set
        ]

        removed = 0
        if to_remove:
            removed = self.apple_music.remove_tracks_from_playlist(name, to_remove)
            self.logger.info(f"  🗑️  Removed {removed}/{len(to_remove)} tracks from '{name}'")
        else:
            self.logger.info(f"  ✔️  No tracks to remove from '{name}'")

        added = 0
        not_found_count = 0
        catalog_only: List[Dict] = []
        if to_add_sp:
            deduped, found_count, not_found_count, catalog_only = self._search_all_tracks(to_add_sp, name)
            added = self.apple_music.add_tracks_to_playlist(name, deduped)
        else:
            self.logger.info(f"  ✔️  No new tracks to add to '{name}'")

        if description:
            if self.apple_music.set_playlist_description(name, description):
                self.logger.info(f"  📝 Updated description for '{name}'")
            else:
                self.logger.warning(f"  ⚠️  Could not set description for '{name}'")

        self.state.record(sp_id, name, snapshot_id, len(tracks), apple_music_id="")

        unchanged = len(am_set & sp_set)
        self.logger.info(
            f"  ✅ Updated '{name}': +{added} added, -{removed} removed, "
            f"{unchanged} unchanged, {not_found_count} not found"
        )

        result: Dict = {
            "tracks_added": added,
            "tracks_removed": removed,
            "tracks_unchanged": unchanged,
            "tracks_not_found": not_found_count,
            "tracks_total": len(tracks),
            "action": "updated",
        }
        if catalog_only:
            result["catalog_only_tracks"] = len(catalog_only)
            self.logger.info(f"  📋 {len(catalog_only)} tracks found in catalog but not in library")
        return result


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync Spotify followed playlists → Apple Music"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create/update playlists (default: dry-run preview)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-sync of all tracked playlists (ignore Spotify snapshot cache)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        metavar="FILE",
        default=None,
        help="Path to playlist filter file (one playlist name per line). "
        "Default: spfy2apple/playlist_filter.txt. If empty/missing, all followed playlists are synced.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel track search workers (default: 4). "
        "Each may spawn an osascript process or make HTTP requests.",
    )
    parser.add_argument(
        "--folder-name",
        type=str,
        default=Config.FOLDER_NAME,
        help=f"Apple Music folder name (default: '{Config.FOLDER_NAME}')",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List followed Spotify playlists without syncing",
    )
    parser.add_argument(
        "--show-state",
        action="store_true",
        help="Show sync state (which playlists are tracked) and exit",
    )
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear sync state (all tracked playlists will be re-evaluated next run)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)

    # Override worker count if specified
    if args.workers is not None:
        Config.SEARCH_WORKERS = args.workers

    # Load filter for display purposes
    playlist_filter = PlaylistFilter(args.filter)

    try:
        # ── State management commands ───────────────────────────
        if args.clear_state:
            state = SyncState()
            count = len(state.all_entries())
            state.state = {"playlists": {}}
            state.save()
            print(f"✅ Cleared sync state ({count} playlist(s) removed from tracking)")
            return 0

        if args.show_state:
            state = SyncState()
            entries = state.all_entries()
            if not entries:
                print("\nNo playlists tracked. Run with --apply to start syncing.")
                return 0
            print(f"\n{'='*70}")
            print(f"SYNC STATE ({len(entries)} playlist(s) tracked)")
            print(f"{'='*70}")
            for sp_id, entry in entries.items():
                name = entry.get("name", "?")
                snapshot = entry.get("spotify_snapshot_id", "?")[:12]
                count = entry.get("track_count", "?")
                last = entry.get("last_synced", "?")
                print(f"  {name}")
                print(f"    spotify_id: {sp_id}")
                print(f"    snapshot:   {snapshot}…")
                print(f"    tracks:     {count}")
                print(f"    last sync:  {last}")
            print(f"{'='*70}\n")
            return 0

        reader = SpotifyReader()

        if args.list_only:
            playlists = reader.get_followed_playlists()
            if not playlists:
                print("\nNo followed playlists found.")
                return 0

            # Cross-reference with sync state
            state = SyncState()

            # Apply filter for display
            if playlist_filter.is_active():
                print(f"\n📋 Filter: '{playlist_filter.path.name}' ({playlist_filter.matched_count()} playlist(s))")
                filtered = [pl for pl in playlists if playlist_filter.allows(pl["name"])]
                print(f"   {len(filtered)}/{len(playlists)} followed playlists match\n")
            else:
                filtered = playlists
                print(f"\n📋 No filter active — all followed playlists shown\n")

            print(f"{'='*70}")
            print(f"SPOTIFY FOLLOWED PLAYLISTS ({len(filtered)} shown, {len(playlists)} total)")
            print(f"{'='*70}")
            for pl in filtered:
                sp_id = pl["id"]
                name = pl["name"]
                owner = pl["owner"]
                total = pl["tracks_total"]
                in_filter = "✓" if playlist_filter.is_active() else " "
                if state.is_synced(sp_id):
                    snapshot = pl.get("snapshot_id", "")
                    if state.snapshot_unchanged(sp_id, snapshot):
                        status = "synced (up to date)"
                    else:
                        status = "synced (needs update)"
                else:
                    status = "not synced"
                print(f"  [{in_filter}] {name}")
                print(f"        by {owner}  ·  {total} tracks  ·  {status}")
            print(f"{'='*70}")
            if playlist_filter.is_active():
                # Show unmatched filter entries (possible typos)
                unmatched = playlist_filter.unmatched_entries([pl["name"] for pl in playlists])
                if unmatched:
                    print(f"\n⚠️  Filter entries not found among your followed playlists:")
                    for name in unmatched:
                        print(f"     • {name}")
                    print()
                print("✓ = in filter   |   Edit: spfy2apple/playlist_filter.txt")
            print()
            return 0

        dry_run = not args.apply
        sync = SpotifyToAppleSync(
            dry_run=dry_run,
            folder_name=args.folder_name,
            force=args.force,
            filter_path=args.filter,
        )
        stats = sync.sync()

        # Summary
        print(f"\n{'='*60}")
        title = "DRY RUN SUMMARY" if dry_run else "SYNC SUMMARY"
        print(title)
        print(f"{'='*60}")

        if not stats:
            print("No playlists processed.")
        else:
            for name, s in stats.items():
                if "error" in s:
                    print(f"❌ {name}: ERROR — {s['error']}")
                elif s.get("dry_run"):
                    action = s.get("action", "?")
                    print(f"🔵 {name}: would {action} with {s['tracks_total']} tracks")
                elif s.get("skipped"):
                    print(f"⏭️  {name}: {s['skipped']}")
                elif s.get("action") == "updated":
                    print(
                        f"✅ {name}: updated — "
                        f"+{s['tracks_added']} added, -{s.get('tracks_removed', 0)} removed, "
                        f"={s.get('tracks_unchanged', 0)} unchanged "
                        f"({s.get('tracks_not_found', 0)} not found, "
                        f"{s['tracks_total']} total on Spotify)"
                    )
                else:
                    print(
                        f"✅ {name}: created — "
                        f"+{s['tracks_added']} tracks "
                        f"({s.get('tracks_not_found', 0)} not found, "
                        f"{s['tracks_total']} total on Spotify)"
                    )
        print(f"{'='*60}")

        if dry_run and stats:
            print("\nThis was a preview. Run with --apply to make changes.\n")

    except ValueError as exc:
        logger.error(str(exc))
        return 1
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
