#!/usr/bin/env python3
"""
curator - Unified CLI Entry Point

Apple Music management tool combining:
1. mood     - AI-based playlist mood/temperament analysis
2. enrich   - Metadata filling from music databases
3. organize - Playlist organization and classification
4. curate   - Favourite Songs curation
5. scan/status/dedupe/export/history - Library observability

Usage:
    curator                   # Interactive menu
    curator --help            # Show help
    curator mood              # Run mood analysis
    curator enrich            # Run metadata enrichment
    curator organize          # Run playlist organization
    curator curate            # Preview Favourite Songs curation
    curator scan              # Scan Apple Music library
    curator status            # Show current state
    curator jobs              # Manage background jobs
"""

import sys
import os
import argparse

from src.logger import setup_logger
from src.apple_music import AppleMusicInterface
from src.job_store import get_job_store
from src.library_state_store import LibraryStateStore
from src.music_tools import MUSIC_TOOLS, format_music_tool_catalog, list_music_tools, run_music_tool
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

logger = setup_logger("curator")
IS_MACOS = sys.platform == "darwin"

# Import main modules
mood_analyzer = None
metadata_fill = None
plsort_module = None  # type: ignore

try:
    from src.mood_analyzer import TemperamentAnalyzer, MusicAppClient, OpenAILLMClient

    mood_analyzer = sys.modules.get("src.mood_analyzer")
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


def run_mood_analysis(args=None):
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

        if args and (
            getattr(args, "playlist", None)
            or getattr(args, "folder", None)
            or getattr(args, "library", False)
        ):
            if (getattr(args, "playlist", None) or getattr(args, "library", False)) and not require_macos("Apple Music enrichment"):
                return 1
            # Map new --library flag to legacy all_playlists for MetadataFillCLI
            if getattr(args, "library", False):
                args.all_playlists = True
                args.all_songs = False
            else:
                args.all_playlists = False
                args.all_songs = False
            cli = MetadataFillCLI()
            return cli.run(args)

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

    scope = getattr(args, "scope", "fav_songs") if args else "fav_songs"

    if args and getattr(args, "apply", False) and scope not in {"playlist_tempers", "fav_songs"}:
        print(error(f"Unsupported apply scope: {scope}"))
        return 1

    if args and getattr(args, "smoke_test", False):
        from src.curation_service import CurationService

        service = CurationService()
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

    if scope == "playlist_tempers":
        playlist_names = getattr(args, "playlist", None)
        if getattr(args, "apply", False):
            if not getattr(args, "yes", False):
                print(
                    error(
                        "Full apply is locked. Use the UI mini-test or --yes with --apply for playlist_tempers."
                    )
                )
                return 1
            from src.curation_service import CurationService

            service = CurationService()
            result = service.apply_playlist_tempers(playlist_names, confirmed=True)
            print(success(f"Applied changes: {result.get('applied', 0)}"))
            if result.get("failed"):
                print(error(f"Failed changes: {result.get('failed', 0)}"))
                return 1
            return 0
        from src.curation_service import CurationService

        service = CurationService()
        preview = service.preview_playlist_tempers(playlist_names)
        item_label = "Selected playlist tracks"
    else:
        if getattr(args, "apply", False):
            if not getattr(args, "yes", False):
                print(
                    error(
                        "Full apply is locked. Use the UI mini-test or --yes with --apply for fav_songs."
                    )
                )
                return 1
            from src.curation_service import CurationService

            service = CurationService()
            batch_size = getattr(args, "batch_size", None)
            if getattr(args, "bulk", False):
                result = service.apply_fav_songs_bulk(
                    confirmed=True,
                    max_tracks=getattr(args, "limit", None),
                    offset=getattr(args, "offset", 0) or 0,
                )
                print(success(f"Bulk applied: {result.get('stdout', '')}"))
            elif batch_size:
                result = service.apply_fav_songs_batched(
                    confirmed=True,
                    batch_size=batch_size,
                    max_tracks=getattr(args, "limit", None),
                    offset=getattr(args, "offset", 0) or 0,
                )
                print(success(f"Applied changes: {result.get('applied', 0)}"))
                print(info(f"Processed tracks: {result.get('processed_tracks', 0)}"))
            else:
                result = service.apply_fav_songs(
                    confirmed=True,
                    max_tracks=getattr(args, "limit", None),
                    offset=getattr(args, "offset", 0) or 0,
                )
                print(success(f"Applied changes: {result.get('applied', 0)}"))
            if result.get("failed"):
                print(error(f"Failed changes: {result.get('failed', 0)}"))
                return 1
            return 0
        from src.curation_service import CurationService

        service = CurationService()
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


