from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MUSIC_LIBRARY_RELATIVE_PATH = "Media (Musik Mediathek)/Music Library [2025-06-20].musiclibrary"
AUTOMATION_FILES = [
    "music_tools/bin/run_all.sh",
    "music_tools/scripts/find_playlist_duplicates.js",
    "music_tools/scripts/sort_favourites_by_genre.js",
    "music_tools/scripts/cleanup_old_genre_playlists.js",
    "music_tools/scripts/route_albums_to_playlists.applescript",
]


def test_automation_scripts_check_the_actual_ssd_library_path():
    for relative_path in AUTOMATION_FILES:
        content = (REPO_ROOT / relative_path).read_text()

        assert MUSIC_LIBRARY_RELATIVE_PATH in content, relative_path
