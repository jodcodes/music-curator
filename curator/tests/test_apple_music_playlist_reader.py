from src.apple_music import AppleMusicInterface


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
