# Technical Requirements: System Architecture

## Overview
The affective_playlists system is a unified Python CLI application that combines three independent music analysis and organization tools into a single cohesive platform.

## System Components

### Core Entry Point
- **File**: `main.py`
- **Purpose**: Unified CLI dispatcher
- **Responsibilities**:
  - Parse command-line arguments
  - Route to appropriate module
  - Handle interactive menu display
  - Manage error handling and logging

### Module 1: Temperament Analyzer (4tempers)
- **File**: `src/temperament_analyzer.py`
- **Purpose**: AI-based emotion classification
- **Dependencies**: OpenAI API, Music.app
- **Output**: Emotional temperament labels

### Module 2: Metadata Enrichment (metad_enr)
- **File**: `src/metadata_fill.py`
- **Purpose**: Automatic metadata filling
- **Dependencies**: MusicBrainz, Spotify, Last.fm APIs
- **Output**: Enriched track metadata

### Module 3: Playlist Organization (plsort)
- **File**: `src/plsort.py`
- **Purpose**: Genre-based organization
- **Dependencies**: Playlist classifier, Apple Music
- **Output**: Organized playlists by genre

## Shared Infrastructure

### Apple Music Interface
- **File**: `src/apple_music.py`
- **Purpose**: Unified Music.app API wrapper
- **Methods**:
  - `authenticate()` - Connect to Music.app
  - `get_playlists()` - Retrieve user's playlists
  - `get_playlist_tracks()` - Get tracks from playlist
  - `update_metadata()` - Modify track metadata

### Configuration Management
- **File**: `src/config.py`
- **Purpose**: Centralized config handling
- **Features**:
  - Load `.env` file
  - Parse `whitelist.json`
  - Manage API credentials
  - Handle environment variables

### Logging System
- **File**: `src/logger.py`
- **Purpose**: Unified logging
- **Features**:
  - File and console output
  - Multiple log levels (DEBUG, INFO, WARNING, ERROR)
  - Timestamped entries
  - Module-specific loggers

### Text Normalization
- **File**: `src/normalizer.py`
- **Purpose**: Standardize text for comparisons
- **Functions**:
  - Whitespace normalization
  - Case normalization
  - Special character handling
  - Genre name standardization

## Data Structure

### Configuration Directory
```
data/
├── config/
│   ├── whitelist.json              # Playlist whitelist
│   └── playlist_whitelist.json      # Alternative whitelist
├── artist_lists/
│   ├── hiphop_artists.json
│   ├── electronic_artists.json
│   ├── jazz_artists.json
│   └── ...
├── logs/
│   └── *.log                        # Application logs
└── cache/
    └── metadata_cache.json          # Cached metadata
```

### Configuration Files

#### whitelist.json
```json
{
  "enabled": false,
  "playlists": [
    "Playlist Name 1",
    "Playlist Name 2"
  ]
}
```

#### .env
```bash
OPENAI_API_KEY=sk-...
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
LASTFM_API_KEY=...
```

## API Integration Points

### External APIs
1. **OpenAI GPT**: Temperament analysis
   - Endpoint: `https://api.openai.com/v1/chat/completions`
   - Auth: Bearer token in OPENAI_API_KEY

2. **Spotify Web API**: Metadata enrichment
   - Auth: OAuth 2.0 client credentials flow
   - Credentials: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

3. **MusicBrainz API**: Metadata enrichment
   - Endpoint: `https://musicbrainz.org/ws/2/`
   - No auth required (rate limited)

4. **Last.fm API**: Metadata enrichment
   - Auth: API key in LASTFM_API_KEY

5. **Apple Music (Local)**: All modules
   - Method: AppleScript via subprocess
   - No authentication (local app access)

## Technology Stack

### Language & Runtime
- Python 3.8+
- Standard library modules

### External Dependencies
```
openai              # GPT API client
spotipy            # Spotify API client
musicbrainzngs     # MusicBrainz API client
pylast             # Last.fm API client
python-dotenv      # .env file management
```

### System Integration
- AppleScript (via subprocess) for Music.app
- macOS-specific (Music.app availability)

## Error Handling Strategy

### API Errors
- Retry with exponential backoff
- Fallback to alternative sources
- Graceful degradation (skip if unavailable)

### Music.app Errors
- Check authentication status first
- Provide clear error messages
- Suggest troubleshooting steps

### File/Config Errors
- Check file existence before access
- Provide template/example files
- Default values for optional configs

### User Input Errors
- Validate playlist names
- Confirm potentially destructive actions
- Provide interactive selection menus

## Security Considerations

### API Keys
- Store in `.env` file (never commit)
- `.gitignore` protects `.env` from git
- Load at runtime via `python-dotenv`

