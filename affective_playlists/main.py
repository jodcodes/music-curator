#!/usr/bin/env python3
"""
affective_playlists - Unified CLI Entry Point

Unified application that combines:
1. 4tempers - AI-based playlist temperament analysis
2. metad_enr - Metadata filling and enrichment
3. plsort - Playlist organization and classification

Usage:
    python main.py                    # Interactive menu
    python main.py --help             # Show help
    python main.py temperament        # Run temperament analysis
    python main.py enrich             # Run metadata enrichment
    python main.py organize           # Run playlist organization
    python main.py curate             # Preview Favourite Songs curation
"""

import sys
import os
import argparse

from src.logger import setup_logger
from src.apple_music import AppleMusicInterface
from src.normalizer import TextNormalizer
from src.config import load_centralized_whitelist
from src.cli_ui import (
    print_header,
    print_footer,
    success,
    error,
    warning,
    info,
    Menu,
    Box,
    Icon,
    Color,
    bold,
)

logger = setup_logger("affective_playlists")
IS_MACOS = sys.platform == "darwin"

# Import main modules
temperament_analyzer = None
metadata_fill = None
plsort_module = None  # type: ignore

try:
    from src.temperament_analyzer import TemperamentAnalyzer, MusicAppClient, OpenAILLMClient

    temperament_analyzer = sys.modules.get("src.temperament_analyzer")
except ImportError as e:
    logger.warning(f"Could not import temperament_analyzer: {e}")

try:
    from src.metadata_fill import MetadataFillCLI

    metadata_fill = sys.modules.get("src.metadata_fill")
except ImportError as e:
    logger.warning(f"Could not import metadata_fill: {e}")
except Exception as e:
    logger.error(f"Error importing metadata_fill: {e}")

try:
    import src.plsort as plsort_module  # type: ignore
except ImportError as e:
    logger.warning(f"Could not import plsort: {e}")


