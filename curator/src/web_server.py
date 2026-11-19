"""
Web Server for curator browser frontend.

Serves static files and provides REST API endpoints for playlist management,
metadata enrichment, and temperament analysis.

Implementation note: This follows the browser-frontend specification:
- openspec/specs/browser-frontend/spec.md

State management:
- Enrichment and temperament operations use task queue (Celery)
- Job state persisted to database via SQLAlchemy ORM
- Real-time updates via WebSocket (fallback: HTTP polling)
"""

from collections import OrderedDict
from copy import deepcopy
import json
import re
import secrets
from threading import Lock
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, g, jsonify, render_template_string, request, session
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from src.web_access import bounded_request_body, install_web_access, load_access_settings

# Fail closed before service imports, logger setup, DB or Music startup work.
_access_settings = load_access_settings()

from src.db import setup_database
from src.job_store import get_job_store
from src.logger import setup_logger
from src.library_state_store import LibraryStateStore
from src.rate_limiter import check_job_quota, rate_limit
from src.realtime import get_realtime_manager, simulate_sse_stream

# Try to import Celery tasks
try:
    from src.tasks import analyze_mood, apply_curation, enrich_metadata

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

# Setup logger
logger = setup_logger(__name__)

# Create Flask app
app = Flask(
    __name__,
    static_folder=str(Path(__file__).parent.parent / "web" / "static"),
    static_url_path="/static",
)

# Register the access guard before all other before_request hooks.
install_web_access(app, _access_settings)
WEB_HOST = _access_settings.host
WEB_PORT = _access_settings.port
WEB_DEBUG = False

# In-memory state for background operations
# In production, use a proper job queue and database
_enrichment_state: Dict[str, Any] = {
    "running": False,
    "progress": 0,
    "current_operation": "",
    "current_track": 0,
    "total_tracks": 0,
    "start_time": 0,
    "job_id": None,
}

_CURATION_SMOKE_TOKEN_TTL_SECONDS = 10 * 60
_curation_smoke_tokens: Dict[str, Dict[str, Any]] = {}

_temperament_state: Dict[str, Any] = {
    "running": False,
    "progress": 0,
    "current_operation": "",
    "start_time": 0,
    "job_id": None,
}

_enrichment_results: Dict[str, Any] = {
    "status": "idle",
    "tracks_enriched": 0,
    "fields_added": 0,
    "duration_seconds": 0,
    "results": [],
}

_temperament_results: List[Dict[str, Any]] = []

# Cached playlists and settings
_playlists_cache: List[Dict[str, Any]] = []
_user_settings: Dict[str, Any] = {}
_db_session = None  # DB session for playlist cache


def _get_playlist_manager():
    """Initialize and return playlist manager."""
    try:
        from src.playlist_manager import PlaylistManager

        return PlaylistManager()
    except Exception as e:
        logger.warning(f"Failed to initialize PlaylistManager: {e}")
        return None


def _init_playlists_from_apple_music():
    """Load playlists from Apple Music on server start and cache to DB."""
    global _playlists_cache
    try:
        from src.db import init_db, Playlist

        pm = _get_playlist_manager()
        if not pm:
            logger.warning("PlaylistManager not available for initial load")
            return

        # Get playlists from Apple Music
        playlists = pm.get_all_playlists() or []
        logger.info(f"Loading {len(playlists)} playlists from Apple Music into cache")

        if not playlists:
            logger.warning("No playlists returned from Apple Music")
            return

        # Store in DB using session from init_db
        _, SessionLocal = init_db()
        session = SessionLocal()

        try:
            playlists_by_id = {}
            for p in playlists:
                playlist_id = str(p.get("id", "")).strip()
                if not playlist_id:
                    continue
                playlists_by_id[playlist_id] = {
                    **p,
                    "id": playlist_id,
                    "name": str(p.get("name", "Unnamed")),
                    "track_count": int(p.get("track_count", 0)),
                }

            if not playlists_by_id:
                logger.warning("No cacheable playlists returned from Apple Music")
                return

            if len(playlists_by_id) != len(playlists):
                logger.info(
                    "Deduplicated playlist cache input from %s to %s records",
                    len(playlists),
                    len(playlists_by_id),
                )

            existing = {
                playlist.persistent_id: playlist
                for playlist in session.query(Playlist)
                .filter(Playlist.persistent_id.in_(playlists_by_id.keys()))
                .all()
            }

            # Upsert current playlists so duplicate Music.app IDs cannot break startup.
            for playlist_id, p in playlists_by_id.items():
                playlist = existing.get(playlist_id)
                if playlist is None:
                    playlist = Playlist(persistent_id=playlist_id)
                    session.add(playlist)
                playlist.name = p["name"]
                playlist.track_count = p["track_count"]
                playlist.genre = p.get("genre")
                playlist.created_date = p.get("created_date")

            session.query(Playlist).filter(
                ~Playlist.persistent_id.in_(playlists_by_id.keys())
            ).delete(synchronize_session=False)

            session.commit()
            _playlists_cache = list(playlists_by_id.values())
            logger.info(f"Successfully cached {len(playlists_by_id)} playlists to DB")
        except Exception as e:
            logger.error(f"Failed to save playlists to DB: {e}")
            session.rollback()
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to initialize playlists: {e}")


