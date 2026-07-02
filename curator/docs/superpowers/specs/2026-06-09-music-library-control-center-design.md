# Music Library Control Center Design

## Context

The current curation UI can preview the real Apple Music `Favourite Songs` playlist and produces the desired target structure:

`Fav Songs / <Genre> / Fav <Genre> <Temper>`

The live library currently has 4106 favourite songs, 139 genres, 4430 planned changes, and 0 skipped tracks. A reversible one-track smoke test confirmed that nested folder creation, track copy, duplicate detection, and cleanup can work safely when routed through the AppleScript apply path.

The next UI iteration should simplify the app around the core workflow instead of exposing many equal-weight tabs and long track/card lists.

## Goals

- Make the first screen useful immediately without forcing a fresh Music.app scan.
- Center the product around `Fav Songs` curation: read, preview, smoke-test, apply.
- Make slow Apple Music operations explicit and visible.
- Prevent accidental full writes to Apple Music.
- Keep the first implementation small enough to ship and verify.

## Non-Goals

- No full redesign of metadata enrichment, mood analysis, or legacy playlist organization.
- No manual per-song reassignment in phase 1.
- No automatic full apply on app load or after preview.
- No background scheduler `--apply` enablement.

## Recommended UX

Use a single `Fav Songs` control center as the main curation surface.

The page has three columns:

1. Left navigation and system status
   - `Fav Songs`
   - `Metadata`
   - `Jobs`
   - `Settings`
   - SSD, Music.app, library path, and snapshot age

2. Main review area
   - Header: `Fav Songs`
   - Actions: `Snapshot laden`, `Neu lesen`
   - Summary counters: songs, genres, planned changes, skipped tracks
   - Search/filter bar
   - Genre x Temper matrix with columns `Woe`, `Frolic`, `Dread`, `Malice`
   - Details open only when a genre row is selected

3. Write-safety panel
   - Shows whether apply is locked or available
   - `Mini-Test ausführen` creates a temporary one-track folder path, validates copy and duplicate-skip, then removes it
   - `Full Apply vorbereiten` stays locked until the current snapshot is fresh and the mini-test passed

## Performance Design

Use snapshot-first loading.

- The UI renders the last saved curation snapshot immediately.
- `Neu lesen` explicitly refreshes from Music.app using the fast bulk-read path.
- The backend stores snapshot metadata: created time, library source, total tracks, total genres, skipped count, and planned changes count.
- The preview response should support summary-first rendering so the UI does not need to render thousands of track cards up front.

Use bulk AppleScript reads for library data.

- Read `persistent ID`, `name`, `artist`, and `genre` as bulk properties.
- Avoid per-track AppleScript loops for large reads.
- Track-level details should be lazy-loaded by genre if needed.

Use jobs for long write operations.

- Full apply should become a background job with progress.
- The UI polls or streams job status.
- The request must not block the browser while thousands of changes are applied.

## API Shape

Phase 1 can add or adapt these endpoints:

- `GET /api/curation/snapshot?scope=fav_songs`
  - Returns the last saved snapshot, or an empty state if none exists.

- `POST /api/curation/refresh`
  - Starts or runs a Music.app refresh.
  - Produces a new snapshot.
  - Returns summary counts and snapshot metadata.

- `GET /api/curation/preview?scope=fav_songs`
  - Can continue to return full preview data for compatibility.
  - Should prefer grouped data for the matrix.

- `POST /api/curation/smoke-test`
  - Runs the one-track temporary-folder write test.
  - Must clean up after itself.
  - Returns copied count, duplicate-skip result, cleanup result, and any leftover object names.

- `POST /api/curation/apply`
  - Remains confirmation-protected.
  - For full apply, should create a job instead of doing all work synchronously.

## Data Model

Add a persisted curation snapshot:

- `scope`
- `created_at`
- `library_name` or source path when available
- `total_assignments`
- `total_genres`
- `total_changes`
- `total_skipped`
- `grouped` genre/temper summary
- optional full assignments payload
- snapshot freshness status

The existing override store remains separate. Phase 1 only reads and displays the current automatic assignment output.

## Safety Rules

- Full apply is disabled until:
  - a current snapshot exists
  - skipped/error count is acceptable
  - the mini-test passed in the current session or against the current library
  - the user confirms the full write

- Mini-test must:
  - use a unique temporary root folder
  - copy exactly one source track
  - run duplicate copy once and verify it does not add another track
  - remove the temporary root folder
  - report any leftover folder or playlist names

- Full apply must:
  - never run from page load
  - never run from `Dry Run`
  - require explicit confirmation
  - show progress and errors

## Testing

Automated tests:

- Snapshot store save/load/freshness behavior
- API returns cached snapshot without hitting Music.app
- Refresh uses Music.app reader and updates snapshot
- Matrix grouping by genre and all four tempers
- Mini-test cleanup success and failure reporting with mocked AppleScript
- Apply remains blocked without explicit confirmation
- Apply starts a job rather than blocking synchronously

Live manual checks:

- `Favourite Songs` count matches the preview assignment count
- UI loads from snapshot without a fresh Apple Music scan
- `Neu lesen` completes and updates snapshot age
- Mini-test creates and removes exactly one temporary path
- Full apply remains locked until gates pass

## Phasing

Phase 1:

- Snapshot cache
- Control Center page
- Genre x Temper matrix
- Mini-test gate
- Full apply remains guarded

Phase 2:

- Manual genre/temper overrides in the UI
- Track-level drilldown and reassignment
- Metadata enrichment controls for cover/year
- Scheduler integration after live apply is trusted
