"""
Tests for Flask web server API endpoints.

Tests follow the browser-frontend specification:
- openspec/specs/browser-frontend/spec.md

Test coverage:
- GET /api/health - Server health check
- GET /api/config - Frontend configuration
- GET /api/playlists - List all playlists
- GET /api/playlists/<id> - Get playlist details
- POST /api/playlists/<id>/classify - Classify playlist by genre
- POST /api/playlists/organize - Dry-run playlist organization
- POST /api/playlists/move - Execute playlist moves
- GET /api/enrichment/status - Check enrichment progress
- POST /api/enrichment/start - Begin enrichment
- GET /api/enrichment/results - Get enrichment results
- POST /api/enrichment/cancel - Cancel enrichment
- POST /api/temperament/classify - Classify tracks by mood
- GET /api/temperament/results - Get mood classification results
- GET /api/history - Show recent runs and jobs
- POST /api/settings - Save user preferences
"""

import json

import pytest

from src.web_server import app


@pytest.fixture
def client(monkeypatch):
    """Create Flask test client."""
    app.config["TESTING"] = True

    # Reset global state before each test
    import src.web_server as ws
    ws._curation_smoke_tokens.clear()

    class FakePlaylistManager:
        def get_all_playlists(self):
            return [
                {
                    "id": "test-playlist-1",
                    "name": "Test Playlist",
                    "track_count": 0,
                }
            ]

        def get_playlist_details(self, playlist_id):
            return {
                "id": playlist_id,
                "name": f"Playlist {playlist_id}",
                "track_count": 0,
                "genre": None,
                "tracks": [],
            }

    monkeypatch.setattr(ws, "_get_playlist_manager", lambda: FakePlaylistManager())

    ws._enrichment_state = {
        "running": False,
        "progress": 0,
        "current_operation": "",
        "current_track": 0,
        "total_tracks": 0,
        "start_time": 0,
        "job_id": None,
    }
    ws._temperament_state = {
        "running": False,
        "progress": 0,
        "current_operation": "",
        "start_time": 0,
        "job_id": None,
    }
    ws._enrichment_results = {
        "status": "idle",
        "tracks_enriched": 0,
        "fields_added": 0,
        "duration_seconds": 0,
        "results": [],
    }
    ws._temperament_results = []
    ws._user_settings = {}

    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for GET /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Health check should return 200 OK."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """Health response should be valid JSON."""
        response = client.get("/api/health")
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_health_has_required_fields(self, client):
        """Health response must have all required fields per spec."""
        response = client.get("/api/health")
        data = json.loads(response.data)

        required_fields = [
            "status",
            "version",
            "playlists_count",
            "tracks_count",
            "platform",
            "apple_music_connected",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_health_status_is_healthy(self, client):
        """Health status should be 'healthy' when server is up."""
        response = client.get("/api/health")
        data = json.loads(response.data)
        assert data["status"] == "healthy"

    def test_health_platform_is_valid(self, client):
        """Platform should be one of: darwin, win32, linux."""
        response = client.get("/api/health")
        data = json.loads(response.data)
        valid_platforms = ["darwin", "win32", "linux"]
        assert data["platform"] in valid_platforms

    def test_health_counts_are_integers(self, client):
        """Playlist and track counts should be integers."""
        response = client.get("/api/health")
        data = json.loads(response.data)
        assert isinstance(data["playlists_count"], int)
        assert isinstance(data["tracks_count"], int)


class TestConfigEndpoint:
    """Tests for GET /api/config endpoint."""

    def test_config_returns_200(self, client):
        """Config endpoint should return 200 OK."""
        response = client.get("/api/config")
        assert response.status_code == 200

    def test_config_returns_json(self, client):
        """Config response should be valid JSON."""
        response = client.get("/api/config")
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_config_has_required_fields(self, client):
        """Config response must have expected fields."""
        response = client.get("/api/config")
        data = json.loads(response.data)

        required_fields = ["app_name", "version", "api_base", "polling_interval", "timeout"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_config_app_name_is_correct(self, client):
        """App name should be 'affective_playlists'."""
        response = client.get("/api/config")
        data = json.loads(response.data)
        assert data["app_name"] == "affective_playlists"

    def test_config_polling_interval_is_positive(self, client):
        """Polling interval should be positive milliseconds."""
        response = client.get("/api/config")
        data = json.loads(response.data)
        assert data["polling_interval"] > 0

    def test_config_timeout_is_positive(self, client):
        """Timeout should be positive milliseconds."""
        response = client.get("/api/config")
        data = json.loads(response.data)
        assert data["timeout"] > 0


class TestPlaylistsEndpoint:
    """Tests for GET /api/playlists endpoint."""

    def test_playlist_cache_initialization_deduplicates_persistent_ids(
        self, tmp_path, monkeypatch
    ):
        """Apple Music cache sync should tolerate duplicate persistent IDs."""
        import src.db as db
        import src.web_server as ws
        from src.db import Playlist

        database_url = f"sqlite:///{tmp_path / 'jobs.db'}"
        original_init_db = db.init_db

        def init_temp_db():
            return original_init_db(database_url)

        class DuplicatePlaylistManager:
            def get_all_playlists(self):
                return [
                    {"id": "duplicate-id", "name": "Old Name", "track_count": 1},
                    {"id": "duplicate-id", "name": "New Name", "track_count": 2},
                    {"id": "unique-id", "name": "Unique", "track_count": 3},
                ]

        monkeypatch.setattr(db, "init_db", init_temp_db)
        monkeypatch.setattr(
            ws, "_get_playlist_manager", lambda: DuplicatePlaylistManager()
        )

        ws._init_playlists_from_apple_music()

        _, SessionLocal = original_init_db(database_url)
        session = SessionLocal()
        try:
            playlists = session.query(Playlist).all()
            duplicate = session.get(Playlist, "duplicate-id")
        finally:
            session.close()

        assert len(playlists) == 2
        assert duplicate.name == "New Name"
        assert duplicate.track_count == 2
        assert len(ws._playlists_cache) == 2

    def test_playlists_returns_200(self, client):
        """Playlists endpoint should return 200 OK."""
        response = client.get("/api/playlists")
        assert response.status_code == 200

    def test_playlists_returns_json_array(self, client):
        """Playlists response should be a JSON array."""
        response = client.get("/api/playlists")
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_playlists_array_items_have_required_fields(self, client):
        """Each playlist item should have required fields per spec."""
        response = client.get("/api/playlists")
        data = json.loads(response.data)

        if len(data) > 0:
            required_fields = ["id", "name", "track_count"]
            playlist = data[0]
            for field in required_fields:
                assert field in playlist, f"Missing field in playlist: {field}"


class TestPlaylistDetailEndpoint:
    """Tests for GET /api/playlists/<id> endpoint."""

    def test_playlist_detail_returns_200(self, client):
        """Playlist detail endpoint should return 200 OK."""
        response = client.get("/api/playlists/test-playlist-1")
        assert response.status_code == 200

    def test_playlist_detail_returns_json(self, client):
        """Playlist detail response should be valid JSON."""
        response = client.get("/api/playlists/test-playlist-1")
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_playlist_detail_has_required_fields(self, client):
        """Playlist detail must have all required fields."""
        response = client.get("/api/playlists/test-playlist-1")
        data = json.loads(response.data)

        required_fields = ["id", "name", "track_count", "genre", "tracks"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_playlist_detail_tracks_is_array(self, client):
        """Tracks field should be an array."""
        response = client.get("/api/playlists/test-playlist-1")
        data = json.loads(response.data)
        assert isinstance(data["tracks"], list)

    def test_playlist_detail_id_matches(self, client):
        """Returned playlist ID should match requested ID."""
        playlist_id = "test-playlist-1"
        response = client.get(f"/api/playlists/{playlist_id}")
        data = json.loads(response.data)
        assert data["id"] == playlist_id


class TestClassifyEndpoint:
    """Tests for POST /api/playlists/<id>/classify endpoint."""

    def test_classify_returns_200(self, client):
        """Classify endpoint should return 200 OK."""
        response = client.post("/api/playlists/test-1/classify")
        assert response.status_code == 200

    def test_classify_returns_json(self, client):
        """Classify response should be valid JSON."""
        response = client.post("/api/playlists/test-1/classify")
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_classify_has_required_fields(self, client):
        """Classify response must have required fields per spec."""
        response = client.post("/api/playlists/test-1/classify")
        data = json.loads(response.data)

        required_fields = ["id", "genre", "confidence", "success"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_classify_confidence_is_float_between_0_and_1(self, client):
        """Confidence should be a float between 0 and 1."""
        response = client.post("/api/playlists/test-1/classify")
        data = json.loads(response.data)
        assert isinstance(data["confidence"], (int, float))
        assert 0 <= data["confidence"] <= 1


class TestEnrichmentStatusEndpoint:
    """Tests for GET /api/enrichment/status endpoint."""

    def test_enrichment_status_returns_200(self, client):
        """Enrichment status endpoint should return 200 OK."""
        response = client.get("/api/enrichment/status")
        assert response.status_code == 200

    def test_enrichment_status_has_required_fields(self, client):
        """Status response must have all required fields per spec."""
        response = client.get("/api/enrichment/status")
        data = json.loads(response.data)

        required_fields = [
            "running",
            "progress",
            "current_operation",
            "current_track",
            "total_tracks",
            "time_elapsed",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_enrichment_status_progress_is_between_0_and_100(self, client):
        """Progress should be between 0-100."""
        response = client.get("/api/enrichment/status")
        data = json.loads(response.data)
        assert 0 <= data["progress"] <= 100

    def test_enrichment_status_running_is_boolean(self, client):
        """Running field should be boolean."""
        response = client.get("/api/enrichment/status")
        data = json.loads(response.data)
        assert isinstance(data["running"], bool)


class TestEnrichmentStartEndpoint:
    """Tests for POST /api/enrichment/start endpoint."""

    def test_enrichment_start_returns_200(self, client):
        """Start enrichment should return 202 ACCEPTED (async job)."""
        response = client.post("/api/enrichment/start", json={})
        assert response.status_code == 202

    def test_enrichment_start_has_required_fields(self, client):
        """Start response must have required fields."""
        response = client.post("/api/enrichment/start", json={})
        data = json.loads(response.data)

        required_fields = ["job_id", "status", "total_tracks", "success"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_enrichment_start_with_playlist_ids(self, client):
        """Start enrichment should accept playlist_ids."""
        payload = {"playlist_ids": ["pl-1", "pl-2"]}
        response = client.post("/api/enrichment/start", json=payload)
        assert response.status_code == 202


class TestEnrichmentResultsEndpoint:
    """Tests for GET /api/enrichment/results endpoint."""

    def test_enrichment_results_returns_200(self, client):
        """Results endpoint should return 200 OK."""
        response = client.get("/api/enrichment/results")
        assert response.status_code == 200

    def test_enrichment_results_has_required_fields(self, client):
        """Results response must have required fields."""
        response = client.get("/api/enrichment/results")
        data = json.loads(response.data)

        required_fields = ["status", "tracks_enriched", "fields_added", "duration_seconds"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_enrichment_results_is_array(self, client):
        """Results field should be an array."""
        response = client.get("/api/enrichment/results")
        data = json.loads(response.data)
        assert isinstance(data.get("results"), list)


class TestEnrichmentCancelEndpoint:
    """Tests for POST /api/enrichment/cancel endpoint."""

    def test_enrichment_cancel_returns_200(self, client):
        """Cancel endpoint should return 200 OK."""
        response = client.post("/api/enrichment/cancel")
        assert response.status_code == 200

    def test_enrichment_cancel_has_success_field(self, client):
        """Cancel response should have success field."""
        response = client.post("/api/enrichment/cancel")
        data = json.loads(response.data)
        assert "success" in data


class TestTemperamentClassifyEndpoint:
    """Tests for POST /api/temperament/classify endpoint."""

    def test_temperament_classify_returns_200(self, client):
        """Classify temperament should return 200 OK."""
        response = client.post("/api/temperament/classify", json={})
        assert response.status_code == 200

    def test_temperament_classify_has_required_fields(self, client):
        """Response must have required fields."""
        response = client.post("/api/temperament/classify", json={})
        data = json.loads(response.data)

        required_fields = ["job_id", "status", "total_tracks", "success"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestTemperamentResultsEndpoint:
    """Tests for GET /api/temperament/results endpoint."""

    def test_temperament_results_returns_200(self, client):
        """Results endpoint should return 200 OK."""
        response = client.get("/api/temperament/results")
        assert response.status_code == 200

    def test_temperament_results_is_array(self, client):
        """Results response should be a JSON array."""
        response = client.get("/api/temperament/results")
        data = json.loads(response.data)
        assert isinstance(data, list)


class TestSettingsEndpoint:
    """Tests for POST /api/settings endpoint."""

    def test_settings_returns_200(self, client):
        """Settings endpoint should return 200 OK."""
        response = client.post("/api/settings", json={})
        assert response.status_code == 200

    def test_settings_has_success_field(self, client):
        """Settings response should have success field."""
        response = client.post("/api/settings", json={})
        data = json.loads(response.data)
        assert "success" in data

    def test_settings_accepts_theme(self, client):
        """Settings should accept theme parameter."""
        payload = {"theme": "dark"}
        response = client.post("/api/settings", json=payload)
        assert response.status_code == 200


class TestHistoryEndpoint:
    """Tests for GET /api/history endpoint."""

    def test_history_returns_recent_runs_and_jobs(self, tmp_path, monkeypatch, client):
        import src.db as db
        import src.library_state_store as state_store
        import src.web_server as ws

        database_url = f"sqlite:///{tmp_path / 'history.db'}"
        original_init_db = db.init_db

        def init_temp_db():
            return original_init_db(database_url)

        class FakeJob:
            def to_dict(self):
                return {"id": "job-1", "type": "enrichment", "status": "completed"}

        class FakeJobStore:
            def list_jobs(self, page=1, limit=20, status=None, job_type=None):
                return 1, [FakeJob()]

        monkeypatch.setattr(db, "init_db", init_temp_db)
        _, SessionLocal = init_temp_db()
        session = SessionLocal()
        monkeypatch.setattr(state_store, "get_session", lambda: session)
        monkeypatch.setattr(ws, "get_job_store", lambda: FakeJobStore())

        store = state_store.LibraryStateStore(session=session)
        store.create_run(
            run_type="enrich",
            target="fav_songs",
            payload={"playlist_ids": ["pl-1"]},
        )

        response = client.get("/api/history")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_type"] == "enrich"
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "job-1"


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_returns_json_error(self, client):
        """404 should return JSON error response."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data

    def test_invalid_json_returns_error(self, client):
        """Invalid JSON should be handled gracefully."""
        response = client.post(
            "/api/settings", data="invalid json", content_type="application/json"
        )
        # Should either return 400, 500 (Flask error), or handle gracefully with 200
        assert response.status_code in [400, 500, 200]


