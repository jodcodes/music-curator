from pathlib import Path

import pytest

from src.audio_tags import MP3TagHandler, TagManager


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

