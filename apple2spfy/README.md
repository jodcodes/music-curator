# Apple Music to Spotify Playlist Sync

Part of the top-level `music-curator` repo. Keep this tool focused on Apple Music → Spotify sync/export. Do not depend on `affective_playlists` unless there is a concrete shared behavior worth extracting.

A Python tool that synchronizes playlists from Apple Music to Spotify using AppleScript and the Spotify Web API.

## Features

- 🎵 **Automatic Playlist Sync**: Syncs all your Apple Music playlists to Spotify
- 🧹 **Clean Sync**: Removes tracks from Spotify that are no longer in Apple Music
- 🔍 **Smart Track Matching**: Finds corresponding tracks on Spotify using title and artist
- 🚀 **API Optimization**: Batch track lookup with deduplication to minimize API calls
- 📊 **Transfer History**: Tracks when playlists were successfully synced with timestamps
- 💾 **Intelligent Caching**: Persistent caching for tracks and playlists to reduce API usage
- 📝 **Comprehensive Logging**: Detailed logs for monitoring sync progress
- ⚙️ **Configurable**: Easy configuration via environment variables
- 🛡️ **Error Handling**: Robust error handling and recovery

## Prerequisites

- macOS (required for AppleScript integration)
- Python 3.7+
- Apple Music with playlists
- Spotify account
- Spotify Developer App (for API access)

## Installation

### Quick Install (Recommended)

The install script will guide you through setup and optionally create a virtual environment:

```bash
git clone https://github.com/jodcodes/apple2spfy.git
cd apple2spfy
./scripts/install.sh
```

The installer will:
- Check Python and pip installation
- Offer to create a virtual environment (recommended)
- Install all dependencies
- Create necessary directories
- Set up configuration template

### Manual Installation

1. **Clone or download this repository**
   ```bash
   git clone https://github.com/jodcodes/apple2spfy.git
   cd apple2spfy
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Spotify Developer App**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Note down your `Client ID` and `Client Secret`
   - Add `http://localhost:8888/callback` as a redirect URI

5. **Configure environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your Spotify credentials
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project directory with the following variables:

```env
# Required: Spotify API credentials
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here

# Optional: Custom settings
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
SPOTIFY_SCOPE=playlist-modify-public playlist-modify-private
APPLE_SCRIPT_PATH=./get_playlist.scpt
LOG_LEVEL=INFO

# API Optimization (default values shown)
ENABLE_BATCH_LOOKUP=true        # Deduplicate tracks across playlists
TRACK_LOOKUP_DELAY=0.1          # Delay between API calls in seconds

# Transfer History (default values shown)
ENABLE_TRANSFER_HISTORY=true    # Track successful playlist transfers
TRANSFER_HISTORY_MAX_ENTRIES=1000  # Maximum history entries to keep

# Cache Settings
CACHE_TTL_DAYS=0                # Cache expiry in days (0 = never expire)
```

### AppleScript Setup

You need an AppleScript file that exports your Apple Music playlists. The script should output playlists in this format:

```
###Playlist Name###
Song Title 1|Artist Name 1
Song Title 2|Artist Name 2
###Another Playlist###
Song Title 3|Artist Name 3
```
A template called `get_playlist.scpt.template` is in the repo — copy it to `get_playlist.scpt` and fill in your playlist names.

## Usage

### Basic Usage

```bash
python sync_playlists.py
```

### Clean Sync (Recommended)

Remove tracks from Spotify that are no longer in Apple Music:

```bash
python sync_playlists.py --clean-sync
```

### API Optimization

The tool automatically optimizes API usage through:

**Batch Track Lookup**: Deduplicates tracks across all playlists before searching, reducing redundant API calls by ~50% on first run.

**Intelligent Caching**: Stores track lookups and playlist metadata in `~/.spotify_cache/` for subsequent runs, reducing API calls by ~90%.

**Smart Playlist Comparison**: Skips syncing playlists that haven't changed (using Spotify's snapshot IDs).

To disable batch lookup (not recommended):
```bash
# In .env file:
ENABLE_BATCH_LOOKUP=false
```

### Transfer History

The tool automatically tracks when playlists are successfully synced:

```bash
# View complete transfer history
python sync_playlists.py --show-history

# View history for a specific playlist
python sync_playlists.py --playlist-history "My Playlist"

# Clear transfer history
python sync_playlists.py --clear-history
```

History is stored in `~/.spotify_cache/transfer_history.json` and includes:
- Timestamp of each transfer
- Tracks added/removed
- Total track count
- Playlist name and Spotify ID

### Force Sync / Cache Behavior

Bypass the cache and force a full sync:

```bash
python sync_playlists.py --force-sync
```

### Clearing Caches

```bash
# Clear caches and continue
python sync_playlists.py --clear-cache

# Clear caches and exit only
python sync_playlists.py --clear-cache-only
```

### Dry Run (Preview)

Simulate a sync without making any changes to Spotify:

```bash
python sync_playlists.py --dry-run
```

### Cache TTL

Control cache expiry via the `.env` file:

```env
CACHE_TTL_DAYS=0  # Never expire (default)
CACHE_TTL_DAYS=30 # Expire after 30 days
```

### Automatic Sync on Drive Connection

Set up automatic sync that runs **once** when you connect a specific external drive. Perfect for backing up your library to an external SSD or triggering syncs when you arrive at a location.

