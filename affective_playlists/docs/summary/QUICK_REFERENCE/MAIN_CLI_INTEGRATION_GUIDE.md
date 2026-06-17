# Main CLI Integration Guide

**Date**: January 4, 2026  
**Status**: Complete  
**Scope**: Unified CLI experience across all features

## Overview

The main.py CLI entry point now uses the new CLI UI library (`cli_ui`) across all features for a cohesive, fun, and engaging user experience. Every feature—temperament analysis, metadata enrichment, and playlist organization—now has colorful output, interactive menus, and professional formatting.

## Updated Architecture

```
main.py
├── print_header()          # Fancy header with emoji and subtitle
├── Menu.select()           # Interactive feature selection
├── print_footer()          # Celebratory footer
│
├── run_temperament_analysis()
│   ├── print_header()
│   ├── info()              # Status messages
│   ├── success()           # Success confirmations
│   └── print_footer()
│
├── run_metadata_enrichment()
│   ├── Menu.select()       # Target selection (playlist/folder)
│   ├── Menu.select()       # Playlist selection from whitelist
│   ├── Menu.input_text()   # Text input for manual entry
│   ├── info()              # Info messages
│   ├── error()             # Error messages
│   └── (Header from MetadataFillCLI)
│
└── run_playlist_organization()
    ├── print_header()
    ├── warning()           # Important warnings
    ├── Menu.confirm()      # Safety confirmation
    ├── info()              # Status messages
    └── print_footer()
```

## Usage Examples

### Interactive Mode (Default)

```bash
python main.py
```

Output:
```
┌──────────────────────────────┐
│   🎵 affective_playlists    │
│  Unified Music Library Org   │
└──────────────────────────────┘

Select a feature to run

  1. 🎭 Temperament Analysis - AI emotion classification
  2. 📝 Metadata Enrichment - Fill missing metadata
  3. 📚 Playlist Organization - Genre-based sorting

→ Choose option [1-3]:
```

### Direct Feature Execution

```bash
python main.py temperament   # Run temperament analysis directly
python main.py enrich        # Run metadata enrichment directly
python main.py organize      # Run playlist organization directly
```

### Verbose Mode

```bash
python main.py -v temperament
python main.py --verbose enrich
```

## Feature-by-Feature UI Updates

### 1. Temperament Analysis

**Before**:
```
======================================================================
TEMPERAMENT ANALYSIS - AI-based Playlist Emotion Classification
======================================================================
```

**After**:
```
┌────────────────────────────────────┐
│ 🎭 Temperament Analysis           │
│ AI-based Playlist Emotion Class... │
└────────────────────────────────────┘

ℹ Initializing clients...
ℹ Connecting to Music.app...
✓ Connected to Music.app
ℹ Starting temperament analysis...
```

**Flow**:
1. Fancy header with emoji and subtitle
2. Status messages showing each step
3. Success/error messages for key events
4. Celebratory footer on completion

**Status Messages**:
- ℹ Info: Step descriptions
- ✓ Success: Connected to Music.app
- ✗ Error: Connection failures

### 2. Metadata Enrichment

**Before**:
```
What would you like to enrich metadata for?
1. Playlist
2. Folder
Enter your choice (1 or 2):
```

**After**:
```
📁 What would you like to enrich?

  1. Playlist
  2. Folder

→ Choose option [1-2]:
```

**Interactive Features**:

1. **Target Selection** (Menu.select)
   ```
   📁 What would you like to enrich?
   1. Playlist
   2. Folder
   ```

2. **Playlist Selection** (Menu.select with whitelist)
   ```
   ℹ Whitelist enabled with 5 playlists
   
   🎵 Choose a playlist
   1. Enter playlist name manually
   2. Favorites
   3. Road Trip
   4. Summer Vibes
   ```

3. **Manual Input** (Menu.input_text)
   ```
   🎵 Playlist name: _
   ```

**Status Messages**:
- ℹ Whitelist status
- ✓ Playlist loaded
- ✗ Enrichment errors

### 3. Playlist Organization

**Before**:
```
======================================================================
PLAYLIST ORGANIZATION - Classify & Organize by Genre
======================================================================

Whitelist is ENABLED with 3 playlists
The system will only process whitelisted playlists.

IMPORTANT: This will ACTUALLY MOVE playlists in Apple Music!
```

**After**:
```
┌──────────────────────────────────┐
│ 📚 Playlist Organization         │
│ Classify & Organize by Genre     │
└──────────────────────────────────┘

⚠ Whitelist ENABLED with 3 playlists

⚠️  This will ACTUALLY MOVE playlists in Apple Music!

Continue with playlist organization? [y/N]: y

ℹ Starting playlist organization...
```

