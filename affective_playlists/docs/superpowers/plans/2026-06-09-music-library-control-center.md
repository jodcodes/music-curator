# Music Library Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the simplified `Fav Songs` Control Center with snapshot-first loading, fast Music.app refresh, a genre x temper matrix, a reversible mini-test gate, and guarded full apply.

**Architecture:** Keep existing curation model/planner behavior, add a small persisted snapshot layer, expose explicit snapshot/refresh/smoke-test endpoints, and replace the current all-at-once curation UI with a focused control center. Music.app reads stay synchronous for phase 1 because the bulk-read path is fast; full apply is moved behind a job-facing API so the UI never blocks on thousands of writes.

**Tech Stack:** Python 3.14, Flask, pytest, AppleScript via `osascript`, vanilla HTML/CSS/JS, existing SQLite/job-store infrastructure.

---

## File Structure

- Create `src/curation_snapshot.py`
  - Owns persisted curation snapshots.
  - Stores and loads JSON snapshots atomically.
  - Calculates freshness metadata.

- Modify `src/curation_service.py`
  - Adds snapshot creation/loading methods.
  - Adds a mini-test method that delegates to the Apple Music apply adapter.
  - Keeps assignment generation in one place.

- Modify `src/apple_music.py`
  - Preserve the live-tested bulk Favourite Songs reader.
  - Avoid per-track AppleScript loops for the curation preview path.

- Modify `src/apple_music_structure.py`
  - Preserve the AppleScript apply adapter.
  - Add `run_smoke_test(track_id)` for the one-track reversible write gate.

- Create `src/scripts/curation_structure.applescript`
  - Productive apply script for folder/playlist creation, copy, duplicate-skip.

- Modify `src/web_server.py`
  - Add snapshot, refresh, smoke-test, and apply-job endpoints.
  - Keep `/api/curation/preview` response-compatible for existing tests and CLI users.

- Modify `web/index.html`
  - Replace the current `Curation Review` markup with the Control Center structure.

- Modify `web/static/js/app.js`
  - Add snapshot-first load.
  - Add refresh, matrix rendering, mini-test gate, and apply-job controls.
  - Stop rendering thousands of track cards on first load.

- Modify `web/static/css/style.css`
  - Add Control Center layout, status rail, matrix, and write-safety panel styles.

- Modify tests:
  - `tests/test_apple_music_folder_structure.py`
  - `tests/test_apple_music_structure.py`
  - `tests/test_curation_service.py`
  - `tests/test_web_server.py`

---

### Task 1: Stabilize Live Apple Music IO Baseline

**Files:**
- Modify: `src/apple_music.py`
- Modify: `src/apple_music_structure.py`
- Create: `src/scripts/curation_structure.applescript`
- Modify: `tests/test_apple_music_folder_structure.py`
- Modify: `tests/test_apple_music_structure.py`
- Modify: `tests/test_curation_service.py`

- [ ] **Step 1: Write or verify the failing fast-reader test**

Ensure `tests/test_apple_music_folder_structure.py` contains this expectation in `test_get_favourite_tracks_normalizes_track_identity`:

```python
script = " ".join(captured["script"].split())
self.assertIn('set targetPlaylist to playlist "Favourite Songs"', script)
self.assertIn("persistent ID of every track of targetPlaylist", script)
self.assertIn("name of every track of targetPlaylist", script)
self.assertNotIn("repeat with trk in tracks of targetPlaylist", script)
self.assertNotIn("composer of trk", script)
self.assertNotIn("duration of trk", script)
self.assertEqual(result[0]["title"], "Track A")
self.assertEqual(result[0]["name"], "Track A")
self.assertEqual(result[0]["persistent_id"], "ABC123")
self.assertEqual(result[1]["genre"], "")
```

- [ ] **Step 2: Run the fast-reader test and verify it fails before implementation**

Run:

```bash
.venv/bin/python -m pytest tests/test_apple_music_folder_structure.py::TestAppleMusicFolderStructure::test_get_favourite_tracks_normalizes_track_identity -q
```

Expected before implementation: FAIL because the script does not use `persistent ID of every track of targetPlaylist`.

- [ ] **Step 3: Implement the bulk Favourite Songs reader**

In `src/apple_music.py`, `get_favourite_tracks()` must call a dedicated `_get_favourite_songs_tracks()` instead of `get_playlist_tracks("Favourite Songs")`.

Use this method body shape:

