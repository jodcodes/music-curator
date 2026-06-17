#!/usr/bin/env python3
"""
plsort - Playlist Organization and Classification (Feature: plsort).

LAYER: Application Layer - Feature Implementation
ROLE: Main orchestrator for playlist genre classification and organization
ARCHITECTURE: See src/README.md for full architecture

Categorizes playlists by genre (world, electronic, jazz, disco/funk/soul, rock, hip-hop)
using enhanced weighted scoring, artist lists, and metadata enrichment.

IMPLEMENTATION FLOW:
1. apple_music.py → Get playlist from Music.app
2. For each track in playlist:
   - playlist_classifier.py → Classify track genre
3. Aggregate track classifications to playlist genre
4. playlist_manager.py → Create genre folders
5. apple_music.py → Move playlist to genre folder
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from src.apple_music import AppleMusicInterface
from src.config import get_filtered_playlists, load_centralized_whitelist
from src.logger import setup_logger
from src.models import Playlist
from src.playlist_classifier import PlaylistClassifier
from src.playlist_manager import PlaylistManager
from src.playlist_utils import PlaylistSelector, PlaylistWhitelistFilter

logger = setup_logger(__name__)

# Project root is parent of src directory
PROJECT_ROOT = Path(__file__).parent.parent


def load_config_data() -> Dict[str, Any]:
    """Load configuration data from centralized config directory."""
    data_root = PROJECT_ROOT.parent if PROJECT_ROOT.name == "src" else PROJECT_ROOT
    config_dir = data_root / "data" / "config"

    config = {
        "genre_map_path": config_dir / "genre_map.json",
        "weights_path": config_dir / "weights.json",
        "artist_lists_dir": data_root / "data" / "artist_lists",
        "playlist_folders_path": config_dir / "playlist_folders.json",
    }

    # Verify all config files exist
    for name, path in config.items():
        if not path.exists():
            logger.error(f"Configuration file not found: {path}")

    return config


def get_apple_music_tracks_data(
    playlist_name: str, apple_music: AppleMusicInterface
) -> List[Dict[str, Any]]:
    """
    Get track data for a playlist from Apple Music.

    Args:
        playlist_name: Name of the playlist
        apple_music: Apple Music interface instance

    Returns:
        List of track metadata dictionaries
    """
    try:
        # Get all playlists to find the target one
        playlist_names = apple_music.get_playlist_names()

        if playlist_names is None:
            logger.error("Failed to retrieve playlist names from Apple Music")
            return []

        if playlist_name not in playlist_names:
            logger.warning(f"Playlist not found: {playlist_name}")
            return []

        # Get tracks for the playlist
        tracks = apple_music.get_playlist_tracks(playlist_name)

        if not tracks:
            logger.warning(f"No tracks found for playlist: {playlist_name}")
            return []

        logger.debug(f"Retrieved {len(tracks)} tracks for '{playlist_name}'")
        return tracks

    except Exception as e:
        logger.error(f"Failed to get tracks for playlist '{playlist_name}': {e}")
        return []


def classify_single_playlist(
    playlist_name: str,
    classifier: PlaylistClassifier,
    apple_music: AppleMusicInterface,
    verbose: bool = False,
) -> tuple[Optional[str], Dict[str, Any]]:
    """
    Classify a single playlist.

    Args:
        playlist_name: Name of the playlist to classify
        classifier: Playlist classifier instance
        apple_music: Apple Music interface instance
        verbose: Enable verbose logging

    Returns:
        Tuple of (assigned_genre, classification_details)
    """
    logger.info(f"Classifying playlist: {playlist_name}")

    # Get track data from Apple Music
    tracks = get_apple_music_tracks_data(playlist_name, apple_music)

    if not tracks:
        return None, {"error": "No tracks found", "playlist_name": playlist_name}

    # Classify the playlist
    assigned_genre, classification_details = classifier.classify_playlist(tracks, playlist_name)

    if verbose:
        print(f"\n" + "=" * 70)
        print(f"CLASSIFICATION DETAILS: {playlist_name}")
        print("=" * 70)
        print(f"Tracks analyzed: {len(tracks)}")
        print(f"Assigned genre: {assigned_genre or 'UNCLASSIFIED'}")
        print(f"Classification method: {classification_details.get('method', 'unknown')}")
        print(f"Confidence: {classification_details.get('confidence', 0):.2f}")
        print(f"Reason: {classification_details.get('reason', 'N/A')}")

        if "scores" in classification_details:
            print("\nGenre Scores:")
            for genre, score in classification_details["scores"].items():
                print(f"  {genre:15s}: {score:.2f}")

        if "tfidf_scores" in classification_details:
            print("\nTF-IDF Fallback Scores:")
            for genre, score in classification_details["tfidf_scores"].items():
                print(f"  {genre:15s}: {score:.3f}")

    return assigned_genre, classification_details


def classify_multiple_playlists(
    playlist_names: List[str],
    classifier: PlaylistClassifier,
    apple_music: AppleMusicInterface,
    verbose: bool = False,
) -> Dict[str, tuple]:
    """
    Classify multiple playlists.

    Args:
        playlist_names: List of playlist names to classify
        classifier: Playlist classifier instance
        apple_music: Apple Music interface instance
        verbose: Enable verbose logging

    Returns:
        Dictionary mapping playlist names to (assigned_genre, classification_details) tuples
    """
    results = {}

    print(f"\n" + "=" * 70)
    print("PLAYLIST CLASSIFICATION")
    print("=" * 70)
    print(f"Classifying {len(playlist_names)} playlists...\n")

    for playlist_name in tqdm(playlist_names, desc="Classifying playlists", unit="playlist"):
        assigned_genre, details = classify_single_playlist(
            playlist_name, classifier, apple_music, verbose
        )
        results[playlist_name] = (assigned_genre, details)

        # Brief status update
        status = assigned_genre if assigned_genre else "unclassified"
        confidence = details.get("confidence", 0)
        print(f"  {playlist_name:40s} -> {status:15s} (confidence: {confidence:.2f})")

    return results


def organize_classified_playlists(
    classification_results: Dict[str, tuple],
    playlist_manager: PlaylistManager,
    dry_run: bool = True,
) -> Dict[str, bool]:
    """
    Organize classified playlists into folders.

    Args:
        classification_results: Results from playlist classification
        playlist_manager: Playlist manager instance
        dry_run: If True, only show what would be done

    Returns:
        Dictionary mapping playlist names to organization success status
    """
    # Filter out unclassified playlists and build assignments
    playlist_assignments = {}
    unclassified_playlists = []

    for playlist_name, (assigned_genre, details) in classification_results.items():
        if assigned_genre:
            playlist_assignments[playlist_name] = assigned_genre
        else:
            unclassified_playlists.append(playlist_name)

    print(f"\n" + "=" * 70)
    print("PLAYLIST ORGANIZATION")
    print("=" * 70)
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"Playlists to organize: {len(playlist_assignments)}")
    print(f"Unclassified playlists: {len(unclassified_playlists)}")
    print()

    # Show what will be done
    if playlist_assignments:
        print("Playlist assignments:")
        for playlist_name, genre in playlist_assignments.items():
            status = "[DRY-RUN]" if dry_run else "[EXECUTE]"
            print(f"  {status} {playlist_name:40s} -> {genre}")

    if unclassified_playlists:
        print(f"\nUnclassified playlists (will be skipped):")
        for playlist_name in unclassified_playlists:
            print(f"  - {playlist_name}")

    # Perform organization
    organization_results = {}

    if playlist_assignments:
        print(f"\n{'-'*70}")
        if dry_run:
            print("DRY-RUN: Simulating playlist organization...")
            # Simulate the organization
            for playlist_name in playlist_assignments:
                organization_results[playlist_name] = True
            print(f"DRY-RUN: Would organize {len(playlist_assignments)} playlists")
        else:
            print("Organizing playlists...")
            organization_results = playlist_manager.organize_playlists(playlist_assignments)

    # Add unclassified playlists to results (marked as not organized)
    for playlist_name in unclassified_playlists:
        organization_results[playlist_name] = False

    return organization_results


def get_user_playlist_selection(
    playlist_names: List[str], whitelist_only: bool = False
) -> Optional[List[str]]:
    """
    Get playlist selection from user via interactive menu.

    Args:
        playlist_names: List of available playlist names
        whitelist_only: If True, show mode indicator

    Returns:
        List of selected playlist names or None if cancelled
    """
    try:
        if not playlist_names:
            print("No playlists available for selection.")
            return None

        # Load whitelist configuration
        whitelist_enabled, whitelist = load_centralized_whitelist()

        # Show playlist selection menu
        print("\n" + "=" * 70)
        mode_text = (
            "WHITELIST-ONLY"
            if whitelist_only
            else (f"WHITELIST: {'ON' if whitelist_enabled else 'OFF'}")
        )
        print(f"PLAYLIST SELECTION ({mode_text})")
        print("=" * 70 + "\n")

        for idx, name in enumerate(playlist_names, 1):
            print(f"{idx:2d}. {name}")

        print("\n" + "-" * 70)
        print("Select playlists to classify:")
        print("  Enter numbers separated by commas (e.g., 1,3,5)")
        print("  Or 'all' to select all playlists")
        print("  Or 'q' to cancel")
        print("-" * 70)

        while True:
            user_input = input("\nYour selection: ").strip().lower()

            if user_input == "q":
                return None

            if user_input == "all":
                print(f"\nSelected all {len(playlist_names)} playlists")
                return playlist_names

            try:
                indices = [int(x.strip()) - 1 for x in user_input.split(",")]
                if any(idx < 0 or idx >= len(playlist_names) for idx in indices):
                    print(
                        f"Invalid selection. Please enter numbers between 1 and {len(playlist_names)}."
                    )
                    continue

                selected_names = [playlist_names[idx] for idx in indices]
                print(f"\nSelected {len(selected_names)} playlist(s):")
                for name in selected_names:
                    print(f"  - {name}")
                return selected_names
            except ValueError:
                print(
                    f"Invalid input. Please enter numbers (1-{len(playlist_names)}) separated by commas, 'all', or 'q'."
                )
                continue

    except Exception as e:
        logger.error(f"Failed to get playlist selection: {e}")
        print(f"ERROR: {e}")
        return None


def run_playlist_organization(
    dry_run: bool = False,
    verbose: bool = False,
    interactive: bool = True,
    playlist_names: Optional[List[str]] = None,
    ignore_whitelist: bool = False,
    select_from_whitelist: bool = False,
) -> int:
    """
    Main function to run playlist organization and classification.

    Args:
        dry_run: If True, only show what would be done
        verbose: Enable verbose logging
        interactive: If True, ask user which playlists to process
        playlist_names: Pre-selected playlist names (if provided, skips interactive selection)

    Returns:
        Exit code
    """
    # Platform guard: playlist organization only on macOS
    if not sys.platform.startswith("darwin"):
        error_msg = (
            "Playlist organization is only supported on macOS.\n"
            "Alternative: Use metadata enrichment with --folder option on other platforms."
        )
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        return 1

    logger.info("Starting playlist organization system...")

    # Load configuration
    config = load_config_data()

    # Initialize components
    try:
        logger.info("Initializing playlist classifier...")
        classifier = PlaylistClassifier(
            genre_map_path=str(config["genre_map_path"]),
            weights_path=str(config["weights_path"]),
            artist_lists_dir=str(config["artist_lists_dir"]),
        )

        logger.info("Initializing playlist manager...")
        playlist_manager = PlaylistManager(dry_run=dry_run)

        logger.info("Initializing Apple Music interface...")
        apple_music = AppleMusicInterface()

    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        return 1

    # Get playlists to process
    if playlist_names:
        selected_playlists = playlist_names
        logger.info(f"Processing {len(selected_playlists)} pre-selected playlists")
    elif select_from_whitelist:
        # Force interactive mode with whitelist only
        all_playlist_names = apple_music.get_playlist_names()
        if all_playlist_names is None:
            logger.error("Failed to retrieve playlists from Apple Music")
            print("❌ Failed to retrieve playlists from Apple Music")
            return 1

        whitelist_enabled, whitelist = load_centralized_whitelist()
        filtered_names = (
            [name for name in all_playlist_names if name in whitelist]
            if whitelist_enabled
            else all_playlist_names
        )
        selected_playlists = get_user_playlist_selection(filtered_names, whitelist_only=True)
        if not selected_playlists:
            print("No playlists selected. Exiting.")
            return 0
    elif interactive:
        all_playlist_names = apple_music.get_playlist_names()
        if all_playlist_names is None:
            logger.error("Failed to retrieve playlists from Apple Music")
            print("❌ Failed to retrieve playlists from Apple Music")
            return 1

        whitelist_enabled, whitelist = load_centralized_whitelist()
        filtered_names = (
            [name for name in all_playlist_names if name in whitelist]
            if whitelist_enabled
            else all_playlist_names
        )
        selected_playlists = get_user_playlist_selection(filtered_names, whitelist_only=False)
        if not selected_playlists:
            print("No playlists selected. Exiting.")
            return 0
    else:
        # Non-interactive mode - get all playlists and filter by whitelist
        try:
            all_playlist_names = apple_music.get_playlist_names()
            if all_playlist_names is None:
                logger.error("Failed to retrieve playlists from Apple Music")
                print("❌ Failed to retrieve playlists from Apple Music")
                return 1

            if ignore_whitelist:
                selected_playlists = all_playlist_names
                logger.info(
                    f"Non-interactive mode ignoring whitelist: processing all {len(selected_playlists)} playlists"
                )
                print(f"\nIgnoring whitelist: Processing all {len(selected_playlists)} playlists")
            else:
                selected_playlists = get_filtered_playlists(all_playlist_names)
                if selected_playlists is None:
                    logger.error("Failed to filter playlists")
                    return 1

                whitelist_enabled, whitelist = load_centralized_whitelist()

                if whitelist_enabled:
                    logger.info(
                        f"Non-interactive mode with whitelist: processing {len(selected_playlists)} "
                        f"whitelisted playlists out of {len(all_playlist_names)} total"
                    )
                    print(
                        f"\nWhitelist enabled: Processing {len(selected_playlists)} whitelisted playlists "
                        f"out of {len(all_playlist_names)} total playlists"
                    )
                else:
                    logger.info(
                        f"Non-interactive mode without whitelist: processing all {len(selected_playlists)} playlists"
                    )
                    print(
                        f"\nWhitelist disabled: Processing all {len(selected_playlists)} playlists"
                    )

        except Exception as e:
            logger.error(f"Failed to get playlists: {e}")
            return 1

    if not selected_playlists:
        print("No playlists to process.")
        return 0

    # Classify playlists
    try:
        classification_results = classify_multiple_playlists(
            selected_playlists, classifier, apple_music, verbose
        )
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return 1

    # Organize playlists
    try:
        organization_results = organize_classified_playlists(
            classification_results, playlist_manager, dry_run
        )
    except Exception as e:
        logger.error(f"Organization failed: {e}")
        return 1

    # Summary
    classified_count = sum(1 for genre, _ in classification_results.values() if genre)
    organized_count = sum(1 for success in organization_results.values() if success)

    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total playlists processed: {len(selected_playlists)}")
    print(f"Successfully classified: {classified_count}")
    print(f"Successfully organized: {organized_count}")
    print(f"Unclassified/skipped: {len(selected_playlists) - classified_count}")

    if dry_run:
        print("\n✓ DRY-RUN completed successfully!")
        print("  Re-run without --dry-run to execute the actual organization.")
    else:
        print("\n✓ Playlist organization completed!")

    return 0


def main(args=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="plsort - Playlist Organization and Classification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: show what would be done without modifying Apple Music",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging and detailed classification output",
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Non-interactive mode: process all whitelisted playlists (or all if whitelist disabled)",
    )

    parser.add_argument(
        "--playlist",
        type=str,
        action="append",
        help="Process specific playlist(s) by name (can be used multiple times)",
    )

    parser.add_argument(
        "--ignore-whitelist", action="store_true", help="Ignore whitelist and process all playlists"
    )

    parser.add_argument(
        "--show-whitelist",
        action="store_true",
        help="Show current whitelist configuration and exit",
    )

    parser.add_argument(
        "--select-from-whitelist",
        action="store_true",
        help="Interactive selection from whitelisted playlists only",
    )

    parsed_args = parser.parse_args(args)

    # Set logging level
    if parsed_args.verbose:
        logger.setLevel("DEBUG")

    # Handle whitelist display option
    if parsed_args.show_whitelist:
        try:
            whitelist_enabled, whitelist = load_centralized_whitelist()
            print(f"\nWhitelist Status: {'ENABLED' if whitelist_enabled else 'DISABLED'}")
            print(f"Whitelisted Playlists: {len(whitelist)}")
            if whitelist:
                print("\nWhitelisted playlists:")
                for playlist in sorted(whitelist):
                    print(f"  - {playlist}")
            else:
                print("No playlists in whitelist.")
            return 0
        except Exception as e:
            print(f"Error loading whitelist: {e}")
            return 1

    # Determine interactive mode and selection type
    interactive = not parsed_args.no_interactive and not parsed_args.select_from_whitelist

    # Use provided playlist names if specified
    playlist_names = parsed_args.playlist

    # Run playlist organization
    return run_playlist_organization(
        dry_run=parsed_args.dry_run,
        verbose=parsed_args.verbose,
        interactive=interactive,
        playlist_names=playlist_names,
        ignore_whitelist=parsed_args.ignore_whitelist,
        select_from_whitelist=parsed_args.select_from_whitelist,
    )


if __name__ == "__main__":
    sys.exit(main())
