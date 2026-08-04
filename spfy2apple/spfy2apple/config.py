"""
Configuration for Spotify → Apple Music playlist sync.

Reuses the same Spotify credentials as apple2spfy (from .env).
Uses a separate token cache so the broader read scope doesn't
invalidate the existing apple2spfy token.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env from multiple candidate locations — the credentials
# live in apple2spfy/.env (shared with apple2spfy) or the repo root .env.
for _env_path in [
    _PROJECT_ROOT / "apple2spfy" / ".env",
    _PROJECT_ROOT / ".env",
]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


class Config:
    # Spotify API (shared with apple2spfy — same .env vars)
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    # We need read scopes in addition to modify scopes
    SPOTIFY_SCOPE = os.getenv(
        "SPFY2APPLE_SPOTIFY_SCOPE",
        "playlist-modify-public playlist-modify-private "
        "playlist-read-private playlist-read-collaborative",
    )

    # Apple Music target folder
    FOLDER_NAME = os.getenv("SPFY2APPLE_FOLDER_NAME", "curated by others")

    # Search delay between Apple Music library searches (seconds)
    SEARCH_DELAY = float(os.getenv("SPFY2APPLE_SEARCH_DELAY", "0.3"))

    # Max tracks to add in a single AppleScript batch
    BATCH_ADD_SIZE = int(os.getenv("SPFY2APPLE_BATCH_ADD_SIZE", "50"))

    # Max search results to examine per track
    MAX_SEARCH_RESULTS = int(os.getenv("SPFY2APPLE_MAX_SEARCH_RESULTS", "20"))

    # Number of parallel AppleScript search workers (each spawns an osascript process)
    SEARCH_WORKERS = int(os.getenv("SPFY2APPLE_SEARCH_WORKERS", "4"))

    # State file for tracking synced playlists (snapshot IDs, last sync time)
    STATE_PATH = os.getenv(
        "SPFY2APPLE_STATE_PATH",
        str(_PROJECT_ROOT / "spfy2apple" / "data" / "sync_state.json"),
    )

    # Playlist filter: only sync Spotify playlists listed in this file.
    # One playlist name per line; lines starting with # are comments.
    # If the file doesn't exist or is empty, all followed playlists are synced.
    PLAYLIST_FILTER_PATH = os.getenv(
        "SPFY2APPLE_PLAYLIST_FILTER",
        str(_PROJECT_ROOT / "spfy2apple" / "playlist_filter.txt"),
    )

    @classmethod
    def validate(cls):
        missing = []
        if not cls.SPOTIFY_CLIENT_ID:
            missing.append("SPOTIFY_CLIENT_ID")
        if not cls.SPOTIFY_CLIENT_SECRET:
            missing.append("SPOTIFY_CLIENT_SECRET")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in your Spotify credentials."
            )

    @classmethod
    def get_spotify_config(cls):
        return {
            "client_id": cls.SPOTIFY_CLIENT_ID,
            "client_secret": cls.SPOTIFY_CLIENT_SECRET,
            "redirect_uri": cls.SPOTIFY_REDIRECT_URI,
            "scope": cls.SPOTIFY_SCOPE,
        }

    @classmethod
    def token_cache_path(cls) -> str:
        cache_dir = os.path.expanduser("~/.spotify_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, ".spfy2apple_token_cache")