#### Quick Setup

```bash
./scripts/setup_drive_sync.sh
# Enter your drive name when prompted (e.g., "2TB_SSD")
```

#### How It Works

The setup creates:
1. **macOS Launch Agent** - Monitors `/Volumes` for drive connections
2. **Auto-sync wrapper script** - Checks for your specific drive and runs sync
3. **Marker file** - Created on the drive after successful sync (`.apple2spfy_synced`)
4. **Automatic reset** - Marker is removed when you eject the drive

**Behavior:**
- ✅ Sync runs automatically when drive is connected
- ✅ Only runs once per connection (marker prevents repeats)
- ✅ Disconnecting the drive removes the marker
- ✅ Next connection triggers a fresh sync
- ✅ Works with virtual environments and conda

#### Monitoring & Management

```bash
# View sync logs in real-time
tail -f /tmp/apple2spfy_drive.log

# Check if service is running
launchctl list | grep apple2spfy

# Disable auto-sync
launchctl unload ~/Library/LaunchAgents/com.user.apple2spfy.drive.plist

# Re-enable auto-sync
launchctl load ~/Library/LaunchAgents/com.user.apple2spfy.drive.plist
```

**Need more help?** Check the troubleshooting section below or review the setup script comments.

### Programmatic Usage

```python
from sync_playlists import PlaylistSync

# Create sync instance
sync = PlaylistSync()

# Sync all playlists with clean sync enabled
stats = sync.sync_all_playlists(clean_sync=True)

# Print results
for playlist_name, data in stats.items():
    print(f"{playlist_name}: +{data['tracks_added']} -{data['tracks_removed']}")
```

## How It Works

1. **Apple Music Extraction**: Uses AppleScript to extract playlist data from Apple Music
2. **Batch Track Lookup** (NEW): Deduplicates tracks across all playlists before searching
3. **Track Matching**: Searches Spotify for each track using title and artist with intelligent caching
4. **Playlist Management**: Creates or updates Spotify playlists
5. **Clean Sync**: Removes tracks from Spotify that are no longer in Apple Music
6. **Transfer History** (NEW): Records successful syncs with timestamps
7. **Logging**: Provides detailed logs of the entire process

## Performance Improvements

The tool includes optimizations that significantly reduce Spotify API usage:

### API Call Reduction

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| First sync (3 playlists, 130 unique tracks) | ~150 API calls | ~65 API calls | **~57% reduction** |
| Second sync (no changes) | ~150 API calls | ~15 API calls | **~90% reduction** |
| Lookup delay per track | 0.2s | 0.1s (configurable) | **50% faster** |

### Optimization Features

1. **Batch Track Lookup**: Deduplicates tracks across all playlists before searching
2. **Persistent Caching**: Stores track IDs and playlist metadata between runs
3. **Snapshot Comparison**: Skips unchanged playlists entirely
4. **Optimized Search**: Uses multiple search strategies with early termination

### Expected Performance

For a typical setup with 10 playlists and 500 total tracks (300 unique):

- **First Run**: ~5-10 minutes (with API delays)
- **Subsequent Runs**: ~30-60 seconds (mostly cached)
- **API Calls Saved**: ~70% reduction on first run, ~95% on subsequent runs


## Project Structure

```
syncAppleSpotifyPlaylists/
├── sync_playlists.py      # Main sync script
├── config.py              # Configuration management
├── logger.py              # Logging setup
├── requirements.txt       # Python dependencies
├── env.example           # Environment variables template
└── README.md             # This file
```

## Classes and Components

### `PlaylistSync`
Main orchestrator class that coordinates the sync process.

### `AppleMusicExtractor`
Handles extraction of playlist data from Apple Music via AppleScript.

### `SpotifyManager`
Manages all Spotify API operations including authentication, playlist creation, and track management.

### `Config`
Configuration management with validation and environment variable handling.

## Error Handling

The tool includes comprehensive error handling:

- **Configuration Validation**: Checks for required environment variables and files
- **API Error Recovery**: Handles Spotify API rate limits and errors
- **Track Matching Failures**: Logs tracks that couldn't be found on Spotify
- **Playlist Sync Errors**: Continues syncing other playlists if one fails

## Logging

The tool provides detailed logging at multiple levels:

- **INFO**: General progress and successful operations
- **WARNING**: Non-critical issues (e.g., tracks not found)
- **ERROR**: Critical errors that prevent operation
- **DEBUG**: Detailed debugging information

## Troubleshooting

### Common Issues

1. **"AppleScript file not found"**
   - Verify the `APPLE_SCRIPT_PATH` in your `.env` file
   - Ensure the AppleScript file exists and is executable

2. **"Spotify authentication failed"**
   - Check your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`
   - Verify your redirect URI matches the one in your Spotify app

3. **"Tracks not found on Spotify"**
   - This is normal for some tracks due to different catalogs
   - Check the logs for specific tracks that couldn't be matched

4. **Permission errors**
   - Ensure your Spotify app has the correct scopes
   - Re-authenticate if needed

### Debug Mode

Enable debug logging for more detailed information:

```env
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Spotipy](https://github.com/plamere/spotipy) for Spotify API integration
- [python-dotenv](https://github.com/theskumar/python-dotenv) for environment variable management
