# Fav Songs Main Genres Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse raw Apple Music genre labels into the requested Fav Songs main genres before building `Fav Songs / <Genre> / Fav <Genre> <Temper>` paths.

**Architecture:** Add a focused genre canonicalization helper in `src/curation_models.py` and route all Fav track target paths through it. Keep playlist assignments on the existing display normalization behavior unless the caller opts into Fav track paths. Update curation preview tests so raw labels like `Indie Rock`, `House`, `IDM/Experimental`, `Disco`, `Funk`, `Soul`, `Blues`, `Pop`, and `Lounge` land in distinct requested folders.

**Tech Stack:** Python 3, pytest, existing `CurationAssignment` and `CurationService` model layer.

---

### Task 1: Canonical Fav Genre Labels

**Files:**
- Modify: `src/curation_models.py`
- Test: `tests/test_curation_models.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_normalize_fav_genre_label_collapses_requested_main_genres():
    assert normalize_fav_genre_label("indie_rock") == "Alternative & Indie"
    assert normalize_fav_genre_label("rock_y_alternativo") == "Rock"
    assert normalize_fav_genre_label("house") == "House"
    assert normalize_fav_genre_label("techno") == "Techno"
    assert normalize_fav_genre_label("breakbeat") == "Breakbeat"
    assert normalize_fav_genre_label("idm/experimental") == "IDM"
    assert normalize_fav_genre_label("disco") == "Disco"
    assert normalize_fav_genre_label("funk") == "Funk"
    assert normalize_fav_genre_label("soul") == "Soul"
    assert normalize_fav_genre_label("jazz") == "Jazz"
    assert normalize_fav_genre_label("blues") == "Blues"
    assert normalize_fav_genre_label("pop") == "Pop"
    assert normalize_fav_genre_label("lounge") == "Lounge"
```

Update Fav track serialization expectations so `genre_label` and `target_path` use the canonical Fav label.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_curation_models.py -q`

Expected: FAIL because `normalize_fav_genre_label` is not defined and Fav paths still use raw normalized labels.

- [ ] **Step 3: Implement minimal helper**

Add `normalize_fav_genre_label(genre: str) -> str` with ordered regex matching for:

`House`, `Techno`, `Breakbeat`, `IDM`, `Disco`, `Funk`, `Soul`, `Jazz`, `Blues`, `Pop`, `Lounge`, `Folk & Singer-Songwriter`, `Alternative & Indie`, `Rock`, `Electronic`, `Hip Hop & RnB`, `Latin & Brasileiro`, `African & World`, `Soundtrack`, `Sonstige`.

Use it for Fav track `target_path()`, `fav_playlist_name()`, and `to_dict()["genre_label"]`.

- [ ] **Step 4: Verify model tests pass**

Run: `.venv/bin/python -m pytest tests/test_curation_models.py -q`

Expected: PASS.

### Task 2: Preview Grouping Uses Canonical Fav Labels

**Files:**
- Modify: `src/curation_service.py`
- Test: `tests/test_curation_service.py`

- [ ] **Step 1: Write failing preview test**

Add a fake Apple Music class with tracks for `Rock`, `Indie Rock`, `House`, `Techno`, `IDM/Experimental`, `Disco`, `Funk`, `Soul`, `Jazz`, `Blues`, `Pop`, and `Lounge`, then assert preview grouped keys and target paths use the requested main genres once.

- [ ] **Step 2: Run service tests to verify failure**

Run: `.venv/bin/python -m pytest tests/test_curation_service.py -q`

Expected: FAIL because grouping still follows `genre_label` from raw normalization.

- [ ] **Step 3: Route grouping through canonical label**

Update `_group_assignments()` to group on already-canonical `genre_label`. If needed, reserialize assignments through `CurationAssignment.to_dict()` so previews, snapshots, apply limits, and changes share one labeling path.

- [ ] **Step 4: Verify service tests pass**

Run: `.venv/bin/python -m pytest tests/test_curation_service.py -q`

Expected: PASS.

### Task 3: Regression Verification

**Files:**
- Modify only if tests expose a gap: `src/curation_models.py`, `src/curation_service.py`
- Test: `tests/test_curation_models.py`, `tests/test_curation_service.py`, `tests/test_apple_music_structure.py`

- [ ] **Step 1: Run focused regression suite**

Run: `.venv/bin/python -m pytest tests/test_curation_models.py tests/test_curation_service.py tests/test_apple_music_structure.py -q`

Expected: PASS.

- [ ] **Step 2: Inspect final diff**

Run: `git diff -- src/curation_models.py src/curation_service.py tests/test_curation_models.py tests/test_curation_service.py docs/superpowers/plans/2026-06-11-fav-songs-main-genres.md`

Expected: Only canonical genre mapping, tests, and this plan changed.
