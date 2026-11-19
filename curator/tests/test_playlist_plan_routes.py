"""Playlist plan HTTP tests using an in-memory fake service only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from unittest.mock import Mock

import pytest

from tests.test_web_access import login, secured_web

PID = "0123456789ABCDEF"
TID = "FEDCBA9876543210"
BASE = "/api/playlist-plans"


class FakeService:
    def __init__(self):
        self.plan = {"version": 1, "fingerprint": "fake-reviewed-fingerprint",
                     "sources": [{"source_id": PID, "parts": [{"track_ids": [TID, TID]}]}]}
        self.calls = []
        self.writes = []
        self.result = {"success": True, "confirmed": True,
                       "parts": [{"status": "complete", "confirmed_count": 2}]}

    def get_seed_playlist_sources(self):
        self.calls.append(("sources",))
        return [{"persistent_id": PID, "name": "Source", "track_count": 2}]

    def get_seed_playlist_source_tracks(self, playlist_id):
        self.calls.append(("tracks", playlist_id))
        return [{"persistent_id": TID, "name": "Track"}]

    def preview_seed_playlist(self, playlist_id, seed_track_id, limit=30):
        self.calls.append(("seed", playlist_id, seed_track_id, limit))
        return self.plan

    def preview_playlist_splits(self, playlist_ids):
        self.calls.append(("split", playlist_ids))
        return self.plan

    def apply_seed_playlist(self, plan, confirmed=False):
        self.writes.append(("seed", plan, confirmed))
        return self.result

    def apply_playlist_splits(self, plan, confirmed=False):
        self.writes.append(("split", plan, confirmed))
        return self.result


@pytest.fixture
def plan_api(secured_web, monkeypatch):
    service = FakeService()
    monkeypatch.setattr(secured_web, "_get_curation_service", Mock(return_value=service))
    client = secured_web.app.test_client()
    headers = login(client)
    yield secured_web, service, client, headers
    secured_web.setup_database.assert_not_called()


def preview(client, headers, kind="seed", **extra):
    body = {"playlist_id": PID, "seed_track_id": TID} if kind == "seed" else {"playlist_ids": [PID]}
    response = client.post(f"{BASE}/{kind}/preview", json={**body, **extra}, headers=headers)
    assert response.status_code == 200, response.json
    return response.json


def apply(client, headers, token, kind="seed", **extra):
    return client.post(f"{BASE}/{kind}/apply", json={"plan_id": token, "confirmed": True, **extra}, headers=headers)


def test_source_reads_use_exact_service_methods(plan_api):
    ws, service, client, _ = plan_api
    sources = client.get(f"{BASE}/sources")
    tracks = client.get(f"{BASE}/source/{PID}/tracks")
    assert sources.status_code == tracks.status_code == 200
    assert sources.json == [{"persistent_id": PID, "name": "Source", "track_count": 2}]
    assert tracks.json == [{"persistent_id": TID, "name": "Track"}]
    assert service.calls == [("sources",), ("tracks", PID)]
    assert service.writes == []


@pytest.mark.parametrize("kind", ["seed", "split"])
@pytest.mark.parametrize("stale", [False, True])
def test_http_exact_plan_with_real_service_and_fake_music(secured_web, monkeypatch, tmp_path, kind, stale):
    from src.curation_service import CurationService
    from tests.test_curation_service import SeedMusic, SOURCE_ID

    music = SeedMusic()
    service = CurationService(apple_music=music, split_journal_path=tmp_path / "fixture-journal")
    service.initialize_playlist_split_journal()
    monkeypatch.setattr(secured_web, "_get_curation_service", lambda: service)
    client = secured_web.app.test_client()
    headers = login(client)
    body = ({"playlist_id": SOURCE_ID, "seed_track_id": "000000000000000A", "limit": 20}
            if kind == "seed" else {"playlist_ids": [SOURCE_ID]})
    response = client.post(f"{BASE}/{kind}/preview", json=body, headers=headers)
    assert response.status_code == 200
    assert music.writes == []
    if stale:
        music.playlists[SOURCE_ID]["tracks"].append("0000000000000010")
    result = apply(client, headers, response.json["plan_id"], kind)
    assert result.status_code == (409 if stale else 200)
    assert result.json["success"] is not stale
    assert (music.writes == []) is stale
    assert apply(client, headers, response.json["plan_id"], kind).status_code == 409
    secured_web.setup_database.assert_not_called()


@pytest.mark.parametrize("kind", ["seed", "split"])
def test_preview_deepcopy_exact_plan_apply_once(plan_api, kind):
    ws, service, client, headers = plan_api
    expected = deepcopy(service.plan)
    reviewed = preview(client, headers, kind)
    assert reviewed["plan"] == expected
    assert reviewed["expires_in"] == 900
    assert len(reviewed["plan_id"]) == 43
    service.plan["sources"][0]["parts"][0]["track_ids"].append("mutated")
    reviewed["plan"]["sources"].clear()  # Client mutation also cannot change the reviewed snapshot.
    response = apply(client, headers, reviewed["plan_id"], kind)
    assert response.status_code == 200
    assert response.json == service.result
    assert service.writes == [(kind, expected, True)]
    assert apply(client, headers, reviewed["plan_id"], kind).status_code == 409
    assert len(service.writes) == 1
    assert ws._playlist_plans.records == {}


def test_seed_default_and_explicit_limit(plan_api):
    _, service, client, headers = plan_api
    preview(client, headers)
    preview(client, headers, limit=1)
    assert service.calls == [("seed", PID, TID, 30), ("seed", PID, TID, 1)]


@pytest.mark.parametrize("confirmed", [False, None, 0, 1, "true", "false", [], {}])
def test_literal_true_required_without_claim_or_service_call(plan_api, confirmed):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    ws._get_curation_service.reset_mock()
    response = apply(client, headers, token, confirmed=confirmed)
    assert response.status_code == 400
    ws._get_curation_service.assert_not_called()
    assert token in ws._playlist_plans.records
    assert service.writes == []
    assert apply(client, headers, token).status_code == 200


@pytest.mark.parametrize("kind,body", [
    ("seed", {}), ("seed", []), ("seed", None),
    ("seed", {"playlist_id": PID, "seed_track_id": TID, "limit": True}),
    ("seed", {"playlist_id": PID, "seed_track_id": TID, "limit": 0}),
    ("seed", {"playlist_id": PID, "seed_track_id": TID, "limit": 31}),
    ("seed", {"playlist_id": PID, "seed_track_id": TID, "limit": "30"}),
    ("seed", {"playlist_id": "invalid", "seed_track_id": TID}),
    ("seed", {"playlist_id": PID, "seed_track_id": 123}),
    ("seed", {"playlist_id": PID, "seed_track_id": TID, "journal_path": "/tmp/not-allowed"}),
    ("split", {"playlist_ids": []}), ("split", {"playlist_ids": PID}),
    ("split", {"playlist_ids": [PID] * 101}), ("split", {"playlist_ids": [False]}),
    ("split", {"playlist_ids": [PID], "plan": {}}),
])
def test_preview_rejects_invalid_or_extra_fields_before_service(plan_api, kind, body):
    ws, service, client, headers = plan_api
    response = client.post(f"{BASE}/{kind}/preview", json=body, headers=headers)
    assert response.status_code == 400
    ws._get_curation_service.assert_not_called()
    assert not ws._playlist_plans.records


@pytest.mark.parametrize("extra", [{"plan": {}}, {"split_journal_path": "/tmp/x"},
    {"journal_path": "/tmp/x"}, {"initialize": True}, {"reset": True}, {"unexpected": 1}])
def test_apply_rejects_caller_plan_paths_and_extra_fields(plan_api, extra):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    ws._get_curation_service.reset_mock()
    assert apply(client, headers, token, **extra).status_code == 400
    ws._get_curation_service.assert_not_called()
    assert token in ws._playlist_plans.records
    assert service.writes == []


@pytest.mark.parametrize("raw,status", [
    ("{bad", 400), ("[]", 400), ("null", 400),
    ('{"playlist_ids": [], "playlist_ids": ["' + PID + '"]}', 400),
    ('{"playlist_ids": NaN}', 400), ('{"playlist_ids": Infinity}', 400),
    (b"\xff", 400), ("[" * 1500 + "]" * 1500, 400),
    ('{"playlist_ids": ["' + "A" * (16 * 1024) + '"]}', 413),
])
def test_malformed_duplicate_nonfinite_and_oversize_json(plan_api, raw, status):
    ws, service, client, headers = plan_api
    response = client.post(f"{BASE}/split/preview", data=raw, content_type="application/json", headers=headers)
    assert response.status_code == status
    ws._get_curation_service.assert_not_called()


def test_denied_access_cannot_claim_a_reviewed_plan(plan_api):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    ws._get_curation_service.reset_mock()
    for denied_headers in ({}, {"Origin": headers["Origin"]},
                           {**headers, "Origin": "null"}):
        assert apply(client, denied_headers, token).status_code == 403
    ws._get_curation_service.assert_not_called()
    assert token in ws._playlist_plans.records
    assert service.writes == []


def test_chunked_oversize_json_is_bounded_without_content_length(plan_api):
    import io
    ws, _, client, headers = plan_api
    body = b'{"playlist_ids":["' + b"A" * 17000 + b'"]}'
    response = client.post(f"{BASE}/split/preview", content_type="application/json", headers=headers,
                           environ_overrides={"wsgi.input": io.BytesIO(body),
                                              "wsgi.input_terminated": True, "CONTENT_LENGTH": ""})
    assert response.status_code == 413
    ws._get_curation_service.assert_not_called()


@pytest.mark.parametrize("token", [None, 1, [], {}, "", "short", "x" * 1000])
def test_invalid_plan_token_shape_is_rejected_without_service(plan_api, token):
    ws, service, client, headers = plan_api
    assert apply(client, headers, token).status_code == 400
    ws._get_curation_service.assert_not_called()
    assert service.writes == []


def test_preview_read_failures_do_not_produce_applicable_tokens(plan_api, monkeypatch):
    ws, service, client, headers = plan_api
    monkeypatch.setattr(service, "preview_seed_playlist", Mock(side_effect=ValueError("missing seed")))
    response = client.post(f"{BASE}/seed/preview", json={"playlist_id": PID, "seed_track_id": TID}, headers=headers)
    assert response.status_code == 400
    assert "plan_id" not in response.json
    assert not ws._playlist_plans.records
    monkeypatch.setattr(ws, "_get_curation_service", Mock(return_value=None))
    assert client.get(f"{BASE}/sources").status_code == 503
    assert client.post(f"{BASE}/split/preview", json={"playlist_ids": [PID]}, headers=headers).status_code == 503
    assert not ws._playlist_plans.records


def test_tampered_apply_json_never_claims(plan_api):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    ws._get_curation_service.reset_mock()
    for raw in (f'{{"plan_id":"{token}","confirmed":false,"confirmed":true}}',
                f'{{"plan_id":"{token}","confirmed":true,"padding":"' + "A" * 17000 + '"}'):
        assert client.post(f"{BASE}/seed/apply", data=raw, content_type="application/json", headers=headers).status_code in (400, 413)
    ws._get_curation_service.assert_not_called()
    assert token in ws._playlist_plans.records


@pytest.mark.parametrize("path", ["/sources?path=/tmp/x", f"/source/{PID}/tracks?limit=1", "/source/invalid/tracks"])
def test_read_boundaries_reject_extra_inputs(plan_api, path):
    ws, _, client, _ = plan_api
    assert client.get(BASE + path).status_code == 400
    ws._get_curation_service.assert_not_called()


def test_no_http_journal_initialization_or_query_parameters(plan_api):
    ws, _, client, headers = plan_api
    for endpoint in ("initialize", "reset", "journal", "split/initialize"):
        assert client.post(f"{BASE}/{endpoint}", json={}, headers=headers).status_code == 404
    for endpoint in ("seed/preview", "seed/apply"):
        assert client.post(f"{BASE}/{endpoint}?journal_path=/tmp/x", json={}, headers=headers).status_code == 400
    assert client.get(f"{BASE}/sources", data="body").status_code == 400
    ws._get_curation_service.assert_not_called()


def test_expiry_wrong_session_wrong_kind_and_random_id_fail_without_writer(plan_api, monkeypatch):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    other = ws.app.test_client()
    other_headers = login(other)
    ws._get_curation_service.reset_mock()
    assert apply(other, other_headers, token).status_code == 409
    assert apply(client, headers, token, "split").status_code == 409
    assert apply(client, headers, "z" * 43).status_code == 409
    assert token in ws._playlist_plans.records
    now = ws.time.monotonic()
    monkeypatch.setattr(ws.time, "monotonic", lambda: now + 901)
    assert apply(client, headers, token).status_code == 409
    ws._get_curation_service.assert_not_called()
    assert service.writes == []


def test_latest_plan_per_kind_and_session(plan_api):
    ws, _, client, headers = plan_api
    first = preview(client, headers)["plan_id"]
    split = preview(client, headers, "split")["plan_id"]
    second = preview(client, headers)["plan_id"]
    assert set(ws._playlist_plans.records) == {split, second}
    assert apply(client, headers, first).status_code == 409
    assert apply(client, headers, split, "split").status_code == 200
    assert apply(client, headers, second).status_code == 200


@pytest.mark.parametrize("report", [
    {"success": False, "parts": [], "error": "Source changed or plan was modified; preview again"},
    {"success": False, "parts": [{"status": "unresolved", "confirmed_count": 1}],
     "unresolved": [{"action": "add", "playlist_id": PID}], "error": "Unresolved write intent; manual recovery required"},
    {"success": False, "parts": [{"status": "not_started"}], "error": "Journal not initialized"},
])
@pytest.mark.parametrize("kind", ["seed", "split"])
def test_service_failures_preserve_honest_reports_and_consume_token(plan_api, report, kind):
    _, service, client, headers = plan_api
    service.result = report
    token = preview(client, headers, kind)["plan_id"]
    response = apply(client, headers, token, kind)
    assert response.status_code == 409
    assert response.json == report
    assert apply(client, headers, token, kind).status_code == 409
    assert len(service.writes) == 1


def test_uncertain_exception_is_not_automatically_resubmitted(plan_api, monkeypatch):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    writer = Mock(side_effect=RuntimeError("unknown write outcome"))
    monkeypatch.setattr(service, "apply_seed_playlist", writer)
    assert apply(client, headers, token).status_code == 500
    response = apply(client, headers, token)
    assert response.status_code == 409
    assert response.json["success"] is False
    writer.assert_called_once()


def test_unavailable_service_consumes_claimed_token(plan_api, monkeypatch):
    ws, _, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    monkeypatch.setattr(ws, "_get_curation_service", Mock(return_value=None))
    assert apply(client, headers, token).status_code == 503
    assert apply(client, headers, token).status_code == 409
    ws._get_curation_service.assert_called_once()


def test_concurrent_requests_only_one_invokes_writer(plan_api, monkeypatch):
    ws, service, client, headers = plan_api
    token = preview(client, headers)["plan_id"]
    entered, release = Event(), Event()
    calls = []

    def writer(plan, confirmed=False):
        calls.append((plan, confirmed))
        entered.set()
        assert release.wait(5)
        return service.result

    monkeypatch.setattr(service, "apply_seed_playlist", writer)
    other = ws.app.test_client()
    name = ws.app.config["SESSION_COOKIE_NAME"]
    other.set_cookie(name, client.get_cookie(name, domain="127.0.0.1").value, domain="127.0.0.1")
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(apply, client, headers, token)
        try:
            assert entered.wait(5)
            assert apply(other, headers, token).status_code == 409
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200
    assert len(calls) == 1
    assert calls[0][1] is True


def test_storage_count_byte_and_expiry_bounds(plan_api, monkeypatch):
    ws, _, _, _ = plan_api
    store = ws._playlist_plans
    tokens = [store.put(str(i), "seed", {"test": i})[0] for i in range(store.max_entries + 2)]
    assert len(store.records) == store.max_entries
    assert tokens[0] not in store.records
    monkeypatch.setattr(store, "max_total_bytes", 100)
    store.put("other", "seed", {"test": "a" * 70})
    assert sum(record["size"] for record in store.records.values()) <= 100
    now = ws.time.monotonic()
    monkeypatch.setattr(ws.time, "monotonic", lambda: now + 901)
    last, _ = store.put("last", "split", {})
    assert set(store.records) == {last}


def test_oversize_plan_is_not_stored_or_truncated(plan_api):
    ws, service, client, headers = plan_api
    service.plan = {"large": "a" * ws._playlist_plans.max_plan_bytes}
    response = client.post(f"{BASE}/split/preview", json={"playlist_ids": [PID]}, headers=headers)
    assert response.status_code == 413
    assert not ws._playlist_plans.records
    assert service.writes == []
