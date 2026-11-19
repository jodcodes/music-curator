import pytest

from src.apple_music import AppleMusicInterface


PLAYLIST_ID = "AABBCCDDEEFF0011"
TRACK_ID = "1122334455667788"


@pytest.fixture(autouse=True)
def block_real_music_calls(monkeypatch):
    def unexpected_call(*args, **kwargs):
        pytest.fail("Adapter tests must not invoke osascript")

    monkeypatch.setattr("src.apple_music.subprocess.Popen", unexpected_call)
    monkeypatch.setattr("src.apple_music.subprocess.run", unexpected_call)


def test_regular_playlist_reader_fetches_track_properties_in_batches(monkeypatch):
    interface = AppleMusicInterface()
    scripts = []

    def fake_run(script):
        scripts.append(script)
        return True, "Song\tID\tArtist\tAlbum\tGenre\t120\t2020\tComposer\t180\t"

    monkeypatch.setattr(interface, "_run_applescript", fake_run)

    tracks = interface._get_regular_playlist_tracks("Favourite Songs")

    assert tracks[0]["persistent_id"] == "ID"
    script = scripts[0]
    assert "set trackNames to name of every track of targetPlaylist" in script
    assert "set trackIDs to persistent ID of every track of targetPlaylist" in script
    assert "set trackLocations to location of every track of targetPlaylist" in script
    assert "repeat with trackIndex from 1 to trackCount" in script
    assert "repeat with trk in tracks of targetPlaylist" not in script


def test_regular_playlist_reader_escapes_playlist_name_quotes(monkeypatch):
    interface = AppleMusicInterface()
    scripts = []

    def fake_run(script):
        scripts.append(script)
        return True, ""

    monkeypatch.setattr(interface, "_run_applescript", fake_run)

    interface._get_regular_playlist_tracks('"STEIN"')

    assert 'set targetPlaylist to playlist "\\\"STEIN\\\""' in scripts[0]


def test_id_reader_preserves_order_duplicate_occurrences_and_metadata(monkeypatch):
    interface = AppleMusicInterface()
    scripts = []
    row = f"Song\t{TRACK_ID}\tArtist\tAlbum\tGenre\t120\t2020\tComposer\t180\t/tmp/song.aiff"
    other = "Other\t8877665544332211\tArtist\tAlbum\tGenre\t0\t2021\t\t150\t"

    def fake_run(script):
        scripts.append(script)
        return True, "TRACK_ROWS\n" + "\n".join([row, other, row]) + "\nEND_TRACK_ROWS"

    monkeypatch.setattr(interface, "_run_applescript", fake_run)
    tracks = interface.get_playlist_tracks_by_id(PLAYLIST_ID)

    assert [track["persistent_id"] for track in tracks] == [TRACK_ID, "8877665544332211", TRACK_ID]
    assert tracks[0]["name"] == "Song"
    assert tracks[0]["filepath"] == "/tmp/song.aiff"
    assert tracks[0]["duration"] == "180"
    assert tracks[0] == tracks[2]
    assert len(scripts) == 1
    assert f'every user playlist whose persistent ID is "{PLAYLIST_ID}"' in scripts[0]
    assert 'set targetPlaylist to playlist "' not in scripts[0]
    assert "error errMsg" in scripts[0]


def test_id_reader_empty_playlist_is_successful_empty_list(monkeypatch):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda script: (True, "TRACK_ROWS\n\nEND_TRACK_ROWS"))
    assert interface.get_playlist_tracks_by_id(PLAYLIST_ID) == []