def _get_playlists_from_cache():
    """Retrieve playlists from database cache."""
    try:
        from src.db import Playlist, get_session

        session = get_session()
        playlists = session.query(Playlist).all()
        result = [p.to_dict() for p in playlists]
        session.close()
        return result
    except Exception as e:
        logger.error(f"Failed to get playlists from cache: {e}")
        return []


def _get_playlist_classifier():
    """Initialize and return playlist classifier."""
    try:
        data_dir = Path(__file__).parent.parent / "data"
        from src.playlist_classifier import PlaylistClassifier

        return PlaylistClassifier(
            genre_map_path=str(data_dir / "config" / "genre_map.json"),
            weights_path=str(data_dir / "config" / "weights.json"),
            artist_lists_dir=str(data_dir / "artist_lists"),
        )
    except Exception as e:
        logger.warning(f"Failed to initialize PlaylistClassifier: {e}")
        return None


def _get_curation_service():
    """Initialize and return curation service."""
    try:
        from src.curation_service import CurationService

        return CurationService()
    except Exception as e:
        logger.warning(f"Failed to initialize CurationService: {e}")
        return None


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
    try:
        pm = _get_playlist_manager()
        platform = sys.platform

        playlists = []
        tracks_count = 0

        if pm and hasattr(pm, "get_all_playlists"):
            try:
                playlists = pm.get_all_playlists()  # pylint: disable=no-member
            except Exception:
                pass

        # Calculate total tracks
        if playlists:
            tracks_count = sum(p.get("track_count", 0) for p in playlists if isinstance(p, dict))

        return jsonify(
            {
                "status": "healthy",
                "version": "1.0.0",
                "playlists_count": len(playlists),
                "tracks_count": tracks_count,
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
        "app_name": "curator",
        "version": "1.0.0",
        "api_base": "/api",
        "polling_interval": 2000,
        "timeout": 30000
      }
    """
    return jsonify(
        {
            "app_name": "curator",
            "version": "1.0.0",
            "api_base": "/api",
            "polling_interval": 2000,  # ms
            "timeout": 30000,  # ms
        }
    )


@app.route("/api/playlists", methods=["GET"])
def get_playlists():
    """
    List all playlists with metadata (from cache).

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
        # Serve from database cache (loaded on server startup)
        playlists = _get_playlists_from_cache()
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
        pm = _get_playlist_manager()

        if pm and hasattr(pm, "get_playlist_details"):
            try:
                details = pm.get_playlist_details(playlist_id)  # pylint: disable=no-member
                if details:
                    return jsonify(details)
            except Exception:
                pass

        # Return mock structure if not found
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
        classifier = _get_playlist_classifier()
        pm = _get_playlist_manager()

        if classifier and pm:
            try:
                # In real implementation, would get tracks and classify
                genre, classification_details = classifier.classify_playlist([], playlist_id)
                if genre or classification_details:
                    return jsonify(
                        {
                            "id": playlist_id,
                            "genre": genre or "unclassified",
                            "confidence": classification_details.get("confidence", 0.0),
                            "reasoning": classification_details.get("reasoning", ""),
                            "success": bool(genre),
                        }
                    )
            except Exception as e:
                logger.warning(f"Classification failed: {e}")

        # Return unclassified response
        return jsonify(
            {
                "id": playlist_id,
                "genre": "unclassified",
                "confidence": 0.0,
                "reasoning": "Classification service unavailable",
                "success": False,
            }
        )
    except Exception as e:
        logger.error(f"Failed to classify playlist {playlist_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/api/playlists/organize")
def organize_playlists():
    try:
        data = _plan_json({"playlist_ids"}, {"dry_run"})
        if data.get("dry_run", True) is not True:
            raise BadRequest("Organization is preview-only; apply the reviewed plan separately")
        ids = data["playlist_ids"]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise BadRequest("Select 1 to 100 explicit persistent IDs")
        for pid in ids:
            _persistent_id(pid)
        classifier = _get_playlist_classifier()
        manager = _get_playlist_manager()
        if classifier is None or manager is None:
            return jsonify(success=False, error="Playlist manager/classifier unavailable"), 503
        classifier.enable_genre_enrichment = False
        plan = manager.preview_playlist_organization(ids, classifier)
        token, snapshot = _playlist_plans.put(session["sid"], "organization", plan)
        changes = snapshot["operations"]
        return jsonify(success=True, plan_id=token, plan=snapshot, changes=changes,
                       total_changes=len(changes), expires_in=_playlist_plans.ttl)
    except (BadRequest, RequestEntityTooLarge) as exc:
        return jsonify(success=False, error=exc.description), exc.code
    except ValueError:
        return jsonify(success=False, error="Selected playlists or folder topology cannot be previewed"), 400
    except Exception:
        return jsonify(success=False, error="Unable to preview folder organization"), 503


@app.post("/api/playlists/move")
def move_playlists():
    try:
        data = _plan_json({"confirmed"}, {"plan_id", "changes"})
        if data["confirmed"] is not True:
            raise BadRequest("confirmed must be literal true")
        if "plan_id" not in data and data.get("changes", []) == []:
            return jsonify(moved=0, applied=0, failed=0, skipped=0, duration_seconds=0, success=True, results=[])
        if "changes" in data:
            raise BadRequest("Submit the reviewed plan_id, not client-supplied moves")
        token = data.get("plan_id")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise BadRequest("A reviewed plan_id is required")
        plan = _playlist_plans.claim(token, session["sid"], "organization")
        if plan is None:
            return jsonify(success=False, error="Folder plan unavailable, expired, replaced or already submitted"), 409
        manager = _get_playlist_manager()
        if manager is None:
            return jsonify(success=False, error="Playlist manager unavailable; plan consumed"), 503
        start = time.monotonic()
        result = manager.apply_playlist_organization(plan, confirmed=True)
        success = result.get("success") is True
        return jsonify({**result, "success": success, "duration_seconds": int(time.monotonic() - start)}), 200 if success else 409
    except (BadRequest, RequestEntityTooLarge) as exc:
        return jsonify(success=False, error=exc.description), exc.code
    except Exception:
        return jsonify(success=False, error="Move outcome uncertain; plan consumed. Inspect Music manually; do not resubmit."), 500


class _PlaylistPlanStore:
    """Process-local, bounded, one-use capabilities; the service owns durable recovery."""

    ttl = 15 * 60
    max_entries = 64
    max_plan_bytes = 2 * 1024 * 1024
    max_total_bytes = 16 * 1024 * 1024

    def __init__(self):
        self.records = OrderedDict()
        self.lock = Lock()

    def _prune(self):
        now = time.monotonic()
        for token, record in list(self.records.items()):
            if record["expires_at"] <= now:
                del self.records[token]

    def put(self, sid, kind, plan):
        snapshot = deepcopy(plan)
        size = len(json.dumps(snapshot, allow_nan=False).encode("utf-8"))
        if size > self.max_plan_bytes:
            raise RequestEntityTooLarge("Preview exceeds the local plan size limit")
        with self.lock:
            self._prune()
            for token, record in list(self.records.items()):
                if (record["sid"], record["kind"]) == (sid, kind):
                    del self.records[token]
            while self.records and (
                len(self.records) >= self.max_entries
                or sum(record["size"] for record in self.records.values()) + size > self.max_total_bytes
            ):
                self.records.popitem(last=False)
            token = secrets.token_urlsafe(32)
            self.records[token] = {
                "sid": sid, "kind": kind, "plan": snapshot, "size": size,
                "expires_at": time.monotonic() + self.ttl,
            }
        return token, snapshot

    def claim(self, token, sid, kind):
        with self.lock:
            self._prune()
            record = self.records.get(token)
            if record is None or (record["sid"], record["kind"]) != (sid, kind):
                return None
            # Remove before service construction/writer invocation, including exceptions.
            del self.records[token]
            return record["plan"]


_playlist_plans = _PlaylistPlanStore()
_PLAN_REQUEST_BYTES = 16 * 1024


def _plan_json(required, optional=()):
    if request.args or not request.is_json:
        raise BadRequest("JSON body without query parameters required")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate fields")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON number")

    try:
        data = json.loads(bounded_request_body(_PLAN_REQUEST_BYTES), object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise BadRequest("Invalid JSON body") from None
    if (not isinstance(data, dict) or not set(required) <= set(data)
            or set(data) - set(required) - set(optional)):
        raise BadRequest("Unexpected or missing fields")
    return data


def _persistent_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{16}", value):
        raise BadRequest("A 16-character persistent ID is required")
    return value


def _playlist_plan_read(playlist_id=None):
    try:
        if request.args or bounded_request_body(_PLAN_REQUEST_BYTES):
            raise BadRequest("This endpoint accepts no query or body")
        if playlist_id is not None:
            _persistent_id(playlist_id)
        service = _get_curation_service()
        if service is None:
            return jsonify(success=False, error="Curation service unavailable"), 503
        rows = (service.get_seed_playlist_sources() if playlist_id is None
                else service.get_seed_playlist_source_tracks(playlist_id))
        return jsonify(rows)
    except (BadRequest, RequestEntityTooLarge) as exc:
        return jsonify(success=False, error=exc.description), exc.code
    except Exception:
        return jsonify(success=False, error="Unable to read selected sources"), 503


@app.get("/api/playlist-plans/sources")
def playlist_plan_sources():
    return _playlist_plan_read()


@app.get("/api/playlist-plans/source/<playlist_id>/tracks")
def playlist_plan_source_tracks(playlist_id):
    return _playlist_plan_read(playlist_id)


@app.post("/api/playlist-plans/seed/preview", defaults={"kind": "seed"})
@app.post("/api/playlist-plans/split/preview", defaults={"kind": "split"})
def playlist_plan_preview(kind):
    try:
        if kind == "seed":
            data = _plan_json({"playlist_id", "seed_track_id"}, {"limit"})
            _persistent_id(data["playlist_id"])
            _persistent_id(data["seed_track_id"])
            limit = data.get("limit", 30)
            if type(limit) is not int or not 1 <= limit <= 30:
                raise BadRequest("limit must be an integer from 1 to 30")
        else:
            data = _plan_json({"playlist_ids"})
            ids = data["playlist_ids"]
            if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
                raise BadRequest("playlist_ids must contain 1 to 100 IDs")
            for playlist_id in ids:
                _persistent_id(playlist_id)
        service = _get_curation_service()
        if service is None:
            return jsonify(success=False, error="Curation service unavailable"), 503
        plan = (service.preview_seed_playlist(data["playlist_id"], data["seed_track_id"], limit=limit)
                if kind == "seed" else service.preview_playlist_splits(ids))
        token, snapshot = _playlist_plans.put(session["sid"], kind, plan)
        return jsonify(plan_id=token, plan=snapshot, expires_in=_playlist_plans.ttl)
    except (BadRequest, RequestEntityTooLarge) as exc:
        return jsonify(success=False, error=exc.description), exc.code
    except ValueError:
        return jsonify(success=False, error="Selected source or seed cannot be previewed"), 400
    except Exception:
        return jsonify(success=False, error="Unable to preview playlist plan"), 503


@app.post("/api/playlist-plans/seed/apply", defaults={"kind": "seed"})
@app.post("/api/playlist-plans/split/apply", defaults={"kind": "split"})
def playlist_plan_apply(kind):
    try:
        data = _plan_json({"plan_id", "confirmed"})
        if data["confirmed"] is not True:
            raise BadRequest("confirmed must be literal true")
        token = data["plan_id"]
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise BadRequest("Invalid plan_id")
        plan = _playlist_plans.claim(token, session["sid"], kind)
        if plan is None:
            return jsonify(success=False, error="Plan unavailable, expired, replaced or already submitted"), 409
        service = _get_curation_service()
        if service is None:
            return jsonify(success=False, error="Curation service unavailable; plan consumed"), 503
        result = (service.apply_seed_playlist(plan, confirmed=True) if kind == "seed"
                  else service.apply_playlist_splits(plan, confirmed=True))
        if not isinstance(result, dict):
            raise RuntimeError("Invalid apply report")
        # Preserve per-part and unresolved reports without turning failures into success.
        success = result.get("success") is True
        return jsonify({**result, "success": success}), 200 if success else 409
    except (BadRequest, RequestEntityTooLarge) as exc:
        return jsonify(success=False, error=exc.description), exc.code
    except Exception:
        return jsonify(success=False, error=(
            "Apply outcome uncertain; plan consumed. Inspect the journal and Music manually; do not resubmit."
        )), 500


@app.route("/api/curation/preview", methods=["GET"])
def curation_preview():
    """Preview playlist curation assignments and changes."""
    try:
        scope = request.args.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        return jsonify(service.preview_fav_songs())
    except Exception as e:
        logger.error(f"Failed to preview curation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation/snapshot", methods=["GET"])
def curation_snapshot():
    """Return cached playlist curation snapshot."""
    try:
        scope = request.args.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        return jsonify(service.get_fav_songs_snapshot())
    except Exception as e:
        logger.error(f"Failed to get curation snapshot: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation/refresh", methods=["POST"])
def curation_refresh():
    """Refresh and return playlist curation snapshot."""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        return jsonify(service.refresh_fav_songs_snapshot())
    except Exception as e:
        logger.error(f"Failed to refresh curation snapshot: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation/apply", methods=["POST"])
def curation_apply():
    """Queue playlist curation changes after confirmation and mini-test."""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        confirmed = data.get("confirmed", False)
        if not isinstance(confirmed, bool):
            return jsonify({"error": "confirmed must be a boolean"}), 400
        if confirmed is not True:
            return jsonify({"error": "Confirmation required"}), 400

        mini_test_passed = data.get("mini_test_passed", False)
        if mini_test_passed is not True:
            return jsonify({"error": "mini_test_passed must be true"}), 400

        max_tracks = data.get("max_tracks")
        if max_tracks is not None:
            if (
                isinstance(max_tracks, bool)
                or not isinstance(max_tracks, int)
                or max_tracks < 1
            ):
                return jsonify({"error": "max_tracks must be a positive integer"}), 400

        smoke_test_token = data.get("smoke_test_token")
        token_record = (
            _curation_smoke_tokens.get(smoke_test_token)
            if isinstance(smoke_test_token, str)
            else None
        )
        if (
            not token_record
            or token_record.get("used")
            or token_record.get("success") is not True
            or token_record.get("scope") != scope
        ):
            return jsonify({"error": "Valid smoke-test token required"}), 400
        if token_record.get("expires_at", 0) < time.time():
            _curation_smoke_tokens.pop(smoke_test_token, None)
            return (
                jsonify({"error": "Smoke-test token expired; run a new smoke test"}),
                400,
            )

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        snapshot = service.get_fav_songs_snapshot()
        if not snapshot or not snapshot.get("available") or not snapshot.get("fresh"):
            return jsonify({"error": "Fresh curation snapshot required"}), 400
        snapshot_created_at = snapshot.get("created_at")
        if not snapshot_created_at:
            return jsonify({"error": "Current curation snapshot required"}), 400
        if snapshot_created_at != token_record.get("snapshot_created_at"):
            return (
                jsonify(
                    {
                        "error": (
                            "Smoke-test token does not match current snapshot; "
                            "run a new smoke test"
                        )
                    }
                ),
                400,
            )

        if not CELERY_AVAILABLE:
            return jsonify({"error": "Curation apply queue unavailable"}), 503

        job_id = f"curation-apply-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        job_store = get_job_store()
        job_payload = {
            "scope": scope,
            "snapshot_created_at": snapshot_created_at,
        }
        if max_tracks is not None:
            job_payload["max_tracks"] = max_tracks

        job_store.create_job(
            job_id=job_id,
            job_type="curation_apply",
            payload=job_payload,
            user_agent=request.headers.get("User-Agent"),
            client_ip=request.remote_addr,
        )

        try:
            task_args = [job_id, scope]
            if max_tracks is not None:
                task_args.append(max_tracks)
            apply_curation.apply_async(
                args=task_args,
                task_id=job_id,
            )
        except Exception as queue_error:
            job_store.update_job_status(
                job_id,
                "failed",
                error_message=str(queue_error),
                error_code="CURATION_QUEUE_ERROR",
            )
            return jsonify({"error": "Curation apply queue unavailable"}), 503

        token_record["used"] = True
        return jsonify(
            {
                "success": True,
                "status": "queued",
                "job_id": job_id,
                "message": "Curation apply queued.",
            }
        ), 202
    except Exception as e:
        logger.error(f"Failed to apply curation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/curation/smoke-test", methods=["POST"])
def curation_smoke_test():
    """Run a reversible one-track curation smoke test."""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "fav_songs")
        if scope != "fav_songs":
            return jsonify({"error": "Unsupported curation scope"}), 400

        service = _get_curation_service()
        if not service:
            return jsonify({"error": "Curation service unavailable"}), 503

        snapshot = service.get_fav_songs_snapshot()
        if not snapshot or not snapshot.get("available") or not snapshot.get("fresh"):
            return jsonify({"error": "Fresh curation snapshot required"}), 400
        snapshot_created_at = snapshot.get("created_at")
        if not snapshot_created_at:
            return jsonify({"error": "Current curation snapshot required"}), 400

        result = service.run_fav_songs_smoke_test()
        if not result.get("success"):
            return jsonify(result), 500

        token = secrets.token_urlsafe(18)
        _curation_smoke_tokens[token] = {
            "scope": scope,
            "snapshot_created_at": snapshot_created_at,
            "success": True,
            "expires_at": time.time() + _CURATION_SMOKE_TOKEN_TTL_SECONDS,
            "used": False,
        }
        result["smoke_test_token"] = token
        return jsonify(result), 200 if result.get("success") else 500
    except Exception as e:
        logger.error(f"Failed to run curation smoke test: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/status", methods=["GET"])
