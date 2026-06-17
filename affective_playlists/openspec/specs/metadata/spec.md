# Metadata Specifications

## Context & Implementation Guide

Metadata enrichment enables users to automatically populate missing track information (BPM, genre, release year) by querying multiple external databases in priority order. The system is designed for safe, reliable operation with robust error handling and source provenance tracking.

### Core Features

- **Field-aware querying**: Skip sources for fields that are already populated
- **Multi-source fallback**: Configured source priority with exhaustive search capabilities
- **Source provenance**: Track which source provided each enriched field
- **Safe write-back**: Per-track error isolation during batch operations
- **Apple Music compatibility**: Skip cover-art embedding for tracks from Apple Music

### Implementation Files

- `src/metadata_enrichment.py` - Core enrichment orchestration
- `src/metadata_fill.py` - Field population logic
- `src/metadata_queries.py` - Multi-source query handling
- `src/llm_client.py` - LLM-based enrichment fallback
- `tests/test_metadata_enrichment.py` - Test suite

### Configuration

- `data/config/weights.json` - Source priority and field weights
- Environment variables for API credentials (Spotify, MusicBrainz, Last.fm, etc.)

### Related Domains

- **Playlist Organization** (`playlists`) - Uses enriched metadata for genre classification
- **Temperament Analysis** (`temperament`) - Uses enriched metadata for mood classification

---

## Overview
Metadata enrichment SHALL fill missing metadata fields for selected tracks using multiple sources with deterministic fallback behavior.

### Requirement: Missing Field Enrichment
The system MUST determine missing metadata fields before querying external sources.

#### Scenario: Field-aware query strategy
- GIVEN a track with existing genre and missing BPM and year
- WHEN enrichment starts
- THEN the system SHALL skip genre lookup and search for BPM/year only

#### Scenario: Exhaustive fallback for missing fields
- GIVEN a track with missing metadata and partial source failures
- WHEN enrichment runs through configured source order
- THEN the system MUST continue until all missing fields are found or all sources are exhausted

### Requirement: Source Priority and Provenance
The system MUST preserve source provenance for each enriched field.

#### Scenario: First-source wins per field
- GIVEN multiple sources return values for the same missing field
- WHEN the first source in priority order returns a valid value
- THEN the system SHALL keep that value and skip later sources for that field

#### Scenario: Enrichment summary includes source details
- GIVEN at least one field was enriched
- WHEN processing completes
- THEN the output MUST include which source provided each field

### Requirement: Safe Application Behavior
The system MUST apply metadata updates safely and report failures without stopping unrelated tracks.

#### Scenario: Per-track failure isolation
- GIVEN one track fails during write-back
- WHEN batch processing continues
- THEN the system SHALL log the failure and continue processing remaining tracks

#### Scenario: Apple Music cover-art guard
- GIVEN a track originates from Apple Music
- WHEN cover-art embedding is requested
- THEN the system MUST skip local embedding and report the skip reason
