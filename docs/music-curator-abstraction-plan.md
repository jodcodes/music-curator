# Music Curator Abstraction Plan

Goal: make this repository publishable on GitHub without over-abstracting the working music workflows.

## 1. Repo Boundary

- Keep one top-level product: `music-curator`.
- Treat `affective_playlists`, `apple2spfy`, and `music_tools` as packages/modules under one repo, not separate hidden projects.
- Move shared code only when at least two modules use it.

Suggested target layout:

```text
music-curator/
  packages/
    affective_playlists/
    apple2spfy/
  tools/
    scripts/
  docs/
  tests/
  pyproject.toml
  README.md
  .env.example
```

## 2. Shared Core Layer

Create a small shared core when duplication appears:

- `music_curator_core/config.py` — env loading, path resolution, safe defaults
- `music_curator_core/music_library.py` — interfaces for Apple Music / Spotify clients
- `music_curator_core/genres.py` — canonical genre grouping, display labels, user-adjustable mappings
- `music_curator_core/jobs.py` — common job status/result objects if web/background jobs stay
- `music_curator_core/logging.py` — one logging setup

Do not move feature-specific behavior into core. Core should be boring plumbing.

## 3. Feature Modules

Keep features as thin, independent services:

- `affective_playlists` — temperament, Fav Songs curation, metadata enrichment, playlist organization
- `apple2spfy` — playlist sync/export/cache
- `music_tools/scripts` — one-off operational scripts until reused, then promote into package code

Each feature should expose:

- a service class for Python use
- a CLI command for user use
- tests for its public behavior

## 4. Configuration

- Keep secrets out of git; provide `.env.example` only.
- Prefer one config entrypoint over scattered config files.
- Make user-tuned data explicit under `data/config/` or a future `config/` folder:
  - genre groups
  - playlist folder names
  - API provider choices
  - safety limits for apply operations

Current genre grouping now starts in `affective_playlists/src/genre_groups.py`; later promote it to shared core only if `apple2spfy` or scripts also need it.

## 5. Public GitHub Cleanup

Before publishing:

- Add top-level `README.md` with: what it does, macOS/Music.app requirement, setup, dry-run first, safety warning.
- Add `LICENSE`.
- Add `.gitignore` for DBs, logs, caches, venvs, local exports, Music snapshots.
- Check for secrets in history before pushing.
- Decide whether to include generated docs/archive folders; keep only useful docs.
- Replace personal paths and local assumptions with documented config.

## 6. Test/CI Baseline

Start small:

- `python -m pytest affective_playlists/tests/test_curation_models.py affective_playlists/tests/test_curation_service.py affective_playlists/tests/test_apple_music_structure.py -q`
- Add GitHub Actions only for tests that do not require macOS Music.app access.
- Mark live Apple Music tests as manual/integration.

## 7. Migration Order

1. Add top-level README, LICENSE, `.gitignore`, and publish-safe `.env.example`.
2. Keep current folders; avoid layout moves until tests are stable.
3. Centralize duplicated config/utilities only when touched by active work.
4. Introduce `pyproject.toml` and one CLI entrypoint.
5. Move to `packages/` layout only if packaging or imports require it.

Principle: abstract seams, not dreams. If only one feature uses code, leave it local.
