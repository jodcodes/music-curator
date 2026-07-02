import logging

from src.metadata_fill import MetadataFiller


class FakeDetector:
    def is_downloaded(self, filepath):
        return True


class RealisticFakeDetector:
    def is_downloaded(self, filepath):
        return bool(filepath and str(filepath).startswith("/local/"))


class FakeTagManager:
    def is_format_supported(self, filepath):
        return filepath.lower().endswith((".mp3", ".flac", ".ogg", ".oga", ".m4a", ".m4b"))

    def read_tags(self, filepath):
        return {
            "artist": "Artist",
            "title": "Song",
            "album": "Album",
            "musicbrainz_release_id": "release-1",
        }

    def write_tags(self, filepath, tags, force):
        return True


class FakeEnriched:
    entries = {}


class FakeEnricher:
    def enrich_track(self, filepath, current_tags, track_id, force):
        return FakeEnriched()


class FakeQueryOrchestrator:
    def query_all_sources(self, artist, title):
        return []


class FakeCoverArtManager:
    def __init__(self):
        self.calls = []

    def enrich_with_cover_art(self, filepath, mbid=None, artist=None, album=None):
        self.calls.append(
            {"filepath": filepath, "mbid": mbid, "artist": artist, "album": album}
        )
        return True


class FakeRequirements:
    def check_metadata_completeness(self, metadata):
        from src.metadata_enrichment import MetadataField

        complete = []
        missing = []
        for field in MetadataField:
            value = str(metadata.get(field.value, "")).strip()
            if value and value not in {"0", "0.0"}:
                complete.append(field)
            else:
                missing.append(field)
        return complete, missing

    def should_enrich(self, missing, skip_complete=True):
        from src.metadata_enrichment import MetadataField

        return any(field in {MetadataField.BPM, MetadataField.GENRE, MetadataField.YEAR, MetadataField.COMPOSER} for field in missing)


def make_filler():
    filler = MetadataFiller.__new__(MetadataFiller)
    filler.logger = logging.getLogger("test-metadata-fill")
    filler.detector = FakeDetector()
    filler.tag_manager = FakeTagManager()
    filler.enricher = FakeEnricher()
    filler.query_orchestrator = FakeQueryOrchestrator()
    filler.cover_art_manager = FakeCoverArtManager()
    filler.requirements = FakeRequirements()
    return filler


def test_playlist_metadata_fill_attempts_cover_art_embedding_for_local_tracks():
    filler = make_filler()

    result = filler._process_tracks(
        [
            {
                "name": "Song",
                "artist": "Artist",
                "album": "Album",
                "filepath": "/tmp/song.mp3",
                "cloudStatus": "uploaded",
            }
        ],
        force=False,
    )

    assert result["processed"] == 1
    assert result["cover_art_embedded"] == 1
    assert filler.cover_art_manager.calls == [
        {
            "filepath": "/tmp/song.mp3",
            "mbid": "release-1",
            "artist": "Artist",
            "album": "Album",
        }
    ]