class TestOrganizeEndpoint:
    """Tests for POST /api/playlists/organize endpoint."""

    def test_organize_returns_200(self, client):
        """Organize endpoint should return 200 OK."""
        response = client.post("/api/playlists/organize", json={})
        assert response.status_code == 200

    def test_organize_has_required_fields(self, client):
        """Response must have required fields per spec."""
        response = client.post("/api/playlists/organize", json={})
        data = json.loads(response.data)

        required_fields = ["changes", "total_changes", "success"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_organize_changes_is_array(self, client):
        """Changes field should be an array."""
        response = client.post("/api/playlists/organize", json={})
        data = json.loads(response.data)
        assert isinstance(data["changes"], list)

    def test_organize_uses_real_classifier_when_available(self, client, monkeypatch):
        """When classifier and playlist manager are available, classify real playlists."""
        import src.web_server as ws

        class FakeClassifier:
            def classify_playlist(self, tracks, playlist_id):
                return "rock", {"confidence": 0.9}

        class FakePM:
            def get_playlist_details(self, pid):
                return {"name": f"Playlist {pid}", "tracks": []}

        monkeypatch.setattr(ws, "_get_playlist_classifier", lambda: FakeClassifier())
        monkeypatch.setattr(ws, "_get_playlist_manager", lambda: FakePM())

        response = client.post("/api/playlists/organize", json={"playlist_ids": ["pl-1", "pl-2"]})
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["total_changes"] == 2
        assert data["changes"][0]["genre"] == "rock"
        assert data["changes"][0]["proposed_location"] == "/Genre/Rock"
        assert "confidence" in data["changes"][0]

    def test_organize_returns_503_when_classifier_unavailable(self, client, monkeypatch):
        """Returns 503 if no classifier can be constructed."""
        import src.web_server as ws
        monkeypatch.setattr(ws, "_get_playlist_classifier", lambda: None)

        response = client.post("/api/playlists/organize", json={"playlist_ids": ["pl-1"]})
        assert response.status_code == 503


class TestMoveEndpoint:
    """Tests for POST /api/playlists/move endpoint."""

    def test_move_requires_confirmation(self, client):
        """Move should require confirmation flag."""
        response = client.post("/api/playlists/move", json={})
        assert response.status_code == 400

    def test_move_with_no_changes_returns_200(self, client):
        """Move with confirmed=true and no changes should return 200 with zero moved."""
        response = client.post("/api/playlists/move", json={"confirmed": True})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["moved"] == 0

    def test_move_response_has_results(self, client):
        """Move response should have results field."""
        response = client.post("/api/playlists/move", json={"confirmed": True})
        data = json.loads(response.data)
        assert "results" in data

    def test_move_calls_playlist_manager(self, client, monkeypatch):
        """Move with real changes calls the playlist manager."""
        import src.web_server as ws

        moved = []

        class FakePM:
            def move_playlist_to_folder(self, name, folder):
                moved.append((name, folder))
                return True

        monkeypatch.setattr(ws, "_get_playlist_manager", lambda: FakePM())

        changes = [
            {"playlist_id": "pl-1", "name": "My Mix", "genre": "jazz"},
            {"playlist_id": "pl-2", "name": "Chill", "genre": "pop"},
        ]
        response = client.post("/api/playlists/move", json={"confirmed": True, "changes": changes})
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["moved"] == 2
        assert data["failed"] == 0
        assert data["success"] is True
        assert len(moved) == 2
        assert moved[0] == ("My Mix", "Genre/Jazz")
        assert moved[1] == ("Chill", "Genre/Pop")

    def test_move_handles_partial_failure(self, client, monkeypatch):
        """Move records per-playlist failures without crashing."""
        import src.web_server as ws

        class FlakyPM:
            def move_playlist_to_folder(self, name, folder):
                if name == "Bad":
                    raise RuntimeError("AppleScript failed")
                return True

        monkeypatch.setattr(ws, "_get_playlist_manager", lambda: FlakyPM())

        changes = [
            {"playlist_id": "pl-1", "name": "Good", "genre": "rock"},
            {"playlist_id": "pl-2", "name": "Bad", "genre": "rock"},
        ]
        response = client.post("/api/playlists/move", json={"confirmed": True, "changes": changes})
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["moved"] == 1
        assert data["failed"] == 1
        assert data["success"] is False

    def test_move_returns_503_when_manager_unavailable(self, client, monkeypatch):
        """Returns 503 if no playlist manager can be constructed."""
        import src.web_server as ws
        monkeypatch.setattr(ws, "_get_playlist_manager", lambda: None)

        changes = [{"playlist_id": "pl-1", "name": "X", "genre": "rock"}]
        response = client.post("/api/playlists/move", json={"confirmed": True, "changes": changes})
        assert response.status_code == 503


class TestRunsEndpoint:
    """Tests for GET /api/runs endpoint."""

    def test_runs_returns_200(self, client, tmp_path, monkeypatch):
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'runs.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)

        store = lss.LibraryStateStore(session=session)
        store.create_run("scan", target="library", payload={})

        response = client.get("/api/runs")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert "runs" in data
        assert "total" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_type"] == "scan"

    def test_runs_supports_type_filter(self, client, tmp_path, monkeypatch):
        import src.db as db
        import src.library_state_store as lss

        url = f"sqlite:///{tmp_path / 'runs2.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)

        store = lss.LibraryStateStore(session=session)
        store.create_run("scan", target="library", payload={})
        store.create_run("enrich", target="playlist:X", payload={})

        response = client.get("/api/runs?type=enrich")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert all(r["run_type"] == "enrich" for r in data["runs"])


class TestDedupeEndpoint:
    """Tests for GET /api/dedupe endpoint."""

    def test_dedupe_returns_200(self, client, tmp_path, monkeypatch):
        import src.db as db
        import src.library_state_store as lss
        from src.deduplication import build_track_key

        url = f"sqlite:///{tmp_path / 'dedup.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)

        store = lss.LibraryStateStore(session=session)
        key = build_track_key(artist="Radiohead", title="Karma Police")
        store.record_track(
            scope="metadata_fill",
            track_key=key,
            artist="Radiohead",
            title="Karma Police",
            album="OK Computer",
        )

        response = client.get("/api/dedupe")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert "entries" in data
        assert len(data["entries"]) == 1
        assert data["entries"][0]["artist"] == "Radiohead"
        assert data["entries"][0]["title"] == "Karma Police"

    def test_dedupe_scope_filter(self, client, tmp_path, monkeypatch):
        import src.db as db
        import src.library_state_store as lss
        from src.deduplication import build_track_key

        url = f"sqlite:///{tmp_path / 'dedup2.db'}"
        _, SessionLocal = db.init_db(url)
        session = SessionLocal()
        monkeypatch.setattr(lss, "get_session", lambda: session)

        store = lss.LibraryStateStore(session=session)
        store.record_track(scope="scope_a", track_key="k1", artist="A", title="T1")
        store.record_track(scope="scope_b", track_key="k2", artist="B", title="T2")

        response = client.get("/api/dedupe?scope=scope_a")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert all(e["scope"] == "scope_a" for e in data["entries"])
        assert len(data["entries"]) == 1


class TestCurationEndpoints:
    """Tests for playlist curation API endpoints."""

    class RecordingService:
        def __init__(self, success_on_confirm=True, error_on_failure="Confirmation required"):
            self.confirmed_values = []
            self.success_on_confirm = success_on_confirm
            self.error_on_failure = error_on_failure

        def apply_fav_songs(self, confirmed):
            self.confirmed_values.append(confirmed)
            if confirmed and self.success_on_confirm:
                return {"success": True, "applied": 1, "failed": 0}
            return {
                "success": False,
                "error": self.error_on_failure,
                "applied": 0,
                "failed": 0,
            }

    class SmokeTestService:
        def __init__(self, result):
            self.result = result
            self.calls = 0

        def run_fav_songs_smoke_test(self):
            self.calls += 1
            return self.result

    def test_curation_preview_returns_assignments_and_changes(self, client, monkeypatch):
        class FakeService:
            def preview_fav_songs(self):
                return {
                    "assignments": [],
                    "changes": [],
                    "total_assignments": 0,
                    "total_changes": 0,
                }

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.get("/api/curation/preview?scope=fav_songs")

        assert response.status_code == 200
        assert response.get_json()["total_assignments"] == 0

    def test_curation_snapshot_returns_cached_state(self, client, monkeypatch):
        class FakeService:
            def get_fav_songs_snapshot(self):
                return {
                    "scope": "fav_songs",
                    "available": True,
                    "fresh": True,
                    "total_assignments": 2,
                    "total_genres": 1,
                    "total_changes": 4,
                    "total_skipped": 0,
                    "grouped": {"Hip Hop": {"Frolic": []}},
                }

            def preview_fav_songs(self):
                raise AssertionError("snapshot should not preview Music.app")

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.get("/api/curation/snapshot?scope=fav_songs")

        assert response.status_code == 200
        assert response.get_json()["total_assignments"] == 2

    def test_curation_refresh_updates_snapshot(self, client, monkeypatch):
        class FakeService:
            def refresh_fav_songs_snapshot(self):
                return {
                    "scope": "fav_songs",
                    "available": True,
                    "fresh": True,
                    "total_assignments": 4106,
                    "total_genres": 139,
                    "total_changes": 4430,
                    "total_skipped": 0,
                    "grouped": {},
                }

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.post("/api/curation/refresh", json={"scope": "fav_songs"})

        assert response.status_code == 200
        assert response.get_json()["total_genres"] == 139

    def test_curation_snapshot_rejects_unsupported_scope(self, client):
        response = client.get("/api/curation/snapshot?scope=albums")

        assert response.status_code == 400
        assert response.get_json()["error"] == "Unsupported curation scope"

    def test_curation_refresh_rejects_unsupported_scope(self, client):
        response = client.post("/api/curation/refresh", json={"scope": "albums"})

        assert response.status_code == 400
        assert response.get_json()["error"] == "Unsupported curation scope"

    def test_curation_snapshot_returns_503_when_service_unavailable(
        self, client, monkeypatch
    ):
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.get("/api/curation/snapshot")

        assert response.status_code == 503
        assert response.get_json()["error"] == "Curation service unavailable"

    def test_curation_apply_requires_smoke_test_token(self, client):
        response = client.post(
            "/api/curation/apply",
            json={"scope": "fav_songs", "confirmed": True, "mini_test_passed": True},
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Valid smoke-test token required"

    def test_curation_apply_queues_job_after_gate_and_consumes_token(
        self, client, monkeypatch
    ):
        import src.web_server as ws

        class FakeApplyTask:
            def __init__(self):
                self.calls = []

            def apply_async(self, args, task_id):
                self.calls.append({"args": args, "task_id": task_id})

        class FakeJobStore:
            def __init__(self):
                self.created = []

            def create_job(self, **kwargs):
                self.created.append(kwargs)

        service = self.SmokeTestService({"success": True})
        service.snapshot = {
            "available": True,
            "fresh": True,
            "created_at": "2026-06-09T10:00:00Z",
        }

        def get_snapshot():
            return service.snapshot

        service.get_fav_songs_snapshot = get_snapshot
        service.apply_fav_songs = lambda confirmed: (_ for _ in ()).throw(
            AssertionError("full apply should not run synchronously")
        )
        task = FakeApplyTask()
        store = FakeJobStore()
        monkeypatch.setattr(ws, "CELERY_AVAILABLE", True)
        monkeypatch.setattr(ws, "apply_curation", task, raising=False)
        monkeypatch.setattr(ws, "get_job_store", lambda: store)
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: service)

        smoke_response = client.post(
            "/api/curation/smoke-test", json={"scope": "fav_songs"}
        )
        token = smoke_response.get_json()["smoke_test_token"]

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": token,
            },
        )

        assert response.status_code == 202
        payload = response.get_json()
        assert payload["status"] == "queued"
        assert payload["success"] is True
        assert payload["job_id"].startswith("curation-apply-")
        assert len(store.created) == 1
        created = store.created[0]
        assert created["job_id"] == payload["job_id"]
        assert created["job_type"] == "curation_apply"
        assert created["payload"] == {
            "scope": "fav_songs",
            "snapshot_created_at": "2026-06-09T10:00:00Z",
        }
        assert created["user_agent"].startswith("Werkzeug/")
        assert created["client_ip"] == "127.0.0.1"
        assert task.calls == [
            {
                "args": [payload["job_id"], "fav_songs"],
                "task_id": payload["job_id"],
            }
        ]
        assert ws._curation_smoke_tokens[token]["used"] is True

    def test_curation_apply_accepts_small_apply_limit(self, client, monkeypatch):
        import src.web_server as ws

        class FakeApplyTask:
            def __init__(self):
                self.calls = []

            def apply_async(self, args, task_id):
                self.calls.append({"args": args, "task_id": task_id})

        class FakeJobStore:
            def __init__(self):
                self.created = []

            def create_job(self, **kwargs):
                self.created.append(kwargs)

        class FakeService:
            def get_fav_songs_snapshot(self):
                return {
                    "available": True,
                    "fresh": True,
                    "created_at": "2026-06-09T10:00:00Z",
                }

            def run_fav_songs_smoke_test(self):
                return {"success": True}

            def apply_fav_songs(self, confirmed):
                raise AssertionError("full apply should not run synchronously")

        task = FakeApplyTask()
        store = FakeJobStore()
        monkeypatch.setattr(ws, "CELERY_AVAILABLE", True)
        monkeypatch.setattr(ws, "apply_curation", task, raising=False)
        monkeypatch.setattr(ws, "get_job_store", lambda: store)
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())
        token = client.post(
            "/api/curation/smoke-test", json={"scope": "fav_songs"}
        ).get_json()["smoke_test_token"]

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": token,
                "max_tracks": 1,
            },
        )

        payload = response.get_json()
        assert response.status_code == 202
        assert store.created[0]["payload"]["max_tracks"] == 1
        assert task.calls == [
            {
                "args": [payload["job_id"], "fav_songs", 1],
                "task_id": payload["job_id"],
            }
        ]

    def test_curation_apply_rejects_invalid_small_apply_limit(self, client):
        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": "token",
                "max_tracks": 0,
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "max_tracks must be a positive integer"

    def test_curation_apply_queue_failure_keeps_smoke_test_token_reusable(
        self, client, monkeypatch
    ):
        import src.web_server as ws

        class FakeApplyTask:
            def apply_async(self, args, task_id):
                raise RuntimeError("queue offline")

        class FakeJobStore:
            def __init__(self):
                self.status_updates = []

            def create_job(self, **kwargs):
                self.job_id = kwargs["job_id"]

            def update_job_status(self, job_id, new_status, error_message=None, error_code=None):
                self.status_updates.append(
                    {
                        "job_id": job_id,
                        "status": new_status,
                        "error_message": error_message,
                        "error_code": error_code,
                    }
                )

        class FakeService:
            def get_fav_songs_snapshot(self):
                return {
                    "available": True,
                    "fresh": True,
                    "created_at": "2026-06-09T10:00:00Z",
                }

            def apply_fav_songs(self, confirmed):
                raise AssertionError("full apply should not run synchronously")

            def run_fav_songs_smoke_test(self):
                return {"success": True}

        store = FakeJobStore()
        monkeypatch.setattr(ws, "CELERY_AVAILABLE", True)
        monkeypatch.setattr(ws, "apply_curation", FakeApplyTask(), raising=False)
        monkeypatch.setattr(ws, "get_job_store", lambda: store)
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())
        token = client.post(
            "/api/curation/smoke-test", json={"scope": "fav_songs"}
        ).get_json()["smoke_test_token"]

        body = {
            "scope": "fav_songs",
            "confirmed": True,
            "mini_test_passed": True,
            "smoke_test_token": token,
        }
        first = client.post("/api/curation/apply", json=body)
        second = client.post("/api/curation/apply", json=body)

        assert first.status_code == 503
        assert second.status_code == 503
        assert first.get_json()["error"] == "Curation apply queue unavailable"
        assert second.get_json()["error"] == "Curation apply queue unavailable"
        assert ws._curation_smoke_tokens[token]["used"] is False
        assert store.status_updates[-1]["status"] == "failed"
        assert store.status_updates[-1]["error_code"] == "CURATION_QUEUE_ERROR"

    def test_curation_apply_rejects_expired_smoke_test_token(self, client, monkeypatch):
        import src.web_server as ws

        ws._curation_smoke_tokens["expired-token"] = {
            "scope": "fav_songs",
            "snapshot_created_at": "2026-06-09T10:00:00Z",
            "success": True,
            "expires_at": ws.time.time() - 1,
            "used": False,
        }

        class FakeService:
            def get_fav_songs_snapshot(self):
                raise AssertionError("expired token should fail before snapshot lookup")

            def apply_fav_songs(self, confirmed):
                raise AssertionError("full apply should not run synchronously")

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": "expired-token",
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == (
            "Smoke-test token expired; run a new smoke test"
        )

    def test_curation_apply_rejects_snapshot_mismatch_token(self, client, monkeypatch):
        class FakeService:
            snapshot_created_at = "2026-06-09T10:00:00Z"

            def get_fav_songs_snapshot(self):
                return {
                    "available": True,
                    "fresh": True,
                    "created_at": self.snapshot_created_at,
                }

            def run_fav_songs_smoke_test(self):
                return {"success": True}

            def apply_fav_songs(self, confirmed):
                raise AssertionError("full apply should not run synchronously")

        service = FakeService()
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: service)
        token = client.post(
            "/api/curation/smoke-test", json={"scope": "fav_songs"}
        ).get_json()["smoke_test_token"]
        service.snapshot_created_at = "2026-06-09T10:05:00Z"

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": token,
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == (
            "Smoke-test token does not match current snapshot; run a new smoke test"
        )

    def test_curation_apply_requires_true_confirmation_after_gate(
        self, client, monkeypatch
    ):
        class FakeService:
            def get_fav_songs_snapshot(self):
                return {"available": True, "fresh": True}

            def apply_fav_songs(self, confirmed):
                raise AssertionError("full apply should not run synchronously")

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": False,
                "mini_test_passed": True,
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Confirmation required"

    def test_curation_apply_rejects_stale_snapshot_after_gate(
        self, client, monkeypatch
    ):
        import src.web_server as ws

        ws._curation_smoke_tokens["valid-token"] = {
            "scope": "fav_songs",
            "snapshot_created_at": "2026-06-09T10:00:00Z",
            "success": True,
            "expires_at": ws.time.time() + 60,
            "used": False,
        }

        class FakeService:
            def get_fav_songs_snapshot(self):
                return {
                    "available": True,
                    "fresh": False,
                    "created_at": "2026-06-09T10:00:00Z",
                }

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": "valid-token",
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Fresh curation snapshot required"

    def test_curation_apply_rejects_missing_snapshot_after_gate(
        self, client, monkeypatch
    ):
        import src.web_server as ws

        ws._curation_smoke_tokens["valid-token"] = {
            "scope": "fav_songs",
            "snapshot_created_at": "2026-06-09T10:00:00Z",
            "success": True,
            "expires_at": ws.time.time() + 60,
            "used": False,
        }

        class FakeService:
            def get_fav_songs_snapshot(self):
                return {
                    "available": False,
                    "fresh": False,
                    "created_at": "2026-06-09T10:00:00Z",
                }

        monkeypatch.setattr("src.web_server._get_curation_service", lambda: FakeService())

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": "valid-token",
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Fresh curation snapshot required"

    def test_curation_apply_rejects_string_confirmation_without_calling_service(
        self, client, monkeypatch
    ):
        service = self.RecordingService()
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: service)

        response = client.post(
            "/api/curation/apply",
            json={"scope": "fav_songs", "confirmed": "false"},
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "confirmed must be a boolean"
        assert service.confirmed_values == []

    def test_curation_apply_returns_503_when_service_unavailable(
        self, client, monkeypatch
    ):
        import src.web_server as ws

        ws._curation_smoke_tokens["valid-token"] = {
            "scope": "fav_songs",
            "snapshot_created_at": "2026-06-09T10:00:00Z",
            "success": True,
            "expires_at": ws.time.time() + 60,
            "used": False,
        }
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.post(
            "/api/curation/apply",
            json={
                "scope": "fav_songs",
                "confirmed": True,
                "mini_test_passed": True,
                "smoke_test_token": "valid-token",
            },
        )

        assert response.status_code == 503
        assert response.get_json()["error"] == "Curation service unavailable"

    def test_curation_smoke_test_returns_success_response(self, client, monkeypatch):
        service = self.SmokeTestService({"success": True})
        service.get_fav_songs_snapshot = lambda: {
            "available": True,
            "fresh": True,
            "created_at": "2026-06-09T10:00:00Z",
        }
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: service)

        response = client.post("/api/curation/smoke-test", json={"scope": "fav_songs"})

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert isinstance(payload["smoke_test_token"], str)
        assert payload["smoke_test_token"]
        assert service.calls == 1

    def test_curation_smoke_test_requires_fresh_snapshot_before_writing(
        self, client, monkeypatch
    ):
        service = self.SmokeTestService({"success": True})
        service.get_fav_songs_snapshot = lambda: {
            "available": True,
            "fresh": False,
            "created_at": "2026-06-09T10:00:00Z",
        }
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: service)

        response = client.post("/api/curation/smoke-test", json={"scope": "fav_songs"})

        assert response.status_code == 400
        assert response.get_json()["error"] == "Fresh curation snapshot required"
        assert service.calls == 0

    def test_curation_smoke_test_rejects_unsupported_scope(self, client, monkeypatch):
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.post("/api/curation/smoke-test", json={"scope": "albums"})

        assert response.status_code == 400
        assert response.get_json()["error"] == "Unsupported curation scope"

    def test_curation_smoke_test_returns_503_when_service_unavailable(
        self, client, monkeypatch
    ):
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.post("/api/curation/smoke-test", json={"scope": "fav_songs"})

        assert response.status_code == 503
        assert response.get_json()["error"] == "Curation service unavailable"

    def test_curation_smoke_test_returns_500_for_failure_result(
        self, client, monkeypatch
    ):
        service = self.SmokeTestService({"success": False, "error": "Smoke failed"})
        service.get_fav_songs_snapshot = lambda: {
            "available": True,
            "fresh": True,
            "created_at": "2026-06-09T10:00:00Z",
        }
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: service)

        response = client.post("/api/curation/smoke-test", json={"scope": "fav_songs"})

        assert response.status_code == 500
        assert response.get_json()["error"] == "Smoke failed"
        assert service.calls == 1

    def test_curation_preview_rejects_unsupported_scope(self, client, monkeypatch):
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.get("/api/curation/preview?scope=library")

        assert response.status_code == 400
        assert response.get_json()["error"] == "Unsupported curation scope"

    def test_curation_apply_rejects_unsupported_scope(self, client, monkeypatch):
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.post("/api/curation/apply", json={"scope": "library"})

        assert response.status_code == 400
        assert response.get_json()["error"] == "Unsupported curation scope"

    def test_curation_preview_returns_503_when_service_unavailable(
        self, client, monkeypatch
    ):
        monkeypatch.setattr("src.web_server._get_curation_service", lambda: None)

        response = client.get("/api/curation/preview?scope=fav_songs")

        assert response.status_code == 503
        assert response.get_json()["error"] == "Curation service unavailable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
