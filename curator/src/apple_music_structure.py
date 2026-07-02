from __future__ import annotations

import subprocess
import tempfile
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .curation_models import AssignmentType, CurationAssignment


def _strip_process_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace").strip()
    return str(value).strip()


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass(frozen=True)
class AppleMusicChange:
    action: str
    path: Sequence[str]
    description: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "path": list(self.path),
            "description": self.description,
        }


class AppleMusicStructurePlanner:
    def plan_fav_tracks(
        self, assignments: Iterable[CurationAssignment]
    ) -> list[AppleMusicChange]:
        changes: list[AppleMusicChange] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()

        def add_change(action: str, path: Sequence[str], description: str) -> None:
            key = (action, tuple(path))
            if key in seen:
                return
            seen.add(key)
            changes.append(AppleMusicChange(action, path, description))

        for assignment in assignments:
            if assignment.item_type not in {
                AssignmentType.FAV_TRACK,
                AssignmentType.TEMPER_TRACK,
            }:
                continue

            target_path = assignment.target_path()
            root = target_path[0]
            playlist_name = target_path[-1]
            add_change("ensure_folder", [root], f"Ensure folder {root}")
            if len(target_path) == 3:
                genre_folder = target_path[1]
                add_change(
                    "ensure_folder",
                    [root, genre_folder],
                    f"Ensure folder {root} / {genre_folder}",
                )
                playlist_path = [root, genre_folder, playlist_name]
            else:
                playlist_path = [root, playlist_name]
            add_change(
                "ensure_playlist",
                playlist_path,
                f"Ensure playlist {playlist_name}",
            )
            add_change(
                "copy_track",
                [assignment.item_id, *playlist_path],
                f"Copy {assignment.item_name} to {playlist_name}",
            )

        return changes

    def plan_stale_fav_track_removals(
        self, existing_tracks: Iterable[dict[str, Any]], desired_track_ids: Iterable[str]
    ) -> list[AppleMusicChange]:
        desired = {str(track_id).strip() for track_id in desired_track_ids if str(track_id).strip()}
        changes: list[AppleMusicChange] = []
        seen: set[tuple[str, str]] = set()

        for track in existing_tracks:
            track_id = str(track.get("persistent_id") or track.get("id") or "").strip()
            playlist_name = str(track.get("target_playlist") or "").strip()
            if not track_id or not playlist_name or track_id in desired:
                continue
            key = (track_id, playlist_name)
            if key in seen:
                continue
            seen.add(key)
            item_name = str(track.get("name") or track.get("title") or track_id)
            changes.append(
                AppleMusicChange(
                    "remove_track",
                    [track_id, "Fav Songs", playlist_name],
                    f"Remove stale {item_name} from {playlist_name}",
                )
            )

        return changes


