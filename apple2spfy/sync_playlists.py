#!/usr/bin/env python3

"""
Apple Music to Spotify Playlist Sync Tool

This script synchronizes playlists from Apple Music to Spotify by:
1. Extracting playlist data using AppleScript
2. Finding corresponding tracks on Spotify
3. Creating or updating Spotify playlists
4. Performing clean sync (removing tracks not in Apple Music)
"""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from apple2spfy.config import Config
from apple2spfy.logger import setup_logger
from apple2spfy.cache_manager import CacheManager

class PlaylistSyncError(Exception):
    """Custom exception for playlist sync errors."""
    pass

class RateLimitExceededError(PlaylistSyncError):
    """Exception raised when Spotify API rate limit is exceeded."""
    def __init__(self, retry_after: int, message: str = "Rate limit exceeded"):
        self.retry_after = retry_after
        super().__init__(message)

class SyncStateManager:
    """Manages the sync state to allow resuming after interruption."""
    
    def __init__(self, state_path: Optional[str] = None):
        self.state_path = Path(state_path or Config.sync_state_path())
        self.logger = setup_logger("sync_state")
        self.state = self._load_state()
        
    def _load_state(self) -> Dict:
        """Load sync state from disk."""
        if not self.state_path.exists():
            return {"completed_playlists": []}
            
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            self.logger.warning(f"Failed to load sync state: {e}")
            return {"completed_playlists": []}
            
    def save(self) -> None:
        """Save sync state to disk."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.state_path.open("w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Saved sync state to {self.state_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save sync state: {e}")
            
    def mark_completed(self, playlist_name: str) -> None:
        """Mark a playlist as successfully completed."""
        if playlist_name not in self.state["completed_playlists"]:
            self.state["completed_playlists"].append(playlist_name)
            self.save()
            
    def is_completed(self, playlist_name: str) -> bool:
        """Check if a playlist has already been completed in this run."""
        return playlist_name in self.state["completed_playlists"]
        
    def clear(self) -> None:
        """Clear the sync state file (call after successful full run)."""
        try:
            if self.state_path.exists():
                self.state_path.unlink()
            self.state = {"completed_playlists": []}
            self.logger.info("Cleared sync state")
        except Exception as e:
            self.logger.warning(f"Failed to clear sync state: {e}")
            
    def get_completed_count(self) -> int:
        """Get the number of completed playlists."""
        return len(self.state["completed_playlists"])

class TransferHistory:
    """Manages transfer history for playlist syncs."""
    
    def __init__(self, history_path: Optional[str] = None):
        self.history_path = Path(history_path or Config.transfer_history_path())
        self.logger = setup_logger("transfer_history")
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """Load transfer history from disk."""
        if not self.history_path.exists():
            return {"transfers": []}
        
        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or "transfers" not in data:
                self.logger.warning("Invalid history file format, starting fresh")
                return {"transfers": []}
            
            # Limit to max entries
            transfers = data.get("transfers", [])
            if len(transfers) > Config.TRANSFER_HISTORY_MAX_ENTRIES:
                transfers = transfers[-Config.TRANSFER_HISTORY_MAX_ENTRIES:]
            
            self.logger.debug(f"Loaded {len(transfers)} transfer history entries")
            return {"transfers": transfers}
        except Exception as e:
            self.logger.warning(f"Failed to load transfer history: {e}")
            return {"transfers": []}
    
    def record_transfer(self, playlist_name: str, spotify_playlist_id: str, 
                       tracks_added: int, tracks_removed: int, 
                       total_tracks: int, apple_track_count: int,
                       status: str = "success") -> None:
        """Record a successful playlist transfer."""
        if not Config.ENABLE_TRANSFER_HISTORY:
            return
        
        transfer_record = {
            "playlist_name": playlist_name,
            "spotify_playlist_id": spotify_playlist_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tracks_added": tracks_added,
            "tracks_removed": tracks_removed,
            "total_tracks": total_tracks,
            "apple_track_count": apple_track_count,
            "status": status
        }
        
        self.history["transfers"].append(transfer_record)
        
        # Limit to max entries
        if len(self.history["transfers"]) > Config.TRANSFER_HISTORY_MAX_ENTRIES:
            self.history["transfers"] = self.history["transfers"][-Config.TRANSFER_HISTORY_MAX_ENTRIES:]
        
        self.save()
        self.logger.debug(f"Recorded transfer for playlist: {playlist_name}")
    
    def save(self) -> None:
        """Persist transfer history to disk."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with self.history_path.open("w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Saved transfer history to {self.history_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save transfer history: {e}")
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict]:
        """Get transfer history, optionally limited to recent entries."""
        transfers = self.history.get("transfers", [])
        if limit:
            return transfers[-limit:]
        return transfers
    
    def get_playlist_history(self, playlist_name: str, limit: Optional[int] = None) -> List[Dict]:
        """Get transfer history for a specific playlist."""
        transfers = [t for t in self.history.get("transfers", []) 
                    if t.get("playlist_name") == playlist_name]
        if limit:
            return transfers[-limit:]
        return transfers
    
    def get_last_transfer(self, playlist_name: str) -> Optional[Dict]:
        """Get the most recent transfer for a playlist."""
        playlist_transfers = self.get_playlist_history(playlist_name)
        return playlist_transfers[-1] if playlist_transfers else None
    
    def clear(self) -> bool:
        """Clear all transfer history."""
        try:
            if self.history_path.exists():
                self.history_path.unlink()
            self.history = {"transfers": []}
            self.logger.info("Cleared transfer history")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to clear transfer history: {e}")
            return False


