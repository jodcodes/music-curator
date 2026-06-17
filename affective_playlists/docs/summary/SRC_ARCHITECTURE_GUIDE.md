# Source Code Architecture Guide

**Location**: `docs/summary/SRC_ARCHITECTURE_GUIDE.md`  
**Date**: January 3, 2026  
**Status**: Active - Reference guide for src/ organization  
**Last Updated**: January 3, 2026

---

This document explains the structure and organization of the `src/` folder without requiring file reorganization.

## Overview

The `src/` folder contains 18 Python modules organized into 4 logical layers:

1. **Infrastructure & Configuration** - System setup and logging
2. **Data Layer** - Track metadata, enrichment, and database queries
3. **Application Layer** - Business logic for each feature
4. **Integration Layer** - External APIs and services

## Module Organization

### Layer 1: Infrastructure & Configuration

These modules handle system setup, configuration, and logging.

```
logger.py              # Logging configuration and setup
├─ setup_logger()     # Initialize logger with proper formatting
└─ Used by all modules for consistent logging

config.py             # Application configuration management
├─ load_centralized_whitelist()  # Load playlist whitelist
└─ Whitelist JSON configuration

normalizer.py         # Text normalization utilities
├─ TextNormalizer class
├─ normalize()        # Single string normalization
└─ normalize_list()   # Batch normalization with deduplication
```

### Layer 2: Data Layer - Metadata & Enrichment

These modules handle music metadata, querying external databases, and enrichment logic.

#### Core Metadata Models
```
metadata_enrichment.py  # Data structures for metadata
├─ MetadataField enum   # Available metadata fields (BPM, Genre, Year, etc.)
├─ DatabaseSource enum  # Available sources (MusicBrainz, Spotify, Last.fm)
├─ MetadataEntry       # Single metadata entry with source/confidence
├─ EnrichedMetadata    # Collection of enriched metadata for a track
└─ TrackIdentifier     # Track identification (artist, title, duration)
```

#### Database Query Modules
```
metadata_queries.py    # Unified database query orchestrator
├─ DatabaseQuery ABC         # Abstract base class for all queries
├─ MusicBrainzQuery          # MusicBrainz query implementation
├─ AcousticBrainzQuery       # AcousticBrainz query (audio analysis)
├─ DiscogsQuery              # Discogs query (vinyl database)
├─ WikidataQuery             # Wikidata query (structured data)
├─ LastfmQuery               # Last.fm query (user-generated tags)
└─ MetadataQueryOrchestrator # Coordinates queries in priority order

databases.py          # Legacy database interface (compatibility layer)
└─ Note: metadata_queries.py is the primary implementation

web_enrichment.py     # Web-based data fetching and caching
├─ WebDataFetcher class      # Fetch and cache web data
├─ fetch_lastfm_artist_tags()
├─ fetch_musicbrainz_genres()
└─ Cache management (TTL-based)
```

#### Track Metadata & Audio Processing
```
track_metadata.py     # Track metadata retrieval from APIs
├─ SpotifyTrackMetadata  # Query Spotify API
├─ MusicBrainzMetadata  # Query MusicBrainz API
└─ Audio feature queries (BPM, key, tempo)

audio_tags.py        # Audio file tag reading/writing
├─ TagManager class          # Read/write ID3, MP4 tags
├─ read_tags()              # Extract metadata from audio files
└─ write_tags()             # Write metadata to audio files
```

### Layer 3: Application Layer - Feature Implementations

These modules implement the three main features.

#### Feature 1: Metadata Enrichment (metad_enr)
```
metadata_fill.py      # Main metadata enrichment CLI
├─ MetadataFiller class       # Core enrichment logic
│  ├─ _get_playlist_ids()     # Get playlists from Apple Music
│  ├─ _get_track_ids()        # Get tracks from playlist/folder
│  ├─ enrich_playlist()        # Enrich all tracks in playlist
│  └─ enrich_tracks()          # Enrich specific tracks
├─ MetadataFillCLI class      # Command-line interface
└─ Entry point: main.py → run_metadata_enrichment()

QUERY PRIORITY ORDER (in metadata_queries.py):
1. MusicBrainz       (primary source)
2. AcousticBrainz    (audio analysis)
3. Discogs           (genre/year)
4. Wikidata          (structured data)
5. Last.fm           (tags/popularity)
```

