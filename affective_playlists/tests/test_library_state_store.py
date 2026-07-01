from pathlib import Path

from src.db import init_db
from src.library_state_store import LibraryStateStore


def make_store(tmp_path: Path) -> LibraryStateStore:
    _, session_factory = init_db(f"sqlite:///{tmp_path / 'state.db'}")
    return LibraryStateStore(session_factory())


def test_library_state_store_records_runs_and_tracks(tmp_path):
    store = make_store(tmp_path)

    run = store.create_run("enrich", target="playlist:Chill", payload={"force": False})
    store.record_track(
        "playlist:Chill",
        "path:/tmp/song.mp3",
        artist="Artist",
        title="Song",
        album="Album",
        filepath="/tmp/song.mp3",
        run_id=run.id,
        skip_reason="duplicate in batch",
    )

    runs = store.list_runs(limit=5)
    tracks = store.list_tracks(scope="playlist:Chill", limit=5)

    assert runs[0].id == run.id
    assert runs[0].status == "running"
    assert store.has_track("playlist:Chill", "path:/tmp/song.mp3") is True
    assert tracks[0].skip_reason == "duplicate in batch"


def test_library_state_store_persists_cache_entries(tmp_path):
    store = make_store(tmp_path)

    store.put_cache(
        "metadata-query:test",
        "metadata_query",
        {"entries": [{"field": "genre", "value": "Rock", "source": "MUSICBRAINZ"}]},
    )

    cached = store.get_cache("metadata-query:test")

    assert cached is not None
    assert cached.cache_type == "metadata_query"
    assert cached.cache_value["entries"][0]["value"] == "Rock"