def run_scan(args=None):
    """Scan Apple Music library and show summary stats."""
    import json

    if not require_macos("scan"):
        return 1
    print_header("🔍 Library Scan", "Apple Music library overview")
    try:
        am = AppleMusicInterface()
        playlists = am.get_playlists() or []
        all_tracks = am.get_all_tracks() or []
        print(info(f"Playlists:  {len(playlists)}"))
        print(info(f"Tracks:     {len(all_tracks)}"))

        # Artist/album quick stats
        artists: set = set()
        albums: set = set()
        missing_meta = 0
        for t in all_tracks:
            if t.get("artist"):
                artists.add(t["artist"])
            if t.get("album"):
                albums.add(t["album"])
            if not t.get("genre") or not t.get("year"):
                missing_meta += 1

        print(info(f"Artists:    {len(artists)}"))
        print(info(f"Albums:     {len(albums)}"))
        print(info(f"Missing genre/year: {missing_meta} tracks"))

        # Persist as a library run
        store = LibraryStateStore()
        run = store.create_run(
            "scan",
            target="library",
            payload={"playlists": len(playlists), "tracks": len(all_tracks)},
        )
        store.finish_run(
            run.id,
            status="completed",
            processed_items=len(all_tracks),
            details={"artists": len(artists), "albums": len(albums), "missing_meta": missing_meta},
        )
        print(success(f"Scan recorded as run {run.id}"))
    except Exception as e:
        print(error(f"Scan failed: {e}"))
        return 1
    print_footer()
    return 0


def show_status(args=None):
    """Show current state: running jobs, last run, dedupe stats."""
    from src.db import get_session, LibraryRun, TrackDedupHistory

    print_header("📊 Status", "Current library state")
    try:
        session = get_session()
        # Last 3 runs
        runs = session.query(LibraryRun).order_by(LibraryRun.created_at.desc()).limit(3).all()
        if runs:
            print(info("Recent runs:"))
            for r in runs:
                ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "?"
                print(f"  {ts}  {r.run_type:<12} {r.status:<12} processed={r.processed_items}")
        else:
            print(info("No runs yet."))

        # Dedupe stats per scope
        from sqlalchemy import func
        scope_counts = (
            session.query(TrackDedupHistory.scope, func.count().label("n"))
            .group_by(TrackDedupHistory.scope)
            .all()
        )
        if scope_counts:
            print(info("Dedupe history:"))
            for scope, n in scope_counts:
                print(f"  {scope:<30} {n} tracks seen")

        # Running background jobs
        job_store = get_job_store()
        _, running = job_store.list_jobs(limit=5, status="running")
        if running:
            print(info(f"Running jobs: {len(running)}"))
            for j in running:
                print(f"  {j.id}  {j.type}  {j.progress}%")
        else:
            print(info("No running jobs."))
        session.close()
    except Exception as e:
        print(error(f"Status check failed: {e}"))
        return 1
    print_footer()
    return 0


def run_dedupe(args=None):
    """Show or run deduplication analysis across playlists."""
    from src.deduplication import build_track_key

    dry_run = not getattr(args, "apply", False)
    scope = getattr(args, "scope", "dedupe") if args else "dedupe"
    print_header("🗂 Deduplication", "Cross-playlist duplicate analysis")

    if not require_macos("dedupe"):
        return 1

    try:
        am = AppleMusicInterface()
        playlists = am.get_playlists() or []
        seen: dict = {}
        dupes = []
        for pl in playlists:
            tracks = am.get_playlist_tracks(pl.get("name", "")) or []
            for t in tracks:
                key = build_track_key(
                    artist=t.get("artist", ""),
                    title=t.get("name", t.get("title", "")),
                    album=t.get("album"),
                )
                if key in seen:
                    dupes.append({
                        "track": t.get("name", "?"),
                        "artist": t.get("artist", "?"),
                        "in": pl.get("name", "?"),
                        "also_in": seen[key],
                    })
                else:
                    seen[key] = pl.get("name", "?")

        print(info(f"Playlists scanned: {len(playlists)}"))
        print(info(f"Unique tracks:     {len(seen)}"))
        print(info(f"Duplicates found:  {len(dupes)}"))
        if dupes:
            for d in dupes[:20]:
                print(f"  {d['artist']} – {d['track']}  [{d['in']}] also in [{d['also_in']}]")
            if len(dupes) > 20:
                print(info(f"  ... and {len(dupes) - 20} more"))

        store = LibraryStateStore()
        run = store.create_run("dedupe", target=scope, payload={"dry_run": dry_run})
        store.finish_run(
            run.id,
            status="completed",
            processed_items=len(seen),
            details={"duplicates": len(dupes)},
        )
        if dry_run:
            print(info("Dry-run mode — nothing removed. Pass --apply to remove duplicates."))
    except Exception as e:
        print(error(f"Dedupe failed: {e}"))
        return 1
    print_footer()
    return 0