```python
def get_favourite_tracks(self) -> List[Dict]:
    """Return tracks from Apple Music's Favourite Songs playlist."""
    return [
        self._normalize_track_dict(track)
        for track in self._get_favourite_songs_tracks()
    ]

def _get_favourite_songs_tracks(self) -> List[Dict]:
    """Get only the Favourite Songs fields needed for curation preview."""
    script = """
on cleanText(rawValue)
    try
        set textValue to rawValue as text
    on error
        set textValue to ""
    end try
    set textValue to my replaceText(tab, " ", textValue)
    set textValue to my replaceText(linefeed, " ", textValue)
    set textValue to my replaceText(return, " ", textValue)
    return textValue
end cleanText

on replaceText(findText, replaceTextValue, sourceText)
    set oldDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to findText
    set textItems to text items of sourceText
    set AppleScript's text item delimiters to replaceTextValue
    set sourceText to textItems as text
    set AppleScript's text item delimiters to oldDelimiters
    return sourceText
end replaceText

tell application "Music"
    set trackRows to {}
    set oldDelimiters to AppleScript's text item delimiters
    try
        set targetPlaylist to playlist "Favourite Songs"
        set trackTotal to count of tracks of targetPlaylist
        set trackIDs to persistent ID of every track of targetPlaylist
        set trackNames to name of every track of targetPlaylist
        set trackArtists to artist of every track of targetPlaylist
        set trackGenres to genre of every track of targetPlaylist
        repeat with trackIndex from 1 to trackTotal
            set trackPID to my cleanText(item trackIndex of trackIDs)
            set trackName to my cleanText(item trackIndex of trackNames)
            set trackArtist to my cleanText(item trackIndex of trackArtists)
            set trackGenre to my cleanText(item trackIndex of trackGenres)
            set AppleScript's text item delimiters to tab
            set end of trackRows to {trackPID, trackName, trackArtist, trackGenre} as text
        end repeat
        set AppleScript's text item delimiters to linefeed
        set outputText to trackRows as text
        set AppleScript's text item delimiters to oldDelimiters
        return outputText
    on error errMsg
        set AppleScript's text item delimiters to oldDelimiters
        error errMsg
    end try
end tell
"""
    success, output = self._run_applescript(script)
    if not success:
        raise RuntimeError(f"Failed to load Favourite Songs tracks: {output}")
    if not output:
        return []
    return self._parse_favourite_songs_output(output)

def _parse_favourite_songs_output(self, output: str) -> List[Dict]:
    tracks: List[Dict] = []
    for row in output.splitlines():
        fields = row.split("\t")
        if len(fields) < 4:
            fields.extend([""] * (4 - len(fields)))
        persistent_id, name, artist, genre = fields[:4]
        tracks.append(
            {
                "persistent_id": persistent_id,
                "title": name,
                "name": name,
                "artist": artist,
                "genre": genre,
            }
        )
    return tracks
```

- [ ] **Step 4: Verify the fast-reader test passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_apple_music_folder_structure.py::TestAppleMusicFolderStructure::test_get_favourite_tracks_normalizes_track_identity -q
```

Expected: PASS.

- [ ] **Step 5: Add or verify the AppleScript apply adapter tests**

In `tests/test_apple_music_structure.py`, the confirmed applier test must expect no JXA language flag:

```python
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
```

Also assert the script searches `Favourite Songs` before the library fallback:

```python
script = Path("src/scripts/curation_structure.applescript").read_text(
    encoding="utf-8"
)
favourite_lookup = 'playlist "Favourite Songs"'
library_lookup = "item 1 of library playlists"
assert favourite_lookup in script
assert library_lookup in script
assert script.index(favourite_lookup) < script.index(library_lookup)
```

- [ ] **Step 6: Implement the AppleScript apply path**

In `src/apple_music_structure.py`, default `script_path` must be:

```python
script_path = str(
    Path(__file__).parent / "scripts" / "curation_structure.applescript"
)
```

The command must be:

```python
command = [
    "osascript",
    self.script_path,
    change.action,
    *change.path,
]
```

Create `src/scripts/curation_structure.applescript` with handlers:

- `ensure_folder root`
- `ensure_folder root genre`
- `ensure_playlist root genre playlist`
- `copy_track persistent_id root genre playlist`
- duplicate detection by persistent ID and name/artist fallback
- `Favourite Songs` lookup before library fallback
- returns `SUCCESS: ...` for success and `ERROR: ...` for errors

- [ ] **Step 7: Run focused baseline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_apple_music_structure.py tests/test_apple_music_folder_structure.py tests/test_curation_service.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit baseline**

```bash
git add src/apple_music.py src/apple_music_structure.py src/scripts/curation_structure.applescript tests/test_apple_music_folder_structure.py tests/test_apple_music_structure.py tests/test_curation_service.py
git commit -m "fix: stabilize apple music curation io"
```

---

### Task 2: Add Curation Snapshot Store

**Files:**
- Create: `src/curation_snapshot.py`
- Create: `tests/test_curation_snapshot.py`
- Modify: `src/curation_service.py`

- [ ] **Step 1: Write snapshot store tests**

Create `tests/test_curation_snapshot.py`:

```python
from datetime import datetime, timezone

from src.curation_snapshot import CurationSnapshotStore


def test_snapshot_store_saves_and_loads_scope(tmp_path):
    store = CurationSnapshotStore(tmp_path / "curation_snapshots.json")
    payload = {
        "scope": "fav_songs",
        "total_assignments": 2,
        "total_genres": 1,
        "total_changes": 4,
        "total_skipped": 0,
        "grouped": {"Hip Hop": {"Frolic": [{"item_id": "a"}]}},
    }

    saved = store.save_snapshot("fav_songs", payload)
    loaded = store.load_snapshot("fav_songs")

    assert saved["scope"] == "fav_songs"
    assert saved["total_assignments"] == 2
    assert "created_at" in saved
    assert loaded == saved


