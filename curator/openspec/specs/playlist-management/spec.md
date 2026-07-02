# Playlist Management Specifications

## Context & Implementation Guide

Playlist Management provides operations for creating, moving, deleting, and organizing playlists in Apple Music library. The system includes safe operations with confirmation workflows, dry-run previews, and error handling. Playlist utilities support fuzzy artist matching, ID resolution, and safe playlist selection.

### Core Features

- **Playlist CRUD**: Create, read, update, delete playlists
- **Playlist moves**: Safe movement of playlists into folder hierarchies
- **Fuzzy playlist selection**: Find playlists by partial name matching
- **Playlist ID resolution**: Get Apple Music playlist IDs by various criteria
- **Folder creation**: Create and manage playlist folder structures
- **Safe operations**: Dry-run preview before real execution
- **Confirmation workflows**: Explicit user confirmation for destructive operations
- **Error isolation**: Per-playlist error handling (don't fail entire batch)
- **Undo capability**: Track operations for potential rollback
- **Batch operations**: Move multiple playlists efficiently

### Implementation Files

- `src/playlist_manager.py` - Playlist operations and orchestration
- `src/playlist_utils.py` - Playlist selection and ID resolution utilities
- `src/apple_music.py` - Apple Music integration layer
- `tests/test_playlist_manager.py` - Playlist operation tests
- `tests/test_playlist_fuzzy_matching.py` - Fuzzy matching tests

### Configuration

- Environment variables:
  - `PLAYLIST_DRY_RUN_ENABLED` - Default to dry-run mode (default: true)
  - `PLAYLIST_FUZZY_MATCH_THRESHOLD` - Name matching threshold (default: 0.80)
  - `PLAYLIST_AUTO_CONFIRM` - Skip confirmation prompts (default: false)
- Configuration files:
  - `data/config/playlist_folders.json` - Mapping of genres to folder paths

### Related Domains

- **Playlist Classification** (`genre-classification`) - Determines target genres
- **Apple Music** (`apple_music`) - Underlying integration with Music.app
- **CLI Interface** (`cli`) - User interface for playlist operations

---

## Overview

Playlist Management SHALL provide safe operations for organizing, moving, and managing playlists with fuzzy selection, dry-run previews, and error isolation.

### Requirement: Playlist Selection
System MUST reliably identify target playlists from library.

#### Scenario: Select playlist by exact name
- GIVEN user specifies playlist "Summer Hits"
- WHEN get_playlist_by_name("Summer Hits", exact=True) called
- THEN system SHALL:
  - Query Apple Music library for exact match
  - Return playlist ID if found
  - Return error if not found or multiple matches

#### Scenario: Select playlist by fuzzy matching
- GIVEN user specifies playlist "Summer" (partial name)
- WHEN get_playlist_by_name("Summer", exact=False) called
- WITH fuzzy_match_threshold = 0.80
- THEN system SHALL:
  - Find all playlists containing "Summer"
  - Calculate name similarity for each
  - Return playlists above threshold
  - Rank by similarity score (highest first)

#### Scenario: Ambiguous playlist selection
- GIVEN user specifies "Summer" and multiple playlists match:
  - "Summer Hits" (0.95)
  - "Summer Vibes" (0.85)
  - "Endless Summer" (0.80)
- WHEN get_playlist_by_name("Summer", exact=False) called
- THEN system SHALL:
  - Return multiple matches
  - Display matches ranked by score
  - Require explicit user selection if interactive
  - Raise AmbiguousPlaylistError if non-interactive with multiple matches

#### Scenario: No playlist found
- GIVEN user specifies playlist "NonExistent"
- WHEN get_playlist_by_name("NonExistent") called
- THEN system SHALL:
  - Search library exhaustively
  - Return not-found error with suggestions
  - Suggest similar playlists if fuzzy matching available
  - List available playlists for manual selection

### Requirement: Playlist ID Resolution
System MUST resolve playlist identifiers consistently.

#### Scenario: Get playlist ID by name
- GIVEN playlist name "Rock Classics"
- WHEN get_playlist_id("Rock Classics") called
- THEN system SHALL:
  - Find playlist in Music.app
  - Return unique playlist ID (UUID or Music.app identifier)
  - Return error if not found or duplicate names

#### Scenario: Get playlist ID by reference
- GIVEN playlist object or reference
- WHEN get_playlist_id(playlist_obj) called
- THEN system SHALL:
  - Extract or confirm ID
  - Validate ID exists in current library
  - Return ID or error if invalid

#### Scenario: ID stability
- GIVEN stable playlist ID from previous operation
- WHEN playlist referenced again with same ID
- THEN system SHALL:
  - Resolve ID consistently
  - Fail gracefully if playlist deleted
  - NOT use IDs from other systems (e.g., Spotify IDs)

### Requirement: Playlist Creation
System MUST create new playlists safely.

#### Scenario: Create simple playlist
- GIVEN playlist name "New Playlist" and optional description
- WHEN create_playlist("New Playlist", description="Test") called
- THEN system SHALL:
  - Create playlist in Music.app
  - Return new playlist ID
  - Playlist ready for track additions

#### Scenario: Create playlist in specific folder
- GIVEN folder structure exists and target folder specified
- WHEN create_playlist("Genre Playlist", folder_id=genre_folder_id) called
- THEN system SHALL:
  - Create playlist in specified folder
  - Return playlist ID
  - Playlist appears in correct location in Music.app

#### Scenario: Prevent duplicate playlists
- GIVEN playlist named "Summer Hits" already exists
- WHEN create_playlist("Summer Hits") called
- THEN system SHALL:
  - Detect existing playlist (by name)
  - Return error or confirmation dialog
  - Option to use existing instead of creating duplicate
  - Option to append suffix ("Summer Hits 2")

### Requirement: Playlist Deletion
System MUST delete playlists with safety guarantees.

#### Scenario: Safe deletion with confirmation
- GIVEN playlist ID and user intent to delete
- WHEN delete_playlist(playlist_id) called
- THEN system SHALL:
  - Display playlist details (name, track count)
  - Require explicit confirmation
  - If confirmation: delete from Music.app
  - Confirm deletion on success

#### Scenario: Prevent accidental bulk deletion
- GIVEN multiple playlists to delete and PLAYLIST_AUTO_CONFIRM=false
- WHEN delete_batch(playlist_ids) called
- THEN system SHALL:
  - List playlists to delete with details
  - Require individual confirmation per playlist
  - Or single confirmation for all (after review)
  - Stop on user rejection

#### Scenario: Deletion with auto-confirm disabled
- GIVEN PLAYLIST_AUTO_CONFIRM=false (safety mode)
- WHEN delete_playlist(playlist_id) called without explicit confirmation
- THEN system SHALL:
  - Return pending deletion (not executed)
  - Require explicit confirmation call
  - prevent accidental deletion

### Requirement: Playlist Movement & Organization
System MUST move playlists safely with preview and confirmation.

#### Scenario: Get movement preview (dry-run)
- GIVEN playlists and target genre categories
- WHEN organize_playlists(dry_run=True) called
- THEN system SHALL:
  - Calculate intended movements
  - Return preview without modifying playlists
  - Show: playlist name, current location, target location
  - Show: reason (classified as genre X)

#### Scenario: Execute playlist moves
- GIVEN dry-run preview reviewed and confirmed
- WHEN organize_playlists(dry_run=False) called
- THEN system SHALL:
  - Execute each move atomically
  - Continue if individual move fails (error isolation)
  - Return summary: moved, failed, skipped
  - Log each operation with timestamp

#### Scenario: Move to non-existent folder
- GIVEN target folder does not exist
- WHEN move_playlist(playlist_id, target_folder_path) called
- THEN system SHALL:
  - Create target folder if configured to do so
  - Move playlist into folder
  - Log folder creation and move
  - OR return error if auto-create disabled

#### Scenario: Move conflict handling
- GIVEN target folder already contains playlist with same name
- WHEN move_playlist(playlist_id, target_folder) called
- THEN system SHALL:
  - Detect naming conflict
  - Rename incoming playlist (append suffix or ID)
  - Log rename operation
  - Continue move after handling conflict
  - OR return error if manual resolution required

#### Scenario: Batch playlist moves
- GIVEN 20 playlists to organize into 6 folders
- WHEN batch_organize(playlists) called
- THEN system SHALL:
  - Process moves efficiently
  - Maintain order if specified
  - Handle errors individually (don't stop on first failure)
  - Return detailed summary per playlist

### Requirement: Folder Management
System MUST create and manage playlist folder hierarchies.

#### Scenario: Create single folder
- GIVEN folder name and optional location
- WHEN create_folder("Genres") called
- THEN system SHALL:
  - Create folder in Music.app
  - Return folder ID
  - Ready to receive playlists

#### Scenario: Create folder hierarchy
- GIVEN folder structure: Genres/ → Rock/ → Classic Rock/
- WHEN create_folder_hierarchy("Genres/Rock/Classic Rock") called
- THEN system SHALL:
  - Create parent folders if not exist
  - Create leaf folder
  - Return leaf folder ID
  - All folders created with correct hierarchy

#### Scenario: Folder existence check
- GIVEN folder path and folder structure
- WHEN folder_exists("Genres/Electronic") called
- THEN system SHALL:
  - Check if folder exists in Music.app
  - Return True if exists
  - Return False if not exist

#### Scenario: List contents of folder
- GIVEN folder ID
- WHEN get_folder_contents(folder_id) called
- THEN system SHALL:
  - Return list of playlists in folder
  - Return list of subfolders
  - Maintain hierarchy information

#### Scenario: Folder configuration from mapping
- GIVEN genre_map.json:
  ```json
  {
    "hip-hop": "Genres/Hip-Hop",
    "electronic": "Genres/Electronic",
    ...
  }
  ```
- WHEN initialize_folders_from_config() called
- THEN system SHALL:
  - Parse configuration
  - Create all specified folder hierarchies
  - Return mapping: genre → folder_id
  - Report created folders

### Requirement: Fuzzy Playlist Matching
System MUST handle playlist selection with name variations.

#### Scenario: Exact initial match
- GIVEN playlists: "Rock Classics", "Rock Covers", "Classic Rock"
- WHEN find_playlists("Rock", threshold=0.80) called
- THEN system SHALL:
  - Return all three playlists
  - Ranked by similarity: "Rock Classics" (0.95), "Rock Covers" (0.95), "Classic Rock" (0.75)

#### Scenario: Threshold-based filtering
- GIVEN fuzzy_match_threshold = 0.90
- WHEN find_playlists("Summer", threshold=0.90) called
- THEN system SHALL:
  - Match "Summer Hits" (0.92)
  - Match "Summer Vibes" (0.91)
  - Exclude "Endless Summer" (0.80 < 0.90)

#### Scenario: Special character handling
- GIVEN playlists: "The Beatles", "The-Beatles", "The & The Beatles"
- WHEN find_playlists("Beatles", threshold=0.80) called
- THEN system SHALL:
  - Normalize names (remove articles, special chars)
  - Find all variations
  - Return all above threshold

#### Scenario: Case-insensitive matching
- GIVEN playlists: "ROCK CLASSICS", "rock classics", "Rock Classics"
- WHEN find_playlists("rock") called
- THEN system SHALL:
  - Normalize case (all lowercase)
  - Find all variations
  - Return consistent results

### Requirement: Error Handling & Recovery
System MUST handle failures gracefully without data loss.

#### Scenario: Apple Music not running
- GIVEN Music.app not running on macOS
- WHEN playlist operation called
- THEN system SHALL:
  - Detect unavailable Music.app
  - Return error with instruction to start Music.app
  - Suggest alternative (folder mode if available)

#### Scenario: Playlist becomes unavailable
- GIVEN playlist existed but now deleted externally
- WHEN operation references playlist ID
- THEN system SHALL:
  - Detect missing playlist
  - Return error with playlist ID
  - Suggest refreshing playlist cache
  - Continue with other playlists if batch operation

#### Scenario: Folder creation fails
- GIVEN insufficient permissions to create folder
- WHEN create_folder("Genres") called
- THEN system SHALL:
  - Detect permission error
  - Return error with remediation steps
  - Suggest checking Music.app permissions
  - NOT partial create (atomic failure)

#### Scenario: Move operation fails mid-batch
- GIVEN moving 10 playlists, 6th move fails
- WHEN batch_organize called
- THEN system SHALL:
  - Complete moves 1-5
  - Log failure for #6 with reason
  - Continue with moves 7-10
  - Return summary: 9 succeeded, 1 failed

#### Scenario: Rollback unsuccessful operation
- GIVEN move operation failed after partial success
- WHEN rollback_batch_operation(operation_id) called
- THEN system SHALL:
  - Attempt to reverse completed operations
  - Restore playlists to original locations
  - Log rollback success/failure for each operation
  - Return summary

### Requirement: Batch Optimization
System MUST handle multiple playlists efficiently.

#### Scenario: Batch retrieve playlist IDs
- GIVEN list of 100 playlist names
- WHEN get_playlist_ids(["pl1", "pl2", ..., "pl100"]) called
- THEN system SHALL:
  - Resolve all IDs with single Music.app query (if possible)
  - Avoid redundant queries per name
  - Return mapping: name → ID
  - Log unresolved names

#### Scenario: Smart caching of playlist list
- GIVEN multiple operations on same playlist set
- WHEN playlist list accessed multiple times
- THEN system SHALL:
  - Cache Music.app playlist list
  - Validate cache before use
  - Timeout old cache (configurable, default: 5 minutes)
  - Reduce redundant Music.app queries

### Requirement: Audit Logging
System MUST track all operations for audit and recovery.

#### Scenario: Log playlist operations
- GIVEN playlist move/create/delete operations
- WHEN operations complete
- THEN system SHALL:
  - Log operation: timestamp, action, playlist, before/after state
  - Log by user (if available) or system
  - Store audit log in database or file
  - Example: "2025-03-09 10:30:15 - move: 'Rock Classics' from 'Misc' to 'Genres/Rock'"

#### Scenario: Audit trail accessibility
- GIVEN audit logs for all operations
- WHEN view_operation_history() called
- THEN system SHALL:
  - Return list of operations with full details
  - Filter by date range, operation type, playlist
  - Export to CSV or JSON
  - Support replaying operations for undo/redo
