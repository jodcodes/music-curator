# Fav Songs Genre Temper UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web UI that previews genre and temperament assignments, lets Joel correct them, and applies confirmed changes to Apple Music, including a separate `Fav Songs / <Genre> / Fav <Genre> <Temper>` structure.

**Architecture:** Add a small curation layer inside `affective_playlists` that produces reviewable assignments and dry-run change plans before Apple Music is touched. The Flask API and static frontend consume that curation layer; `music_tools/bin/run_all.sh` later calls the same curation code for scheduled Favourite Songs syncing. Apple Music write operations stay behind a focused `osascript`/JXA adapter so tests can verify planning without launching Music.app.

**Tech Stack:** Python 3.10, Flask, SQLAlchemy only where already used, static HTML/CSS/JS, JXA through `osascript -l JavaScript`, existing `PlaylistClassifier`, existing temperament classes, existing `music_tools` launchd wrapper.

---

## File Structure

- Create `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_models.py` for assignment dataclasses, enums, and naming helpers.
- Create `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_store.py` for persisted manual overrides in `data/curation/assignments.json`.
- Create `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/apple_music_structure.py` for dry-run and apply operations against Music.app.
- Create `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_service.py` for orchestration across playlist classification, favourite track classification, overrides, and Apple Music apply.
- Create `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/scripts/curation_structure.js` as a JXA `osascript -l JavaScript` adapter for folder, nested folder, playlist, move, and duplicate operations not covered by existing scripts.
- Modify `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/web_server.py` to expose curation preview, override, dry-run, and apply endpoints.
- Modify `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/index.html`, `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/js/app.js`, and `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/css/style.css` to add the review UI.
- Modify `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/main.py` to add a `curate` CLI entry for scheduled Favourite Songs sync.
- Modify `/Users/joeldebeljak/own_repos/music-curator/music_tools/bin/run_all.sh` after the UI workflow is passing, so the scheduled automation calls the new curation CLI instead of the old genre-only script.
- Create tests:
  - `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_models.py`
  - `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_store.py`
  - `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_apple_music_structure.py`
  - `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_service.py`
  - Extend `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_web_server.py`
  - Extend `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_main_cli_platform.py`

## Domain Rules

- Favourite Songs has a dedicated top-level folder named `Fav Songs`.
- Each genre inside `Fav Songs` is a real Apple Music folder: `Fav Songs / Hiphop`, `Fav Songs / Electronic`, `Fav Songs / Jazz`.
- Each temperament inside a Favourite Songs genre folder is a playlist named `Fav <Genre> <Temper>`, for example `Fav Hiphop Frolic`.
- Favourite Songs apply copies tracks into target playlists and skips duplicates by persistent ID and normalized `artist + title`.
- Favourite Songs apply never deletes tracks from existing playlists in the first implementation.
- Whole user playlists are reviewed separately from Favourite Songs buckets.
- All Apple Music writes require a dry-run plan first; the API rejects non-dry-run apply when `confirmed` is not `true`.
- The system stores manual overrides and uses them over classifier output.
- Live Music.app/library smoke tests are deferred until Joel has the Apple Music library connected. Automated tests, dry-run output, and mocked apply calls are the acceptance criteria until then.

---

### Task 1: Curation Models And Naming

**Files:**
- Create: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_models.py`
- Test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_models.py`

- [ ] **Step 1: Write failing model and naming tests**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_models.py
from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
    TemperBucket,
    fav_playlist_name,
    normalize_genre_label,
)


def test_normalize_genre_label_keeps_short_names_readable():
    assert normalize_genre_label("hiphop") == "Hiphop"
    assert normalize_genre_label("disco_funk_soul") == "Disco Funk Soul"
    assert normalize_genre_label("Electronic") == "Electronic"


def test_fav_playlist_name_uses_requested_format():
    assert fav_playlist_name("hiphop", TemperBucket.FROLIC) == "Fav Hiphop Frolic"
    assert fav_playlist_name("electronic", TemperBucket.DREAD) == "Fav Electronic Dread"


