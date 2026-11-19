"""Local web boundary tests: no Music, real library, or external services."""
import importlib
from unittest.mock import Mock

import pytest

TOKEN = "fixture-only-access-token-0123456789abcdef"
ORIGIN = "http://127.0.0.1:4000"


@pytest.fixture
def secured_web(monkeypatch, tmp_path):
    monkeypatch.setenv("CURATOR_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("WEB_HOST", "127.0.0.1")
    monkeypatch.setenv("WEB_PORT", "4000")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'web.db'}")
    (tmp_path / "logs").mkdir()
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    ws = importlib.import_module("src.web_server")
    monkeypatch.setitem(ws.app.config, "TESTING", True)
    monkeypatch.setitem(ws.app.config, "SERVER_NAME", "127.0.0.1:4000")
    monkeypatch.delattr(ws.app, "_db_initialized", raising=False)
    for name in ("setup_database", "_get_playlist_manager", "_get_playlist_classifier",
                 "_get_curation_service", "get_job_store", "LibraryStateStore"):
        monkeypatch.setattr(ws, name, Mock(side_effect=AssertionError(f"Unexpected {name}")))
    if hasattr(ws, "_playlist_plans"):
        monkeypatch.setattr(ws, "_playlist_plans", type(ws._playlist_plans)())
    yield ws


def login(client):
    response = client.post("/unlock", data={"token": TOKEN}, headers={"Origin": ORIGIN})
    assert response.status_code == 303
    response = client.get("/api/session")
    assert response.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": response.get_json()["csrf_token"]}


def assert_no_work(ws):
    for name in ("setup_database", "_get_playlist_manager", "_get_playlist_classifier",
                 "_get_curation_service", "get_job_store", "LibraryStateStore"):
        getattr(ws, name).assert_not_called()


def test_every_api_denies_anonymous_before_work(secured_web):
    ws = secured_web
    client = ws.app.test_client()
    for rule in ws.app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        path = rule.rule.replace("<playlist_id>", "1111111111111111").replace("<job_id>", "job")
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            response = client.open(path, method=method)
            assert response.status_code == 401, (path, method, response.status_code)
    assert_no_work(ws)


@pytest.mark.parametrize("headers,environ", [
    ({"Host": "evil.test:4000"}, {}),
    ({"Host": "localhost:4000"}, {}),
    ({"Host": "127.0.0.1:5000"}, {}),
    ({"Host": "127.0.0.1:4000.evil.test"}, {}),
    ({"Origin": "null"}, {}),
    ({"Origin": "https://127.0.0.1:4000"}, {}),
    ({"Origin": "http://evil.test"}, {}),
    ({"Sec-Fetch-Site": "cross-site"}, {}),
    ({"Sec-Fetch-Site": "same-site"}, {}),
    ({"X-Forwarded-For": "127.0.0.1", "X-Forwarded-Host": "127.0.0.1:4000"},
     {"REMOTE_ADDR": "192.0.2.1"}),
    ({}, {"REMOTE_ADDR": "not-an-ip"}),
    ({}, {"REMOTE_ADDR": ""}),
])
def test_network_boundary_precedes_login_and_database(secured_web, headers, environ):
    client = secured_web.app.test_client()
    for path in ("/unlock", "/", "/api/health", "/static/js/app.js"):
        assert client.get(path, headers=headers, environ_overrides=environ).status_code == 403
    assert_no_work(secured_web)


def test_unlock_is_manual_secret_not_reflected_and_session_is_private(secured_web):
    client = secured_web.app.test_client()
    assert client.get("/").location == "/unlock"
    form = client.get("/unlock")
    assert form.status_code == 200
    assert b'type="password"' in form.data
    for headers in ({}, {"Origin": "null"}, {"Origin": "http://evil.test"}):
        assert client.post("/unlock", data={"token": TOKEN}, headers=headers).status_code == 403
    denied = client.post("/unlock", data={"token": "wrong"}, headers={"Origin": ORIGIN})
    assert denied.status_code == 401
    response = client.post("/unlock", data={"token": TOKEN}, headers={"Origin": ORIGIN})
    assert response.status_code == 303
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Expires=" in cookie
    assert TOKEN not in response.get_data(as_text=True) + str(response.headers)
    session_response = client.get("/api/session")
    assert len(session_response.json["csrf_token"]) >= 32
    assert TOKEN not in str(session_response.json)
    for response in (form, denied, session_response):
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert_no_work(secured_web)


@pytest.mark.parametrize("origin,csrf", [(None, True), ("null", True),
    ("http://evil.test", True), (ORIGIN, False), (ORIGIN, "wrong")])
def test_authenticated_write_requires_origin_and_csrf_before_db(secured_web, origin, csrf):
    client = secured_web.app.test_client()
    valid = login(client)
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if csrf:
        headers["X-CSRF-Token"] = valid["X-CSRF-Token"] if csrf is True else csrf
    for path in ("/api/settings", "/api/curation/smoke-test", "/api/playlist-plans/seed/apply"):
        assert client.post(path, json={}, headers=headers).status_code == 403
    assert_no_work(secured_web)


def test_expired_and_tampered_sessions_cannot_read_or_write(secured_web, monkeypatch):
    from src import web_access
    client = secured_web.app.test_client()
    headers = login(client)
    now = web_access.time.time()
    monkeypatch.setattr(web_access.time, "time", lambda: now + 3601)
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/settings", json={}, headers=headers).status_code == 401
    client.set_cookie(secured_web.app.config["SESSION_COOKIE_NAME"], "tampered")
    assert client.get("/api/health").status_code == 401
    assert_no_work(secured_web)