def run_export(args=None):
    """Export library state (runs, dedupe history, job summary) to JSON."""
    import json

    out_path = getattr(args, "output", "library_export.json") if args else "library_export.json"
    limit = getattr(args, "limit", 100) if args else 100
    print_header("📦 Export", f"Exporting library state to {out_path}")

    try:
        store = LibraryStateStore()
        job_store = get_job_store()

        runs = [r.to_dict() for r in store.list_runs(limit=limit)]
        tracks = [
            {
                "scope": t.scope,
                "track_key": t.track_key,
                "artist": t.artist,
                "title": t.title,
                "album": t.album,
                "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
                "skip_reason": t.skip_reason,
            }
            for t in store.list_tracks(limit=limit)
        ]
        total_jobs, jobs = job_store.list_jobs(limit=limit)

        payload = {
            "runs": runs,
            "dedupe_history": tracks,
            "jobs": [j.to_dict() for j in jobs],
            "summary": {
                "total_runs": len(runs),
                "total_dedupe_entries": len(tracks),
                "total_jobs": total_jobs,
            },
        }
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(success(f"Exported {len(runs)} runs, {len(tracks)} track entries, {total_jobs} jobs"))
        print(info(f"Written to: {out_path}"))
    except Exception as e:
        print(error(f"Export failed: {e}"))
        return 1
    print_footer()
    return 0


def run_music_tools(args=None):
    """Run the bundled maintenance scripts."""
    tool_name = getattr(args, "tool", None) if args else None
    tool_args = getattr(args, "tool_args", None) if args else None
    if not args or (tool_name is None and not getattr(args, "list", False)):
        print_header("🛠 Music Tools", "Bundled maintenance scripts")
        tools = list_music_tools()
        choices = [f"{tool.name}: {tool.description}" for tool in tools]
        choice = Menu.select("Select a maintenance script", choices)
        selected = tools[choice].name
        result = run_music_tool(selected, [])
        if result.stdout:
            print(result.stdout.rstrip())
        if result.returncode != 0 and result.stderr:
            print(error(result.stderr.rstrip()))
        print_footer()
        return result.returncode

    if getattr(args, "list", False):
        print_header("🛠 Music Tools", "Bundled maintenance scripts")
        for line in format_music_tool_catalog():
            print(line)
        print_footer()
        return 0

    if not tool_name:
        print_header("🛠 Music Tools", "Bundled maintenance scripts")
        for line in format_music_tool_catalog():
            print(line)
        print_footer()
        return 0

    try:
        result = run_music_tool(tool_name, tool_args or [])
    except KeyError as e:
        print(error(str(e)))
        return 1
    except FileNotFoundError as e:
        print(error(f"Unable to launch music tool '{tool_name}': {e}"))
        return 1

    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0 and result.stderr:
        print(error(result.stderr.rstrip()))
    return result.returncode


def show_job_history(args=None):
    """Show recent background jobs."""
    limit = getattr(args, "limit", 10) if args else 10
    status = getattr(args, "status", None) if args else None
    run_store = LibraryStateStore()
    job_store = get_job_store()

    runs = run_store.list_runs(limit=limit)
    total_jobs, jobs = job_store.list_jobs(limit=limit, status=status)

    print_header("🕘 Job History", "Recent enrichment and curation runs")
    if not runs and not jobs:
        print(info("No history found"))
        print_footer()
        return 0

    if runs:
        print(info("Library runs:"))
        for run in runs:
            created = run.created_at.isoformat() if run.created_at else "unknown"
            print(
                f"- {run.id} | {run.run_type} | {run.status} | "
                f"processed={run.processed_items} skipped={run.skipped_items} | {created}"
            )

    if jobs:
        print(info(f"Jobs: showing {len(jobs)} of {total_jobs}"))
        for job in jobs:
            created = job.created_at.isoformat() if job.created_at else "unknown"
            progress = f"{job.progress}%" if job.progress is not None else "n/a"
            print(f"- {job.id} | {job.type} | {job.status} | {progress} | {created}")

    print_footer()
    return 0


