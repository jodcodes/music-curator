"""
Music maintenance tool registry.

These scripts stay standalone JXA files, but the CLI treats them as part of the
curator product surface.
"""

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Iterable, Sequence


@dataclass(frozen=True)
class MusicTool:
    name: str
    script_name: str
    description: str
    help_text: str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MUSIC_TOOLS_DIR = PROJECT_ROOT / "music_tools" / "scripts"

MUSIC_TOOLS = {
    "sort-favourites": MusicTool(
        name="sort-favourites",
        script_name="sort_favourites_by_genre.js",
        description="Sort Favourite Songs into ♥ genre playlists",
        help_text="Default sorter and cleanup pass for favourite tracks",
    ),
    "find-duplicates": MusicTool(
        name="find-duplicates",
        script_name="find_playlist_duplicates.js",
        description="Detect and remove duplicate tracks in user playlists",
        help_text="Scans playlists for duplicate tracks and applies tie-break rules",
    ),
    "cleanup-genres": MusicTool(
        name="cleanup-genres",
        script_name="cleanup_old_genre_playlists.js",
        description="Remove obsolete ♥ genre playlists",
        help_text="Dry-run by default; pass --apply to delete stale genre buckets",
    ),
    "enrich-genres": MusicTool(
        name="enrich-genres",
        script_name="enrich_missing_genres.js",
        description="Fill missing genre tags from iTunes Search",
        help_text="Use --dry-run to preview; otherwise writes genres back",
    ),
}


def list_music_tools() -> list[MusicTool]:
    return list(MUSIC_TOOLS.values())


def get_music_tool(name: str) -> MusicTool:
    try:
        return MUSIC_TOOLS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown music tool: {name}") from exc


def build_music_tool_command(name: str, extra_args: Sequence[str] | None = None) -> list[str]:
    tool = get_music_tool(name)
    script_path = MUSIC_TOOLS_DIR / tool.script_name
    args = ["/usr/bin/osascript", "-l", "JavaScript", str(script_path)]
    if extra_args:
        args.extend(extra_args)
    return args


def run_music_tool(name: str, extra_args: Sequence[str] | None = None) -> CompletedProcess[str]:
    """
    Run a maintenance script.

    ponytail: keep the JXA scripts as-is for now; a direct Python port would be larger
    and risk diverging from the live Apple Music behavior.
    """

    command = build_music_tool_command(name, extra_args)
    return run(command, capture_output=True, text=True, check=False)


def format_music_tool_catalog() -> list[str]:
    return [f"{tool.name:16} {tool.description}" for tool in list_music_tools()]
