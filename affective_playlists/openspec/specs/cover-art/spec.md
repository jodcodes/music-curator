# Cover Art Specifications

## Context & Implementation Guide

Cover Art provides functionality for downloading, caching, and embedding cover artwork for tracks using external sources (Spotify, MusicBrainz, Discogs, Last.fm). The system includes intelligent caching, fallback strategies, and support for multiple image formats and sizes.

### Core Features

- **Multi-source downloading**: Fetch artwork from Spotify, MusicBrainz, Discogs, Last.fm
- **Smart caching**: Cache downloaded artwork by artist/album to avoid redundant API calls
- **Format support**: JPEG, PNG, GIF, WebP with automatic format selection
- **Size optimization**: Download appropriately-sized images (thumbnail, medium, large)
- **Embedded artwork**: Write artwork to audio file tags (ID3 APIC, iTunes covr)
- **Fallback strategy**: Try multiple sources in priority order
- **Source attribution**: Track which source provided each artwork
- **Duplicate detection**: Identify identical artwork across different sources
- **Error handling**: Graceful failure with fallback on source unavailability
- **Rate limiting**: Respect API rate limits when downloading
- **Apple Music guard**: Skip embedding for Apple Music tracks

### Implementation Files

- `src/cover_art.py` - Core cover art downloading and embedding orchestration
- `src/cover_art/spotify_client.py` - Spotify API integration
- `src/cover_art/musicbrainz_client.py` - MusicBrainz image API
- `src/cover_art/discogs_client.py` - Discogs API integration
- `src/cover_art/lastfm_client.py` - Last.fm image API
- `data/cache/cover_art/` - Local cache directory for downloaded artwork
- `tests/test_cover_art.py` - Cover art download and embedding tests

### Configuration

- Environment variables:
  - `COVER_ART_CACHE_ENABLED` - Enable local caching (default: true)
  - `COVER_ART_CACHE_DIR` - Cache directory (default: data/cache/cover_art/)
  - `COVER_ART_CACHE_TTL_DAYS` - Cache lifetime (default: 180 days)
  - `COVER_ART_PREFERRED_SIZE` - Preferred image size (small/medium/large, default: large)
  - `COVER_ART_PREFERRED_FORMAT` - Preferred format (jpeg/png, default: jpeg)
  - `COVER_ART_EMBED_ENABLED` - Enable embedding in audio files (default: true)
  - `COVER_ART_SOURCE_PRIORITY` - Source fetch order (default: spotify,musicbrainz,discogs,lastfm)
- API credentials:
  - `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`
  - `MUSICBRAINZ_USER_AGENT` (required by MusicBrainz)
  - `DISCOGS_PERSONAL_TOKEN`
  - `LASTFM_API_KEY`

### Related Domains

- **Metadata Enrichment** (`metadata`) - Fetches artwork as part of enrichment
- **Audio Tags** (`audio_tags`) - Embeds artwork in audio file tags
- **Apple Music** (`apple_music`) - Skips embedding for Apple Music tracks

---

## Overview

Cover Art SHALL download track artwork from external sources with intelligent caching and support embedding into audio file tags with safe error handling.

### Requirement: Multi-Source Downloading
System MUST fetch artwork from multiple sources with fallback strategy.

#### Scenario: Spotify artwork download
- GIVEN artist and album metadata available
- WHEN download_artwork(artist, album, source='spotify') called
- THEN system SHALL:
  - Query Spotify API for album artwork
  - Return highest-resolution image available
  - Respect Spotify rate limits (429 handling)
  - Cache result locally (if caching enabled)

#### Scenario: MusicBrainz artwork fallback
- GIVEN Spotify returns no artwork for album
- WHEN source priority includes MusicBrainz
- THEN system SHALL:
  - Query MusicBrainz API for images
  - Return available images (typically from Cover Art Archive)
  - Continue with next source if MusicBrainz unavailable

#### Scenario: Discogs fallback
- GIVEN Spotify and MusicBrainz unavailable or return no artwork
- WHEN source priority includes Discogs
- THEN system SHALL:
  - Query Discogs API for release artwork
  - Return artwork if record exists
  - Continue with next source if Discogs unavailable

#### Scenario: Last.fm fallback
- GIVEN previous sources return no artwork
- WHEN source priority includes Last.fm
- THEN system SHALL:
  - Query Last.fm API for album artwork
  - Return artwork if available
  - Mark as "last-resort" source in metadata

#### Scenario: Source priority configuration
- GIVEN `COVER_ART_SOURCE_PRIORITY = "musicbrainz,spotify,discogs,lastfm"`
- WHEN download_artwork is called
- THEN system SHALL fetch in configured order:
  - 1. MusicBrainz
  - 2. Spotify
  - 3. Discogs
  - 4. Last.fm
- Respect user-configured priority

