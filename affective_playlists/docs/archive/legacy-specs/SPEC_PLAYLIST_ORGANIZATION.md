# Functional Specification: Playlist Organization (plsort)

## Overview
Genre-based playlist classification and organization system that categorizes and organizes playlists by musical genre (Hip-Hop, Electronic, Jazz, etc.) in Apple Music.

## Purpose
Automatically classify playlists by genre and organize them within Apple Music library, using both track metadata and AI-assisted genre detection to create a well-organized, genre-based library structure.

## Functional Requirements

### F1: Genre Classification
- Classify playlists into predefined genre categories
- Support multiple genre types (Hip-Hop, Electronic, Jazz, Rock, Pop, etc.)
- Handle genre hybrid playlists
- Use track-level genre metadata as primary source

### F2: Playlist Analysis
- Scan all playlists in Apple Music
- Analyze track genre metadata
- Aggregate genre information
- Determine dominant genre(s)

### F3: Whitelist Support
- Respect whitelist configuration
- Allow processing of all playlists when whitelist disabled
- Support selective playlist processing
- Display whitelist status on startup

### F4: Organization Actions
- Create genre-based folders/groups (if supported)
- Rename playlists with genre tags
- Move playlists to genre collections
- Maintain original playlist data

### F5: Safety Features
- Dry-run mode to preview changes
- Interactive confirmation before changes
- Rollback capability
- No-interactive mode for scripting

## Technical Requirements

### T1: Dependencies
- Apple Music integration via AppleScript
- Standard library: `json`, `logging`, `argparse`, `sys`
- Custom modules: `src/playlist_classifier.py`, `src/playlist_manager.py`

### T2: Configuration
- Whitelist configuration: `data/config/whitelist.json`
- Artist lists per genre: `data/artist_lists/`
- Genre definitions: `src/config.py`

### T3: Data Flow
1. Load whitelist configuration
2. Retrieve all (or whitelisted) playlists
3. For each playlist:
   - Extract track metadata
   - Identify dominant genres
   - Classify playlist
4. Present classification results
5. Apply changes (with confirmation or dry-run)
6. Log all changes

### T4: Genre Classification Logic
- Primary: Track-level genre metadata
- Secondary: Artist genre matching (from artist lists)
- Fallback: Manual classification option
- Confidence scoring

### T5: Apple Music Integration
- Query playlist structure
- Read track metadata
- Modify playlist organization
- Handle special playlists (Library, Recent, etc.)

## Input/Output

### Input
- Optional: `--select-from-whitelist` - Choose specific playlists
- Optional: `--dry-run` - Preview without changes
- Optional: `--no-interactive` - Batch mode
- Optional: `--ignore-whitelist` - Process all playlists

### Output
- Classification results per playlist
- Genre assignments
- Summary of changes
- Success/failure log

## Configuration
- Whitelist: `data/config/whitelist.json`
- Artist lists: `data/artist_lists/` directory
- Genre taxonomy: Defined in code

## Dependencies
- `subprocess` - AppleScript execution
- `json` - Config file handling
- `logging` - Operation tracking
- Custom: `src/playlist_classifier.py`
- Custom: `src/playlist_manager.py`

## Implementation Details
- Source: `src/plsort.py`
- Entry point: `main.py` → `run_playlist_organization()`
- Related: `src/playlist_classifier.py`, `src/playlist_manager.py`, `src/apple_music.py`

## Error Scenarios
- Whitelist not found → Use default or disable
- Playlist locked/protected → Skip with warning
- AppleScript execution fails → Retry or abort
- Genre conflict → Present for user decision
- Dry-run only, no actual changes applied

## Non-Functional Requirements

### Performance Requirements
- **Genre Classification**: < 2 seconds per playlist (all metadata local)
- **AppleScript Execution**: < 5 seconds per action
- **Batch Processing**: Process 100 playlists in < 10 minutes
- **Memory Usage**: < 500MB for 100-playlist batch
- **Throughput**: ~10 playlists/minute
- **Max Playlists**: Support up to 1,000 playlists

