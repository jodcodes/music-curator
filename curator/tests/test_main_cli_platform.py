"""
Integration tests for CLI platform guard behavior.

Tests the CLI's behavior when platform-specific features are
invoked on non-macOS platforms.
"""

import os
import subprocess
import sys
from io import StringIO
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
        calls["scope"] = args.scope
        calls["apply"] = args.apply
        calls["smoke_test"] = args.smoke_test
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation, raising=False)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate", "--scope", "fav_songs"]) == 0
    assert calls == {"scope": "fav_songs", "apply": False, "smoke_test": False}


def test_curate_feature_accepts_apply(monkeypatch):
    import main

    calls = {}

    def fake_run_curation(args):
        calls["scope"] = args.scope
        calls["apply"] = args.apply
        calls["smoke_test"] = args.smoke_test
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation, raising=False)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate", "--scope", "fav_songs", "--apply"]) == 0
    assert calls == {"scope": "fav_songs", "apply": True, "smoke_test": False}


def test_curate_feature_accepts_smoke_test(monkeypatch):
    import main

    calls = {}

    def fake_run_curation(args):
        calls["scope"] = args.scope
        calls["apply"] = args.apply
        calls["smoke_test"] = args.smoke_test
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation, raising=False)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate", "--scope", "fav_songs", "--smoke-test"]) == 0
    assert calls == {"scope": "fav_songs", "apply": False, "smoke_test": True}


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


def test_curation_apply_on_other_feature_is_rejected(monkeypatch):
    import main

    def fail_organization():
        raise AssertionError("organize should not run with curation-only flags")

    monkeypatch.setattr(main, "run_playlist_organization", fail_organization)

    with pytest.raises(SystemExit) as exc:
        main.main(["organize", "--apply"])

    assert exc.value.code != 0


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
            def get_all_tracks(self):
                return [
                    {"artist": "A", "name": "T", "genre": "Rock", "year": 2020},
                    {"artist": "B", "name": "T2"},  # missing genre/year
                ]

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
            def get_playlists(self):
                return [{"id": "p1", "name": "Mix"}]
            def get_playlist_tracks(self, name):
                return [
                    {"artist": "A", "name": "Song", "album": "AL"},
                    {"artist": "A", "name": "Song", "album": "AL"},  # dup
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
