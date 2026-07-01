from pathlib import Path
from datetime import datetime
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.apple_music_structure import (
    AppleMusicChange,
    AppleMusicStructureApplier,
    AppleMusicStructurePlanner,
)
from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
    TemperBucket,
)


def fav_assignment(track_id: str, genre: str, temper: TemperBucket) -> CurationAssignment:
    return CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id=track_id,
        item_name=f"Track {track_id}",
        genre=genre,
        temperament=temper,
        source=AssignmentSource.AUTO,
        confidence=0.8,
    )


def playlist_assignment(item_id: str, genre: str, temper: TemperBucket) -> CurationAssignment:
    return CurationAssignment(
        item_type=AssignmentType.PLAYLIST,
        item_id=item_id,
        item_name=f"Playlist {item_id}",
        genre=genre,
        temperament=temper,
        source=AssignmentSource.AUTO,
        confidence=0.8,
    )


def test_change_to_dict_returns_path_copy():
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    payload = change.to_dict()
    payload["path"].append("Mutated")

    assert payload["path"] == ["Fav Songs", "Mutated"]
    assert change.path == ("Fav Songs",)


def test_plan_creates_fav_folder_genre_folder_playlist_and_copy():
    planner = AppleMusicStructurePlanner()
    changes = planner.plan_fav_tracks(
        [fav_assignment("1", "hiphop", TemperBucket.FROLIC)]
    )

    assert AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs") in changes
    assert AppleMusicChange(
        "ensure_playlist",
        ["Fav Songs", "Fav Hip Hop & RnB"],
        "Ensure playlist Fav Hip Hop & RnB",
    ) in changes
    assert AppleMusicChange(
        "copy_track",
        ["1", "Fav Songs", "Fav Hip Hop & RnB"],
        "Copy Track 1 to Fav Hip Hop & RnB",
    ) in changes


def test_plan_deduplicates_folder_and_playlist_changes():
    planner = AppleMusicStructurePlanner()
    changes = planner.plan_fav_tracks(
        [
            fav_assignment("1", "hiphop", TemperBucket.FROLIC),
            fav_assignment("2", "hiphop", TemperBucket.FROLIC),
        ]
    )

    ensure_playlist = [c for c in changes if c.action == "ensure_playlist"]
    copy_track = [c for c in changes if c.action == "copy_track"]

    assert len(ensure_playlist) == 1
    assert len(copy_track) == 2


def test_plan_stale_fav_track_removals_only_removes_existing_non_desired_tracks():
    planner = AppleMusicStructurePlanner()

    changes = planner.plan_stale_fav_track_removals(
        [
            {"persistent_id": "keep", "name": "Keep", "target_playlist": "Rock"},
            {"persistent_id": "stale", "name": "Stale", "target_playlist": "Rock"},
            {"persistent_id": "stale", "name": "Stale", "target_playlist": "Rock"},
            {"persistent_id": "missing-playlist", "name": "No Playlist"},
        ],
        ["keep"],
    )

    assert changes == [
        AppleMusicChange(
            "remove_track",
            ["stale", "Fav Songs", "Rock"],
            "Remove stale Stale from Rock",
        )
    ]


def test_plan_ignores_non_fav_track_assignments():
    planner = AppleMusicStructurePlanner()

    changes = planner.plan_fav_tracks(
        [playlist_assignment("playlist-1", "hiphop", TemperBucket.FROLIC)]
    )

    assert changes == []


def test_plan_deduplicates_structural_changes_but_keeps_distinct_track_copies():
    planner = AppleMusicStructurePlanner()
    changes = planner.plan_fav_tracks(
        [
            fav_assignment("1", "hiphop", TemperBucket.FROLIC),
            fav_assignment("2", "hiphop", TemperBucket.FROLIC),
        ]
    )

    ensure_root_folder = [
        c for c in changes if c.action == "ensure_folder" and c.path == ("Fav Songs",)
    ]
    ensure_playlist = [c for c in changes if c.action == "ensure_playlist"]
    copy_track = [c for c in changes if c.action == "copy_track"]

    assert len(ensure_root_folder) == 1
    assert len(ensure_playlist) == 1
    assert len(copy_track) == 2


