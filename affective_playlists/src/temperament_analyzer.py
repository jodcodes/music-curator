#!/usr/bin/env python3
"""
Music Playlist Temperament Analyzer (Feature: 4tempers).

LAYER: Application Layer - Feature Implementation
ROLE: Main orchestrator for temperament analysis
ARCHITECTURE: See src/README.md for full architecture

Categorizes macOS Music.app playlists into four temperament folders:
- Woe (Melancholic) - sadness, introspection, melancholy
- Frolic (Sanguine) - joy, happiness, optimism, celebration
- Dread (Phlegmatic) - fear, anxiety, tension, dramatic
- Malice (Choleric) - rage, anger, intense, aggressive

Uses LLM-based analysis of track metadata via native macOS AppleScript.
No Apple developer account needed!

IMPLEMENTATION FLOW:
1. apple_music.py → Get playlist from Music.app
2. For each track:
   - llm_client.py → Send to LLM (OpenAI or Claude)
   - prompts.py → Use temperament classification prompt
   - Receive temperament classification
3. playlist_manager.py → Create temperament folders
4. apple_music.py → Move playlists to folders

SETUP INSTRUCTIONS:
1. Install dependencies:
   pip install requests python-dotenv

2. Create .env file with:
   OPENAI_API_KEY=your_openai_key
   or
   ANTHROPIC_API_KEY=your_anthropic_key

3. Music.app must be installed (comes with macOS)

Uses native macOS Music.app with AppleScript automation.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess

# Add project root to path for shared imports
import sys
import time
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

import requests
from dotenv import load_dotenv
from tqdm import tqdm

from src.models import ClassificationResult, Playlist, Temperament, Track
from src.playlist_utils import PlaylistSelector, PlaylistWhitelistFilter
from src.prompts import (
    SYSTEM_PROMPT_PLAYLIST,
    SYSTEM_PROMPT_TRACK,
    get_playlist_classification_prompt,
    get_track_classification_prompt,
    log_temperament_info,
)
from src.result_utils import ResultSummary, ResultWriter
from src.track_metadata import (
    MockTrackMetadataClient,
    MusicBrainzTrackMetadataClient,
    SpotifyTrackMetadataClient,
    TrackMetadataClient,
)

# ==================== CONFIGURATION ====================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("temperament_analyzer.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# NOTE: Data models (Track, Playlist, Temperament, ClassificationResult)
# are now defined in models.py and imported above


# NOTE: Interactive playlist selection is now in PlaylistSelector (playlist_utils.py)
# Use PlaylistSelector.select_playlists_interactive() instead


# ==================== ABSTRACT INTERFACES ====================


class MusicLibraryClient(ABC):
    """Abstract interface for music library access"""

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the music service"""
        pass

    @abstractmethod
    def get_playlists(
        self, metadata_client: Optional[TrackMetadataClient] = None
    ) -> List[Playlist]:
        """Retrieve all user playlists"""
        pass

    @abstractmethod
    def create_folder(self, folder_name: str) -> str:
        """Create a playlist folder and return its ID"""
        pass

    @abstractmethod
    def move_playlist_to_folder(self, playlist_id: str, folder_id: str) -> bool:
        """Move a playlist to a folder"""
        pass


class LLMClient(ABC):
    """Abstract interface for LLM-based classification"""

    @abstractmethod
    def classify_track(self, track: Track) -> ClassificationResult:
        """Classify a single track by temperament"""
        pass

    @abstractmethod
    def classify_playlist(
        self, playlist: Playlist, track_classifications: List[ClassificationResult]
    ) -> ClassificationResult:
        """Classify a playlist based on its tracks and metadata"""
        pass


# ==================== MACOS MUSIC APP IMPLEMENTATION ====================