#### Feature 2: Playlist Organization (plsort)
```
plsort.py           # Main playlist organization CLI
├─ run_playlist_organization()  # Main entry point
├─ classify_playlists()         # Classify by genre
├─ organize_playlists()         # Move to folders
└─ Dry-run support for safety

playlist_classifier.py  # Genre classification logic
├─ PlaylistClassifier class
├─ classify_track()     # Single track classification
└─ classify_playlist()   # Batch classification

playlist_manager.py    # Playlist manipulation
├─ PlaylistManager class
├─ create_folder()      # Create playlist folder
└─ move_to_folder()     # Move playlist to folder
```

#### Feature 3: Temperament Analysis (4tempers)
```
temperament_analyzer.py  # Main temperament analysis
├─ TemperamentAnalyzer class
│  ├─ analyze_playlist()    # Analyze single playlist
│  ├─ analyze_playlists()   # Batch analyze
│  └─ organize_by_temperament()  # Create temperament folders
├─ MusicLibraryClient ABC   # Apple Music interface
├─ LLMClient ABC            # LLM interface
└─ Entry point: main.py → run_temperament_analysis()

llm_client.py        # LLM integration (Claude, OpenAI, GPT)
├─ OpenAILLMClient   # OpenAI integration
├─ AnthropicLLMClient # Claude/Anthropic integration
└─ classify_track()   # LLM-based classification

prompts.py          # LLM prompts and templates
├─ TEMPERAMENT_SYSTEM_PROMPT
├─ TRACK_CLASSIFICATION_PROMPT
├─ PLAYLIST_ANALYSIS_PROMPT
└─ Genre suggestion prompts
```

### Layer 4: Integration Layer

These modules integrate with external systems.

```
apple_music.py      # Apple Music integration via AppleScript
├─ AppleMusicInterface class
├─ authenticate()    # Connect to Music.app
├─ get_playlists()  # List playlists
├─ get_tracks()     # Get playlist tracks
├─ update_track()   # Write metadata to track
└─ create_folder()  # Create playlist folder
```

## Data Flow Diagrams

### Metadata Enrichment Workflow (metad_enr)
```
User Input (Playlist/Folder)
    ↓
metadata_fill.py → get tracks from Apple Music
    ↓
For each track:
    ├→ metadata_queries.py
    │  ├→ MusicBrainzQuery (1st priority)
    │  ├→ AcousticBrainzQuery (2nd priority)
    │  ├→ DiscogsQuery (3rd priority)
    │  ├→ WikidataQuery (4th priority)
    │  └→ LastfmQuery (5th priority)
    │
    ├→ web_enrichment.py (caching)
    │
    └→ metadata_enrichment.py (merge/conflict resolution)
        ↓
    audio_tags.py → Write to file
        ↓
    apple_music.py → Update Apple Music metadata
```

### Temperament Analysis Workflow (4tempers)
```
User Input (Playlist)
    ↓
temperament_analyzer.py
    ├→ apple_music.py (get playlist)
    │
    ├→ For each track:
    │  ├→ llm_client.py (classify temperament)
    │  │  ├→ OpenAILLMClient (call OpenAI)
    │  │  └─ or AnthropicLLMClient (call Claude)
    │  │
    │  └─ prompts.py (provide classification prompt)
    │
    └→ playlist_manager.py (organize by temperament)
        ↓
    apple_music.py (create folders, move playlists)
```

### Playlist Organization Workflow (plsort)
```
User Input (Playlist)
    ↓
plsort.py
    ├→ apple_music.py (get playlist)
    │
    ├→ playlist_classifier.py
    │  └→ For each track: classify genre
    │
    └→ playlist_manager.py (organize)
        ↓
    apple_music.py (create folders, move playlists)
```

## Module Dependencies

### Core Dependencies (used by many modules)
- `logger.py` - Used by all modules
- `config.py` - Configuration management
- `normalizer.py` - Text processing

### Metadata Pipeline Dependencies
```
metadata_fill.py
    ↓ uses
metadata_queries.py + web_enrichment.py
    ↓ uses
metadata_enrichment.py (data structures)
    ↓ uses
apple_music.py + audio_tags.py
```

