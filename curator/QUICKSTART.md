# curator — Quick Start

## 1. Install

```bash
cd curator
python -m pip install -e ".[dev]"
cp .env.example .env
```

## 2. Add API keys

Open `.env` and add at minimum:

```bash
OPENAI_API_KEY=sk-...          # required for: curator mood
```

Optional (richer metadata):

```bash
LASTFM_API_KEY=
DISCOGS_TOKEN=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

## 3. Run

```bash
curator          # interactive menu
curator --help   # all commands
```

---

## Common workflows

### Enrich metadata for a playlist

```bash
curator enrich --playlist "80s Mix"
curator enrich --library          # whole library
curator enrich --folder ~/Music   # local folder
```

Pulls BPM, year, genre, cover art from MusicBrainz → AcousticBrainz → Discogs → Last.fm in priority order.

### Analyse mood (AI)

```bash
curator mood --playlist "Chill"
curator mood --library --apply    # classify + move all playlists to mood folders
```

Classifies each playlist as **Woe / Frolic / Dread / Malice** using OpenAI or Claude.

### Organise playlists by genre

```bash
curator organize           # preview
curator organize --apply   # commit
```

### Find duplicates

```bash
curator dedupe             # dry-run report
curator dedupe --apply     # remove
```

### Library state

```bash
curator scan               # sync from Music.app
curator status             # last runs, job queue, dedup stats
curator history            # full run log
curator export --output lib.json
```

### Favourite Songs curation

```bash
curator curate --scope fav_songs          # preview
curator curate --scope fav_songs --apply  # apply
```

---

## File locations

| Path | What |
|---|---|
| `.env` | API keys (never commit) |
| `jobs.db` | SQLite state (runs, jobs, cache, dedup history) |
| `data/config/` | Genre map, playlist folders, curation sources |
| `data/config/whitelist.json` | Restrict enrichment to listed playlists |
| `logs/` | Per-feature log files |
| `mood_analyzer.log` | Mood analysis run log |

## Troubleshooting

**`curator: command not found`** — install first: `pip install -e .`

**`OPENAI_API_KEY not found`** — `curator mood` requires it; add to `.env`

**`Music.app not accessible`** — System Settings → Privacy & Security → Automation → grant Terminal access to Music

**Tests**

```bash
python -m pytest          # full suite (~60s, 582 tests)
python -m pytest tests/test_metadata_fill.py -q   # targeted
```


## One-Command Installation

```bash
git clone https://github.com/jodcodes/affective_playlists.git
cd affective_playlists
bash install.sh
```

That's it! The script handles:
- Python version checking
- Virtual environment setup
- Dependency installation
- Package installation
- Test running
- Configuration setup

## First Run

### 1. Configure API Credentials (Required)

```bash
vim .env
```

Add at minimum:
```bash
OPENAI_API_KEY=sk-your-key-here
```

Get your key from: https://platform.openai.com/api-keys

### 2. Activate Environment

Every new terminal session:
```bash
source activate.sh
```

You should see:
```
affective_playlists environment ready!

Available commands:
  affective-playlists                 # Interactive menu
  affective-playlists temperament     # AI-based Playlist Temperament Analysis
  affective-playlists enrich          # Metadata Filling and Enrichment
  affective-playlists organize        # Playlist Organization by Genre
```

### 3. Run the App

```bash
affective-playlists
```

Choose from the interactive menu.

## Usage Examples

### Interactive Menu
```bash
affective-playlists
```
Select option from menu.

### Temperament Analysis
```bash
# Interactive prompt for playlist selection
affective-playlists temperament

# With verbose logging
affective-playlists temperament -v
```

Analyzes emotional tone of playlists using OpenAI GPT.

### Metadata Enrichment
```bash
# Interactive prompt
affective-playlists enrich

# Specific playlist
affective-playlists enrich --playlist "My Playlist"

# Verbose mode
affective-playlists enrich --playlist "My Playlist" -v
```

Fills missing: BPM, Genre, Year, Cover Art

### Playlist Organization
```bash
# Interactive mode with confirmation
affective-playlists organize
```

Organizes playlists by genre (Hip-Hop, Jazz, Electronic, etc.)

## Configuration

### Environment Variables (.env)

**Required:**
```bash
OPENAI_API_KEY=sk-...
```

**Optional:**
```bash
SPOTIFY_CLIENT_ID=your-id
SPOTIFY_CLIENT_SECRET=your-secret
LASTFM_API_KEY=your-key
DISCOGS_TOKEN=your-token
```

Cover art fallback order for enrichment:
1. MusicBrainz (MBID/coverartarchive)
2. Spotify (requires Spotify credentials)
3. Last.fm (requires API key)
4. Discogs (requires token)

If provider credentials are missing, that source is skipped gracefully and the
next provider is attempted.

### Whitelist Configuration

Control which playlists to process in `data/config/whitelist.json`:

```json
{
  "enabled": true,
  "playlists": [
    "My Playlist 1",
    "My Playlist 2"
  ]
}
```

- `enabled: false` - Process all playlists (default)
- `enabled: true` - Process only listed playlists

## Common Commands

```bash
# After first installation, activate with:
source activate.sh

# Then use any of these:
affective-playlists                  # Interactive menu
affective-playlists --help           # Show help
affective-playlists --version        # Show version
affective-playlists -v               # Verbose mode

# Or specific features:
affective-playlists temperament
affective-playlists enrich
affective-playlists organize
```

## File Locations

- **Config**: `.env`
- **Logs**: `data/logs/` or `temperament_analyzer.log`
- **Cache**: `data/cache/`
- **Whitelist**: `data/config/whitelist.json`
- **Data**: `data/` (all application data)

## Troubleshooting

### "affective-playlists: command not found"
```bash
# Activate environment first
source activate.sh
affective-playlists
```

### "OPENAI_API_KEY not found"
```bash
# Edit .env
vim .env

# Add your key:
OPENAI_API_KEY=sk-your-key
```

### "Python 3 not found"
```bash
# Install Python 3.10+
brew install python@3.10
```

### "Music.app not accessible"
1. System Preferences → Security & Privacy
2. Give Terminal Full Disk Access
3. Restart Music.app

## Running Tests

```bash
source activate.sh
pytest tests/ -v
```

All 136+ tests should pass.

## Documentation

- **[README.md](README.md)** - Full documentation
- **[docs/INSTALLATION.md](docs/INSTALLATION.md)** - Detailed setup
- **[docs/OVERVIEW.md](docs/OVERVIEW.md)** - Architecture
- **[docs/requirements/](docs/requirements/)** - Specifications
- **[docs/rules/](docs/rules/)** - Development standards

## Next Steps

1. ✅ Run `bash install.sh`
2. ✅ Edit `.env` with API keys
3. ✅ Run `source activate.sh`
4. ✅ Run `affective-playlists`
5. 📖 Read [README.md](README.md) for detailed info

---

**That's it! Enjoy managing your music library. 🎵**