class MusicAppClient(MusicLibraryClient):
    """
    macOS Music.app client using AppleScript.

    No API keys or developer account needed!
    Uses native macOS automation to control the Music app.
    """

    def __init__(self):
        self.music_app = "Music"  # macOS Monterey+ uses "Music" app
        # Point to scripts directory (now in src/scripts/)
        self.script_dir = os.path.join(os.path.dirname(__file__), "scripts")
        # Load shared configurations
        self.whitelist_enabled, self.whitelist = self._load_whitelist()
        self.playlist_folders_config = self._load_playlist_folders_config()
        # Cache for playlists with IDs
        self._playlist_ids_cache = None

    @staticmethod
    def _load_whitelist():
        """Load centralized whitelist configuration using shared module"""
        try:
            from src.config import load_centralized_whitelist

            return load_centralized_whitelist(enabled_by_default=False)
        except ImportError:
            logger.warning("Could not import shared.config")
            return False, set()

    def _load_playlist_folders_config(self) -> Dict[str, Any]:
        """Load playlist folders config from data/config/ directory"""
        try:
            import json

            config_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "config", "playlist_folders.json"
            )
            with open(config_path, "r") as f:
                return cast(Dict[str, Any], json.load(f))
        except Exception as e:
            logger.warning(f"Could not load playlist folders config: {e}")
            return {}

    def authenticate(self) -> bool:
        """Check if Music app is available"""
        try:
            # Use external AppleScript
            script_path = os.path.join(self.script_dir, "music_app.applescript")
            result = self._run_applescript_file(script_path)

            if result:
                logger.info(f"Successfully connected to {result.strip()}")
                return True

        except Exception as e:
            logger.error(f"Failed to connect to Music app: {e}")

        return False

    def _get_playlist_ids(self) -> Dict[str, str]:
        """Get all user playlists with their persistent IDs"""
        if self._playlist_ids_cache is not None:
            return self._playlist_ids_cache

        try:
            script_path = os.path.join(self.script_dir, "get_ids_playlists.applescript")
            result = self._run_applescript_file(script_path)

            if not result:
                logger.error("Failed to get playlist IDs")
                return {}

            # Parse output: name:PlaylistName, id:HEXid, name:...
            import re

            playlists: Dict[str, str] = {}
            # Match both with and without quotes around names
            matches: List[Tuple[str, str]] = re.findall(r"name:([^,]+),\s*id:([A-F0-9]+)", result)  # type: ignore[assignment]

            for name, pid in matches:
                # Clean up name (remove quotes if present)
                name = name.strip().strip("'\"")
                if name and pid:
                    playlists[name] = pid

            logger.debug(f"Parsed {len(playlists)} playlists from AppleScript output")
            self._playlist_ids_cache = playlists
            return playlists  # type: ignore[return-value]

        except Exception as e:
            logger.error(f"Error getting playlist IDs: {e}")
            return {}

    def get_playlists(
        self, metadata_client: Optional[TrackMetadataClient] = None
    ) -> List[Playlist]:
        """Retrieve all user playlists from Music.app using persistent IDs"""
        playlists = []

        try:
            logger.info("Fetching playlists from Music.app...")

            # Get all playlists with their IDs
            playlists_with_ids = self._get_playlist_ids()
            if not playlists_with_ids:
                logger.warning("No playlists found in Music app")
                return []

            logger.info(f"Found {len(playlists_with_ids)} total playlists in Music.app")

            # Filter to whitelist if enabled
            if self.whitelist_enabled and self.whitelist:
                playlists_to_process = {
                    name: pid for name, pid in playlists_with_ids.items() if name in self.whitelist
                }
                logger.info(
                    f"Whitelist enabled: Filtered to {len(playlists_to_process)} whitelisted playlists"
                )
            else:
                logger.info("Whitelist disabled: Processing all playlists")
                playlists_to_process = playlists_with_ids

            # Fetch tracks for each playlist using ID
            for playlist_name, playlist_id in tqdm(
                playlists_to_process.items(), desc="Loading playlists", unit="playlist"
            ):
                try:
                    logger.debug(f"Processing playlist: {playlist_name} (ID: {playlist_id})")
                    playlist = self._get_playlist_with_tracks_by_id(
                        playlist_name, playlist_id, metadata_client
                    )

                    if playlist and playlist.tracks:
                        playlists.append(playlist)
                        logger.info(f"Loaded: {playlist_name} ({len(playlist.tracks)} tracks)")
                    else:
                        logger.debug(f"Skipped playlist '{playlist_name}' - no tracks")

                except Exception as e:
                    logger.warning(f"Failed to load playlist '{playlist_name}': {e}")
                    continue

            logger.info(f"Successfully loaded {len(playlists)} playlists with tracks")
            return playlists

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to retrieve playlists: {error_msg}")
            print(f"\nError: {error_msg}")
            if "609" in error_msg:
                print("Tip: Restart the Music app and try again.")
            return []

    def _get_playlist_with_tracks_by_id(
        self,
        playlist_name: str,
        playlist_id: str,
        metadata_client: Optional[TrackMetadataClient] = None,
    ) -> Optional[Playlist]:
        """Get a specific playlist with all its tracks using persistent ID"""
        try:
            logger.debug(f"Fetching tracks for playlist: {playlist_name} (ID: {playlist_id})")
            script_path = os.path.join(self.script_dir, "get_tracks_info_playlists.applescript")
            result = self._run_applescript_file(script_path, [playlist_id])

            if not result or result.strip() == "" or "ERROR" in result:
                logger.debug(f"No tracks found in playlist '{playlist_name}'")
                return None

            # Parse AppleScript record format
            # Format: key1:value1, key2:value2, key3:value3, ...
            import re

            tracks: List[Track] = []
            seen_tracks: set = set()

            # Split by "playlistID:" to separate tracks
            track_strings = result.split("playlistID:")[1:]  # Skip empty first split

            for track_str in track_strings:
                try:
                    track_dict = {}
                    parts = track_str.split(", ")

                    # Parse key-value pairs
                    for part in parts:
                        if ":" in part:
                            key, val = part.split(":", 1)
                            key = key.strip()
                            val = val.strip()
                            track_dict[key] = val

                    # Extract fields
                    track_name = track_dict.get("name", "")
                    artist = track_dict.get("artist", "")

                    if not track_name or not artist:
                        continue

                    # Deduplication
                    track_key = f"{track_name}_{artist}".lower()
                    if track_key in seen_tracks:
                        logger.debug(f"Skipping duplicate: {track_name}")
                        continue

                    seen_tracks.add(track_key)

                    # Create track
                    track = Track(
                        track_id=track_dict.get("trackID", f"{playlist_id}_{len(tracks)}"),
                        name=track_name,
                        artist=artist,
                        album=track_dict.get("album"),
                        genre=track_dict.get("genre"),
                    )

                    # Enrich with metadata if client provided
                    if metadata_client:
                        try:
                            enriched = metadata_client.get_track_info(track.name, track.artist)
                            if enriched:
                                track.album = track.album or enriched.album
                                track.genre = track.genre or enriched.genre
                        except Exception as e:
                            logger.debug(f"Could not enrich track {track.name}: {e}")

                    tracks.append(track)

                except Exception as e:
                    logger.warning(f"Failed to process track in '{playlist_name}': {e}")
                    continue

            if not tracks:
                logger.debug(f"No valid tracks found in playlist '{playlist_name}'")
                return None

            # Create playlist
            playlist = Playlist(
                playlist_id=playlist_id,
                name=playlist_name,
                tracks=tracks,
                folder_path=None,
                description=None,
            )

            logger.debug(f"Loaded {len(tracks)} tracks for playlist '{playlist_name}'")
            return playlist

        except Exception as e:
            logger.error(f"Failed to get tracks for playlist '{playlist_name}': {e}")
            return None

    def create_folder(self, folder_name: str) -> str:
        """Create a playlist folder in Music.app and return its ID"""
        try:
            # Use AppleScript to create folder
            script = f"""
tell application "Music"
    set newFolder to make new folder playlist with properties {{name:"{folder_name}"}}
    return (get persistent ID of newFolder)
end tell
            """
            result = self._run_applescript(script)
            folder_id = result.strip() if result else None

            if folder_id:
                logger.info(f"Created folder: {folder_name} (ID: {folder_id})")
                return cast(str, folder_id)
            else:
                logger.error(f"Failed to create folder: {folder_name}")
                # Fallback: return mock ID or raise error
                return ""

        except Exception as e:
            logger.warning(f"Could not create folder via AppleScript: {e}")
            # Fallback: return mock ID
            return cast(str, f"folder_{folder_name.lower().replace(' ', '_')}")

    def move_playlist_to_folder(self, playlist_id: str, folder_id: str) -> bool:
        """Move a playlist to a folder using persistent IDs"""
        try:
            script_path = os.path.join(self.script_dir, "move_playlist_to_folder.applescript")
            result = self._run_applescript_file(script_path, [playlist_id, folder_id])

            if result and "SUCCESS" in result:
                logger.info(f"Moved playlist (ID: {playlist_id}) to folder (ID: {folder_id})")
                return True
            else:
                logger.error(f"Failed to move playlist: {result}")
                return False

        except Exception as e:
            logger.error(f"Error moving playlist: {e}")
            return False

    def _run_applescript(self, script: str) -> str:
        """Execute AppleScript and return output"""
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                raise Exception(f"AppleScript error: {error_msg}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise Exception("AppleScript execution timed out")
        except Exception as e:
            raise Exception(f"Failed to execute AppleScript: {e}")

    def _run_applescript_file(self, script_path: str, args: Optional[List[str]] = None) -> str:
        """Execute an AppleScript file and return output"""
        try:
            if not os.path.exists(script_path):
                raise Exception(f"AppleScript file not found: {script_path}")

            cmd = ["osascript", script_path]
            if args:
                cmd.extend(args)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                raise Exception(f"AppleScript error: {error_msg}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise Exception("AppleScript execution timed out")
        except Exception as e:
            raise Exception(f"Failed to execute AppleScript: {e}")


# ==================== OPENAI LLM IMPLEMENTATION ====================


class OpenAILLMClient(LLMClient):
    """OpenAI GPT-based classification client"""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

    def classify_track(self, track: Track) -> ClassificationResult:
        """Classify a track using GPT"""
        prompt = get_track_classification_prompt(track.get_metadata_string())

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_TRACK},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            }

            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            classification = json.loads(content)

            temp_map = {
                "Woe": Temperament.WOE,
                "Frolic": Temperament.FROLIC,
                "Dread": Temperament.DREAD,
                "Malice": Temperament.MALICE,
            }

            temperament = temp_map.get(classification["temperament"], Temperament.FROLIC)

            logger.debug(
                f"Track '{track.name}' classified as {temperament.value} (confidence: {classification.get('confidence', 0.5):.2f})"
            )

            return ClassificationResult(
                temperament=temperament,
                confidence=classification.get("confidence", 0.5),
                reasoning=classification.get("reasoning", "No reasoning provided"),
            )

        except Exception as e:
            logger.error(f"Failed to classify track '{track.name}': {e}")
            return ClassificationResult(
                temperament=Temperament.FROLIC,
                confidence=0.1,
                reasoning=f"Classification failed: {str(e)}",
            )

    def classify_playlist(
        self, playlist: Playlist, track_classifications: List[ClassificationResult]
    ) -> ClassificationResult:
        """Classify a playlist based on track classifications and metadata"""

        temperament_counts = Counter([c.temperament for c in track_classifications])
        avg_confidences = {}

        for temp in Temperament:
            relevant = [c for c in track_classifications if c.temperament == temp]
            if relevant:
                avg_confidences[temp] = sum(c.confidence for c in relevant) / len(relevant)
            else:
                avg_confidences[temp] = 0.0

        track_summary = self._format_track_summary(temperament_counts, avg_confidences)
        sample_tracks = self._format_sample_tracks(playlist.tracks[:5])

        prompt = get_playlist_classification_prompt(
            playlist.get_metadata_string(), track_summary, sample_tracks
        )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_PLAYLIST},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            }

            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            classification = json.loads(content)

            temp_map = {
                "Woe": Temperament.WOE,
                "Frolic": Temperament.FROLIC,
                "Dread": Temperament.DREAD,
                "Malice": Temperament.MALICE,
            }

            temperament = temp_map.get(classification["temperament"], Temperament.FROLIC)

            logger.debug(
                f"Playlist '{playlist.name}' classified as {temperament.value} (confidence: {classification.get('confidence', 0.5):.2f})"
            )

            return ClassificationResult(
                temperament=temperament,
                confidence=classification.get("confidence", 0.5),
                reasoning=classification.get("reasoning", "No reasoning provided"),
            )

        except Exception as e:
            logger.error(f"Failed to classify playlist '{playlist.name}': {e}")
            dominant_temp = (
                temperament_counts.most_common(1)[0][0]
                if temperament_counts
                else Temperament.FROLIC
            )
            return ClassificationResult(
                temperament=dominant_temp,
                confidence=avg_confidences.get(dominant_temp, 0.3),
                reasoning=f"Using track-level majority vote due to API error: {str(e)}",
            )

    def _format_track_summary(self, counts: Counter, confidences: Dict[Temperament, float]) -> str:
        """Format track classification summary"""
        lines = []
        for temp in Temperament:
            count = counts.get(temp, 0)
            conf = confidences.get(temp, 0.0)
            lines.append(f"  - {temp.value}: {count} tracks (avg confidence: {conf:.2f})")
        return "\n".join(lines)

    def _format_sample_tracks(self, tracks: List[Track]) -> str:
        """Format sample tracks for context"""
        return "\n".join([f"  - {t.name} by {t.artist}" for t in tracks])


