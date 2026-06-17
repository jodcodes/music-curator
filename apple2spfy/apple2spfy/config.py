"""
Configuration management for Apple Music to Spotify playlist sync.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root is one level above this package directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Config:
    """Configuration class for the playlist sync application."""
    
    # Spotify API configuration
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    SPOTIFY_SCOPE = os.getenv("SPOTIFY_SCOPE", "playlist-modify-public playlist-modify-private")
    
    # Playlist configuration
    PLAYLIST_PREFIXES_TO_REMOVE = ["gC ", "gc ", "RGC "]
    
    # Logging configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # Cache TTL in days for playlist and track caches. Set to 0 to disable expiry
    CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "0"))
    
    # API Optimization settings
    ENABLE_BATCH_LOOKUP = os.getenv("ENABLE_BATCH_LOOKUP", "true").lower() == "true"
    TRACK_LOOKUP_DELAY = float(os.getenv("TRACK_LOOKUP_DELAY", "0.5"))
    
    # Transfer History settings
    ENABLE_TRANSFER_HISTORY = os.getenv("ENABLE_TRANSFER_HISTORY", "true").lower() == "true"
    TRANSFER_HISTORY_MAX_ENTRIES = int(os.getenv("TRANSFER_HISTORY_MAX_ENTRIES", "1000"))

    # Staleness: skip playlists synced more recently than this many days (0 = always sync)
    STALE_SYNC_DAYS = int(os.getenv("STALE_SYNC_DAYS", "7"))

    # Rate-limit handling: if Spotify asks us to wait longer than this (seconds),
    # save progress and exit instead of blocking.  Short waits are retried in place.
    # Default is 0 (always save-and-exit) since Spotify's quota reset is typically 24h.
    RATE_LIMIT_MAX_WAIT = int(os.getenv("RATE_LIMIT_MAX_WAIT", "0"))
    
    # SQLite Configuration
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH") or str(_PROJECT_ROOT / "data" / "apple2spfy.db")
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        required_vars = [
            "SPOTIFY_CLIENT_ID",
            "SPOTIFY_CLIENT_SECRET"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Check if AppleScript file exists
        apple_script_path = Path(cls.apple_script_path())
        if not apple_script_path.exists():
            raise FileNotFoundError(f"AppleScript file not found: {apple_script_path}")
        
        # Validate Spotify credentials format
        if len(cls.SPOTIFY_CLIENT_ID) != 32:
            raise ValueError("Spotify Client ID should be 32 characters long")
        
        if len(cls.SPOTIFY_CLIENT_SECRET) != 32:
            raise ValueError("Spotify Client Secret should be 32 characters long")
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if cls.LOG_LEVEL.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {cls.LOG_LEVEL}. Must be one of: {', '.join(valid_log_levels)}")
    
    @classmethod
    def get_cache_dir(cls):
        """Get the cache directory path."""
        cache_dir = os.path.expanduser("~/.spotify_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    @classmethod
    def get_spotify_config(cls):
        """Get Spotify configuration as a dictionary."""
        return {
            "client_id": cls.SPOTIFY_CLIENT_ID,
            "client_secret": cls.SPOTIFY_CLIENT_SECRET,
            "redirect_uri": cls.SPOTIFY_REDIRECT_URI,
            "scope": cls.SPOTIFY_SCOPE
        }

    @classmethod
    def apple_script_path(cls) -> str:
        """
        Resolve the AppleScript path so it always follows the Python files,
        falling back to an environment override only when it points to an
        existing file.
        """
        script_dir = _PROJECT_ROOT
        default_path = script_dir / "get_playlist.scpt"
        
        env_path = os.getenv("APPLE_SCRIPT_PATH")
        if env_path:
            candidate = Path(env_path).expanduser()
            if candidate.exists():
                return str(candidate)
        
        return str(default_path)

    @classmethod
    def track_cache_path(cls) -> str:
        """
        Resolve the location for the persistent track lookup cache file.
        Defaults to the project directory but allows overriding via env.
        """
        env_path = os.getenv("TRACK_CACHE_PATH")
        if env_path:
            return str(Path(env_path).expanduser())
        
        script_dir = _PROJECT_ROOT
        return str(script_dir / "track_cache.json")
    
    @classmethod
    def transfer_history_path(cls) -> str:
        """
        Resolve the location for the transfer history file.
        Defaults to the cache directory.
        """
        env_path = os.getenv("TRANSFER_HISTORY_PATH")
        if env_path:
            return str(Path(env_path).expanduser())
        
        cache_dir = Path(cls.get_cache_dir())
        return str(cache_dir / "transfer_history.json")

    @classmethod
    def sync_state_path(cls) -> str:
        """
        Resolve the location for the sync state file (for resume capability).
        Defaults to the cache directory.
        """
        env_path = os.getenv("SYNC_STATE_PATH")
        if env_path:
            return str(Path(env_path).expanduser())
        
        cache_dir = Path(cls.get_cache_dir())
        return str(cache_dir / "sync_state.json")
