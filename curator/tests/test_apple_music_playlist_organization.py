"""Recorded AppleScript output and script inspection only; no live Music calls."""
import pytest

from src.apple_music import AppleMusicInterface


P, F, G = "AABBCCDDEEFF0011", "1122334455667788", "FFEEDDCCBBAA0099"


@pytest.fixture(autouse=True)
def block_music(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Never execute real AppleScript in adapter tests")
    monkeypatch.setattr("src.apple_music.subprocess.Popen", forbidden)
    monkeypatch.setattr("src.apple_music.subprocess.run", forbidden)


def recorded(monkeypatch, rows, success=True, count=None):
    scripts = []
    def run(script):
        scripts.append(script)
        if not success:
            return False, rows
        total = len(rows.split("\n")) if rows else 0
        return True, f"TOPOLOGY_ROWS\n{total if count is None else count}\n{rows}\nEND_TOPOLOGY_ROWS"
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", run)
    return interface, scripts


def test_topology_preserves_exact_names_duplicate_names_and_full_parent_links(monkeypatch):
    interface, scripts = recorded(monkeypatch,
        f'{F.lower()}\t  Genre\\tRoot\\nName\\\\  \tfolder\t\ttrue\n'
        f'{G}\tDisco/Funk/Soul\tfolder\t{F.lower()}\ttrue\n'
        f'{P.lower()}\tSame Name\tplaylist\t{G}\ttrue\n'
        '0000000000000001\tSame Name\tplaylist\t\tfalse')
    rows = interface.get_playlist_topology_strict()
    assert rows[0] == {"persistent_id": F, "name": "  Genre\tRoot\nName\\  ",
                       "kind": "folder", "parent_id": None, "modifiable": True}
    assert rows[1]["name"] == "Disco/Funk/Soul" and rows[1]["parent_id"] == F
    assert rows[2]["persistent_id"] == P and rows[2]["parent_id"] == G
    assert rows[2]["name"] == rows[3]["name"] and rows[3]["modifiable"] is False
    assert len(scripts) == 1
    assert "every playlist" in scripts[0] and "parent of pl" in scripts[0]
    assert "class of pl is folder playlist" in scripts[0]
    assert "smart of pl" in scripts[0] and "special kind of pl" in scripts[0]
    assert "error errMsg" in scripts[0]
    assert r'my replaceText(tab, "\\t", textValue)' in scripts[0]


@pytest.mark.parametrize("rows", [
    f"bad\tName\tplaylist\t\ttrue", f"{P}\t\tplaylist\t\ttrue",
    f"{P}\tName\tplaylist\t\t1", f"{P}\tName\tother\t\ttrue",
    f"{P}\tName\tplaylist\t\ttrue\textra", f"{P}\tName\\bad\tplaylist\t\ttrue",
    f"{P}\tName\\\tplaylist\t\ttrue", f"{P}\tName\tplaylist\tbad\ttrue",
    f"{P}\tName\tplaylist\t{F}\ttrue",  # Orphan: never silently treated as root.
    f"{P}\tChild\tplaylist\t{F}\ttrue\n{F}\tFolder\tfolder\t{G}\ttrue",
    f"{P}\tName\tplaylist\t{P}\ttrue",  # Parent must be a folder.
    f"{F}\tName\tfolder\t{F}\ttrue",  # Cycle.
    f"{F}\tOne\tfolder\t{G}\ttrue\n{G}\tTwo\tfolder\t{F}\ttrue",
    f"{P}\tOne\tplaylist\t\ttrue\n{P.lower()}\tTwo\tplaylist\t\ttrue",
])
def test_topology_rejects_malformed_ids_parents_cycles_and_duplicates(monkeypatch, rows):
    interface, _ = recorded(monkeypatch, rows)
    with pytest.raises(RuntimeError):
        interface.get_playlist_topology_strict()


def test_topology_requires_full_count_and_framed_empty_read(monkeypatch):
    interface, _ = recorded(monkeypatch, "")
    assert interface.get_playlist_topology_strict() == []
    interface, _ = recorded(monkeypatch, f"{P}\tName\tplaylist\t\ttrue", count=2)
    with pytest.raises(RuntimeError):
        interface.get_playlist_topology_strict()
    monkeypatch.setattr(interface, "_run_applescript", lambda s: (True, ""))
    with pytest.raises(RuntimeError):
        interface.get_playlist_topology_strict()


def test_topology_permission_error_propagates(monkeypatch):
    interface, _ = recorded(monkeypatch, "Permission denied", success=False)
    with pytest.raises(RuntimeError, match="Permission denied"):
        interface.get_playlist_topology_strict()


@pytest.mark.parametrize("parent", [None, F.lower()])
def test_create_true_folder_under_exact_parent_id_escapes_name(monkeypatch, parent):
    interface = AppleMusicInterface()
    scripts = []
    def run(script):
        scripts.append(script)
        return True, G.lower()
    monkeypatch.setattr(interface, "_run_applescript", run)
    assert interface.create_playlist_folder_by_id('Disco/Funk/Soul "mix" \\ copy', parent) == G
    assert 'make new folder playlist' in scripts[0]
    assert 'name:"Disco/Funk/Soul \\"mix\\" \\\\ copy"' in scripts[0]
    assert 'whose name' not in scripts[0]
    if parent:
        assert f'every playlist whose persistent ID is "{F}"' in scripts[0]
        assert 'class of targetFolder is not folder playlist' in scripts[0]
        assert 'at targetFolder' in scripts[0]
    else:
        assert 'at targetFolder' not in scripts[0]


@pytest.mark.parametrize("bad", ["", "a\nb", "a\x00b", None])
def test_folder_create_rejects_invalid_names_without_call(monkeypatch, bad):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda s: pytest.fail("Invalid name reached runner"))
    with pytest.raises(ValueError):
        interface.create_playlist_folder_by_id(bad, None)


