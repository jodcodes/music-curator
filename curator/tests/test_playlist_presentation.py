"""Static presentation guidance must never probe or change Music/account state."""

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from src.apple_music import AppleMusicInterface


@pytest.fixture
def offline_music(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Capability information must not contact Music or the network")

    monkeypatch.setattr(AppleMusicInterface, "_run_applescript", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("socket.socket.connect", forbidden)
    return AppleMusicInterface()


@pytest.mark.parametrize("script_result", [
    (False, "unsupported property"),
    (True, "track artwork written"),
    (False, "publication failed"),
    (True, "shared = true"),
])
def test_static_guidance_never_promotes_script_results(offline_music, monkeypatch, script_result):
    runner = Mock(return_value=script_result)
    monkeypatch.setattr(offline_music, "_run_applescript", runner)

    capabilities = offline_music.get_playlist_presentation_capabilities()

    runner.assert_not_called()
    assert set(capabilities) == {"cover", "public_share"}
    assert capabilities["cover"]["status"] == "manual"
    assert capabilities["cover"]["automation"] == "unsupported"
    assert capabilities["public_share"]["status"] == "manual"
    assert capabilities["public_share"]["automation"] == "unknown"
    for capability in capabilities.values():
        assert capability["evidence"]
        assert capability["instructions"]
    assert capabilities["public_share"]["visibility"] == "unknown"
    assert capabilities["public_share"]["public_url"] is None


def test_static_guidance_has_manual_steps_and_limits(offline_music):
    capabilities = offline_music.get_playlist_presentation_capabilities()
    cover = capabilities["cover"]
    sharing = capabilities["public_share"]

    assert "track artwork" in cover["evidence"]
    assert "Done" in cover["instructions"]
    assert "explicit user action" in sharing["instructions"]
    assert "Apple Music profile" in sharing["instructions"]
    assert "Show in My Profile and in Search" in sharing["instructions"]
    assert "cloud propagation" in sharing["evidence"]


def test_presentation_cli_is_offline_on_any_platform(offline_music, monkeypatch, capsys):
    import main

    monkeypatch.setattr(main, "IS_MACOS", False)
    # The static API also avoids constructing a Music adapter in this command.
    monkeypatch.setattr(AppleMusicInterface, "__init__", Mock(side_effect=AssertionError("No construction")))

    assert main.main(["playlist-presentation"]) == 0

    output = capsys.readouterr().out
    assert "cover: manual" in output
    assert "public_share: manual" in output
    assert "automation: unsupported" in output
    assert "automation: unknown" in output
    assert "visibility: unknown" in output
    assert "public_url: None" in output
    assert "explicit user action" in output
    assert "Apple Music profile" in output
    assert "docs/playlist-presentation.md" in output


def test_presentation_cli_has_no_apply_option(monkeypatch):
    import main

    monkeypatch.setattr(main, "AppleMusicInterface", Mock(side_effect=AssertionError("No writes")))
    with pytest.raises(SystemExit) as exc:
        main.main(["playlist-presentation", "--apply"])
    assert exc.value.code == 2


def test_presentation_cli_cold_start_creates_no_files(tmp_path):
    script = tmp_path / "cold_start.py"
    script.write_text('''
import socket
import subprocess
import sys

def forbidden(*args, **kwargs):
    raise AssertionError("Static command must not contact Music or the network")

socket.socket.connect = forbidden
socket.create_connection = forbidden
subprocess.Popen = forbidden
import main
assert main.main(["playlist-presentation"]) == 0
assert "src.mood_analyzer" not in sys.modules
''')
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    result = subprocess.run(
        [sys.executable, "-B", str(script)], cwd=tmp_path,
        env=env, capture_output=True, text=True,
    )

    assert set(tmp_path.iterdir()) == {script}, "Static CLI startup must not create logs/state"
    assert result.returncode == 0, result.stderr
    assert "cover: manual" in result.stdout
    assert "public_share: manual" in result.stdout
