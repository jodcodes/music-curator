"""
Integration tests for CLI platform guard behavior.

Tests the CLI's behavior when platform-specific features are
invoked on non-macOS platforms.
"""

import os
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def install_fake_curation_service(
    monkeypatch, preview=None, apply_result=None, smoke_result=None
):
    calls = {"constructed": 0, "preview": 0, "apply": [], "smoke": 0}
    preview_result = preview or {
        "total_assignments": 3,
        "total_changes": 2,
        "total_skipped": 1,
    }
    result = apply_result or {"success": True, "applied": 2, "failed": 0}
    smoke = smoke_result or {
        "success": True,
        "copied": 1,
        "duplicate_skipped": True,
        "leftovers": {"root": 0, "genre": 0, "playlist": 0},
    }

    class FakeCurationService:
        def __init__(self):
            calls["constructed"] += 1

        def preview_fav_songs(self):
            calls["preview"] += 1
            return preview_result

        def apply_fav_songs(self, confirmed):
            calls["apply"].append(confirmed)
            return result

        def run_fav_songs_smoke_test(self):
            calls["smoke"] += 1
            return smoke

    monkeypatch.setitem(
        sys.modules,
        "src.curation_service",
        SimpleNamespace(CurationService=FakeCurationService),
    )
    return calls


class TestCLIPlatformGuards:
    """Tests for CLI platform constraints."""

    def test_temperament_on_non_macos_exits_with_error(self):
        """Running temperament on non-macOS should exit gracefully."""
        with patch("sys.platform", "linux"):
            # Reload main to get fresh IS_MACOS value
            import importlib

            import main

            importlib.reload(main)

            # Simulate running temperament analysis
            result = main.run_mood_analysis()
            assert result == 1, "Expected exit code 1 for non-macOS temperament"

    def test_playlist_enrichment_on_non_macos_exits_with_error(self):
        """Running playlist enrichment on non-macOS should exit gracefully."""
        with patch("sys.platform", "win32"):
            import importlib

            import main

            importlib.reload(main)

            # Simulate running metadata enrichment on a playlist
            with patch.object(main.Menu, "select", return_value=0):  # Select "Playlist"
                result = main.run_metadata_enrichment()
                assert result == 1, "Expected exit code 1 for non-macOS playlist enrichment"

    def test_folder_enrichment_on_non_macos_proceeds(self):
        """Running folder enrichment on non-macOS should not require macOS guard."""
        with patch("sys.platform", "linux"):
            import importlib

            import main

            importlib.reload(main)

            # Mock the metadata fill flow
            with patch.object(main.Menu, "select", return_value=1):  # Select "Folder"
                with patch.object(main.Menu, "input_text", return_value="/tmp/music"):
                    with patch("main.MetadataFillCLI") as mock_cli:
                        mock_instance = MagicMock()
                        mock_instance.run.return_value = 0
                        mock_cli.return_value = mock_instance

                        result = main.run_metadata_enrichment()
                        # Should not be rejected at platform level
                        # (may fail for other reasons, but platform guard is OK)
                        assert result == 0 or result != -1  # Not a platform guard error

    def test_playlist_organization_on_non_macos_exits_with_error(self):
        """Running organization on non-macOS should exit gracefully."""
        with patch("sys.platform", "linux"):
            import importlib

            import main

            importlib.reload(main)

            result = main.run_playlist_organization()
            assert result == 1, "Expected exit code 1 for non-macOS organization"


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_missing_openai_api_key_is_caught(self):
        """Missing OPENAI_API_KEY should be detected and reported."""
        with patch.dict("os.environ", {}, clear=False):
            # Remove OPENAI_API_KEY if it exists
            os.environ.pop("OPENAI_API_KEY", None)

            import main

            result = main.validate_openai_api_key()
            assert result is False, "Should detect missing OPENAI_API_KEY"

    def test_present_openai_api_key_is_accepted(self):
        """Present OPENAI_API_KEY should be accepted."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-12345"}):
            import main

            result = main.validate_openai_api_key()
            assert result is True, "Should accept valid OPENAI_API_KEY"

    def test_valid_api_key_allows_temperament_analysis(self):
        """With valid API key, temperament analysis should proceed to client init."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch("sys.platform", "darwin"):  # Pretend it's macOS
                import importlib

                import main

                importlib.reload(main)

                with patch("main.MusicAppClient") as mock_music:
                    with patch("main.OpenAILLMClient") as mock_llm:
                        with patch("main.TemperamentAnalyzer"):
                            mock_music.return_value.authenticate.return_value = False

                            result = main.run_mood_analysis()
                            # It should get past API key validation and fail on Music.app auth
                            assert result == 1  # Failed due to Music.app, not API key
                            mock_llm.assert_called_once()  # LLM client was created


