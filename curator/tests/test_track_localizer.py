import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.track_localizer import (
    LocalAudioTrack,
    LocalizationResult,
    MatchStatus,
    TrackLocalizer,
)


class FakeMusicClient:
    def __init__(
        self,
        import_result="NEW-ID",
        add_result=True,
        remove_result=True,
        import_error=None,
        add_error=None,
        playlists=None,
    ):
        self.import_result = import_result
        self.add_result = add_result
        self.remove_result = remove_result
        self.import_error = import_error
        self.add_error = add_error
        self.playlists = playlists or {}
        self.calls = []

    def get_user_playlist_names(self):
        return list(self.playlists)

    def get_playlist_tracks(self, playlist_name):
        self.calls.append(("tracks", playlist_name))
        tracks = self.playlists.get(playlist_name, [])
        if isinstance(tracks, Exception):
            raise tracks
        return tracks

    def import_local_track(self, filepath):
        self.calls.append(("import", filepath))
        if self.import_error:
            raise self.import_error
        return self.import_result

    def add_library_track_to_playlist(self, playlist_name, persistent_id):
        self.calls.append(("add", playlist_name, persistent_id))
        if self.add_error:
            raise self.add_error
        return self.add_result

    def remove_playlist_track(self, playlist_name, persistent_id):
        self.calls.append(("remove", playlist_name, persistent_id))
        return self.remove_result


def tagged(artist, title, album=None):
    tags = {"artist": [artist], "title": [title]}
    if album is not None:
        tags["album"] = [album]
    return type("Audio", (), {"tags": tags})()


def build_library(tmp_path, files):
    for relative_path in files:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")


def test_canonicalize_normalizes_unicode_case_separators_and_whitespace_without_losing_content():
    assert (
        TrackLocalizer.canonicalize("  Ｂeyoncé—Halo  (feat. JAY‑Z)!  ")
        == "beyoncé-halo (feat. jay-z)!"
    )


def test_featured_artist_versions_remain_distinct(tmp_path):
    build_library(tmp_path, ["jay-z.mp3", "kanye.mp3"])

    def load(path, easy):
        featured_artist = "JAY-Z" if Path(path).name == "jay-z.mp3" else "Kanye West"
        return tagged("Beyoncé", f"Halo (feat. {featured_artist})")

    with patch("src.track_localizer.mutagen.File", side_effect=load):
        result = TrackLocalizer(tmp_path).match("Beyoncé", "Halo (feat. JAY-Z)")

    assert result.unique is not None
    assert result.unique.path == tmp_path / "jay-z.mp3"


@pytest.mark.parametrize("variant", ["Remix", "Live", "Remaster", "Cover"])
def test_exact_variant_labels_are_never_automatic_matches(tmp_path, variant):
    build_library(tmp_path, ["song.mp3"])
    title = f"Song ({variant})"
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", title)):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.match("Artist", title).candidates == ()


@pytest.mark.parametrize(
    "title",
    ["Live and Let Die", "Cover Me", "Song (Cover Me)", "Song - Live and Let Die"],
)
def test_ordinary_title_words_that_resemble_variants_remain_eligible(tmp_path, title):
    build_library(tmp_path, ["song.mp3"])
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", title)):
        result = TrackLocalizer(tmp_path).match("Artist", title)

    assert result.status is MatchStatus.UNIQUE
    assert result.unique is not None


@pytest.mark.parametrize("suffix", ["Live", "Remastered 2011"])
def test_technical_suffix_variants_are_never_automatic_matches(tmp_path, suffix):
    build_library(tmp_path, ["song.mp3"])
    title = f"Song - {suffix}"
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", title)):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.match("Artist", title).status is MatchStatus.PROHIBITED_VARIANT
    assert localizer.match("Artist", title).candidates == ()


def test_remix_is_not_matched_to_original(tmp_path):
    build_library(tmp_path, ["song.mp3"])
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song (Remix)")):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.match("Artist", "Song").candidates == ()


