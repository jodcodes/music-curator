import logging

from src.metadata_fill import MetadataFiller


class FakeDetector:
    def is_downloaded(self, filepath):
        return True


class FakeTagManager:
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


def make_filler():
    filler = MetadataFiller.__new__(MetadataFiller)
    filler.logger = logging.getLogger("test-metadata-fill")
    filler.detector = FakeDetector()
    filler.tag_manager = FakeTagManager()
    filler.enricher = FakeEnricher()
    filler.query_orchestrator = FakeQueryOrchestrator()
    filler.cover_art_manager = FakeCoverArtManager()
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


def test_playlist_metadata_fill_skips_cover_art_without_musicbrainz_release_id():
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

    assert result["cover_art_embedded"] == 0
    assert filler.cover_art_manager.calls == []