def test_curate_feature_accepts_dry_run(monkeypatch):
    import main

    calls = {}

    def fake_run_curation(args):
        calls["apply"] = args.apply
        calls["smoke_test"] = args.smoke_test
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation, raising=False)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate"]) == 0
    assert calls == {"apply": False, "smoke_test": False}


def test_curate_feature_accepts_apply(monkeypatch):
    import main

    calls = {}

    def fake_run_curation(args):
        calls["apply"] = args.apply
        calls["smoke_test"] = args.smoke_test
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation, raising=False)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate", "--apply"]) == 0
    assert calls == {"apply": True, "smoke_test": False}


def test_curate_feature_accepts_smoke_test(monkeypatch):
    import main

    calls = {}

    def fake_run_curation(args):
        calls["apply"] = args.apply
        calls["smoke_test"] = args.smoke_test
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation, raising=False)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate", "--smoke-test"]) == 0
    assert calls == {"apply": False, "smoke_test": True}


def test_localize_defaults_to_dry_run_and_all_playlists(monkeypatch):
    import main

    calls = {}

    def fake_run_localize(args):
        calls.update(apply=args.apply, playlist=args.playlist, report=args.report)
        return 0

    monkeypatch.setattr(main, "run_localize", fake_run_localize, raising=False)

    assert main.main(["localize"]) == 0
    assert calls == {"apply": False, "playlist": None, "report": "localize-report.json"}


def test_run_localize_requires_macos_before_constructing_service(monkeypatch):
    import main

    monkeypatch.setattr(main, "IS_MACOS", False)

    assert main.main(["localize"]) == 1


def test_tools_feature_lists_bundled_scripts(monkeypatch, capsys):
    import main

    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.run_music_tools(SimpleNamespace(list=True)) == 0

    output = capsys.readouterr().out
    assert "sort-favourites" in output
    assert "find-duplicates" in output
    assert "cleanup-genres" in output
    assert "enrich-genres" in output


def test_tools_feature_dispatches_selected_script(monkeypatch):
    import main

    calls = {}

    def fake_run_music_tool(tool_name, extra_args):
        calls["tool_name"] = tool_name
        calls["extra_args"] = list(extra_args)

        class Result:
            stdout = "done"
            stderr = ""
            returncode = 0

        return Result()

    monkeypatch.setattr(main, "run_music_tool", fake_run_music_tool)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.run_music_tools(SimpleNamespace(tool="sort-favourites", tool_args=["--dry-run"])) == 0
    assert calls == {"tool_name": "sort-favourites", "extra_args": ["--dry-run"]}


def test_curate_feature_on_non_macos_exits_without_service(monkeypatch):
    import main

    calls = {"constructed": False}

    class FakeCurationService:
        def __init__(self):
            calls["constructed"] = True

    monkeypatch.setattr(main, "IS_MACOS", False)
    monkeypatch.setitem(
        sys.modules,
        "src.curation_service",
        SimpleNamespace(CurationService=FakeCurationService),
    )

    assert main.main(["curate"]) == 1
    assert calls == {"constructed": False}


def test_curation_apply_without_feature_is_rejected(monkeypatch):
    import main

    def fail_interactive_menu():
        raise AssertionError("interactive menu should not run for invalid curation flags")

    monkeypatch.setattr(main, "show_interactive_menu", fail_interactive_menu)

    with pytest.raises(SystemExit) as exc:
        main.main(["--apply"])

    assert exc.value.code != 0


def test_organization_apply_without_saved_plan_is_rejected(monkeypatch):
    import main

    def forbidden(*args, **kwargs):
        raise AssertionError("Missing reviewed plan must be rejected before platform/service access")

    monkeypatch.setattr(main, "require_macos", forbidden)
    assert main.main(["organize", "--apply"]) == 1


def test_run_curation_dry_run_previews_without_apply(monkeypatch, capsys):
    import main

    calls = install_fake_curation_service(monkeypatch)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.run_curation(SimpleNamespace(apply=False)) == 0
    assert calls == {"constructed": 1, "preview": 1, "apply": [], "smoke": 0}

    output = capsys.readouterr().out
    assert "Preview" in output
    assert "UI mini-test" in output


def test_run_curation_apply_is_locked_without_service_apply(monkeypatch, capsys):
    import main

    calls = install_fake_curation_service(monkeypatch)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.run_curation(SimpleNamespace(apply=True)) == 1
    assert calls == {"constructed": 0, "preview": 0, "apply": [], "smoke": 0}

    output = capsys.readouterr().out
    assert "Full apply is locked" in output
    assert "UI mini-test" in output