def test_present_playlist_album_must_match_exactly(tmp_path):
    build_library(tmp_path, ["song.flac"])
    with patch(
        "src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song", "First Album")
    ):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.match("Artist", "Song", "Other Album").candidates == ()
    assert localizer.match("Artist", "Song").unique.path == tmp_path / "song.flac"


def test_duplicate_exact_matches_are_ambiguous(tmp_path):
    build_library(tmp_path, ["one.mp3", "nested/two.m4a"])
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song", "Album")):
        result = TrackLocalizer(tmp_path).match("artist", "song", "album")

    assert result.is_ambiguous
    assert result.unique is None
    assert len(result.candidates) == 2
    assert all(isinstance(track, LocalAudioTrack) for track in result.candidates)


def test_match_status_distinguishes_all_outcomes(tmp_path):
    build_library(tmp_path, ["one.mp3", "two.mp3"])
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song")):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.match("Nobody", "Missing").status is MatchStatus.NOT_FOUND
    assert localizer.match("Artist", "Song").status is MatchStatus.AMBIGUOUS
    assert localizer.match("Artist", "Song (Live)").status is MatchStatus.PROHIBITED_VARIANT


def test_index_ignores_non_audio_untagged_and_unreadable_audio(tmp_path):
    build_library(tmp_path, ["good.WAV", "notes.txt", "untagged.mp3", "broken.ogg"])

    def load(path, easy):
        assert easy is True
        name = Path(path).name
        if name == "good.WAV":
            return tagged("Artist", "Song")
        if name == "broken.ogg":
            raise OSError("bad audio")
        return tagged("Artist", "")

    with patch("src.track_localizer.mutagen.File", side_effect=load) as mutagen_file:
        localizer = TrackLocalizer(tmp_path)

    assert [track.path.name for track in localizer.tracks] == ["good.WAV"]
    assert localizer.skipped_files[0].path == tmp_path / "broken.ogg"
    assert localizer.skipped_files[0].error_type == "OSError"
    assert localizer.skipped_files[0].message == "bad audio"
    assert mutagen_file.call_count == 3


def test_index_records_mutagen_parse_errors(tmp_path):
    build_library(tmp_path, ["broken.mp3"])
    with patch(
        "src.track_localizer.mutagen.File",
        side_effect=__import__("mutagen").MutagenError("invalid tags"),
    ):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.tracks == ()
    assert localizer.skipped_files[0].error_type == "MutagenError"


@pytest.mark.parametrize(
    ("artist", "title", "missing"),
    [("", "Song", "artist"), ("Artist", "", "title")],
)
def test_index_records_files_missing_required_metadata(tmp_path, artist, title, missing):
    build_library(tmp_path, ["untagged.mp3"])
    with patch("src.track_localizer.mutagen.File", return_value=tagged(artist, title)):
        localizer = TrackLocalizer(tmp_path)

    assert localizer.tracks == ()
    assert localizer.skipped_files[0].path == tmp_path / "untagged.mp3"
    assert localizer.skipped_files[0].error_type == "MissingMetadata"
    assert localizer.skipped_files[0].message == f"missing required {missing} metadata"


def test_index_does_not_swallow_unexpected_errors(tmp_path):
    build_library(tmp_path, ["broken.mp3"])
    with patch("src.track_localizer.mutagen.File", side_effect=RuntimeError("bug")):
        with pytest.raises(RuntimeError, match="bug"):
            TrackLocalizer(tmp_path)


def test_indexed_tracks_property_is_read_only(tmp_path):
    localizer = TrackLocalizer(tmp_path)

    assert localizer.tracks == ()
    with pytest.raises(AttributeError):
        localizer.tracks = ()


@pytest.mark.parametrize("kind", ["missing", "file", "unreadable"])
def test_invalid_source_is_rejected(tmp_path, kind):
    source = tmp_path / kind
    if kind == "file":
        source.write_text("not a directory")

    access = patch("src.track_localizer.os.access", return_value=False) if kind == "unreadable" else None
    if access:
        source.mkdir()
        access.start()
    try:
        with pytest.raises(ValueError, match="readable directory"):
            TrackLocalizer(source)
    finally:
        if access:
            access.stop()


