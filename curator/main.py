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
import hashlib
import json
from collections import Counter
from pathlib import Path

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
metadata_fill = None
plsort_module = None  # type: ignore


def __getattr__(name):
    """Keep mood aliases available without its dotenv/log startup for other commands."""
    if name in {"mood_analyzer", "TemperamentAnalyzer", "MusicAppClient", "OpenAILLMClient"}:
        from importlib import import_module

        module = import_module("src.mood_analyzer")
        return module if name == "mood_analyzer" else getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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


def show_playlist_presentation(args=None):
    """Print static guidance; never inspect or modify Music/library/account state."""
    print("Playlist presentation: static guidance, not a live capability check.")
    for name, capability in AppleMusicInterface.get_playlist_presentation_capabilities().items():
        print(f"{name}: {capability['status']}")
        for field, value in capability.items():
            if field != "status":
                print(f"  {field}: {value}")
    print("Evidence and manual guide: docs/playlist-presentation.md")
    return 0


def run_playlist_cover(args=None):
    """Preview or confirm one playlist cover replacement by stable playlist ID."""
    playlist_id = getattr(args, "playlist_id", None)
    image = getattr(args, "image", None)
    apply = getattr(args, "apply", False)
    confirmed = getattr(args, "yes", False)
    if not playlist_id or not image or (apply and not confirmed) or (confirmed and not apply):
        print(error("Preview requires --playlist-id ID --image PATH. Apply separately with --apply --yes."))
        return 1
    if apply:
        print(error(
            "Automated playlist cover replacement is unsupported on Music 1.7: "
            "AppleScript cannot create artwork objects (make new artwork fails; "
            "duplicate/copy leave the playlist unchanged). "
            f"In Music, select the playlist, open Edit via the playlist's More menu, "
            f"click the artwork Add control, choose {image}, confirm with Done, then "
            "verify the displayed cover."
        ))
        return 1

    if not require_macos("Playlist cover"):
        return 1
    try:
        music = AppleMusicInterface()
        cover = music._cover_image(image)
        digest = hashlib.sha256()
        with open(cover["path"], "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        playlist = music.get_playlist_info_by_id(playlist_id)
        count = music.get_playlist_artwork_count_by_id(playlist_id)
        print(json.dumps({
            "playlist_id": playlist["persistent_id"],
            "playlist_name": playlist["name"],
            "image": {**cover, "sha256": digest.hexdigest()},
            "existing_artwork_count": count,
            "planned": "replace",
            "applied": False,
        }, ensure_ascii=False, indent=2))
        print(info("Preview only; no artwork changed. Apply with --apply --yes after review."))
        return 0
    except Exception as exc:
        print(error(f"Playlist cover failed: {exc}"))
        return 1


def run_localize(args=None):
    """Preview or apply verified local replacements for unavailable playlist tracks."""
    if not require_macos("Local playlist replacement"):
        return 1

    from src.track_localizer import TrackLocalizer

    source = Path(getattr(args, "source", ""))
    report_path = Path(getattr(args, "report", "localize-report.json"))
    playlist_name = getattr(args, "playlist", None)
    apply = getattr(args, "apply", False)
    print_header("💾 Localize Playlists", "Replacing only verified local track matches")

    try:
        localizer = TrackLocalizer(source, music_client=AppleMusicInterface())
        results = localizer.scan(playlist_name=playlist_name, apply=apply)
        TrackLocalizer.write_report(report_path, results)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.error("Local playlist replacement failed: %s", exc, exc_info=True)
        print(error(f"Local playlist replacement failed: {exc}"))
        return 1

    for status, count in sorted(Counter(result.status for result in results).items()):
        print(info(f"{status}: {count}"))
    print(info(f"Report written to: {report_path}"))
    if not apply:
        print(info("Dry-run mode — no playlist entries were changed. Pass --apply to replace verified matches."))
    print_footer()
    return 0


def run_mood_analysis(args=None):
    """Run AI mood/temperament analysis on playlists."""
    target_playlist = getattr(args, "playlist", None) if args else None
    apply = getattr(args, "apply", False) if args else False
    header = f"AI Mood Classification — {target_playlist or 'all playlists'}"
    print_header("🎭 Mood Analysis", header)

    if not require_macos("Mood analysis"):
        return 1

    if not validate_openai_api_key():
        return 1

    try:
        print(info("Initializing clients..."))
        logger.debug("Initializing mood analysis clients")

        cli = sys.modules[__name__]
        music_client = cli.MusicAppClient()
        llm_client = cli.OpenAILLMClient()

        print(info("Connecting to Music.app..."))
        if not music_client.authenticate():
            logger.error("Failed to authenticate with Music.app")
            print(error("Could not connect to Music.app"))
            return 1

        print(success("Connected to Music.app"))
        analyzer = cli.TemperamentAnalyzer(music_client, llm_client)
        # ponytail: TemperamentAnalyzer.run() does full library; per-playlist
        # filtering would require extending the analyzer — pass playlist hint via
        # an env var or future run(playlist=...) API if needed.
        if target_playlist:
            print(info(f"Analysing playlist: {target_playlist}"))
        analyzer.run()

        print_footer()
        return 0
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(error(f"Configuration error: {e}"))
        return 1
    except Exception as e:
        logger.error(f"Mood analysis failed: {e}", exc_info=True)
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
    playlist_ids = getattr(args, "playlist_id", None) or []
    apply = getattr(args, "apply", False)
    saved = getattr(args, "plan", None)
    output = getattr(args, "save_plan", None)
    confirmed = getattr(args, "yes", False)
    valid = (saved and confirmed and not (playlist_ids or output)) if apply else (
        playlist_ids and not (saved or confirmed)
    )
    if not valid:
        print(error("Preview requires --playlist-id ID [--save-plan PATH]. Apply separately with --plan PATH --apply --yes."))
        return 1
    if not require_macos("Playlist organization"):
        return 1
    try:
        from src.playlist_manager import PlaylistManager

        if apply:
            with Path(saved).open(encoding="utf-8") as handle:
                plan = json.load(handle)
            result = PlaylistManager().apply_playlist_organization(plan, confirmed=True)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("success") is True else 1

        from src.playlist_classifier import PlaylistClassifier

        data = Path(__file__).resolve().parent / "data"
        classifier = PlaylistClassifier(
            genre_map_path=str(data / "config/genre_map.json"),
            weights_path=str(data / "config/weights.json"),
            artist_lists_dir=str(data / "artist_lists"),
            enable_genre_enrichment=False,
        )
        plan = PlaylistManager().preview_playlist_organization(playlist_ids, classifier)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        if output:
            with open(output, "x", encoding="utf-8", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
                json.dump(plan, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        print(info("Preview only; no folder/playlist writes. Review the saved plan, then use --plan PATH --apply --yes."))
        return 0
    except Exception as exc:
        print(error(f"Playlist organization failed: {exc}"))
        return 1


def run_curation(args=None):
    """Preview or apply genre-based Favourite Songs curation."""
    print_header("Favorites Curator", "Sort Favourite Songs by genre")

    if not require_macos("Favorites Curator"):
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

    if args and getattr(args, "apply", False):
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


def run_playlist_split(args):
    """Preview explicit source IDs or apply the exact saved, reviewed plan."""
    playlist_ids = args.playlist_id or []
    if args.init_journal:
        if playlist_ids or args.plan or args.save_plan or args.apply or args.yes:
            print(error("Use --init-journal separately, without preview/apply options."))
            return 1
    elif args.apply:
        if not args.yes or not args.plan or playlist_ids or args.save_plan:
            print(error("Apply requires --plan PATH --apply --yes, without preview options."))
            return 1
    elif not playlist_ids or args.plan or args.yes:
        print(error("Preview requires explicit --playlist-id ID (repeatable); use --save-plan PATH to retain it."))
        return 1

    if not args.init_journal and not require_macos("Playlist split"):
        return 1

    try:
        if args.apply:
            with Path(args.plan).open(encoding="utf-8") as handle:
                plan = json.load(handle)
            if not isinstance(plan, dict) or not plan.get("sources"):
                raise ValueError("A saved split plan with selected sources is required")

        from src.curation_service import CurationService

        service = CurationService()
        if args.init_journal:
            service.initialize_playlist_split_journal()
            print(success(f"Initialized split journal: {service.split_journal_path}"))
            print(info("Keep this journal for every apply. Never delete or reinitialize it to retry."))
            return 0

        print_header("Playlist Split", "Source playlists are retained; ordered occurrences are copied")
        if args.apply:
            print(info(f"Applying saved plan: {plan.get('fingerprint', 'unknown')}"))
            result = service.apply_playlist_splits(plan, confirmed=True)
            print(info("Durably recorded per-part progress (historical until verified):"))
            for part in result.get("parts", []):
                print(info(
                    f"{part['source_id']} → {part['name']}: {part['status']}; "
                    f"target={part.get('playlist_id') or 'unknown'}; "
                    f"confirmed occurrences={part['confirmed_count']}"
                ))
            for pending in result.get("unresolved", []):
                print(warning(f"Unresolved operation: {json.dumps(pending, ensure_ascii=False, sort_keys=True)}"))
            if not result.get("success"):
                print(error(f"Split apply stopped: {result.get('error', 'Unknown error')}"))
                print(warning(
                    "Keep the original journal. Never initialize/reset it to bypass a failure. "
                    "Unresolved writes require manual recovery; no automatic repair or rollback is available."
                ))
                return 1
            print(success("Saved split plan completed; source playlists retained."))
            return 0

        plan = service.preview_playlist_splits(playlist_ids)
        print(info(f"Plan fingerprint: {plan['fingerprint']}"))
        for source in plan["sources"]:
            print(info(f"Source {source['source_id']}: {source['source_name']!r} ({len(source['track_ids'])} occurrences)"))
            if source["skip_reason"]:
                print(warning(f"Skipped: {source['skip_reason']}"))
            offset = 0
            for part in source["parts"]:
                count = len(part["track_ids"])
                print(info(f"  {part['name']}: {count} occurrences, source positions {offset + 1}–{offset + count}"))
                offset += count
        if args.save_plan:
            with open(
                args.save_plan, "x", encoding="utf-8",
                opener=lambda path, flags: os.open(path, flags, 0o600),
            ) as handle:
                json.dump(plan, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print(info(f"Saved exact plan for review: {args.save_plan}"))
        print(info(
            "Preview only; no Music writes or journal creation. "
            "Review the saved JSON, then use --plan PATH --apply --yes."
        ))
        return 0
    except Exception as exc:
        print(error(f"Playlist split failed: {exc}"))
        print(info("Keep any existing journal; initialization never resets existing state."))
        return 1


def run_seed_playlist(args):
    """Preview an explicitly selected seed or apply only its saved reviewed plan."""
    preview_options = args.playlist_id is not None or args.seed_track_id is not None or args.limit is not None
    if args.init_journal:
        valid = not (preview_options or args.plan or args.save_plan or args.apply or args.yes)
    elif args.apply:
        valid = args.yes and args.plan and not (preview_options or args.save_plan)
    else:
        valid = args.playlist_id and args.seed_track_id and not (args.plan or args.yes)
    if not valid:
        print(error(
            "Preview requires --playlist-id ID --seed-track-id ID [--limit 1..30] [--save-plan PATH]. "
            "Apply separately with --plan PATH --apply --yes; initialize separately with --init-journal."
        ))
        return 1
    if not args.init_journal and not require_macos("Seed playlist"):
        return 1

    try:
        if args.apply:
            with Path(args.plan).open(encoding="utf-8") as handle:
                plan = json.load(handle)
            if not isinstance(plan, dict) or plan.get("kind") != "seed":
                raise ValueError("A saved seed plan is required")

        from src.curation_service import CurationService

        service = CurationService()
        if args.init_journal:
            service.initialize_playlist_split_journal()
            print(success(f"Initialized shared split/seed journal: {service.split_journal_path}"))
            print(info("Keep the same journal for every apply. Never delete or reinitialize it to retry."))
            return 0

        if args.apply:
            print(info(f"Applying saved seed plan: {plan.get('fingerprint', 'unknown')}"))
            result = service.apply_seed_playlist(plan, confirmed=True)
            print(info("Durably recorded per-part progress (historical until verified):"))
            for part in result.get("parts", []):
                print(info(
                    f"{part['source_id']} → {part['name']}: {part['status']}; "
                    f"target={part.get('playlist_id') or 'unknown'}; "
                    f"confirmed occurrences={part['confirmed_count']}"
                ))
            for pending in result.get("unresolved", []):
                print(warning(f"Unresolved operation: {json.dumps(pending, ensure_ascii=False, sort_keys=True)}"))
            if not result.get("success"):
                print(error(f"Seed apply stopped: {result.get('error', 'Unknown error')}"))
                print(warning(
                    "Keep the original journal. Never initialize/reset it to bypass a failure. "
                    "Unresolved writes require manual recovery; no automatic repair or rollback is available."
                ))
                return 1
            print(success("Saved seed plan completed; source playlist retained."))
            return 0

        plan = service.preview_seed_playlist(args.playlist_id, args.seed_track_id,
                                             limit=args.limit if args.limit is not None else 30)
        source, seed = plan["source"], plan["seed"]
        print(info(f"Source {source['source_id']}: {source['source_name']!r}"))
        print(info(f"Seed {seed['persistent_id']}: {seed.get('title') or seed.get('name')} — {seed['artist']}"))
        print(info(f"Candidate scope: {plan['candidate_scope']}; ranking basis: {plan['ranking_basis']}"))
        print(info(f"Plan fingerprint: {plan['fingerprint']}"))
        print(info(f"Output: {plan['output']['name']} ({len(plan['tracks'])} tracks)"))
        for row in plan["tracks"]:
            track = row["track"]
            print(info(
                f"{row['persistent_id']}: {track.get('title') or track.get('name')} — {track['artist']}; "
                f"reason={row['reason']}; warnings={','.join(row['warnings']) or 'none'}"
            ))
        for message in plan["warnings"]:
            print(warning(message))
        if args.save_plan:
            with open(args.save_plan, "x", encoding="utf-8",
                      opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
                json.dump(plan, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print(info(f"Saved exact plan for review: {args.save_plan}"))
        print(info("Preview only; source retained, no Music writes or journal creation. Review before --plan PATH --apply --yes."))
        return 0
    except Exception as exc:
        print(error(f"Seed playlist failed: {exc}"))
        print(info("Keep any existing journal; initialization never resets existing state."))
        return 1


def run_scan(args=None):
    """Scan Apple Music library and show summary stats."""
    if not require_macos("scan"):
        return 1
    print_header("🔍 Library Scan", "Apple Music library overview")
    try:
        am = AppleMusicInterface()
        playlists = am.get_playlists() or []
        track_count = am.get_track_count()
        print(info(f"Playlists:  {len(playlists)}"))
        print(info(f"Tracks:     {track_count}"))

        # Persist as a library run
        store = LibraryStateStore()
        run = store.create_run(
            "scan",
            target="library",
            payload={"playlists": len(playlists), "tracks": track_count},
        )
        store.finish_run(
            run.id,
            status="completed",
            processed_items=track_count,
            details={"playlists": len(playlists)},
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
        print(info("Fetching all playlist tracks (one AppleScript call)..."))
        flat = am.get_all_playlists_tracks_flat()

        seen: dict = {}
        dupes = []
        playlists_seen: set = set()
        for entry in flat:
            pl_name = entry.get("playlist", "")
            playlists_seen.add(pl_name)
            key = build_track_key(
                artist=entry.get("artist", ""),
                title=entry.get("name", ""),
                album=entry.get("album"),
            )
            if key in seen:
                dupes.append({
                    "track": entry.get("name", "?"),
                    "artist": entry.get("artist", "?"),
                    "in": pl_name,
                    "also_in": seen[key],
                })
            else:
                seen[key] = pl_name

        print(info(f"Playlists scanned: {len(playlists_seen)}"))
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


def run_import(args=None):
    """Import library state from a JSON file produced by 'curator export'."""
    import json

    in_path = getattr(args, "input", None) if args else None
    if not in_path:
        print(error("--input <file> is required"))
        return 1

    print_header("📥 Import", f"Importing library state from {in_path}")
    try:
        with open(in_path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(error(f"Could not read {in_path}: {e}"))
        return 1

    store = LibraryStateStore()
    imported_runs = 0
    skipped_runs = 0
    for run_dict in payload.get("runs", []):
        try:
            existing = store.list_runs(limit=1, run_type=run_dict.get("run_type"))
            if any(r.id == run_dict.get("id") for r in existing):
                skipped_runs += 1
                continue
            run = store.create_run(
                run_type=run_dict.get("run_type", "import"),
                target=run_dict.get("target", ""),
                payload=run_dict.get("payload", {}),
            )
            store.finish_run(
                run.id,
                status=run_dict.get("status", "completed"),
                processed_items=run_dict.get("processed_items", 0),
                skipped_items=run_dict.get("skipped_items", 0),
                details=run_dict.get("details", {}),
            )
            imported_runs += 1
        except Exception:
            skipped_runs += 1

    print(success(f"Imported {imported_runs} runs ({skipped_runs} skipped)"))
    print_footer()
    return 0


def run_replay(args=None):
    """Re-execute a past LibraryRun by its ID."""
    run_id = getattr(args, "run_id", None) if args else None
    if not run_id:
        print(error("--run-id <id> is required"))
        return 1

    store = LibraryStateStore()
    runs = store.list_runs(limit=200)
    target_run = next((r for r in runs if str(r.id) == str(run_id)), None)
    if not target_run:
        print(error(f"Run {run_id} not found"))
        return 1

    print_header("🔁 Replay", f"Re-running {target_run.run_type} run {run_id}")
    print(info(f"Original: {target_run.run_type} | target={target_run.target} | {target_run.created_at}"))

    from types import SimpleNamespace
    replay_args = SimpleNamespace()

    run_type = target_run.run_type
    if run_type == "scan":
        return run_scan(replay_args)
    elif run_type == "enrich":
        replay_args.library = True
        replay_args.playlist = None
        replay_args.folder = None
        replay_args.force = False
        replay_args.verbose = False
        return run_metadata_enrichment(replay_args)
    elif run_type == "dedupe":
        replay_args.apply = False
        replay_args.scope = target_run.target or "dedupe"
        return run_dedupe(replay_args)
    else:
        print(error(f"Replay not supported for run type '{run_type}'. Supported: scan, enrich, dedupe"))
        return 1


def run_jobs_command(args=None):
    """Manage background jobs: list, status, cancel."""
    action = getattr(args, "jobs_action", None) if args else None
    job_store = get_job_store()

    if action == "list" or action is None:
        limit = getattr(args, "limit", 20) if args else 20
        status_filter = getattr(args, "status", None) if args else None
        print_header("🗂 Jobs", "Background job queue")
        total, jobs = job_store.list_jobs(limit=limit, status=status_filter)
        if not jobs:
            print(info("No jobs found"))
        else:
            print(info(f"Showing {len(jobs)} of {total} jobs"))
            for job in jobs:
                created = job.created_at.isoformat() if job.created_at else "unknown"
                progress = f"{job.progress}%" if job.progress is not None else "n/a"
                print(f"  {job.id}  {job.type:<20} {job.status:<12} {progress:>5}  {created}")
        print_footer()
        return 0

    elif action == "status":
        job_id = getattr(args, "job_id", None) if args else None
        if not job_id:
            print(error("job_id required"))
            return 1
        job = job_store.get_job(job_id)
        if not job:
            print(error(f"Job {job_id} not found"))
            return 1
        print_header("🗂 Job Status", job_id)
        print(info(f"Type:     {job.type}"))
        print(info(f"Status:   {job.status}"))
        print(info(f"Progress: {job.progress}%") if job.progress is not None else info("Progress: n/a"))
        print(info(f"Created:  {job.created_at}"))
        print(info(f"Updated:  {job.updated_at}"))
        if job.error:
            print(error(f"Error: {job.error}"))
        print_footer()
        return 0

    elif action == "cancel":
        job_id = getattr(args, "job_id", None) if args else None
        if not job_id:
            print(error("job_id required"))
            return 1
        try:
            job_store.update_job(job_id, status="cancelled")
            print(success(f"Job {job_id} cancelled"))
            return 0
        except Exception as e:
            print(error(f"Could not cancel job {job_id}: {e}"))
            return 1

    else:
        print(error(f"Unknown jobs action: {action}"))
        return 1


def run_mood_show(args=None):
    """Show current mood assignments from Music.app folder structure."""
    if not require_macos("mood show"):
        return 1
    print_header("🎭 Mood Map", "Current playlist mood assignments")
    try:
        am = AppleMusicInterface()
        folder_structure = am.get_playlist_folder_structure() or {}
        buckets: dict[str, list[str]] = {"Woe": [], "Frolic": [], "Dread": [], "Malice": []}
        other_folders: dict[str, list[str]] = {}

        for folder_name, playlist_names in folder_structure.items():
            matched = False
            for bucket in buckets:
                if bucket.lower() in folder_name.lower():
                    buckets[bucket].extend(playlist_names)
                    matched = True
                    break
            if not matched and playlist_names:
                other_folders[folder_name] = playlist_names

        any_mood = any(buckets.values())
        if not any_mood:
            print(info("No mood assignments found. Run: curator mood analyze --apply"))
        else:
            for bucket, names in buckets.items():
                if names:
                    print(bold(f"\n{bucket} ({len(names)}):"))
                    for n in sorted(names):
                        print(f"  • {n}")
        print_footer()
        return 0
    except Exception as e:
        print(error(f"mood show failed: {e}"))
        return 1


def run_mood_suggest(args=None):
    """Suggest playlists matching a mood bucket."""
    mood = getattr(args, "mood", None) if args else None
    if not mood:
        print(error("--mood <woe|frolic|dread|malice> is required"))
        return 1
    if not require_macos("mood suggest"):
        return 1
    print_header("🎭 Mood Suggest", f"Playlists matching mood: {mood.title()}")
    try:
        am = AppleMusicInterface()
        folder_structure = am.get_playlist_folder_structure() or {}
        matches = []
        for folder_name, playlist_names in folder_structure.items():
            if mood.lower() in folder_name.lower():
                matches.extend(playlist_names)

        if not matches:
            print(info(f"No playlists classified as '{mood.title()}' yet. Run: curator mood analyze --apply"))
        else:
            print(info(f"Found {len(matches)} playlists:"))
            for name in sorted(matches):
                print(f"  • {name}")
        print_footer()
        return 0
    except Exception as e:
        print(error(f"mood suggest failed: {e}"))
        return 1


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
                "🎭 Mood Analyze     - AI emotion classification of playlists",
                "🗺  Mood Show        - Current mood folder assignments",
                "📝 Enrich Metadata  - Fill missing metadata from music databases",
                "📚 Organize         - Genre-based playlist sorting",
                "🔍 Scan Library     - Sync and show library stats",
                "📊 Status           - Current jobs and run state",
                "🗂  Deduplicate      - Cross-playlist duplicate analysis",
                "🗃  Jobs             - Background job queue",
                "📦 Export           - Export state to JSON",
                "🛠  Music Tools      - Playlist cleanup and genre maintenance",
                "🕘 Job History      - Review recent runs",
            ]

            choice = Menu.select("Select a feature to run", features)

            if choice == 0:
                return run_mood_analysis()
            elif choice == 1:
                return run_mood_show()
            elif choice == 2:
                return run_metadata_enrichment()
            elif choice == 3:
                return run_playlist_organization()
            elif choice == 4:
                return run_scan()
            elif choice == 5:
                return show_status()
            elif choice == 6:
                return run_dedupe()
            elif choice == 7:
                return run_jobs_command()
            elif choice == 8:
                return run_export()
            elif choice == 9:
                return run_music_tools()
            elif choice == 10:
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

    # mood sub-subcommands: analyze, show, suggest
    mood_parser = add_feature_parser("mood", "Mood analysis: analyze, show, suggest")
    mood_sub = mood_parser.add_subparsers(dest="mood_action", metavar="action")
    analyze_p = mood_sub.add_parser("analyze", help="AI mood classification (default)")
    analyze_scope = analyze_p.add_mutually_exclusive_group()
    analyze_scope.add_argument("--library", action="store_true", help="Analyse all playlists")
    analyze_scope.add_argument("--playlist", help="Specific playlist to analyse")
    analyze_p.add_argument("--apply", action="store_true", help="Move playlists to mood folders")
    show_p = mood_sub.add_parser("show", help="Show current mood folder assignments")
    show_p.add_argument("--playlist", help="Filter to a specific playlist")
    suggest_p = mood_sub.add_parser("suggest", help="List playlists for a mood bucket")
    suggest_p.add_argument(
        "--mood", choices=["woe", "frolic", "dread", "malice"], required=True,
        help="Mood bucket to filter by"
    )

    enrich_parser = add_feature_parser("enrich", "Fill metadata from music databases")
    enrich_scope = enrich_parser.add_mutually_exclusive_group()
    enrich_scope.add_argument("--library", action="store_true", help="Enrich every song in the library")
    enrich_scope.add_argument("--playlist", help="Apple Music playlist name to enrich")
    enrich_scope.add_argument("--folder", help="Local audio folder path or name to enrich")
    enrich_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing metadata fields"
    )
    organize_parser = add_feature_parser("organize", "Preview explicit playlist IDs or apply an exact reviewed folder plan")
    organize_parser.add_argument("--playlist-id", action="append", help="Source persistent ID; repeat to select multiple playlists")
    organize_parser.add_argument("--save-plan", metavar="PATH", help="Save exact preview privately to a new JSON file")
    organize_parser.add_argument("--plan", metavar="PATH", help="Saved, reviewed organization plan")
    organize_parser.add_argument("--apply", action="store_true", help="Apply only the saved plan; requires --yes")
    organize_parser.add_argument("--yes", action="store_true", help="Explicitly confirm applying the saved plan")
    add_feature_parser("playlist-presentation", "Show offline cover/sharing guidance (no Music access or writes)")
    cover_parser = add_feature_parser("playlist-cover", "Preview or apply one playlist cover by ID (PNG/JPEG)")
    cover_parser.add_argument("--playlist-id", required=True, help="Exact playlist persistent ID")
    cover_parser.add_argument("--image", required=True, help="PNG or JPEG cover file")
    cover_parser.add_argument("--apply", action="store_true", help="Replace the playlist cover; requires --yes")
    cover_parser.add_argument("--yes", action="store_true", help="Explicitly confirm the cover replacement")

    localize_parser = add_feature_parser(
        "localize", "Preview/apply local replacements for unavailable playlist tracks"
    )
    localize_parser.add_argument("--playlist", help="Only process one user playlist")
    localize_parser.add_argument(
        "--source",
        default="/Volumes/2TB_SSD/Media (Musik Mediathek)/Music Library [2025-06-20].musiclibrary",
        help="Local Music library folder to search",
    )
    localize_parser.add_argument(
        "--report", default="localize-report.json", help="JSON report output path"
    )
    localize_parser.add_argument(
        "--apply",
        action="store_true",
        help="Import, add, then remove only verified replacements",
    )

    split_parser = add_feature_parser("split", "Preview playlist parts (maximum 100 tracks), or apply a reviewed plan")
    split_parser.add_argument("--playlist-id", action="append", help="Explicit source persistent ID; repeat for multiple sources")
    split_parser.add_argument("--save-plan", metavar="PATH", help="Save preview JSON to a new file for review (never overwrites)")
    split_parser.add_argument("--plan", metavar="PATH", help="Previously saved, reviewed JSON plan to apply")
    split_parser.add_argument("--apply", action="store_true", help="Apply the saved plan; requires --yes")
    split_parser.add_argument("--yes", action="store_true", help="Explicitly confirm applying the saved plan")
    split_parser.add_argument("--init-journal", action="store_true", help="Separate local-only first-use journal initialization; never resets existing state")

    seed_parser = add_feature_parser("seed-playlist", "Preview a selected seed using recorded library metadata, or apply a reviewed plan")
    seed_parser.add_argument("--playlist-id", help="Explicit source playlist persistent ID")
    seed_parser.add_argument("--seed-track-id", help="Explicit member track persistent ID")
    seed_parser.add_argument("--limit", type=int, default=None, help="Total tracks including seed (1–30; default 30)")
    seed_parser.add_argument("--save-plan", metavar="PATH", help="Save exact preview privately to a new JSON file")
    seed_parser.add_argument("--plan", metavar="PATH", help="Previously saved, reviewed seed plan")
    seed_parser.add_argument("--apply", action="store_true", help="Apply only the saved plan; requires --yes")
    seed_parser.add_argument("--yes", action="store_true", help="Explicitly confirm applying the saved plan")
    seed_parser.add_argument("--init-journal", action="store_true", help="Separate local-only initialization of the shared split/seed journal; never resets")

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

    # jobs sub-subcommands: list, status, cancel
    jobs_parser = add_feature_parser("jobs", "Manage background jobs")
    jobs_sub = jobs_parser.add_subparsers(dest="jobs_action", metavar="action")
    jobs_list_p = jobs_sub.add_parser("list", help="List recent jobs (default)")
    jobs_list_p.add_argument("--limit", type=int, default=20, help="Max jobs to show")
    jobs_list_p.add_argument(
        "--status",
        choices=["queued", "running", "completed", "failed", "cancelled", "timeout"],
        help="Filter by status",
    )
    jobs_status_p = jobs_sub.add_parser("status", help="Show detail for a single job")
    jobs_status_p.add_argument("job_id", help="Job ID")
    jobs_cancel_p = jobs_sub.add_parser("cancel", help="Cancel a queued or running job")
    jobs_cancel_p.add_argument("job_id", help="Job ID")

    import_parser = add_feature_parser("import", "Import library state from a JSON export")
    import_parser.add_argument("--input", required=True, help="Path to JSON file from 'curator export'")

    replay_parser = add_feature_parser("replay", "Re-run a past library run by ID")
    replay_parser.add_argument("--run-id", required=True, dest="run_id", help="LibraryRun ID to replay")

    curate_parser = add_feature_parser("curate", "Preview/apply Favourite Songs curation")
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
        action = getattr(args, "mood_action", None)
        if action == "show":
            return run_mood_show(args)
        elif action == "suggest":
            return run_mood_suggest(args)
        else:  # "analyze" or no sub-action
            return run_mood_analysis(args)
    elif args.feature == "enrich":
        return run_metadata_enrichment(args)
    elif args.feature == "organize":
        return run_playlist_organization(args)
    elif args.feature == "playlist-presentation":
        return show_playlist_presentation(args)
    elif args.feature == "playlist-cover":
        return run_playlist_cover(args)
    elif args.feature == "localize":
        return run_localize(args)
    elif args.feature == "split":
        return run_playlist_split(args)
    elif args.feature == "seed-playlist":
        return run_seed_playlist(args)
    elif args.feature == "scan":
        return run_scan(args)
    elif args.feature == "status":
        return show_status(args)
    elif args.feature == "dedupe":
        return run_dedupe(args)
    elif args.feature == "export":
        return run_export(args)
    elif args.feature == "import":
        return run_import(args)
    elif args.feature == "replay":
        return run_replay(args)
    elif args.feature == "jobs":
        return run_jobs_command(args)
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
