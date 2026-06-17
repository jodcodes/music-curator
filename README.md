# Music Curator

Personal music automation tools for Apple Music, Spotify playlist sync, and local library maintenance.

This repo is intentionally split into small tools instead of one shared framework. Some duplication is cheaper than a brittle abstraction.

## Tools

- [`affective_playlists/`](affective_playlists/) — Apple Music playlist curation: 4tempers mood buckets, Fav Songs genre/temper folders, metadata enrichment, playlist organization.
- [`apple2spfy/`](apple2spfy/) — Apple Music to Spotify playlist sync/export helpers.
- [`music_tools/`](music_tools/) — small operational scripts for local music-library cleanup and maintenance.

## Safety

Most live operations touch Music.app playlists or external APIs. Prefer preview/dry-run commands first. Keep backups of important playlists before applying bulk changes.

## Setup

Each tool has its own setup notes and dependencies. Start in the tool folder you want to use:

```bash
python3 music_curator.py --list
python3 music_curator.py affective --help

cd affective_playlists
python -m pytest tests/test_curation_models.py tests/test_curation_service.py tests/test_apple_music_structure.py -q
```

Copy `.env.example` to `.env` only for local use. Never commit real tokens, exports, logs, caches, or Music snapshots.

## Repo Plan

See [`docs/music-curator-abstraction-plan.md`](docs/music-curator-abstraction-plan.md). Short version: keep the tools separate, only extract shared code when two tools actively need the same behavior.
