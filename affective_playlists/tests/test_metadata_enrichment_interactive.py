#!/usr/bin/env python3
"""
Test script for metadata enrichment on a single playlist.

Usage:
    python run_metadata_enrichment_test.py                 # Interactive mode
    python run_metadata_enrichment_test.py "Playlist Name" # Direct playlist

This script demonstrates the complete metadata enrichment workflow:
1. Get list of available playlists
2. Let user select a playlist (or pass directly)
3. Enrich metadata for tracks in the playlist
4. Display results and statistics
"""

import argparse
import os
import sys
from pathlib import Path

from src.config import load_centralized_whitelist
from src.logger import setup_logger
from src.metadata_fill import MetadataFillCLI, MetadataFiller


def get_available_playlists() -> dict:
    """Get list of available playlists."""
    logger = setup_logger("metadata_test")

    print("\n" + "=" * 70)
    print("METADATA ENRICHMENT TEST - Getting Available Playlists")
    print("=" * 70 + "\n")

    try:
        filler = MetadataFiller(logger)
        playlists = filler._get_playlist_ids()

        if not playlists:
            print("ERROR: No playlists found in Apple Music")
            return {}

        print(f"Found {len(playlists)} playlists:\n")
        for i, (name, pid) in enumerate(sorted(playlists.items()), 1):
            print(f"  {i:2d}. {name}")

        return playlists
    except Exception as e:
        print(f"ERROR: Failed to get playlists: {e}")
        import traceback

        traceback.print_exc()
        return {}


def select_playlist(playlists: dict) -> str:
    """Interactive playlist selection."""
    if not playlists:
        return None

    playlist_list = sorted(list(playlists.keys()))

    print("\n" + "-" * 70)
    print("SELECT PLAYLIST FOR ENRICHMENT")
    print("-" * 70)
    print("\nChoose a playlist:")
    print("  0. Exit")

    for i, name in enumerate(playlist_list, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input("\nEnter playlist number: ").strip()
            choice_num = int(choice)

            if choice_num == 0:
                print("\nExiting...")
                return None
            elif 1 <= choice_num <= len(playlist_list):
                selected = playlist_list[choice_num - 1]
                print(f"\n✓ Selected: {selected}")
                return selected
            else:
                print(f"ERROR: Please enter 0-{len(playlist_list)}")
        except ValueError:
            print("ERROR: Please enter a valid number")


def run_metadata_enrichment(playlist_name: str, force: bool = False) -> bool:
    """Run metadata enrichment for a playlist."""
    logger = setup_logger("metadata_test")

    print("\n" + "=" * 70)
    print(f"METADATA ENRICHMENT - {playlist_name}")
    print("=" * 70 + "\n")

    try:
        # Create MetadataFillCLI instance
        cli = MetadataFillCLI()

        # Create args namespace matching CLI expectations
        args = argparse.Namespace(playlist=playlist_name, folder=None, force=force, verbose=False)

        # Run enrichment
        result = cli.run(args)

        return result == 0

    except Exception as e:
        print(f"ERROR: Metadata enrichment failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def print_test_summary(playlist_name: str, success: bool):
    """Print test summary."""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Playlist:  {playlist_name}")
    print(f"Status:    {'✓ SUCCESS' if success else '✗ FAILED'}")
    print("=" * 70 + "\n")


def main():
    """Main test entry point."""
    parser = argparse.ArgumentParser(description="Test metadata enrichment for a single playlist")
    parser.add_argument(
        "playlist", nargs="?", help="Playlist name (if not provided, shows interactive selection)"
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite existing metadata")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Get available playlists
    playlists = get_available_playlists()

    if not playlists:
        print("\nERROR: Could not retrieve playlists from Apple Music")
        return 1

    # Determine which playlist to use
    if args.playlist:
        # Direct playlist name provided
        if args.playlist not in playlists:
            print(f"\nERROR: Playlist '{args.playlist}' not found")
            print(f"Available playlists: {', '.join(sorted(playlists.keys())[:5])}...")
            return 1
        playlist_name = args.playlist
    else:
        # Interactive selection
        playlist_name = select_playlist(playlists)
        if not playlist_name:
            return 0

    # Run enrichment
    success = run_metadata_enrichment(playlist_name, force=args.force)

    # Print summary
    print_test_summary(playlist_name, success)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