def validate_openai_api_key() -> bool:
    """Validate that OPENAI_API_KEY is configured.

    Returns:
        True if valid, False otherwise (and prints user-facing error).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(error("OPENAI_API_KEY is not configured."))
        print(info("Setup: Add to your .env file or set environment variable:"))
        print(info("  OPENAI_API_KEY=sk-your-actual-key"))
        print(info("Get a key from: https://platform.openai.com/api-keys"))
        logger.error("OPENAI_API_KEY missing at temperament analysis startup")
        return False
    return True


def require_macos(feature_name: str) -> bool:
    """Return False and print a user-facing error if the feature needs macOS."""
    if IS_MACOS:
        return True

    print(error(f"{feature_name} requires macOS and Music.app (AppleScript integration)."))
    print(info("Tip: On non-macOS, use metadata enrichment in Folder mode."))
    return False


def run_temperament_analysis(args=None):
    """Run 4tempers - AI temperament analysis."""
    print_header("🎭 Temperament Analysis", "AI-based Playlist Emotion Classification")

    if not require_macos("Temperament analysis"):
        return 1

    if not validate_openai_api_key():
        return 1

    try:
        print(info("Initializing clients..."))
        logger.debug("Initializing temperament analysis clients")

        # Initialize clients
        music_client = MusicAppClient()
        llm_client = OpenAILLMClient()

        # Authenticate
        print(info("Connecting to Music.app..."))
        if not music_client.authenticate():
            logger.error("Failed to authenticate with Music.app")
            print(error("Could not connect to Music.app"))
            return 1

        print(success("Connected to Music.app"))
        logger.info("Successfully authenticated with Music.app")

        # Run analysis
        print(info("Starting temperament analysis..."))
        analyzer = TemperamentAnalyzer(music_client, llm_client)
        analyzer.run()

        print_footer()
        return 0
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(error(f"Configuration error: {e}"))
        return 1
    except Exception as e:
        logger.error(f"Temperament analysis failed: {e}", exc_info=True)
        print(error(f"Analysis failed: {e}"))
        return 1


def run_metadata_enrichment(args=None):
    """Run metad_enr - metadata enrichment."""
    # Header is printed by MetadataFillCLI, but we show info here

    try:
        from src.metadata_fill import MetadataFillCLI
        import argparse

        # Check if whitelist is enabled
        whitelist_enabled, whitelist = load_centralized_whitelist()

        # Create interactive menu
        target_options = ["Playlist", "Folder"]
        target_choice = Menu.select("📁 What would you like to enrich?", target_options)

        cli = MetadataFillCLI()

        # Create args namespace
        args_ns = argparse.Namespace()
        args_ns.force = False
        args_ns.verbose = os.getenv("VERBOSE", "false").lower() == "true"

        if target_choice == 0:  # Playlist
            if not require_macos("Playlist enrichment"):
                return 1

            # Check if whitelist is enabled
            if whitelist_enabled and whitelist:
                print(info(f"Whitelist enabled with {len(whitelist)} playlists"))

                whitelist_list = sorted(list(whitelist))
                playlist_options = ["Enter playlist name manually"] + whitelist_list
                pl_choice = Menu.select("🎵 Choose a playlist", playlist_options)

                if pl_choice == 0:
                    playlist_name = Menu.input_text("Playlist name")
                else:
                    playlist_name = whitelist_list[pl_choice - 1]
            else:
                playlist_name = Menu.input_text("🎵 Playlist name")

            if not playlist_name:
                print(error("Playlist name required"))
                return 1
            args_ns.playlist = playlist_name
            args_ns.folder = None
        else:  # Folder
            folder_path = Menu.input_text("📁 Folder path or name")
            if not folder_path:
                print(error("Folder path required"))
                return 1
            args_ns.playlist = None
            args_ns.folder = folder_path

        exit_code = cli.run(args_ns)
        return exit_code

    except Exception as e:
        logger.error(f"Metadata enrichment failed: {e}")
        print(error(f"Enrichment failed: {e}"))
        import traceback

        traceback.print_exc()
        return 1


def run_playlist_organization(args=None):
    """Run plsort - playlist organization by genre."""
    print_header("📚 Playlist Organization", "Classify & Organize by Genre")

    if not require_macos("Playlist organization"):
        return 1

    try:
        if plsort_module is None:
            print(error("plsort module not available"))
            return 1

        # Check if whitelist is enabled
        whitelist_enabled, whitelist = load_centralized_whitelist()

        if whitelist_enabled:
            print(warning(f"Whitelist ENABLED with {len(whitelist)} playlists"))
        else:
            print(info("Whitelist disabled - all playlists will be processed"))

        print()
        print(warning("⚠️  This will ACTUALLY MOVE playlists in Apple Music!"))
        print()

        # Show dry-run warning
        if not Menu.confirm("Continue with playlist organization?", default=False):
            print(info("Organization cancelled"))
            return 0

        print(info("Starting playlist organization..."))

        # Run plsort with default settings (will actually move playlists)
        result = plsort_module.main(args=["--no-interactive"])

        print_footer()
        return result if result is not None else 0
    except Exception as e:
        logger.error(f"Playlist organization failed: {e}")
        print(error(f"Organization failed: {e}"))
        return 1


def run_curation(args=None):
    """Run curation preview/apply."""
    print_header("Curation", "Review playlist curation structure")

    if not require_macos("Curation"):
        return 1

    if args and getattr(args, "apply", False):
        print(
            error(
                "Full apply is locked for the CLI in this phase. "
                "Use the UI mini-test and queued workflow instead."
            )
        )
        return 1

    from src.curation_service import CurationService

    service = CurationService()

    if args and getattr(args, "smoke_test", False):
        result = service.run_fav_songs_smoke_test()
        if result.get("success"):
            print(success("Smoke test completed and cleaned up."))
            print(info(f"copied: {result.get('copied', 0)}"))
            print(info(f"duplicate_skipped: {result.get('duplicate_skipped', False)}"))
            print(info(f"leftovers: {result.get('leftovers', {})}"))
            return 0

        print(error(f"Smoke test failed: {result.get('error', 'Unknown error')}"))
        print(info(f"leftovers: {result.get('leftovers', {})}"))
        return 1

    scope = getattr(args, "scope", "fav_songs") if args else "fav_songs"
    if scope == "playlist_tempers":
        playlist_names = list(getattr(args, "playlist", None) or [])
        if not playlist_names:
            print(error("Use --playlist at least once for playlist_tempers scope."))
            return 1
        preview = service.preview_playlist_tempers(playlist_names)
        item_label = "Selected playlist tracks"
    else:
        preview = service.preview_fav_songs()
        item_label = "Favourite tracks"

    print(
        info(
            "Preview only - no changes written. "
            "Use the UI mini-test and queued workflow to apply changes."
        )
    )
    print(info(f"{item_label}: {preview['total_assignments']}"))
    print(info(f"Planned changes: {preview['total_changes']}"))
    if preview.get("total_skipped"):
        print(warning(f"Skipped tracks: {preview['total_skipped']}"))
    return 0


def show_interactive_menu():
    """Show interactive menu to select and run a feature."""
    print_header("🎵 affective_playlists", "Unified Music Library Organization")

    while True:
        try:
            features = [
                "🎭 Temperament Analysis - AI emotion classification",
                "📝 Metadata Enrichment - Fill missing metadata",
                "📚 Playlist Organization - Genre-based sorting",
            ]

            choice = Menu.select("Select a feature to run", features)

            if choice == 0:
                return run_temperament_analysis()
            elif choice == 1:
                return run_metadata_enrichment()
            elif choice == 2:
                return run_playlist_organization()
        except KeyboardInterrupt:
            print()
            if Menu.confirm("Exit affective_playlists?"):
                print(success("Goodbye!"))
                return 0


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="affective_playlists",
        description="Unified music analysis and organization tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="feature", metavar="feature")

    def add_feature_parser(name, help_text):
        feature_parser = subparsers.add_parser(name, help=help_text)
        feature_parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            default=argparse.SUPPRESS,
            help=argparse.SUPPRESS,
        )
        feature_parser.add_argument(
            "--version",
            action="version",
            version="%(prog)s 1.0.0",
            help=argparse.SUPPRESS,
        )
        return feature_parser

    add_feature_parser("temperament", "Run temperament analysis")
    add_feature_parser("enrich", "Run metadata enrichment")
    add_feature_parser("organize", "Run playlist organization")

    curate_parser = add_feature_parser("curate", "Preview/apply Favourite Songs curation")
    curate_parser.add_argument(
        "--scope",
        choices=["fav_songs", "playlist_tempers"],
        default="fav_songs",
        help="Curation scope",
    )
    curate_parser.add_argument(
        "--playlist",
        action="append",
        help="Source playlist name for playlist_tempers scope. Repeatable.",
    )
    curate_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply Favourite Songs curation changes",
    )
    curate_parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run reversible one-track curation smoke test only",
    )

    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel("DEBUG")

    # Run selected feature
    if args.feature == "temperament":
        return run_temperament_analysis()
    elif args.feature == "enrich":
        return run_metadata_enrichment()
    elif args.feature == "organize":
        return run_playlist_organization()
    elif args.feature == "curate":
        return run_curation(args)
    else:
        # Show interactive menu if no feature specified
        return show_interactive_menu()


if __name__ == "__main__":
    sys.exit(main())