#### Scenario: All sources exhausted
- GIVEN all sources return no artwork
- WHEN all sources attempted in priority order
- THEN system SHALL:
  - Return null/no artwork available
  - Log which sources were tried
  - Flag track for manual artwork addition
  - NOT fail operation (graceful degradation)

### Requirement: Smart Caching
System MUST cache downloaded artwork to minimize API calls.

#### Scenario: Cache hit
- GIVEN artwork cached for "The Beatles" - "Abbey Road"
- WHEN download_artwork("The Beatles", "Abbey Road") called again
- THEN system SHALL:
  - Check cache first
  - Return cached image (if not expired)
  - NOT make API request
  - Log "cache hit" in results

#### Scenario: Cache key generation
- GIVEN artist "The Beatles" and album "Abbey Road"
- WHEN cache key generated
- THEN system SHALL:
  - Normalize artist/album names (consistent casing, remove special characters)
  - Create key: "the-beatles_abbey-road"
  - Store in cache directory with this key

#### Scenario: Cache expiration
- GIVEN `COVER_ART_CACHE_TTL_DAYS = 180`
- WHEN artwork cached 181 days ago
- THEN system SHALL:
  - Detect expired cache entry
  - Remove from cache (or mark invalid)
  - Fetch fresh artwork from source
  - Update cache with new artwork

#### Scenario: Cache directory cleanup
- GIVEN cache directory with many old entries
- WHEN cache maintenance runs (on startup or scheduled)
- THEN system SHALL:
  - Identify expired entries (older than TTL)
  - Remove expired cache files
  - Log cleanup summary (files deleted, space freed)

#### Scenario: Cache with multiple formats
- GIVEN track has cached JPEG artwork
- WHEN preferred format changes to PNG
- THEN system SHALL:
  - Use existing JPEG if conversion acceptable
  - Or fetch PNG from source (if not cached)
  - Avoid re-downloading if format not critical

### Requirement: Image Format & Size Management
System MUST handle multiple image formats and sizes appropriately.

#### Scenario: Format download preferences
- GIVEN `COVER_ART_PREFERRED_FORMAT = "jpeg"`
- WHEN downloading artwork
- THEN system SHALL:
  - Request JPEG format if available from source
  - Fall back to PNG if JPEG unavailable
  - Accept GIF or WebP as last resort
  - Log actual format in results