def test_id_reader_merges_bulk_file_track_locations(monkeypatch):
    interface = AppleMusicInterface()
    scripts = []
    row = f"Song\t{TRACK_ID}\tArtist\tAlbum\tGenre\t120\t2020\tComposer\t180\t"
    stream = "Stream\t8877665544332211\tArtist\tAlbum\tGenre\t0\t2021\t\t150\t"
    response = (
        "TRACK_ROWS\n" + row + "\n" + stream + "\nEND_TRACK_ROWS"
        f"\nFILE_ROWS\n{TRACK_ID}\t/Volumes/Music/song.aiff\nEND_FILE_ROWS"
    )

    def fake_run(script):
        scripts.append(script)
        return True, response

    monkeypatch.setattr(interface, "_run_applescript", fake_run)
    tracks = interface.get_playlist_tracks_by_id(PLAYLIST_ID)

    assert tracks[0]["filepath"] == "/Volumes/Music/song.aiff"
    assert tracks[1]["filepath"] == ""
    assert "persistent ID of every file track of targetPlaylist" in scripts[0]
    assert "location of every track of targetPlaylist" not in scripts[0]


def test_id_reader_preserves_empty_trailing_fields_through_runner_trimming(monkeypatch):
    interface = AppleMusicInterface()
    row = f"Song\t{TRACK_ID}\tArtist\tAlbum\tGenre\t120\t2020\t\t\t"

    class Process:
        returncode = 0

        def communicate(self, input, timeout):
            if 'return "TRACK_ROWS" & linefeed & outputText & linefeed & "END_TRACK_ROWS"' in input:
                return "TRACK_ROWS\n" + row + "\nEND_TRACK_ROWS\n", ""
            return row + "\n", ""

    monkeypatch.setattr("src.apple_music.subprocess.Popen", lambda *args, **kwargs: Process())
    tracks = interface.get_playlist_tracks_by_id(PLAYLIST_ID)
    assert tracks[0]["persistent_id"] == TRACK_ID
    assert tracks[0]["composer"] == ""
    assert tracks[0]["duration"] == ""
    assert tracks[0]["filepath"] == ""


@pytest.mark.parametrize("output", ["Missing playlist", "Permission denied", "Ambiguous playlist ID"])
def test_id_readers_report_failures_without_name_fallback(monkeypatch, output):
    interface = AppleMusicInterface()
    scripts = []

    def fake_run(script):
        scripts.append(script)
        return False, output

    monkeypatch.setattr(interface, "_run_applescript", fake_run)
    for method in (interface.get_playlist_tracks_by_id, interface.get_playlist_info_by_id):
        with pytest.raises(RuntimeError, match=output):
            method(PLAYLIST_ID)
    assert len(scripts) == 2


@pytest.mark.parametrize("output", ["truncated row", f"Song\t{TRACK_ID}", "Song\tbad-id\t\t\t\t\t\t\t\t"])
def test_id_reader_rejects_malformed_membership(monkeypatch, output):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda script: (True, "TRACK_ROWS\n" + output + "\nEND_TRACK_ROWS"))
    with pytest.raises(RuntimeError, match="Malformed"):
        interface.get_playlist_tracks_by_id(PLAYLIST_ID)


def test_id_info_distinguishes_playlists_with_the_same_name(monkeypatch):
    interface = AppleMusicInterface()
    other_id = "FFEEDDCCBBAA0099"
    scripts = []

    def fake_run(script):
        scripts.append(script)
        return True, 'PLAYLIST_NAME\nSame "Name"\nEND_PLAYLIST_NAME'

    monkeypatch.setattr(interface, "_run_applescript", fake_run)
    assert interface.get_playlist_info_by_id(PLAYLIST_ID) == {"persistent_id": PLAYLIST_ID, "name": 'Same "Name"'}
    assert interface.get_playlist_info_by_id(other_id) == {"persistent_id": other_id, "name": 'Same "Name"'}
    assert f'whose persistent ID is "{PLAYLIST_ID}"' in scripts[0]
    assert f'whose persistent ID is "{other_id}"' in scripts[1]
    assert all("name of targetPlaylist" in script for script in scripts)


def test_id_info_preserves_name_whitespace_through_runner_trimming(monkeypatch):
    interface = AppleMusicInterface()

    class Process:
        returncode = 0

        def communicate(self, input, timeout):
            if '"PLAYLIST_NAME" & linefeed & (name of targetPlaylist)' in input:
                return "PLAYLIST_NAME\n  Same Name  \nEND_PLAYLIST_NAME\n", ""
            return "  Same Name  \n", ""

    monkeypatch.setattr("src.apple_music.subprocess.Popen", lambda *args, **kwargs: Process())
    assert interface.get_playlist_info_by_id(PLAYLIST_ID)["name"] == "  Same Name  "