def show_interactive_menu():
    """Show interactive menu to select and run a feature."""
    print_header("🎵 curator", "Unified Music Library Organization")

    while True:
        try:
            features = [
                "🎭 Mood Analysis    - AI emotion classification of playlists",
                "📝 Enrich Metadata  - Fill missing metadata from music databases",
                "📚 Organize         - Genre-based playlist sorting",
                "🔍 Scan Library     - Sync and show library stats",
                "📊 Status           - Current jobs and run state",
                "🗂  Deduplicate      - Cross-playlist duplicate analysis",
                "📦 Export           - Export state to JSON",
                "🛠  Music Tools      - Playlist cleanup and genre maintenance",
                "🕘 Job History      - Review recent runs",
            ]

            choice = Menu.select("Select a feature to run", features)

            if choice == 0:
                return run_mood_analysis()
            elif choice == 1:
                return run_metadata_enrichment()
            elif choice == 2:
                return run_playlist_organization()
            elif choice == 3:
                return run_scan()
            elif choice == 4:
                return show_status()
            elif choice == 5:
                return run_dedupe()
            elif choice == 6:
                return run_export()
            elif choice == 7:
                return run_music_tools()
            elif choice == 8:
                return show_job_history()
        except KeyboardInterrupt:
            print()
            if Menu.confirm("Exit curator?"):
                print(success("Goodbye!"))
                return 0


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="curator",
        description="curator — Apple Music management: enrich, mood, organize, curate",
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

    mood_parser = add_feature_parser("mood", "Analyse playlist mood via AI")
    mood_scope = mood_parser.add_mutually_exclusive_group()
    mood_scope.add_argument("--library", action="store_true", help="Analyse mood for all playlists")
    mood_scope.add_argument("--playlist", help="Apple Music playlist name to analyse")
    mood_parser.add_argument("--apply", action="store_true", help="Move playlists to mood folders")

    enrich_parser = add_feature_parser("enrich", "Fill metadata from music databases")
    enrich_scope = enrich_parser.add_mutually_exclusive_group()
    enrich_scope.add_argument("--library", action="store_true", help="Enrich every song in the library")
    enrich_scope.add_argument("--playlist", help="Apple Music playlist name to enrich")
    enrich_scope.add_argument("--folder", help="Local audio folder path or name to enrich")
    enrich_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing metadata fields"
    )
    add_feature_parser("organize", "Run playlist organization")

    scan_parser = add_feature_parser("scan", "Scan Apple Music library and show stats")
    _ = scan_parser  # no extra args needed yet

    status_parser = add_feature_parser("status", "Show current state: jobs, last run, dedupe stats")
    _ = status_parser

    dedupe_parser = add_feature_parser("dedupe", "Analyse duplicate tracks across playlists")
    dedupe_parser.add_argument(
        "--apply", action="store_true", help="Remove duplicates (default: dry-run)"
    )
    dedupe_parser.add_argument("--scope", default="dedupe", help="Dedupe scope label")

    export_parser = add_feature_parser("export", "Export library state to JSON")
    export_parser.add_argument(
        "--output", default="library_export.json", help="Output file path"
    )
    export_parser.add_argument(
        "--limit", type=int, default=100, help="Max records per category"
    )

    tools_parser = add_feature_parser("tools", "Run bundled music maintenance scripts")
    tools_parser.add_argument(
        "tool",
        nargs="?",
        choices=sorted(MUSIC_TOOLS.keys()),
        help="Maintenance script to run",
    )
    tools_parser.add_argument(
        "tool_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected maintenance script",
    )
    tools_parser.add_argument(
        "--list", action="store_true", help="Show bundled maintenance scripts"
    )
    history_parser = add_feature_parser("history", "Show recent job history")
    history_parser.add_argument(
        "--limit", type=int, default=10, help="Number of recent jobs to show"
    )
    history_parser.add_argument(
        "--status",
        choices=["queued", "running", "completed", "failed", "cancelled", "timeout"],
        help="Filter jobs by status",
    )

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
        "--yes",
        action="store_true",
        help="Confirm apply",
    )
    curate_parser.add_argument(
        "--limit",
        type=int,
        help="Limit fav_songs apply to this many tracks",
    )
    curate_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip this many fav_songs tracks before applying",
    )
    curate_parser.add_argument(
        "--batch-size",
        type=int,
        help="Apply fav_songs in internal batches after one preview scan",
    )
    curate_parser.add_argument(
        "--bulk",
        action="store_true",
        help="Apply fav_songs through one bulk AppleScript call",
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
    if args.feature == "mood":
        return run_mood_analysis()
    elif args.feature == "enrich":
        return run_metadata_enrichment(args)
    elif args.feature == "organize":
        return run_playlist_organization()
    elif args.feature == "scan":
        return run_scan(args)
    elif args.feature == "status":
        return show_status(args)
    elif args.feature == "dedupe":
        return run_dedupe(args)
    elif args.feature == "export":
        return run_export(args)
    elif args.feature == "tools":
        return run_music_tools(args)
    elif args.feature == "history":
        return show_job_history(args)
    elif args.feature == "curate":
        return run_curation(args)
    else:
        # Show interactive menu if no feature specified
        return show_interactive_menu()


if __name__ == "__main__":
    sys.exit(main())
