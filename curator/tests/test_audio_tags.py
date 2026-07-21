from pathlib import Path

import pytest

from src.audio_tags import AIFFWAVTagHandler, AudioTagFactory, M4ATagHandler, MP3TagHandler, TagManager
from tests.conftest import write_minimal_aiff, write_minimal_wav


mutagen_id3 = pytest.importorskip("mutagen.id3")


def test_mp3_tag_handler_writes_year_frame(tmp_path):
    filepath = tmp_path / "song.mp3"
    filepath.write_bytes(b"")

    handler = MP3TagHandler(str(filepath))

    assert handler.write_tags({"year": "1999"}, overwrite=True) is True

    tags = mutagen_id3.ID3(str(filepath))
    assert str(tags["TDRC"].text[0]) == "1999"


def test_mp3_tag_handler_preserves_existing_year_without_overwrite(tmp_path):
    filepath = tmp_path / "song.mp3"
    filepath.write_bytes(b"")
    tags = mutagen_id3.ID3()
    tags.add(mutagen_id3.TDRC(encoding=3, text=["1990"]))
    tags.save(str(filepath))

    handler = MP3TagHandler(str(filepath))

    assert handler.write_tags({"year": "1999"}, overwrite=False) is True

    updated = mutagen_id3.ID3(str(filepath))
    assert str(updated["TDRC"].text[0]) == "1990"


def test_tag_manager_rejects_missing_file_for_writes(tmp_path):
    filepath = tmp_path / "missing.mp3"

    assert TagManager().write_tags(str(filepath), {"year": "1999"}) is False


def test_m4a_tag_handler_writes_year_genre_and_bpm(tmp_path):
    mutagen_mp4 = pytest.importorskip("mutagen.mp4")
    filepath = tmp_path / "song.m4a"
    filepath.write_bytes(b"")

    class FakeMP4(dict):
        saved = False

        def save(self):
            self.saved = True

    audio = FakeMP4()

    def fake_mp4(path):
        assert path == str(filepath)
        return audio

    from unittest.mock import patch

    with patch.object(mutagen_mp4, "MP4", fake_mp4):
        assert M4ATagHandler(str(filepath)).write_tags(
            {"year": "1999", "genre": "Rock", "bpm": "123"}, overwrite=True
        ) is True

    assert audio["\xa9day"] == ["1999"]
    assert audio["\xa9gen"] == ["Rock"]
    assert audio["tmpo"] == [123]
    assert audio.saved is True


@pytest.mark.parametrize("ext,writer", [(".aiff", write_minimal_aiff), (".aif", write_minimal_aiff), (".wav", write_minimal_wav)])
def test_aiffwav_tag_handler_supports_format(tmp_path, ext, writer):
    filepath = tmp_path / f"song{ext}"
    writer(str(filepath))

    assert AIFFWAVTagHandler(str(filepath)).supports_format() is True


def test_aiffwav_tag_handler_rejects_other_formats(tmp_path):
    filepath = tmp_path / "song.mp3"
    filepath.write_bytes(b"")

    assert AIFFWAVTagHandler(str(filepath)).supports_format() is False


def test_get_supported_formats_includes_aiff_aif_wav():
    formats = AudioTagFactory.get_supported_formats()
    assert ".aiff" in formats
    assert ".aif" in formats
    assert ".wav" in formats


@pytest.mark.parametrize("ext,writer", [(".aiff", write_minimal_aiff), (".aif", write_minimal_aiff), (".wav", write_minimal_wav)])
def test_aiffwav_tag_handler_write_and_read_roundtrip(tmp_path, ext, writer):
    filepath = tmp_path / f"song{ext}"
    writer(str(filepath))
    handler = AIFFWAVTagHandler(str(filepath))

    ok = handler.write_tags(
        {
            "artist": "Test Artist",
            "title": "Test Title",
            "album": "Test Album",
            "genre": "Jazz",
            "year": "1999",
            "bpm": "120",
        },
        overwrite=True,
    )

    assert ok is True
    tags = handler.read_tags()
    assert tags["artist"] == "Test Artist"
    assert tags["title"] == "Test Title"
    assert tags["album"] == "Test Album"
    assert tags["genre"] == "Jazz"
    assert tags["year"] == "1999"
    assert tags["bpm"] == "120"


@pytest.mark.parametrize("ext,writer", [(".aiff", write_minimal_aiff), (".wav", write_minimal_wav)])
def test_aiffwav_tag_handler_preserves_existing_value_without_overwrite(tmp_path, ext, writer):
    filepath = tmp_path / f"song{ext}"
    writer(str(filepath))
    handler = AIFFWAVTagHandler(str(filepath))
    assert handler.write_tags({"year": "1990"}, overwrite=True) is True

    assert handler.write_tags({"year": "1999"}, overwrite=False) is True

    assert handler.read_tags()["year"] == "1990"


def test_tag_manager_reads_and_writes_aiff_via_factory(tmp_path):
    filepath = tmp_path / "song.aiff"
    write_minimal_aiff(str(filepath))
    manager = TagManager()

    assert manager.is_format_supported(str(filepath)) is True
    assert manager.write_tags(str(filepath), {"artist": "Someone"}, overwrite=True) is True
    assert manager.read_tags(str(filepath))["artist"] == "Someone"
