import os
import shutil
import stat
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOLVER = os.path.join(REPO_ROOT, "music_tools", "bin", "lib", "resolve_curator_python.sh")


def run_resolver(curator_dir):
    return subprocess.run(
        ["/bin/bash", RESOLVER, curator_dir],
        capture_output=True,
        text=True,
    )


def _make_venv_pointing_at(curator_dir, real_python):
    venv_bin = os.path.join(curator_dir, ".venv", "bin")
    os.makedirs(venv_bin, exist_ok=True)
    py_path = os.path.join(venv_bin, "python")
    os.symlink(real_python, py_path)
    return py_path


def test_resolves_venv_python_when_present_and_modern(tmp_path):
    curator_dir = str(tmp_path / "curator")
    os.makedirs(curator_dir)
    expected = _make_venv_pointing_at(curator_dir, shutil.which("python3.12") or shutil.which("python3"))

    result = run_resolver(curator_dir)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_fails_clearly_when_venv_missing(tmp_path):
    curator_dir = str(tmp_path / "curator")
    os.makedirs(curator_dir)

    result = run_resolver(curator_dir)

    assert result.returncode != 0
    assert "not found" in result.stderr
    assert result.stdout.strip() == ""


def test_fails_clearly_when_python_too_old(tmp_path):
    curator_dir = str(tmp_path / "curator")
    os.makedirs(curator_dir)
    _make_venv_pointing_at(curator_dir, "/usr/bin/python3")  # Apple system python, 3.9.x

    result = run_resolver(curator_dir)

    assert result.returncode != 0
    assert "too old" in result.stderr
    assert result.stdout.strip() == ""


def test_fails_clearly_when_not_executable(tmp_path):
    curator_dir = str(tmp_path / "curator")
    venv_bin = os.path.join(curator_dir, ".venv", "bin")
    os.makedirs(venv_bin)
    py_path = os.path.join(venv_bin, "python")
    with open(py_path, "w") as f:
        f.write("#!/bin/sh\necho fake\n")
    os.chmod(py_path, stat.S_IRUSR | stat.S_IWUSR)  # not executable

    result = run_resolver(curator_dir)

    assert result.returncode != 0
    assert result.stdout.strip() == ""