def test_snapshot_store_returns_empty_state_when_missing(tmp_path):
    store = CurationSnapshotStore(tmp_path / "curation_snapshots.json")

    loaded = store.load_snapshot("fav_songs")

    assert loaded["scope"] == "fav_songs"
    assert loaded["available"] is False
    assert loaded["total_assignments"] == 0
    assert loaded["total_genres"] == 0
    assert loaded["total_changes"] == 0
    assert loaded["total_skipped"] == 0


def test_snapshot_store_marks_stale_snapshot(tmp_path):
    store = CurationSnapshotStore(tmp_path / "curation_snapshots.json", ttl_seconds=1)
    saved = store.save_snapshot("fav_songs", {"scope": "fav_songs"})
    saved["created_at"] = "2020-01-01T00:00:00+00:00"
    store._write_all({"fav_songs": saved})

    loaded = store.load_snapshot("fav_songs")

    assert loaded["available"] is True
    assert loaded["fresh"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_curation_snapshot.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.curation_snapshot'`.

- [ ] **Step 3: Implement snapshot store**

Create `src/curation_snapshot.py`:

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CurationSnapshotStore:
    def __init__(self, path: str | Path = "data/curation_snapshots.json", ttl_seconds: int = 3600) -> None:
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds

    def load_snapshot(self, scope: str) -> dict[str, Any]:
        data = self._read_all()
        snapshot = data.get(scope)
        if not snapshot:
            return self._empty_snapshot(scope)

        loaded = dict(snapshot)
        loaded["available"] = True
        loaded["fresh"] = self._is_fresh(loaded.get("created_at"))
        return loaded

    def save_snapshot(self, scope: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read_all()
        snapshot = dict(payload)
        snapshot["scope"] = scope
        snapshot["available"] = True
        snapshot["fresh"] = True
        snapshot["created_at"] = datetime.now(timezone.utc).isoformat()
        data[scope] = snapshot
        self._write_all(data)
        return snapshot

    def _empty_snapshot(self, scope: str) -> dict[str, Any]:
        return {
            "scope": scope,
            "available": False,
            "fresh": False,
            "created_at": None,
            "total_assignments": 0,
            "total_genres": 0,
            "total_changes": 0,
            "total_skipped": 0,
            "grouped": {},
            "changes": [],
            "skipped_tracks": [],
        }

    def _is_fresh(self, created_at: Any) -> bool:
        if not created_at:
            return False
        try:
            created = datetime.fromisoformat(str(created_at))
        except ValueError:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
        return age_seconds <= self.ttl_seconds

    def _read_all(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _write_all(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)
```

- [ ] **Step 4: Run snapshot tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_curation_snapshot.py -q
```

Expected: PASS.

- [ ] **Step 5: Wire store into `CurationService` constructor**

Modify `src/curation_service.py` imports:

```python
from src.curation_snapshot import CurationSnapshotStore
```

Modify constructor signature:

```python
snapshot_store: Optional[CurationSnapshotStore] = None,
```

Set instance field:

```python
self.snapshot_store = snapshot_store or CurationSnapshotStore()
```

- [ ] **Step 6: Add service snapshot methods**

In `CurationService`:

```python
def get_fav_songs_snapshot(self) -> Dict[str, Any]:
    return self.snapshot_store.load_snapshot("fav_songs")

def refresh_fav_songs_snapshot(self) -> Dict[str, Any]:
    preview = self.preview_fav_songs()
    snapshot_payload = self._snapshot_payload(preview)
    return self.snapshot_store.save_snapshot("fav_songs", snapshot_payload)

def _snapshot_payload(self, preview: Dict[str, Any]) -> Dict[str, Any]:
    grouped = preview.get("grouped") or {}
    return {
        "scope": "fav_songs",
        "total_assignments": int(preview.get("total_assignments") or 0),
        "total_genres": len(grouped),
        "total_changes": int(preview.get("total_changes") or 0),
        "total_skipped": int(preview.get("total_skipped") or 0),
        "grouped": grouped,
        "changes": preview.get("changes") or [],
        "skipped_tracks": preview.get("skipped_tracks") or [],
    }
```

- [ ] **Step 7: Commit snapshot store**

```bash
git add src/curation_snapshot.py src/curation_service.py tests/test_curation_snapshot.py
git commit -m "feat: add curation snapshot store"
```

---

### Task 3: Add Snapshot And Refresh API

**Files:**
- Modify: `src/web_server.py`
- Modify: `tests/test_web_server.py`

- [ ] **Step 1: Write API tests**

Add tests near existing curation endpoint tests in `tests/test_web_server.py`:

```python
def test_curation_snapshot_returns_cached_state(client, monkeypatch):
    class FakeService:
        def get_fav_songs_snapshot(self):
            return {
                "scope": "fav_songs",
                "available": True,
                "fresh": True,
                "total_assignments": 2,
                "total_genres": 1,
                "total_changes": 4,
                "total_skipped": 0,
                "grouped": {"Hip Hop": {"Frolic": []}},
            }

    monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

    response = client.get("/api/curation/snapshot?scope=fav_songs")

    assert response.status_code == 200
    assert response.get_json()["total_assignments"] == 2


def test_curation_refresh_updates_snapshot(client, monkeypatch):
    class FakeService:
        def refresh_fav_songs_snapshot(self):
            return {
                "scope": "fav_songs",
                "available": True,
                "fresh": True,
                "total_assignments": 4106,
                "total_genres": 139,
                "total_changes": 4430,
                "total_skipped": 0,
                "grouped": {},
            }

    monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

    response = client.post("/api/curation/refresh", json={"scope": "fav_songs"})

    assert response.status_code == 200
    assert response.get_json()["total_genres"] == 139


def test_curation_snapshot_rejects_unsupported_scope(client):
    response = client.get("/api/curation/snapshot?scope=albums")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Unsupported curation scope"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_server.py -q
```

Expected: FAIL with 404 for the new endpoints.

- [ ] **Step 3: Implement API endpoints**

In `src/web_server.py`, add after `curation_preview()`:

```python
@app.route("/api/curation/snapshot", methods=["GET"])
def curation_snapshot():
    """Return the last saved curation snapshot without reading Music.app."""
    try:
        scope = request.args.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        return jsonify(service.get_fav_songs_snapshot())
    except Exception as e:
        logger.error(f"Failed to load curation snapshot: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation/refresh", methods=["POST"])
def curation_refresh():
    """Refresh the curation snapshot from Music.app."""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        return jsonify(service.refresh_fav_songs_snapshot())
    except Exception as e:
        logger.error(f"Failed to refresh curation snapshot: {e}")
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: Run API tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_server.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit API endpoints**

```bash
git add src/web_server.py tests/test_web_server.py
git commit -m "feat: expose curation snapshot api"
```

---

### Task 4: Add Mini-Test Gate API

**Files:**
- Modify: `src/curation_service.py`
- Modify: `src/apple_music_structure.py`
- Modify: `src/web_server.py`
- Modify: `tests/test_curation_service.py`
- Modify: `tests/test_web_server.py`

- [ ] **Step 1: Write service mini-test test**

In `tests/test_curation_service.py`:

```python
class MiniTestAppleMusic:
    def get_favourite_tracks(self):
        return [
            {
                "persistent_id": "track-1",
                "name": "Track A",
                "artist": "Artist A",
                "genre": "Hip-Hop",
            }
        ]


class MiniTestApplier:
    def __init__(self):
        self.calls = []

    def run_smoke_test(self, track_id):
        self.calls.append(track_id)
        return {
            "success": True,
            "track_id": track_id,
            "copied": 1,
            "duplicate_skipped": True,
            "leftovers": {"root": 0, "genre": 0, "playlist": 0},
        }


def test_mini_test_uses_first_favourite_track_and_reports_cleanup():
    applier = MiniTestApplier()
    service = CurationService(
        apple_music=MiniTestAppleMusic(),
        temper_classifier=StaticTemperClassifier(),
        applier=applier,
    )

    result = service.run_fav_songs_smoke_test()

    assert result["success"] is True
    assert result["duplicate_skipped"] is True
    assert result["leftovers"] == {"root": 0, "genre": 0, "playlist": 0}
    assert applier.calls == ["track-1"]
```

- [ ] **Step 2: Run service test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_curation_service.py::test_mini_test_uses_first_favourite_track_and_reports_cleanup -q
```

Expected: FAIL with `AttributeError: 'CurationService' object has no attribute 'run_fav_songs_smoke_test'`.

- [ ] **Step 3: Implement service method**

In `src/curation_service.py`:

```python
def run_fav_songs_smoke_test(self) -> Dict[str, Any]:
    tracks = self.apple_music.get_favourite_tracks()
    for track in tracks:
        track_id = str(track.get("persistent_id") or track.get("id") or "").strip()
        if track_id:
            result = self.applier.run_smoke_test(track_id)
            result["source_track"] = {
                "persistent_id": track_id,
                "name": str(track.get("name") or track.get("title") or "Unknown Track"),
                "artist": str(track.get("artist") or ""),
            }
            return result
    return {
        "success": False,
        "error": "No Favourite Songs track with a stable persistent ID was found",
        "copied": 0,
        "duplicate_skipped": False,
        "leftovers": {},
    }
```

- [ ] **Step 4: Add applier smoke-test method with mocked tests**

In `tests/test_apple_music_structure.py`, add:

```python
def test_applier_smoke_test_runs_reversible_one_track_flow(tmp_path):
    script_path = tmp_path / "curation_structure.applescript"
    script_path.write_text("-- test", encoding="utf-8")
    applier = AppleMusicStructureApplier(script_path=str(script_path))

    with patch("src.apple_music_structure.subprocess.run") as run:
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="SUCCESS: folder ensured root", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: folder ensured root / genre", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: playlist ensured root / genre / playlist", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: track copied to playlist", stderr=""),
            SimpleNamespace(returncode=0, stdout="SUCCESS: track already exists in playlist", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
            SimpleNamespace(returncode=0, stdout="0", stderr=""),
        ]

        result = applier.run_smoke_test("track-1", stamp="20260609-000000")

    assert result["success"] is True
    assert result["copied"] == 1
    assert result["duplicate_skipped"] is True
    assert result["leftovers"] == {"root": 0, "genre": 0, "playlist": 0}
```

- [ ] **Step 5: Implement `run_smoke_test`**

In `src/apple_music_structure.py`, add:

```python
def run_smoke_test(self, track_id: str, stamp: str | None = None) -> dict[str, Any]:
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    root = f"__Codex Curation Smoke Test {stamp}"
    genre = f"Smoke Genre {stamp}"
    playlist = f"Smoke One Track {stamp}"
    changes = [
        AppleMusicChange("ensure_folder", [root], f"Ensure folder {root}"),
        AppleMusicChange("ensure_folder", [root, genre], f"Ensure folder {root} / {genre}"),
        AppleMusicChange("ensure_playlist", [root, genre, playlist], f"Ensure playlist {playlist}"),
        AppleMusicChange("copy_track", [track_id, root, genre, playlist], f"Copy smoke track to {playlist}"),
        AppleMusicChange("copy_track", [track_id, root, genre, playlist], f"Copy smoke track duplicate to {playlist}"),
    ]
    result = self.apply_changes(changes, confirmed=True)
    leftovers = self._cleanup_smoke_test(root, genre, playlist)
    return {
        "success": bool(result.get("success")) and all(value == 0 for value in leftovers.values()),
        "track_id": track_id,
        "root": root,
        "genre": genre,
        "playlist": playlist,
        "copied": 1 if result.get("applied", 0) >= 4 else 0,
        "duplicate_skipped": result.get("applied", 0) >= 5,
        "leftovers": leftovers,
        "apply_result": result,
    }
```

Also import `datetime`:

```python
from datetime import datetime
```

Add `_cleanup_smoke_test` as a small private helper that runs `osascript -e` cleanup/count commands for user playlist, genre folder, and root folder. It must return integer counts:

```python
def _cleanup_smoke_test(self, root: str, genre: str, playlist: str) -> dict[str, int]:
    cleanup_commands = [
        f'tell application "Music" to delete (every user playlist whose name is "{playlist}")',
        f'tell application "Music" to delete (every folder playlist whose name is "{genre}")',
        f'tell application "Music" to delete (every folder playlist whose name is "{root}")',
    ]
    for script in cleanup_commands:
        subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)

    return {
        "root": self._count_music_objects(f'every folder playlist whose name is "{root}"'),
        "genre": self._count_music_objects(f'every folder playlist whose name is "{genre}"'),
        "playlist": self._count_music_objects(f'every user playlist whose name is "{playlist}"'),
    }
```

- [ ] **Step 6: Add smoke-test endpoint**

In `src/web_server.py`:

```python
@app.route("/api/curation/smoke-test", methods=["POST"])
def curation_smoke_test():
    """Run a reversible one-track curation write test."""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        result = service.run_fav_songs_smoke_test()
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error(f"Failed to run curation smoke test: {e}")
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_curation_service.py tests/test_apple_music_structure.py tests/test_web_server.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit mini-test gate**

```bash
git add src/curation_service.py src/apple_music_structure.py src/web_server.py tests/test_curation_service.py tests/test_apple_music_structure.py tests/test_web_server.py
git commit -m "feat: add curation smoke test gate"
```

---

### Task 5: Build Control Center Markup And Styles

**Files:**
- Modify: `web/index.html`
- Modify: `web/static/css/style.css`
- Modify: `tests/test_web_server.py` if static HTML assertions exist

- [ ] **Step 1: Replace curation view markup**

In `web/index.html`, replace the `section id="curation-view"` body with:

```html
<section id="curation-view" class="view">
    <div class="control-center">
        <aside class="control-rail">
            <h3>Fav Songs</h3>
            <div id="curation-system-status" class="system-status">
                <div><span>SSD</span><strong>Unknown</strong></div>
                <div><span>Music.app</span><strong>Unknown</strong></div>
                <div><span>Snapshot</span><strong>Not loaded</strong></div>
            </div>
        </aside>

        <section class="control-main">
            <div class="control-main-header">
                <div>
                    <h3>Fav Songs</h3>
                    <p class="text-muted">Genre folders with four temper playlists per genre.</p>
                </div>
                <div class="curation-actions">
                    <button class="btn btn-secondary" id="curation-load-snapshot-btn">Snapshot laden</button>
                    <button class="btn btn-primary" id="curation-refresh-btn">Neu lesen</button>
                </div>
            </div>

            <div id="curation-summary" class="curation-summary"></div>

            <div class="matrix-toolbar">
                <input id="curation-genre-filter" class="search-input" type="search" aria-label="Genre suchen">
                <button class="btn btn-secondary" id="curation-problems-only-btn" type="button">Nur Probleme</button>
                <button class="btn btn-secondary" id="curation-top-genres-btn" type="button">Top Genres</button>
            </div>

            <section id="curation-review-panel" class="curation-review-panel">
                <div class="card curation-empty-state">
                    <h3>No Snapshot Loaded</h3>
                    <p class="text-muted">Load the last snapshot or read Music.app again.</p>
                </div>
            </section>
        </section>

        <aside id="curation-write-panel" class="write-safety-panel">
            <h3>Schreibschutz</h3>
            <p class="text-muted">Full apply is locked until a fresh snapshot and mini-test are available.</p>
            <button class="btn btn-secondary" id="curation-smoke-test-btn" type="button" disabled>Mini-Test ausführen</button>
            <button class="btn btn-primary" id="curation-apply-btn" type="button" disabled>Full Apply vorbereiten</button>
            <div id="curation-change-panel" class="curation-change-panel"></div>
        </aside>
    </div>
</section>
```

- [ ] **Step 2: Add CSS**

In `web/static/css/style.css`, add:

```css
.control-center {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr) 300px;
    gap: 16px;
    align-items: start;
}

.control-rail,
.write-safety-panel {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--card-bg);
    padding: 16px;
}

.control-main {
    min-width: 0;
}

.control-main-header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 16px;
}

