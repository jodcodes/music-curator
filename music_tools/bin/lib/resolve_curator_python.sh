#!/bin/bash
# ============================================================
# resolve_curator_python.sh
#
# Deterministically resolves the ONE python interpreter run_all.sh is
# allowed to use for curator: curator/.venv/bin/python.
#
# Under launchd, PATH is minimal and /usr/bin/env python3 resolves to
# Apple's bundled Python (3.9.x), which is below curator's >=3.10
# requirement. No PATH tricks, no hardcoded Homebrew path — just the
# repo-local venv, validated before use.
#
# Usage: resolve_curator_python.sh <curator_dir>
#   stdout: absolute path to a working python >=3.10 (exit 0)
#   stderr: human-readable reason (exit 1) if venv missing/unusable
# ============================================================

resolve_curator_python() {
    local curator_dir="$1"
    local py="$curator_dir/.venv/bin/python"

    if [ ! -e "$py" ]; then
        echo "curator venv python not found at $py (run: cd curator && python3 -m venv .venv && .venv/bin/pip install -e .)" >&2
        return 1
    fi
    if [ ! -x "$py" ]; then
        echo "curator venv python at $py exists but is not executable" >&2
        return 1
    fi
    if ! "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        local ver
        ver="$("$py" --version 2>&1)"
        echo "curator venv python at $py is too old ($ver); curator requires >=3.10" >&2
        return 1
    fi

    echo "$py"
    return 0
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    resolve_curator_python "$1"
fi