@pytest.mark.parametrize("result", [(False, "Permission denied"), (True, ""), (True, "not-an-id")])
def test_folder_create_failure_is_uncertain_and_never_retried(monkeypatch, result):
    interface = AppleMusicInterface()
    scripts = []
    monkeypatch.setattr(interface, "_run_applescript", lambda s: (scripts.append(s) or result))
    with pytest.raises(RuntimeError):
        interface.create_playlist_folder_by_id("Genre", None)
    assert len(scripts) == 1


@pytest.mark.parametrize("parent", [None, F])
@pytest.mark.parametrize("result,expected", [((True, "true"), True), ((True, "false"), False),
                                          ((True, ""), False), ((False, "Permission denied"), False)])
def test_move_uses_only_ids_validates_classes_and_reports_exact_boolean(monkeypatch, parent, result, expected):
    interface = AppleMusicInterface()
    scripts = []
    monkeypatch.setattr(interface, "_run_applescript", lambda s: (scripts.append(s) or result))
    assert interface.move_playlist_by_id(P.lower(), parent) is expected
    assert f'whose persistent ID is "{P}"' in scripts[0]
    assert 'whose name' not in scripts[0] and 'smart of targetPlaylist' in scripts[0]
    assert 'special kind of targetPlaylist' in scripts[0]
    if parent:
        assert f'whose persistent ID is "{F}"' in scripts[0]
        assert 'class of targetFolder is not folder playlist' in scripts[0]
        assert 'move targetPlaylist to targetFolder' in scripts[0]
    else:
        assert 'move targetPlaylist to application "Music"' in scripts[0]


@pytest.mark.parametrize("bad", ["Genre", "", '"injected', 123])
def test_new_writers_reject_invalid_ids_before_runner(monkeypatch, bad):
    interface = AppleMusicInterface()
    monkeypatch.setattr(interface, "_run_applescript", lambda s: pytest.fail("Invalid ID reached runner"))
    for method, args in [(interface.create_playlist_folder_by_id, ("Genre", bad)),
                         (interface.move_playlist_by_id, (bad, F)),
                         (interface.move_playlist_by_id, (P, bad))]:
        with pytest.raises(ValueError):
            method(*args)