def test_assignment_serializes_for_api():
    assignment = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.FROLIC,
        source=AssignmentSource.AUTO,
        confidence=0.91,
    )

    assert assignment.to_dict() == {
        "item_type": "fav_track",
        "item_id": "track-1",
        "item_name": "Track A",
        "genre": "hiphop",
        "genre_label": "Hiphop",
        "temperament": "Frolic",
        "source": "auto",
        "confidence": 0.91,
        "manual_override": False,
        "target_path": ["Fav Songs", "Hiphop", "Fav Hiphop Frolic"],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_curation_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.curation_models'`.

- [ ] **Step 3: Add model implementation**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


FAV_ROOT_FOLDER = "Fav Songs"


class TemperBucket(Enum):
    WOE = "Woe"
    FROLIC = "Frolic"
    DREAD = "Dread"
    MALICE = "Malice"


class AssignmentType(Enum):
    PLAYLIST = "playlist"
    FAV_TRACK = "fav_track"


class AssignmentSource(Enum):
    AUTO = "auto"
    MANUAL = "manual"


def normalize_genre_label(genre: str) -> str:
    cleaned = str(genre or "").replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return "Other"
    return " ".join(part.capitalize() for part in cleaned.split())


def fav_playlist_name(genre: str, temperament: TemperBucket) -> str:
    return f"Fav {normalize_genre_label(genre)} {temperament.value}"


@dataclass(frozen=True)
class CurationAssignment:
    item_type: AssignmentType
    item_id: str
    item_name: str
    genre: str
    temperament: TemperBucket
    source: AssignmentSource
    confidence: float
    manual_override: bool = False

    def target_path(self) -> List[str]:
        if self.item_type == AssignmentType.FAV_TRACK:
            genre_label = normalize_genre_label(self.genre)
            return [FAV_ROOT_FOLDER, genre_label, fav_playlist_name(self.genre, self.temperament)]
        return [normalize_genre_label(self.genre), self.temperament.value]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_type": self.item_type.value,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "genre": self.genre,
            "genre_label": normalize_genre_label(self.genre),
            "temperament": self.temperament.value,
            "source": self.source.value,
            "confidence": round(float(self.confidence), 4),
            "manual_override": self.manual_override,
            "target_path": self.target_path(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "CurationAssignment":
        return CurationAssignment(
            item_type=AssignmentType(str(data["item_type"])),
            item_id=str(data["item_id"]),
            item_name=str(data["item_name"]),
            genre=str(data["genre"]),
            temperament=TemperBucket(str(data["temperament"])),
            source=AssignmentSource(str(data["source"])),
            confidence=float(data["confidence"]),
            manual_override=bool(data.get("manual_override", False)),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_curation_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add src/curation_models.py tests/test_curation_models.py
git commit -m "feat: add curation assignment models"
```

---

### Task 2: Manual Override Store

**Files:**
- Create: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_store.py`
- Test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_store.py`

- [ ] **Step 1: Write failing persistence tests**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_store.py
from src.curation_models import AssignmentSource, AssignmentType, CurationAssignment, TemperBucket
from src.curation_store import CurationStore


def test_store_round_trips_manual_override(tmp_path):
    store = CurationStore(tmp_path / "assignments.json")
    assignment = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.MANUAL,
        confidence=1.0,
        manual_override=True,
    )

    store.save_override(assignment)
    loaded = store.get_override(AssignmentType.FAV_TRACK, "track-1")

    assert loaded == assignment


def test_store_merges_overrides_over_auto_assignments(tmp_path):
    store = CurationStore(tmp_path / "assignments.json")
    auto = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="electronic",
        temperament=TemperBucket.FROLIC,
        source=AssignmentSource.AUTO,
        confidence=0.7,
    )
    manual = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.MANUAL,
        confidence=1.0,
        manual_override=True,
    )

    store.save_override(manual)

    assert store.apply_overrides([auto]) == [manual]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_curation_store.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.curation_store'`.

- [ ] **Step 3: Add JSON store**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src.curation_models import AssignmentType, CurationAssignment


class CurationStore:
    def __init__(self, path: Path | str = "data/curation/assignments.json"):
        self.path = Path(path)

    def _key(self, item_type: AssignmentType, item_id: str) -> str:
        return f"{item_type.value}:{item_id}"

    def _load(self) -> Dict[str, dict]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return {}
        return data

    def _save(self, data: Dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        tmp_path.replace(self.path)

    def save_override(self, assignment: CurationAssignment) -> None:
        data = self._load()
        data[self._key(assignment.item_type, assignment.item_id)] = assignment.to_dict()
        self._save(data)

    def get_override(
        self, item_type: AssignmentType, item_id: str
    ) -> Optional[CurationAssignment]:
        payload = self._load().get(self._key(item_type, item_id))
        if not payload:
            return None
        return CurationAssignment.from_dict(payload)

    def apply_overrides(
        self, assignments: Iterable[CurationAssignment]
    ) -> List[CurationAssignment]:
        overrides = self._load()
        merged: List[CurationAssignment] = []
        for assignment in assignments:
            payload = overrides.get(self._key(assignment.item_type, assignment.item_id))
            merged.append(CurationAssignment.from_dict(payload) if payload else assignment)
        return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_curation_store.py tests/test_curation_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add src/curation_store.py tests/test_curation_store.py
git commit -m "feat: persist curation overrides"
```

---

### Task 3: Apple Music Structure Planner And Dry Run

**Files:**
- Create: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/apple_music_structure.py`
- Test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_apple_music_structure.py`

- [ ] **Step 1: Write failing dry-run tests**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_apple_music_structure.py
from src.apple_music_structure import AppleMusicChange, AppleMusicStructurePlanner
from src.curation_models import AssignmentSource, AssignmentType, CurationAssignment, TemperBucket


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


def test_plan_creates_fav_folder_genre_folder_playlist_and_copy():
    planner = AppleMusicStructurePlanner()
    changes = planner.plan_fav_tracks([fav_assignment("1", "hiphop", TemperBucket.FROLIC)])

    assert AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs") in changes
    assert AppleMusicChange(
        "ensure_folder", ["Fav Songs", "Hiphop"], "Ensure folder Fav Songs / Hiphop"
    ) in changes
    assert AppleMusicChange(
        "ensure_playlist",
        ["Fav Songs", "Hiphop", "Fav Hiphop Frolic"],
        "Ensure playlist Fav Hiphop Frolic",
    ) in changes
    assert AppleMusicChange(
        "copy_track",
        ["1", "Fav Songs", "Hiphop", "Fav Hiphop Frolic"],
        "Copy Track 1 to Fav Hiphop Frolic",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_apple_music_structure.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.apple_music_structure'`.

- [ ] **Step 3: Add dry-run planner**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/apple_music_structure.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Set, Tuple

from src.curation_models import AssignmentType, CurationAssignment


@dataclass(frozen=True)
class AppleMusicChange:
    action: str
    path: List[str]
    description: str

    def to_dict(self) -> dict:
        return {"action": self.action, "path": self.path, "description": self.description}


class AppleMusicStructurePlanner:
    def plan_fav_tracks(self, assignments: Iterable[CurationAssignment]) -> List[AppleMusicChange]:
        changes: List[AppleMusicChange] = []
        seen: Set[Tuple[str, Tuple[str, ...]]] = set()

        def add(action: str, path: List[str], description: str) -> None:
            key = (action, tuple(path))
            if key not in seen:
                seen.add(key)
                changes.append(AppleMusicChange(action, path, description))

        for assignment in assignments:
            if assignment.item_type != AssignmentType.FAV_TRACK:
                continue
            root, genre_folder, playlist_name = assignment.target_path()
            add("ensure_folder", [root], f"Ensure folder {root}")
            add(
                "ensure_folder",
                [root, genre_folder],
                f"Ensure folder {root} / {genre_folder}",
            )
            add(
                "ensure_playlist",
                [root, genre_folder, playlist_name],
                f"Ensure playlist {playlist_name}",
            )
            add(
                "copy_track",
                [assignment.item_id, root, genre_folder, playlist_name],
                f"Copy {assignment.item_name} to {playlist_name}",
            )

        return changes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_apple_music_structure.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add src/apple_music_structure.py tests/test_apple_music_structure.py
git commit -m "feat: plan apple music curation changes"
```

---

### Task 4: JXA Apply Adapter

**Files:**
- Modify: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/apple_music_structure.py`
- Create: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/scripts/curation_structure.js`
- Test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_apple_music_structure.py`

- [ ] **Step 1: Add failing adapter tests with mocked subprocess**

Append to `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_apple_music_structure.py`:

```python
from unittest.mock import patch

from src.apple_music_structure import AppleMusicStructureApplier


def test_applier_rejects_unconfirmed_apply():
    applier = AppleMusicStructureApplier(script_path="/tmp/curation_structure.js")
    result = applier.apply_changes(
        [AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")],
        confirmed=False,
    )

    assert result["success"] is False
    assert result["error"] == "Confirmation required"


@patch("src.apple_music_structure.subprocess.run")
def test_applier_calls_jxa_for_confirmed_changes(mock_run, tmp_path):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "SUCCESS"
    mock_run.return_value.stderr = ""
    script_path = tmp_path / "curation_structure.js"
    script_path.write_text("// test script", encoding="utf-8")

    applier = AppleMusicStructureApplier(script_path=str(script_path))
    result = applier.apply_changes(
        [AppleMusicChange("ensure_folder", ["Fav Songs"], "Ensure folder Fav Songs")],
        confirmed=True,
    )

    assert result["success"] is True
    assert result["applied"] == 1
    assert mock_run.call_args.args[0] == [
        "osascript",
        "-l",
        "JavaScript",
        str(script_path),
        "ensure_folder",
        "Fav Songs",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_apple_music_structure.py -v`

Expected: FAIL with `ImportError: cannot import name 'AppleMusicStructureApplier'`.

- [ ] **Step 3: Add Python applier**

Append to `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/apple_music_structure.py`:

```python
import os
import subprocess
from pathlib import Path


class AppleMusicStructureApplier:
    def __init__(self, script_path: str | None = None):
        default_script = Path(__file__).parent / "scripts" / "curation_structure.js"
        self.script_path = str(script_path or default_script)

    def apply_changes(self, changes: Iterable[AppleMusicChange], confirmed: bool) -> dict:
        if not confirmed:
            return {"success": False, "error": "Confirmation required", "applied": 0, "failed": 0}
        if not os.path.exists(self.script_path):
            return {"success": False, "error": f"Script not found: {self.script_path}", "applied": 0, "failed": 0}

        applied = 0
        failed = 0
        errors = []
        for change in changes:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", self.script_path, change.action, *change.path],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and "SUCCESS" in result.stdout:
                applied += 1
            else:
                failed += 1
                errors.append(
                    {
                        "change": change.to_dict(),
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                    }
                )
        return {"success": failed == 0, "applied": applied, "failed": failed, "errors": errors}
```

- [ ] **Step 4: Add JXA command adapter**

```javascript
#!/usr/bin/env osascript -l JavaScript
// /Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/scripts/curation_structure.js
const Music = Application("Music");
Music.includeStandardAdditions = true;
try { Music.timeout = 600; } catch (e) {}

function firstNamed(collection, name) {
  const matches = collection.whose({ name });
  return matches.length > 0 ? matches[0] : null;
}

function getOrCreateFolder(name) {
  const existing = firstNamed(Music.folderPlaylists, name);
  if (existing) return existing;
  return Music.FolderPlaylist({ name }).make();
}

function getOrCreatePlaylist(name) {
  const existing = firstNamed(Music.userPlaylists, name);
  if (existing) return existing;
  return Music.UserPlaylist({ name }).make();
}

function moveInto(item, parentFolder) {
  try {
    Music.move(item, { to: parentFolder });
  } catch (e) {
    // Music may throw when the item is already inside the target folder.
  }
  return item;
}

function ensureGenreFolder(rootName, genreName) {
  const rootFolder = getOrCreateFolder(rootName);
  const genreFolder = getOrCreateFolder(`${rootName} / ${genreName}`);
  genreFolder.name = genreName;
  return moveInto(genreFolder, rootFolder);
}

function ensureTemperPlaylist(rootName, genreName, playlistName) {
  const genreFolder = ensureGenreFolder(rootName, genreName);
  const playlist = getOrCreatePlaylist(playlistName);
  return moveInto(playlist, genreFolder);
}

function trackKey(artist, name) {
  return `${(artist || "").toLowerCase()}|||${(name || "").toLowerCase()}`;
}

function findLibraryTrackByPersistentID(trackPID) {
  const library = Music.libraryPlaylists[0];
  const tracks = library.tracks.whose({ persistentID: trackPID });
  if (tracks.length === 0) throw new Error(`Source track not found: ${trackPID}`);
  return tracks[0];
}

function targetContainsTrack(targetPlaylist, sourceTrack) {
  const existingIDs = new Set(targetPlaylist.tracks.persistentID());
  if (existingIDs.has(sourceTrack.persistentID())) return true;

  const names = targetPlaylist.tracks.name();
  const artists = targetPlaylist.tracks.artist();
  const sourceKey = trackKey(sourceTrack.artist(), sourceTrack.name());
  for (let i = 0; i < names.length; i++) {
    if (trackKey(artists[i], names[i]) === sourceKey) return true;
  }
  return false;
}

function run(argv) {
  if (argv.length < 2) return "ERROR: action and path required";
  const action = argv[0];

  if (action === "ensure_folder") {
    if (argv.length === 2) getOrCreateFolder(argv[1]);
    if (argv.length === 3) ensureGenreFolder(argv[1], argv[2]);
    return "SUCCESS";
  }

  if (action === "ensure_playlist") {
    ensureTemperPlaylist(argv[1], argv[2], argv[3]);
    return "SUCCESS";
  }

  if (action === "copy_track") {
    const sourceTrack = findLibraryTrackByPersistentID(argv[1]);
    const targetPlaylist = ensureTemperPlaylist(argv[2], argv[3], argv[4]);
    if (targetContainsTrack(targetPlaylist, sourceTrack)) return "SUCCESS: skipped duplicate";
    Music.duplicate(sourceTrack, { to: targetPlaylist });
    return "SUCCESS";
  }

  return `ERROR: unsupported action ${action}`;
}
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_apple_music_structure.py -v`

Expected: PASS.

- [ ] **Step 6: Manual smoke test on macOS Music.app**

Skip this step until Joel confirms that the Apple Music library is connected.

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && osascript -l JavaScript src/scripts/curation_structure.js ensure_folder "Fav Songs"`

Expected: stdout contains `SUCCESS` and Music.app has a `Fav Songs` folder. If Music.app creates the folder but JXA returns a wording variant, update the Python success check to accept exact stdout after observing it.

- [ ] **Step 7: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add src/apple_music_structure.py src/scripts/curation_structure.js tests/test_apple_music_structure.py
git commit -m "feat: apply curation changes to music"
```

---

### Task 5: Curation Service

**Files:**
- Create: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_service.py`
- Test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_service.py`

- [ ] **Step 1: Write failing service tests with fake inputs**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_curation_service.py
from src.curation_models import TemperBucket
from src.curation_service import CurationService


class FakeAppleMusic:
    def get_favourite_tracks(self):
        return [
            {"persistent_id": "track-1", "name": "Track A", "artist": "Artist A", "genre": "Hip-Hop"},
            {"persistent_id": "track-2", "name": "Track B", "artist": "Artist B", "genre": "Electronic"},
        ]


class FakeTemperClassifier:
    def classify_track(self, track):
        return TemperBucket.FROLIC if track["persistent_id"] == "track-1" else TemperBucket.DREAD


def test_fav_preview_builds_assignments_and_changes():
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    targets = [a["target_path"] for a in preview["assignments"]]
    assert ["Fav Songs", "Hip Hop", "Fav Hip Hop Frolic"] in targets
    assert ["Fav Songs", "Electronic", "Fav Electronic Dread"] in targets
    assert preview["changes"][0]["action"] == "ensure_folder"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_curation_service.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.curation_service'`.

- [ ] **Step 3: Add service implementation**

```python
# /Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/curation_service.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.apple_music import AppleMusicInterface
from src.apple_music_structure import AppleMusicStructureApplier, AppleMusicStructurePlanner
from src.curation_models import AssignmentSource, AssignmentType, CurationAssignment, TemperBucket
from src.curation_store import CurationStore


class KeywordTemperClassifier:
    def classify_track(self, track: Dict[str, Any]) -> TemperBucket:
        text = f"{track.get('name', '')} {track.get('artist', '')} {track.get('genre', '')}".lower()
        if any(word in text for word in ["dark", "dread", "night", "bass", "industrial"]):
            return TemperBucket.DREAD
        if any(word in text for word in ["sad", "lonely", "melancholy", "blue"]):
            return TemperBucket.WOE
        if any(word in text for word in ["rage", "hard", "aggressive", "drill"]):
            return TemperBucket.MALICE
        return TemperBucket.FROLIC


class CurationService:
    def __init__(
        self,
        apple_music: Optional[Any] = None,
        temper_classifier: Optional[Any] = None,
        store: Optional[CurationStore] = None,
        planner: Optional[AppleMusicStructurePlanner] = None,
        applier: Optional[AppleMusicStructureApplier] = None,
    ):
        self.apple_music = apple_music or AppleMusicInterface()
        self.temper_classifier = temper_classifier or KeywordTemperClassifier()
        self.store = store or CurationStore()
        self.planner = planner or AppleMusicStructurePlanner()
        self.applier = applier or AppleMusicStructureApplier()

    def preview_fav_songs(self) -> Dict[str, Any]:
        tracks = self.apple_music.get_favourite_tracks()
        assignments: List[CurationAssignment] = []
        for track in tracks:
            genre = str(track.get("genre") or "other").strip().lower().replace(" ", "_")
            temperament = self.temper_classifier.classify_track(track)
            assignments.append(
                CurationAssignment(
                    item_type=AssignmentType.FAV_TRACK,
                    item_id=str(track.get("persistent_id") or track.get("id")),
                    item_name=str(track.get("name") or "Unknown Track"),
                    genre=genre,
                    temperament=temperament,
                    source=AssignmentSource.AUTO,
                    confidence=0.75,
                )
            )

        assignments = self.store.apply_overrides(assignments)
        changes = self.planner.plan_fav_tracks(assignments)
        return {
            "assignments": [assignment.to_dict() for assignment in assignments],
            "changes": [change.to_dict() for change in changes],
            "total_assignments": len(assignments),
            "total_changes": len(changes),
        }

    def apply_fav_songs(self, confirmed: bool) -> Dict[str, Any]:
        preview = self.preview_fav_songs()
        changes = self.planner.plan_fav_tracks(
            [CurationAssignment.from_dict(item) for item in preview["assignments"]]
        )
        result = self.applier.apply_changes(changes, confirmed=confirmed)
        result["preview"] = preview
        return result
```

- [ ] **Step 4: Add AppleMusicInterface method for Favourite Songs**

Modify `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/apple_music.py` with:

```python
    def get_favourite_tracks(self) -> List[Dict]:
        """Return tracks from Apple Music's Favourite Songs playlist."""
        tracks = self.get_playlist_tracks("Favourite Songs")
        return tracks or []
```

- [ ] **Step 5: Run focused tests**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_curation_service.py tests/test_apple_music_folder_structure.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add src/curation_service.py src/apple_music.py tests/test_curation_service.py
git commit -m "feat: preview favourite song curation"
```

---

### Task 6: Flask API Endpoints

**Files:**
- Modify: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/web_server.py`
- Modify test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_web_server.py`

- [ ] **Step 1: Add failing endpoint tests**

Append to `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_web_server.py`:

```python
class TestCurationEndpoints:
    def test_curation_preview_returns_assignments_and_changes(self, client, monkeypatch):
        class FakeService:
            def preview_fav_songs(self):
                return {"assignments": [], "changes": [], "total_assignments": 0, "total_changes": 0}

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.get("/api/curation/preview?scope=fav_songs")

        assert response.status_code == 200
        assert response.get_json()["total_assignments"] == 0

    def test_curation_apply_requires_confirmation(self, client, monkeypatch):
        class FakeService:
            def apply_fav_songs(self, confirmed):
                return {"success": False, "error": "Confirmation required", "applied": 0, "failed": 0}

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.post("/api/curation/apply", json={"scope": "fav_songs", "confirmed": False})

        assert response.status_code == 400
        assert response.get_json()["error"] == "Confirmation required"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_web_server.py::TestCurationEndpoints -v`

Expected: FAIL because routes do not exist.

- [ ] **Step 3: Add service factory and routes**

Add near the other helper factories in `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/src/web_server.py`:

```python
def _get_curation_service():
    try:
        from src.curation_service import CurationService

        return CurationService()
    except Exception as e:
        logger.warning(f"Failed to initialize CurationService: {e}")
        return None
```

Add routes before error handlers:

```python
@app.route("/api/curation/preview", methods=["GET"])
def curation_preview():
    scope = request.args.get("scope", "fav_songs")
    service = _get_curation_service()
    if service is None:
        return jsonify({"error": "Curation service unavailable"}), 503
    if scope != "fav_songs":
        return jsonify({"error": f"Unsupported scope: {scope}"}), 400
    return jsonify(service.preview_fav_songs())


@app.route("/api/curation/apply", methods=["POST"])
def curation_apply():
    data = request.get_json() or {}
    scope = data.get("scope", "fav_songs")
    confirmed = bool(data.get("confirmed", False))
    service = _get_curation_service()
    if service is None:
        return jsonify({"error": "Curation service unavailable"}), 503
    if scope != "fav_songs":
        return jsonify({"error": f"Unsupported scope: {scope}"}), 400

    result = service.apply_fav_songs(confirmed=confirmed)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result)
```

- [ ] **Step 4: Run endpoint tests**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_web_server.py::TestCurationEndpoints -v`

Expected: PASS.

- [ ] **Step 5: Run full web server tests**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_web_server.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add src/web_server.py tests/test_web_server.py
git commit -m "feat: expose curation review api"
```

---

### Task 7: Static Web UI

**Files:**
- Modify: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/index.html`
- Modify: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/js/app.js`
- Modify: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/css/style.css`

- [ ] **Step 1: Add UI shell**

In `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/index.html`, add a nav item and a view section:

```html
<button class="nav-link" data-view="curation">Curation Review</button>

<section id="curation-view" class="view">
  <div class="view-header">
    <h2>Curation Review</h2>
    <div class="view-actions">
      <button id="curation-refresh-btn" class="btn btn-secondary">Refresh Preview</button>
      <button id="curation-dry-run-btn" class="btn btn-secondary">Dry Run</button>
      <button id="curation-apply-btn" class="btn btn-primary">Apply Fav Songs</button>
    </div>
  </div>
  <div id="curation-summary" class="summary-grid"></div>
  <div class="curation-layout">
    <aside id="curation-genre-tree" class="curation-sidebar"></aside>
    <main id="curation-review-panel" class="curation-review-panel"></main>
    <aside id="curation-change-panel" class="curation-change-panel"></aside>
  </div>
</section>
```

- [ ] **Step 2: Add frontend API and rendering functions**

Append to `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/js/app.js`:

```javascript
let curationPreview = null;

async function loadCurationPreview() {
  showSpinner(true);
  try {
    const response = await fetch('/api/curation/preview?scope=fav_songs');
    if (!response.ok) {
      throw new Error(`Preview failed: ${response.status}`);
    }
    curationPreview = await response.json();
    renderCurationPreview(curationPreview);
  } catch (err) {
    showAlert(err.message, 'error');
  } finally {
    showSpinner(false);
  }
}

function renderCurationPreview(preview) {
  const summary = document.getElementById('curation-summary');
  const tree = document.getElementById('curation-genre-tree');
  const review = document.getElementById('curation-review-panel');
  const changes = document.getElementById('curation-change-panel');
  if (!summary || !tree || !review || !changes) return;

  summary.innerHTML = `
    <div class="stat-card"><span>${preview.total_assignments}</span><label>Favourite Tracks</label></div>
    <div class="stat-card"><span>${preview.total_changes}</span><label>Planned Changes</label></div>
  `;

  const grouped = {};
  for (const item of preview.assignments) {
    const genre = item.genre_label;
    if (!grouped[genre]) grouped[genre] = [];
    grouped[genre].push(item);
  }

  tree.innerHTML = Object.keys(grouped).sort().map((genre) => `
    <button class="curation-genre-button" data-genre="${genre}">
      <strong>${genre}</strong>
      <span>${grouped[genre].length} tracks</span>
    </button>
  `).join('');

  review.innerHTML = Object.keys(grouped).sort().map((genre) => `
    <section class="curation-genre-section">
      <h3>${genre}</h3>
      <div class="temper-grid">
        ${['Frolic', 'Woe', 'Dread', 'Malice'].map((temper) => `
          <div class="temper-column">
            <h4>${temper}</h4>
            ${grouped[genre]
              .filter((item) => item.temperament === temper)
              .map((item) => `<div class="assignment-row">${item.item_name}<small>${item.target_path.join(' / ')}</small></div>`)
              .join('')}
          </div>
        `).join('')}
      </div>
    </section>
  `).join('');

  changes.innerHTML = `
    <h3>Dry Run</h3>
    ${preview.changes.map((change) => `<div class="change-row">${change.description}</div>`).join('')}
  `;
}

async function applyFavSongsCuration() {
  const confirmed = window.confirm('Apply confirmed Favourite Songs structure to Apple Music?');
  if (!confirmed) return;
  showSpinner(true);
  try {
    const response = await fetch('/api/curation/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: 'fav_songs', confirmed: true }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || 'Apply failed');
    }
    showAlert(`Applied ${result.applied} changes`, 'success');
    await loadCurationPreview();
  } catch (err) {
    showAlert(err.message, 'error');
  } finally {
    showSpinner(false);
  }
}
```

- [ ] **Step 3: Wire buttons in `setupEventListeners()`**

Add inside existing `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/js/app.js` `setupEventListeners()`:

```javascript
const curationRefreshBtn = document.getElementById('curation-refresh-btn');
if (curationRefreshBtn) curationRefreshBtn.addEventListener('click', loadCurationPreview);

const curationDryRunBtn = document.getElementById('curation-dry-run-btn');
if (curationDryRunBtn) curationDryRunBtn.addEventListener('click', loadCurationPreview);

const curationApplyBtn = document.getElementById('curation-apply-btn');
if (curationApplyBtn) curationApplyBtn.addEventListener('click', applyFavSongsCuration);
```

- [ ] **Step 4: Add CSS**

Append to `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/web/static/css/style.css`:

```css
.curation-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}

.curation-sidebar,
.curation-review-panel,
.curation-change-panel {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
  padding: 16px;
}

.curation-genre-button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  margin-bottom: 8px;
  cursor: pointer;
}

.temper-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.temper-column,
.assignment-row,
.change-row {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px;
}

.assignment-row {
  margin-bottom: 8px;
}

.assignment-row small {
  display: block;
  margin-top: 4px;
  color: var(--muted-color);
}

@media (max-width: 980px) {
  .curation-layout {
    grid-template-columns: 1fr;
  }
  .temper-grid {
    grid-template-columns: 1fr 1fr;
  }
}
```

- [ ] **Step 5: Run server and manually verify UI**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && python -m src.web_server`

Open: `http://127.0.0.1:4000`

Expected: `Curation Review` appears in navigation; clicking `Refresh Preview` calls `/api/curation/preview`; clicking `Apply Fav Songs` prompts for confirmation before calling `/api/curation/apply`.

- [ ] **Step 6: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add web/index.html web/static/js/app.js web/static/css/style.css
git commit -m "feat: add curation review ui"
```

---

### Task 8: CLI Entry For Scheduled Favourite Songs Sync

**Files:**
- Modify: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/main.py`
- Test: `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_main_cli_platform.py`

- [ ] **Step 1: Add failing CLI parser test**

Append to `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/tests/test_main_cli_platform.py`:

```python
def test_curate_feature_accepts_dry_run(monkeypatch):
    import main

    calls = {}

    def fake_run_curation(args):
        calls["scope"] = args.scope
        calls["apply"] = args.apply
        return 0

    monkeypatch.setattr(main, "run_curation", fake_run_curation)
    monkeypatch.setattr(main, "IS_MACOS", True)

    assert main.main(["curate", "--scope", "fav_songs"]) == 0
    assert calls == {"scope": "fav_songs", "apply": False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_main_cli_platform.py::test_curate_feature_accepts_dry_run -v`

Expected: FAIL because `main.main()` currently does not accept an argument list and `curate` is not a valid choice.

- [ ] **Step 3: Update `main.py` parser and curation command**

Modify `/Users/joeldebeljak/own_repos/music-curator/affective_playlists/main.py`:

```python
def run_curation(args=None):
    """Run curation preview/apply for Favourite Songs."""
    print_header("🎛️ Curation", "Review and apply Favourite Songs structure")

    if not require_macos("Curation"):
        return 1

    from src.curation_service import CurationService

    service = CurationService()
    if args and getattr(args, "apply", False):
        result = service.apply_fav_songs(confirmed=True)
        print(info(f"Applied: {result.get('applied', 0)} | Failed: {result.get('failed', 0)}"))
        return 0 if result.get("success") else 1

    preview = service.preview_fav_songs()
    print(info(f"Favourite tracks: {preview['total_assignments']}"))
    print(info(f"Planned changes: {preview['total_changes']}"))
    return 0


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="affective_playlists",
        description="Unified music analysis and organization tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "feature",
        nargs="?",
        choices=["temperament", "enrich", "organize", "curate"],
        help="Feature to run (if not specified, shows interactive menu)",
    )
    parser.add_argument("--scope", choices=["fav_songs"], default="fav_songs")
    parser.add_argument("--apply", action="store_true", help="Apply curation changes")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel("DEBUG")

    if args.feature == "temperament":
        return run_temperament_analysis()
    elif args.feature == "enrich":
        return run_metadata_enrichment()
    elif args.feature == "organize":
        return run_playlist_organization()
    elif args.feature == "curate":
        return run_curation(args)
    else:
        return show_interactive_menu()
```

- [ ] **Step 4: Run CLI tests**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/test_main_cli_platform.py -v`

Expected: PASS.

- [ ] **Step 5: Manual CLI dry-run**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && python main.py curate --scope fav_songs`

Expected: Prints Favourite track count and planned change count without modifying Apple Music.

- [ ] **Step 6: Commit**

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
git add main.py tests/test_main_cli_platform.py
git commit -m "feat: add curation cli"
```

---

### Task 9: Scheduled Automation Migration

**Files:**
- Modify: `/Users/joeldebeljak/own_repos/music-curator/music_tools/bin/run_all.sh`
- Modify docs: `/Users/joeldebeljak/own_repos/music-curator/music_tools/README.md`

- [ ] **Step 1: Add dry-run command to wrapper before replacing old sorter**

Modify `/Users/joeldebeljak/own_repos/music-curator/music_tools/bin/run_all.sh` after `export MUSIC_TOOLS_LIBRARY_PATH="$MUSIC_LIBRARY_PATH"`:

```bash
AFFECTIVE_PLAYLISTS_DIR="$(cd "$REPO_DIR/../affective_playlists" && pwd)"
AFFECTIVE_PLAYLISTS_CMD=(/usr/bin/env python3 "$AFFECTIVE_PLAYLISTS_DIR/main.py" curate --scope fav_songs)
```

Modify the scripts loop so `sort_favourites_by_genre.js` stays active until the new CLI has completed one successful dry-run:

```bash
if [ -d "$AFFECTIVE_PLAYLISTS_DIR" ]; then
    log "→ affective_playlists curate --scope fav_songs"
    (cd "$AFFECTIVE_PLAYLISTS_DIR" && "${AFFECTIVE_PLAYLISTS_CMD[@]}") >> "$LOG_DIR/curate_fav_songs.log" 2>> "$LOG_DIR/curate_fav_songs.err.log" || OVERALL_RC=$?
fi
```

- [ ] **Step 2: Run wrapper dry-run**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/music_tools && bin/run_all.sh`

Expected: Existing scripts still run. `logs/curate_fav_songs.log` contains planned curation counts. No Apple Music curation apply is performed.

- [ ] **Step 3: Replace old genre-only sorter after dry-run is accepted**

Modify the script loop in `/Users/joeldebeljak/own_repos/music-curator/music_tools/bin/run_all.sh` from:

```bash
for s in "$SCRIPTS_DIR/sort_favourites_by_genre.js" "$SCRIPTS_DIR/route_albums_to_playlists.applescript" "$SCRIPTS_DIR/find_playlist_duplicates.js"; do
```

to:

```bash
for s in "$SCRIPTS_DIR/route_albums_to_playlists.applescript" "$SCRIPTS_DIR/find_playlist_duplicates.js"; do
```

Then change the curation command to apply:

```bash
AFFECTIVE_PLAYLISTS_CMD=(/usr/bin/env python3 "$AFFECTIVE_PLAYLISTS_DIR/main.py" curate --scope fav_songs --apply)
```

- [ ] **Step 4: Update README**

Replace the `sort_favourites_by_genre.js` row in `/Users/joeldebeljak/own_repos/music-curator/music_tools/README.md` with:

```markdown
| `../affective_playlists/main.py curate --scope fav_songs --apply` | Holt Tracks aus „Favourite Songs“ und sortiert sie in `Fav Songs / <Genre> / Fav <Genre> <Temper>` Playlists. Die gleiche Logik wird auch von der Web-UI verwendet. | im Wrapper |
```

- [ ] **Step 5: Commit inside the owning repo if initialized**

`music_tools` is not currently a Git repository. If it has been initialized by then, run:

```bash
cd /Users/joeldebeljak/own_repos/music-curator/music_tools
git add bin/run_all.sh README.md
git commit -m "feat: schedule fav song curation"
```

If `music_tools` is still not a Git repository, skip the commit and record the changed files in the final handoff.

---

### Task 10: Verification Pass

**Files:**
- All files touched in Tasks 1-9.

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists
pytest \
  tests/test_curation_models.py \
  tests/test_curation_store.py \
  tests/test_apple_music_structure.py \
  tests/test_curation_service.py \
  tests/test_web_server.py::TestCurationEndpoints \
  tests/test_main_cli_platform.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && pytest tests/ -v`

Expected: PASS. If tests unrelated to curation fail, document the failing test names and confirm they predate this work before merging.

- [ ] **Step 3: Run web server and inspect UI**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && python -m src.web_server`

Open: `http://127.0.0.1:4000`

Expected:
- `Curation Review` loads.
- Refresh Preview shows Favourite Songs assignments grouped by genre and temperament.
- Apply requires a browser confirmation dialog.
- Applying with confirmation writes only through `/api/curation/apply`.

- [ ] **Step 4: Run Apple Music dry-run CLI**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && python main.py curate --scope fav_songs`

Expected: Prints planned assignment and change counts; no Apple Music writes.

- [ ] **Step 5: Run Apple Music apply only after reviewing dry-run**

Run: `cd /Users/joeldebeljak/own_repos/music-curator/affective_playlists && python main.py curate --scope fav_songs --apply`

Expected:
- Folder `Fav Songs` exists.
- Genre folders exist under `Fav Songs`.
- Playlists named `Fav <Genre> <Temper>` exist.
- Favourite Songs tracks are copied into matching target playlists.
- Duplicate Favourite Songs tracks are skipped immediately by persistent ID and normalized `artist + title`.
- If the Apple Music library is not connected, stop before this live apply and record it as deferred rather than failed.

---

## Self-Review

- Spec coverage: The plan covers the approved UI direction, separate Favourite Songs folder, genre folders, `Fav <Genre> <Temper>` playlist names, dry-run before apply, and scheduled automation reuse.
- No incomplete markers: The plan contains concrete paths, commands, route names, class names, and expected outcomes.
- Type consistency: Assignment types use `playlist` and `fav_track`; temperaments use `Woe`, `Frolic`, `Dread`, `Malice`; Favourite Songs target paths always use `["Fav Songs", "<Genre>", "Fav <Genre> <Temper>"]`.
- Scope check: This is one coherent feature with two consumers: Web UI and scheduled Favourite Songs sync. Whole-playlist curation is represented in the UI design, while the first implementation plan focuses apply logic on Favourite Songs because that is the automatic behavior requested.
