"""
Shared playlist utilities used by all three features (4tempers, metad_enr, plsort).

Consolidates:
- Interactive playlist selection
- Fuzzy matching and playlist lookup
- Whitelist filtering
- Playlist fetching and caching

Previously scattered across temperament_analyzer.py, metadata_fill.py, and plsort.py.
"""

import difflib
import logging
import os
import re
import subprocess
from typing import Dict, List, Optional, Set, Tuple

from src.logger import setup_logger
from src.models import Playlist, Track

logger = setup_logger(__name__)


class PlaylistSelector:
    """Interactive CLI menu for playlist selection and filtering."""

    @staticmethod
    def select_playlists_interactive(playlists: List[Playlist]) -> List[Playlist]:
        """Interactive CLI menu to select which playlists to process.

        Args:
            playlists: List of available playlists

        Returns:
            List of selected playlists

        Raises:
            ValueError: If playlists list is empty
        """
        if not playlists:
            raise ValueError("No playlists available")

        print("\n" + "=" * 60)
        print("AVAILABLE PLAYLISTS")
        print("=" * 60)

        # Display playlists with numbering
        for idx, playlist in enumerate(playlists, 1):
            track_count = len(playlist.tracks)
            print(f"{idx:2d}. {playlist.name:40s} ({track_count:3d} tracks)")

        print("\n" + "-" * 60)
        print("Select playlists to process:")
        print("  Enter numbers separated by commas (e.g., 1,3,5)")
        print("  Or 'all' to process all playlists")
        print("  Or 'q' to quit")
        print("-" * 60)

        while True:
            try:
                user_input = input("\nYour selection: ").strip().lower()

                # Handle quit
                if user_input == "q":
                    logger.info("User cancelled playlist selection")
                    return []

                # Handle all playlists
                if user_input == "all":
                    logger.info(f"User selected all {len(playlists)} playlists")
                    return playlists

                # Parse number selection
                selected_indices = [int(x.strip()) - 1 for x in user_input.split(",")]

                # Validate indices
                if any(idx < 0 or idx >= len(playlists) for idx in selected_indices):
                    print(
                        f"Invalid selection. Please enter numbers between 1 and {len(playlists)}."
                    )
                    continue

                # Get selected playlists
                selected = [playlists[idx] for idx in selected_indices]
                logger.info(f"User selected {len(selected)} playlist(s)")

                print(f"\nSelected {len(selected)} playlist(s):")
                for playlist in selected:
                    print(f"  - {playlist.name} ({len(playlist.tracks)} tracks)")

                return selected

            except ValueError:
                print(
                    f"Invalid input. Please enter numbers (1-{len(playlists)}) separated by commas, 'all', or 'q'."
                )
                continue


class PlaylistFuzzyMatcher:
    """Fuzzy matching for playlist names (case-insensitive, handles typos)."""

    @staticmethod
    def find_playlist_by_name(
        playlist_name: str, playlist_ids: Dict[str, str], cutoff: float = 0.8
    ) -> Optional[str]:
        """Fuzzy match playlist name to persistent ID.

        Handles:
        - Case-insensitive matching
        - Partial matches (>80% similarity)
        - Typos and variations

        Args:
            playlist_name: Name to search for
            playlist_ids: Dictionary mapping names to hex IDs
            cutoff: Similarity threshold (0.0-1.0)

        Returns:
            Playlist ID if found, None otherwise
        """
        if not playlist_ids:
            logger.warning("No playlists available for fuzzy matching")
            return None

        # Exact case-insensitive match (fastest)
        for name in playlist_ids.keys():
            if name.lower() == playlist_name.lower():
                logger.debug(f"Fuzzy match (exact): {playlist_name} -> {name}")
                return playlist_ids[name]

        # Fuzzy string matching using difflib
        playlist_list = list(playlist_ids.keys())
        matches = difflib.get_close_matches(
            playlist_name.lower(), [n.lower() for n in playlist_list], n=1, cutoff=cutoff
        )

        if matches:
            # Find original name with correct casing
            idx = [n.lower() for n in playlist_list].index(matches[0])
            original_name = playlist_list[idx]
            logger.debug(f"Fuzzy match (similarity): {playlist_name} -> {original_name}")
            return playlist_ids[original_name]

        logger.warning(f"No fuzzy match found for: {playlist_name}")
        return None

    @staticmethod
    def find_closest_match(playlist_name: str, available_names: List[str]) -> Optional[str]:
        """Find closest matching playlist name from list.

        Args:
            playlist_name: Name to search for
            available_names: List of available names

        Returns:
            Closest matching name or None if no good match
        """
        if not available_names:
            return None

        # Exact case-insensitive match
        for name in available_names:
            if name.lower() == playlist_name.lower():
                return name

        # Fuzzy match
        matches = difflib.get_close_matches(
            playlist_name.lower(), [n.lower() for n in available_names], n=1, cutoff=0.8
        )

        if matches:
            idx = [n.lower() for n in available_names].index(matches[0])
            return available_names[idx]

        return None


