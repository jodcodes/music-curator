# curator

> Apple Music management CLI — enrich metadata, analyse mood, organise playlists, deduplicate tracks.

Part of the [`music-curator`](https://github.com/jodcodes/music-curator) monorepo. Requires macOS + Music.app for live operations; most tests run without it.

## Features

| Command | What it does | Needs Music.app |
|---|---|---|
| `curator scan` | Sync library state into local DB | ✓ |
| `curator enrich` | Fill metadata from MusicBrainz, AcousticBrainz, Discogs, Last.fm | ✓ |
| `curator mood` | AI mood classification of playlists (OpenAI / Claude) | ✓ |
| `curator organize` | Move playlists into genre folders | ✓ |
| `curator dedupe` | Find and remove duplicate tracks across playlists | ✓ |
| `curator curate` | Favourite Songs curation pipeline | ✓ |
| `curator status` | Show last runs, job queue, dedupe stats | — |
| `curator history` | Browse run log | — |
| `curator export` | Export state to JSON | — |
| `curator tools` | Bundled JXA/AppleScript maintenance scripts | ✓ |

## Requirements

- Python 3.10+
- macOS (for any command that touches Music.app)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for `curator mood`

Optional (for richer metadata):
- `LASTFM_API_KEY`
- `DISCOGS_TOKEN`
- `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET`

## Installation

```bash
cd curator
python -m pip install -e ".[dev]"
cp .env.example .env   # then fill in your keys
```

## Usage

```bash
# Interactive menu (no args)
curator

# Scan your library
curator scan

# Enrich metadata for a playlist
curator enrich --playlist "80s Mix"

# Enrich entire library
curator enrich --library

# Analyse mood for a playlist (requires API key)
curator mood --playlist "Chill"

# Organise all playlists into genre folders (dry-run by default)
curator organize
curator organize --apply

# Find duplicates across playlists
curator dedupe

# Run Favourite Songs curation (preview)
curator curate --scope fav_songs

# Check current state
curator status
curator history

# Export library state to JSON
curator export --output my_library.json
```

## How it works

```
Apple Music ──► scan ──► SQLite (jobs.db)
                          │
                ┌─────────┼──────────┐
                ▼         ▼          ▼
             enrich     mood      organize
          (music DBs)  (LLM AI)  (classifier)
                │         │          │
                └────►  dedupe ◄─────┘
                          │
                       export / history / status
```

All parallel work goes through a shared bounded thread pool (`AFFECTIVE_MAX_WORKERS`, default 8). Every run is recorded in SQLite with a full audit trail.

## Mood classification

`curator mood` sends track metadata to an LLM (OpenAI or Claude) and classifies each playlist into one of four emotional buckets:

| Bucket | Character |
|---|---|
| **Woe** | Melancholy, introspection, sadness |
| **Frolic** | Joy, optimism, celebration |
| **Dread** | Tension, anxiety, dramatic |
| **Malice** | Rage, aggression, intensity |

Playlists are then moved into `4 Tempers/<Genre> <Mood>` folders.

## Metadata sources

Priority order for `curator enrich`:

1. MusicBrainz — primary (BPM, year, MBID)
2. AcousticBrainz — audio analysis (requires MBID)
3. Discogs — genre, release info
4. Wikidata — structured artist/track relationships
5. Last.fm — user-generated tags (lowest priority)

## Persistent state

All state lives in `jobs.db` (SQLite, local). Tables:

| Table | Contains |
|---|---|
| `jobs` | Background job queue |
| `library_runs` | Scan/enrich/dedupe run history |
| `track_dedup_history` | Dedup audit trail per track |
| `state_cache_entries` | Metadata query cache |

Switch to PostgreSQL by setting `DATABASE_URL=postgresql://...` — the repository interface is the same.

## Automation (LaunchAgent)

A macOS LaunchAgent (`com.joeldebeljak.music-tools`) fires automatically on SSD mount + AC power and runs `curator curate --scope fav_songs`. See [`music_tools/`](../music_tools/) for the agent and its companion JXA scripts.

## Development

```bash
# Run all tests
python -m pytest

# Run a targeted suite
python -m pytest tests/test_metadata_fill.py -q

# Environment variable reference
AFFECTIVE_MAX_WORKERS=8   # parallel worker cap
DATABASE_URL=sqlite:///jobs.db
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LASTFM_API_KEY=
DISCOGS_TOKEN=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

Tests do not require Music.app — all Apple Music calls are mocked. 582 tests, ~60s.

## Docs

```
curator/docs/
├── INSTALLATION.md          full dependency and setup guide
├── OVERVIEW.md              architecture overview
├── domain-guides/
│   ├── metadata/            enrichment pipeline details
│   ├── playlists/           playlist management concepts
│   └── temperament/         mood classification internals
└── archive/                 legacy specs and reports
```


**Unified suite for music analysis and organization**

A powerful, single-command music tool that combines three complementary features into one streamlined application for Apple Music.

## Features

- **Temperament Analysis** - AI-powered playlist emotion classification (Woe, Frolic, Dread, Malice)
- **Metadata Enrichment** - Automatic metadata filling (BPM, Genre, Year, Cover Art) from multiple sources
- **Playlist Organization** - Intelligent genre-based playlist classification and organization
- **Music Tools** - Duplicate cleanup, genre cleanup, and favorite-song sorting helpers

## Quick Start (One Command)

### Installation

Clone and install in one command:

```bash
git clone https://github.com/jodcodes/affective_playlists.git
cd affective_playlists
bash install.sh
```

That's it! The script will:
- Check Python version (3.10+)
- Create virtual environment
- Install all dependencies
- Install CLI commands
- Run tests
- Set up configuration directories

### First Time Setup

1. **Configure API credentials** (2 minutes):
   ```bash
   vim .env
   ```
   Add your OpenAI API key (required for temperament analysis):
   ```
   OPENAI_API_KEY=sk-your-key
   ```
   Optional APIs for better results:
   ```
   SPOTIFY_CLIENT_ID=your-id
   SPOTIFY_CLIENT_SECRET=your-secret
   LASTFM_API_KEY=your-key
   DISCOGS_TOKEN=your-token
   ```

   Cover art source behavior:
   - MusicBrainz (CoverArtArchive): works without credentials via MBID
   - Spotify: requires `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET`
   - Last.fm: requires `LASTFM_API_KEY`
   - Discogs: requires `DISCOGS_TOKEN`

2. **Activate environment** (every new terminal):
   ```bash
   source activate.sh
   ```

3. **Run the app**:
   ```bash
   affective-playlists
   ```

## Usage

### Interactive Menu (Recommended)
```bash
affective-playlists
```

Choose from:
1. **Temperament Analysis** - AI-based emotion classification
2. **Metadata Enrichment** - Fill missing audio metadata
3. **Playlist Organization** - Genre-based sorting
4. **Music Tools** - Playlist cleanup and genre maintenance

### Command Line

```bash
# Show interactive menu
affective-playlists

# Run temperament analysis
affective-playlists temperament

# Fill metadata for a playlist
affective-playlists enrich --playlist "My Playlist"

# Organize playlists by genre
affective-playlists organize

# Run bundled music tools
affective-playlists tools --list
affective-playlists tools sort-favourites

# Show help
affective-playlists --help

# Show version
affective-playlists --version

# Verbose output
affective-playlists -v
```

## Project Structure

```
affective_playlists/
├── install.sh              ← ONE-COMMAND SETUP
├── activate.sh             ← Activate environment
├── main.py                 ← CLI entry point
├── setup.py                ← Package setup
├── pyproject.toml          ← Modern Python config
├── requirements.txt        ← All dependencies
├── README.md               ← This file
├── QUICKSTART.md           ← Quick reference
├── .env.example            ← Environment template
│
├── src/                    ← All source code
│   ├── temperament_analyzer.py     ← Temperament Analysis
│   ├── metadata_fill.py             ← Metadata Enrichment
│   ├── plsort.py                    ← Playlist Organization
│   ├── apple_music.py               ← Shared Apple Music interface
│   ├── config.py                    ← Config management
│   ├── logger.py                    ← Logging
│   ├── normalizer.py                ← Text normalization
│   └── scripts/                     ← AppleScript files
│
├── tests/                  ← Test suite (136+ tests)
│   ├── test_*.py
│   └── ...
│
├── docs/                   ← Documentation
│   ├── rules/             ← Development standards
│   ├── domain-guides/     ← DEPRECATED (migrated to openspec/specs)
│   └── project-management/← Project tracking docs
│
├── openspec/               ← OpenSpec specification framework
│   ├── specs/             ← Domain specifications
│   └── changes/           ← Change packages
│
├── data/                   ← Centralized data
│   ├── config/            ← Configuration files
│   ├── logs/              ← Application logs
│   └── cache/             ← Cached metadata
│
└── venv/                   ← Virtual environment (created by install.sh)
```

## System Requirements

- **OS**: macOS 10.13+ (for Apple Music integration)
- **Python**: 3.10 or higher
- **Dependencies**: Automatically installed by `install.sh`

## Features Overview

### 1. Temperament Analysis

Classifies playlists into emotional categories using AI:
- **Woe** (Melancholic) - Sadness, loneliness, introspection
- **Frolic** (Sanguine) - Joy, celebration, energy
- **Dread** (Phlegmatic) - Fear, tension, anxiety
- **Malice** (Choleric) - Rage, aggression, intensity

Uses OpenAI GPT for intelligent classification.

### 2. Metadata Enrichment

Automatically fills missing metadata using multiple sources:
- **Sources**: MusicBrainz, AcousticBrainz, Discogs, Wikidata, Last.fm
- **Fields**: BPM, Genre, Release Year, Cover Art
- **Strategy**: Per-field enrichment (stops searching once field is found)
- **Smart**: ~50% fewer API calls than traditional approaches

### 3. Playlist Organization

Intelligently organizes playlists by genre:
- Hip-Hop, Electronic, Disco/Funk/Soul, Jazz, World, Rock
- Genre detection via track metadata
- One-command organization
- Undo support

## Testing

The installation script runs the full test suite (136+ tests). To run manually:

```bash
source activate.sh
pytest tests/ -v
```

Test categories:
- Unit tests for core modules
- Integration tests for workflows
- End-to-end tests
- API mocking
- Edge case coverage

## Code Quality

All code follows professional Python standards:
- Type hints on all functions
- Comprehensive docstrings (Google style)
- Specific exception handling
- Centralized logging
- Proper code organization

See [docs/rules/CODE_QUALITY_STANDARDS.md](docs/rules/CODE_QUALITY_STANDARDS.md) for details.

## Development

### Setup for Development
```bash
bash install.sh                    # Install everything
source activate.sh
pip install -e ".[dev]"           # Install dev tools
```

### Development Commands
```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
pylint src/

# Run tests
pytest tests/ -v --cov=src

# Run specific test
pytest tests/test_metadata_fill.py::TestMetadataFiller -v
```

### Spec-Driven Workflow (Brownfield)

The repository uses a brownfield spec-driven development approach:

- `AGENTS.md` - Agent workflow and quality gates
- `openspec/config.yaml` - OpenSpec project configuration
- `openspec/specs/` - Seeded domain specifications
- `docs/project-management/fix_plan.md` - Prioritized execution plan
- `docs/project-management/spec_debt.md` - Behavior not yet fully specified

Recommended OpenSpec cycle for changes:

```bash
openspec propose <change-name>
openspec verify
openspec archive <change-name>
```

## Troubleshooting

### Installation Issues

**Problem: "Python 3 not found"**
```bash
# Install Python 3.10+
brew install python@3.10
# Or download from https://www.python.org
```

**Problem: "Permission denied" on install.sh**
```bash
chmod +x install.sh
bash install.sh
```

**Problem: Venv not activating**
```bash
source venv/bin/activate
export PYTHONPATH="$(pwd):${PYTHONPATH}"
```

### Apple Music Issues

**Problem: "Music.app not accessible"**
1. Open System Preferences → Security & Privacy
2. Grant Terminal Full Disk Access
3. Restart Music.app

**Problem: Playlist not found**
- Check that playlist exists in Apple Music
- Try exact spelling
- The tool uses fuzzy matching for common variations

### API Issues

**Problem: "OPENAI_API_KEY not found"**
```bash
# Check .env file
cat .env

# Ensure it has the key:
OPENAI_API_KEY=sk-your-actual-key
```

**Problem: API rate limits**
- The tool respects rate limits
- Metadata enrichment queues requests automatically
- Wait a few minutes and retry

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Quick reference guide
- **[docs/INSTALLATION.md](docs/INSTALLATION.md)** - Detailed installation
- **[docs/OVERVIEW.md](docs/OVERVIEW.md)** - Architecture overview
- **[openspec/specs/](openspec/specs/)** - Authoritative feature specifications
- **[docs/rules/](docs/rules/)** - Development standards

## Contributing

1. Clone the repository
2. Run `bash install.sh`
3. Follow [CODE_QUALITY_STANDARDS.md](docs/rules/CODE_QUALITY_STANDARDS.md)
4. Run tests before submitting PRs: `pytest tests/ -v`

## License

MIT License - See [LICENSE](LICENSE) for details

## Support

Having issues?

1. Check the relevant docs in `docs/`
2. View logs in `data/logs/` or `temperament_analyzer.log`
3. Review configuration in `.env` and `data/config/`
4. Run with verbose mode: `affective-playlists -v`
5. Run tests: `pytest tests/ -v`

---

**Version**: 1.0.0  
**Last Updated**: January 4, 2026  
**Status**: Production Ready