class AppleMusicStructureApplier:
    def __init__(self, script_path: str | None = None) -> None:
        if script_path is None:
            script_path = str(
                Path(__file__).parent / "scripts" / "curation_structure.applescript"
            )
        self.script_path = str(script_path)

    def apply_changes(
        self, changes: Iterable[AppleMusicChange], confirmed: bool
    ) -> dict[str, Any]:
        if not confirmed:
            return {
                "success": False,
                "error": "Confirmation required",
                "applied": 0,
                "failed": 0,
            }

        if not Path(self.script_path).is_file():
            return {
                "success": False,
                "error": f"Script not found: {self.script_path}",
                "applied": 0,
                "failed": 0,
            }

        applied = 0
        failed = 0
        errors: list[dict[str, Any]] = []

        for change in changes:
            command = [
                "osascript",
                self.script_path,
                change.action,
                *change.path,
            ]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                stdout = _strip_process_output(result.stdout)
                stderr = _strip_process_output(result.stderr)
            except subprocess.TimeoutExpired as exc:
                failed += 1
                errors.append(
                    {
                        "change": change.to_dict(),
                        "stdout": _strip_process_output(exc.output),
                        "stderr": _strip_process_output(exc.stderr) or str(exc),
                    }
                )
                break
            except OSError as exc:
                failed += 1
                errors.append(
                    {
                        "change": change.to_dict(),
                        "stdout": "",
                        "stderr": str(exc),
                    }
                )
                break

            if result.returncode == 0 and "SUCCESS" in stdout:
                applied += 1
                continue

            failed += 1
            errors.append(
                {
                    "change": change.to_dict(),
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            break

        return {
            "success": failed == 0,
            "applied": applied,
            "failed": failed,
            "errors": errors,
        }

    def apply_fav_tracks_bulk(
        self, assignments: Iterable[CurationAssignment], confirmed: bool
    ) -> dict[str, Any]:
        if not confirmed:
            return {"success": False, "error": "Confirmation required", "applied": 0, "failed": 0}

        rows: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for assignment in assignments:
            if assignment.item_type is not AssignmentType.FAV_TRACK:
                continue
            target_path = assignment.target_path()
            if len(target_path) != 2 or target_path[0] != "Fav Songs":
                continue
            key = (assignment.item_id, target_path[1])
            if key in seen:
                continue
            seen.add(key)
            rows.append(key)

        if not rows:
            return {"success": True, "applied": 0, "failed": 0, "stdout": ""}

        script_path = Path(__file__).parent / "scripts" / "bulk_fav_songs.applescript"
        if not script_path.is_file():
            return {"success": False, "error": f"Script not found: {script_path}", "applied": 0, "failed": 0}

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            data_path = Path(handle.name)
            for track_id, playlist_name in rows:
                safe_playlist = playlist_name.replace("\t", " ").replace("\n", " ")
                handle.write(f"{track_id}\t{safe_playlist}\n")

        try:
            result = subprocess.run(
                ["osascript", str(script_path), str(data_path)],
                capture_output=True,
                text=True,
                timeout=900,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "success": False,
                "applied": 0,
                "failed": len(rows),
                "stdout": _strip_process_output(exc.output),
                "stderr": _strip_process_output(exc.stderr) or str(exc),
            }
        finally:
            try:
                data_path.unlink()
            except OSError:
                pass

        stdout = _strip_process_output(result.stdout)
        stderr = _strip_process_output(result.stderr)
        success = result.returncode == 0 and stdout.startswith("SUCCESS")
        return {
            "success": success,
            "applied": len(rows) if success else 0,
            "failed": 0 if success else len(rows),
            "stdout": stdout,
            "stderr": stderr,
        }

    def run_smoke_test(
        self, track_id: str, stamp: str | None = None
    ) -> dict[str, Any]:
        stamp = stamp or (
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:12]}"
        )
        root = f"__Codex Curation Smoke Test {stamp}"
        genre = f"Smoke Genre {stamp}"
        playlist = f"Smoke One Track {stamp}"

        changes = [
            AppleMusicChange("ensure_folder", [root], f"Ensure folder {root}"),
            AppleMusicChange(
                "ensure_folder",
                [root, genre],
                f"Ensure folder {root} / {genre}",
            ),
            AppleMusicChange(
                "ensure_playlist",
                [root, genre, playlist],
                f"Ensure playlist {playlist}",
            ),
            AppleMusicChange(
                "copy_track",
                [track_id, root, genre, playlist],
                f"Copy smoke-test track to {playlist}",
            ),
            AppleMusicChange(
                "copy_track",
                [track_id, root, genre, playlist],
                f"Copy smoke-test track to {playlist} again",
            ),
        ]

        error = None
        try:
            apply_result = self._run_smoke_changes(changes)
        except Exception as exc:  # defensive: cleanup must still run
            error = str(exc)
            apply_result = {
                "success": False,
                "applied": 0,
                "failed": 1,
                "errors": [{"stdout": "", "stderr": str(exc)}],
                "steps": [],
            }
        cleanup_result = self._cleanup_smoke_test(root, genre, playlist)
        leftovers = cleanup_result["leftovers"]
        cleanup_errors = cleanup_result["errors"]
        steps = apply_result.get("steps", [])
        first_copy_stdout = (
            steps[3].get("stdout", "").lower() if len(steps) > 3 else ""
        )
        second_copy_stdout = (
            steps[4].get("stdout", "").lower() if len(steps) > 4 else ""
        )
        copied = 1 if "track copied" in first_copy_stdout else 0
        duplicate_skipped = "track already exists" in second_copy_stdout

        result = {
            "success": bool(apply_result.get("success"))
            and copied == 1
            and duplicate_skipped
            and all(count == 0 for count in leftovers.values())
            and not cleanup_errors,
            "track_id": track_id,
            "root": root,
            "genre": genre,
            "playlist": playlist,
            "copied": copied,
            "duplicate_skipped": duplicate_skipped,
            "leftovers": leftovers,
            "apply_result": apply_result,
            "cleanup_errors": cleanup_errors,
        }
        if error:
            result["error"] = error
        return result

    def _run_smoke_changes(
        self, changes: Sequence[AppleMusicChange]
    ) -> dict[str, Any]:
        if not Path(self.script_path).is_file():
            return {
                "success": False,
                "error": f"Script not found: {self.script_path}",
                "applied": 0,
                "failed": 0,
                "errors": [],
                "steps": [],
            }

        applied = 0
        failed = 0
        errors: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []

        for change in changes:
            step = self._run_smoke_change(change)
            steps.append(step)
            if step["success"]:
                applied += 1
                continue
            failed += 1
            errors.append(
                {
                    "change": change.to_dict(),
                    "stdout": step["stdout"],
                    "stderr": step["stderr"],
                }
            )

        return {
            "success": failed == 0,
            "applied": applied,
            "failed": failed,
            "errors": errors,
            "steps": steps,
        }

    def _run_smoke_change(self, change: AppleMusicChange) -> dict[str, Any]:
        command = [
            "osascript",
            self.script_path,
            change.action,
            *change.path,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
            )
            stdout = _strip_process_output(result.stdout)
            stderr = _strip_process_output(result.stderr)
            return {
                "success": result.returncode == 0 and "SUCCESS" in stdout,
                "action": change.action,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "success": False,
                "action": change.action,
                "stdout": _strip_process_output(exc.output),
                "stderr": _strip_process_output(exc.stderr) or str(exc),
                "returncode": None,
            }
        except OSError as exc:
            return {
                "success": False,
                "action": change.action,
                "stdout": "",
                "stderr": str(exc),
                "returncode": None,
            }

    def _cleanup_smoke_test(
        self, root: str, genre: str, playlist: str
    ) -> dict[str, Any]:
        delete_playlist = f"""
tell application "Music"
    set playlistName to {_applescript_string(playlist)}
    set genreName to {_applescript_string(genre)}
    set rootName to {_applescript_string(root)}
    set matches to every user playlist whose name is playlistName
    repeat with candidate in matches
        try
            if name of parent of candidate is genreName and name of parent of parent of candidate is rootName then
                delete candidate
            end if
        end try
    end repeat
end tell
"""
        delete_genre = f"""
tell application "Music"
    set genreName to {_applescript_string(genre)}
    set rootName to {_applescript_string(root)}
    set matches to every folder playlist whose name is genreName
    repeat with candidate in matches
        try
            if name of parent of candidate is rootName then
                delete candidate
            end if
        end try
    end repeat
end tell
"""
        delete_root = f"""
tell application "Music"
    set rootName to {_applescript_string(root)}
    set matches to every folder playlist whose name is rootName
    repeat with candidate in matches
        try
            delete candidate
        end try
    end repeat
end tell
"""

        errors: list[dict[str, Any]] = []
        for name, script in (
            ("delete_playlist", delete_playlist),
            ("delete_genre", delete_genre),
            ("delete_root", delete_root),
        ):
            error = self._run_cleanup_script(name, script)
            if error:
                errors.append(error)

        leftovers: dict[str, int] = {}
        for name, count in (
            ("root", self._count_smoke_root(root)),
            ("genre", self._count_smoke_genre(root, genre)),
            ("playlist", self._count_smoke_playlist(root, genre, playlist)),
        ):
            leftovers[name] = count["count"]
            errors.extend(count["errors"])

        return {
            "leftovers": leftovers,
            "errors": errors,
        }

    def _run_cleanup_script(self, name: str, script: str) -> dict[str, Any] | None:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "phase": "cleanup",
                "name": name,
                "stdout": _strip_process_output(exc.output),
                "stderr": _strip_process_output(exc.stderr) or str(exc),
            }
        except OSError as exc:
            return {
                "phase": "cleanup",
                "name": name,
                "stdout": "",
                "stderr": str(exc),
            }

        if result.returncode == 0:
            return None
        return {
            "phase": "cleanup",
            "name": name,
            "stdout": _strip_process_output(result.stdout),
            "stderr": _strip_process_output(result.stderr),
        }

    def _run_count_script(self, name: str, script: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "count": -1,
                "errors": [
                    {
                        "phase": "count",
                        "name": name,
                        "stdout": _strip_process_output(exc.output),
                        "stderr": _strip_process_output(exc.stderr) or str(exc),
                    }
                ],
            }
        except OSError as exc:
            return {
                "count": -1,
                "errors": [
                    {
                        "phase": "count",
                        "name": name,
                        "stdout": "",
                        "stderr": str(exc),
                    }
                ],
            }

        try:
            count = int(_strip_process_output(result.stdout))
        except ValueError:
            count = -1

        errors = []
        if result.returncode != 0:
            errors.append(
                {
                    "phase": "count",
                    "name": name,
                    "stdout": _strip_process_output(result.stdout),
                    "stderr": _strip_process_output(result.stderr),
                }
            )
        return {"count": count, "errors": errors}

    def _count_smoke_root(self, root: str) -> dict[str, Any]:
        return self._run_count_script(
            "root",
            f"""
tell application "Music"
    return count of (every folder playlist whose name is {_applescript_string(root)})
end tell
"""
        )

    def _count_smoke_genre(self, root: str, genre: str) -> dict[str, Any]:
        return self._run_count_script(
            "genre",
            f"""
tell application "Music"
    set genreName to {_applescript_string(genre)}
    set rootName to {_applescript_string(root)}
    set remaining to 0
    set matches to every folder playlist whose name is genreName
    repeat with candidate in matches
        try
            if name of parent of candidate is rootName then set remaining to remaining + 1
        end try
    end repeat
    return remaining
end tell
"""
        )

    def _count_smoke_playlist(self, root: str, genre: str, playlist: str) -> dict[str, Any]:
        return self._run_count_script(
            "playlist",
            f"""
tell application "Music"
    set playlistName to {_applescript_string(playlist)}
    set genreName to {_applescript_string(genre)}
    set rootName to {_applescript_string(root)}
    set remaining to 0
    set matches to every user playlist whose name is playlistName
    repeat with candidate in matches
        try
            if name of parent of candidate is genreName and name of parent of parent of candidate is rootName then set remaining to remaining + 1
        end try
    end repeat
    return remaining
end tell
"""
        )