class PlaylistIDFetcher:
    """Fetch persistent IDs for playlists from Apple Music."""

    def __init__(self, scripts_dir: str = "scripts"):
        """Initialize ID fetcher.

        Args:
            scripts_dir: Directory containing AppleScript templates
        """
        self.scripts_dir = scripts_dir
        self._cache: Optional[Dict[str, str]] = None

    def get_all_playlist_ids(self, use_cache: bool = True) -> Dict[str, str]:
        """Get all user playlists with their persistent hex IDs.

        Args:
            use_cache: Use cached results if available

        Returns:
            Dictionary mapping playlist names to hex IDs
        """
        if use_cache and self._cache is not None:
            return self._cache

        try:
            script_path = os.path.join(self.scripts_dir, "get_ids_playlists.applescript")
            result = subprocess.run(
                ["osascript", script_path], capture_output=True, text=True, timeout=30
            )

            if not result.stdout:
                logger.error("Failed to get playlist IDs from AppleScript")
                return {}

            playlists = self._parse_playlist_ids(result.stdout)
            self._cache = playlists
            return playlists

        except subprocess.TimeoutExpired:
            logger.error("AppleScript timeout while fetching playlist IDs")
            return {}
        except Exception as e:
            logger.error(f"Error getting playlist IDs: {e}")
            return {}

    def clear_cache(self):
        """Clear the cached playlist IDs."""
        self._cache = None

    @staticmethod
    def _parse_playlist_ids(output: str) -> Dict[str, str]:
        """Parse AppleScript output to extract playlist names and hex IDs.

        Args:
            output: Raw AppleScript output

        Returns:
            Dictionary mapping playlist names to hex IDs
        """
        playlists = {}

        # Find all hex IDs (16 hex digits - exactly what Music.app uses)
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


class PlaylistWhitelistFilter:
    """Handle whitelist filtering for playlist processing."""

    @staticmethod
    def load_whitelist() -> Tuple[bool, Set[str]]:
        """Load centralized whitelist configuration.

        Returns:
            Tuple of (enabled: bool, whitelist_set: Set[str])
        """
        try:
            from src.config import load_centralized_whitelist

            return load_centralized_whitelist(enabled_by_default=False)
        except ImportError:
            logger.warning("Could not import config module for whitelist")
            return False, set()

    @staticmethod
    def filter_playlists(
        all_playlists: List[Playlist], whitelist_enabled: bool, whitelist: Optional[Set[str]] = None
    ) -> List[Playlist]:
        """Filter playlists based on whitelist configuration.

        Args:
            all_playlists: All available playlists
            whitelist_enabled: Whether whitelist filtering is enabled
            whitelist: Set of playlist names to allow (if enabled)

        Returns:
            Filtered list of playlists to process
        """
        if not whitelist_enabled:
            logger.debug(f"Whitelist disabled - processing all {len(all_playlists)} playlists")
            return all_playlists

        if not whitelist:
            logger.warning("Whitelist enabled but empty - no playlists will be processed")
            return []

        # Filter playlists by whitelist
        filtered = [p for p in all_playlists if p.name.lower() in {w.lower() for w in whitelist}]

        logger.info(f"Whitelist filtering: {len(all_playlists)} -> {len(filtered)} playlists")
        return filtered


# Re-export for convenience
__all__ = [
    "PlaylistSelector",
    "PlaylistFuzzyMatcher",
    "PlaylistIDFetcher",
    "PlaylistWhitelistFilter",
]