### Classification Pipeline Dependencies
```
temperament_analyzer.py + plsort.py
    ↓ uses
llm_client.py + playlist_classifier.py
    ↓ uses
apple_music.py + playlist_manager.py
```

## Adding New Features

To add a new feature without creating folders:

1. **Create the main feature module**: `my_feature.py`
2. **Add CLI entry point** in `main.py`: `run_my_feature()`
3. **Document in this README** under appropriate layer
4. **Use existing infrastructure**: logger, config, normalizer
5. **Leverage existing layers**: apple_music, metadata_enrichment, etc.

### Example: Adding "Export to Spotify" feature
```python
# new file: src/spotify_exporter.py

from logger import setup_logger
from metadata_enrichment import EnrichedMetadata
from apple_music import AppleMusicInterface
import spotipy

class SpotifyExporter:
    """Export Apple Music playlists to Spotify."""
    
    def __init__(self):
        self.logger = setup_logger("spotify_exporter")
        self.apple_music = AppleMusicInterface()
    
    def export_playlist(self, playlist_name: str) -> bool:
        """Export playlist to Spotify."""
        # Use existing infrastructure
        # Implement feature
        pass

# Then add to main.py:
def run_spotify_export(args=None):
    """Export to Spotify."""
    exporter = SpotifyExporter()
    # ... implementation
```

## File Naming Conventions

- **Core abstractions**: `*_enrichment.py`, `*_analyzer.py` - Data structures and base classes
- **Implementations**: `metadata_fill.py`, `metadata_queries.py` - Concrete implementations
- **Utilities**: `logger.py`, `normalizer.py`, `config.py` - Helper/utility modules
- **Integrations**: `apple_music.py`, `llm_client.py`, `track_metadata.py` - External integrations
- **Web/API**: `web_enrichment.py` - Web-based data fetching
- **Audio**: `audio_tags.py` - Audio file handling

## Import Best Practices

### DO ✓
```python
from logger import setup_logger  # Infrastructure first
from metadata_enrichment import MetadataField  # Data structures
from metadata_queries import MetadataQueryOrchestrator  # Business logic
from apple_music import AppleMusicInterface  # Integration layer
```

### DON'T ✗
```python
from metadata_fill import MetadataFiller  # Too specific/circular
import *  # Star imports
```

## Testing

Each module should have corresponding tests in `tests/`:
- `tests/test_metadata_enrichment.py` - Data structures
- `tests/test_metadata_enrichment_interactive.py` - Interactive workflows
- `tests/test_temperament_analyzer_quick.py` - Quick tests
- `tests/test_integration.py` - Integration tests

See `tests/README.md` for testing guidelines.

## Performance Notes

### Database Query Order Rationale
1. **MusicBrainz first** - Most comprehensive, free, no rate limit
2. **AcousticBrainz second** - Audio analysis (needs MusicBrainz ID)
3. **Discogs third** - Vinyl database, good for older music
4. **Wikidata fourth** - Structured data backup
5. **Last.fm last** - User-generated tags, least reliable

### Caching Strategy
- `web_enrichment.py` implements 7-day TTL caching
- Metadata queries cache previous results
- Apple Music metadata cached in memory during session

## Troubleshooting

**"Module not found"** - Ensure `src/` is in PYTHONPATH: `source activate.sh`

**Circular imports** - Check import order (Layer 1 → Layer 2 → Layer 3 → Layer 4)

**SSL errors** - Already fixed in `metadata_queries.py` and `web_enrichment.py`. See [SSL_CERTIFICATE_FIX_QUICK_REFERENCE.md](QUICK_REFERENCE/SSL_CERTIFICATE_FIX_QUICK_REFERENCE.md)

---

**Last Updated**: January 3, 2026  
**Status**: Active  
**Related**: [SPEC_METADATA_ENRICHMENT.md](requirements/SPEC_METADATA_ENRICHMENT.md), [SPEC_TEMPERAMENT_ANALYZER.md](requirements/SPEC_TEMPERAMENT_ANALYZER.md), [SETUP_STATUS_SUMMARY.md](PROJECT_SUMMARIES/SETUP_STATUS_SUMMARY.md)
