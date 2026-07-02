from src.deduplication import build_track_key


def test_build_track_key_prefers_file_path():
    assert build_track_key(filepath="/tmp/Song.mp3", artist="A", title="T") == "path:/tmp/Song.mp3"


def test_build_track_key_normalizes_track_fields():
    key = build_track_key(
        artist="  The Beatles ",
        title="Hey   Jude",
        album="  Hey Jude ",
        duration_seconds=431,
    )

    assert key == "track:the beatles|hey jude|hey jude|431"
