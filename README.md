# music-curator

Monorepo for Apple Music automation tools.

```
music-curator/
├── curator/          ← main product: enrich · mood · organize · curate
├── apple2spfy/       ← sync Apple Music playlists to Spotify
├── pitch2play/       ← pitch detection and playlist routing
├── music_tools/      ← LaunchAgent + JXA/AppleScript automation scripts
└── music_curator.py  ← top-level launcher
```

## Products

| Tool | What it does | Requires |
|---|---|---|
| [`curator`](curator/) | Metadata enrichment, AI mood analysis, playlist org, dedup, curation | macOS + Music.app |
| [`apple2spfy`](apple2spfy/) | Export/sync Apple Music playlists → Spotify | macOS |
| [`pitch2play`](pitch2play/) | Pitch detection → playlist routing | macOS |

## Quick start

```bash
# list available tools
python3 music_curator.py --list

# launch curator interactive menu
python3 music_curator.py curator

# or go directly into curator
cd curator
python -m pip install -e ".[dev]"
curator
```

## Automation

`music_tools/` contains a macOS LaunchAgent (`com.joeldebeljak.music-tools`) that fires on SSD mount + AC power and runs:

1. `curator curate --scope fav_songs` — Favourite Songs curation
2. `sort_favourites_by_genre.js` — sort favourites by genre
3. `route_albums_to_playlists.applescript` — route albums into playlists
4. `find_playlist_duplicates.js` — flag cross-playlist duplicates

Logs land in `logs/`. The agent enforces a 12-hour minimum interval between runs.

## Safety

All write operations default to **dry-run / preview**. Pass `--apply` explicitly to commit changes. Back up important playlists before bulk operations.

## Docs

- [`curator/README.md`](curator/README.md) — full curator feature reference
- [`curator/QUICKSTART.md`](curator/QUICKSTART.md) — 5-minute setup
- [`docs/music-curator-abstraction-plan.md`](docs/music-curator-abstraction-plan.md) — architecture decisions
