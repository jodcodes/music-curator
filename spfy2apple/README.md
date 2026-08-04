# spfy2apple — Spotify → Apple Music Playlist Sync

Syncs Spotify playlists you follow (but didn't create) to Apple Music.
Playlists land in an Apple Music playlist folder named **"curated by others"**.

## What it does

1. Reads your Spotify playlists and filters to those you **follow** (owner ≠ you)
2. For each playlist, decides what to do:
   - **New** (not in Apple Music, not tracked) → create playlist, add tracks, move to folder, set description
   - **Changed** (tracked, Spotify snapshot differs) → clear & re-add current tracks, update description
   - **Unchanged** (tracked, same snapshot) → skip
   - **User-created** (in Apple Music but not tracked by this tool) → skip
3. Uses a sync state file to track which playlists we've synced and their Spotify
   snapshot IDs, so unchanged playlists are skipped instantly on re-runs
4. **Playlist descriptions** are synced from Spotify to Apple Music (HTML entities
   and tags are cleaned up automatically)
5. **Searches the Apple Music catalog** via the free iTunes Search API + your
   library via AppleScript

## Requirements

- **macOS** with the **Music.app** running (for AppleScript playlist management)
- **Apple Music subscription**
- **Spotify API credentials** — same `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`
  as `apple2spfy` (in the root `.env`)
- **No Apple Developer Program required**

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Spotify credentials

Ensure `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are set in the root `.env`
(same as `apple2spfy`). Spotify OAuth opens on first run; the token is cached at
`~/.spotify_cache/.spfy2apple_token_cache`.

## Usage

```bash
# Preview what would be synced (default — no changes made)
python3 sync_from_spotify.py

# Actually create / update playlists
python3 sync_from_spotify.py --apply

# Force re-sync of all tracked playlists (ignore snapshot cache)
python3 sync_from_spotify.py --apply --force

# List followed Spotify playlists with sync status
python3 sync_from_spotify.py --list-only

# Show sync state (which playlists are tracked)
python3 sync_from_spotify.py --show-state

# Clear sync state (all playlists will be re-evaluated next run)
python3 sync_from_spotify.py --clear-state

# Custom folder name
python3 sync_from_spotify.py --apply --folder-name "From Spotify"

# Use a different filter file
python3 sync_from_spotify.py --apply --filter /path/to/my_playlists.txt

# Run with 8 parallel search workers
python3 sync_from_spotify.py --apply --workers 8
```

Or via the top-level launcher:

```bash
python3 music_curator.py spfy2apple --apply
```

## Playlist filter

`spfy2apple/playlist_filter.txt` lets you control which followed Spotify playlists
get synced. One playlist name per line. Matching is **case-insensitive** and
**Unicode-normalised**, so you can write names in any case:

```
white sands
what's new on because
intimate fonk
rosa welle
```

- Lines starting with `#` are comments
- If the file is empty or missing, **all** followed playlists are synced
- Use `--filter /path/to/file.txt` to specify a different file

`--list-only` shows which playlists match the filter (marked with `✓`) and warns
about filter entries that don't match any followed playlist (possible typos).

## How it works

### Track search (two-stage)

1. **Library search** (AppleScript) — searches your Apple Music library for
   each Spotify track. Found tracks are added to the playlist by persistent ID.
2. **Catalog search** (iTunes Search API, free, no auth) — for tracks not in
   your library, the iTunes Search API finds the track in the Apple Music
   catalog and returns the Apple Music URL.

### Playlist management (AppleScript)

Playlists are created and managed via AppleScript:
- `make new playlist` — create playlist (with description)
- `duplicate track to playlist` — add library tracks
- `delete every track of playlist` — clear playlist for updates
- `set description of playlist` — update description

### Folder management (AppleScript)

- Creating the "curated by others" folder
- Moving playlists into the folder

### Parallelism

Track searches run in parallel using `ThreadPoolExecutor`. Each worker may
spawn an `osascript` process (library search) or make an HTTP request
(catalog search).

- Default: **4 workers** (`SPFY2APPLE_SEARCH_WORKERS` env var or `--workers N`)

### How updates work

When a Spotify playlist changes (tracks added or removed), its `snapshot_id`
changes. On the next run, the script detects the change and:

1. Fetches the current track list from Spotify
2. Searches each track in the library + catalog
3. Clears all tracks from the Apple Music playlist
4. Re-adds all found library tracks

This mirrors the current Spotify state. Unchanged playlists are skipped
instantly (no track fetching or searching).

## State file

Sync state is stored at `spfy2apple/data/sync_state.json`. It tracks:

- Spotify playlist ID → playlist name, snapshot ID, track count, last sync time

Use `--show-state` to inspect it, or `--clear-state` to reset tracking.

## Limitations

- **Catalog tracks not in your library cannot be added to playlists
  automatically** without the Apple Developer Program ($99/year). The free
  iTunes Search API can find tracks in the catalog, but AppleScript can only
  add tracks already in your library. Tracks found only in the catalog are
  reported with their Apple Music URLs — you can add them manually, then
  re-run the sync to populate the playlists.
- Track matching uses title + artist search. Some tracks may not match due
  to naming differences between Spotify and Apple Music.
- Updates clear and re-add all tracks. This is reliable but may take time
  for large playlists. Use `--force` only when needed.
- Music.app must be running during sync (AppleScript is used for all
  playlist and folder operations).
