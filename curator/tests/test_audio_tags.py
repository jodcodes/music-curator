from pathlib import Path

import pytest

from src.audio_tags import M4ATagHandler, MP3TagHandler, TagManager


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