@pytest.mark.parametrize("bad_id", ["", "name", "AABBCCDDEEFF001", "AABBCCDDEEFF001G", '"\nerror "injected', None, 123])
def test_id_methods_reject_invalid_identity_before_running_music(monkeypatch, bad_id):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda script: pytest.fail("Invalid ID reached Music"))
    for method, args in (
        (interface.get_playlist_tracks_by_id, (bad_id,)),
        (interface.get_playlist_info_by_id, (bad_id,)),
        (interface.add_library_track_to_playlist_by_id, (bad_id, TRACK_ID)),
        (interface.add_library_track_to_playlist_by_id, (PLAYLIST_ID, bad_id)),
        (interface.remove_playlist_track_by_id, (bad_id, TRACK_ID)),
        (interface.remove_playlist_track_by_id, (PLAYLIST_ID, bad_id)),
    ):
        with pytest.raises(ValueError, match="persistent ID"):
            method(*args)


def test_create_playlist_returns_new_id_and_never_reuses_same_name(monkeypatch):
    interface = AppleMusicInterface()
    scripts = []

    def fake_run(script):
        scripts.append(script)
        return True, PLAYLIST_ID

    monkeypatch.setattr(interface, "_run_applescript", fake_run)
    assert interface.create_playlist('Same "Name" \\ copy') == PLAYLIST_ID
    assert 'make new user playlist with properties {name:"Same \\"Name\\" \\\\ copy"}' in scripts[0]
    assert "return persistent ID of createdPlaylist" in scripts[0]
    assert "existing" not in scripts[0]
    assert "whose name" not in scripts[0]


@pytest.mark.parametrize("name", ["", "  ", "a\nb", "a\rb", "a\x00b", None])
def test_create_playlist_rejects_invalid_names_without_running_music(monkeypatch, name):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda script: pytest.fail("Invalid name reached Music"))
    with pytest.raises(ValueError):
        interface.create_playlist(name)


@pytest.mark.parametrize("result", [(False, "Permission denied"), (True, ""), (True, "not-an-id")])
def test_create_playlist_reports_runner_and_identity_failures(monkeypatch, result):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda script: result)
    with pytest.raises(RuntimeError):
        interface.create_playlist("Same Name")


@pytest.mark.parametrize("method", ["add_library_track_to_playlist_by_id", "remove_playlist_track_by_id"])
@pytest.mark.parametrize("result, expected", [((True, "true"), True), ((True, "false"), False), ((False, "Permission denied"), False), ((True, ""), False)])
def test_id_writes_target_exact_membership_and_report_outcome(monkeypatch, method, result, expected):
    interface = AppleMusicInterface()
    scripts = []

    def fake_run(script):
        scripts.append(script)
        return result

    monkeypatch.setattr(interface, "_run_applescript", fake_run)
    assert getattr(interface, method)(PLAYLIST_ID, TRACK_ID) is expected
    assert len(scripts) == 1
    assert f'every user playlist whose persistent ID is "{PLAYLIST_ID}"' in scripts[0]
    assert 'count of playlistMatches' in scripts[0]
    assert "smart of targetPlaylist" in scripts[0]
    assert 'user playlist "' not in scripts[0]
    if method.startswith("add_"):
        assert f'library playlist 1 whose persistent ID is "{TRACK_ID}"' in scripts[0]
        assert "duplicate sourceTrack to targetPlaylist" in scripts[0]
    else:
        assert f'persistent ID of playlistTrack is "{TRACK_ID}"' in scripts[0]
        assert "delete playlistTrack\n            return true" in scripts[0]
        assert "delete targetPlaylist" not in scripts[0]


def fake_process_output(monkeypatch, output, returncode=0):
    scripts = []

    class Process:
        def communicate(self, input, timeout):
            scripts.append(input)
            return output, "Provider denied access" if returncode else ""

    Process.returncode = returncode
    monkeypatch.setattr("src.apple_music.subprocess.Popen", lambda *args, **kwargs: Process())
    return scripts