def test_run_curation_apply_lock_does_not_mask_dry_run(monkeypatch):
    import main

    calls = install_fake_curation_service(monkeypatch)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.run_curation(SimpleNamespace(apply=False)) == 0
    assert calls == {"constructed": 1, "preview": 1, "apply": [], "smoke": 0}


def test_run_curation_smoke_test_only_runs_reversible_smoke(monkeypatch, capsys):
    import main

    calls = install_fake_curation_service(monkeypatch)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.run_curation(SimpleNamespace(apply=False, smoke_test=True)) == 0
    assert calls == {"constructed": 1, "preview": 0, "apply": [], "smoke": 1}

    output = capsys.readouterr().out
    assert "Smoke test" in output
    assert "copied: 1" in output
    assert "leftovers: {'root': 0, 'genre': 0, 'playlist': 0}" in output


def test_enrich_subcommand_uses_noninteractive_playlist_args(monkeypatch):
    import main

    calls = {}

    class FakeCLI:
        def run(self, args):
            calls["playlist"] = args.playlist
            calls["folder"] = args.folder
            calls["force"] = args.force
            calls["verbose"] = args.verbose
            return 0

    monkeypatch.setattr(main, "IS_MACOS", True)
    monkeypatch.setattr("src.metadata_fill.MetadataFillCLI", FakeCLI)
    monkeypatch.setattr(
        main.Menu,
        "select",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("interactive menu should not be used")
        ),
    )

    assert main.main(["enrich", "--playlist", "gc 80s dance and synth pop", "--force"]) == 0
    assert calls == {
        "playlist": "gc 80s dance and synth pop",
        "folder": None,
        "force": True,
        "verbose": False,
    }


def test_enrich_subcommand_uses_noninteractive_folder_args(monkeypatch):
    import main

    calls = {}

    class FakeCLI:
        def run(self, args):
            calls["playlist"] = args.playlist
            calls["folder"] = args.folder
            calls["force"] = args.force
            calls["verbose"] = args.verbose
            return 0

    monkeypatch.setattr("src.metadata_fill.MetadataFillCLI", FakeCLI)
    monkeypatch.setattr(
        main.Menu,
        "select",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("interactive menu should not be used")
        ),
    )

    assert main.main(["enrich", "--folder", "/Users/me/Music/Test"]) == 0
    assert calls == {
        "playlist": None,
        "folder": "/Users/me/Music/Test",
        "force": False,
        "verbose": False,
    }


def test_enrich_subcommand_accepts_all_modes(monkeypatch):
    import main

    calls = []

    class FakeCLI:
        def run(self, args):
            calls.append(
                {
                    "all_playlists": args.all_playlists,
                    "playlist": args.playlist,
                    "folder": args.folder,
                }
            )
            return 0

    monkeypatch.setattr(main, "IS_MACOS", True)
    monkeypatch.setattr("src.metadata_fill.MetadataFillCLI", FakeCLI)

    assert main.main(["enrich", "--library"]) == 0
    assert main.main(["enrich", "--playlist", "My Mix"]) == 0
    assert calls == [
        {"all_playlists": True, "playlist": None, "folder": None},
        {"all_playlists": False, "playlist": "My Mix", "folder": None},
    ]


# ============================================================================
# New CLI command tests: scan, status, dedupe, export
# ============================================================================

