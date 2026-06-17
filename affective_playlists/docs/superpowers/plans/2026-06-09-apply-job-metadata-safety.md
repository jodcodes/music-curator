# Apply Job And Metadata Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make curation apply and metadata writes safer, observable, and ready for small live validation.

**Architecture:** Replace naive UTC calls with a shared aware UTC helper. Queue full curation apply through Celery and persistent jobs after existing UI/API gates pass. Add explicit MP3 metadata write surfaces for year and cover behavior, keeping real-library validation manual and small.

**Tech Stack:** Python 3.14, Flask, Celery, SQLAlchemy, pytest, mutagen, AppleScript via `osascript`.

---

### Task 1: Timezone-Aware Job Timestamps

**Files:**
- Modify: `src/db.py`
- Modify: `src/job_store.py`
- Modify: `src/realtime.py`
- Test: `tests/test_job_persistence.py`
- Test: `tests/test_web_server.py`

- [ ] Write a failing test that creates/updates a job with warnings treated as errors: `pytest tests/test_web_server.py::TestEnrichmentStartEndpoint::test_enrichment_start_returns_200 -W error::DeprecationWarning`.
- [ ] Add `utc_now()` in `src/db.py` returning `datetime.now(timezone.utc)`.
- [ ] Replace SQLAlchemy `default=datetime.utcnow`, `onupdate=datetime.utcnow`, and all `JobStore` explicit `datetime.utcnow()` calls with `utc_now()`.
- [ ] Replace realtime `datetime.utcnow().isoformat()` with `utc_now().isoformat()`.
- [ ] Run targeted warning-as-error tests and the full suite.
- [ ] Commit with `fix: use timezone-aware job timestamps`.

### Task 2: Persistent Background Curation Apply

**Files:**
- Modify: `src/tasks.py`
- Modify: `src/web_server.py`
- Test: `tests/test_web_server.py`
- Test: `tests/test_background_jobs.py`

- [ ] Write failing tests that `/api/curation/apply` creates a `JobStore` job and queues `apply_curation.apply_async()` after confirmation, mini-test, token, and snapshot gates pass.
- [ ] Write a failing test that a queue failure does not consume the smoke-test token.
- [ ] Add a Celery task named `affective_playlists.tasks.curation:apply_curation` that marks the job running, calls `CurationService().apply_fav_songs(confirmed=True)`, stores the result, and marks the job completed or failed.
- [ ] Update `/api/curation/apply` to return `202`, `{success: true, status: "queued", job_id}` only after job creation and queue submission succeed.
- [ ] Keep direct full apply out of tests by mocking the Celery task and `CurationService`.
- [ ] Run targeted curation/background tests and the full suite.
- [ ] Commit with `feat: queue curation apply jobs`.

### Task 3: Small Reversible Library Validation Command

**Files:**
- Modify: `main.py`
- Modify: `src/curation_service.py`
- Test: `tests/test_main_cli_platform.py`
- Test: `tests/test_curation_service.py`

- [ ] Write failing tests for a CLI path that runs only the existing curation smoke test and reports cleanup/leftovers without full apply.
- [ ] Add a CLI flag or subcommand path for smoke-test-only validation.
- [ ] Ensure it uses `run_fav_songs_smoke_test()` and never calls `apply_fav_songs()`.
- [ ] Run targeted CLI/service tests and the full suite.
- [ ] Commit with `feat: add curation smoke validation command`.

### Task 4: MP3 Year And Cover Write Surface

**Files:**
- Modify: `src/audio_tags.py`
- Modify: `src/cover_art.py`
- Modify: `src/metadata_enrichment.py`
- Test: `tests/test_audio_tags.py`
- Test: `tests/test_cover_art.py`
- Test: `tests/test_metadata_enrichment.py`

- [ ] Write failing tests for MP3 year write using a temporary file or mocked mutagen ID3 object.
- [ ] Write failing tests that cover art writes still reject missing files and unsupported image data.
- [ ] Add explicit metadata write methods for supported MP3 fields, starting with year.
- [ ] Wire metadata enrichment so year/cover writes are explicit and report skipped/failed status.
- [ ] Run targeted metadata/cover tests and the full suite.
- [ ] Commit with `feat: add explicit mp3 metadata writes`.

### Task 5: Final Verification

**Files:**
- Review: all changed files

- [ ] Run `pytest tests -q`.
- [ ] Run `pytest tests/test_web_server.py tests/test_background_jobs.py tests/test_metadata_enrichment.py tests/test_cover_art.py -q`.
- [ ] Confirm no `datetime.utcnow()` warnings remain in test output.
- [ ] Do not run full curation apply.
- [ ] Report manual SSD/library smoke-test instructions separately.

