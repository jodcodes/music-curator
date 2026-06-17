# Audio Tags Specifications

## Context & Implementation Guide

Audio Tags provides format-specific handling for reading and writing track metadata to audio files. The system supports multiple audio formats (MP3 ID3v2, M4A/MP4 iTunes, OGG Vorbis, FLAC) with consistent interface across format implementations. Safe tag writing with backup/rollback ensures data integrity.

### Core Features

- **Format support**: ID3v2 (MP3), iTunes (M4A/MP4), Vorbis Comments (OGG/Opus), Vorbis Comments (FLAC)
- **Tag reading**: Extract metadata fields (title, artist, album, genre, BPM, year, etc.) from files
- **Tag writing**: Write enriched metadata back to files with validation
- **Format detection**: Auto-detect file format and select appropriate handler
- **Atomic writes**: Ensure file integrity during write operations
- **Backup protection**: Optional backup before writing, rollback on failure
- **Encoding safety**: Handle UTF-8, Latin-1, and other encodings consistently
- **Validation**: Validate metadata fields before writing (type, length, format)
- **Embedded art**: Support reading/writing of embedded cover artwork
- **Field mapping**: Map canonical field names to format-specific names
- **Error handling**: Graceful failure with per-file error isolation

### Implementation Files

- `src/audio_tags.py` - Core tag handler abstraction and factory
- `src/audio_tags/id3_handler.py` - ID3v2 (MP3) implementation
- `src/audio_tags/itunes_handler.py` - iTunes/M4A handler
- `src/audio_tags/vorbis_handler.py` - Ogg Vorbis/FLAC handler
- `tests/test_audio_tags.py` - Tag handling tests
- `tests/fixtures/audio_samples/` - Test audio files (various formats)

### Configuration

- Environment variables:
  - `AUDIO_TAG_BACKUP_ENABLED` - Create backups before writing (default: true)
  - `AUDIO_TAG_VALIDATE_BEFORE_WRITE` - Validate fields before write (default: true)
  - `AUDIO_TAG_ENCODING` - Default encoding (default: utf-8)
- Tag field mappings:
  - Canonical names (title, artist, album, genre, bpm, year, comment)
  - Format-specific mappings (ID3: TIT2, TPE1, etc.; iTunes: ©nam, ©ART, etc.)

### Related Domains

- **Metadata Enrichment** (`metadata`) - Writes enriched metadata via audio tags
- **Cover Art** (`cover_art`) - Reads/writes embedded artwork
- **Apple Music** (`apple_music`) - Complements Apple Music metadata sync

---

## Overview

Audio Tags SHALL provide safe, format-specific reading and writing of metadata fields to audio files with validation, backup, and error isolation.

### Requirement: Format Detection & Handler Selection
System MUST automatically select correct handler based on file format.

#### Scenario: MP3 file detection
- GIVEN audio file with .mp3 extension
- WHEN AudioTagHandler.load(filepath) is called
- THEN system SHALL:
  - Detect file as MP3 format
  - Initialize ID3v2Handler
  - Return handler ready to read/write ID3v2 tags

#### Scenario: M4A file detection
- GIVEN audio file with .m4a or .mp4 extension
- WHEN AudioTagHandler.load(filepath) is called
- THEN system SHALL:
  - Detect file as M4A/iTunes format
  - Initialize iTunesHandler
  - Return handler ready to read/write iTunes atoms

#### Scenario: FLAC file detection
- GIVEN audio file with .flac extension
- WHEN AudioTagHandler.load(filepath) is called
- THEN system SHALL:
  - Detect file as FLAC format
  - Initialize FLACHandler (uses Vorbis Comments)
  - Return handler ready to read/write

#### Scenario: OGG file detection
- GIVEN audio file with .ogg or .opus extension
- WHEN AudioTagHandler.load(filepath) is called
- THEN system SHALL:
  - Detect file as OGG Vorbis or Opus
  - Initialize VorbisHandler
  - Return handler ready to read/write Vorbis Comments

#### Scenario: Unknown format handling
- GIVEN audio file with unsupported format or extension
- WHEN AudioTagHandler.load(filepath) is called
- THEN system SHALL:
  - Attempt to detect format by file header (magic bytes)
  - If detection fails, raise AudioFormatUnsupportedError
  - Log file path and attempted formats
  - Return error message with supported formats list

### Requirement: Tag Reading
System MUST extract metadata fields safely and consistently.

#### Scenario: Read standard fields (all formats)
- GIVEN audio file in any supported format
- WHEN handler.read_tags() is called
- THEN system SHALL return dict with canonical field names:
  - title, artist, album, album_artist, genre, year, track_number
  - bpm, composer, comment, copyright, release_date
  - Any present field, null/empty string if not present

