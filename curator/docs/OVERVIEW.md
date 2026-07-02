# affective_playlists - Project Documentation

## Quick Summary

**affective_playlists** is a unified Python CLI application for advanced music library management and analysis. It combines three powerful tools into a single, cohesive platform for Apple Music users.

## What This Project Does

### Three Core Features

#### 1. 🎵 Temperament Analysis (4tempers)
Uses AI (OpenAI GPT) to classify playlists into four emotional temperaments:
- **Woe**: Sad, melancholic, introspective music
- **Frolic**: Happy, upbeat, energetic music
- **Dread**: Dark, ominous, intense music
- **Malice**: Aggressive, hostile, chaotic music

#### 2. 📝 Metadata Enrichment (metad_enr)
Automatically fills missing music metadata by querying multiple sources:
- Retrieves BPM (Beats Per Minute)
- Identifies and sets genre
- Adds release year information
- Integrates data from MusicBrainz, Spotify, Last.fm

#### 3. 📁 Playlist Organization (plsort)
Organizes playlists by genre classification:
- Analyzes playlist contents
- Assigns genre categories (Hip-Hop, Electronic, Jazz, etc.)
- Organizes playlists for better library structure
- Supports dry-run mode for preview

## Architecture Overview

```
┌─────────────────────────────────────────┐
│          main.py (CLI Entry)            │
└────────────┬────────────────────────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐
│4temp │ │metad │ │plsort│
│ers   │ │_enr  │ │      │
└──────┘ └──────┘ └──────┘
    │        │        │
    └────────┼────────┘
             │
    ┌────────▼────────┐
    │ Shared Services │
    ├─────────────────┤
    │ Apple Music API │
    │ Config Manager  │
    │ Logger          │
    │ Normalizer      │
    └─────────────────┘
```

## Project Structure

```
affective_playlists/
├── main.py                      # Unified CLI entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
│
├── src/                         # All application code
│   ├── temperament_analyzer.py  # 4tempers: AI analysis
│   ├── metadata_fill.py         # metad_enr: Metadata enrichment
│   ├── plsort.py               # plsort: Organization
│   ├── apple_music.py          # Apple Music interface
│   ├── config.py               # Configuration management
│   ├── logger.py               # Logging utilities
│   ├── normalizer.py           # Text normalization
│   ├── databases.py            # Database queries
│   ├── metadata_*.py           # Metadata-related modules
│   └── scripts/                # AppleScript automation
│
├── data/                        # Data and configuration
│   ├── config/                 # Configuration files
│   │   ├── whitelist.json      # Playlist whitelist
│   │   └── *.json              # Other configs
│   ├── artist_lists/           # Genre artist lists
│   ├── logs/                   # Application logs
│   └── cache/                  # Cached data
│
├── tests/                       # Test suite
│
└── docs/                        # Project documentation
    ├── OVERVIEW.md             # This file
    ├── rules/                  # Documentation rules
    │   ├── DOCUMENTATION_STANDARDS.md
    │   └── TEST_ORGANIZATION_RULE.md
    ├── requirements/           # Functional specs & technical requirements
    │   ├── SPEC_TEMPERAMENT_ANALYZER.md
    │   ├── SPEC_METADATA_ENRICHMENT.md
    │   ├── SPEC_PLAYLIST_ORGANIZATION.md
    │   └── TECH_REQ_SYSTEM_ARCHITECTURE.md
    └── summary/                # Reports and summaries
        ├── IMPLEMENTATION_REPORTS/
        ├── PROJECT_SUMMARIES/
        └── QUICK_REFERENCE/
```

## How to Use

### Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure (copy template and edit)
cp .env.example .env
vim .env

# 3. Run the unified CLI
python main.py
```

### Run Specific Feature
```bash
python main.py temperament    # Run temperament analysis
python main.py enrich         # Run metadata enrichment
python main.py organize       # Run playlist organization
```

### Interactive Menu (Default)
```bash
python main.py                # Shows menu to select feature
```

## Documentation Structure

### Rules
- **DOCUMENTATION_STANDARDS.md** - Guidelines for creating specs

### Functional Specifications
- **SPEC_TEMPERAMENT_ANALYZER.md** - 4tempers feature requirements
- **SPEC_METADATA_ENRICHMENT.md** - metad_enr feature requirements
- **SPEC_PLAYLIST_ORGANIZATION.md** - plsort feature requirements

### Technical Requirements
- **TECH_REQ_SYSTEM_ARCHITECTURE.md** - System design and integration

## Key Components

### Entry Point: main.py
- Unified CLI dispatcher
- Routes to appropriate feature
- Handles interactive menu
- Manages error handling

### Source Code: src/
- **temperament_analyzer.py** - OpenAI GPT integration for emotion classification
- **metadata_fill.py** - Multi-source metadata enrichment
- **plsort.py** - Genre-based playlist organization
- **apple_music.py** - Apple Music AppleScript wrapper
- **config.py** - Centralized configuration management
- **logger.py** - Unified logging system
- Supporting modules for metadata, databases, and utilities

### Configuration: data/
- Whitelist configuration for controlled processing
- Artist lists for genre matching
- Log files for operation tracking
- Cache for metadata optimization

## Key Features

✅ **Unified Interface** - One command for all three tools
✅ **AI-Powered** - Uses OpenAI GPT for intelligent analysis
✅ **Multi-Source Data** - Queries MusicBrainz, Spotify, Last.fm
✅ **Safety Features** - Dry-run mode, whitelist control, confirmations
✅ **Comprehensive Logging** - Track all operations and errors
✅ **Configuration Management** - Centralized `.env` and JSON configs
✅ **Interactive Mode** - Menu-driven interface for ease of use
✅ **Batch Processing** - Handle entire playlists/library

## Configuration

### Environment Variables (.env)
```bash
OPENAI_API_KEY=sk-...              # Required for 4tempers
SPOTIFY_CLIENT_ID=...              # Optional for better metadata
SPOTIFY_CLIENT_SECRET=...          # Optional for better metadata
LASTFM_API_KEY=...                 # Optional for better metadata
```

### Playlist Whitelist (data/config/whitelist.json)
```json
{
  "enabled": false,
  "playlists": [
    "Playlist 1",
    "Playlist 2"
  ]
}
```
- `enabled: false` - Process all playlists
- `enabled: true` - Process only listed playlists

## Technology Stack

- **Language**: Python 3.8+
- **APIs**: OpenAI, Spotify, MusicBrainz, Last.fm
- **Local Integration**: macOS Music.app via AppleScript
- **Key Libraries**: openai, spotipy, musicbrainzngs, pylast

## Getting Help

- **Quick Start**: See QUICKSTART.md
- **Main README**: See README.md
- **Feature Specs**: See docs/requirements/ folder
- **System Design**: See TECH_REQ_SYSTEM_ARCHITECTURE.md
- **Testing Guide**: See docs/summary/QUICK_REFERENCE/TESTING_QUICK_REFERENCE.md

## Support

For issues or questions:
1. Check the documentation in docs/requirements/
2. Review log files in data/logs/ or temperament_analyzer.log
3. Verify .env configuration
4. Check whitelist.json if using whitelist mode

---

**Made with ❤️ for Apple Music lovers**