### Data Privacy
- No personal data sent to external APIs
- Metadata queries only
- User controls what's processed via whitelist

### File Access
- Only read/write to designated directories
- Respect macOS sandboxing
- Proper error handling for permission issues

## Performance Considerations

### Batch Processing
- Process multiple tracks efficiently
- Cache metadata results
- Queue large operations

### API Rate Limiting
- Implement throttling per service
- Respect rate limit headers
- Queue requests if limits exceeded

### Memory Usage
- Stream playlist data when possible
- Clear large data structures after use
- Avoid loading entire library at once

## Deployment & Environment

### Development
- Virtual environment: `venv/`
- Setup script: `setup.sh`
- Activation: `activate.sh`

### Configuration
- Environment template: `.env.example`
- Quick start: `QUICKSTART.md`
- Project docs: `README.md`

### Logging
- Default log file: `temperament_analyzer.log`
- Centralized logs: `data/logs/`
- Configurable log levels

## Exit Codes
- `0` - Success
- `1` - General error
- `130` - Keyboard interrupt (Ctrl+C)

## Data Models & Schemas

### Core Data Structures

#### Playlist
```python
{
    "id": str,                      # Apple Music ID
    "name": str,
    "track_count": int,
    "is_system": bool,              # System vs user playlist
    "creation_date": str,           # ISO 8601
    "modification_date": str        # ISO 8601
}
```

#### Track
```python
{
    "id": str,                      # Apple Music ID
    "title": str,
    "artist": str,
    "album": str,
    "genre": str or None,
    "bpm": int or None,
    "year": int or None,
    "duration_ms": int,
    "composer": str or None
}
```

#### WhitelistConfig
```python
{
    "enabled": bool,
    "playlists": [str],             # List of playlist names
    "last_updated": str             # ISO 8601
}
```

### API Response Schemas

#### Spotify Track Response
```python
{
    "id": str,
    "name": str,
    "artist": str,
    "album": str,
    "explicit": bool,
    "popularity": int,              # 0-100
    "tempo": int,                   # BPM (may be 0)
    "time_signature": str,
    "audio_features": {
        "energy": float,            # 0-1
        "danceability": float,
        "valence": float
    }
}
```

#### MusicBrainz Recording Response
```python
{
    "id": str,
    "title": str,
    "artist-credit": str,
    "date": str,                    # Release date
    "genres": [str],
    "work": {
        "id": str,
        "type": str
    }
}
```

## Persistence Layer

### Storage Strategy
- **Configuration**: JSON files in `data/config/`
- **Results**: Append-only JSON logs in `data/logs/`
- **Cache**: Optional SQLite in `data/cache/` (future enhancement)
- **Credentials**: Environment variables from `.env`

### File Structures

#### Temperament Results (`data/logs/temperament_results.json`)
```
[JSONL format - one result per line]
{"playlist_name": "...", "temperament": "...", "timestamp": "..."}
```

#### Enrichment History (`data/logs/enrichment_history.json`)
```
[JSONL format - one operation per line]
{"track_id": "...", "field": "genre", "old": "...", "new": "...", "timestamp": "..."}
```

#### Organization Log (`data/logs/organization_log.json`)
```
[JSONL format - one action per line]
{"playlist": "...", "action": "rename", "before": "...", "after": "...", "status": "success"}
```

## Concurrency & Thread Safety

### Current Model
- **Single-threaded**: All modules run sequentially
- **CLI-only**: No async operations
- **No Race Conditions**: Data accessed locally only

### Future Multi-threading (if needed)
- Use thread-safe queues for batch processing
- Lock-based protection for log files
- Consider asyncio for API calls

## Caching Strategy

### In-Memory Cache (Session)
- **Temperament**: Cache GPT responses (max 50)
- **Metadata**: Cache API responses (max 100)
- **Cleared on**: CLI exit

### File-Based Cache (Optional)
- **Location**: `data/cache/`
- **Format**: SQLite or JSON
- **TTL**: User-configurable (default 7 days)
- **Size Limit**: 100MB

### Cache Invalidation
- **Manual**: `--no-cache` flag to bypass
- **Time-based**: TTL per cached item
- **Event-based**: Refresh on whitelist change
- **User-triggered**: Explicit refresh option

## Error Handling Strategy

### Layered Approach
1. **Input Validation**: Validate at entry point
2. **API Layer**: Handle external API errors
3. **File I/O**: Safe file access with backups
4. **User Feedback**: Clear error messages
5. **Logging**: Log all errors with context

### Retry Patterns
```python
# Exponential backoff template
def retry_with_backoff(fn, max_retries=3):
    for attempt in range(max_retries):
        try:
            return fn()
        except TemporaryError:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                sleep(wait)
            else:
                raise
```

