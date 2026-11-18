# curator

> Apple Music management CLI — enrich metadata, analyse mood, organise playlists, deduplicate tracks.

Part of the [`music-curator`](https://github.com/jodcodes/music-curator) monorepo. Requires macOS + Music.app for live operations; most tests run without it.

## Features

| Command | What it does | Needs Music.app |
|---|---|---|
| `curator scan` | Sync library state into local DB | ✓ |
| `curator enrich` | Fill metadata from MusicBrainz, AcousticBrainz, Discogs, Last.fm | ✓ |
| `curator mood` | AI mood classification of playlists (OpenAI / Claude) | ✓ |
| `curator organize` | Preview folder moves for explicit playlist IDs; apply a reviewed plan | ✓ |
| `curator dedupe` | Find and remove duplicate tracks across playlists | ✓ |
| `curator curate` | Favourite Songs curation pipeline | ✓ |
| `curator localize` | Replace unavailable playlist tracks with verified local files | ✓ |
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

# Preview folder moves for explicit playlist IDs; save the exact plan
curator organize --playlist-id 0123456789ABCDEF \
  --save-plan data/curation/playlist_split_reviews/organize-review.json

# Only after review: apply that exact saved plan
curator organize --plan data/curation/playlist_split_reviews/organize-review.json --apply --yes

# Find duplicates across playlists
curator dedupe

# Run Favourite Songs curation (preview)
curator curate --scope fav_songs

# Preview local replacements for every own playlist (no changes)
curator localize

# Check current state
curator status
curator history

# Export library state to JSON
curator export --output my_library.json
```

## Local playlist replacement

`curator localize` scans all own Music.app playlists and writes a
`localize-report.json` preview. It searches the configured local Music library
for one exact artist/title match (and exact album when the playlist track has an
album). Fuzzy scores are never used.

```bash
# Preview all own playlists; changes nothing.
curator localize

# Inspect a single playlist.
curator localize --playlist "Playlist Name"

# Apply only exact, unique matches after reviewing localize-report.json.
curator localize --apply
```

The default source is `/Volumes/2TB_SSD/Media (Musik Mediathek)/Music Library
[2025-06-20].musiclibrary`; override it with `--source PATH` when needed.
When given a `.musiclibrary` bundle, the command searches its sibling `Music/`
folder, where the audio files are stored.
`--apply` imports the local file, adds it to the playlist, and only then removes
the old playlist entry. Remixes, live versions, remasters, covers, unavailable
files, and ambiguous matches are reported but never replaced automatically.

## Split oversized playlists

`curator split` previews only explicitly selected persistent playlist IDs.
Repeat `--playlist-id` to select multiple sources. Sources with at most 100
tracks are reported as skipped. Larger sources become balanced, contiguous
parts of at most 100 tracks: 101 tracks become 51 + 50. Track order and duplicate
occurrences are preserved. Parts are named `<source name> · 01`, `· 02`, etc.;
the source playlists are always retained.

```bash
# Run these commands from curator/.
# Read-only preview: no Music writes and no split journal creation.
curator split --playlist-id 0123456789ABCDEF

# Save the exact preview to a NEW JSON file for review; never overwrites.
mkdir -p data/curation/playlist_split_reviews
curator split --playlist-id 0123456789ABCDEF \
  --playlist-id FEDCBA9876543210 \
  --save-plan data/curation/playlist_split_reviews/split-review.json

# Separate local-only first-use action. Run ONCE before the first apply.
curator split --init-journal

# Only after reviewing that saved JSON: explicitly opt in to Music writes.
curator split --plan data/curation/playlist_split_reviews/split-review.json --apply --yes
```

Preview shows each source ID/name, skipped reason, ordered part names, counts,
source positions, and plan fingerprint. The saved JSON includes the exact
ordered track IDs. Apply consumes that saved plan; it never silently approves a
new preview. Missing `--plan`, `--apply`, or `--yes` prevents apply. Preview IDs
and export options cannot be combined with apply. If source membership or name
has changed, apply stops; create and review a new plan file explicitly.

Saved plans contain personal source names and track IDs. New exports request
owner-only permissions (`0600`, further restricted by the process umask). The
example review directory and the default split journal directory are Git-ignored;
keep private plans there or outside the repository. Custom export paths are not
automatically ignored. No existing files are overwritten or have their permissions
changed by export.

All invocations use the service's fixed journal at
`curator/data/curation/playlist_split_journal/`, resolved relative to the installed
module, independent of the current directory. Keep this directory and its
permanent `lock` file across runs. Apply never initializes missing/corrupt state,
and `--init-journal` refuses every existing directory, including an interrupted
first-use initialization. If state is missing or corrupt after prior use, stop
and restore the original trustworthy journal under exclusive control; never
initialize an empty replacement or use a separate checkout's empty journal to
retry against the same library.

Apply reports each part's status, known target ID (or `unknown`), and durably
confirmed occurrence count when it returns; this is not live streaming progress.
On failure, recorded sibling progress may be historical rather than freshly
verified Music state. Pending operations include their action, fingerprint and
identities. An `unresolved` write blocks further apply and requires manual
investigation: a timeout may have created a playlist or appended a track even
when confirmation was lost. Matching names do not prove ownership. There is no
automatic reconciliation, rollback, deletion or journal reset; partial outputs
remain. Completed retries verify recorded IDs and membership before doing any
further work. Exactly-once Music writes and live-library acceptance are not claimed.

## Seed playlists from recorded metadata

`curator seed-playlist` requires both a source playlist ID and an explicit member
track ID. Preview prints the actual source, seed title/artist, IDs, candidate scope,
ranking reasons, metadata warnings, output name and plan fingerprint. Candidates
come only from the existing library. The selected seed comes first; `--limit`
includes the seed and must be 1–30 (default 30). Recorded mood/genre determine
ranking; missing track mood remains visible, and genre fallback is labeled.
This does not infer acoustic similarity or assign playlist mood to tracks.

```bash
# From curator/: read-only preview, with no journal creation.
curator seed-playlist --playlist-id 0123456789ABCDEF --seed-track-id 0011223344556677

# Save privately in the existing Git-ignored review directory; never overwrite.
mkdir -p data/curation/playlist_split_reviews
curator seed-playlist --playlist-id 0123456789ABCDEF \
  --seed-track-id 0011223344556677 --limit 20 \
  --save-plan data/curation/playlist_split_reviews/seed-review.json

# ONCE only, if the shared split/seed journal has never been initialized.
# Skip this when curator split --init-journal already provisioned it.
curator seed-playlist --init-journal

# Only after reviewing the saved JSON: apply that exact plan.
curator seed-playlist --plan data/curation/playlist_split_reviews/seed-review.json --apply --yes
```

The saved plan contains personal source and library metadata and requests `0600`
permissions. Custom paths are not automatically Git-ignored. Apply uses the shared
split journal and all recovery rules above; it never creates replacement provenance,
regenerates approval, or adopts a same-named playlist. Source identity, ordered
membership, metadata and the entire library candidate snapshot must still match.
Changes require a new preview and explicit review. Sources remain intact; only a
new `Seed · <title>` playlist is created. Status/progress is reported after the
synchronous service returns; unresolved writes require manual recovery.

### Protected local browser workflow

The **Seed & Split** view offers read-only source selection, explicit seed selection
(up to 30 tracks), balanced split previews, exact JSON review and separately confirmed
apply. The **Organization** view works the same way for folder moves: select explicit
playlist IDs, preview the exact plan, then confirm that single reviewed plan. Source IDs distinguish duplicate playlist names. Selection changes discard the
review; plan IDs expire after 15 minutes and can be submitted only once in their
issuing session. Partial/unresolved reports are retained; writes are never retried
automatically. Initialize the shared journal using the CLI first; the web interface
cannot initialize or reset it.

Set `CURATOR_ACCESS_TOKEN` to a private random value of 32–1024 non-space ASCII
characters in the server environment, then start `python -m src.web_server` from
`curator/`. Startup reads Music and initializes the local database, so run it only
when you intend that access. The browser unlock form accepts a manually pasted token;
do not put it in a URL, command arguments, browser storage or source control.

The entire application requires an authenticated session (static assets and the
unlock form contain no library data). The server accepts only its configured loopback
Host and port, rejects foreign/null Origins and cross-site requests, and requires
same-origin CSRF headers for writes. Default host/port: `127.0.0.1:4000`.
`WEB_HOST` must be a literal loopback address or `localhost`; wildcard/remote binds,
Flask CLI startup, debugger and reloader are refused. Sessions last one hour and
are invalidated by server restart or a new unlock in the same browser. This is a
local access boundary, not protection against another process already running as
your operating-system user. Live Music/provider acceptance remains unverified.

## Organize playlists into folders

`curator organize` targets explicit persistent IDs, never names or "all playlists".
Preview reads the complete playlist/folder topology and each selected playlist's
ordered membership, classifies locally (provider enrichment is disabled) and prints
a versioned plan with a fingerprint. Configured labels are literal single folder
components, so `Disco/Funk/Soul` remains one folder name rather than a path.
Targets are `Genre/<configured label>`; missing folders are created only during apply.

```bash
# Read-only preview; optionally save privately to a new 0600 file.
curator organize --playlist-id 0123456789ABCDEF \
  --playlist-id FEDCBA9876543210 \
  --save-plan data/curation/playlist_split_reviews/organize-review.json

# Apply only that exact reviewed plan.
curator organize --plan data/curation/playlist_split_reviews/organize-review.json --apply --yes
```

Apply never re-classifies and never trusts client-supplied moves. It rejects a
tampered fingerprint, changed folder mapping, stale topology or changed track
membership, then re-verifies every created folder and every moved playlist against
an expected topology transition. The first failure or uncertainty stops all further
writes, reports moved/failed/skipped honestly and does not retry or roll back.
Playlist contents are not modified; only the folder placement changes. Web apply
consumes its reviewed plan ID once; a network failure after submission requires
manual inspection instead of resubmission.

## Playlist cover and public-sharing capabilities

`curator playlist-presentation` prints static, offline guidance without contacting
Music or reading/writing library/account state. Both cover and public sharing are
**manual**; automated setters, persistence, cloud propagation, public URLs and
search visibility remain unverified/unknown. Track artwork support does not
establish playlist-cover support. Public visibility requires explicit user action
and an Apple Music profile, with audience/account restrictions reviewed first.
See [the evidence and manual steps](docs/playlist-presentation.md). This command
does not publish anything or accept `--apply`.

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

Library/job state lives in `jobs.db` (SQLite, local). Playlist split provenance
uses the separate durable journal described above. Tables:

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
│   └── mood/               mood classification internals
└── archive/                 legacy specs and reports
```


**Unified suite for music analysis and organization**

A powerful, single-command music tool that combines three complementary features into one streamlined application for Apple Music.

## Features

- **Mood Analysis** - AI-powered playlist emotion classification (Woe, Frolic, Dread, Malice)
- **Metadata Enrichment** - Automatic metadata filling (BPM, Genre, Year, Cover Art) from multiple sources
- **Playlist Organization** - Intelligent genre-based playlist classification and organization
- **Music Tools** - Duplicate cleanup, genre cleanup, and favorite-song sorting helpers

## Quick Start (One Command)

### Installation

Clone and install in one command:

```bash
git clone https://github.com/jodcodes/music-curator.git
cd curator
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
   Add your OpenAI API key (required for mood analysis):
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
   curator
   ```

## Usage

### Interactive Menu (Recommended)
```bash
curator
```

Choose from:
1. **Mood Analysis** - AI-based emotion classification
2. **Metadata Enrichment** - Fill missing audio metadata
3. **Playlist Organization** - Genre-based sorting
4. **Music Tools** - Playlist cleanup and genre maintenance

### Command Line

```bash
# Show interactive menu
curator

# Run mood analysis
curator mood

# Fill metadata for a playlist
curator enrich --playlist "My Playlist"

# Preview organizing explicit playlists by genre (no writes)
curator organize --playlist-id 0123456789ABCDEF

# Run bundled music tools
curator tools --list
curator tools sort-favourites

# Show help
curator --help

# Show version
curator --version

# Verbose output
curator -v
```

## Project Structure

```
curator/
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
│   ├── mood_analyzer.py     ← Mood Analysis
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

### 1. Mood Analysis

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
2. View logs in `data/logs/` or `mood_analyzer.log`
3. Review configuration in `.env` and `data/config/`
4. Run with verbose mode: `curator -v`
5. Run tests: `pytest tests/ -v`

---

**Version**: 1.0.0  
**Last Updated**: January 4, 2026  
**Status**: Production Ready