def test_strict_source_list_keeps_duplicate_names_ids_and_exact_text(monkeypatch):
    output = (
        f'PLAYLIST_ROWS\n{PLAYLIST_ID.lower()}\t  Same, "Name"  \t2\n'
        'FFEEDDCCBBAA0099\t  Same, "Name"  \t0\nEND_PLAYLIST_ROWS\n'
    )
    scripts = fake_process_output(monkeypatch, output)
    rows = AppleMusicInterface().get_user_playlists_with_counts_strict()
    assert rows == [
        {"persistent_id": PLAYLIST_ID, "name": '  Same, "Name"  ', "track_count": 2},
        {"persistent_id": "FFEEDDCCBBAA0099", "name": '  Same, "Name"  ', "track_count": 0},
    ]
    assert len(scripts) == 1
    assert "every user playlist" in scripts[0]
    assert "class of pl is not folder playlist" in scripts[0]
    assert "special kind of pl is none" in scripts[0]
    assert "persistent ID of pl" in scripts[0]
    assert "count of tracks of pl" in scripts[0]
    assert "error errMsg" in scripts[0]


@pytest.mark.parametrize("method, frame", [
    ("get_user_playlists_with_counts_strict", "PLAYLIST_ROWS"),
    ("get_library_tracks_strict", "TRACK_ROWS"),
])
def test_strict_enumerations_accept_only_framed_empty_success(monkeypatch, method, frame):
    fake_process_output(monkeypatch, f"{frame}\n\nEND_{frame}\n")
    assert getattr(AppleMusicInterface(), method)() == []
    fake_process_output(monkeypatch, "")
    with pytest.raises(RuntimeError, match="Malformed"):
        getattr(AppleMusicInterface(), method)()
    fake_process_output(monkeypatch, "", returncode=1)
    with pytest.raises(RuntimeError, match="Provider denied access"):
        getattr(AppleMusicInterface(), method)()


@pytest.mark.parametrize("row", [
    "bad-id\tName\t2", f"{PLAYLIST_ID}\tName", f"{PLAYLIST_ID}\tName\t-1",
    f"{PLAYLIST_ID}\tName\tunknown", f"{PLAYLIST_ID}\t\t2",
    f"{PLAYLIST_ID}\tName\t2\textra", f"{PLAYLIST_ID}\tName\t2\n",
    f"{PLAYLIST_ID}\tName\t2\n{PLAYLIST_ID.lower()}\tOther\t3",
])
def test_strict_source_list_rejects_malformed_or_ambiguous_rows(monkeypatch, row):
    fake_process_output(monkeypatch, f"PLAYLIST_ROWS\n{row}\nEND_PLAYLIST_ROWS")
    with pytest.raises(RuntimeError, match="Malformed|ambiguous"):
        AppleMusicInterface().get_user_playlists_with_counts_strict()


def test_strict_library_enumerates_real_ids_and_all_metadata(monkeypatch):
    row = f"  Song  \t{TRACK_ID}\tArtist\tAlbum\tGenre\t120\t2020\tComposer\t180\t"
    scripts = fake_process_output(monkeypatch, f"TRACK_ROWS\n{row}\nEND_TRACK_ROWS\n")
    assert AppleMusicInterface().get_library_tracks_strict() == [{
        "persistent_id": TRACK_ID, "name": "  Song  ", "title": "  Song  ",
        "artist": "Artist", "album": "Album", "genre": "Genre", "bpm": "120",
        "year": "2020", "composer": "Composer", "duration": "180", "filepath": "",
    }]
    assert len(scripts) == 1
    assert "set targetPlaylist to library playlist 1" in scripts[0]
    assert "set trackIDs to persistent ID of every track of targetPlaylist" in scripts[0]
    assert 'set trackLocations to {}' not in scripts[0]
    assert 'set textValue to ""\n    end try' not in scripts[0]
    assert r'my replaceText("\\", "\\\\", textValue)' in scripts[0]
    assert r'my replaceText(tab, "\\t", textValue)' in scripts[0]