.system-status {
    display: grid;
    gap: 10px;
    margin-top: 16px;
}

.system-status div {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 0.9rem;
}

.matrix-toolbar {
    display: flex;
    gap: 8px;
    margin: 16px 0;
}

.curation-matrix {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    background: var(--card-bg);
}

.curation-matrix-row {
    display: grid;
    grid-template-columns: minmax(180px, 1.3fr) repeat(4, minmax(64px, 0.65fr)) minmax(80px, 0.8fr);
    gap: 8px;
    align-items: center;
    padding: 12px;
    border-top: 1px solid var(--border-color);
}

.curation-matrix-row:first-child {
    border-top: 0;
}

.curation-matrix-header {
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
}

@media (max-width: 1100px) {
    .control-center {
        grid-template-columns: 1fr;
    }
}
```

- [ ] **Step 3: Verify markup still serves**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_server.py -q
node --check web/static/js/app.js
```

Expected: tests pass; JS syntax still valid.

- [ ] **Step 4: Commit markup and styles**

```bash
git add web/index.html web/static/css/style.css
git commit -m "feat: add control center layout"
```

---

### Task 6: Implement Snapshot-First UI And Matrix Rendering

**Files:**
- Modify: `web/static/js/app.js`
- Modify: `tests/test_web_server.py` if API contract needs adjustment