@rate_limit(limit=300)  # Status polls can be frequent
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
        job_id = request.args.get("job_id")

        if not job_id:
            # Return fallback status if no specific job requested
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

        # Get job from database
        job_store = get_job_store()
        job = job_store.get_job(job_id)

        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Calculate elapsed time
        elapsed = 0
        if job.started_at:
            elapsed = int((time.time() - job.started_at.timestamp()))

        # Estimate ETA
        eta_seconds = None
        if job.status == "running" and job.progress > 0:
            estimated_total = (elapsed * 100) / job.progress
            eta_seconds = max(0, int(estimated_total - elapsed))

        return jsonify(
            {
                "running": job.status == "running",
                "progress": job.progress,
                "current_operation": f"Processing {job.current_track}/{job.total_tracks}",
                "current_track": job.current_track,
                "total_tracks": job.total_tracks,
                "time_elapsed": elapsed,
                "eta_seconds": eta_seconds,
            }
        )
    except Exception as e:
        logger.error(f"Failed to get enrichment status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/start", methods=["POST"])
@rate_limit(limit=100)  # 100 requests/min for general API
@check_job_quota()  # Add stricter job submission quota (5/min, 100/day)
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
        "status": "queued",
        "total_tracks": 0,
        "success": true
      }
    """
    try:
        data = request.get_json() or {}
        playlist_ids = data.get("playlist_ids", [])
        sources = data.get("sources", ["spotify"])

        # Create unique job ID
        job_id = f"enrichment-{int(time.time())}-{uuid.uuid4().hex[:8]}"

        # Persist to database
        job_store = get_job_store()
        job_store.create_job(
            job_id=job_id,
            job_type="enrichment",
            payload=data,
            user_agent=request.headers.get("User-Agent"),
            client_ip=request.remote_addr,
        )

        # Submit to Celery queue if available
        if CELERY_AVAILABLE:
            try:
                enrich_metadata.apply_async(
                    args=[job_id, playlist_ids, sources],
                    task_id=job_id,
                )
                logger.info(f"Submitted enrichment task to Celery: {job_id}")
            except Exception as e:
                logger.warning(f"Celery unavailable, job persisted to database: {e}")
        else:
            logger.info(f"Celery unavailable, job persisted to database: {job_id}")

        total_tracks = len(playlist_ids) * 10  # Mock estimation

        return (
            jsonify(
                {
                    "job_id": job_id,
                    "status": "queued",
                    "total_tracks": total_tracks,
                    "success": True,
                }
            ),
            202,
        )  # 202 ACCEPTED
    except Exception as e:
        logger.error(f"Failed to start enrichment: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/enrichment/results", methods=["GET"])
def enrichment_results():
    """Get completed enrichment results from the persistent state store."""
    try:
        job_id = request.args.get("job_id")
        limit = request.args.get("limit", 20, type=int)

        job_store = get_job_store()
        state_store = LibraryStateStore()

        if job_id:
            job = job_store.get_job(job_id)
            if not job:
                return jsonify({"error": "Job not found"}), 404
            # Pull recent enrich runs that match this job's scope
            runs = state_store.list_runs(limit=1, run_type="enrich")
            status = job.status
            tracks_enriched = runs[0].processed_items if runs else job.current_track
            duration = 0
            if job.started_at and job.completed_at:
                duration = int((job.completed_at - job.started_at).total_seconds())
        else:
            runs = state_store.list_runs(limit=1, run_type="enrich")
            status = runs[0].status if runs else "idle"
            tracks_enriched = runs[0].processed_items if runs else 0
            duration = 0
            if runs and runs[0].started_at and runs[0].completed_at:
                duration = int((runs[0].completed_at - runs[0].started_at).total_seconds())

        # Recent track history for this scope
        recent_tracks = state_store.list_tracks(scope="metadata_fill", limit=limit)
        results = [
            {
                "track_key": t.track_key,
                "artist": t.artist,
                "title": t.title,
                "album": t.album,
                "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
                "skip_reason": t.skip_reason,
            }
            for t in recent_tracks
        ]

        return jsonify(
            {
                "status": status,
                "tracks_enriched": tracks_enriched,
                "fields_added": 0,  # ponytail: field-level tracking not yet wired; upgrade when needed
                "duration_seconds": duration,
                "results": results,
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
        global _enrichment_state

        tracks_processed = _enrichment_state["current_track"]
        _enrichment_state = {
            "running": False,
            "progress": 0,
            "current_operation": "",
            "current_track": 0,
            "total_tracks": 0,
            "start_time": 0,
            "job_id": None,
        }

        return jsonify(
            {"status": "cancelled", "tracks_processed": tracks_processed, "success": True}
        )
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
        global _temperament_state

        if _temperament_state["running"]:
            return (
                jsonify(
                    {
                        "error": "Analysis already running",
                        "job_id": _temperament_state["job_id"],
                    }
                ),
                409,
            )

        data = request.get_json() or {}
        track_ids = data.get("track_ids", [])

        job_id = f"temperament-{int(time.time())}"

        _temperament_state = {
            "running": True,
            "progress": 0,
            "current_operation": "Analyzing mood...",
            "start_time": time.time(),
            "job_id": job_id,
        }

        logger.info(f"Started temperament analysis job {job_id}")

        return jsonify(
            {
                "job_id": job_id,
                "status": "started",
                "total_tracks": len(track_ids),
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
        return jsonify(_temperament_results)
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
        global _user_settings

        data = request.get_json() or {}
        _user_settings.update(data)

        logger.debug(f"Settings saved: {_user_settings}")

        return jsonify({"success": True, "message": "Settings saved"})
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return jsonify({"error": str(e)}), 500


@app.before_request
def before_request_handler():
    """Initialize only after access checks, never for login/static/plan validation."""
    if (not g.get("web_authenticated") or request.endpoint in {"session_info", "organize_playlists", "move_playlists"}
            or request.path.startswith("/api/playlist-plans")):
        return

    def init():
        try:
            if not hasattr(app, "_db_initialized"):
                setup_database()
                app._db_initialized = True
        except Exception as e:
            logger.warning(f"Database initialization skipped: {e}")

    # Only run once
    init()


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
        <title>curator - Browser Frontend</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
            .loading { text-align: center; padding: 50px; color: #666; }
        </style>
    </head>
    <body>
        <div class="loading">
            <h1>curator</h1>
            <p>Loading front-end assets...</p>
        </div>
        <script>
            console.error('index.html not found - run: npm install or setup frontend files');
        </script>
    </body>
    </html>
    """


