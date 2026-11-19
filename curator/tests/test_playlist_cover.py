"""Playlist cover validation, preview and confirmed-write boundaries."""

import json
from types import SimpleNamespace

import pytest

import main
from src.apple_music import AppleMusicInterface

PID = "0123456789ABCDEF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fixture-png"
JPEG_BYTES = b"\xff\xd8\xff" + b"fixture-jpeg"


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "cover.png"
    path.write_bytes(PNG_BYTES)
    return path


def test_cover_accepts_png_and_jpeg(png, tmp_path):
    assert AppleMusicInterface._cover_image(png)["format"] == "PNG"
    jpg = tmp_path / "cover.jpg"
    jpg.write_bytes(JPEG_BYTES)
    assert AppleMusicInterface._cover_image(jpg)["format"] == "JPEG"


def test_cover_rejects_missing_symlink_empty_unknown_and_oversized(png, tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        AppleMusicInterface._cover_image(tmp_path / "missing.png")

    link = tmp_path / "link.png"
    link.symlink_to(png)
    with pytest.raises(ValueError):
        AppleMusicInterface._cover_image(link)

    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    with pytest.raises(ValueError):
        AppleMusicInterface._cover_image(empty)

    text = tmp_path / "cover.txt"
    text.write_bytes(b"not an image")
    with pytest.raises(ValueError):
        AppleMusicInterface._cover_image(text)

    monkeypatch.setattr(AppleMusicInterface, "_MAX_COVER_BYTES", 8)
    with pytest.raises(ValueError):
        AppleMusicInterface._cover_image(png)


def test_artwork_count_requires_numeric_strict_output(monkeypatch):
    music = AppleMusicInterface()
    monkeypatch.setattr(music, "_run_applescript", lambda script: (True, "2"))
    assert music.get_playlist_artwork_count_by_id(PID) == 2
    monkeypatch.setattr(music, "_run_applescript", lambda script: (True, "2\n3"))
    with pytest.raises(RuntimeError):
        music.get_playlist_artwork_count_by_id(PID)
    monkeypatch.setattr(music, "_run_applescript", lambda script: (False, "denied"))
    with pytest.raises(RuntimeError):
        music.get_playlist_artwork_count_by_id(PID)


class FakeMusic:
    _cover_image = staticmethod(AppleMusicInterface._cover_image)

    def __init__(self):
        self.calls = []

    def get_playlist_info_by_id(self, playlist_id):
        self.calls.append(("info", playlist_id))
        return {"persistent_id": playlist_id.upper(), "name": "Reviewed Mix"}

    def get_playlist_artwork_count_by_id(self, playlist_id):
        self.calls.append(("count", playlist_id))
        return 2



@pytest.fixture
def fake_cli(monkeypatch):
    fake = FakeMusic()
    monkeypatch.setattr(main, "AppleMusicInterface", lambda: fake)
    monkeypatch.setattr(main, "require_macos", lambda name: True)
    return fake


def test_cover_preview_reads_only_and_reports_hash(fake_cli, png, capsys):
    args = SimpleNamespace(playlist_id=PID, image=str(png), apply=False, yes=False)
    assert main.run_playlist_cover(args) == 0
    assert [call[0] for call in fake_cli.calls] == ["info", "count"]
    output = capsys.readouterr().out
    assert '"applied": false' in output
    assert '"existing_artwork_count": 2' in output
    assert '"sha256":' in output
    assert "Preview only" in output


def test_cover_apply_requires_literal_confirmation(fake_cli, png, capsys):
    assert main.run_playlist_cover(SimpleNamespace(
        playlist_id=PID, image=str(png), apply=True, yes=False)) == 1
    assert main.run_playlist_cover(SimpleNamespace(
        playlist_id=PID, image=str(png), apply=False, yes=True)) == 1
    assert fake_cli.calls == []
    assert "Apply separately" in capsys.readouterr().out


def test_cover_apply_is_refused_without_touching_music(fake_cli, png, capsys):
    args = SimpleNamespace(playlist_id=PID, image=str(png), apply=True, yes=True)
    assert main.run_playlist_cover(args) == 1
    assert fake_cli.calls == []
    output = capsys.readouterr().out
    assert "unsupported on Music 1.7" in output
    assert "make new artwork" in output
    assert str(png) in output


def test_cover_cli_rejects_invalid_modes_without_music(fake_cli, png):
    assert main.run_playlist_cover(SimpleNamespace(
        playlist_id=None, image=str(png), apply=False, yes=False)) == 1
    assert main.run_playlist_cover(SimpleNamespace(
        playlist_id=PID, image=None, apply=False, yes=False)) == 1
    assert fake_cli.calls == []