def test_process_tracks_skips_cloud_only_tracks_without_local_file(monkeypatch):
    filler = make_filler()
    filler.detector = RealisticFakeDetector()

    def fail_query(*args, **kwargs):
        raise AssertionError("cloud-only tracks should not be queried")

    monkeypatch.setattr(filler.query_orchestrator, "query_all_sources", fail_query)

    result = filler._process_tracks(
        [
            {
                "name": "Cloud Song",
                "artist": "Artist",
                "album": "Album",
                "filepath": "",
                "location": "",
                "cloudStatus": "uploaded",
            }
        ],
        force=False,
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1


def test_playlist_metadata_fill_falls_back_to_artist_album_for_cover_art():
    filler = make_filler()

    class TagsWithoutMusicBrainzId(FakeTagManager):
        def read_tags(self, filepath):
            return {
                "artist": "Artist",
                "title": "Song",
                "album": "Album",
            }

    filler.tag_manager = TagsWithoutMusicBrainzId()

    result = filler._process_tracks(
        [
            {
                "name": "Song",
                "artist": "Artist",
                "album": "Album",
                "filepath": "/tmp/song.mp3",
                "cloudStatus": "uploaded",
            }
        ],
        force=False,
    )

    assert result["cover_art_embedded"] == 1
    assert filler.cover_art_manager.calls == [
        {
            "filepath": "/tmp/song.mp3",
            "mbid": None,
            "artist": "Artist",
            "album": "Album",
        }
    ]


def test_fill_all_playlists_processes_each_user_playlist(monkeypatch):
    filler = make_filler()
    filler.apple_music = type(
        "FakeAppleMusic",
        (),
        {"get_playlist_ids": lambda self: {"One": "id1", "Two": "id2"}},
    )()
    calls = []

    def fake_fill_playlist(name, force=False):
        calls.append((name, force))
        return {"success": True, "processed": 1, "enriched": 1, "skipped": 0, "cover_art_embedded": 0}

    monkeypatch.setattr(filler, "fill_playlist", fake_fill_playlist)

    result = filler.fill_all_playlists(force=True)

    assert calls == [("One", True), ("Two", True)]
    assert result["success"] is True
    assert result["playlists_processed"] == 2
    assert result["processed"] == 2
    assert result["enriched"] == 2


def test_fill_all_songs_processes_library_tracks(monkeypatch):
    filler = make_filler()
    filler.apple_music = type(
        "FakeAppleMusic",
        (),
        {"get_library_tracks": lambda self: [{"name": "Song", "artist": "Artist", "filepath": "/tmp/song.mp3"}]},
    )()
    calls = []

    def fake_process_tracks(tracks, force=False, workers=None, scope="metadata_fill"):
        calls.append((tracks, force, workers, scope))
        return {"success": True, "processed": 1, "enriched": 1, "skipped": 0, "cover_art_embedded": 1}

    monkeypatch.setattr(filler, "_process_tracks", fake_process_tracks)

    result = filler.fill_all_songs(force=True)

    assert calls == [([{"name": "Song", "artist": "Artist", "filepath": "/tmp/song.mp3"}], True, None, "library")]
    assert result["success"] is True
    assert result["processed"] == 1
    assert result["cover_art_embedded"] == 1


def test_process_tracks_accepts_parallel_workers():
    filler = make_filler()

    result = filler._process_tracks(
        [
            {"name": "One", "artist": "Artist", "album": "Album", "filepath": "/tmp/one.mp3"},
            {"name": "Two", "artist": "Artist", "album": "Album", "filepath": "/tmp/two.mp3"},
        ],
        force=False,
        workers=2,
    )

    assert result["processed"] == 2


def test_process_tracks_skips_database_queries_when_all_writable_fields_present(monkeypatch):
    filler = make_filler()

    class CompleteTags(FakeTagManager):
        def read_tags(self, filepath):
            return {
                "artist": "Artist",
                "title": "Song",
                "album": "Real Album",
                "genre": "Rock",
                "year": "1999",
                "bpm": "123",
                "composer": "Composer",
            }

    filler.tag_manager = CompleteTags()

    def fail_query(*args, **kwargs):
        raise AssertionError("database query should be skipped for complete writable fields")

    monkeypatch.setattr(filler.query_orchestrator, "query_all_sources", fail_query)

    result = filler._process_tracks(
        [
            {
                "name": "Song",
                "artist": "Artist",
                "album": "Real Album",
                "filepath": "/tmp/song.mp3",
                "cloudStatus": "uploaded",
            }
        ],
        force=False,
    )

    assert result["processed"] == 1
    assert result["enriched"] == 0


def test_process_tracks_skips_cover_art_for_compilation_album():
    filler = make_filler()

    result = filler._process_tracks(
        [
            {
                "name": "Bad Day",
                "artist": "Darwin Deez",
                "album": "00s",
                "filepath": "/tmp/song.mp3",
                "cloudStatus": "uploaded",
            }
        ],
        force=False,
    )

    assert result["cover_art_embedded"] == 0
    assert filler.cover_art_manager.calls == []


def test_process_tracks_skips_unsupported_audio_formats(monkeypatch):
    filler = make_filler()

    class UnsupportedTagManager(FakeTagManager):
        def is_format_supported(self, filepath):
            return False

        def read_tags(self, filepath):
            raise AssertionError("read_tags should not run for unsupported formats")

        def write_tags(self, filepath, tags, force):
            raise AssertionError("write_tags should not run for unsupported formats")

    filler.tag_manager = UnsupportedTagManager()

    def fail_query(*args, **kwargs):
        raise AssertionError("unsupported formats should not query databases")

    monkeypatch.setattr(filler.query_orchestrator, "query_all_sources", fail_query)

    result = filler._process_tracks(
        [
            {
                "name": "Song",
                "artist": "Artist",
                "album": "Album",
                "filepath": "/tmp/song.aiff",
                "cloudStatus": "uploaded",
            }
        ],
        force=False,
    )

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert filler.cover_art_manager.calls == []


def test_process_tracks_remembers_already_seen_tracks_between_runs(monkeypatch):
    filler = make_filler()
    calls = []

    def fake_process_one_track(track, force, track_num, total_tracks):
        calls.append(track["name"])
        return {"processed": 1, "enriched": 1, "skipped": 0, "cover_art_embedded": 0}

    monkeypatch.setattr(filler, "_process_one_track", fake_process_one_track)

    track = {"name": "Song", "artist": "Artist", "album": "Album", "filepath": "/tmp/song.mp3"}

    first = filler._process_tracks([track], force=False)
    second = filler._process_tracks([track], force=False)

    assert calls == ["Song"]
    assert first["processed"] == 1
    assert second["processed"] == 0
    assert second["skipped"] == 1


def test_process_tracks_uses_parallel_workers_automatically(monkeypatch):
    filler = make_filler()
    called_workers = []

    original_map = __import__("src.worker_pool", fromlist=["map_parallel"]).map_parallel

    def tracking_map(fn, items, workers=None, label="items"):
        called_workers.append(workers)
        return original_map(fn, items, workers=workers, label=label)

    monkeypatch.setattr("src.metadata_fill.map_parallel", tracking_map)
    monkeypatch.setattr(
        filler,
        "_process_one_track",
        lambda track, force, track_num, total_tracks: {
            "processed": 1,
            "enriched": 1,
            "skipped": 0,
            "cover_art_embedded": 0,
        },
    )

    result = filler._process_tracks(
        [
            {"name": "One", "artist": "Artist", "album": "Album", "filepath": "/tmp/one.mp3"},
            {"name": "Two", "artist": "Artist", "album": "Album", "filepath": "/tmp/two.mp3"},
        ],
        force=False,
    )

    assert len(called_workers) == 1, "map_parallel called once"
    assert result["processed"] == 2


def test_fill_all_playlists_uses_parallel_workers_automatically(monkeypatch):
    filler = make_filler()
    called_workers = []
    calls = []

    original_map = __import__("src.worker_pool", fromlist=["map_parallel"]).map_parallel

    def tracking_map(fn, items, workers=None, label="items"):
        called_workers.append(workers)
        return original_map(fn, items, workers=workers, label=label)

    filler.apple_music = type(
        "FakeAppleMusic",
        (),
        {"get_playlist_ids": lambda self: {"One": "id1", "Two": "id2", "Three": "id3"}},
    )()

    monkeypatch.setattr("src.metadata_fill.map_parallel", tracking_map)

    def fake_fill_playlist(name, force=False, workers=None):
        calls.append((name, force, workers))
        return {"success": True, "processed": 1, "enriched": 1, "skipped": 0, "cover_art_embedded": 0}

    monkeypatch.setattr(filler, "fill_playlist", fake_fill_playlist)

    result = filler.fill_all_playlists(force=True)

    assert len(called_workers) == 1, "map_parallel called once"
    assert len(calls) == 3
    assert result["playlists_processed"] == 3
    assert result["processed"] == 3

