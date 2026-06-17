# Functional Specification: Metadata Enrichment (metad_enr)

## Overview
Automatic metadata filling and enrichment system that retrieves missing audio metadata (BPM, Genre, Year, Cover Art) from multiple databases and applies it to music tracks in Apple Music and local audio files.

## Purpose
Fill gaps in music metadata across user's library by querying multiple sources (MusicBrainz, Spotify, Last.fm) and automatically applying corrections to Apple Music, improving library consistency and quality.

## Functional Requirements

### F1: Metadata Retrieval
- Query MusicBrainz for track metadata
- Query Spotify API for track information
- Query Last.fm API for track statistics
- Support multiple fallback sources

### F2: Metadata Detection
- Identify missing metadata fields:
  - BPM (Beats Per Minute)
  - Genre classification
  - Release year
  - Album art/cover images
  - Composer/writer information
- Detect cover art availability from databases

### F3: Interactive Selection
- Allow user to select playlist for enrichment
- Allow user to select folder path for enrichment
- Display whitelist of available playlists (if enabled)
- Support manual playlist name entry

### F4: Metadata Application
- Update Apple Music track metadata
- Embed cover art in local audio files (MP3, MP4/M4A)
- Batch process multiple tracks
- Handle conflicts and duplicates
- Provide dry-run mode for preview
- Skip cover art embedding for Apple Music tracks (managed by Apple)

### F5: Progress Tracking
- Display progress during processing
- Log all metadata changes
- Provide summary of changes made

## Technical Requirements

### T1: Dependencies
- MusicBrainz API client
- Spotify API client (`spotipy`)
- Last.fm API client
- Apple Music integration via AppleScript
- Audio tag library (`mutagen` for MP3/MP4 cover art embedding)
- Standard library: `json`, `logging`, `argparse`, `urllib`

### T2: Environment Variables (Optional)
- `SPOTIFY_CLIENT_ID` - Spotify API access
- `SPOTIFY_CLIENT_SECRET` - Spotify API access
- `LASTFM_API_KEY` - Last.fm API access

### T3: Data Flow
1. User selects playlist or folder
2. System retrieves all tracks
3. For each track, query metadata sources
4. Merge metadata from multiple sources
5. Present conflicts/suggestions to user
6. Apply selected metadata to Apple Music
7. Log all changes

### T4: Database Queries

**Query Order (Priority) - "Enrich Once" Strategy:**
1. **Discogs** - Genre, year, release information (cover art requires API token)
2. **Last.fm** - Genre tags, popularity, user-generated classification
3. **Wikidata** - Genre, year, artist information
4. **MusicBrainz** - Track metadata, BPM, year, release ID
5. **AcousticBrainz** - Audio analysis data (BPM, key, tempo) from MusicBrainz ID
6. **CoverArtArchive** - Cover art only (separate flow, never required for metadata enrichment)

**Enrich Once Behavior (Exact Missing Fields Strategy):**
- Identifies which fields are MISSING from the track metadata
- Only searches for those specific missing fields (not already-present fields)
- Discogs returns Genre + Year (if both are missing) → collects both
- Last.fm returns Genre (already found from Discogs) → skips Genre
- Continues querying sources for remaining missing fields until all found OR sources exhausted
- **Ensures NO SONGS ARE SKIPPED** - searches all sources for missing metadata
- Each missing field enriched once from the highest-priority source that has it
- Improves performance by only searching for what's actually needed
- Example: Track missing BPM + Year → Queries until both found, skips already-present Genre

Each database:
- Discogs: Genre, release year, catalog information (first queried)
- Last.fm: Genre tags, track popularity, user classifications
- Wikidata: Genre, release year, artist/track relationships
- MusicBrainz: Track search, metadata retrieval, MBID lookup
- AcousticBrainz: Audio analysis data (requires MusicBrainz ID, queried last)
- CoverArtArchive: Only for cover art (separate workflow)

### T5: Configuration
- Whitelist enabled flag in `data/config/whitelist.json`
- API rate limiting and timeouts
- Retry logic for failed queries

## Input/Output

### Input
- Playlist name or folder path
- Optional: Force refresh flag
- Optional: Verbose logging flag

### Output
- Summary of metadata additions
- Conflicts and user decisions
- Change log with timestamps
- Success/failure count

## Configuration
- Whitelist configuration: `data/config/whitelist.json`
- API credentials: `.env` file
- Config path: `data/config/`

## Dependencies
- `spotipy` - Spotify API client
- `musicbrainzngs` - MusicBrainz API client
- `pylast` - Last.fm API client
- `mutagen` - Audio file tag reading/writing (cover art embedding)
- Custom: `src/apple_music.py`
- Custom: `src/metadata_queries.py`
- Custom: `src/cover_art.py`

## Implementation Details
- Source: `src/metadata_fill.py`
- Entry point: `main.py` → `run_metadata_enrichment()`
- Related: `src/metadata_queries.py`, `src/databases.py`, `src/config.py`

## Error Scenarios
- Missing API credentials → Use free tier or skip source
- Playlist not found → Suggest whitelisted playlists
- Rate limit exceeded → Queue for batch processing
- Network timeout → Retry with exponential backoff
- Metadata conflicts → Present to user for decision