### Graceful Degradation
- **Missing Optional APIs**: Skip and log warning
- **Playlist Not Found**: Suggest alternatives
- **AppleScript Failure**: Abort operation cleanly
- **Network Errors**: Queue for retry later

## Monitoring & Observability

### Logging Levels
- **DEBUG**: API requests/responses, detailed operations
- **INFO**: Major operations (start/end), results
- **WARNING**: Recoverable errors, skipped items
- **ERROR**: Failure requiring user attention

### Metrics to Track
- API call count and latency per service
- Success/failure rates per operation
- Processing time per playlist/track
- Cache hit rates
- Error frequency and types

### Log Aggregation
- **Current**: File-based logs in `data/logs/`
- **Future**: Consider centralized logging

### Health Checks (Future)
- API availability checks
- Music.app connectivity
- Disk space warnings
- Network connectivity

## System Requirements

### Minimum Specifications
- **OS**: macOS 10.13+ (High Sierra+)
- **Python**: 3.8.0 or higher
- **RAM**: 512MB minimum, 2GB recommended
- **Disk**: 200MB for app + 100MB for cache/logs
- **Network**: Internet required for external APIs
- **Music.app**: Must be installed and accessible

### Library Versions
```
Python:                    3.8+
openai:                    0.27.0+
spotipy:                   2.19.0+
musicbrainzngs:            0.7.12+
pylast:                    4.8.0+
python-dotenv:             0.19.0+
requests:                  2.28.0+
```

### macOS Compatibility Matrix
| macOS Version | Status | Notes |
|:---|:---|:---|
| 10.13-10.14 | Supported | Music.app may have limits |
| 10.15+ | Fully Supported | Recommended minimum |
| 11.0+ (Big Sur) | Fully Supported | |
| 12.0+ (Monterey) | Fully Supported | |
| 13.0+ (Ventura) | Fully Supported | |

## Security Considerations

### API Key Management
- **Storage**: `.env` file (gitignored)
- **Loading**: `python-dotenv` at runtime
- **Rotation**: User responsible for key rotation
- **Expiration**: Log warnings for stale keys
- **No Hardcoding**: Never embed keys in code

### Data Privacy
- **Playlist Data**: Not uploaded to external APIs (except search)
- **Metadata Queries**: Only artist/title sent
- **Caching**: User data never persisted in logs
- **Audit Trail**: Track what changed, not sensitive content

### File Security
- **Permissions**: Config files should be 600 (user-only read)
- **Backup**: Keep secure backups of results
- **Deletion**: Clear cache/logs periodically
- **Recovery**: Maintain rollback history

## CI/CD & Testing Strategy

### Unit Test Requirements
- **Coverage**: Minimum 70% of all modules
- **Framework**: pytest
- **Mocking**: Mock all external APIs
- **Fixtures**: Pre-recorded API responses

### Integration Tests
- **Scope**: Full workflows with mock Music.app
- **Test Data**: 10-500 track playlists
- **Scenarios**: Success, partial failure, full failure
- **Edge Cases**: Empty playlists, special characters, rate limits

### Automated Testing Pipeline
```
1. Lint (pylint, flake8)
2. Type Check (mypy)
3. Unit Tests (pytest)
4. Integration Tests
5. Code Coverage Report
6. Security Scan (bandit)
```

### Pre-commit Hooks
- Format check (black)
- Import sort (isort)
- Lint check (pylint)
- Type hints (mypy)

## Version Compatibility & Deprecation

### Python Version Support
- **Active Support**: 3.8, 3.9, 3.10, 3.11
- **EOL Plan**: Drop support for 3.8 in v2.0 (after 6 months)
- **Deprecation Notice**: Announce 3+ months in advance

### API Compatibility
- **Schema Versioning**: Include `version` field in JSON outputs
- **Backwards Compatibility**: Support reading v1 and v2 formats
- **Migration Tools**: Provide scripts to upgrade data
- **Transition Period**: Maintain support for 2 major versions

### Configuration Migration
```python
def migrate_config(old_config):
    """Upgrade old config format to new schema"""
    if not old_config.get("version"):
        # v0 → v1 migration
        pass
    return updated_config
```

## Development & Deployment

### Local Development
```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Testing
pytest tests/ --cov=src/

# Linting
pylint src/ tests/

# Type checking
mypy src/
```

### Release Process
1. Update version in `__init__.py`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Tag release: `git tag v1.0.0`
5. Create GitHub release
6. Publish PyPI package (future)

### Backwards Compatibility Checklist
- [ ] Changes don't break existing config files
- [ ] Old API responses still parseable
- [ ] Migration script tested
- [ ] Deprecation warnings added (if removing feature)
- [ ] Documentation updated
