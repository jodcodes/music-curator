import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO_ROOT, "scripts", "lib", "sync_wrapper_helpers.sh")


def run(*args):
    return subprocess.run(["/bin/bash", LIB, *args], capture_output=True, text=True)


def test_validate_python_interpreter_accepts_working_python():
    result = run("validate_python_interpreter", "/usr/bin/python3")
    assert result.returncode == 0


def test_validate_python_interpreter_rejects_missing_path(tmp_path):
    result = run("validate_python_interpreter", str(tmp_path / "nope"))
    assert result.returncode != 0


def test_validate_python_interpreter_rejects_non_executable(tmp_path):
    p = tmp_path / "python"
    p.write_text("#!/bin/sh\necho hi\n")
    result = run("validate_python_interpreter", str(p))
    assert result.returncode != 0


def test_parse_stale_sync_days_accepts_valid_integer():
    result = run("parse_stale_sync_days", "14", "7")
    assert result.stdout.strip() == "14"


def test_parse_stale_sync_days_falls_back_on_empty():
    result = run("parse_stale_sync_days", "", "7")
    assert result.stdout.strip() == "7"


def test_parse_stale_sync_days_falls_back_on_garbage():
    result = run("parse_stale_sync_days", "abc", "7")
    assert result.stdout.strip() == "7"


def test_parse_stale_sync_days_falls_back_on_zero():
    result = run("parse_stale_sync_days", "0", "7")
    assert result.stdout.strip() == "7"


def test_parse_last_run_timestamp_accepts_valid_integer():
    result = run("parse_last_run_timestamp", "1732000000")
    assert result.stdout.strip() == "1732000000"


def test_parse_last_run_timestamp_falls_back_to_zero_on_garbage():
    result = run("parse_last_run_timestamp", "not-a-number")
    assert result.stdout.strip() == "0"


def test_parse_last_run_timestamp_falls_back_to_zero_on_empty():
    result = run("parse_last_run_timestamp", "")
    assert result.stdout.strip() == "0"


def test_timestamp_is_within_cooldown_when_recent():
    result = run("is_within_cooldown", "1000", "3600", "2000")
    assert result.returncode == 0


def test_timestamp_is_not_within_cooldown_when_expired():
    result = run("is_within_cooldown", "1000", "3600", "5000")
    assert result.returncode != 0