# ==================== CORE ANALYZER ====================


class TemperamentAnalyzer:
    """Main analyzer that orchestrates the classification process"""

    def __init__(self, music_client: MusicLibraryClient, llm_client: LLMClient):
        self.music_client = music_client
        self.llm_client = llm_client
        self.track_cache: Dict[str, ClassificationResult] = {}
        self.results_log: List[Dict] = []

    def analyze_and_organize(
        self, playlists: Optional[List[Playlist]] = None, batch_size: int = 10
    ) -> bool:
        """Main method to analyze playlists and organize them

        Args:
            playlists: Specific playlists to analyze. If None, analyzes all.
            batch_size: Number of tracks before pausing between API calls
        """
        logger.info("Starting temperament analysis...")

        if not self.music_client.authenticate():
            logger.error("Failed to authenticate with music service")
            return False

        # If no specific playlists provided, fetch all
        if playlists is None:
            logger.info("Fetching playlists...")
            playlists = self.music_client.get_playlists()
        else:
            logger.info(f"Analyzing {len(playlists)} selected playlist(s)...")

        if not playlists:
            logger.warning("No playlists found")
            return False

        logger.info(f"Found {len(playlists)} playlists to analyze")

        logger.info("Setting up temperament folders...")
        folders = self._create_temperament_folders()

        logger.info("Classifying playlists...")

        for idx, playlist in enumerate(playlists, 1):
            logger.info(
                f"Processing playlist {idx}/{len(playlists)}: {playlist.name} (ID: {playlist.playlist_id})"
            )

            try:
                track_classifications = []

                for track_idx, track in enumerate(playlist.tracks, 1):
                    # Use track_id for deduplication (persistent identifier)
                    cache_key = track.track_id

                    if cache_key in self.track_cache:
                        classification = self.track_cache[cache_key]
                        logger.debug(f"Using cached classification for track ID: {track.track_id}")
                    else:
                        classification = self.llm_client.classify_track(track)
                        self.track_cache[cache_key] = classification
                        logger.debug(
                            f"Classified {track_idx}/{len(playlist.tracks)}: {track.name} -> {classification.temperament.value}"
                        )

                    track_classifications.append(classification)

                    if track_idx % batch_size == 0:
                        time.sleep(1)

                playlist_classification = self.llm_client.classify_playlist(
                    playlist, track_classifications
                )

                logger.info(
                    f"Playlist '{playlist.name}' classified as: {playlist_classification.temperament.value} "
                    f"(confidence: {playlist_classification.confidence:.2f})"
                )
                logger.info(f"Reasoning: {playlist_classification.reasoning}")

                folder_id = folders[playlist_classification.temperament]
                success = self.music_client.move_playlist_to_folder(playlist.playlist_id, folder_id)

                self.results_log.append(
                    {
                        "playlist_name": playlist.name,
                        "playlist_id": playlist.playlist_id,
                        "temperament": playlist_classification.temperament.value,
                        "confidence": playlist_classification.confidence,
                        "reasoning": playlist_classification.reasoning,
                        "track_count": len(playlist.tracks),
                        "moved": success,
                    }
                )

                time.sleep(2)

            except Exception as e:
                logger.error(f"Failed to process playlist '{playlist.name}': {e}")
                continue

        self._save_results()

        logger.info("Analysis complete!")
        return True

    def _create_temperament_folders(self) -> Dict[Temperament, str]:
        """Create folders for each temperament category"""
        folders = {}

        for temperament in Temperament:
            folder_id = self.music_client.create_folder(temperament.value)
            folders[temperament] = folder_id
            logger.info(f"Folder for {temperament.value}: {folder_id}")

        return folders

    def _save_results(self):
        """Save classification results using shared utilities"""
        writer = ResultWriter("data/logs", "temperament")
        success = writer.save_results(self.results_log, "temperament_analysis_results.json")

        if success:
            ResultSummary.print_temperament_summary(self.results_log)