class AppleMusicExtractor:
    """Handles extraction of playlist data from Apple Music via AppleScript."""
    
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.logger = setup_logger("apple_music_extractor")
    
    def get_playlists(self, max_retries: int = 3) -> Dict[str, List[Dict[str, str]]]:
        """
        Execute AppleScript and return playlist data.
        
        Args:
            max_retries: Maximum number of retry attempts for AppleScript execution
            
        Returns:
            Dictionary mapping playlist names to lists of track dictionaries
            Format: {"Playlist Name": [{"title": "...", "artist": "...", "album": "..." (optional)}, ...]}
            The AppleScript can output tracks as "Title|Artist" or "Title|Artist|Album"
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Executing AppleScript: {self.script_path} (attempt {attempt + 1}/{max_retries})")
                
                # Add timeout to prevent hanging
                result = subprocess.run(
                    ["osascript", self.script_path],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    encoding='utf-8',
                    errors='replace'  # Handle encoding errors gracefully
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    self.logger.warning(f"AppleScript returned non-zero exit code: {result.returncode}")
                    self.logger.warning(f"Error output: {error_msg}")
                    
                    if attempt < max_retries - 1:
                        self.logger.info(f"Retrying in 5 seconds... (attempt {attempt + 2}/{max_retries})")
                        time.sleep(5)
                        continue
                    else:
                        raise PlaylistSyncError(f"AppleScript failed after {max_retries} attempts: {error_msg}")
                
                lines = result.stdout.splitlines()
                break
                
            except subprocess.TimeoutExpired:
                self.logger.warning(f"AppleScript timed out (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in 10 seconds... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(10)
                    continue
                else:
                    raise PlaylistSyncError(f"AppleScript timed out after {max_retries} attempts")
            except FileNotFoundError:
                self.logger.error(f"AppleScript file not found: {self.script_path}")
                raise PlaylistSyncError(f"AppleScript file not found: {self.script_path}")
            except Exception as e:
                self.logger.error(f"Unexpected error executing AppleScript: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in 5 seconds... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(5)
                    continue
                else:
                    raise PlaylistSyncError(f"Failed to execute AppleScript after {max_retries} attempts: {e}")

        playlists = {}
        current_playlist = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect new playlist
            if line.startswith("###") and line.endswith("###"):
                playlist_name = line.strip("# ").strip()
                current_playlist = playlist_name
                playlists[current_playlist] = []
                self.logger.debug(f"Found playlist: {playlist_name}")
            elif current_playlist and "|" in line:
                # Parse track: "Title|Artist" or "Title|Artist|Album"
                try:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        artist = parts[1].strip()
                        album = parts[2].strip() if len(parts) >= 3 else None
                        track = {
                            "title": title,
                            "artist": artist
                        }
                        if album:
                            track["album"] = album
                        playlists[current_playlist].append(track)
                    else:
                        self.logger.warning(f"Invalid track format: {line}")
                except ValueError:
                    self.logger.warning(f"Invalid track format: {line}")
            # Lines without "|" are ignored (e.g., "NOT FOUND")

        self.logger.info(f"Extracted {len(playlists)} playlists from Apple Music")
        return playlists

class SpotifyManager:
    """Handles Spotify API operations."""
    
    def __init__(self, minimal: bool = False, authenticate: bool = True):
        self.logger = setup_logger("spotify_manager")
        self.minimal = minimal
        # If minimal output requested, suppress console logging
        if self.minimal:
            try:
                self.logger.setLevel(logging.ERROR)
                for handler in list(self.logger.handlers):
                    handler.setLevel(logging.ERROR)
            except Exception:
                pass
        self.sp = None
        
        # Initialize CacheManager
        self.cache_manager = CacheManager()
        
        # Stats used for minimal summary
        self._stats = {
            "track_cache_hits": 0,
            "track_lookups": 0,
            "playlist_cache_skips": 0
        }
        # Transfer history tracking
        self.transfer_history = TransferHistory() if Config.ENABLE_TRANSFER_HISTORY else None
        
        # Sync state manager (for resume capability)
        self.sync_state_manager = SyncStateManager()
        
        if authenticate:
            self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Spotify API."""
        try:
            # Create cache directory if it doesn't exist
            cache_dir = os.path.expanduser("~/.spotify_cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Use a proper cache file path
            cache_file = os.path.join(cache_dir, ".spotify_token_cache")
            
            spotify_config = Config.get_spotify_config()
            spotify_config['cache_path'] = cache_file
            
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(**spotify_config))
            # Test authentication
            user = self.sp.me()
            self.logger.info(f"Authenticated as Spotify user: {user['display_name']}")
        except Exception as e:
            self.logger.error(f"Spotify authentication failed: {e}")
            raise PlaylistSyncError(f"Spotify authentication failed: {e}")
    
    def clean_playlist_name(self, name: str) -> str:
        """Remove prefixes from playlist name."""
        for prefix in Config.PLAYLIST_PREFIXES_TO_REMOVE:
            if name.startswith(prefix):
                cleaned = name[len(prefix):].strip()
                self.logger.debug(f"Cleaned playlist name: '{name}' -> '{cleaned}'")
                return cleaned
        return name
    
    def _make_api_call(self, api_call, max_retries: int = 5):
        """Make an API call with rate limiting and retry logic.
        
        Args:
            api_call: Callable that makes the API call
            max_retries: Maximum number of retry attempts
            
        Returns:
            The result of the API call
            
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Add delay between API calls to respect rate limits
                # Use configured delay (default 0.5s), increasing with retries
                base_delay = Config.TRACK_LOOKUP_DELAY
                delay = base_delay * (2 ** attempt)
                time.sleep(min(delay, 10.0))  # Cap at 10 seconds
                
                return api_call()
                
            except spotipy.exceptions.SpotifyException as e:
                last_exception = e
                
                if e.http_status == 429:  # Rate limited
                    retry_after = int(e.headers.get('Retry-After', 60)) if e.headers else 60
                    if retry_after <= Config.RATE_LIMIT_MAX_WAIT:
                        # Short wait — sleep and retry transparently
                        self.logger.warning(f"⚠️ Rate limited. Waiting {retry_after}s then retrying (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(retry_after)
                        continue
                    else:
                        # Long wait — save progress and exit so the user can resume later
                        self.logger.error(
                            f"🛑 Rate limit requires waiting {retry_after}s (> max {Config.RATE_LIMIT_MAX_WAIT}s). "
                            f"Saving progress — run again to resume."
                        )
                        raise RateLimitExceededError(retry_after, f"Spotify API rate limit exceeded. Retry after {retry_after}s.")

                elif 500 <= e.http_status < 600:  # Server error
                    retry_after = min(5 * (attempt + 1), 30)  # Cap at 30 seconds for server errors
                    self.logger.warning(f"Server error {e.http_status}. Waiting {retry_after} seconds before retry...")
                    time.sleep(retry_after)
                    continue
                    
                # For other errors, log and re-raise
                self.logger.error(f"Spotify API error: {e}")
                raise
                
            except Exception as e:
                last_exception = e
                retry_after = min(2 * (attempt + 1), 10)  # Cap at 10 seconds for other errors
                self.logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}). Waiting {retry_after} seconds: {e}")
                time.sleep(retry_after)
                continue
        
        # If we get here, all retries failed
        self.logger.error(f"All {max_retries} attempts failed. Last error: {last_exception}")
        raise last_exception or Exception("Unknown error in _make_api_call")
        
        raise Exception(f"API call failed after {max_retries} attempts")

    def save_cache(self):
        """Deprecated: Cache is now saved automatically to SQLite."""
        pass

    def save_playlist_cache(self):
        """Deprecated: Cache is now saved automatically to SQLite."""
        pass

    def clear_track_cache(self):
        """Clear the persistent track cache."""
        return self.cache_manager.clear_tracks()

    def clear_playlist_cache(self):
        """Clear the persistent playlist metadata cache."""
        return self.cache_manager.clear_playlists()

    def clear_all_cache(self):
        """Clear both track and playlist caches."""
        return self.cache_manager.clear_all()

    def _batch_add_tracks(self, playlist_id: str, track_ids: List[str], dry_run: bool = False) -> int:
        """Add tracks to playlist in batches to avoid API limits.
        
        Args:
            playlist_id: ID of the playlist to add tracks to
            track_ids: List of track IDs to add
            
        Returns:
            Number of tracks successfully added
        """
        if not track_ids:
            return 0

        # Sanitize: keep only valid Spotify track IDs and convert to URI form.
        # Spotify rejects whole batches with HTTP 400 "Unsupported URL / URI"
        # if any single entry is None/empty/local/invalid.
        def _to_uri(tid):
            if not tid or not isinstance(tid, str):
                return None
            s = tid.strip()
            if not s:
                return None
            if s.startswith("spotify:track:"):
                return s
            if s.startswith("spotify:local:"):
                return None  # local files can't be added via Web API
            # Bare base62 ID (typically 22 chars)
            if len(s) == 22 and s.isalnum():
                return f"spotify:track:{s}"
            return None

        uris = [u for u in (_to_uri(t) for t in track_ids) if u]
        skipped = len(track_ids) - len(uris)
        if skipped:
            self.logger.warning(f"⚠️  Skipping {skipped} invalid/local track IDs before add")
        if not uris:
            return 0

        batch_size = 50  # Spotify allows up to 100, but we'll be conservative
        total_added = 0

        if dry_run:
            # Simulate all tracks being added
            return len(uris)

        for i in range(0, len(uris), batch_size):
            batch = uris[i:i + batch_size]
            retries = 3
            
            for attempt in range(retries):
                try:
                    self._make_api_call(
                        lambda: self.sp.playlist_add_items(playlist_id, batch)
                    )
                    total_added += len(batch)
                    self.logger.debug(f"Added {len(batch)} tracks to playlist (batch {i//batch_size + 1})")
                    
                    # Add delay between batches to respect rate limits
                    if i + batch_size < len(uris):
                        time.sleep(1.0)  # Increased delay between batches
                        
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if attempt == retries - 1:  # Last attempt
                        self.logger.error(f"Failed to add batch {i//batch_size + 1} after {retries} attempts: {e}")
                    else:
                        wait_time = 2 ** (attempt + 1)  # Exponential backoff
                        self.logger.warning(f"Error adding batch {i//batch_size + 1}, attempt {attempt + 1}/{retries}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                
        return total_added
    
    def _batch_remove_tracks(self, playlist_id: str, track_ids: List[str], dry_run: bool = False) -> int:
        """Remove tracks from playlist, optionally as a dry-run."""
        return self._batch_remove_tracks_internal(playlist_id, track_ids, dry_run=dry_run)

    def _batch_remove_tracks_internal(self, playlist_id: str, track_ids: List[str], dry_run: bool = False) -> int:
        """Remove tracks from playlist in batches to avoid API limits."""
        batch_size = 100  # Spotify API limit
        total_removed = 0
        
        if dry_run:
            return len(track_ids)
        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i:i + batch_size]
            try:
                self._make_api_call(lambda: self.sp.playlist_remove_all_occurrences_of_items(playlist_id, batch))
                total_removed += len(batch)
                self.logger.debug(f"Removed batch of {len(batch)} tracks from playlist")
            except Exception as e:
                self.logger.error(f"Failed to remove batch of tracks: {e}")
                # Continue with next batch instead of failing completely
        
        return total_removed
    
    def find_track(self, title: str, artist: str, album: Optional[str] = None) -> Optional[str]:
        """Find a track on Spotify by title and artist using flexible search strategies."""
        try:
            # Check SQLite cache first (also catches negative "NOT_FOUND" entries)
            cache_key = self._track_cache_key(title, artist, album)
            signature = "|".join([str(x) for x in cache_key])
            cached_track_id = self.cache_manager.get_track(signature)

            if cached_track_id is not None:
                self._stats["track_cache_hits"] += 1
                # "NOT_FOUND" sentinel means we already tried every strategy and failed
                return None if cached_track_id == "NOT_FOUND" else cached_track_id

            # Helper: always persist result (including failures) so we never re-search the same track
            def _cache_and_return(track_id: Optional[str]) -> Optional[str]:
                self.cache_manager.save_track(
                    signature, track_id if track_id is not None else "NOT_FOUND",
                    title, artist, album
                )
                return track_id

            self._stats["track_lookups"] += 1

            # Pre-compute all text variants once (avoids redundant work across strategies)
            normalized_title = self._normalize_unicode(title)
            normalized_artist = self._normalize_unicode(artist)
            normalized_album = self._normalize_unicode(album) if album else None
            cleaned_title = self._clean_title(title)
            cleaned_normalized_title = (
                self._normalize_unicode(cleaned_title)
                if cleaned_title != title else None
            )

            # ── CHEAP: exact Spotify search (1 API call each) ─────────────────

            # Strategy 1: Exact search with original text
            track_id = self._search_exact(title, artist)
            if track_id:
                return _cache_and_return(track_id)

            # Strategy 2: Exact search with normalized text
            if normalized_title != title or normalized_artist != artist:
                track_id = self._search_exact(normalized_title, normalized_artist)
                if track_id:
                    self.logger.debug(f"Found track with normalized text: {normalized_title} - {normalized_artist}")
                    return _cache_and_return(track_id)

            # Strategy 3: Exact search with cleaned title
            if cleaned_title != title:
                track_id = self._search_exact(cleaned_title, artist)
                if track_id:
                    self.logger.debug(f"Found track with cleaned title: {cleaned_title} - {artist}")
                    return _cache_and_return(track_id)

                # Strategy 4: Exact search with normalized+cleaned title
                if cleaned_normalized_title and cleaned_normalized_title != cleaned_title:
                    track_id = self._search_exact(cleaned_normalized_title, normalized_artist)
                    if track_id:
                        self.logger.debug(f"Found track with normalized cleaned title: {cleaned_normalized_title} - {normalized_artist}")
                        return _cache_and_return(track_id)

            # ── MEDIUM: album-scoped search (1 API call each) ─────────────────

            if album:
                track_id = self._search_in_specific_album(title, artist, album)
                if track_id:
                    self.logger.debug(f"Found track in specific album '{album}': {title} - {artist}")
                    return _cache_and_return(track_id)

                if normalized_album and normalized_album != album:
                    track_id = self._search_in_specific_album(title, artist, normalized_album)
                    if track_id:
                        self.logger.debug(f"Found track in normalized album '{normalized_album}': {title} - {artist}")
                        return _cache_and_return(track_id)

            # ── PARTIAL: fuzzy word search (up to 4 API calls each) ───────────

            # Strategy 6: Partial title search
            track_id = self._search_partial(title, artist)
            if track_id:
                return _cache_and_return(track_id)

            # Strategy 7: Partial title search with normalized text
            if normalized_title != title or normalized_artist != artist:
                track_id = self._search_partial(normalized_title, normalized_artist)
                if track_id:
                    self.logger.debug(f"Found track with partial normalized search: {normalized_title} - {normalized_artist}")
                    return _cache_and_return(track_id)

            # Strategy 8: Partial title search with cleaned title
            if cleaned_title != title:
                track_id = self._search_partial(cleaned_title, artist)
                if track_id:
                    self.logger.debug(f"Found track with partial cleaned title: {cleaned_title} - {artist}")
                    return _cache_and_return(track_id)

            # ── EXPENSIVE: browse large result sets ───────────────────────────

            # Strategy 9: Artist-only search
            track_id = self._search_artist_only(title, artist)
            if track_id:
                self.logger.debug(f"Found track with artist-only search: {title} - {artist}")
                return _cache_and_return(track_id)

            # Strategy 10: Browse all artist albums (last resort — up to 20+ API calls)
            track_id = self._search_in_artist_albums(title, artist, exclude_album=album)
            if track_id:
                self.logger.debug(f"Found track in artist albums: {title} - {artist}")
                return _cache_and_return(track_id)

            self.logger.warning(f"Track not found: {title} - {artist}" + (f" (album: {album})" if album else ""))
            return _cache_and_return(None)

        except Exception as e:
            self.logger.error(f"Error searching for track '{title} - {artist}': {e}")
            return None
    
    def batch_find_tracks(self, all_playlists: Dict[str, List[Dict[str, str]]]) -> Dict[Tuple[str, str, Optional[str]], Optional[str]]:
        """Batch lookup tracks. (Optimized in finding loop now, but kept for pre-warm)."""
        if not Config.ENABLE_BATCH_LOOKUP:
            return {}
        
        # Collect all unique tracks across all playlists
        unique_tracks = {}
        for playlist_name, tracks in all_playlists.items():
            for track in tracks:
                title = track.get("title", "")
                artist = track.get("artist", "")
                album = track.get("album")
                cache_key = self._track_cache_key(title, artist, album)
                signature = "|".join([str(x) for x in cache_key])
                
                # Check if already in DB
                if not self.cache_manager.get_track(signature):
                     unique_tracks[signature] = (title, artist, album)
        
        total_unique = len(unique_tracks)
        if total_unique == 0:
            self.logger.info("All tracks already in cache, no batch lookup needed")
            return {}
        
        self.logger.info(f"🔍 Batch lookup: {total_unique} unique tracks to search across all playlists")
        
        results = {}
        for i, (signature, (title, artist, album)) in enumerate(unique_tracks.items(), 1):
             if i % 25 == 0:
                self.logger.info(f"  Batch progress: {i}/{total_unique} tracks")
             track_id = self.find_track(title, artist, album)
             results[signature] = track_id
             # find_track already saves to DB
             time.sleep(Config.TRACK_LOOKUP_DELAY)
             
        return results


    def _track_cache_key(self, title: str, artist: str, album: Optional[str]) -> Tuple[str, str, Optional[str]]:
        """Build a normalized cache key for track lookups."""
        normalized_title = title.strip().lower()
        normalized_artist = artist.strip().lower()
        normalized_album = album.strip().lower() if album else None
        return (normalized_title, normalized_artist, normalized_album)
    
    def _clean_title(self, title: str) -> str:
        """Remove common suffixes that might differ between Apple Music and Spotify."""
        # Lowercase suffixes only — compared against title.lower() for true case-insensitivity
        suffixes_to_remove = [
            " (hq)", " (hq version)",
            " (remix)", " (remix version)",
            " (extended)", " (extended version)",
            " (radio edit)", " (clean)", " (explicit)",
            " (live)", " (live version)",
            " (acoustic)", " (acoustic version)",
            " (instrumental)", " (original mix)", " (club mix)",
            " (album version)", " (single version)", " (radio version)",
            " (music video)", " (official video)", " (official)",
            " (feat.", " (ft.", " (featuring",
        ]

        title_lower = title.lower()
        for suffix in suffixes_to_remove:
            if title_lower.endswith(suffix):
                return title[:len(title) - len(suffix)].strip()

        return title
    
    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters for better matching."""
        import unicodedata
        
        # Normalize Unicode characters (NFD -> NFC)
        normalized = unicodedata.normalize('NFC', text)
        
        # Replace common Unicode variants with ASCII equivalents
        replacements = {
            '：': ':',  # Full-width colon
            '，': ',',  # Full-width comma
            '（': '(',  # Full-width parentheses
            '）': ')',  # Full-width parentheses
            '「': '"',  # Full-width quotes
            '」': '"',  # Full-width quotes
            '『': '"',  # Full-width quotes
            '』': '"',  # Full-width quotes
            '・': ' ',  # Middle dot
            '〜': '~',  # Full-width tilde
            '！': '!',  # Full-width exclamation
            '？': '?',  # Full-width question mark
        }
        
        for unicode_char, ascii_char in replacements.items():
            normalized = normalized.replace(unicode_char, ascii_char)
        
        return normalized.strip()
    
    def _search_artist_only(self, title: str, artist: str) -> Optional[str]:
        """Search for track using only artist name (fallback strategy)."""
        try:
            # Search by artist only and try to find a matching title
            query = f"artist:\"{artist}\""
            results = self._make_api_call(lambda: self.sp.search(q=query, type="track", limit=20))
            items = results.get("tracks", {}).get("items", [])
            
            if not items:
                return None
            
            # Try to find the best match by comparing titles
            title_lower = title.lower()
            for item in items:
                found_title = item["name"].lower()
                # Check if the original title is contained in the found title
                if title_lower in found_title or found_title in title_lower:
                    track_id = item["id"]
                    self.logger.debug(f"Found track with artist-only search: {item['name']} - {item['artists'][0]['name']}")
                    return track_id
            
            # If no exact match, try with cleaned title
            cleaned_title = self._clean_title(title)
            if cleaned_title != title:
                cleaned_title_lower = cleaned_title.lower()
                for item in items:
                    found_title = item["name"].lower()
                    if cleaned_title_lower in found_title or found_title in cleaned_title_lower:
                        track_id = item["id"]
                        self.logger.debug(f"Found track with artist-only search (cleaned): {item['name']} - {item['artists'][0]['name']}")
                        return track_id
            
            return None
        except Exception as e:
            self.logger.debug(f"Artist-only search failed for '{title} - {artist}': {e}")
            return None
    
    def _search_in_specific_album(self, title: str, artist: str, album_name: str) -> Optional[str]:
        """Search for a track in a specific album using a single combined query (1 API call)."""
        try:
            query = f"track:\"{title}\" artist:\"{artist}\" album:\"{album_name}\""
            results = self._make_api_call(lambda: self.sp.search(q=query, type="track", limit=5))
            items = results.get("tracks", {}).get("items", [])

            if not items:
                return None

            title_lower = title.lower()
            cleaned_title_lower = self._clean_title(title).lower()
            album_name_lower = album_name.lower()

            for item in items:
                item_album = item.get("album", {}).get("name", "").lower()
                if album_name_lower not in item_album and item_album not in album_name_lower:
                    continue
                found_title = item["name"].lower()
                if (title_lower in found_title or found_title in title_lower or
                        cleaned_title_lower in found_title or found_title in cleaned_title_lower):
                    self.logger.debug(f"Found track in album '{album_name}': {item['name']} - {artist}")
                    return item["id"]

            # Spotify's combined query already filtered by album+artist+track — trust first result
            return items[0]["id"]
        except Exception as e:
            self.logger.debug(f"Specific album search failed for '{title} - {artist}' (album: {album_name}): {e}")
            return None
    
    def _search_in_artist_albums(self, title: str, artist: str, exclude_album: Optional[str] = None) -> Optional[str]:
        """Search for track by looking through artist's albums, optionally excluding a specific album."""
        try:
            # First, find the artist
            query = f"artist:\"{artist}\""
            artist_results = self._make_api_call(lambda: self.sp.search(q=query, type="artist", limit=1))
            artists = artist_results.get("artists", {}).get("items", [])
            
            if not artists:
                return None
            
            artist_id = artists[0]["id"]
            self.logger.debug(f"Found artist ID: {artist_id} for '{artist}'")
            
            # Get artist's albums (limit to first 20 albums to avoid too many API calls)
            albums = self._make_api_call(lambda: self.sp.artist_albums(artist_id, album_type="album,single", limit=20))
            album_items = albums.get("items", [])
            
            if not album_items:
                return None
            
            title_lower = title.lower()
            cleaned_title = self._clean_title(title)
            cleaned_title_lower = cleaned_title.lower() if cleaned_title != title else None
            exclude_album_lower = exclude_album.lower() if exclude_album else None
            
            # Search through each album
            for album in album_items:
                # Skip the excluded album if specified
                if exclude_album_lower:
                    album_name_lower = album["name"].lower()
                    if exclude_album_lower in album_name_lower or album_name_lower in exclude_album_lower:
                        continue
                
                album_id = album["id"]
                try:
                    # Get tracks from album
                    album_tracks = self._make_api_call(lambda: self.sp.album_tracks(album_id, limit=50))
                    tracks = album_tracks.get("items", [])
                    
                    # Search for matching track in this album
                    for track in tracks:
                        if not track:
                            continue
                        track_name = track["name"].lower()
                        
                        # Check if title matches (exact or partial)
                        if (title_lower == track_name or 
                            title_lower in track_name or 
                            track_name in title_lower):
                            track_id = track["id"]
                            self.logger.debug(f"Found track in album '{album['name']}': {track['name']} - {artist}")
                            return track_id
                        
                        # Also try with cleaned title
                        if cleaned_title_lower and (cleaned_title_lower == track_name or 
                                                    cleaned_title_lower in track_name or 
                                                    track_name in cleaned_title_lower):
                            track_id = track["id"]
                            self.logger.debug(f"Found track in album '{album['name']}' (cleaned): {track['name']} - {artist}")
                            return track_id
                            
                except Exception as e:
                    self.logger.debug(f"Error getting tracks from album '{album.get('name', 'unknown')}': {e}")
                    continue
            
            return None
        except Exception as e:
            self.logger.debug(f"Search in artist albums failed for '{title} - {artist}': {e}")
            return None
    
    def _search_exact(self, title: str, artist: str) -> Optional[str]:
        """Search for track using exact title and artist match."""
        try:
            query = f"track:\"{title}\" artist:\"{artist}\""
            results = self._make_api_call(lambda: self.sp.search(q=query, type="track", limit=1))
            items = results.get("tracks", {}).get("items", [])
            
            if items:
                track_id = items[0]["id"]
                self.logger.debug(f"Found track (exact): {title} - {artist} -> {track_id}")
                return track_id
            return None
        except Exception as e:
            self.logger.debug(f"Exact search failed for '{title} - {artist}': {e}")
            return None
    
    def _search_partial(self, title: str, artist: str) -> Optional[str]:
        """Search for track using partial title matching."""
        try:
            # Split title into words and try different combinations
            title_words = title.split()
            
            # Try with first 3-4 words of title
            for num_words in range(min(4, len(title_words)), 0, -1):
                partial_title = " ".join(title_words[:num_words])
                query = f"track:\"{partial_title}\" artist:\"{artist}\""
                results = self._make_api_call(lambda: self.sp.search(q=query, type="track", limit=5))
                items = results.get("tracks", {}).get("items", [])
                
                if items:
                    # Find best match by checking if the partial title is contained in the found track
                    for item in items:
                        found_title = item["name"].lower()
                        if partial_title.lower() in found_title:
                            track_id = item["id"]
                            self.logger.debug(f"Found track (partial): {partial_title} - {artist} -> {track_id}")
                            return track_id
            
            # Try with just the first word if title has multiple words
            if len(title_words) > 1:
                first_word = title_words[0]
                query = f"track:\"{first_word}\" artist:\"{artist}\""
                results = self._make_api_call(lambda: self.sp.search(q=query, type="track", limit=5))
                items = results.get("tracks", {}).get("items", [])
                
                if items:
                    # Find best match
                    for item in items:
                        found_title = item["name"].lower()
                        if first_word.lower() in found_title:
                            track_id = item["id"]
                            self.logger.debug(f"Found track (first word): {first_word} - {artist} -> {track_id}")
                            return track_id
            
            return None
        except Exception as e:
            self.logger.debug(f"Partial search failed for '{title} - {artist}': {e}")
            return None
    
    def get_playlist_tracks(self, playlist_id: str, force_refresh: bool = False) -> List[str]:
        """Get all track IDs from a Spotify playlist, using cached track IDs if snapshot hasn't changed."""
        try:
            metadata = self.get_playlist_metadata(playlist_id)
            snapshot_id = metadata.get("snapshot_id")
            total = metadata.get("total", 0)

            cached = self.cache_manager.get_playlist_metadata(playlist_id)
            # Use cached track IDs when snapshot matches and not forced
            if not force_refresh and cached and cached.get("snapshot_id") == snapshot_id:
                  # Note: access track_ids if stored? CacheManager doesn't seem to store track_ids in playlist_metadata table?
                  # Wait, I initialized playlists table with only metadata.
                  # Ah, the legacy json stored track_ids too.
                  # I should probably just fetch from API if I don't store full track lists in DB.
                  # The prompt says: "Migrate Caching to SQLite".
                  # Storing full track lists for 500 playlists in one JSON was bad.
                  # In SQLite, we could store (playlist_id, track_id) relation.
                  # But `apple_playlist_state` already stores what *should* be there.
                  # `get_playlist_tracks` fetches what *is* there.
                  # If we don't cache "what is there", we hit API always.
                  # But `get_playlist_tracks` is only called if we detect a change/diff or clean_sync is on.
                  # The optimization is to SKIP this call if nothing changed.
                  # So we don't strictly need to cache the *list* of tracks if we skip correctly.
                  # HOWEVER, `sync_playlist` calls it to calculate difference.
                  # If we can't skip, we pay the cost.
                  # The user request "Incremental Diffing" relies on `apple_playlist_state` (what we synced).
                  # If `apple_playlist_state` says "we synced X", and Spotify snapshot hasn't changed, we assume Spotify has X.
                  # So we don't need to call `get_playlist_tracks` to know what's there?
                  # Yes! That's the optimization of `sync_playlist` logic I wrote:
                  # "If AM hasn't changed AND Spotify hasn't changed ... return 0, 0".
                  # So we only call `get_playlist_tracks` if something MUST happen.
                  # In that case, we probably WANT fresh data from API to be safe.
                  # So removing caching of *Spotify Content* is acceptable IF we cache *Spotify Metadata* (snapshot) effectively.
                  pass
            
            # Since CacheManager doesn't store the full list of tracks for a Spotify playlist (only Metadata),
            # we will always fetch from API here *unless* callerLogic skips calling this.
            # My `sync_playlist` logic already handles the skipping.
            # So `get_playlist_tracks` can just be a direct API caller.

            track_ids = []
            limit = 100
            offset = 0
            while True:
                results = self._make_api_call(lambda: self.sp.playlist_items(
                    playlist_id,
                    fields="items.track.id,total",
                    limit=limit,
                    offset=offset,
                    additional_types=["track"]
                ))
                items = results.get("items", [])
                for item in items:
                    if item["track"] and item["track"]["id"]:
                        track_ids.append(item["track"]["id"])
                if len(items) < limit:
                    break
                offset += limit

            # Update cache (name is preserved from get_playlist_metadata call above)
            self.cache_manager.save_playlist_metadata(playlist_id, snapshot_id, total)
            self.logger.debug(f"Retrieved {len(track_ids)} tracks from playlist {playlist_id}")
            return track_ids
        except Exception as e:
            self.logger.error(f"Error getting playlist tracks: {e}")
            return []
    
    def get_playlist_track_count(self, playlist_id: str) -> int:
        """Get total number of tracks in a Spotify playlist without fetching all items."""
        try:
            metadata = self.get_playlist_metadata(playlist_id)
            return metadata.get("total", 0)
        except Exception as e:
            self.logger.error(f"Error getting playlist track count: {e}")
            raise

    def get_playlist_metadata(self, playlist_id: str) -> Dict[str, Optional[str]]:
        """Get playlist metadata (snapshot_id and total tracks) from Spotify and update cache."""
        try:
            result = self._make_api_call(lambda: self.sp.playlist(playlist_id, fields="snapshot_id,tracks.total,name"))
            snapshot_id = result.get("snapshot_id")
            total = result.get("tracks", {}).get("total", 0)
            name = result.get("name")
            
            # Update playlist cache
            self.cache_manager.save_playlist_metadata(playlist_id, snapshot_id, total, name)
            return {"snapshot_id": snapshot_id, "total": total}
        except Exception as e:
            self.logger.error(f"Error getting playlist metadata: {e}")
            raise
    
    def update_playlist_details(
        self,
        playlist_id: str,
        new_name: Optional[str] = None,
        description: str = ""
    ) -> bool:
        """
        Update Spotify playlist details and keep the sync-created description empty.
        
        Args:
            playlist_id: Spotify playlist ID
            new_name: New name for the playlist, if it needs to change
            description: Playlist description to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            details = {"description": description}
            if new_name is not None:
                details["name"] = new_name
            self._make_api_call(
                lambda: self.sp.playlist_change_details(playlist_id, **details)
            )
            if new_name is not None:
                self.logger.debug(f"Updated playlist name to '{new_name}' for ID: {playlist_id}")
            self.logger.debug(f"Updated playlist description for ID: {playlist_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error updating playlist details: {e}")
            return False

    def update_playlist_name(self, playlist_id: str, new_name: str) -> bool:
        """
        Update the name of a Spotify playlist while clearing sync attribution text.

        Args:
            playlist_id: Spotify playlist ID
            new_name: New name for the playlist

        Returns:
            True if successful, False otherwise
        """
        return self.update_playlist_details(playlist_id, new_name=new_name)
    
    def find_or_create_playlist(self, name: str, dry_run: bool = False) -> str:
        """
        Find existing playlist or create new one with the given name.
        Uses playlist mapping to track playlists even when names change.
        
        Args:
            name: Name of the playlist to find or create (Apple Music playlist name)
            dry_run: If True, don't create playlists or update names
            
        Returns:
            Playlist ID
        """
        try:
            # Clean the playlist name
            clean_name = self.clean_playlist_name(name)
            
            # Step 1: Check if we have a mapping for this Apple Music playlist name
            mapped_spotify_id = self.cache_manager.get_playlist_mapping(name)
            
            if mapped_spotify_id:
                # We have a mapping! Verify the playlist still exists and check for name changes
                try:
                    playlist_info = self._make_api_call(
                        lambda: self.sp.playlist(mapped_spotify_id, fields="id,name,description,snapshot_id")
                    )
                    current_spotify_name = playlist_info.get("name", "")
                    current_description = playlist_info.get("description", "") or ""
                    name_changed = current_spotify_name != clean_name
                    description_changed = current_description != ""
                    
                    # Check if the Spotify playlist details need to be updated
                    if name_changed or description_changed:
                        if name_changed:
                            self.logger.info(f"📝 Playlist name changed: '{current_spotify_name}' → '{clean_name}'")
                        elif description_changed:
                            self.logger.info(f"📝 Clearing Spotify playlist description for '{clean_name}'")
                        if not dry_run:
                            # Update Spotify details to match Apple Music and keep description empty
                            self.update_playlist_details(
                                mapped_spotify_id,
                                new_name=clean_name if name_changed else None,
                            )
                            if name_changed:
                                self.logger.info(f"✅ Updated Spotify playlist name to '{clean_name}'")
                        else:
                            self.logger.info(f"[DRY RUN] Would update Spotify playlist details for '{clean_name}'")
                    
                    # Update mapping with current info
                    if not dry_run:
                        self.cache_manager.save_playlist_mapping(name, mapped_spotify_id, clean_name)
                    
                    # Update playlist cache
                    try:
                        metadata = self.get_playlist_metadata(mapped_spotify_id)
                    except Exception:
                        pass
                    
                    self.logger.debug(f"Found playlist via mapping: {clean_name} (ID: {mapped_spotify_id})")
                    return mapped_spotify_id
                    
                except Exception as e:
                    # Playlist no longer exists or API error - remove mapping and continue to search/create
                    self.logger.warning(f"Mapped playlist {mapped_spotify_id} not found or error: {e}. Removing mapping.")
                    if not dry_run:
                        self.cache_manager.delete_playlist_mapping(name)
            
            # Step 2: No mapping or mapping was invalid - search for playlist by name
            # Get current user ID first
            user_id = self._make_api_call(
                lambda: self.sp.me()["id"]
            )
            
            # Try to find existing playlist with pagination
            offset = 0
            limit = 50
            
            while True:
                playlists = self._make_api_call(
                    lambda: self.sp.current_user_playlists(limit=limit, offset=offset)
                )
                
                # Check if playlist exists in current page
                for playlist in playlists["items"]:
                    if playlist["name"] == clean_name:
                        self.logger.debug(f"Found existing playlist by name: {clean_name}")
                        playlist_id = playlist["id"]
                        
                        # Create mapping for this playlist
                        if not dry_run:
                            self.cache_manager.save_playlist_mapping(name, playlist_id, clean_name)
                            self.logger.info(f"Created mapping for existing playlist: {name} → {playlist_id}")
                            self.update_playlist_details(playlist_id)
                        
                        try:
                            # Update playlist cache by fetching lightweight metadata
                            metadata = self.get_playlist_metadata(playlist_id)
                        except Exception:
                            # Ignore cache update failures; still return playlist id
                            pass
                        return playlist_id
                
                # If we've fetched all playlists, break the loop
                if not playlists["items"] or len(playlists["items"]) < limit:
                    break
                    
                offset += limit
            
            # Step 3: Playlist doesn't exist - create it (unless dry_run)
            if dry_run:
                # In dry run, return a synthetic playlist id and do not create
                playlist_id = f"dryrun:{clean_name}"
                return playlist_id
                
            playlist = self._make_api_call(
                lambda: self.sp.user_playlist_create(
                    user=user_id,
                    name=clean_name,
                    public=False,
                    description=""
                )
            )
            
            playlist_id = playlist["id"]
            
            # Create mapping for new playlist
            self.cache_manager.save_playlist_mapping(name, playlist_id, clean_name)
            self.logger.info(f"Created new playlist and mapping: {clean_name} (ID: {playlist_id})")
            
            # Update playlist cache with basic metadata
            self.get_playlist_metadata(playlist_id)
            
            return playlist_id
            
        except Exception as e:
            self.logger.error(f"Error in find_or_create_playlist for '{name}': {e}")
            raise PlaylistSyncError(f"Failed to find/create playlist '{name}': {e}")

    
    def sync_playlist(self, playlist_name: str, tracks: List[Dict[str, str]], clean_sync: bool = True, force_sync: bool = False, dry_run: bool = False) -> Tuple[int, int]:
        """
        Sync a single playlist to Spotify using CacheManager and incremental updates.
        """
        try:
            spotify_name = self.clean_playlist_name(playlist_name)
            if self.minimal:
                print(f"→ {spotify_name} ({len(tracks)} tracks)")
            else:
                self.logger.info(f"🔄 Syncing playlist: {spotify_name} ({len(tracks)} tracks)")
            
            # 1. Get or Create Spotify Playlist
            playlist_id = None
            for attempt in range(3):
                try:
                    playlist_id = self.find_or_create_playlist(spotify_name, dry_run=dry_run)
                    break
                except Exception as e:
                    if attempt == 2: raise
                    time.sleep(2)
            
            if not playlist_id:
                raise PlaylistSyncError(f"Failed to find or create playlist: {spotify_name}")

            # 2. Check State for Optimizations
            # Get current Spotify metadata
            try:
                sp_meta = self.get_playlist_metadata(playlist_id)
                sp_snapshot = sp_meta.get("snapshot_id")
                sp_total = sp_meta.get("total", 0)
            except Exception:
                # If metadata fails, force sync
                sp_snapshot = None
                sp_total = 0

            # Staleness check: skip if recently synced AND track count is unchanged
            # This avoids all further API calls for untouched playlists.
            if not force_sync and Config.STALE_SYNC_DAYS > 0 and self.transfer_history:
                last = self.transfer_history.get_last_transfer(spotify_name)
                if last and last.get("status") == "success":
                    try:
                        last_ts = datetime.fromisoformat(last["timestamp"])
                        age_days = (datetime.now(timezone.utc) - last_ts).days
                        if age_days < Config.STALE_SYNC_DAYS and len(tracks) == sp_total:
                            if self.minimal:
                                print(f"  SKIPPED: {spotify_name} (synced {age_days}d ago, {len(tracks)} tracks unchanged)")
                            else:
                                self.logger.info(
                                    f"⏩ Skipping '{spotify_name}': synced {age_days}d ago, "
                                    f"count unchanged ({len(tracks)} tracks)"
                                )
                            self._stats["playlist_cache_skips"] += 1
                            return 0, 0
                    except Exception:
                        pass  # Malformed timestamp — proceed with normal sync

            # Get local state of Apple Music playlist from last successful sync
            local_am_state = self.cache_manager.get_apple_playlist_state(playlist_name)
            
            # Build signature for current Apple Music tracks
            current_am_signatures = []
            for t in tracks:
                key = self._track_cache_key(t["title"], t["artist"], t.get("album"))
                current_am_signatures.append("|".join([str(x) for x in key]))

            # Compare AM state (Has Apple Music changed?)
            last_am_signatures = [x["signature"] for x in local_am_state]
            am_changed = current_am_signatures != last_am_signatures
            
            # Compare Spotify state (Has Spotify changed externally?)
            cached_playlist = self.cache_manager.get_playlist_metadata(playlist_id)
            sp_changed = True
            if cached_playlist and sp_snapshot == cached_playlist.get("snapshot_id") and sp_total == len(tracks):
                 sp_changed = False

            # Optimization condition:
            # If AM hasn't changed AND Spotify hasn't changed externally AND not forced
            if not force_sync and not am_changed and not sp_changed:
                 if self.minimal:
                     print(f"  SKIPPED: {spotify_name} (no changes)")
                 else:
                     self.logger.info(f"✅ No changes detected for '{spotify_name}'. Skipping sync.")
                 self._stats["playlist_cache_skips"] += 1
                 return 0, 0

            # 3. Resolve Track IDs
            # We must resolve all tracks to ensure we have the correct target list for Spotify
            # Thanks to CacheManager, this is fast for known tracks.
            target_spotify_ids = []
            not_found_tracks = []
            
            # Identify which tracks are "new" to this playlist effectively (for logging mainly)
            # The actual finding happens for all, leveraging cache.
            
            total_tracks = len(tracks)
            if self.minimal:
                print(f"  Resolving {total_tracks} tracks...")
            else:
                self.logger.info(f"🔍 Resolving {total_tracks} tracks...")

            resolved_tracks_for_state = [] # List of dicts for updating DB state

            for i, track in enumerate(tracks, 1):
                if not self.minimal and i % 50 == 0:
                     self.logger.info(f"  Processed {i}/{total_tracks}...")
                
                title = track["title"]
                artist = track["artist"]
                album = track.get("album")
                
                # find_track uses SQLite cache internaly
                track_id = self.find_track(title, artist, album)
                
                signature = "|".join([str(x) for x in self._track_cache_key(title, artist, album)])
                
                if track_id:
                    target_spotify_ids.append(track_id)
                    resolved_tracks_for_state.append({
                        "signature": signature,
                        "spotify_track_id": track_id
                    })
                else:
                    album_info = f" (album: {album})" if album else ""
                    not_found_tracks.append(f"{title} - {artist}{album_info}")
                    # For state, we record it but with no ID, preventing caching of empty results effectively
                    # or should we cache failure? find_track handles cache.
            
            if not_found_tracks:
                 self.logger.warning(f"⚠️ {len(not_found_tracks)} tracks not found for '{spotify_name}'")

            # 4. Update Spotify
            # Get current tracks from Spotify to calc diff
            current_spotify_ids = self.get_playlist_tracks(playlist_id, force_refresh=True)
            
            tracks_added = 0
            tracks_removed = 0

            # Deduplicate target list while preserving order
            seen = set()
            deduped_target_ids = []
            for tid in target_spotify_ids:
                if tid not in seen:
                    seen.add(tid)
                    deduped_target_ids.append(tid)
            target_spotify_ids = deduped_target_ids

            if clean_sync:
                # Clear the entire playlist then re-add the exact target list.
                # This is the only reliable way to remove duplicates and stale tracks.
                current_set = set(current_spotify_ids)
                target_set = set(target_spotify_ids)
                tracks_removed = len(current_set - target_set)  # net removals for stats
                tracks_added = len(target_set - current_set)    # net additions for stats
                if not dry_run:
                    n = len(current_spotify_ids)
                    self.logger.info(f"🧹 Clearing playlist ({n} tracks) for clean sync...")
                    self._make_api_call(lambda: self.sp.playlist_replace_items(playlist_id, []))
                    self._batch_add_tracks(playlist_id, target_spotify_ids, dry_run=False)
            else:
                # Incremental: only add tracks not already present (no removal)
                current_set = set(current_spotify_ids)
                to_add = [tid for tid in target_spotify_ids if tid not in current_set]
                if to_add:
                    self.logger.info(f"➕ Adding {len(to_add)} new tracks...")
                    tracks_added = self._batch_add_tracks(playlist_id, to_add, dry_run=dry_run)

            self.logger.info(f"✅ Sync result: +{tracks_added} / -{tracks_removed}")

            # 5. Update State
            if not dry_run:
                # Update Apple Playlist State (local definition of what SHOULD be there)
                self.cache_manager.update_apple_playlist_state(playlist_name, resolved_tracks_for_state)
                
                # Fetch final metadata to update playlist cache
                final_meta = self.get_playlist_metadata(playlist_id)
                # We don't need to fetch tracks again, we assume sync worked
                # But to be safe for next run snapshot check:
                self.cache_manager.save_playlist_metadata(
                    playlist_id, 
                    final_meta.get("snapshot_id"), 
                    final_meta.get("total"),
                    spotify_name
                )
                
                # Record History
                if self.transfer_history:
                    self.transfer_history.record_transfer(
                        playlist_name=spotify_name,
                        spotify_playlist_id=playlist_id,
                        tracks_added=tracks_added,
                        tracks_removed=tracks_removed,
                        total_tracks=len(target_spotify_ids),
                        apple_track_count=len(tracks),
                        status="success"
                    )

            return tracks_added, tracks_removed

        except Exception as e:
            self.logger.error(f"❌ Error syncing playlist '{playlist_name}': {e}")
            raise PlaylistSyncError(f"Failed to sync playlist '{playlist_name}': {e}")

class PlaylistSync:
    """Main class for syncing playlists from Apple Music to Spotify."""
    
    def __init__(self, minimal_output: bool = False, show_cache: bool = False, dry_run: bool = False):
        self.minimal_output = minimal_output
        self.show_cache = show_cache
        self.logger = setup_logger("playlist_sync")
        if self.minimal_output:
            try:
                self.logger.setLevel(logging.ERROR)
                for h in list(self.logger.handlers):
                    h.setLevel(logging.ERROR)
            except Exception:
                pass
        self.apple_extractor = AppleMusicExtractor(Config.apple_script_path())
        # Allow SpotifyManager to skip authentication for cache-only operations by default authenticate=True
        self.spotify_manager = SpotifyManager(minimal=self.minimal_output, authenticate=True)
        self.dry_run = dry_run
    
    def sync_all_playlists(self, clean_sync: bool = False, force_sync: bool = False, dry_run: bool = False, map_only: bool = False) -> Dict[str, Dict[str, int]]:
        """
        Sync all Apple Music playlists to Spotify.
        
        Args:
            clean_sync: Whether to remove tracks not in Apple Music
            force_sync: Whether to ignore cached playlist metadata
            dry_run: Whether to simulate changes
            map_only: Whether to only establish mappings without syncing tracks
            
        Returns:
            Dictionary with sync statistics per playlist
        """
        try:
            # Validate configuration
            Config.validate()
            
            # Get Apple Music playlists
            self.logger.info("🎵 Extracting playlists from Apple Music...")
            apple_playlists = self.apple_extractor.get_playlists()
            
            if not apple_playlists:
                self.logger.warning("No playlists found in Apple Music")
                return {}
            
            # Sync each playlist with progress tracking
            sync_stats = {}
            total_tracks_added = 0
            total_tracks_removed = 0
            total_playlists = len(apple_playlists)
            
            # Resume capability: Filter out already completed playlists
            sync_state_manager = self.spotify_manager.sync_state_manager
            completed_playlists = 0
            
            # If we are starting fresh (clean sync or user request), clear the state
            # If we are starting fresh (clean sync or user request), clear the state
            if clean_sync or force_sync:  # Using args here is tricky, we need to pass this info down
                # Actually, sync_all_playlists doesn't have access to args directly, but we can infer intent
                # If force_sync is True, we probably shouldn't be resuming, OR we should resume but re-sync?
                # The user requirement is: "resume on next run". 
                # If the user explicitly asks for a force sync, maybe we should ignore state?
                # Let's keep it simple: if there is state, we try to resume regardless, unless cleared.
                # But wait, 'force_sync' usually means re-do everything.
                pass

            playlists_to_process = {}
            for name, content in apple_playlists.items():
                if not map_only and not force_sync and sync_state_manager.is_completed(name):
                    playlists_to_process[name] = {"skipped": True}
                    completed_playlists += 1
                else:
                    playlists_to_process[name] = {"skipped": False, "content": content}
            
            if completed_playlists > 0:
                self.logger.info(f"⏩ Resuming: Skipping {completed_playlists} already synced playlists.")
            
            # Filter the actual dictionary to process
            active_playlists = {k: v["content"] for k, v in playlists_to_process.items() if not v["skipped"]}
            
            self.logger.info(f"📋 Found {total_playlists} total playlists, {len(active_playlists)} to process")
            
            # Batch lookup all unique tracks across playlists to minimize API calls
            if Config.ENABLE_BATCH_LOOKUP and not map_only and active_playlists:
                self.logger.info("🚀 Starting batch track lookup to optimize API usage...")
                self.spotify_manager.batch_find_tracks(active_playlists)
            
            # We process active_playlists, but we need to track index relative to total
            processed_count = 0
            
            for playlist_name, tracks in active_playlists.items():
                processed_count += 1
                i = completed_playlists + processed_count # Approximate index
                
                mode_str = "Mapping" if map_only else "Syncing"
                self.logger.info(f"🔄 [{i}/{total_playlists}] {mode_str} playlist: {playlist_name} ({len(tracks)} tracks)")
                
                try:
                    if map_only:
                        # Just find or create (this establishes the mapping and updates the name if needed)
                        # We don't call sync_playlist which does track updates
                        playlist_id = self.spotify_manager.find_or_create_playlist(playlist_name, dry_run=dry_run)
                        sync_stats[playlist_name] = {
                            "status": "mapped",
                            "spotify_id": playlist_id,
                            "total_tracks": len(tracks)
                        }
                    else:
                        tracks_added, tracks_removed = self.spotify_manager.sync_playlist(
                            playlist_name, tracks, clean_sync, force_sync, dry_run
                        )
                        
                        sync_stats[playlist_name] = {
                            "tracks_added": tracks_added,
                            "tracks_removed": tracks_removed,
                            "total_tracks": len(tracks)
                        }
                        
                        total_tracks_added += tracks_added
                        total_tracks_removed += tracks_removed
                        
                        # Mark as completed in state manager ONLY if not dry run
                        if not dry_run:
                            sync_state_manager.mark_completed(playlist_name)
                    
                    # Progress indicator
                    progress = (i / total_playlists) * 100
                    self.logger.info(f"✅ [{i}/{total_playlists}] Completed {playlist_name} ({progress:.1f}%)")
                
                except RateLimitExceededError as e:
                    self.logger.error(f"🛑 RATE LIMIT EXCEEDED while syncing '{playlist_name}': {e}")
                    self.logger.info("💾 Progress has been saved. Run the script again later to resume from where you left off.")
                    # We re-raise to exit the loop and the program
                    raise
                    
                except PlaylistSyncError as e:
                    self.logger.error(f"❌ [{i}/{total_playlists}] Failed to process playlist '{playlist_name}': {e}")
                    sync_stats[playlist_name] = {
                        "tracks_added": 0,
                        "tracks_removed": 0,
                        "total_tracks": len(tracks),
                        "error": str(e)
                    }
                finally:
                    pass
            
            # Summary
            if map_only:
                self.logger.info("🎉 Mapping completed!")
            else:
                self.logger.info("🎉 Sync completed!")
                self.logger.info(f"📊 Total tracks added: {total_tracks_added}")
                self.logger.info(f"🗑️  Total tracks removed: {total_tracks_removed}")
                
                # If we completed successfully without exceptions and it wasn't a dry run, clear the state
                if not dry_run:
                    sync_state_manager.clear()
            
            self.logger.info(f"📋 Playlists processed: {total_playlists}")
            
            return sync_stats
            
        except RateLimitExceededError:
            # Already logged in the loop
            # Return partial stats or just raise to exit?
            # Raising lets main() handle it if needed, or just exit.
            # But we want to ensure we don't clear the state.
            raise
            
        except Exception as e:
            self.logger.error(f"💥 Sync failed: {e}")
            raise PlaylistSyncError(f"Sync failed: {e}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync Apple Music playlists to Spotify")
    parser.add_argument(
        "--clean-sync",
        action="store_true",
        help="Remove Spotify tracks that are no longer present on Apple Music"
    )
    parser.add_argument(
        "--force-sync",
        action="store_true",
        help="Ignore cached playlist metadata and force a sync (may use more API calls)"
    )
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Suppress verbose logs and show only concise run summary"
    )
    parser.add_argument(
        "--cache-summary",
        action="store_true",
        help="Print cache summary at end of run (track/playlist counts and sample)"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear playlist and track caches and continue"
    )
    parser.add_argument(
        "--clear-cache-only",
        action="store_true",
        help="Clear caches and exit without syncing"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate sync without making changes to Spotify"
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        help="Show transfer history for all playlists"
    )
    parser.add_argument(
        "--playlist-history",
        type=str,
        metavar="PLAYLIST_NAME",
        help="Show transfer history for a specific playlist"
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear all transfer history"
    )
    parser.add_argument(
        "--show-mappings",
        action="store_true",
        help="Show all playlist mappings (Apple Music → Spotify)"
    )
    parser.add_argument(
        "--show-mapping",
        type=str,
        metavar="PLAYLIST_NAME",
        help="Show mapping for a specific Apple Music playlist"
    )
    parser.add_argument(
        "--clear-mappings",
        action="store_true",
        help="Clear all playlist mappings"
    )
    parser.add_argument(
        "--map-only",
        action="store_true",
        help="Establish playlist mappings only without syncing tracks"
    )
    args = parser.parse_args()
    
    logger = setup_logger("main")
    
    try:
        logger.info(
            "Starting Apple Music to Spotify playlist sync (clean_sync=%s, force_sync=%s)...",
            args.clean_sync,
            args.force_sync
        )
        if args.minimal:
            # reduce global verbosity for minimal mode
            logging.getLogger().setLevel(logging.ERROR)
        sync = PlaylistSync()
        sync = PlaylistSync(minimal_output=args.minimal, show_cache=args.cache_summary, dry_run=args.dry_run)

        # Handle transfer history options
        if args.show_history or args.playlist_history or args.clear_history:
            history = TransferHistory()
            
            if args.clear_history:
                if history.clear():
                    print("✅ Cleared transfer history")
                    return 0
                else:
                    print("❌ Failed to clear transfer history")
                    return 1
            
            if args.show_history:
                transfers = history.get_history()
                if not transfers:
                    print("No transfer history found")
                    return 0
                
                print("\n" + "="*70)
                print("TRANSFER HISTORY")
                print("="*70)
                for transfer in transfers:
                    timestamp = transfer.get("timestamp", "Unknown")
                    playlist = transfer.get("playlist_name", "Unknown")
                    added = transfer.get("tracks_added", 0)
                    removed = transfer.get("tracks_removed", 0)
                    total = transfer.get("total_tracks", 0)
                    print(f"{timestamp} | {playlist}")
                    print(f"  ➕ {added} added, ➖ {removed} removed, 📊 {total} total")
                print("="*70)
                return 0
            
            if args.playlist_history:
                transfers = history.get_playlist_history(args.playlist_history)
                if not transfers:
                    print(f"No transfer history found for playlist: {args.playlist_history}")
                    return 0
                
                print("\n" + "="*70)
                print(f"TRANSFER HISTORY: {args.playlist_history}")
                print("="*70)
                for transfer in transfers:
                    timestamp = transfer.get("timestamp", "Unknown")
                    added = transfer.get("tracks_added", 0)
                    removed = transfer.get("tracks_removed", 0)
                    total = transfer.get("total_tracks", 0)
                    status = transfer.get("status", "unknown")
                    print(f"{timestamp} | Status: {status}")
                    print(f"  ➕ {added} added, ➖ {removed} removed, 📊 {total} total")
                print("="*70)
                return 0

        # Handle playlist mapping options
        if args.show_mappings or args.show_mapping or args.clear_mappings:
            from cache_manager import CacheManager
            cache_mgr = CacheManager()
            
            if args.clear_mappings:
                if cache_mgr.clear_all_playlist_mappings():
                    print("✅ Cleared all playlist mappings")
                    return 0
                else:
                    print("❌ Failed to clear playlist mappings")
                    return 1
            
            if args.show_mapping:
                mapping_id = cache_mgr.get_playlist_mapping(args.show_mapping)
                if mapping_id:
                    print(f"\n{'='*70}")
                    print(f"PLAYLIST MAPPING: {args.show_mapping}")
                    print(f"{'='*70}")
                    print(f"Apple Music Name: {args.show_mapping}")
                    print(f"Spotify ID: {mapping_id}")
                    print(f"{'='*70}\n")
                else:
                    print(f"No mapping found for playlist: {args.show_mapping}")
                return 0
            
            if args.show_mappings:
                mappings = cache_mgr.get_all_playlist_mappings()
                if not mappings:
                    print("No playlist mappings found")
                    return 0
                
                print(f"\n{'='*70}")
                print("PLAYLIST MAPPINGS")
                print(f"{'='*70}")
                for mapping in mappings:
                    apple_name = mapping.get("apple_name", "Unknown")
                    spotify_id = mapping.get("spotify_id", "Unknown")
                    spotify_name = mapping.get("spotify_name", "Unknown")
                    last_synced = mapping.get("last_synced", "Never")
                    print(f"Apple: {apple_name}")
                    print(f"  → Spotify: {spotify_name} (ID: {spotify_id})")
                    print(f"  Last synced: {last_synced}")
                    print()
                print(f"{'='*70}\n")
                return 0

        # Handle cache clearing options before proceeding
        if args.clear_cache_only:
            manager = SpotifyManager(minimal=args.minimal, authenticate=False)
            if manager.clear_all_cache():
                print("Cleared caches")
                return 0
            else:
                print("Failed to clear caches")
                return 1

        if args.clear_cache:
            manager = SpotifyManager(minimal=args.minimal, authenticate=False)
            ok = manager.clear_all_cache()
            if ok:
                print("Cleared caches")
            else:
                print("Failed to clear caches")
        stats = sync.sync_all_playlists(
            clean_sync=args.clean_sync, 
            force_sync=args.force_sync,
            dry_run=args.dry_run,
            map_only=args.map_only
        )
        
        # Print summary
        title = "MAPPING SUMMARY" if args.map_only else "SYNC SUMMARY"
        print("\n" + "="*50)
        print(title)
        print("="*50)
        for playlist_name, stats_data in stats.items():
            if "error" in stats_data:
                print(f"❌ {playlist_name}: ERROR - {stats_data['error']}")
            elif args.map_only:
                print(f"✅ {playlist_name}: Mapped to {stats_data.get('spotify_id')} ({stats_data['total_tracks']} tracks)")
            else:
                print(f"✅ {playlist_name}: +{stats_data['tracks_added']} -{stats_data['tracks_removed']} ({stats_data['total_tracks']} total)")
        print("="*50)
        
    except PlaylistSyncError as e:
        logger.error(f"Sync failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
