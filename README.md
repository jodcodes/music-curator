# Music Curator

Umbrella workspace for music automation tools. The product surface is `affective_playlists`; `apple2spfy` stays separate.

Requires macOS for commands that talk to Music.app. Some read-only tests run on Linux in CI.

`affective_playlists` now also owns the bundled maintenance scripts from `music_tools`, so one CLI covers curation, dedupe, cleanup, and enrichment.

## Tools

- [`affective_playlists/`](affective_playlists/) — Apple Music playlist curation plus bundled maintenance scripts.
- [`apple2spfy/`](apple2spfy/) — Apple Music to Spotify playlist sync/export helpers.
- [`music_tools/`](music_tools/) — legacy script home; now wired into `affective_playlists tools`.

## Safety

Most live operations touch Music.app playlists or external APIs. Prefer preview/dry-run commands first. Keep backups of important playlists before applying bulk changes.

## Setup

Each tool has its own setup notes and dependencies. Start in the tool folder you want to use:

```bash
python3 music_curator.py --list
python3 music_curator.py
python3 music_curator.py affective --help
python3 music_curator.py apple2spfy --help
python3 music_curator.py music-tools --list

cd affective_playlists
python -m pytest tests/test_curation_models.py tests/test_curation_service.py tests/test_apple_music_structure.py -q
```

Track curation targets are intentionally flat:

```text
Fav Songs / <Genre>
4 Tempers / <Genre> <Temper>
```

Put source playlists for 4 Tempers in `affective_playlists/data/config/curation_sources.json`, then preview:

```bash
cd affective_playlists
python main.py curate --scope playlist_tempers
```

Install dependencies inside each tool folder when needed:

```bash
cd affective_playlists && python -m pip install -e ".[dev]"
cd apple2spfy && python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` only for local use. Never commit real tokens, exports, logs, caches, or Music snapshots.

## Repo Plan

See [`docs/music-curator-abstraction-plan.md`](docs/music-curator-abstraction-plan.md). Short version: keep `apple2spfy` separate, but treat `affective_playlists` + `music_tools` as one product surface.
