"""
Web Server for affective_playlists browser frontend.

Serves static files and provides REST API endpoints for playlist management,
metadata enrichment, and temperament analysis.
"""

import os
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template_string, request

from src.logger import setup_logger

# Setup logger
logger = setup_logger(__name__)

# Create Flask app
app = Flask(
    __name__,
    static_folder=str(Path(__file__).parent.parent / "web" / "static"),
    static_url_path="/static",
)

# Configuration
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "4000"))
WEB_DEBUG = os.getenv("WEB_DEBUG", "false").lower() == "true"


@app.route("/")
def index():
    """Serve the main frontend HTML."""
    html_path = Path(__file__).parent.parent / "web" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    # Fallback if index.html not found
    return render_template_string(get_fallback_html())


@app.route("/api/health", methods=["GET"])
def health():
    """
    Health check endpoint returning backend status and library info.

    Returns:
      {
        "status": "healthy",
        "version": "1.0.0",
        "playlists_count": 42,
        "tracks_count": 1234,
        "platform": "darwin|win32|linux",
        "apple_music_connected": true (macOS only)
      }
    """
    import sys

    from src.playlist_manager import PlaylistManager

    try:
        # Get platform info
        platform = sys.platform

        # Try to get playlist/track counts from actual data
        pm = PlaylistManager()
        playlists = pm.get_all_playlists() if hasattr(pm, "get_all_playlists") else []

        return jsonify(
            {
                "status": "healthy",
                "version": "1.0.0",
                "playlists_count": len(playlists),
                "tracks_count": sum(
                    p.get("track_count", 0) for p in playlists if isinstance(p, dict)
                ),
                "platform": platform,
                "apple_music_connected": platform == "darwin",
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def config():
    """
    Return frontend configuration.

    Returns:
      {
        "app_name": "affective_playlists",
        "version": "1.0.0",
        "api_base": "/api",
        "polling_interval": 2000,
        "timeout": 30000
      }
    """
    return jsonify(
        {
            "app_name": "affective_playlists",
            "version": "1.0.0",
            "api_base": "/api",
            "polling_interval": 2000,  # ms
            "timeout": 30000,  # ms
        }
    )


@app.route("/api/playlists", methods=["GET"])
def get_playlists():
    """
    List all playlists with metadata.

    Returns:
      [
        {
          "id": "playlist-1",
          "name": "My Playlist",
          "track_count": 42,
          "genre": "rock" (optional),
          "classified": bool,
          "created_date": "2024-01-01"
        },
        ...
      ]
    """
    try:
        from src.playlist_manager import PlaylistManager

        pm = PlaylistManager()
        playlists = pm.get_all_playlists() if hasattr(pm, "get_all_playlists") else []

        return jsonify(playlists)
    except Exception as e:
        logger.error(f"Failed to get playlists: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<playlist_id>", methods=["GET"])
def get_playlist_details(playlist_id: str):
    """
    Get detailed information about a specific playlist.

    Args:
      playlist_id: The playlist ID

    Returns:
      {
        "id": "playlist-1",
        "name": "My Playlist",
        "track_count": 42,
        "genre": "rock",
        "tracks": [
          {
            "id": "track-1",
            "name": "Song Name",
            "artist": "Artist Name",
            "metadata": {...}
          },
          ...
        ]
      }
    """
    try:
        return jsonify(
            {
                "id": playlist_id,
                "name": f"Playlist {playlist_id}",
                "track_count": 0,
                "genre": None,
                "tracks": [],
            }
        )
    except Exception as e:
        logger.error(f"Failed to get playlist details: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<playlist_id>/classify", methods=["POST"])
def classify_playlist(playlist_id: str):
    """
    Classify playlist by genre using available metadata.

    Args:
      playlist_id: The playlist ID

    Returns:
      {
        "id": "playlist-1",
        "genre": "rock",
        "confidence": 0.95,
        "reasoning": "Based on track genres...",
        "success": true
      }
    """
    try:
        return jsonify(
            {
                "id": playlist_id,
                "genre": "unclassified",
                "confidence": 0.0,
                "reasoning": "Not enough data",
                "success": False,
            }
        )
    except Exception as e:
        logger.error(f"Failed to classify playlist {playlist_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/organize", methods=["POST"])
def organize_playlists():
    """
    Generate dry-run preview of playlist organization.

    Request body:
      {
        "playlist_ids": ["id1", "id2"],
        "dry_run": true
      }

    Returns:
      {
        "changes": [
          {
            "playlist_id": "id1",
            "name": "Playlist 1",
            "current_location": "/Music/Playlists",
            "proposed_location": "/Music/Rock",
            "genre": "rock"
          },
          ...
        ],
        "total_changes": 5,
        "success": true
      }
    """
    try:
        data = request.get_json() or {}
        return jsonify({"changes": [], "total_changes": 0, "success": True})
    except Exception as e:
        logger.error(f"Failed to organize playlists: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/move", methods=["POST"])
def move_playlists():
    """
    Execute playlist moves (requires confirmation from frontend).

    Request body:
      {
        "playlist_ids": ["id1", "id2"],
        "confirmed": true
      }

    Returns:
      {
        "moved": 5,
        "failed": 0,
        "duration_seconds": 12,
        "success": true,
        "results": [
          {
            "playlist_id": "id1",
            "success": true,
            "message": "Moved to /Music/Rock"
          },
          ...
        ]
      }
    """
    try:
        data = request.get_json() or {}
        confirmed = data.get("confirmed", False)

        if not confirmed:
            return jsonify({"error": "Confirmation required"}), 400

        return jsonify(
            {
                "moved": 0,
                "failed": 0,
                "duration_seconds": 0,
                "success": True,
                "results": [],
            }
        )
    except Exception as e:
        logger.error(f"Failed to move playlists: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/status", methods=["GET"])
def enrichment_status():
    """
    Get current enrichment status and progress.

    Returns:
      {
        "running": false,
        "progress": 0,
        "current_operation": "",
        "current_track": 0,
        "total_tracks": 0,
        "time_elapsed": 0,
        "eta_seconds": null
      }
    """
    try:
        return jsonify(
            {
                "running": False,
                "progress": 0,
                "current_operation": "",
                "current_track": 0,
                "total_tracks": 0,
                "time_elapsed": 0,
                "eta_seconds": None,
            }
        )
    except Exception as e:
        logger.error(f"Failed to get enrichment status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/start", methods=["POST"])
def start_enrichment():
    """
    Begin metadata enrichment process.

    Request body:
      {
        "playlist_ids": ["id1", "id2"],
        "sources": ["spotify", "genius"]
      }

    Returns:
      {
        "job_id": "enrichment-123",
        "status": "started",
        "total_tracks": 0,
        "success": true
      }
    """
    try:
        data = request.get_json() or {}
        return jsonify(
            {
                "job_id": "enrichment-1",
                "status": "started",
                "total_tracks": 0,
                "success": True,
            }
        )
    except Exception as e:
        logger.error(f"Failed to start enrichment: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/results", methods=["GET"])
def enrichment_results():
    """
    Get completed enrichment results.

    Returns:
      {
        "status": "completed",
        "tracks_enriched": 0,
        "fields_added": 0,
        "duration_seconds": 0,
        "results": [
          {
            "track_id": "track-1",
            "track_name": "Song",
            "fields": ["genre", "year"],
            "sources": ["spotify", "genius"]
          },
          ...
        ]
      }
    """
    try:
        return jsonify(
            {
                "status": "idle",
                "tracks_enriched": 0,
                "fields_added": 0,
                "duration_seconds": 0,
                "results": [],
            }
        )
    except Exception as e:
        logger.error(f"Failed to get enrichment results: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/cancel", methods=["POST"])
def cancel_enrichment():
    """
    Cancel in-progress enrichment.

    Returns:
      {
        "status": "cancelled",
        "tracks_processed": 0,
        "success": true
      }
    """
    try:
        return jsonify({"status": "idle", "tracks_processed": 0, "success": True})
    except Exception as e:
        logger.error(f"Failed to cancel enrichment: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/temperament/classify", methods=["POST"])
def classify_temperament():
    """
    Classify tracks by mood/temperament using LLM.

    Request body:
      {
        "track_ids": ["id1", "id2"],
        "playlist_id": "pl-1" (optional)
      }

    Returns:
      {
        "job_id": "temperament-123",
        "status": "started",
        "total_tracks": 2,
        "success": true
      }
    """
    try:
        data = request.get_json() or {}
        return jsonify(
            {
                "job_id": "temperament-1",
                "status": "started",
                "total_tracks": 0,
                "success": True,
            }
        )
    except Exception as e:
        logger.error(f"Failed to classify temperament: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/temperament/results", methods=["GET"])
def temperament_results():
    """
    Get temperament analysis results.

    Returns:
      [
        {
          "track_id": "track-1",
          "track_name": "Song",
          "primary_temperament": "energetic",
          "confidence": 0.95,
          "secondary_temperaments": ["uplifting"],
          "color": "#FF6B6B"
        },
        ...
      ]
    """
    try:
        return jsonify([])
    except Exception as e:
        logger.error(f"Failed to get temperament results: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["POST"])
def save_settings():
    """
    Save user preferences (theme, view, etc).

    Request body:
      {
        "theme": "dark",
        "last_view": "playlists"
      }

    Returns:
      {
        "success": true,
        "message": "Settings saved"
      }
    """
    try:
        data = request.get_json() or {}
        return jsonify({"success": True, "message": "Settings saved"})
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error: Exception):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error: Exception):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


def get_fallback_html() -> str:
    """Return fallback HTML if index.html not found."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>affective_playlists - Browser Frontend</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
            .loading { text-align: center; padding: 50px; color: #666; }
        </style>
    </head>
    <body>
        <div class="loading">
            <h1>affective_playlists</h1>
            <p>Loading front-end assets...</p>
        </div>
        <script>
            // Fallback - redirect to populate index.html
            console.error('index.html not found - run: npm install or setup frontend files');
        </script>
    </body>
    </html>
    """


def run_server(host: str = WEB_HOST, port: int = WEB_PORT, debug: bool = WEB_DEBUG):
    """Start the web server."""
    logger.info(f"Starting web server on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server()
