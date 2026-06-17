# Apply Job And Metadata Safety Design

## Goal

Finish the next safe slice of the music curation workflow:

- remove `datetime.utcnow()` deprecation warnings from job persistence paths
- replace the locked curation apply response with a real background job
- provide a reversible local library smoke-test path for the connected SSD library
- extend local metadata enrichment toward MP3 year and cover writes

## Constraints

Full Apple Music writes are high risk. The UI may queue a full curation apply only after the existing gates pass: fresh snapshot, successful smoke test, matching one-use token, explicit confirmation, and background job creation. Development and verification must not trigger a full library apply.

MP3 metadata writes must be testable without touching the real library. Unit tests use temporary files or mocked tag objects. Any real-library validation remains a small manual smoke test, not an automated bulk write.

## Architecture

Job timestamps use a single timezone-aware UTC helper shared by SQLAlchemy defaults and `JobStore`. Realtime payload timestamps use the same UTC convention.

Curation apply becomes a Celery task in `src/tasks.py`. The web endpoint validates gates, creates a persistent `JobStore` record, consumes the smoke-test token only after job creation succeeds, and queues the task. The task calls `CurationService.apply_fav_songs(confirmed=True)` and stores result/error state.

Metadata enrichment remains separate from curation. MP3 year writes live in a focused tag writer path near existing audio tag handling, while cover embedding continues through `CoverArtEmbedder`. The first implementation surface is explicit, testable functions rather than implicit bulk mutation.

## Safety Rules

- Never run full curation apply from tests.
- Never consume a smoke-test token if queuing fails.
- Keep smoke-test cleanup verification.
- Keep MP3 writes behind explicit function calls.
- Prefer preview/dry-run output before any manual real-library write.

