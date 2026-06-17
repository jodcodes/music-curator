# Apple Music Integration Specifications

## Context & Implementation Guide

Apple Music integration provides AppleScript-based access to macOS Music.app library, enabling reading of playlists, extraction of track metadata, and playlist organization operations. The system handles both regular playlists and playlist folders with robust error handling and subprocess management.

### Core Features

- **Playlist enumeration**: Read all playlists and folders from Music.app
- **Track metadata extraction**: Retrieve track information (name, artist, album, duration, etc.) from playlists
- **Playlist organization**: Move playlists into targeted folders with validation
- **Folder management**: Create and manage playlist folder structures
- **AppleScript interface**: Encapsulated subprocess execution with error handling
- **Template-based scripts**: Load AppleScript templates for different operations
- **Version detection**: Query Music.app version for compatibility checks

### Implementation Files

- `src/apple_music.py` - Core AppleScript interface and operations
- `src/scripts/` - AppleScript template directory
  - `get_tracks_info_playlists.applescript` - Track extraction
  - `move_playlists.applescript` - Playlist organization
  - `create_folders.applescript` - Folder creation
- `tests/test_integration.py` - Integration tests (requires macOS)

### Configuration

- Apple Music must be running during operations
- macOS Music.app must be accessible via AppleScript
- AppleScript templates must be in `src/scripts/` directory

### Deployment Constraints

- **macOS required**: All operations require macOS and Music.app via AppleScript
- **Runtime requirement**: Music.app must be running
- **No cross-platform support**: Windows/Linux cannot access Music.app

### Related Domains

- **Metadata Enrichment** (`metadata`) - Uses track data from Apple Music
- **Playlist Organization** (`playlists`) - Moves playlists via Apple Music interface
- **Temperament Analysis** (`temperament`) - Analyzes playlists from Music.app

---

## Overview

Apple Music integration SHALL provide AppleScript-based access to macOS Music.app library for reading, enriching, and organizing playlists.

### Requirement: Playlist Enumeration
The system MUST enumerate all playlists and folders in Music.app library.

#### Scenario: Get all playlists and folders
- GIVEN Music.app is running on macOS
- WHEN get_playlist_names() is called
- THEN the system SHALL return list of all playlists and folder names
- AND return empty list if Music.app is unavailable (instead of raising exception)

#### Scenario: Playlist not found
- GIVEN a requested playlist does not exist
- WHEN playlist lookup is attempted
- THEN the system SHALL return empty results
- AND log the failure with context

### Requirement: Track Information Extraction
The system MUST extract track metadata from Music.app playlists.

#### Scenario: Extract track list from playlist
- GIVEN a valid playlist exists in Music.app
- WHEN get_tracks_info_and_playlist_id() is called with playlist name
- THEN the system SHALL return list of Track objects with metadata
- AND include track name, artist, album, duration, and source

#### Scenario: Handle missing playlist
- GIVEN playlist name does not exist
- WHEN track extraction is attempted
- THEN the system SHALL return empty list
- AND log with debug level (expected case)

#### Scenario: Extract from playlist folder
- GIVEN a playlist folder exists in Music.app
- WHEN requesting tracks from folder
- THEN the system SHALL return empty list or skip (folders contain no tracks)

### Requirement: AppleScript Execution
The system MUST safely execute AppleScript via subprocess with error handling.

#### Scenario: Successful AppleScript execution
- GIVEN valid AppleScript is provided
- WHEN _run_applescript() is called
- THEN the system SHALL execute via osascript subprocess
- AND return (success=True, output=script_output)

#### Scenario: AppleScript execution failure
- GIVEN AppleScript fails or osascript is unavailable
- WHEN execution completes
- THEN the system SHALL return (success=False, error_message)
- AND log the error context

#### Scenario: AppleScript subprocess times out
- GIVEN AppleScript execution is slow or hangs
- WHEN subprocess completes with timeout
- THEN the system SHALL handle gracefully
- AND return failure status

### Requirement: Template-Based AppleScripts
The system MUST load AppleScript templates from files.

#### Scenario: Load valid AppleScript template
- GIVEN template file exists in scripts/ directory
- WHEN _load_script_template(name) is called
- THEN the system SHALL read and return script content

#### Scenario: Template file not found
- GIVEN template file does not exist
- WHEN template loading is attempted
- THEN the system SHALL raise FileNotFoundError
- AND include full path in error message

### Requirement: Playlist Organization
The system MUST safely move playlists into target folders.

#### Scenario: Move playlist to folder
- GIVEN playlist and target folder exist in Music.app
- WHEN move_playlists_to_folders() is called
- THEN the system SHALL move playlist via AppleScript
- AND verify operation succeeded

#### Scenario: Target folder does not exist
- GIVEN target folder does not exist
- WHEN move operation is attempted
- THEN the system SHALL create folder first (or return error)
- AND report action taken

#### Scenario: Playlist move fails
- GIVEN AppleScript execution fails
- WHEN playlist move is attempted
- THEN the system SHALL log failure context
- AND return error status (do not raise exception)

### Requirement: Folder Management
The system MUST create playlist folders in Music.app.

#### Scenario: Create new playlist folder
- GIVEN folder name is provided
- WHEN create_playlist_folder() is called
- THEN the system SHALL create folder via AppleScript
- AND return success status

#### Scenario: Folder already exists
- GIVEN folder with name already exists
- WHEN creation is attempted
- THEN the system SHALL return failure or skip gracefully
- AND log that folder exists

### Requirement: Version Detection
The system MUST detect Music.app version for compatibility.

#### Scenario: Get Music.app version
- GIVEN Music.app is running
- WHEN get_apple_music_version() is called
- THEN the system SHALL return version string or None if unavailable
- AND handle gracefully if version detection fails

### Requirement: Error Resilience
The system MUST not interrupt unrelated operations due to Apple Music failures.

#### Scenario: Per-playlist failure isolation
- GIVEN operation on one playlist fails
- WHEN batch processing continues
- THEN the system SHALL log and continue with remaining playlists
- AND return partial results with failure info

#### Scenario: AppleScript unavailability
- GIVEN osascript is unavailable or non-macOS platform
- WHEN AppleScript execution is attempted
- THEN the system SHALL return error status
- AND suggest platform constraints to user
