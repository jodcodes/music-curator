"""
Configuration utilities for plMetaTemp subrepos.

Provides centralized access to configuration files and whitelists.
"""

import json
import logging
import os
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


def load_centralized_whitelist(enabled_by_default: bool = False) -> tuple[bool, Set[str]]:
    """
    Load the centralized whitelist configuration from project root.

    Returns:
        Tuple of (enabled, playlist_set)
        - enabled: Whether whitelisting is currently enabled
        - playlist_set: Set of whitelisted playlist names (empty if disabled)
    """
    try:
        # Path to centralized whitelist in data/config/
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Try multiple paths in case we're in different directories
        possible_paths = [
            os.path.join(current_dir, "..", "data", "config", "whitelist.json"),
            os.path.join(current_dir, "..", "data", "config", "playlist_whitelist.json"),
            "data/config/whitelist.json",
            "../data/config/whitelist.json",
            "../../data/config/whitelist.json",
        ]

        whitelist_path = None
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                whitelist_path = abs_path
                logger.debug(f"Found whitelist at: {whitelist_path}")
                break

        if not whitelist_path:
            logger.warning(f"Centralized whitelist not found. Checked paths: {possible_paths}")
            return enabled_by_default, set()

        with open(whitelist_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        enabled = config.get("enabled", enabled_by_default)
        playlists = set(config.get("playlists", []))

        logger.info(f"Loaded whitelist: enabled={enabled}, playlists={len(playlists)}")

        if enabled:
            return True, playlists
        else:
            return False, set()

    except Exception as e:
        logger.error(f"Failed to load centralized whitelist: {e}")
        return enabled_by_default, set()


def filter_playlists_by_whitelist(
    playlist_names: List[str], whitelist_enabled: bool, whitelist: Set[str]
) -> List[str]:
    """
    Filter playlist names based on whitelist settings.

    Args:
        playlist_names: List of all available playlists
        whitelist_enabled: Whether whitelist filtering is enabled
        whitelist: Set of whitelisted playlist names

    Returns:
        Filtered list of playlists to process
    """
    if not whitelist_enabled or not whitelist:
        # Whitelist disabled - return all playlists
        return playlist_names

    # Whitelist enabled - filter to whitelisted only
    filtered = [name for name in playlist_names if name in whitelist]
    logger.info(f"Filtered {len(playlist_names)} playlists to {len(filtered)} whitelisted")
    return filtered


def get_filtered_playlists(playlist_names: List[str]) -> List[str]:
    """
    Convenience function that loads whitelist and filters playlists in one call.

    This is the recommended way for modules to filter playlists:

    Usage:
        from src.config import get_filtered_playlists

        playlists = api.get_playlists()
        filtered = get_filtered_playlists(playlists)

        for pl in filtered:
            process(pl)

    Args:
        playlist_names: List of all available playlists

    Returns:
        Filtered list based on centralized whitelist configuration
    """
    enabled, whitelist = load_centralized_whitelist()
    return filter_playlists_by_whitelist(playlist_names, enabled, whitelist)