- [ ] **Step 1: Update DOM bindings**

In `web/static/js/app.js`, update the curation DOM mapping:

```javascript
curationLoadSnapshotBtn: () => document.getElementById('curation-load-snapshot-btn'),
curationRefreshBtn: () => document.getElementById('curation-refresh-btn'),
curationSmokeTestBtn: () => document.getElementById('curation-smoke-test-btn'),
curationApplyBtn: () => document.getElementById('curation-apply-btn'),
curationSummary: () => document.getElementById('curation-summary'),
curationReviewPanel: () => document.getElementById('curation-review-panel'),
curationChangePanel: () => document.getElementById('curation-change-panel'),
curationSystemStatus: () => document.getElementById('curation-system-status'),
curationGenreFilter: () => document.getElementById('curation-genre-filter'),
```

- [ ] **Step 2: Replace preview load functions**

Add:

```javascript
let curationSnapshot = null;
let curationSmokeTest = null;
let curationRefreshLoading = false;

async function loadCurationSnapshot() {
    if (curationRefreshLoading || curationApplyInFlight) return;
    curationPreviewLoading = true;
    setCurationButtonsState();
    try {
        const snapshot = await app.api('/curation/snapshot?scope=fav_songs');
        curationSnapshot = snapshot;
        curationPreview = snapshot.available ? snapshot : null;
        renderCurationControlCenter(snapshot);
    } catch (error) {
        renderCurationError('Unable to load curation snapshot.');
        showAlert('Failed to load curation snapshot: ' + error.message, 'danger');
    } finally {
        curationPreviewLoading = false;
        setCurationButtonsState();
    }
}

async function refreshCurationSnapshot() {
    if (curationRefreshLoading || curationApplyInFlight) return;
    curationRefreshLoading = true;
    setCurationButtonsState();
    showSpinner(true);
    try {
        const snapshot = await app.api('/curation/refresh', {
            method: 'POST',
            body: { scope: 'fav_songs' },
        });
        curationSnapshot = snapshot;
        curationPreview = snapshot;
        curationSmokeTest = null;
        renderCurationControlCenter(snapshot);
    } catch (error) {
        renderCurationError('Unable to refresh curation snapshot.');
        showAlert('Failed to refresh curation snapshot: ' + error.message, 'danger');
    } finally {
        curationRefreshLoading = false;
        setCurationButtonsState();
        showSpinner(false);
    }
}
```