#### Scenario: Read ID3v2 fields (MP3)
- GIVEN MP3 file with ID3v2 tags
- WHEN ID3v2Handler reads file
- THEN system SHALL correctly map:
  - TIT2 → title
  - TPE1 → artist
  - TALB → album
  - TPE2 → album_artist
  - TCON → genre
  - TDRC → year
  - TBPM → bpm
  - TPOS → track_number (disc/track info)

#### Scenario: Read iTunes atoms (M4A)
- GIVEN M4A file with iTunes metadata atoms
- WHEN iTunesHandler reads file
- THEN system SHALL correctly map:
  - ©nam → title
  - ©ART → artist
  - ©alb → album
  - aART → album_artist
  - ©gen → genre
  - ©day → year
  - tmpo → bpm
  - trkn → track_number

#### Scenario: Read Vorbis Comments (FLAC/OGG)
- GIVEN FLAC or OGG file with Vorbis Comments
- WHEN VorbisHandler reads file
- THEN system SHALL correctly map:
  - TITLE → title
  - ARTIST → artist
  - ALBUM → album
  - ALBUMARTIST → album_artist
  - GENRE → genre
  - DATE → year
  - BPM → bpm
  - TRACKNUMBER → track_number

#### Scenario: Multiple values per field
- GIVEN tag field with multiple values (e.g., multiple genres: "Rock;Pop")
- WHEN handler.read_tags() is called
- THEN system SHALL:
  - Return concatenated string or list based on format
  - For single-value fields, return first value
  - Document multi-value handling strategy

#### Scenario: Encoding detection (legacy tags)
- GIVEN ID3v2 file with Latin-1 encoded text (ID3v2.2 or improperly encoded v2.4)
- WHEN handler reads tags
- THEN system SHALL:
  - Detect encoding (ID3v2 frame header specifies encoding)
  - Decode from Latin-1/UTF-16 to UTF-8
  - Return consistently encoded strings

#### Scenario: Missing or corrupted tags
- GIVEN audio file with missing or incomplete ID3 tags
- WHEN handler.read_tags() is called
- THEN system SHALL:
  - Return dict with null/empty values for missing fields
  - Log warning for corrupted tags
  - NOT raise exception (graceful degradation)
  - Allow retry on next operation

### Requirement: Tag Writing
System MUST write metadata safely with validation and protection.

#### Scenario: Write standard fields
- GIVEN metadata dict with title, artist, album, genre, year
- WHEN handler.write_tags(metadata) is called
- THEN system SHALL:
  - Validate each field (type, length, format)
  - Format values according to target format requirements
  - Write atomically to file
  - Return success or detailed error

#### Scenario: Validate before write
- GIVEN AUDIO_TAG_VALIDATE_BEFORE_WRITE=true
- WHEN handler attempts to write invalid data
- THEN system SHALL:
  - Reject invalid field values (e.g., non-numeric BPM)
  - Return validation error with field details
  - NOT write partial data
  - Suggest corrected value if possible

#### Scenario: Field length constraints
- GIVEN artist name 300 characters (beyond typical tag capacity)
- WHEN handler.write_tags() with validation enabled
- THEN system SHALL:
  - Accept UTF-8 encoding that fits format constraints
  - Truncate gracefully or warn if required
  - Document truncation in results
  - For short fields (ID3v2 COMM), enforce limit

#### Scenario: Atomic write protection
- GIVEN audio file ready for metadata update
- WHEN handler.write_tags(metadata) is in progress
- THEN system SHALL:
  - Write to temporary file first
  - Validate write succeeded
  - Atomically replace original file
  - Restore from backup if replacement fails

#### Scenario: Backup before write
- GIVEN AUDIO_TAG_BACKUP_ENABLED=true
- WHEN handler.write_tags(metadata) called
- THEN system SHALL:
  - Create backup: original_file.mp3 → original_file.mp3.backup
  - Write to original file
  - Retain backup for rollback if needed
  - Log backup location for recovery

#### Scenario: Rollback on write failure
- GIVEN write operation fails (corruption detected, disk full)
- WHEN backup exists (AUDIO_TAG_BACKUP_ENABLED=true)
- THEN system SHALL:
  - Detect write failure
  - Restore from backup: original_file.mp3.backup → original_file.mp3
  - Log rollback action
  - Return error with recovery confirmation

#### Scenario: No backup if disabled
- GIVEN AUDIO_TAG_BACKUP_ENABLED=false
- WHEN handler.write_tags() called
- THEN system SHALL:
  - Write directly without backup
  - Accept risk of data loss on failure
  - Log risk in result

### Requirement: ID3v2 (MP3) Specific Handling
System MUST correctly handle ID3v2 tags with version compatibility.

#### Scenario: ID3v2.3 vs v2.4 handling
- GIVEN MP3 with ID3v2.3 tags (legacy)
- WHEN handler reads and writes
- THEN system SHALL:
  - Preserve version (write v2.3 if originally v2.3, unless updated)
  - Handle encoding differences (v2.4 uses UTF-8, v2.3 uses Latin-1)
  - Support reading both versions
  - Optionally upgrade to v2.4 on write (if configured)