@app.route("/api/jobs/<job_id>", methods=["GET"])
@rate_limit(limit=200)  # Reads
def get_job(job_id: str):
    """
    Get specific job by ID.

    Args:
      job_id: The job ID

    Returns:
      {
        "id": "enrichment-123...",
        "type": "enrichment",
        "status": "running",
        "created_at": "2026-03-09T15:30:00Z",
        "progress": 50,
        "current_track": 10,
        "total_tracks": 20
      }
    """
    try:
        job_store = get_job_store()
        job = job_store.get_job(job_id)

        if not job:
            return jsonify({"error": "Job not found"}), 404

        return jsonify(job.to_dict())
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs", methods=["GET"])
@rate_limit(limit=200)  # Reads can be more liberal
def list_jobs():
    """
    List all jobs with pagination.

    Query parameters:
      - page: Page number (default: 1)
      - limit: Results per page (default: 20)
      - status: Filter by status
      - type: Filter by job type

    Returns:
      {
        "jobs": [
          {
            "id": "enrichment-123...",
            "type": "enrichment",
            "status": "completed",
            "created_at": "2026-03-09T15:30:00Z"
          },
          ...
        ],
        "total_count": 47,
        "page": 1,
        "pages": 3
      }
    """
    try:
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 20, type=int)
        status = request.args.get("status")
        job_type = request.args.get("type")

        job_store = get_job_store()
        total_count, jobs = job_store.list_jobs(
            page=page, limit=limit, status=status, job_type=job_type
        )

        jobs_data = [job.to_dict() for job in jobs]

        return jsonify(
            {
                "jobs": jobs_data,
                "total_count": total_count,
                "page": page,
                "pages": (total_count + limit - 1) // limit,
            }
        )
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["GET"])
@rate_limit(limit=200)
def history():
    """Return recent library runs and jobs from the shared state stores."""
    try:
        limit = request.args.get("limit", 20, type=int)
        run_type = request.args.get("type")
        status = request.args.get("status")
        job_type = request.args.get("job_type")

        state_store = LibraryStateStore()
        job_store = get_job_store()

        runs = [run.to_dict() for run in state_store.list_runs(limit=limit, run_type=run_type)]
        total_jobs, jobs = job_store.list_jobs(
            page=1, limit=limit, status=status, job_type=job_type
        )

        return jsonify(
            {
                "runs": runs,
                "jobs": [job.to_dict() for job in jobs],
                "jobs_total_count": total_jobs,
                "limit": limit,
            }
        )
    except Exception as e:
        logger.error(f"Failed to list history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/runs", methods=["GET"])