#### Scenario: Size selection
- GIVEN `COVER_ART_PREFERRED_SIZE = "large"`
- WHEN Spotify returns images: 64x64, 300x300, 640x640
- THEN system SHALL:
  - Select 640x640 (closest to large)
  - Download largest available if "large" not available
  - Avoid oversizing (don't download unnecessary large files)

#### Scenario: Size variants for different purposes
- GIVEN artwork needed for:
  - Cache/embedding (need largest)
  - Web display (medium sufficient)
  - Thumbnail (small sufficient)
- WHEN download_artwork called with different purposes
- THEN system SHALL:
  - Download appropriately-sized image
  - Optimize for use case

#### Scenario: Format validation
- GIVEN downloaded image file
- WHEN validation checks file
- THEN system SHALL:
  - Verify file header (magic bytes) matches claimed format
  - Reject if format mismatch (e.g., .jpg with PNG header)
  - Log format discrepancy warning
  - Accept or reject based on validation strictness setting

### Requirement: Artwork Embedding
System MUST embed downloaded artwork in audio files safely.

#### Scenario: ID3v2 embedding (MP3)
- GIVEN MP3 file and downloaded artwork
- WHEN embed_artwork(mp3_file, image_bytes) called
- THEN system SHALL:
  - Create APIC (Attached Picture) frame in ID3v2
  - Set picture type: 3 (Cover Front)
  - Set image MIME type (image/jpeg, image/png)
  - Add optional description
  - Write atomically (backup + rollback support)

#### Scenario: iTunes embedding (M4A)
- GIVEN M4A file and downloaded artwork
- WHEN embed_artwork(m4a_file, image_bytes) called
- THEN system SHALL:
  - Create covr atom in iTunes metadata
  - Check image size < iTunes limits (typically 2MB)
  - Write atomically with backup support

#### Scenario: Vorbis embedding (FLAC/OGG)
- GIVEN FLAC or OGG file and downloaded artwork
- WHEN embed_artwork(flac_file, image_bytes) called
- THEN system SHALL:
  - Create METADATA_BLOCK_PICTURE (FLAC native)
  - Create METADATA_BLOCK_PICTURE in Vorbis Comments (OGG)
  - Set picture type and MIME type
  - Write with atomic safety

#### Scenario: Apple Music track guard
- GIVEN track originates from Apple Music
- WHEN embed_artwork called for this track
- THEN system SHALL:
  - Skip embedding (configured in metadata)
  - Log "skipped: Apple Music track"
  - Return success (non-critical operation)
  - Continue with other tracks

#### Scenario: Existing artwork handling
- GIVEN audio file already has embedded artwork
- WHEN embed_artwork called with new artwork
- THEN system SHALL:
  - Replace existing APIC/covr with new artwork
  - Preserve other metadata (non-destructive update)
  - Log "replaced existing artwork"
  - Option to append (keep multiple picture frames)

### Requirement: Duplicate Detection
System MUST identify and eliminate duplicate artwork.

#### Scenario: Identical artwork same album
- GIVEN Spotify and MusicBrainz both return same album artwork
- WHEN compare_artwork(image1, image2) called
- THEN system SHALL:
  - Calculate image hash (SHA256 of image bytes)
  - Compare hashes
  - Detect as identical
  - Cache only once (use first source)

#### Scenario: Different images same artist/album
- GIVEN multiple album editions with different artwork
- WHEN downloading artwork for different editions
- THEN system SHALL:
  - Allow multiple entries in cache (cache key includes edition)
  - Store separately with metadata identifying edition
  - Return correct version per edition

#### Scenario: Pixel-level difference detection
- GIVEN two images that appear identical but have minor pixel differences
- WHEN duplicate detection enabled with perceptual hashing
- THEN system SHALL:
  - Use perceptual hash (e.g., pHash)
  - Detect visual similarity even if byte-level different
  - Treat as duplicates if similarity > threshold
  - Reduce storage with deduplication

### Requirement: Source Attribution
System MUST track which source provided each artwork.

#### Scenario: Source attribution in metadata
- GIVEN artwork downloaded from Spotify
- WHEN metadata stored or returned
- THEN system SHALL include:
  ```
  {
    "artwork_url": "...",
    "source": "spotify",
    "downloaded_at": "2025-03-09T10:30:00Z",
    "image_size": "640x640",
    "format": "jpeg"
  }
  ```

#### Scenario: Attribution in audio file
- GIVEN artwork embedded in audio file
- WHEN artwork written to ID3/iTunes/Vorbis
- THEN system SHALL:
  - Store source attribution in description field or comment
  - Example: "Front cover (from Spotify)"
  - Enable future auditing of artwork sources

### Requirement: Error Handling
System MUST handle failures gracefully without blocking enrichment.

#### Scenario: API timeout
- GIVEN API request times out (> 30 seconds)
- WHEN download_artwork called
- THEN system SHALL:
  - Return timeout error
  - NOT retry indefinitely (limit retries)
  - Log timeout with source name
  - Continue to next source or skip this source

#### Scenario: Network error
- GIVEN network connection lost during download
- WHEN download interrupted mid-transfer
- THEN system SHALL:
  - Detect network error
  - Clean up partial download
  - Try next source
  - Log network error without blocking

#### Scenario: API rate limit (429)
- GIVEN Spotify returns 429 Too Many Requests
- WHEN rate limit encountered
- THEN system SHALL:
  - Read Retry-After header
  - Pause requests for specified duration
  - Resume downloading
  - Log rate limit backoff

#### Scenario: Invalid credentials
- GIVEN API key expired or revoked
- WHEN source initialization fails on startup
- THEN system SHALL:
  - Log configuration error
  - Skip source (don't include in fallback chain)
  - Continue with other sources
  - Suggest credential update in startup message

### Requirement: Batch Operations
System MUST handle multiple artwork downloads efficiently.

#### Scenario: Batch download with concurrency
- GIVEN list of 100 tracks to enrich with artwork
- WHEN batch_download_artwork(tracks) called
- THEN system SHALL:
  - Download artwork for multiple tracks in parallel
  - Respect API rate limits (queue requests)
  - Cache results to minimize API calls
  - Complete within reasonable time (< 2 minutes for 100 tracks)

#### Scenario: Batch operation error handling
- GIVEN batch download of 100 tracks, 5 fail
- WHEN batch operation completes
- THEN system SHALL:
  - Successfully download artwork for 95 tracks
  - Log details for 5 failed tracks
  - Continue without stopping (per-track error isolation)
  - Return summary: succeeded, failed, skipped

### Requirement: Configuration & Customization
System MUST support flexible configuration for different use cases.

#### Scenario: Disable embedding for certain formats
- GIVEN `COVER_ART_EMBED_ENABLED=false`
- WHEN artwork download completes
- THEN system SHALL:
  - Download and cache artwork
  - NOT embed in audio files
  - Still return artwork data (for UI display)
  - Log "embedding disabled"

#### Scenario: Custom cache directory
- GIVEN `COVER_ART_CACHE_DIR=/var/cache/affective_artwork/`
- WHEN artwork cached
- THEN system SHALL:
  - Create cache in custom directory
  - Create missing parent directories
  - Validate write permissions
  - Use custom path for all cache operations