### Reliability & Robustness
- **Retry Strategy**: AppleScript failures retry 2x with 2-second delay
- **Timeout Threshold**: 30 seconds max per AppleScript operation
- **Partial Failure**: Log failed playlists, continue with others
- **Safe Defaults**: Never modify without user confirmation (unless --dry-run or scripted)
- **Recovery**: If interrupted mid-operation, detect partial changes on restart

### Security & Data Privacy
- Playlist data held in memory only during processing
- No caching of playlist contents
- Log only playlist names (sanitized)
- Track record of all modifications (audit trail)
- Preserve original playlist order/content

## Data Models/Schemas

### Playlist Classification Result
```python
{
    "playlist_name": str,
    "playlist_id": str,             # Apple Music identifier
    "track_count": int,
    "primary_genre": str,           # Most common genre
    "secondary_genres": [str],      # Up to 3 secondary genres
    "genre_confidence": float,      # 0.0-1.0 overall confidence
    "source_breakdown": {
        "metadata_match": int,      # Tracks with explicit genre
        "artist_match": int,        # Tracks matched to artist
        "manual_classify": int      # Unmatched tracks
    },
    "classification_timestamp": str,
    "recommended_action": str       # What to organize as
}
```

### Organization Action Log
```python
{
    "timestamp": str,               # ISO 8601
    "action": str,                  # "rename", "move", "create_group"
    "playlist_name": str,
    "old_value": str,
    "new_value": str,
    "status": str,                  # "success", "failed", "skipped"
    "reason": str or None           # If failed/skipped
}
```

## Acceptance Criteria
- ✓ Classifies playlists into correct genres
- ✓ Respects whitelist configuration (enabled/disabled)
- ✓ Dry-run mode shows changes without modifying
- ✓ Interactive mode requires user confirmation
- ✓ Batch mode (--no-interactive) applies changes without prompts
- ✓ Handles locked/system playlists gracefully
- ✓ Maintains audit trail of all changes
- ✓ Survives interruption with recovery capability

## Constraints & Compatibility
- **Python Version**: 3.8+
- **macOS Version**: 10.13+ (Music.app availability)
- **Disk Space**: 50MB for configuration and logs
- **Network**: Not required (local operation)
- **Permissions**: User must have Music.app permissions
- **Maximum Playlists**: 1,000 (tested and supported)

## Test Strategy
### Unit Tests
- [ ] Genre classification algorithm
- [ ] Whitelist filtering logic
- [ ] Genre conflict detection
- [ ] Confidence scoring
- [ ] Genre normalization

### Integration Tests
- [ ] Full classification workflow
- [ ] Dry-run mode verification
- [ ] AppleScript execution
- [ ] Playlist modification operations
- [ ] Whitelist enabled/disabled modes
- [ ] Recovery from interruption

### Test Data
- 10 playlists of varying sizes (5-500 tracks)
- Playlists with mixed genres
- Playlists with no metadata
- System/locked playlists
- Test whitelist configurations

## State Management
- **Classification Cache**: In-memory during session
- **Organization Log**: Persisted to `data/logs/organization_log.json`
- **Whitelist State**: Loaded from `data/config/whitelist.json`
- **Recovery**: Can resume from organization log if interrupted
- **Concurrency**: Single-threaded, not thread-safe
- **Idempotency**: Re-running same operation is safe (compares before change)

## Rollback Mechanism
- **Change Tracking**: Store original state before each modification
- **Undo History**: Keep 30-day history of changes
- **Storage**: `data/logs/organization_rollback.json`
- **Manual Rollback**: Provide `--rollback` option to revert last N operations
- **Scope**: Rollback by playlist name, date range, or operation type

## Genre Taxonomy
- **Supported Genres**: Hip-Hop, Electronic, Jazz, Rock, Pop, Classical, Country, R&B/Soul, Indie, Alternative, Metal, Latin, World, Ambient, EDM, Folk
- **Extensibility**: User can add custom genres to artist lists
- **Fallback**: "Uncategorized" for unknown genres
- **Hybrid Playlists**: Support "Multi-Genre" tag if no single dominant genre

## AppleScript Integration
- **Command Pattern**: Batch AppleScript commands for performance
- **Error Handling**: Parse AppleScript errors, provide user-friendly messages
- **Limitations**: Cannot move playlists (only rename/reorganize)
- **Verification**: Read back modified playlist to confirm change