def test_musiclibrary_bundle_uses_sibling_music_folder(tmp_path):
    bundle = tmp_path / "Library.musiclibrary"
    music_folder = tmp_path / "Music"
    bundle.mkdir()
    music_folder.mkdir()

    localizer = TrackLocalizer(bundle)

    assert localizer.source == music_folder


def test_apply_never_removes_when_import_fails(tmp_path):
    music = FakeMusicClient(import_result=None)
    localizer = TrackLocalizer(tmp_path, music_client=music)
    candidate = LocalAudioTrack(Path("/music/new.mp3"), "Artist", "Title", "Album")
    old_track = {"persistent_id": "OLD-ID", "artist": "Artist", "title": "Title", "album": "Album"}

    result = localizer.apply_replacement("Playlist", old_track, candidate)

    assert result.status == "import_failed"
    assert not any(call[0] == "remove" for call in music.calls)


def test_apply_never_removes_when_add_fails(tmp_path):
    music = FakeMusicClient(add_result=False)
    localizer = TrackLocalizer(tmp_path, music_client=music)
    candidate = LocalAudioTrack(Path("/music/new.mp3"), "Artist", "Title", "Album")
    old_track = {"persistent_id": "OLD-ID", "artist": "Artist", "title": "Title", "album": "Album"}

    result = localizer.apply_replacement("Playlist", old_track, candidate)

    assert result.status == "playlist_add_failed"
    assert not any(call[0] == "remove" for call in music.calls)


def test_apply_never_removes_when_import_raises(tmp_path):
    music = FakeMusicClient(import_error=RuntimeError("import error"))
    localizer = TrackLocalizer(tmp_path, music_client=music)
    candidate = LocalAudioTrack(Path("/music/new.mp3"), "Artist", "Title", "Album")
    old_track = {"persistent_id": "OLD-ID", "artist": "Artist", "title": "Title"}

    with pytest.raises(RuntimeError, match="import error"):
        localizer.apply_replacement("Playlist", old_track, candidate)

    assert not any(call[0] == "remove" for call in music.calls)


def test_apply_never_removes_when_add_raises(tmp_path):
    music = FakeMusicClient(add_error=RuntimeError("add error"))
    localizer = TrackLocalizer(tmp_path, music_client=music)
    candidate = LocalAudioTrack(Path("/music/new.mp3"), "Artist", "Title", "Album")
    old_track = {"persistent_id": "OLD-ID", "artist": "Artist", "title": "Title"}

    with pytest.raises(RuntimeError, match="add error"):
        localizer.apply_replacement("Playlist", old_track, candidate)

    assert not any(call[0] == "remove" for call in music.calls)


def test_apply_requires_music_client(tmp_path):
    localizer = TrackLocalizer(tmp_path)
    candidate = LocalAudioTrack(Path("/music/new.mp3"), "Artist", "Title")

    with pytest.raises(RuntimeError, match="music client is required"):
        localizer.apply_replacement("Playlist", {"persistent_id": "OLD-ID"}, candidate)


def test_apply_imports_then_adds_then_removes(tmp_path):
    music = FakeMusicClient()
    localizer = TrackLocalizer(tmp_path, music_client=music)
    candidate = LocalAudioTrack(Path("/music/new.mp3"), "Artist", "Title", "Album")
    old_track = {"persistent_id": "OLD-ID", "artist": "Artist", "title": "Title", "album": "Album"}

    result = localizer.apply_replacement("Playlist", old_track, candidate)

    assert result.status == "replaced"
    assert music.calls == [
        ("import", candidate.path),
        ("add", "Playlist", "NEW-ID"),
        ("remove", "Playlist", "OLD-ID"),
    ]


def playlist_track(**overrides):
    return {
        "persistent_id": "OLD-ID",
        "artist": "Artist",
        "title": "Song",
        "album": "Album",
        "filepath": "",
        **overrides,
    }


