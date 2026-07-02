# CLI UI Quick Reference

A fun and engaging command-line interface library for the affective_playlists project.

## Overview

The `cli_ui` module provides colorful, interactive CLI components that make user interactions more engaging:
- ANSI color codes (16 colors + bright variants)
- Unicode icons and symbols
- Progress bars with ETA
- Interactive menus and confirmations
- Tables for data display
- Status messages (success, error, warning, info)
- Fancy boxes and headers

## Quick Start

```python
from cli_ui import (
    print_header, print_footer,
    success, error, warning, info,
    Menu, ProgressBar, Table
)

# Print header
print_header("🎵 Feature Name", "Subtitle")

# Status messages
print(success("Operation completed!"))
print(error("Something went wrong"))
print(warning("Be careful"))
print(info("FYI: This is important"))

# Progress bar
prog = ProgressBar(100, "Processing")
for i in range(100):
    time.sleep(0.01)
    prog.update()

# Interactive menu
choice = Menu.select("Choose an option", ["Option 1", "Option 2", "Option 3"])

# Confirmation
if Menu.confirm("Continue?"):
    print(success("Continuing..."))

# Print footer
print_footer()
```

## Color System

### Basic Colors
```python
from cli_ui import Color, colorize

# Use color codes
text = colorize("Red text", Color.RED)
text = colorize("Green text", Color.GREEN)
text = colorize("Blue text", Color.BLUE)

# Styling
text = bold("Bold text")
text = dim("Faint text")
text = underline("Underlined text")
```

### Available Colors
- `Color.RED`, `Color.GREEN`, `Color.BLUE`
- `Color.YELLOW`, `Color.MAGENTA`, `Color.CYAN`
- `Color.BRIGHT_RED`, `Color.BRIGHT_GREEN`, etc.
- `Color.RESET` - Reset to default

## Icons

```python
from cli_ui import Icon

# Status icons
Icon.SUCCESS       # ✓
Icon.ERROR         # ✗
Icon.WARNING       # ⚠
Icon.INFO          # ℹ

# Progress icons
Icon.STAR          # ★
Icon.CIRCLE        # ●
Icon.DIAMOND       # ◆

# Music icons
Icon.MUSIC_NOTE    # ♪
Icon.MUSIC_NOTES   # ♫

# Box drawing
Icon.BOX_H         # ─
Icon.BOX_V         # │
Icon.BOX_TL        # ┌
Icon.BOX_BR        # ┘
```

## Status Messages

```python
# Success message (green)
print(success("All metadata enriched!"))

# Error message (red)
print(error("Failed to connect to API"))

# Warning message (yellow)
print(warning("Some fields were skipped"))

# Info message (cyan)
print(info("Processing 150 tracks"))
```

## Progress Bar

```python
prog = ProgressBar(total=100, label="Tracks", width=40)

# Update by 1
prog.update()

# Update by amount
prog.update(5)

# Set to specific value
prog.set(50)
```

Output:
```
Tracks              [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 50/100 ETA: 2s
```

## Interactive Menu

```python
# Selection menu
choice = Menu.select(
    "Which database to use?",
    ["Discogs", "Last.fm", "MusicBrainz"]
)
# Returns: 0, 1, or 2 (index of selected option)

# Confirmation prompt
if Menu.confirm("Continue with enrichment?"):
    print("Continuing...")

# Text input
name = Menu.input_text("Enter playlist name", default="My Playlist")
```

## Tables

```python
table = Table(["Field", "Source", "Value"], title="Enriched Metadata")
table.add_row("Genre", "Discogs", "Electronic")
table.add_row("Year", "MusicBrainz", "2020")
table.add_row("BPM", "AcousticBrainz", "128")
table.print()
```

Output:
```
Enriched Metadata

 Field  | Source         | Value
--------|----------------|----------
 Genre  | Discogs        | Electronic
 Year   | MusicBrainz    | 2020
 BPM    | AcousticBrainz | 128
```

## Boxes

```python
# Simple box
print(Box.simple("Content here", title="Header"))

# Section header
print(Box.section("Database Query Results", "Found 5 matches"))
```

## Statistics Display

```python
stats = {
    'Enriched': 45,
    'Skipped': 5,
    'Errors': 0
}
print(format_stats("Summary", stats))
```

Output:
```
Summary
  Enriched        45  ( 90.0%) ███████████████████████
  Skipped          5  ( 10.0%) ██
  Errors           0  (  0.0%)
```

## Headers and Footers

```python
# Fancy header
print_header("🎵 Metadata Enrichment", "Making your library complete")

# Do work...

# Fancy footer
print_footer()
```

## Disabling Colors

For non-TTY environments (logs, pipes), disable colors:

```python
Color.disable()
```

This sets all color codes to empty strings, so output is plain text.

## Usage in metadata_fill.py

The `metadata_fill.py` CLI now uses `cli_ui` for better UX:

```python
# Fancy header
print_header("🎵 Metadata Enrichment", "Making your library complete")

# Status messages
print(success("Playlist loaded"))
print(error("Database query failed"))

# Progress during processing
prog = ProgressBar(len(tracks), "Tracks")
for track in tracks:
    # process...
    prog.update()

# Summary stats
stats = {
    'Enriched': result['enriched'],
    'Skipped': result['skipped'],
    'Errors': result['errors'],
}
print(format_stats("Enrichment Summary", stats))

# Fancy footer
print_footer()
```

## Best Practices

1. **Use headers for major operations**: Mark the start of workflows with `print_header()`
2. **Use status messages consistently**: Help users understand what's happening
3. **Show progress for long operations**: Use `ProgressBar` for operations > 1 second
4. **Use tables for data display**: Present enriched metadata in organized tables
5. **End with footer**: Celebrate completion with `print_footer()`
6. **Disable colors for logs**: Call `Color.disable()` if output goes to files

## Testing

The `cli_ui` module is fully tested:

```bash
pytest tests/test_cli_ui.py -v
```

31 tests covering:
- Color codes and styling
- Icons and symbols
- Progress bars
- Status messages
- Tables
- Statistics formatting
- Color disabling

## Module Structure

- `Color` - ANSI color codes
- `Icon` - Unicode symbols
- `colorize()`, `bold()`, `dim()`, `underline()` - Text styling
- `success()`, `error()`, `warning()`, `info()` - Status messages
- `Box` - Box drawing utilities
- `ProgressBar` - Progress indicator with ETA
- `Spinner` - Animated loading spinner
- `Menu` - Interactive prompts
- `Table` - Data table formatting
- `format_stats()` - Statistics display
- `print_header()`, `print_footer()` - Decorative headers/footers

## Integration with metadata_fill

The metadata enrichment CLI (`metadata_fill.py`) uses `cli_ui` to provide:
1. Colorful header showing start of operation
2. Status messages during processing
3. Progress tracking for track processing
4. Final statistics summary with percentages
5. Celebratory footer on completion

---

**Last Updated**: January 4, 2026  
**Status**: Production Ready  
**Related**: [metadata_fill.py](/src/metadata_fill.py), [cli_ui.py](/src/cli_ui.py)
