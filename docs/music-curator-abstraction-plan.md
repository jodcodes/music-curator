# Music Curator Abstraction Plan

Goal: keep the family of music tools coherent without over-abstracting the working workflows.

## 1. Repo Boundary

- Keep one top-level family name: `music-curator`.
- Treat `affective_playlists` as the main product repo surface.
- Keep `apple2spfy` separate.
- Keep `music_tools` as bundled commands inside `affective_playlists`, not a separate product boundary.
- Move shared code only when at least two feature areas use it.

Suggested target layout:

```text
music-curator/
  affective_playlists/
  apple2spfy/
  music_tools/   # bundled through affective_playlists tools
  docs/
  tests/
  README.md
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

- `affective_playlists` — temperament, Fav Songs curation, metadata enrichment, playlist organization, and bundled maintenance commands
- `apple2spfy` — playlist sync/export/cache
- `music_tools` — operational scripts invoked through the `affective_playlists tools` command group

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
2. Keep current folders, but expose the merged `affective_playlists` command surface consistently.
3. Centralize duplicated config/utilities only when touched by active work.
4. Introduce `pyproject.toml` and one CLI entrypoint.
5. Move to a package/workspace layout only if packaging or imports require it.

Principle: abstract seams, not dreams. If only one feature uses code, leave it local.
