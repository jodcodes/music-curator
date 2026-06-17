import subprocess
import sys


def test_music_curator_lists_available_tools():
    result = subprocess.run(
        [sys.executable or "python3", "music_curator.py", "--list"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "affective" in result.stdout
    assert "apple2spfy" in result.stdout
    assert "music-tools" in result.stdout