def test_scan_all_skips_existing_reachable_location(tmp_path):
    existing = tmp_path / "existing.mp3"
    existing.write_bytes(b"audio")
    music = FakeMusicClient(playlists={"Playlist": [playlist_track(filepath=str(existing))]})

    assert TrackLocalizer(tmp_path, music).scan()[0].status == "already_local"


def test_scan_reports_not_found_for_missing_track(tmp_path):
    music = FakeMusicClient(playlists={"Playlist": [playlist_track()]})

    assert TrackLocalizer(tmp_path, music).scan()[0].status == "not_found"


def test_scan_reports_ambiguous_for_multiple_matches(tmp_path):
    build_library(tmp_path, ["one.mp3", "two.mp3"])
    music = FakeMusicClient(playlists={"Playlist": [playlist_track()]})
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song", "Album")):
        results = TrackLocalizer(tmp_path, music).scan()

    assert results[0].status == "ambiguous"


def test_scan_dry_run_reports_would_replace(tmp_path):
    build_library(tmp_path, ["song.mp3"])
    music = FakeMusicClient(playlists={"Playlist": [playlist_track()]})
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song", "Album")):
        result = TrackLocalizer(tmp_path, music).scan()[0]

    assert result.status == "would_replace"
    assert result.candidate_path == tmp_path / "song.mp3"
    assert not any(call[0] in {"import", "add", "remove"} for call in music.calls)


def test_scan_apply_replaces(tmp_path):
    build_library(tmp_path, ["song.mp3"])
    music = FakeMusicClient(playlists={"Playlist": [playlist_track()]})
    with patch("src.track_localizer.mutagen.File", return_value=tagged("Artist", "Song", "Album")):
        result = TrackLocalizer(tmp_path, music).scan(apply=True)[0]

    assert result.status == "replaced"
    assert [call[0] for call in music.calls] == ["tracks", "import", "add", "remove"]


def test_scan_single_playlist_filter(tmp_path):
    music = FakeMusicClient(
        playlists={"Only Me": [playlist_track()], "Other": [playlist_track()]}
    )

    TrackLocalizer(tmp_path, music).scan(playlist_name="Only Me")

    assert music.calls == [("tracks", "Only Me")]


def test_scan_reports_malformed_track_error_and_continues(tmp_path):
    malformed = playlist_track()
    del malformed["persistent_id"]
    music = FakeMusicClient(playlists={"Playlist": [malformed, playlist_track()]})

    results = TrackLocalizer(tmp_path, music).scan()

    assert [result.status for result in results] == ["error", "not_found"]


def test_scan_playlist_retrieval_error_continues_with_remaining_playlists(tmp_path):
    music = FakeMusicClient(
        playlists={
            "Broken": RuntimeError("playlist unavailable"),
            "Working": [playlist_track()],
        }
    )

    results = TrackLocalizer(tmp_path, music).scan()

    assert [result.status for result in results] == ["not_found"]
    assert music.calls == [("tracks", "Broken"), ("tracks", "Working")]


def test_scan_error_preserves_available_track_identity(tmp_path):
    malformed = {
        "artist": "Known Artist",
        "title": "Known Title",
        "album": "Known Album",
    }
    music = FakeMusicClient(playlists={"Playlist": [malformed]})

    result = TrackLocalizer(tmp_path, music).scan()[0]

    assert result.status == "error"
    assert result.old_persistent_id == ""
    assert result.artist == "Known Artist"
    assert result.title == "Known Title"
    assert result.album == "Known Album"


def test_write_report_contains_track_identity_status_and_candidate_path(tmp_path):
    candidate = tmp_path / "song.mp3"
    result = LocalizationResult(
        "Playlist", "OLD-ID", "NEW-ID", "Artist", "Song", "Album", "replaced", candidate
    )
    report = tmp_path / "report.json"

    TrackLocalizer.write_report(report, [result])

    assert json.loads(report.read_text(encoding="utf-8")) == [{
        "playlist": "Playlist",
        "old_persistent_id": "OLD-ID",
        "new_persistent_id": "NEW-ID",
        "artist": "Artist",
        "title": "Song",
        "album": "Album",
        "status": "replaced",
        "candidate_path": str(candidate),
    }]
