"""M8 runs only against an in-memory library, never Music or providers."""
import copy
import hashlib
import json

import pytest

from src.playlist_manager import PlaylistManager


P1, P2, F1, F2, ROOT, JAZZ, UNKNOWN = [f"{n:016X}" for n in range(1, 8)]
TRACK = "AABBCCDDEEFF0011"


def row(pid, name, kind="playlist", parent=None, modifiable=True):
    return {"persistent_id": pid, "name": name, "kind": kind,
            "parent_id": parent, "modifiable": modifiable}


class FakeMusic:
    def __init__(self):
        self.rows = [row(F1, "Inbox", "folder"), row(F2, "Archive", "folder"),
                     row(P1, "Same Name", parent=F1), row(P2, "Same Name", parent=F2)]
        self.tracks = {pid: [{"persistent_id": TRACK, "name": "Song", "genre": "Jazz"}]
                       for pid in (P1, P2)}
        self.writes = []
        self.reads = []
        self.create_failure = None
        self.move_failure = None

    def get_playlist_topology_strict(self):
        self.reads.append("topology")
        return copy.deepcopy(self.rows)

    def get_playlist_tracks_by_id(self, pid):
        self.reads.append(pid)
        value = self.tracks[pid]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def create_playlist_folder_by_id(self, name, parent):
        self.writes.append(("create", name, parent))
        if self.create_failure == "permission":
            raise RuntimeError("Permission denied")
        pid = f"{100 + len(self.writes):016X}"
        created = row(pid, name, "folder", parent)
        if self.create_failure == "wrong_parent":
            created["parent_id"] = F2
        if self.create_failure == "wrong_name":
            created["name"] = "Wrong"
        if self.create_failure == "playlist":
            created["kind"] = "playlist"
        if self.create_failure == "collision":
            self.rows.append(row(f"{500:016X}", name, "folder", parent))
        self.rows.append(created)
        return "invalid" if self.create_failure == "bad_id" else pid

    def move_playlist_by_id(self, pid, parent):
        self.writes.append(("move", pid, parent))
        if self.move_failure == "permission":
            raise RuntimeError("Permission denied")
        if self.move_failure == "false":
            return False
        if self.move_failure != "uncertain":
            next(r for r in self.rows if r["persistent_id"] == pid)["parent_id"] = parent
        return True


class Classifier:
    enable_genre_enrichment = False

    def __init__(self, music, genre="jazz"):
        self.music = music
        self.genre = genre
        self.calls = []

    def classify_playlist(self, tracks, pid):
        assert "topology" in self.music.reads and pid in self.music.reads
        self.calls.append((copy.deepcopy(tracks), pid))
        # A classifier may mutate metadata; the source snapshot must not change.
        tracks[0]["genre"] = "Classified locally"
        return self.genre, {"confidence": 0.75}


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("M8 tests must never invoke Music")
    monkeypatch.setattr("src.apple_music.subprocess.Popen", forbidden)
    monkeypatch.setattr("src.apple_music.subprocess.run", forbidden)


@pytest.fixture
def setup(monkeypatch):
    music = FakeMusic()
    monkeypatch.setattr("src.playlist_manager.AppleMusicInterface", lambda *args: music)
    manager = PlaylistManager()
    return manager, music, Classifier(music)


def preview(setup, selected=None):
    manager, music, classifier = setup
    return manager.preview_playlist_organization(selected or [P1, P2], classifier)