**Safety Features**:
1. Warning emoji (⚠) before destructive operations
2. Menu.confirm() with default=False for safety
3. Clear confirmation before proceeding

## Menu Components Used

### 1. Menu.select() - Feature Selection

```python
choice = Menu.select("📁 What would you like to enrich?", ["Playlist", "Folder"])
# Returns: 0 or 1 (index of selected option)
```

**UI**:
```
📁 What would you like to enrich?

  1. Playlist
  2. Folder

→ Choose option [1-2]:
```

### 2. Menu.input_text() - Manual Entry

```python
playlist_name = Menu.input_text("🎵 Playlist name")
# Returns: user-entered text
```

**UI**:
```
🎵 Playlist name: _
```

### 3. Menu.confirm() - Safety Confirmation

```python
if Menu.confirm("Continue with organization?", default=False):
    # User confirmed
```

**UI**:
```
Continue with organization? [y/N]: y
```

## Header and Footer Format

### Header
```
┌────────────────────────────────────┐
│ 🎭 Feature Name                   │
│ Feature Description               │
└────────────────────────────────────┘
```

### Footer
```
✨ All done! 🎉
──────────────────
```

## Color Scheme

- **Success** (Green): ✓ Operation completed successfully
- **Error** (Red): ✗ Operation failed
- **Warning** (Yellow): ⚠ Important warnings
- **Info** (Cyan): ℹ Status messages and information
- **Headers** (Magenta): Feature names and section titles

## Status Message Examples

```python
# Success
print(success("Connected to Music.app"))  # ✓ Connected to Music.app

# Error
print(error("Failed to load playlist"))   # ✗ Failed to load playlist

# Warning
print(warning("This is destructive"))     # ⚠ This is destructive

# Info
print(info("Processing tracks..."))       # ℹ Processing tracks...
```

## Emoji Usage

- 🎵 Music-related operations (playlists, tracks)
- 🎭 Temperament analysis (emotions)
- 📝 Metadata (data enrichment)
- 📁 Folders and file operations
- 📚 Organization (collections)
- 🔥 Special effects (active operations)
- ✨ Celebration (completion)

## Backwards Compatibility

The updated main.py is fully backwards compatible:

✓ All command-line arguments work identically
✓ Return codes unchanged (0 = success, 1 = failure)
✓ Behavior identical, only UI enhanced
✓ Non-TTY output gracefully disables colors
✓ All existing tests pass

## Testing

All CLI UI components are tested:

```bash
pytest tests/test_cli_ui.py -v  # 31 tests for UI components
pytest tests/test_enrich_once_hierarchy.py -v  # 21 tests for metadata
```

Total: 52 tests passing, 0 failures

## Future Enhancements

1. **Progress tracking**: Add progress bars for long operations
2. **Spinners**: Add animated spinners for async operations
3. **Rich tables**: Display results in formatted tables
4. **Statistics**: Show summary statistics with visual bars
5. **Keyboard shortcuts**: Add keyboard navigation to menus
6. **History**: Remember recent playlists/folders

## Code Example: Complete Flow

```python
# Interactive menu
print_header("🎵 affective_playlists", "Unified Music Library Organization")

# Feature selection
features = [
    "🎭 Temperament Analysis - AI emotion classification",
    "📝 Metadata Enrichment - Fill missing metadata",
    "📚 Playlist Organization - Genre-based sorting",
]
choice = Menu.select("Select a feature to run", features)

if choice == 0:
    # Temperament Analysis
    print_header("🎭 Temperament Analysis", "AI-based...")
    print(info("Initializing clients..."))
    try:
        # ... do work ...
        print(success("Analysis complete"))
        print_footer()
    except Exception as e:
        print(error(f"Failed: {e}"))

elif choice == 1:
    # Metadata Enrichment
    target_choice = Menu.select("📁 What to enrich?", ["Playlist", "Folder"])
    if target_choice == 0:
        playlist_name = Menu.input_text("🎵 Playlist name")
        print(info("Starting enrichment..."))
        # ... do work ...
        print(success("Enrichment complete"))
```

## Integration Summary

**Files Modified**:
- `main.py` - Complete CLI UI integration

**Files Used**:
- `src/cli_ui.py` - CLI UI library
- `src/metadata_fill.py` - Already integrated with CLI UI

**Tests Passing**: 52/52 ✓

**Status**: Production Ready

---

**Last Updated**: January 4, 2026  
**Status**: Complete  
**Related**: [cli_ui.py](/src/cli_ui.py), [CLI_UI_QUICK_REFERENCE.md](/docs/summary/QUICK_REFERENCE/CLI_UI_QUICK_REFERENCE.md)
