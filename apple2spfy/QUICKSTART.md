# 🚀 Apple2Spfy - Quick Start Guide

## Installation

### 1. Clone and Install

```bash
git clone https://github.com/jodcodes/apple2spfy.git
cd apple2spfy
./scripts/install.sh
```

The installer will:
- Check Python and pip
- Offer to create a virtual environment (recommended)
- Install all dependencies
- Set up configuration template

### 2. Configure Credentials

```bash
cp env.example .env
# Edit .env with your Spotify API credentials
```

Get your Spotify credentials from: https://developer.spotify.com/dashboard

### 3. Set Up AppleScript

Copy `get_playlist.scpt.template` to `get_playlist.scpt` and fill in your playlist names.

## Usage

### Basic Sync

```bash
# Activate virtual environment if you created one
source venv/bin/activate

# Run sync with clean mode (recommended)
python sync_playlists.py --clean-sync
```

### Auto-Sync on Drive Connection

Perfect for triggering syncs when you connect an external drive:

```bash
./scripts/setup_drive_sync.sh
# Enter your drive name when prompted (e.g., "2TB_SSD")
```

**Monitor sync logs:**
```bash
tail -f /tmp/apple2spfy_drive.log
```

**Manage auto-sync:**
```bash
# Disable
launchctl unload ~/Library/LaunchAgents/com.user.apple2spfy.drive.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.user.apple2spfy.drive.plist
```

### View Transfer History

```bash
# Show all sync history
python sync_playlists.py --show-history

# Show history for specific playlist
python sync_playlists.py --playlist-history "My Playlist"
```

## Features

✅ **API Optimization** - 50-90% fewer API calls with intelligent caching
✅ **Transfer History** - Track all successful syncs with timestamps
✅ **Drive-Triggered Sync** - Automatic sync when drive connects
✅ **Virtual Environment** - Isolated Python dependencies
✅ **Clean Sync** - Remove tracks no longer in Apple Music

## Documentation

- **Full Documentation**: [README.md](README.md)
- **Configuration**: See `.env` file

## Troubleshooting

**Sync not running?**
```bash
# Check if service is loaded
launchctl list | grep apple2spfy

# Check logs
tail -f /tmp/apple2spfy_drive.log
```

**Python issues?**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Verify dependencies
pip list | grep spotipy
```

For more help, see the full [README.md](README.md).