@rate_limit(limit=200)
def list_runs():
    """List library runs (enrich, dedupe, scan, organize) from the persistent state store."""
    try:
        limit = request.args.get("limit", 20, type=int)
        run_type = request.args.get("type")

        state_store = LibraryStateStore()
        runs = state_store.list_runs(limit=limit, run_type=run_type)

        return jsonify(
            {
                "runs": [r.to_dict() for r in runs],
                "total": len(runs),
                "limit": limit,
            }
        )
    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/dedupe", methods=["GET"])
@rate_limit(limit=200)
def list_dedupe():
    """Return recent deduplication history entries."""
    try:
        limit = request.args.get("limit", 50, type=int)
        scope = request.args.get("scope")

        state_store = LibraryStateStore()
        entries = state_store.list_tracks(scope=scope, limit=limit)

        return jsonify(
            {
                "entries": [
                    {
                        "scope": e.scope,
                        "track_key": e.track_key,
                        "artist": e.artist,
                        "title": e.title,
                        "album": e.album,
                        "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
                        "skip_reason": e.skip_reason,
                        "source": e.source,
                    }
                    for e in entries
                ],
                "total": len(entries),
                "limit": limit,
                "scope": scope,
            }
        )
    except Exception as e:
        logger.error(f"Failed to list dedupe entries: {e}")
        return jsonify({"error": str(e)}), 500


def run_server(host: str = WEB_HOST, port: int = WEB_PORT, debug: bool = WEB_DEBUG):
    """Start only a protected loopback listener; never enable debugger/reloader."""
    settings = load_access_settings(host, port, debug)
    app.extensions["web_access"] = settings
    logger.info("Starting local web server at %s", settings.origin)

    # Initialize database first
    logger.info("Initializing database...")
    setup_database()

    # Initialize playlist cache from Apple Music on startup
    logger.info("Loading playlists from Apple Music...")
    _init_playlists_from_apple_music()

    app.run(host=settings.bind_host, port=settings.port, debug=False,
            use_reloader=False, use_debugger=False)


if __name__ == "__main__":
    run_server()