def redigest(plan):
    payload = {k: v for k, v in plan.items() if k != "fingerprint"}
    plan["fingerprint"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def test_preview_frozen_ids_duplicate_names_nested_paths_zero_writes(setup):
    manager, music, classifier = setup
    music.rows.insert(0, row(ROOT, "Collection", "folder"))
    music.rows[1]["parent_id"] = ROOT
    plan = preview(setup)
    assert manager.dry_run is True
    assert plan["selected_ids"] == [P1, P2]
    a, b = plan["operations"]
    assert a["source"]["name"] == b["source"]["name"] == "Same Name"
    assert a["current_components"] == ["Collection", "Inbox"]
    assert b["current_components"] == ["Archive"]
    assert a["target_components"] == ["Genre", "Jazz"]
    assert a["target_chain_ids"] == [None, None]
    assert a["tracks"][0]["genre"] == "Jazz"
    assert a["genre"] == "jazz" and a["confidence"] == 0.75
    assert [pid for _, pid in classifier.calls] == [P1, P2]
    assert music.writes == []
    json.dumps(plan, allow_nan=False)


@pytest.mark.parametrize("selected", [[], None, "all", ["Same Name"], [P1, P1], [P1, P1.lower()], [123]])
def test_selection_requires_explicit_nonempty_unique_stable_ids(setup, selected):
    manager, music, classifier = setup
    with pytest.raises(ValueError):
        manager.preview_playlist_organization(selected, classifier)
    assert music.writes == [] and classifier.calls == []


@pytest.mark.parametrize("confirmed", [False, None, 1, "true", [], {}])
def test_apply_requires_literal_true_zero_writes(setup, confirmed):
    manager, music, classifier = setup
    plan = preview(setup)
    result = manager.apply_playlist_organization(plan, confirmed=confirmed)
    assert result["success"] is False
    assert result["moved"] == result["applied"] == result["failed"] == 0
    assert result["skipped"] == 2 and len(result["results"]) == 2
    assert music.writes == []


def test_unknown_folder_special_empty_and_unknown_genre_are_explicit_skips(setup):
    manager, music, classifier = setup
    music.rows[3]["modifiable"] = False
    plan = manager.preview_playlist_organization([UNKNOWN, F1, P2], classifier)
    assert [op["reason"] for op in plan["operations"]] == ["missing_source", "ineligible_source", "ineligible_source"]
    assert classifier.calls == [] and music.writes == []
    music.tracks[P1] = []
    assert preview(setup, [P1])["operations"][0]["reason"] == "empty_playlist"
    music.tracks[P1] = [{"persistent_id": TRACK, "name": "Song"}]
    classifier.genre = "not_mapped"
    assert preview(setup, [P1])["operations"][0]["reason"] == "unknown_genre"
    classifier.genre = None
    assert preview(setup, [P1])["operations"][0]["reason"] == "unclassified"


def test_strict_read_failure_is_not_empty_or_classified(setup):
    manager, music, classifier = setup
    music.tracks[P1] = RuntimeError("Permission denied")
    plan = preview(setup)
    assert plan["operations"][0]["reason"] == "tracks_unavailable"
    assert plan["operations"][0]["tracks"] is None
    assert [pid for _, pid in classifier.calls] == [P2]
    assert music.writes == []


def test_preview_refuses_provider_enrichment(setup):
    manager, music, classifier = setup
    classifier.enable_genre_enrichment = True
    with pytest.raises(ValueError, match="enrichment"):
        preview(setup)
    assert music.writes == [] and classifier.calls == []


def test_literal_slash_target_reuses_unique_full_chain(setup):
    manager, music, classifier = setup
    classifier.genre = "disco_funk_soul"
    music.rows += [row(ROOT, "Genre", "folder"), row(JAZZ, "Disco/Funk/Soul", "folder", ROOT),
                   row(UNKNOWN, "Disco/Funk/Soul", "folder", F2)]
    plan = preview(setup)
    assert plan["operations"][0]["target_components"] == ["Genre", "Disco/Funk/Soul"]
    assert plan["operations"][0]["target_chain_ids"] == [ROOT, JAZZ]
    calls = len(classifier.calls)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert result["success"] is True and result["moved"] == result["applied"] == 2
    assert music.writes == [("move", P1, JAZZ), ("move", P2, JAZZ)]
    assert len(classifier.calls) == calls
    assert result["results"][0]["source_id"] == P1
    assert result["results"][0]["current_components"] == ["Inbox"]


def test_apply_creates_true_nested_folders_once_then_fresh_preview_is_noop(setup):
    manager, music, classifier = setup
    result = manager.apply_playlist_organization(preview(setup), confirmed=True)
    assert result["success"] is True and result["moved"] == 2
    assert [w[0] for w in music.writes] == ["create", "create", "move", "move"]
    root_id = next(r["persistent_id"] for r in music.rows if r["name"] == "Genre")
    assert music.writes[1][2] == root_id
    fresh = preview(setup)
    assert all(op["reason"] == "already_correct" for op in fresh["operations"])
    writes = list(music.writes)
    no_op = manager.apply_playlist_organization(fresh, confirmed=True)
    assert no_op["moved"] == no_op["failed"] == 0 and no_op["skipped"] == 2
    assert no_op["success"] is False  # No blanket success for skipped selections.
    assert music.writes == writes


@pytest.mark.parametrize("collision", ["playlist_root", "playlist_child", "duplicate_root", "duplicate_child"])
def test_target_folder_vs_playlist_or_ambiguous_sibling_collision(setup, collision):
    manager, music, classifier = setup
    music.rows += [row(ROOT, "Genre", "folder")]
    if collision == "playlist_root":
        music.rows[-1]["kind"] = "playlist"
    elif collision == "duplicate_root":
        music.rows.append(row(JAZZ, "Genre", "folder"))
    else:
        music.rows.append(row(JAZZ, "Jazz", "playlist" if collision == "playlist_child" else "folder", ROOT))
        if collision == "duplicate_child":
            music.rows.append(row(UNKNOWN, "Jazz", "folder", ROOT))
    plan = preview(setup)
    assert all(op["action"] == "skip" and op["reason"] == "target_collision" for op in plan["operations"])
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert result["success"] is False and music.writes == []


@pytest.mark.parametrize("stale", ["source_name", "source_parent", "source_permission", "tracks", "track_order", "target_collision", "folder_name"])
def test_global_preflight_detects_stale_later_source_before_any_write(setup, stale):
    manager, music, classifier = setup
    music.tracks[P2] *= 2
    music.tracks[P2][1] = {"persistent_id": "FFEEDDCCBBAA0099", "name": "Other"}
    plan = preview(setup)
    if stale == "source_name":
        music.rows[3]["name"] = "Renamed"
    elif stale == "source_parent":
        music.rows[3]["parent_id"] = F1
    elif stale == "source_permission":
        music.rows[3]["modifiable"] = False
    elif stale == "tracks":
        music.tracks[P2][0]["genre"] = "Rock"
    elif stale == "track_order":
        music.tracks[P2].reverse()
    elif stale == "target_collision":
        music.rows.append(row(ROOT, "Genre", "playlist"))
    else:
        music.rows[1]["name"] = "Changed"
    calls = len(classifier.calls)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert not result["success"] and result["failed"] >= 1
    assert result["moved"] == 0 and len(result["results"]) == 2
    assert len(classifier.calls) == calls and music.writes == []


@pytest.mark.parametrize("tamper", ["digest", "target", "source", "chain", "action", "schema", "version", "mapping"])
def test_tampered_plan_rejected_even_with_recomputed_digest_for_invalid_semantics(setup, tamper):
    manager, music, classifier = setup
    plan = copy.deepcopy(preview(setup))
    if tamper == "digest":
        plan["fingerprint"] = "0" * 64
    elif tamper == "target":
        plan["operations"][0]["target_components"] = ["Genre", "Rock"]
    elif tamper == "source":
        plan["operations"][0]["source_id"] = P2
    elif tamper == "chain":
        plan["operations"][0]["target_chain_ids"] = [F1, F2]
    elif tamper == "action":
        plan["operations"][0]["reason"] = "already_correct"
    elif tamper == "schema":
        del plan["operations"][0]["tracks"]
    elif tamper == "version":
        plan["version"] = True
    else:
        plan["genre_folders"]["jazz"] = "Rock"
    if tamper != "digest":
        redigest(plan)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert not result["success"] and music.writes == []
    assert len(result["results"]) == 2


def test_apply_rereads_actual_mapping(setup, monkeypatch):
    manager, music, classifier = setup
    plan = preview(setup)
    changed = dict(plan["genre_folders"], jazz="Changed")
    monkeypatch.setattr(manager, "_load_genre_folders", lambda: changed)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert not result["success"] and music.writes == []


@pytest.mark.parametrize("failure", ["permission", "bad_id", "wrong_parent", "wrong_name", "playlist", "collision"])
def test_failed_or_uncertain_folder_stops_all_remaining_writes(setup, failure):
    manager, music, classifier = setup
    music.create_failure = failure
    result = manager.apply_playlist_organization(preview(setup), confirmed=True)
    assert result["moved"] == result["applied"] == 0
    assert result["failed"] == 1 and result["skipped"] == 1 and not result["success"]
    assert [r["status"] for r in result["results"]] == ["failed", "skipped"]
    assert len(music.writes) == 1


@pytest.mark.parametrize("failure", ["permission", "false", "uncertain"])
def test_failed_or_uncertain_move_honest_counts_and_no_retry(setup, failure):
    manager, music, classifier = setup
    music.rows += [row(ROOT, "Genre", "folder"), row(JAZZ, "Jazz", "folder", ROOT)]
    music.move_failure = failure
    result = manager.apply_playlist_organization(preview(setup), confirmed=True)
    assert result["moved"] == 0 and result["failed"] == 1 and result["skipped"] == 1
    assert result["success"] is False and music.writes == [("move", P1, JAZZ)]


def test_partial_success_is_counted_before_later_failure(setup, monkeypatch):
    manager, music, classifier = setup
    original = music.move_playlist_by_id
    def move(pid, parent):
        if pid == P2:
            music.move_failure = "false"
        return original(pid, parent)
    monkeypatch.setattr(music, "move_playlist_by_id", move)
    result = manager.apply_playlist_organization(preview(setup), confirmed=True)
    assert result["moved"] == result["applied"] == 1
    assert result["failed"] == 1 and result["skipped"] == 0 and not result["success"]


def test_shared_missing_child_under_existing_root_created_once(setup):
    manager, music, classifier = setup
    music.rows.append(row(ROOT, "Genre", "folder"))
    plan = preview(setup)
    assert plan["operations"][0]["target_chain_ids"] == [ROOT, None]
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert result["success"] is True
    assert music.writes[0] == ("create", "Jazz", ROOT)
    assert [w[0] for w in music.writes] == ["create", "move", "move"]


def test_all_strict_membership_reads_precede_any_classification(setup, monkeypatch):
    manager, music, classifier = setup
    original = classifier.classify_playlist
    def classify(tracks, pid):
        assert P1 in music.reads and P2 in music.reads
        return original(tracks, pid)
    monkeypatch.setattr(classifier, "classify_playlist", classify)
    preview(setup)
    assert len(classifier.calls) == 2


def test_mixed_missing_and_moved_selections_are_not_blanket_success(setup):
    manager, music, classifier = setup
    plan = manager.preview_playlist_organization([UNKNOWN, P1], classifier)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert result["success"] is False
    assert result["moved"] == 1 and result["skipped"] == 1 and result["failed"] == 0
    assert [r["source_id"] for r in result["results"]] == [UNKNOWN, P1]


@pytest.mark.parametrize("stage", ["preflight", "post_create", "post_move"])
def test_permission_failure_on_verification_stops_remaining_operations(setup, monkeypatch, stage):
    manager, music, classifier = setup
    plan = preview(setup)
    original = music.get_playlist_topology_strict
    def topology():
        if (stage == "preflight" or
                (stage == "post_create" and music.writes) or
                (stage == "post_move" and any(w[0] == "move" for w in music.writes))):
            raise RuntimeError("Read permission denied")
        return original()
    monkeypatch.setattr(music, "get_playlist_topology_strict", topology)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert result["failed"] == 1 and result["skipped"] == 1 and result["moved"] == 0
    assert len(music.writes) == {"preflight": 0, "post_create": 1, "post_move": 3}[stage]
    assert not result["success"]


def test_global_track_preflight_permission_error_prevents_first_source_write(setup):
    manager, music, classifier = setup
    plan = preview(setup)
    music.tracks[P2] = RuntimeError("Permission denied")
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert not result["success"] and result["moved"] == 0 and music.writes == []
    assert [r["source_id"] for r in result["results"] if r["status"] == "failed"] == [P2]


@pytest.mark.parametrize("change", ["source_name", "source_parent", "source_modifiable", "current_components", "target_components"])
def test_frozen_source_and_path_tampering_refused_with_valid_digest(setup, change):
    manager, music, classifier = setup
    plan = preview(setup)
    op = plan["operations"][0]
    if change == "source_name":
        op["source"]["name"] = "Renamed"
    elif change == "source_parent":
        op["source"]["parent_id"] = F2
    elif change == "source_modifiable":
        op["source"]["modifiable"] = 1  # bool/int equality must not bypass schema checks.
    else:
        op[change] = ["Wrong", "Path"]
    redigest(plan)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert not result["success"] and music.writes == []


def test_nonmodifiable_target_folder_is_refused(setup):
    manager, music, classifier = setup
    music.rows.append(row(ROOT, "Genre", "folder", modifiable=False))
    plan = preview(setup)
    assert all(op["reason"] == "target_collision" for op in plan["operations"])
    assert not manager.apply_playlist_organization(plan, confirmed=True)["success"]
    assert music.writes == []


def test_malformed_source_schema_does_not_crash_rejection_report(setup):
    manager, music, classifier = setup
    plan = preview(setup)
    plan["operations"][0]["source"] = "not a row"
    redigest(plan)
    result = manager.apply_playlist_organization(plan, confirmed=True)
    assert not result["success"] and len(result["results"]) == 2 and music.writes == []


def test_empty_or_malformed_apply_plan_has_no_writers(setup):
    manager, music, classifier = setup
    for plan in (None, {}, {"selected_ids": [P1], "operations": []}):
        assert not manager.apply_playlist_organization(plan, confirmed=True)["success"]
    assert music.writes == []