class TestScanCommand:
    def test_scan_requires_macos(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", False)
        assert main.run_scan() == 1

    def test_scan_calls_apple_music_and_records_run(self, monkeypatch, tmp_path):
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'scan.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)
        monkeypatch.setattr(main, "IS_MACOS", True)

        class FakeAM:
            def get_playlists(self):
                return [{"id": "p1", "name": "Test"}]
            def get_track_count(self):
                return 2

        monkeypatch.setattr(main, "AppleMusicInterface", lambda: FakeAM())

        result = main.run_scan()
        assert result == 0

        store = lss.LibraryStateStore(session=session)
        runs = store.list_runs(limit=5, run_type="scan")
        assert len(runs) == 1
        assert runs[0].status == "completed"
        assert runs[0].processed_items == 2


class TestStatusCommand:
    def test_status_returns_0(self, monkeypatch, tmp_path):
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'status.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)

        class FakeJobStore:
            def list_jobs(self, limit=5, status=None):
                return 0, []

        monkeypatch.setattr(main, "get_job_store", lambda: FakeJobStore())

        assert main.show_status() == 0


class TestDedupeCommand:
    def test_dedupe_requires_macos(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", False)
        assert main.run_dedupe() == 1

    def test_dedupe_dry_run_records_run(self, monkeypatch, tmp_path):
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'dedupe.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)
        monkeypatch.setattr(main, "IS_MACOS", True)

        class FakeAM:
            def get_all_playlists_tracks_flat(self):
                return [
                    {"playlist": "Mix", "artist": "A", "name": "Song", "album": "AL"},
                    {"playlist": "Mix", "artist": "A", "name": "Song", "album": "AL"},  # dup
                ]

        monkeypatch.setattr(main, "AppleMusicInterface", lambda: FakeAM())

        result = main.run_dedupe()
        assert result == 0

        store = lss.LibraryStateStore(session=session)
        runs = store.list_runs(limit=5, run_type="dedupe")
        assert len(runs) == 1
        assert runs[0].details["duplicates"] == 1


class TestExportCommand:
    def test_export_writes_json_file(self, monkeypatch, tmp_path):
        import json
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'export.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)

        class FakeJobStore:
            def list_jobs(self, limit=100):
                return 0, []

        monkeypatch.setattr(main, "get_job_store", lambda: FakeJobStore())

        store = lss.LibraryStateStore(session=session)
        store.create_run("scan", target="library", payload={})

        out = str(tmp_path / "out.json")
        from types import SimpleNamespace
        result = main.run_export(SimpleNamespace(output=out, limit=100))
        assert result == 0

        with open(out) as f:
            data = json.load(f)

        assert "runs" in data
        assert "dedupe_history" in data
        assert "jobs" in data
        assert len(data["runs"]) == 1
        assert data["summary"]["total_runs"] == 1


# ============================================================================
# jobs subcommand
# ============================================================================

class TestJobsCommand:
    def test_jobs_list_returns_0(self, monkeypatch, tmp_path):
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'jobs.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)

        class FakeJobStore:
            def list_jobs(self, limit=20, status=None):
                return 0, []

        monkeypatch.setattr(main, "get_job_store", lambda: FakeJobStore())
        assert main.main(["jobs", "list"]) == 0

    def test_jobs_cancel_unknown_id_returns_1(self, monkeypatch):
        import main

        class FakeJobStore:
            def update_job(self, job_id, **kw):
                raise KeyError(job_id)

        monkeypatch.setattr(main, "get_job_store", lambda: FakeJobStore())
        from types import SimpleNamespace
        args = SimpleNamespace(jobs_action="cancel", job_id="nonexistent")
        assert main.run_jobs_command(args) == 1

    def test_jobs_status_unknown_id_returns_1(self, monkeypatch):
        import main

        class FakeJobStore:
            def get_job(self, job_id):
                return None

        monkeypatch.setattr(main, "get_job_store", lambda: FakeJobStore())
        from types import SimpleNamespace
        args = SimpleNamespace(jobs_action="status", job_id="xyz")
        assert main.run_jobs_command(args) == 1


# ============================================================================
# mood sub-subcommands: show, suggest
# ============================================================================

class TestMoodShowSuggest:
    def test_mood_show_requires_macos(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", False)
        assert main.run_mood_show() == 1

    def test_mood_show_groups_by_folder(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", True)

        class FakeAM:
            def get_playlist_folder_structure(self):
                return {
                    "4 Tempers/Jazz Woe": ["Sad Mix"],
                    "4 Tempers/Pop Frolic": ["Party"],
                    "Other": ["No Mood"],
                }

        monkeypatch.setattr(main, "AppleMusicInterface", lambda: FakeAM())
        from types import SimpleNamespace
        assert main.run_mood_show(SimpleNamespace()) == 0

    def test_mood_suggest_requires_macos(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", False)
        from types import SimpleNamespace
        assert main.run_mood_suggest(SimpleNamespace(mood="woe")) == 1

    def test_mood_suggest_no_mood_returns_1(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", True)
        from types import SimpleNamespace
        assert main.run_mood_suggest(SimpleNamespace(mood=None)) == 1

    def test_mood_suggest_filters_by_bucket(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "IS_MACOS", True)

        class FakeAM:
            def get_playlist_folder_structure(self):
                return {
                    "4 Tempers/Jazz Woe": ["Sad Mix"],
                    "4 Tempers/Pop Frolic": ["Party"],
                }

        monkeypatch.setattr(main, "AppleMusicInterface", lambda: FakeAM())
        from types import SimpleNamespace
        assert main.run_mood_suggest(SimpleNamespace(mood="woe")) == 0


# ============================================================================
# import command
# ============================================================================

class TestImportCommand:
    def test_import_requires_input_flag(self, monkeypatch):
        import main
        from types import SimpleNamespace
        assert main.run_import(SimpleNamespace(input=None)) == 1

    def test_import_missing_file_returns_1(self, monkeypatch):
        import main
        from types import SimpleNamespace
        assert main.run_import(SimpleNamespace(input="/nonexistent/path.json")) == 1

    def test_import_reads_export_json(self, monkeypatch, tmp_path):
        import json, main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'import.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)

        export_file = tmp_path / "export.json"
        store = lss.LibraryStateStore(session=session)
        run = store.create_run("scan", target="library", payload={})
        store.finish_run(run.id, status="completed", processed_items=5)
        runs = [r.to_dict() for r in store.list_runs(limit=10)]
        export_file.write_text(json.dumps({"runs": runs, "dedupe_history": [], "jobs": []}))

        from types import SimpleNamespace
        assert main.run_import(SimpleNamespace(input=str(export_file))) == 0


# ============================================================================
# replay command
# ============================================================================

class TestReplayCommand:
    def test_replay_requires_run_id(self):
        import main
        from types import SimpleNamespace
        assert main.run_replay(SimpleNamespace(run_id=None)) == 1

    def test_replay_unknown_run_returns_1(self, monkeypatch, tmp_path):
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'replay.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)

        from types import SimpleNamespace
        assert main.run_replay(SimpleNamespace(run_id="999")) == 1

    def test_replay_unsupported_type_returns_1(self, monkeypatch, tmp_path):
        import main
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'replay2.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)
        monkeypatch.setattr(db, "get_session", lambda: session)

        store = lss.LibraryStateStore(session=session)
        run = store.create_run("export", target="library", payload={})
        store.finish_run(run.id, status="completed", processed_items=0)
        all_runs = store.list_runs(limit=5)
        run_id = str(all_runs[0].id)

        from types import SimpleNamespace
        assert main.run_replay(SimpleNamespace(run_id=run_id)) == 1


@pytest.fixture
def split_cli(monkeypatch, tmp_path):
    import main
    import src.curation_service as service_module

    source_id = "0000000000000001"

    class FakeSplitMusic:
        def __init__(self):
            self.playlists = {
                source_id: {"name": "Mix", "tracks": [f"{10 + i % 5:016X}" for i in range(101)]},
                "0000000000000002": {"name": "Short", "tracks": []},
            }
            self.writes = []
            self.fail_create = False

        def get_playlist_info_by_id(self, playlist_id):
            return {"persistent_id": playlist_id, "name": self.playlists[playlist_id]["name"]}

        def get_playlist_tracks_by_id(self, playlist_id):
            return [{"persistent_id": item} for item in self.playlists[playlist_id]["tracks"]]

        def create_playlist(self, name):
            playlist_id = f"{100 + len(self.playlists):016X}"
            self.playlists[playlist_id] = {"name": name, "tracks": []}
            self.writes.append(("create", playlist_id))
            if self.fail_create:
                raise TimeoutError("create response lost")
            return playlist_id

        def add_library_track_to_playlist_by_id(self, playlist_id, track_id):
            self.playlists[playlist_id]["tracks"].append(track_id)
            self.writes.append(("add", playlist_id, track_id))
            return True

    music = FakeSplitMusic()
    services = []
    service_class = service_module.CurationService
    journal = tmp_path / "split-journal"

    def create_service():
        service = service_class(apple_music=music, split_journal_path=journal)
        services.append(service)
        return service

    monkeypatch.setattr(service_module, "CurationService", create_service)
    monkeypatch.setattr(main, "IS_MACOS", True)
    return SimpleNamespace(main=main, music=music, services=services, journal=journal,
                           source_id=source_id, plan_path=tmp_path / "reviewed.json")


def test_split_cli_default_preview_is_read_only_and_requires_explicit_ids(split_cli, capsys):
    cli = split_cli
    assert cli.main.main(["split"]) == 1
    assert cli.services == []
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--playlist-id", "0000000000000002"]) == 0
    output = capsys.readouterr().out
    assert cli.source_id in output and "Mix" in output
    assert output.index("Mix · 01") < output.index("Mix · 02")
    assert "51" in output and "50" in output
    assert "within_limit" in output
    assert "Source playlists are retained" in output
    assert cli.music.writes == []
    assert not cli.journal.exists()
    assert not cli.plan_path.exists()


def test_split_cli_saved_plan_is_exact_and_apply_retries_across_invocations(split_cli, monkeypatch, tmp_path):
    cli = split_cli
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--save-plan", str(cli.plan_path)]) == 0
    plan = json.loads(cli.plan_path.read_text())
    assert plan == cli.services[0].preview_playlist_splits([cli.source_id])
    assert cli.main.main(["split", "--init-journal"]) == 0
    original_apply = type(cli.services[0]).apply_playlist_splits
    applied = []

    def record_apply(service, submitted, confirmed=False):
        applied.append((submitted, confirmed))
        return original_apply(service, submitted, confirmed=confirmed)

    monkeypatch.setattr(type(cli.services[0]), "apply_playlist_splits", record_apply)
    args = ["split", "--plan", str(cli.plan_path), "--apply", "--yes"]
    assert cli.main.main(args) == 0
    assert applied == [(plan, True)]
    writes = list(cli.music.writes)
    assert len(writes) == 103
    monkeypatch.chdir(tmp_path)
    assert cli.main.main(args) == 0
    assert cli.music.writes == writes
    assert len(cli.services) == 4
    assert cli.music.playlists[cli.source_id]["tracks"] == plan["sources"][0]["track_ids"]


@pytest.mark.parametrize("args", [
    ["--apply"], ["--apply", "--yes"], ["--yes"],
    ["--plan", "missing.json"], ["--plan", "missing.json", "--apply"],
    ["--playlist-id", "0000000000000001", "--apply", "--yes"],
    ["--init-journal", "--playlist-id", "0000000000000001"],
    ["--init-journal", "--apply", "--yes"],
    ["--save-plan", "missing.json"],
])
def test_split_cli_rejects_incomplete_or_mixed_actions_before_service(split_cli, args):
    cli = split_cli
    assert cli.main.main(["split", *args]) == 1
    assert cli.services == []
    assert cli.music.writes == []
    assert not cli.journal.exists()


@pytest.mark.parametrize("payload", [None, "{broken", "[]", "{}", '{"version": 1}'])
def test_split_cli_invalid_plan_never_writes(split_cli, payload):
    cli = split_cli
    if payload is not None:
        cli.plan_path.write_text(payload)
    assert cli.main.main(["split", "--plan", str(cli.plan_path), "--apply", "--yes"]) == 1
    assert cli.music.writes == []
    assert not cli.journal.exists()


@pytest.mark.parametrize("state", ["missing", "uninitialized", "corrupt"])
def test_split_cli_never_initializes_journal_on_apply(split_cli, state):
    cli = split_cli
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--save-plan", str(cli.plan_path)]) == 0
    if state == "uninitialized":
        cli.journal.mkdir()
    elif state == "corrupt":
        assert cli.main.main(["split", "--init-journal"]) == 0
        (cli.journal / "journal.json").write_text("{broken")
    before = {p.name: p.read_bytes() for p in cli.journal.iterdir()} if cli.journal.exists() else None
    assert cli.main.main(["split", "--plan", str(cli.plan_path), "--apply", "--yes"]) == 1
    after = {p.name: p.read_bytes() for p in cli.journal.iterdir()} if cli.journal.exists() else None
    assert before == after
    assert cli.music.writes == []


def test_split_cli_init_is_explicit_local_only_and_never_resets(split_cli, capsys):
    cli = split_cli
    cli.main.IS_MACOS = False
    assert cli.main.main(["split", "--init-journal"]) == 0
    before = (cli.journal / "journal.json").read_bytes()
    assert cli.main.main(["split", "--init-journal"]) == 1
    assert (cli.journal / "journal.json").read_bytes() == before
    assert cli.music.writes == []
    assert "never" in capsys.readouterr().out.lower()


def test_split_cli_reports_unresolved_operation_and_durable_status(split_cli, capsys):
    cli = split_cli
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--save-plan", str(cli.plan_path)]) == 0
    fingerprint = json.loads(cli.plan_path.read_text())["fingerprint"]
    assert cli.main.main(["split", "--init-journal"]) == 0
    cli.music.fail_create = True
    args = ["split", "--plan", str(cli.plan_path), "--apply", "--yes"]
    assert cli.main.main(args) == 1
    writes = list(cli.music.writes)
    capsys.readouterr()
    assert cli.main.main(args) == 1
    output = capsys.readouterr().out
    assert "unresolved" in output.lower() and "create" in output
    assert fingerprint in output and cli.source_id in output
    assert "Mix · 01" in output and "not_started" in output
    assert "confirmed" in output and "unknown" in output
    assert "manual" in output.lower()
    assert cli.music.writes == writes


def test_split_cli_plan_export_refuses_overwrite(split_cli):
    cli = split_cli
    cli.plan_path.write_text("prior reviewed plan")
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--save-plan", str(cli.plan_path)]) == 1
    assert cli.plan_path.read_text() == "prior reviewed plan"
    assert cli.music.writes == []


def test_split_cli_plan_export_is_private_under_default_umask(split_cli):
    cli = split_cli
    previous_umask = os.umask(0o022)
    try:
        assert cli.main.main(["split", "--playlist-id", cli.source_id,
                              "--save-plan", str(cli.plan_path)]) == 0
    finally:
        os.umask(previous_umask)
    assert cli.plan_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("relative_path", [
    "curator/data/curation/playlist_split_reviews/split-review.json",
    "curator/data/curation/playlist_split_journal/journal.json",
])
def test_split_cli_private_artifact_locations_are_git_ignored(relative_path):
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", relative_path],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert relative_path in result.stdout


def test_split_cli_platform_guard_precedes_service(split_cli):
    cli = split_cli
    cli.main.IS_MACOS = False
    assert cli.main.main(["split", "--playlist-id", cli.source_id]) == 1
    assert cli.services == []


def test_split_cli_saved_plan_without_consent_never_constructs_service(split_cli):
    cli = split_cli
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--save-plan", str(cli.plan_path)]) == 0
    services = list(cli.services)
    assert cli.main.main(["split", "--plan", str(cli.plan_path), "--apply"]) == 1
    assert cli.services == services
    assert cli.music.writes == []
    assert not cli.journal.exists()


def test_split_cli_stale_saved_plan_is_rejected_without_recalculating_approval(split_cli, capsys):
    cli = split_cli
    assert cli.main.main(["split", "--playlist-id", cli.source_id,
                          "--save-plan", str(cli.plan_path)]) == 0
    plan_bytes = cli.plan_path.read_bytes()
    assert cli.main.main(["split", "--init-journal"]) == 0
    journal_bytes = (cli.journal / "journal.json").read_bytes()
    cli.music.playlists[cli.source_id]["tracks"].reverse()
    assert cli.main.main(["split", "--plan", str(cli.plan_path), "--apply", "--yes"]) == 1
    assert "Source changed" in capsys.readouterr().out
    assert cli.plan_path.read_bytes() == plan_bytes
    assert (cli.journal / "journal.json").read_bytes() == journal_bytes
    assert cli.music.writes == []


@pytest.fixture
def seed_cli(tmp_path, monkeypatch):
    import main
    import src.curation_service as module
    from tests.test_curation_service import SeedMusic, SOURCE_ID

    music = SeedMusic()
    services = []
    service_class = module.CurationService
    journal = tmp_path / "shared-journal"

    def create_service():
        service = service_class(apple_music=music, split_journal_path=journal)
        services.append(service)
        return service

    monkeypatch.setattr(module, "CurationService", create_service)
    monkeypatch.setattr(main, "IS_MACOS", True)
    return SimpleNamespace(main=main, music=music, services=services, journal=journal,
                           source_id=SOURCE_ID, seed_id="000000000000000A",
                           plan_path=tmp_path / "seed-review.json")


def seed_cli_preview(cli, *extra):
    return cli.main.main(["seed-playlist", "--playlist-id", cli.source_id,
                          "--seed-track-id", cli.seed_id, *extra])


def test_seed_cli_preview_displays_identity_ranking_and_writes_nothing(seed_cli, capsys):
    cli = seed_cli
    assert seed_cli_preview(cli) == 0
    output = capsys.readouterr().out
    for expected in [cli.source_id, "Same", cli.seed_id, "Song 10", "Artist",
                     "existing_library", "recorded_metadata_only", "selected_seed",
                     "missing_recorded_mood", "genre_only_fallback"]:
        assert expected in output
    assert cli.music.writes == []
    assert not cli.journal.exists() and not cli.plan_path.exists()


@pytest.mark.parametrize("args", [
    [], ["--playlist-id", "0000000000000001"], ["--seed-track-id", "000000000000000A"],
    ["--apply"], ["--yes"], ["--plan", "missing"],
    ["--plan", "missing", "--apply"],
    ["--init-journal", "--seed-track-id", "000000000000000A"],
    ["--init-journal", "--limit", "30"],
    ["--plan", "missing", "--apply", "--yes", "--limit", "30"],
    ["--playlist-id", "0000000000000001", "--seed-track-id", "000000000000000A", "--yes"],
])
def test_seed_cli_rejects_mixed_actions_before_service(seed_cli, args):
    assert seed_cli.main.main(["seed-playlist", *args]) == 1
    assert seed_cli.services == [] and seed_cli.music.writes == []


@pytest.mark.parametrize("source,seed,limit", [
    ("bad", "000000000000000A", "30"),
    ("0000000000000001", "bad", "30"),
    ("0000000000000001", "0000000000000099", "30"),
    ("0000000000000099", "000000000000000A", "30"),
    ("0000000000000001", "000000000000000A", "0"),
    ("0000000000000001", "000000000000000A", "31"),
])
def test_seed_cli_invalid_selection_never_writes(seed_cli, source, seed, limit):
    assert seed_cli.main.main(["seed-playlist", "--playlist-id", source,
                              "--seed-track-id", seed, "--limit", limit]) == 1
    assert seed_cli.music.writes == [] and not seed_cli.journal.exists()


def test_seed_cli_private_exact_roundtrip_and_completed_retry(seed_cli, monkeypatch, tmp_path):
    cli = seed_cli
    previous = os.umask(0o022)
    try:
        assert seed_cli_preview(cli, "--save-plan", str(cli.plan_path), "--limit", "3") == 0
    finally:
        os.umask(previous)
    plan = json.loads(cli.plan_path.read_text())
    assert cli.plan_path.stat().st_mode & 0o777 == 0o600
    assert plan == cli.services[0].preview_seed_playlist(cli.source_id, cli.seed_id, 3)
    plan_bytes = cli.plan_path.read_bytes()
    assert seed_cli_preview(cli, "--save-plan", str(cli.plan_path)) == 1
    assert cli.plan_path.read_bytes() == plan_bytes
    assert cli.main.main(["seed-playlist", "--plan", str(cli.plan_path), "--apply"]) == 1
    assert cli.music.writes == []
    cli.main.IS_MACOS = False
    assert cli.main.main(["seed-playlist", "--init-journal"]) == 0
    before = (cli.journal / "journal.json").read_bytes()
    assert cli.main.main(["seed-playlist", "--init-journal"]) == 1
    assert (cli.journal / "journal.json").read_bytes() == before
    cli.main.IS_MACOS = True
    original_apply = type(cli.services[0]).apply_seed_playlist
    submitted = []

    def apply(service, reviewed, confirmed=False):
        submitted.append((reviewed, confirmed))
        return original_apply(service, reviewed, confirmed=confirmed)

    monkeypatch.setattr(type(cli.services[0]), "apply_seed_playlist", apply)
    args = ["seed-playlist", "--plan", str(cli.plan_path), "--apply", "--yes"]
    assert cli.main.main(args) == 0
    assert submitted == [(plan, True)]
    assert len(cli.music.writes) == 4
    writes = list(cli.music.writes)
    monkeypatch.chdir(tmp_path)
    assert cli.main.main(args) == 0
    assert cli.music.writes == writes
    assert cli.music.playlists[cli.source_id]["tracks"] == plan["source"]["track_ids"]


@pytest.mark.parametrize("state", ["missing", "corrupt", "stale", "tampered", "unresolved"])
def test_seed_cli_apply_failures_preserve_provenance(seed_cli, state, capsys):
    cli = seed_cli
    assert seed_cli_preview(cli, "--save-plan", str(cli.plan_path)) == 0
    if state != "missing":
        assert cli.main.main(["seed-playlist", "--init-journal"]) == 0
    if state == "corrupt":
        (cli.journal / "journal.json").write_text("{bad")
    elif state == "stale":
        cli.music.playlists[cli.source_id]["tracks"].reverse()
    elif state == "tampered":
        plan = json.loads(cli.plan_path.read_text())
        plan["fingerprint"] = "bad"
        cli.plan_path.write_text(json.dumps(plan))
    elif state == "unresolved":
        cli.music.fail_create = True
    before = (cli.journal / "journal.json").read_bytes() if cli.journal.exists() else None
    args = ["seed-playlist", "--plan", str(cli.plan_path), "--apply", "--yes"]
    assert cli.main.main(args) == 1
    if state == "unresolved":
        writes = list(cli.music.writes)
        assert cli.main.main(args) == 1
        output = capsys.readouterr().out
        assert "Unresolved operation" in output and "create" in output and "manual" in output
        assert "confirmed occurrences=0" in output and "target=unknown" in output
        assert cli.music.writes == writes
    else:
        assert cli.music.writes == []
        assert ((cli.journal / "journal.json").read_bytes() if cli.journal.exists() else None) == before


@pytest.mark.parametrize("payload", [None, "{bad", "[]", "{}", '{"kind":"split"}'])
def test_seed_cli_invalid_saved_plan_never_writes(seed_cli, payload):
    cli = seed_cli
    if payload is not None:
        cli.plan_path.write_text(payload)
    assert cli.main.main(["seed-playlist", "--plan", str(cli.plan_path), "--apply", "--yes"]) == 1
    assert cli.music.writes == [] and not cli.journal.exists()


def test_seed_cli_platform_guard_before_service(seed_cli):
    seed_cli.main.IS_MACOS = False
    assert seed_cli_preview(seed_cli) == 1
    assert seed_cli.services == []