- [ ] **Step 3: Render matrix from grouped data**

Add:

```javascript
function groupedToMatrixRows(grouped) {
    return Object.entries(grouped || {})
        .map(([genre, temperMap]) => {
            const counts = {};
            CURATION_TEMPERS.forEach(temper => {
                counts[temper] = asArray(temperMap && temperMap[temper]).length;
            });
            const total = Object.values(counts).reduce((sum, value) => sum + value, 0);
            return { genre, counts, total, status: total > 0 ? 'ready' : 'empty' };
        })
        .sort((left, right) => right.total - left.total || left.genre.localeCompare(right.genre));
}

function renderCurationMatrix(panel, grouped) {
    panel.replaceChildren();
    const rows = groupedToMatrixRows(grouped);
    if (!rows.length) {
        const empty = appendElement(panel, 'div', 'card curation-empty-state');
        appendElement(empty, 'h3', null, 'No Snapshot Loaded');
        appendElement(empty, 'p', 'text-muted', 'Load a snapshot or read Music.app again.');
        return;
    }

    const matrix = appendElement(panel, 'div', 'curation-matrix');
    const header = appendElement(matrix, 'div', 'curation-matrix-row curation-matrix-header');
    ['Genre', 'Woe', 'Frolic', 'Dread', 'Malice', 'Status'].forEach(label => {
        appendElement(header, 'div', null, label);
    });

    rows.forEach(row => {
        const item = appendElement(matrix, 'button', 'curation-matrix-row');
        item.type = 'button';
        appendElement(item, 'div', null, `${row.genre} (${row.total})`);
        CURATION_TEMPERS.forEach(temper => {
            appendElement(item, 'div', null, row.counts[temper]);
        });
        appendElement(item, 'div', null, row.status);
    });
}
```

