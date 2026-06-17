from src.curation_snapshot import CurationSnapshotStore
from src.curation_service import CurationService


def test_snapshot_store_saves_and_loads_scope(tmp_path):
    store = CurationSnapshotStore(tmp_path / "curation_snapshots.json")
    payload = {
        "scope": "fav_songs",
        "total_assignments": 2,
        "total_genres": 1,
        "total_changes": 4,
        "total_skipped": 0,
        "grouped": {"Hip Hop": {"Frolic": [{"item_id": "a"}]}},
    }

    saved = store.save_snapshot("fav_songs", payload)
    loaded = store.load_snapshot("fav_songs")

    assert saved["scope"] == "fav_songs"
    assert saved["total_assignments"] == 2
    assert "created_at" in saved
    assert loaded == saved


def test_snapshot_store_returns_empty_state_when_missing(tmp_path):
    store = CurationSnapshotStore(tmp_path / "curation_snapshots.json")

    loaded = store.load_snapshot("fav_songs")

    assert loaded["scope"] == "fav_songs"
    assert loaded["available"] is False
    assert loaded["total_assignments"] == 0
    assert loaded["total_genres"] == 0
    assert loaded["total_changes"] == 0
    assert loaded["total_skipped"] == 0


def test_snapshot_store_marks_stale_snapshot(tmp_path):
    store = CurationSnapshotStore(tmp_path / "curation_snapshots.json", ttl_seconds=1)
    saved = store.save_snapshot("fav_songs", {"scope": "fav_songs"})
    saved["created_at"] = "2020-01-01T00:00:00+00:00"
    store._write_all({"fav_songs": saved})

    loaded = store.load_snapshot("fav_songs")

    assert loaded["available"] is True
    assert loaded["fresh"] is False


def test_snapshot_store_returns_empty_state_when_malformed(tmp_path):
    path = tmp_path / "curation_snapshots.json"
    path.write_text("{bad json", encoding="utf-8")
    store = CurationSnapshotStore(path)

    loaded = store.load_snapshot("fav_songs")

    assert loaded["scope"] == "fav_songs"
    assert loaded["available"] is False
    assert loaded["fresh"] is False
    assert loaded["grouped"] == {}
    assert loaded["changes"] == []
    assert loaded["skipped_tracks"] == []


def test_snapshot_store_returns_empty_state_when_file_has_invalid_utf8(tmp_path):
    path = tmp_path / "curation_snapshots.json"
    path.write_bytes(b"\xff\xfe\x00")
    store = CurationSnapshotStore(path)

    loaded = store.load_snapshot("fav_songs")

    assert loaded["scope"] == "fav_songs"
    assert loaded["available"] is False
    assert loaded["fresh"] is False
    assert loaded["created_at"] is None
    assert loaded["total_assignments"] == 0
    assert loaded["total_genres"] == 0
    assert loaded["total_changes"] == 0
    assert loaded["total_skipped"] == 0
    assert loaded["grouped"] == {}
    assert loaded["changes"] == []
    assert loaded["skipped_tracks"] == []


class FakeSnapshotStore:
    def __init__(self):
        self.saved = []

    def load_snapshot(self, scope):
        return {"scope": scope, "available": True, "fresh": True}

    def save_snapshot(self, scope, payload):
        self.saved.append((scope, payload))
        return {**payload, "available": True, "fresh": True, "created_at": "now"}


def test_curation_service_get_fav_songs_snapshot_delegates_to_store():
    store = FakeSnapshotStore()
    service = CurationService(snapshot_store=store)

    snapshot = service.get_fav_songs_snapshot()

    assert snapshot == {"scope": "fav_songs", "available": True, "fresh": True}


def test_curation_service_refresh_fav_songs_snapshot_saves_preview_payload():
    store = FakeSnapshotStore()
    service = CurationService(snapshot_store=store)
    service.preview_fav_songs = lambda: {
        "total_assignments": 2,
        "grouped": {"Hip Hop": {"Frolic": [{"item_id": "a"}]}},
        "changes": [{"action": "copy_track"}],
        "skipped_tracks": [{"name": "Missing"}],
        "total_skipped": 1,
    }

    snapshot = service.refresh_fav_songs_snapshot()

    assert store.saved == [
        (
            "fav_songs",
            {
                "scope": "fav_songs",
                "total_assignments": 2,
                "total_genres": 1,
                "total_changes": 1,
                "total_skipped": 1,
                "grouped": {"Hip Hop": {"Frolic": [{"item_id": "a"}]}},
                "changes": [{"action": "copy_track"}],
                "skipped_tracks": [{"name": "Missing"}],
            },
        )
    ]
    assert snapshot["available"] is True