# ==================== MAIN FUNCTION ====================


def main():
    """Main entry point with interactive playlist selection"""
    print("\n" + "=" * 60)
    print("Music Playlist Temperament Analyzer")
    print("=" * 60)

    # Log temperament definitions
    log_temperament_info()

    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error("\nMissing required environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        logger.error("\nCreate a .env file with:")
        logger.error("  OPENAI_API_KEY=your_openai_api_key")
        return 1

    try:
        logger.info("Initializing clients...")
        logger.info("Starting Music Playlist Temperament Analyzer")

        # Initialize metadata client (optional)
        # Determine metadata provider based on available credentials
        metadata_client = None
        if os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET"):
            logger.info("Using Spotify for track metadata")
            metadata_client = SpotifyTrackMetadataClient()
        elif True:  # MusicBrainz is always available
            logger.info("Using MusicBrainz for track metadata")
            metadata_client = MusicBrainzTrackMetadataClient()
        else:
            logger.info("Using Mock database for track metadata (testing mode)")
            metadata_client = MockTrackMetadataClient()

        # Initialize music library client
        music_client = MusicAppClient()

        # Initialize LLM client (OpenAI is default)
        llm_client = OpenAILLMClient()
        logger.info("Using OpenAI GPT as LLM provider")

        # Authenticate with Music.app
        if not music_client.authenticate():
            print("\nFailed to authenticate with Music.app")
            return 1

        print("Fetching your playlists...")
        all_playlists = music_client.get_playlists(metadata_client=metadata_client)

        if not all_playlists:
            print("\nNo playlists found in Music.app")
            return 1

        # Let user select which playlists to analyze
        selected_playlists = PlaylistSelector.select_playlists_interactive(all_playlists)

        if not selected_playlists:
            print("\nNo playlists selected. Exiting.")
            return 0

        logger.info(f"Starting analysis of {len(selected_playlists)} selected playlists")

        # Create analyzer and run analysis
        analyzer = TemperamentAnalyzer(music_client, llm_client)
        success = analyzer.analyze_and_organize(playlists=selected_playlists)

        if success:
            print("\n" + "=" * 60)
            print("Analysis completed successfully!")
            print("=" * 60)
            print("\nResults saved to:")
            print("  - temperament_analysis_results.json")
            print("  - temperament_analyzer.log")
            print("\n")
            return 0
        else:
            print("\nAnalysis failed!")
            return 1

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