- [ ] **Step 4: Update button state**

Update `setCurationButtonsState()`:

```javascript
const hasFreshSnapshot = curationSnapshot && curationSnapshot.available && curationSnapshot.fresh;
const smokePassed = curationSmokeTest && curationSmokeTest.success;
if (applyBtn) {
    applyBtn.disabled = isBusy || !hasFreshSnapshot || !smokePassed;
}
if (smokeBtn) {
    smokeBtn.disabled = isBusy || !hasFreshSnapshot;
}
```

- [ ] **Step 5: Wire event listeners**

In initialization code:

```javascript
const loadSnapshotBtn = DOM.curationLoadSnapshotBtn();
if (loadSnapshotBtn) loadSnapshotBtn.addEventListener('click', loadCurationSnapshot);

const refreshBtn = DOM.curationRefreshBtn();
if (refreshBtn) refreshBtn.addEventListener('click', refreshCurationSnapshot);
```

When showing the curation view, call `loadCurationSnapshot()` instead of `loadCurationPreview()`.

- [ ] **Step 6: Verify JS syntax**

Run:

```bash
node --check web/static/js/app.js
```

Expected: no output, exit 0.

- [ ] **Step 7: Commit UI behavior**

```bash
git add web/static/js/app.js
git commit -m "feat: load curation control center from snapshots"
```

---

### Task 7: Wire Mini-Test UI Gate

**Files:**
- Modify: `web/static/js/app.js`
- Modify: `web/static/css/style.css`

- [ ] **Step 1: Add mini-test action**

In `web/static/js/app.js`:

```javascript
async function runCurationSmokeTest() {
    if (!curationSnapshot || !curationSnapshot.fresh) {
        showAlert('Refresh the curation snapshot before running the mini-test.', 'warning');
        return;
    }
    curationApplyInFlight = true;
    setCurationButtonsState();
    try {
        const result = await app.api('/curation/smoke-test', {
            method: 'POST',
            body: { scope: 'fav_songs' },
        });
        curationSmokeTest = result;
        renderCurationWritePanel(curationSnapshot, result);
        showAlert('Mini-test completed and cleaned up.', 'success');
    } catch (error) {
        curationSmokeTest = { success: false, error: error.message };
        renderCurationWritePanel(curationSnapshot, curationSmokeTest);
        showAlert('Mini-test failed: ' + error.message, 'danger');
    } finally {
        curationApplyInFlight = false;
        setCurationButtonsState();
    }
}
```

- [ ] **Step 2: Add write panel renderer**

```javascript
function renderCurationWritePanel(snapshot, smokeTest) {
    const panel = DOM.curationChangePanel();
    if (!panel) return;
    panel.replaceChildren();
    appendElement(panel, 'h3', null, 'Write Safety');
    appendElement(panel, 'p', 'text-muted', snapshot && snapshot.fresh ? 'Snapshot is fresh.' : 'Snapshot is stale or missing.');
    if (smokeTest) {
        appendElement(panel, 'p', smokeTest.success ? 'status-success' : 'status-danger',
            smokeTest.success ? 'Mini-test passed and cleaned up.' : `Mini-test failed: ${textValue(smokeTest.error, 'unknown error')}`
        );
    } else {
        appendElement(panel, 'p', 'text-muted', 'Mini-test has not run for this snapshot.');
    }
}
```

- [ ] **Step 3: Wire mini-test button**

```javascript
const smokeBtn = DOM.curationSmokeTestBtn();
if (smokeBtn) smokeBtn.addEventListener('click', runCurationSmokeTest);
```

- [ ] **Step 4: Add CSS states**

```css
.status-success {
    color: #047857;
    font-weight: 700;
}

.status-danger {
    color: #b91c1c;
    font-weight: 700;
}
```

- [ ] **Step 5: Verify syntax**

Run:

```bash
node --check web/static/js/app.js
```

Expected: exit 0.

- [ ] **Step 6: Commit mini-test UI**

```bash
git add web/static/js/app.js web/static/css/style.css
git commit -m "feat: gate curation apply behind mini test"
```

---

### Task 8: Convert Full Apply To Job-Facing API