def test_session_rotation_revokes_previous_cookie(secured_web):
    client = secured_web.app.test_client()
    first = login(client)
    name = secured_web.app.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(name, domain="127.0.0.1").value
    login(client)
    replay = secured_web.app.test_client()
    replay.set_cookie(name, cookie, domain="127.0.0.1")
    assert replay.get("/api/session").status_code == 401
    assert replay.post("/api/settings", json={}, headers=first).status_code == 401
    assert_no_work(secured_web)


def test_session_rotation_invalidates_old_csrf(secured_web):
    client = secured_web.app.test_client()
    first, second = login(client), login(client)
    assert first != second
    assert client.post("/api/settings", json={}, headers=first).status_code == 403
    assert_no_work(secured_web)


@pytest.mark.parametrize("token", [None, "", "short", "x" * 31, " " * 40])
def test_startup_fails_closed_without_strong_token(secured_web, monkeypatch, token):
    if token is None:
        monkeypatch.delenv("CURATOR_ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("CURATOR_ACCESS_TOKEN", token)
    run = Mock()
    monkeypatch.setattr(secured_web.app, "run", run)
    with pytest.raises(RuntimeError, match="CURATOR_ACCESS_TOKEN"):
        secured_web.run_server()
    run.assert_not_called()
    assert_no_work(secured_web)


@pytest.mark.parametrize("kwargs", [{"host": "0.0.0.0"}, {"host": "::"},
    {"host": "evil.test"}, {"debug": True}, {"port": 0}, {"port": True}])
def test_unsafe_startup_options_fail_before_effects(secured_web, kwargs):
    with pytest.raises((ValueError, RuntimeError)):
        secured_web.run_server(**kwargs)
    assert_no_work(secured_web)


def test_valid_startup_uses_only_loopback_without_debugger(secured_web, monkeypatch):
    # All startup effects are mocked; this never starts a listener or reads Music.
    ws = secured_web
    run, database, music = Mock(), Mock(), Mock()
    monkeypatch.setattr(ws.app, "run", run)
    monkeypatch.setattr(ws, "setup_database", database)
    monkeypatch.setattr(ws, "_init_playlists_from_apple_music", music)
    monkeypatch.setitem(ws.app.extensions, "web_access", ws.app.extensions["web_access"])
    ws.run_server(host="localhost", port=4567)
    run.assert_called_once_with(host="127.0.0.1", port=4567, debug=False,
                                use_reloader=False, use_debugger=False)
    database.assert_called_once()
    music.assert_called_once()
    assert ws.app.extensions["web_access"].origin == "http://localhost:4567"


@pytest.mark.parametrize("host,authority,peer", [
    ("localhost", "localhost:4567", "127.0.0.1"),
    ("::1", "[::1]:4567", "::1"),
])
def test_configured_host_port_and_loopback_ipv6(host, authority, peer, monkeypatch):
    from flask import Flask
    from src.web_access import install_web_access, load_access_settings
    monkeypatch.setenv("CURATOR_ACCESS_TOKEN", TOKEN)
    app = Flask(__name__)
    install_web_access(app, load_access_settings(host, 4567))
    client = app.test_client()
    response = client.post("/unlock", base_url=f"http://{authority}", data={"token": TOKEN},
                           headers={"Origin": f"http://{authority}"},
                           environ_overrides={"REMOTE_ADDR": peer})
    assert response.status_code == 303
    assert client.get("/unlock", base_url=f"http://{authority}",
                      environ_overrides={"REMOTE_ADDR": peer}).status_code == 200
    assert client.get("/unlock", base_url="http://127.0.0.1:4000").status_code == 403


def test_unlock_extra_fields_json_query_and_oversize_denied(secured_web):
    client = secured_web.app.test_client()
    headers = {"Origin": ORIGIN}
    assert client.post("/unlock", json={"token": TOKEN}, headers=headers).status_code == 400
    assert client.post("/unlock", data={"token": TOKEN, "extra": "no"}, headers=headers).status_code == 400
    assert client.post("/unlock?token=not-a-secret", data={"token": TOKEN}, headers=headers).status_code == 400
    assert client.post("/unlock", data={"token": "x" * 5000}, headers=headers).status_code == 413
    assert client.get("/api/session").status_code == 401
    assert_no_work(secured_web)


def test_authenticated_reads_still_reject_host_origin_and_fetch_metadata(secured_web):
    client = secured_web.app.test_client()
    login(client)
    for headers in ({"Host": "evil.test:4000"}, {"Origin": "null"},
                    {"Sec-Fetch-Site": "cross-site"}):
        assert client.get("/api/health", headers=headers).status_code == 403
    assert_no_work(secured_web)


def test_import_without_token_precedes_project_startup_imports(secured_web, monkeypatch):
    import runpy
    monkeypatch.delenv("CURATOR_ACCESS_TOKEN")
    import builtins
    original_import = builtins.__import__
    project_imports = []

    def guarded_import(name, *args, **kwargs):
        if name.startswith("src.") and name != "src.web_access":
            project_imports.append(name)
            raise AssertionError("Project import before access validation")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(RuntimeError, match="CURATOR_ACCESS_TOKEN"):
        runpy.run_path(secured_web.__file__, run_name="access_import_test")
    assert project_imports == []
