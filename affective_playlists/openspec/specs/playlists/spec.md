# Playlists Specifications

## Context & Implementation Guide

Playlist organization enables users to classify playlists by genre and optionally move them into configured folder structures. The system provides a safe workflow with dry-run preview, explicit confirmation steps, and platform-specific constraints.

### Core Features

- **Genre classification**: Classify playlists using available track metadata and configured genre logic
- **Safe organization**: Explicit user confirmation before executing playlist moves
- **Dry-run mode**: Preview intended moves without modifying playlists
- **Unclassified handling**: Playlists that cannot be reliably classified are flagged and not moved
- **Platform constraints**: Move operations require macOS; metadata enrichment works on all platforms

### Implementation Files

- `src/playlist_classifier.py` - Genre classification logic
- `src/playlist_manager.py` - Playlist move orchestration
- `src/playlist_utils.py` - Playlist utilities
- `tests/test_playlist_classifier.py` - Test suite

### Configuration

- `data/config/playlist_folders.json` - Target folder mappings by genre
- `data/config/genre_map.json` - Genre classification rules

### Deployment Constraints

- **macOS required**: Playlist move operations require macOS and Music.app access via AppleScript
- **Non-macOS**: Metadata enrichment can still run in folder mode without modification
- **Apple Music**: The system integrates with Apple Music library on macOS

### Related Domains

- **Metadata Enrichment** (`metadata`) - Provides enriched metadata for classification
- **Temperament Analysis** (`temperament`) - Alternative classification approach based on mood

---

## Overview
Playlist organization SHALL classify playlists by genre and optionally move them into configured folders with explicit confirmation safeguards.

### Requirement: Genre Classification
The system MUST classify each selected playlist using available track metadata and configured genre logic.

#### Scenario: Playlist classified with confidence
- GIVEN a playlist with sufficient track metadata
- WHEN classification runs
- THEN the system SHALL produce a genre assignment with details

#### Scenario: Unclassified playlist handling
- GIVEN a playlist cannot be classified reliably
- WHEN organization summary is produced
- THEN the system MUST mark it as unclassified and avoid moving it automatically

### Requirement: Safe Organization Actions
The system MUST require explicit user confirmation before executing real playlist move operations.

#### Scenario: User declines confirmation
- GIVEN organization is about to run in execute mode
- WHEN the user declines confirmation
- THEN the system SHALL cancel without changing playlist locations

#### Scenario: Dry-run behavior
- GIVEN dry-run mode is active
- WHEN organization is executed
- THEN the system MUST report intended moves without performing them

### Requirement: Platform Constraints
Apple Music move operations MUST only run on macOS.

#### Scenario: Non-macOS organization attempt
- GIVEN the command runs on non-macOS
- WHEN the user starts playlist organization
- THEN the CLI MUST stop with platform-error message and guide to alternatives
- AND exit code SHALL be 1

#### Scenario: Folder-based enrichment on non-macOS (allowed)
- GIVEN the user selects metadata enrichment in Folder mode on non-macOS
- WHEN enrichment runs
- THEN the system SHALL NOT apply platform guard (macOS not required for folders)
- AND processing SHALL continue normally