**Files:**
- Modify: `src/web_server.py`
- Modify: `tests/test_web_server.py`
- Modify: `web/static/js/app.js`

- [ ] **Step 1: Write apply job API test**

In `tests/test_web_server.py`:

```python
def test_curation_apply_requires_smoke_test_token(client):
    response = client.post(
        "/api/curation/apply",
        json={"scope": "fav_songs", "confirmed": True},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "mini_test_passed must be true"


def test_curation_apply_accepts_job_request_after_gate(client, monkeypatch):
    class FakeService:
        def get_fav_songs_snapshot(self):
            return {"available": True, "fresh": True}

    monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

    response = client.post(
        "/api/curation/apply",
        json={
            "scope": "fav_songs",
            "confirmed": True,
            "mini_test_passed": True,
        },
    )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["status"] == "queued"
    assert payload["job_id"].startswith("curation-apply-")
```

- [ ] **Step 2: Run apply API tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_server.py::test_curation_apply_requires_smoke_test_token tests/test_web_server.py::test_curation_apply_accepts_job_request_after_gate -q
```

Expected: FAIL because current apply runs synchronously.

- [ ] **Step 3: Implement gated queued response**

In `src/web_server.py`, change `curation_apply()` after boolean confirmation validation:

```python
mini_test_passed = data.get("mini_test_passed", False)
if mini_test_passed is not True:
    return jsonify({"error": "mini_test_passed must be true"}), 400

snapshot = service.get_fav_songs_snapshot()
if not snapshot.get("available") or not snapshot.get("fresh"):
    return jsonify({"error": "Fresh curation snapshot required"}), 400

job_id = f"curation-apply-{int(time.time())}-{uuid.uuid4().hex[:8]}"
return jsonify(
    {
        "success": True,
        "status": "queued",
        "job_id": job_id,
        "message": "Curation apply queued. Background execution will be wired in the next phase.",
    }
), 202
```

This deliberately returns a queued job envelope in phase 1. Do not perform full apply synchronously.

- [ ] **Step 4: Update UI apply request**

In `applyFavSongsCuration()` request body:

```javascript
body: {
    scope: 'fav_songs',
    confirmed: true,
    mini_test_passed: Boolean(curationSmokeTest && curationSmokeTest.success),
},
```

After success:

```javascript
showAlert(`Curation apply queued: ${result.job_id}`, 'success');
```

- [ ] **Step 5: Run tests and syntax**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_server.py -q
node --check web/static/js/app.js
```

Expected: PASS and JS syntax clean.

- [ ] **Step 6: Commit apply gate**

```bash
git add src/web_server.py tests/test_web_server.py web/static/js/app.js
git commit -m "feat: queue gated curation apply requests"
```

---

### Task 9: Browser QA And Live Dry-Run Verification

**Files:**
- No source edits expected unless QA finds a bug.

- [ ] **Step 1: Run full automated verification**

Run:

```bash
.venv/bin/python -m pytest tests -q
node --check web/static/js/app.js
node --check src/scripts/curation_structure.js
osascript src/scripts/curation_structure.applescript
bash -n /Users/joeldebeljak/own_repos/music-curator/music_tools/bin/run_all.sh
git diff --check
```

Expected:

- `470 passed` or updated count with 0 failures
- JS checks exit 0
- AppleScript no-arg guard prints `ERROR: action and path required`
- shell syntax exits 0
- diff check exits 0

- [ ] **Step 2: Restart dev server**

Run:

```bash
pkill -f "python -m src.web_server" || true
.venv/bin/python -m src.web_server
```

Expected: server listens on `http://127.0.0.1:4000`.

- [ ] **Step 3: Verify API live dry-run**

Run:

```bash
.venv/bin/python main.py curate --scope fav_songs
```

Expected:

- `Preview only - no changes written`
- `Favourite tracks: 4106` or current real count
- planned changes printed
- no traceback

- [ ] **Step 4: Verify UI in browser**

Use Browser plugin against `http://127.0.0.1:4000/`.

Checks:

- Control Center loads from snapshot without immediately blocking on Music.app.
- `Neu lesen` refreshes and updates counts.
- Matrix shows genres as rows and `Woe/Frolic/Dread/Malice` as columns.
- `Full Apply vorbereiten` is disabled before mini-test.
- `Mini-Test ausführen` reports success and cleanup.
- `Full Apply vorbereiten` becomes enabled only after mini-test success.
- Do not click final confirmation for full apply.

- [ ] **Step 5: Commit QA fixes if needed**

If QA required fixes:

```bash
git add <changed-files>
git commit -m "fix: polish curation control center"
```

If no fixes were needed, do not create an empty commit.

---

## Final Verification Checklist

- [ ] `pytest tests -q` passes.
- [ ] `node --check web/static/js/app.js` passes.
- [ ] `osascript src/scripts/curation_structure.applescript` returns the no-arg guard.
- [ ] Live dry-run reads `Favourite Songs` without timeout.
- [ ] Mini-test creates/copies/deduplicates/cleans up one temporary path.
- [ ] Full apply is not executed during verification.
- [ ] `git status --short --branch` is clean except allowed local `.superpowers/` mockup artifacts.
