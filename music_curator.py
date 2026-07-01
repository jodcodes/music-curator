#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TOOLS = {
    "affective": (
        "4tempers, Fav Songs curation, metadata, playlist organization, bundled music tools",
        ROOT / "affective_playlists",
        ["python3", "main.py"],
    ),
    "apple2spfy": (
        "Apple Music to Spotify playlist sync",
        ROOT / "apple2spfy",
        ["python3", "sync_playlists.py"],
    ),
    "music-tools": (
        "alias for affective_playlists tools",
        ROOT / "affective_playlists",
        ["python3", "main.py", "tools"],
    ),
}


def list_tools() -> None:
    for name, (description, _, _) in TOOLS.items():
        print(f"{name:12} {description}")


def run_tool(name: str, args: list[str]) -> int:
    _, cwd, command = TOOLS[name]
    return subprocess.call(command + args, cwd=cwd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run music-curator tools")
    parser.add_argument("tool", nargs="?", choices=TOOLS.keys())
    parser.add_argument("tool_args", nargs=argparse.REMAINDER)
    parser.add_argument("--list", action="store_true", help="list available tools")
    parsed = parser.parse_args(argv)

    if parsed.list or not parsed.tool:
        list_tools()
        return 0

    return run_tool(parsed.tool, parsed.tool_args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
