import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TOKEN = "fixture-only-access-token-0123456789abcdef"
PID = "0123456789ABCDEF"
TID = "FEDCBA9876543210"


def forbidden(*args, **kwargs):
    raise AssertionError("Fixture server forbids external connections and subprocesses")


socket.socket.connect = forbidden
socket.create_connection = forbidden
subprocess.Popen = forbidden
fixture = Path(os.environ["CURATOR_FIXTURE_DIR"])
os.chdir(fixture)
os.environ.update(CURATOR_ACCESS_TOKEN=TOKEN, WEB_HOST="127.0.0.1", WEB_PORT="4000",
                  LOG_DIR=str(fixture / "logs"), DATABASE_URL=f"sqlite:///{fixture}/fixture.db")
import src.web_server as ws
from src.web_access import load_access_settings
from werkzeug.serving import make_server


class Service:
    def get_seed_playlist_sources(self):
        return [dict(persistent_id=PID, name="<img src=x onerror=alert(1)> Same name", track_count=101),
                dict(persistent_id="0000000000000002", name="Same name", track_count=101)]

    def get_seed_playlist_source_tracks(self, playlist_id):
        return [dict(persistent_id=TID, name="Fixture seed <script>alert(1)</script>", artist="Fixture artist")]

    def preview_seed_playlist(self, playlist_id, seed_track_id, limit=30):
        return dict(version=1, source=dict(source_id=playlist_id), seed=dict(persistent_id=seed_track_id),
                    limit=limit, tracks=[dict(persistent_id=TID, reason="selected_seed")],
                    output=dict(name="Fixture seed playlist", track_ids=[TID]), fingerprint="fixture-only")

    def preview_playlist_splits(self, playlist_ids):
        return dict(version=1, sources=[dict(source_id=pid, parts=[dict(name="Part 01", track_ids=[TID])]) for pid in playlist_ids], fingerprint="fixture-only")

    def apply_seed_playlist(self, plan, confirmed=False):
        return dict(success=True, parts=[dict(status="complete", confirmed_count=1)])

    def apply_playlist_splits(self, plan, confirmed=False):
        return dict(success=False, error="Unresolved write intent; manual recovery required",
                    parts=[dict(status="unresolved", confirmed_count=1)], unresolved=[dict(action="add")])


class OrganizationClassifier:
    enable_genre_enrichment = True


class OrganizationManager:
    def preview_playlist_organization(self, playlist_ids, classifier):
        assert classifier.enable_genre_enrichment is False
        return dict(version=1, selected_ids=playlist_ids, fingerprint="fixture-only",
                    operations=[dict(source_id=pid, action="move", reason="genre_assignment",
                                     target_components=["Genre", "Jazz"]) for pid in playlist_ids])

    def apply_playlist_organization(self, plan, confirmed=False):
        return dict(success=True, moved=len(plan["selected_ids"]), applied=len(plan["selected_ids"]),
                    failed=0, skipped=0,
                    results=[dict(source_id=pid, status="moved") for pid in plan["selected_ids"]])


ws._get_curation_service = lambda: Service()
ws._get_playlist_manager = lambda: OrganizationManager()
ws._get_playlist_classifier = lambda: OrganizationClassifier()
ws.setup_database = lambda: None
ws.app._db_initialized = True
ws.app.view_functions["health"] = lambda: ws.jsonify(platform="darwin", playlists_count=2, tracks_count=202)
ws.app.view_functions["history"] = lambda: ws.jsonify(runs=[], jobs=[])
server = make_server("127.0.0.1", 0, ws.app, threaded=True)
ws.app.extensions["web_access"] = load_access_settings("127.0.0.1", server.server_port)
print(json.dumps(dict(origin=f"http://127.0.0.1:{server.server_port}")), flush=True)
server.serve_forever()