@pytest.mark.parametrize("row", [
    f"Song\t{TRACK_ID}", "Song\tbad-id\t\t\t\t\t\t\t\t",
    f"\t{TRACK_ID}\t\t\t\t\t\t\t\t", f"Song\t{TRACK_ID}\t\t\t\t\t\t\t\t\textra",
    f"Song\t{TRACK_ID}\t\t\t\t\t\t\t\t\nSong\t{TRACK_ID}\t\t\t\t\t\t\t\t",
])
def test_strict_library_rejects_incomplete_and_ambiguous_records(monkeypatch, row):
    fake_process_output(monkeypatch, f"TRACK_ROWS\n{row}\nEND_TRACK_ROWS")
    with pytest.raises(RuntimeError, match="Malformed|ambiguous"):
        AppleMusicInterface().get_library_tracks_strict()


def test_strict_readers_preserve_escaped_metadata_and_names(monkeypatch):
    fake_process_output(monkeypatch, f"PLAYLIST_ROWS\n{PLAYLIST_ID}\tName\\tTab\\nLine\\rReturn\\\\Slash\t1\nEND_PLAYLIST_ROWS")
    assert AppleMusicInterface().get_user_playlists_with_counts_strict()[0]["name"] == "Name\tTab\nLine\rReturn\\Slash"
    row = f"Song\\nTitle\t{TRACK_ID}\tArtist\\tName\tAlbum\tGenre\t0\t0\t\t180\t/tmp/slash\\\\song"
    fake_process_output(monkeypatch, f"TRACK_ROWS\n{row}\nEND_TRACK_ROWS")
    track = AppleMusicInterface().get_library_tracks_strict()[0]
    assert track["name"] == "Song\nTitle"
    assert track["artist"] == "Artist\tName"
    assert track["filepath"] == "/tmp/slash\\song"


@pytest.mark.parametrize("bad_text", ["Name\\unknown", "Name\\"])
@pytest.mark.parametrize("method, frame, row", [
    ("get_user_playlists_with_counts_strict", "PLAYLIST_ROWS", f"{PLAYLIST_ID}\t{{text}}\t1"),
    ("get_library_tracks_strict", "TRACK_ROWS", f"{{text}}\t{TRACK_ID}\t\t\t\t\t\t\t\t"),
])
def test_strict_readers_reject_malformed_text_escapes(monkeypatch, bad_text, method, frame, row):
    fake_process_output(monkeypatch, f"{frame}\n{row.format(text=bad_text)}\nEND_{frame}")
    with pytest.raises(RuntimeError, match="Malformed"):
        getattr(AppleMusicInterface(), method)()


def test_strict_library_preserves_distinct_ids_and_unusual_metadata(monkeypatch):
    row = f"Song\u2028Title\t{PLAYLIST_ID.lower()}\tmissing value\tAlbum\t\t0\t0\t\t180\t"
    other = row.replace(PLAYLIST_ID.lower(), "FFEEDDCCBBAA0099")
    fake_process_output(monkeypatch, f"TRACK_ROWS\n{row}\n{other}\nEND_TRACK_ROWS")
    tracks = AppleMusicInterface().get_library_tracks_strict()
    assert [track["persistent_id"] for track in tracks] == [PLAYLIST_ID, "FFEEDDCCBBAA0099"]
    assert tracks[0]["name"] == "Song\u2028Title"
    assert tracks[0]["artist"] == "missing value"


@pytest.mark.parametrize("method", ["get_user_playlists_with_counts_strict", "get_library_tracks_strict"])
def test_strict_readers_propagate_runner_start_failure(monkeypatch, method):
    def fail_start(*args, **kwargs):
        raise OSError("fake osascript unavailable")

    monkeypatch.setattr("src.apple_music.subprocess.Popen", fail_start)
    with pytest.raises(RuntimeError, match="fake osascript unavailable"):
        getattr(AppleMusicInterface(), method)()