#### Scenario: Extended header support
- GIVEN ID3v2 file with extended header
- WHEN handler processes file
- THEN system SHALL:
  - Parse extended header (flags, size, data)
  - Preserve on write
  - Document any extended header fields in results

#### Scenario: Frame flags and encoding
- GIVEN text frame with text information identifier (TTTT format)
- WHEN handler builds ID3v2 tags
- THEN system SHALL:
  - Use proper frame ID (e.g., TIT2 for title)
  - Set text encoding flag (0=ISO-8859-1, 1=UTF-16BE, 3=UTF-8)
  - Encode string according to flag
  - Encode BOM for UTF-16 if needed

### Requirement: iTunes/M4A Specific Handling
System MUST handle iTunes metadata atoms correctly.

#### Scenario: iTunes atom structure
- GIVEN M4A file with nested iTunes atoms
- WHEN handler reads atoms within meta/ilst
- THEN system SHALL:
  - Navigate atom hierarchy correctly
  - Extract data atoms (datas) within metadata atoms
  - Handle atom size and offsets properly

#### Scenario: iTunes mean atom handling
- GIVEN iTunes file with freeform atoms (using mean atom)
- WHEN handler encounters freeform metadata
- THEN system SHALL:
  - Parse mean atom (namespace identifier)
  - Parse name atom (parameter name)
  - Extract data from data atom
  - Map to canonical field if recognized

#### Scenario: Sample data types (iTunes)
- GIVEN BPM metadata (tmpo atom, big-endian integer)
- WHEN handler reads/writes BPM
-THEN system SHALL:
  - Write as 4-byte big-endian integer
  - Return as integer (not string)
  - Validate numeric range

### Requirement: Vorbis Comments (FLAC/OGG)
System MUST handle Vorbis Comments correctly.

#### Scenario: Vorbis case-insensitive field names
- GIVEN Vorbis Comments with "ARTIST" vs "artist" field names
- WHEN handler processes fields
- THEN system SHALL:
  - Treat field names case-insensitively
  - Normalize to uppercase on write
  - Return consistent field names

#### Scenario: Multiple values in single field
- GIVEN "ARTIST=Artist1" and "ARTIST=Artist2" (multiple values)
- WHEN handler reads file
- THEN system SHALL:
  - Support multiple values per field name
  - Return as list or concatenated string based on field type
  - Preserve on write if multiple values present

### Requirement: Embedded Cover Art
System MUST read and write embedded artwork safely.

#### Scenario: Read embedded artwork
- GIVEN MP3 with APIC (attached picture) frame
- WHEN handler.read_artwork() called
- THEN system SHALL:
  - Extract APIC frame
  - Return image data (bytes)
  - Return image format (image/jpeg, image/png, etc.)
  - Return description if present

#### Scenario: Write embedded artwork
- GIVEN image file and audio file
- WHEN handler.write_artwork(image_bytes, format) called
- THEN system SHALL:
  - Create APIC frame (ID3) or similar for format
  - Embed image in file
  - Preserve existing metadata (non-destructive write)
  - Return success or error

### Requirement: Batch Operations
System MUST handle multiple files efficiently.

#### Scenario: Batch read tags
- GIVEN list of 100 audio files
- WHEN handler.batch_read(file_list) called
- THEN system SHALL:
  - Process all files
  - Return list of metadata dicts (one per file)
  - Continue on per-file errors (error isolation)
  - Log files with errors for review

#### Scenario: Batch write tags
- GIVEN list of 100 audio files and metadata updates
- WHEN handler.batch_write(updates) called
- THEN system SHALL:
  - Write to all files with backups
  - Continue on per-file errors
  - Return summary: succeeded, failed, partially written
  - Log detailed errors for failed files

### Requirement: Error Handling & Recovery
System MUST handle errors gracefully without data loss.

#### Scenario: Corrupted audio file
- GIVEN audio file with corrupted headers or frames
- WHEN handler attempts to read
- THEN system SHALL:
  - Detect corruption (invalid magic bytes, size mismatches)
  - Return error with file path
  - NOT attempt to write (prevent further corruption)
  - Flag file for manual inspection

#### Scenario: Permission denied
- GIVEN audio file with read-only permission
- WHEN handler.write_tags() called and write requested
- THEN system SHALL:
  - Attempt write
  - Detect permission error
  - Return PermissionError with file path
  - Suggest `chmod` or file permission change
  - NOT corrupt file (failed write)

#### Scenario: Disk full during write
- GIVEN insufficient disk space for backup + write
- WHEN handler.write_tags() called
- THEN system SHALL:
  - Detect disk full error during backup creation
  - Abort before touching original file
  - Return DiskFullError
  - Leave original file intact (no data loss)