## Non-Functional Requirements

### Performance Requirements
- **Per-Track Processing**: < 5 seconds (including all API queries)
- **Batch Size**: Process 50 tracks/batch, max 500 tracks/session
- **Memory Usage**: < 300MB for 500-track batch
- **Throughput**: ~12 tracks/minute (accounting for API rate limits)
- **Database Query Time**: < 2 seconds per track (all sources)

### Reliability & Robustness
- **Retry Strategy**: Exponential backoff (1s, 2s, 4s) max 3 retries per source
- **Request Timeout**: 15 seconds per API call
- **Partial Failures**: Continue with other sources if one fails
- **Missing Fields**: Gracefully handle incomplete responses
- **API Rate Limiting**: Queue requests, respect rate limits per source
  - MusicBrainz: 1 request/second max
  - Spotify: 429 response handling with Retry-After
  - Last.fm: 5 requests/second max

### Security & Data Privacy
- API credentials stored in .env (never logged)
- Never cache credentials in memory
- Minimal logging of track metadata (names only, no audio data)
- User controls which playlists are processed (whitelist)
- Audit trail: timestamp, source, field updated, old/new values

## Data Models/Schemas

### MetadataQuery Request
```python
{
    "track_name": str,              # Required
    "artist_name": str,             # Required
    "album_name": str,              # Optional
    "source": str                   # One of: musicbrainz, spotify, lastfm
}
```

### MetadataResult Schema
```python
{
    "track_id": str,                # Apple Music track ID
    "track_name": str,
    "artist_name": str,
    "results": {
        "musicbrainz": {
            "bpm": int or None,
            "genre": [str],
            "year": int or None,
            "confidence": float,    # 0.0-1.0
            "matched_track_id": str
        },
        "spotify": {
            "bpm": int or None,
            "genre": [str],
            "year": int or None,
            "confidence": float,
            "popularity": int       # 0-100
        },
        "lastfm": {
            "genre": [str],
            "tags": [str],
            "confidence": float
        }
    },
    "merged_result": {
        "recommended_bpm": int or None,
        "recommended_genre": str,
        "recommended_year": int or None,
        "confidence_score": float,
        "source_priority": [str]    # Which source won
    },
    "last_updated": str             # ISO 8601 timestamp
}
```

## Acceptance Criteria
- ✓ Retrieves metadata from at least one source for 90% of tracks
- ✓ Downloads cover art from MusicBrainz CoverArtArchive when available
- ✓ Embeds cover art in local audio files (MP3, MP4/M4A)
- ✓ Handles missing cover art gracefully (continues without error)
- ✓ Caches downloaded cover art to minimize network requests
- ✓ Handles missing API credentials gracefully
- ✓ Displays metadata conflicts to user for decision
- ✓ Respects rate limits (no API bans)
- ✓ Updates Apple Music metadata without corruption
- ✓ Maintains audit trail of changes (including cover art)
- ✓ Can process 500-track playlist without crashes

## Constraints & Compatibility
- **Python Version**: 3.8+
- **macOS Version**: 10.13+
- **Disk Space**: 50MB for metadata cache
- **Network**: Requires internet access
- **Optional APIs**: Works with subset of API keys (degrades gracefully)
- **Library Versions**: spotipy 2.19+, musicbrainzngs 0.7.12+, pylast 4.8+

## Test Strategy
### Unit Tests
- [ ] Metadata parsing for each source
- [ ] Conflict resolution algorithm
- [ ] Deduplication matching
- [ ] Data validation (BPM ranges, valid years)
- [ ] Retry/backoff logic
- [ ] Source fallback when primary fails

### Integration Tests
- [ ] Full metadata enrichment workflow
- [ ] Multiple sources returning different data
- [ ] Rate limiting behavior
- [ ] Interrupted batch processing (resume)

### Test Data
- Mock responses from MusicBrainz, Spotify, Last.fm
- Edge cases: Different artist spellings, multiple releases, remixes
- Invalid metadata: BPM > 300, negative years, empty genres

## Conflict Resolution Algorithm
- **BPM**: Median of all sources (removes outliers)
- **Genre**: Weighted vote (confidence-based)
- **Year**: Most recent source if within 5 years, else user prompt
- **Confidence**: Average of source confidences, min 0.6 to apply
- **User Override**: Allow manual selection before applying

## Deduplication Strategy
- **Fuzzy Matching**: 80%+ match on (artist, title) with Levenshtein distance
- **Exact Matching**: Case-insensitive, normalize whitespace
- **Multi-Release Handling**: If multiple versions, pick most popular/recent
- **Cache Previous Matches**: Store matched track IDs to skip re-queries

## Data Validation
- **BPM**: Must be 30-300, integer, reject if outside range
- **Year**: Must be 1900-2100, integer
- **Genre**: Non-empty string, reject if blank/whitespace
- **Track Match**: Confidence > 0.7 before applying
- **Sanitization**: Remove special characters from genres

## State Management
- **Enrichment History**: File-based log in `data/logs/enrichment_history.json`
- **Persistence**: Append enrichment record per batch
- **Recovery**: If interrupted, can resume from last processed track
- **Tracking**: Store source of data, timestamp, confidence
- **Rollback**: Ability to revert to original metadata (store backup)