def test_applier_rejects_without_confirmation(tmp_path):
    script_path = tmp_path / "curation_structure.js"
    script_path.write_text("// test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    with patch("src.apple_music_structure.subprocess.run") as run:
        result = applier.apply_changes([change], confirmed=False)

    run.assert_not_called()
    assert result["success"] is False
    assert result["error"] == "Confirmation required"
    assert result["applied"] == 0
    assert result["failed"] == 0


def test_applier_runs_confirmed_changes_with_applescript(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.return_value = SimpleNamespace(returncode=0, stdout="SUCCESS", stderr="")
        result = applier.apply_changes([change], confirmed=True)

    run.assert_called_once_with(
        [
            "osascript",
            str(script_path),
            "ensure_folder",
            "Fav Songs",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result["success"] is True
    assert result["applied"] == 1
    assert result["failed"] == 0


def test_applier_records_subprocess_failures(tmp_path):
    script_path = tmp_path / "curation_structure.js"
    script_path.write_text("// test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.return_value = SimpleNamespace(
            returncode=1,
            stdout="partial output\n",
            stderr="failed to create folder\n",
        )
        result = applier.apply_changes([change], confirmed=True)

    assert result["success"] is False
    assert result["applied"] == 0
    assert result["failed"] == 1
    assert result["errors"] == [
        {
            "change": change.to_dict(),
            "stdout": "partial output",
            "stderr": "failed to create folder",
        }
    ]


def test_applier_stops_after_first_failed_write(tmp_path):
    script_path = tmp_path / "curation_structure.js"
    script_path.write_text("// test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    folder_change = AppleMusicChange(
        "ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs"
    )
    copy_change = AppleMusicChange(
        "copy_track",
        ["track-1", "Fav Songs", "Hip Hop & RnB", "Fav Hip Hop & RnB Frolic"],
        "Copy track",
    )

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(
                returncode=1,
                stdout="partial output\n",
                stderr="failed to create folder\n",
            ),
            SimpleNamespace(returncode=0, stdout="SUCCESS\n", stderr=""),
        ]
        result = applier.apply_changes(
            [folder_change, copy_change], confirmed=True
        )

    assert run.call_count == 1
    assert result["success"] is False
    assert result["applied"] == 0
    assert result["failed"] == 1
    assert result["errors"] == [
        {
            "change": folder_change.to_dict(),
            "stdout": "partial output",
            "stderr": "failed to create folder",
        }
    ]


def test_applier_records_timeout_failures(tmp_path):
    script_path = tmp_path / "curation_structure.js"
    script_path.write_text("// test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = subprocess.TimeoutExpired(
            cmd=["osascript"],
            timeout=120,
            output="partial output\n",
            stderr="timed out\n",
        )
        result = applier.apply_changes([change], confirmed=True)

    assert result["success"] is False
    assert result["applied"] == 0
    assert result["failed"] == 1
    assert result["errors"] == [
        {
            "change": change.to_dict(),
            "stdout": "partial output",
            "stderr": "timed out",
        }
    ]


def test_applier_records_os_errors(tmp_path):
    script_path = tmp_path / "curation_structure.js"
    script_path.write_text("// test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = OSError("osascript unavailable")
        result = applier.apply_changes([change], confirmed=True)

    assert result["success"] is False
    assert result["applied"] == 0
    assert result["failed"] == 1
    assert result["errors"] == [
        {
            "change": change.to_dict(),
            "stdout": "",
            "stderr": "osascript unavailable",
        }
    ]


def test_applier_reports_missing_script_and_rejects_directories(tmp_path):
    script_path = tmp_path / "script_directory"
    script_path.mkdir()
    applier = AppleMusicStructureApplier(script_path=str(script_path))
    change = AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")

    with patch("src.apple_music_structure.subprocess.run") as run:
        result = applier.apply_changes([change], confirmed=True)

    run.assert_not_called()
    assert result["success"] is False
    assert result["error"].startswith("Script not found:")
    assert result["applied"] == 0
    assert result["failed"] == 0


def test_applier_smoke_test_copies_once_skips_duplicate_and_cleans_up(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: track copied", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: track already exists", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
        ]

        result = applier.run_smoke_test("track-1", stamp="20260609-000000")

    assert result["success"] is True
    assert result["track_id"] == "track-1"
    assert result["root"] == "__Codex Curation Smoke Test 20260609-000000"
    assert result["genre"] == "Smoke Genre 20260609-000000"
    assert result["playlist"] == "Smoke One Track 20260609-000000"
    assert result["copied"] == 1
    assert result["duplicate_skipped"] is True
    assert result["leftovers"] == {"root": 0, "genre": 0, "playlist": 0}
    assert result["apply_result"]["applied"] == 5
    assert run.call_count == 11


def test_applier_smoke_test_cleans_up_when_apply_raises(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = [
            RuntimeError("unexpected apply failure"),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
        ]

        result = applier.run_smoke_test("track-1", stamp="20260609-apply-raises")

    assert result["success"] is False
    assert result["copied"] == 0
    assert result["duplicate_skipped"] is False
    assert "unexpected apply failure" in result["error"]
    assert result["leftovers"] == {"root": 0, "genre": 0, "playlist": 0}
    assert run.call_count == 7


def test_applier_smoke_test_reports_cleanup_and_count_failures(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: track copied", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: track already exists", stderr=""),
            subprocess.TimeoutExpired(cmd=["osascript"], timeout=60),
            OSError("cleanup unavailable"),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            subprocess.TimeoutExpired(cmd=["osascript"], timeout=60),
            OSError("count unavailable"),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
        ]

        result = applier.run_smoke_test("track-1", stamp="20260609-cleanup-fails")

    assert result["success"] is False
    assert result["copied"] == 1
    assert result["duplicate_skipped"] is True
    assert result["leftovers"] == {"root": -1, "genre": -1, "playlist": 0}
    assert len(result["cleanup_errors"]) == 4


def test_applier_smoke_test_default_stamps_are_collision_resistant(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))

    responses = [
        SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
        SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
        SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
        SimpleNamespace(returncode=0, stdout="SUCCESS: track copied", stderr=""),
        SimpleNamespace(returncode=0, stdout="SUCCESS: track already exists", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=0, stdout="0", stderr=""),
        SimpleNamespace(returncode=0, stdout="0", stderr=""),
        SimpleNamespace(returncode=0, stdout="0", stderr=""),
    ]

    with (
        patch("src.apple_music_structure.datetime") as datetime_class,
        patch("src.apple_music_structure.subprocess.run") as run,
    ):
        datetime_class.now.return_value = datetime(2026, 6, 9, 0, 0, 0)
        run.side_effect = responses + responses

        first = applier.run_smoke_test("track-1")
        second = applier.run_smoke_test("track-1")

    assert first["root"] != second["root"]
    assert first["root"].startswith("__Codex Curation Smoke Test 20260609-000000-")
    assert second["root"].startswith("__Codex Curation Smoke Test 20260609-000000-")


def test_applier_smoke_test_classifies_copy_results_from_copy_stdout(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test script", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: playlist touched", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: duplicate touched", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
        ]

        result = applier.run_smoke_test("track-1", stamp="20260609-copy-classify")

    assert result["success"] is False
    assert result["copied"] == 0
    assert result["duplicate_skipped"] is False


def test_applescript_remove_track_is_limited_to_fav_songs_root():
    script = Path("src/scripts/curation_structure.applescript").read_text(
        encoding="utf-8"
    )

    assert 'actionName is "remove_track"' in script
    assert 'if rootName is not "Fav Songs" then' in script
    assert 'remove_track is only allowed under Fav Songs' in script


def test_applescript_copy_track_searches_favourite_songs_before_library():
    script = Path("src/scripts/curation_structure.applescript").read_text(
        encoding="utf-8"
    )

    favourite_lookup = 'playlist "Favourite Songs"'
    library_lookup = "item 1 of library playlists"
    assert favourite_lookup in script
    assert library_lookup in script
    assert script.index(favourite_lookup) < script.index(library_lookup)


def test_applescript_playlist_lookup_validates_full_root_genre_path():
    script = Path("src/scripts/curation_structure.applescript").read_text(
        encoding="utf-8"
    )

    assert "findUniqueUserPlaylistByFullPath(playlistName, genreName, rootName)" in script
    assert "name of parent of candidate is genreName" in script
    assert "name of parent of parent of candidate is rootName" in script
    assert "findUserPlaylistByNameAndParent(playlistName, genreName)" not in script


def test_applescript_root_folder_lookup_fails_on_ambiguous_matches():
    script = Path("src/scripts/curation_structure.applescript").read_text(
        encoding="utf-8"
    )

    root_handler = script[
        script.index("on ensureRootFolder(rootName)") : script.index(
            "end ensureRootFolder"
        )
    ]
    assert "if (count of matches) > 1 then" in root_handler
    assert 'error "Ambiguous root folder' in root_handler
    assert "return item 1 of matches" not in root_handler


def test_applescript_nested_lookup_fails_on_ambiguous_path_matches():
    script = Path("src/scripts/curation_structure.applescript").read_text(
        encoding="utf-8"
    )

    assert "findUniqueFolderByNameAndParent" in script
    assert "findUniqueUserPlaylistByFullPath" in script
    assert 'error "Ambiguous folder path' in script
    assert 'error "Ambiguous playlist path' in script
    assert "findFolderByNameAndParent" not in script
    assert "findUserPlaylistByFullPath" not in script


def test_curation_structure_no_arg_guard_returns_fast_error():
    if shutil.which("osascript") is None:
        pytest.skip("osascript is not available")

    result = subprocess.run(
        [
            "osascript",
            "src/scripts/curation_structure.applescript",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ERROR: action and path required"
