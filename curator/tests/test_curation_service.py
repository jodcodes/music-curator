from unittest.mock import patch
from copy import deepcopy
import json

import pytest

from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
)
from src.apple_music import AppleMusicInterface
from src.curation_service import CurationService
from src.curation_store import CurationStore


SOURCE_ID = "0000000000000001"
OTHER_ID = "0000000000000002"


class SplitMusic:
    """Ordered occurrence store; never invokes Music.app."""

    def __init__(self):
        self.playlists = {
            SOURCE_ID: {"name": "Same", "tracks": [f"{i % 5 + 10:016X}" for i in range(101)]},
            OTHER_ID: {"name": "Same", "tracks": ["0000000000000020"] * 101},
            "0000000000000003": {"name": "Same · 01", "tracks": []},
        }
        self.writes = []
        self.fail_create = False
        self.fail_add_at = None
        self.before_create = None

    def get_playlist_info_by_id(self, playlist_id):
        return {"persistent_id": playlist_id, "name": self.playlists[playlist_id]["name"]}

    def get_playlist_tracks_by_id(self, playlist_id):
        return [{"persistent_id": item} for item in self.playlists[playlist_id]["tracks"]]

    def create_playlist(self, name):
        if self.before_create:
            self.before_create()
        playlist_id = f"{len(self.playlists) + 100:016X}"
        self.playlists[playlist_id] = {"name": name, "tracks": []}
        self.writes.append(("create", playlist_id))
        if self.fail_create:
            raise TimeoutError("response lost after create")
        return playlist_id

    def add_library_track_to_playlist_by_id(self, playlist_id, track_id):
        self.playlists[playlist_id]["tracks"].append(track_id)
        self.writes.append(("add", playlist_id, track_id))
        if self.fail_add_at == len(self.playlists[playlist_id]["tracks"]):
            return False  # A timeout may have written successfully.
        return True


@pytest.fixture
def split_service(tmp_path):
    return CurationService(apple_music=SplitMusic(), split_journal_path=tmp_path / "split-journal")


def test_split_preview_is_read_only_balanced_and_preserves_occurrences(split_service):
    plan = split_service.preview_playlist_splits([SOURCE_ID, OTHER_ID])
    first, second = plan["sources"]
    assert first["source_id"] == SOURCE_ID
    assert second["source_id"] == OTHER_ID
    assert [p["name"] for p in first["parts"]] == ["Same · 01", "Same · 02"]
    assert [len(p["track_ids"]) for p in first["parts"]] == [51, 50]
    assert sum((p["track_ids"] for p in first["parts"]), []) == first["track_ids"]
    assert plan == split_service.preview_playlist_splits([SOURCE_ID, OTHER_ID])
    assert split_service.apple_music.writes == []
    assert not split_service.split_journal_path.exists()


def test_split_apply_requires_literal_confirmation_and_existing_journal(split_service):
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    for confirmation in (False, "yes", 1):
        assert not split_service.apply_playlist_splits(plan, confirmed=confirmation)["success"]
    assert not split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    assert split_service.apple_music.writes == []
    assert not split_service.split_journal_path.exists()


def test_split_apply_exact_ids_and_durable_retry_without_duplicate_outputs(split_service):
    music = split_service.apple_music
    original = deepcopy(music.playlists)
    plan = split_service.preview_playlist_splits([SOURCE_ID, OTHER_ID])
    split_service.initialize_playlist_split_journal()
    result = split_service.apply_playlist_splits(plan, confirmed=True)
    assert result["success"]
    assert len(result["parts"]) == 4
    for source in plan["sources"]:
        outputs = [p for p in result["parts"] if p["source_id"] == source["source_id"]]
        assert sum((music.playlists[p["playlist_id"]]["tracks"] for p in outputs), []) == source["track_ids"]
    assert all(music.playlists[key] == value for key, value in original.items())
    writes = list(music.writes)
    restarted = CurationService(apple_music=music, split_journal_path=split_service.split_journal_path)
    assert restarted.apply_playlist_splits(plan, confirmed=True)["success"]
    assert music.writes == writes


@pytest.mark.parametrize("mutation", ["reorder", "rename", "add", "tamper", "rehash"])
def test_split_rejects_stale_or_tampered_plan_before_writes(split_service, mutation):
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    split_service.initialize_playlist_split_journal()
    source = split_service.apple_music.playlists[SOURCE_ID]
    if mutation == "reorder":
        source["tracks"].reverse()
    elif mutation == "rename":
        source["name"] = "Changed"
    elif mutation == "add":
        source["tracks"].append("0000000000000090")
    else:
        plan["sources"][0]["parts"][0]["name"] = "Unreviewed"
        if mutation == "rehash":
            import hashlib
            payload = {key: value for key, value in plan.items() if key != "fingerprint"}
            plan["fingerprint"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert not split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    assert split_service.apple_music.writes == []


@pytest.mark.parametrize("operation", ["create", "add"])
def test_split_uncertain_write_blocks_retries_across_restart(split_service, operation):
    music = split_service.apple_music
    original = deepcopy(music.playlists[SOURCE_ID])
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    split_service.initialize_playlist_split_journal()
    music.fail_create = operation == "create"
    music.fail_add_at = 2 if operation == "add" else None
    result = split_service.apply_playlist_splits(plan, confirmed=True)
    assert not result["success"]
    assert result["parts"][0]["status"] == "unresolved"
    writes = list(music.writes)
    restarted = CurationService(apple_music=music, split_journal_path=split_service.split_journal_path)
    assert not restarted.apply_playlist_splits(plan, confirmed=True)["success"]
    assert music.writes == writes
    assert music.playlists[SOURCE_ID] == original


def test_split_concurrent_apply_is_rejected_while_adapter_call_is_running(split_service):
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    split_service.initialize_playlist_split_journal()
    other = CurationService(apple_music=split_service.apple_music, split_journal_path=split_service.split_journal_path)
    nested = []
    split_service.apple_music.before_create = lambda: nested.append(other.apply_playlist_splits(plan, confirmed=True))
    assert split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    assert nested and all(not result["success"] for result in nested)


@pytest.mark.parametrize("damage", ["missing", "corrupt", "invalid", "lock_missing"])
def test_split_journal_damage_never_resets_provenance(split_service, damage):
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    split_service.initialize_playlist_split_journal()
    journal = split_service.split_journal_path / "journal.json"
    if damage == "missing":
        journal.unlink()
    elif damage == "lock_missing":
        (split_service.split_journal_path / "lock").unlink()
    else:
        journal.write_text("{" if damage == "corrupt" else "{}")
    assert not split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    with pytest.raises(FileExistsError):
        split_service.initialize_playlist_split_journal()
    assert split_service.apple_music.writes == []


def test_split_failed_journal_write_stops_before_side_effect(split_service):
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    split_service.initialize_playlist_split_journal()
    with patch("src.curation_service.os.replace", side_effect=OSError("disk full")):
        assert not split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    assert split_service.apple_music.writes == []


def test_split_new_preview_cannot_bypass_unresolved_write(split_service):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    split_service.apple_music.fail_create = True
    assert not split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    split_service.apple_music.playlists[SOURCE_ID]["name"] = "Renamed"
    new_plan = split_service.preview_playlist_splits([SOURCE_ID, OTHER_ID])
    writes = list(split_service.apple_music.writes)
    result = split_service.apply_playlist_splits(new_plan, confirmed=True)
    assert not result["success"]
    assert result["unresolved"][0]["fingerprint"] == plan["fingerprint"]
    assert split_service.apple_music.writes == writes


@pytest.mark.parametrize("operation", ["create", "add"])
def test_split_failed_post_write_journal_save_stays_pending_on_restart(split_service, operation):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    import os
    replace = os.replace

    def fail_after_create(*args):
        writes = split_service.apple_music.writes
        if writes and (operation == "create" or writes[-1][0] == "add"):
            raise OSError("disk full after external create")
        return replace(*args)

    with patch("src.curation_service.os.replace", side_effect=fail_after_create):
        assert not split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    writes = list(split_service.apple_music.writes)
    restarted = CurationService(apple_music=split_service.apple_music, split_journal_path=split_service.split_journal_path)
    assert not restarted.apply_playlist_splits(plan, confirmed=True)["success"]
    assert split_service.apple_music.writes == writes


def test_split_default_journal_uses_same_project_data_directory_across_cwds(tmp_path, monkeypatch):
    first = CurationService(apple_music=SplitMusic()).split_journal_path
    monkeypatch.chdir(tmp_path)
    second = CurationService(apple_music=SplitMusic()).split_journal_path
    assert first == second
    assert first.is_absolute()


def test_split_safe_read_failure_resumes_confirmed_occurrences_after_restart(split_service):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    music = split_service.apple_music
    reader = music.get_playlist_tracks_by_id
    checks = []

    def fail_before_next_write(playlist_id):
        tracks = reader(playlist_id)
        if playlist_id not in (SOURCE_ID, OTHER_ID) and len(tracks) == 2:
            checks.append(playlist_id)
            if len(checks) == 2:
                raise RuntimeError("temporary read failure before intent")
        return tracks

    music.get_playlist_tracks_by_id = fail_before_next_write
    result = split_service.apply_playlist_splits(plan, confirmed=True)
    assert not result["success"]
    assert result["parts"][0]["status"] == "partial"
    music.get_playlist_tracks_by_id = reader
    restarted = CurationService(apple_music=music, split_journal_path=split_service.split_journal_path)
    result = restarted.apply_playlist_splits(plan, confirmed=True)
    assert result["success"]
    assert len([write for write in music.writes if write[0] == "create"]) == 2
    assert sum((music.playlists[part["playlist_id"]]["tracks"] for part in result["parts"]), []) == plan["sources"][0]["track_ids"]


def test_split_restart_reports_completed_and_unresolved_parts(split_service):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    music = split_service.apple_music

    def fail_second_part():
        if any(write[0] == "create" for write in music.writes):
            music.fail_add_at = 2

    music.before_create = fail_second_part
    first = split_service.apply_playlist_splits(plan, confirmed=True)
    assert not first["success"]
    restarted = CurationService(apple_music=music, split_journal_path=split_service.split_journal_path)
    retried = restarted.apply_playlist_splits(plan, confirmed=True)
    assert [part["status"] for part in retried["parts"]] == ["complete", "unresolved"]
    assert retried["parts"][0]["confirmed_count"] == 51
    assert retried["parts"][1]["confirmed_count"] == 1
    assert retried["parts"][1]["playlist_id"] == first["parts"][1]["playlist_id"]


@pytest.mark.parametrize("change", ["rename", "reorder", "missing"])
def test_split_modified_known_output_blocks_all_further_writes(split_service, change):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    result = split_service.apply_playlist_splits(plan, confirmed=True)
    assert result["success"]
    output_id = result["parts"][0]["playlist_id"]
    if change == "rename":
        split_service.apple_music.playlists[output_id]["name"] = "User edit"
    elif change == "reorder":
        split_service.apple_music.playlists[output_id]["tracks"].reverse()
    else:
        del split_service.apple_music.playlists[output_id]
    writes = list(split_service.apple_music.writes)
    retried = split_service.apply_playlist_splits(plan, confirmed=True)
    assert not retried["success"]
    assert [part["playlist_id"] for part in retried["parts"]] == [part["playlist_id"] for part in result["parts"]]
    assert [part["confirmed_count"] for part in retried["parts"]] == [51, 50]
    assert [part["status"] for part in retried["parts"]] == ["unresolved", "complete"]
    assert split_service.apple_music.writes == writes


def test_split_generated_output_as_source_does_not_modify_journal(split_service):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    applied = split_service.apply_playlist_splits(plan, confirmed=True)
    assert applied["success"]
    journal = split_service.split_journal_path / "journal.json"
    before = journal.read_bytes()
    writes = list(split_service.apple_music.writes)
    generated_plan = split_service.preview_playlist_splits([applied["parts"][0]["playlist_id"]])
    assert generated_plan["sources"][0]["skip_reason"] == "within_limit"
    assert not split_service.apply_playlist_splits(generated_plan, confirmed=True)["success"]
    assert journal.read_bytes() == before
    assert split_service.apply_playlist_splits(plan, confirmed=True)["success"]
    assert journal.read_bytes() == before
    assert split_service.apple_music.writes == writes


def test_split_stale_source_retry_preserves_all_durable_output_progress(split_service):
    split_service.initialize_playlist_split_journal()
    plan = split_service.preview_playlist_splits([SOURCE_ID])
    applied = split_service.apply_playlist_splits(plan, confirmed=True)
    assert applied["success"]
    journal = split_service.split_journal_path / "journal.json"
    before = journal.read_bytes()
    writes = list(split_service.apple_music.writes)
    split_service.apple_music.playlists[SOURCE_ID]["name"] = "Renamed source"
    retried = split_service.apply_playlist_splits(plan, confirmed=True)
    assert not retried["success"]
    assert [part["playlist_id"] for part in retried["parts"]] == [part["playlist_id"] for part in applied["parts"]]
    assert [part["confirmed_count"] for part in retried["parts"]] == [51, 50]
    assert [part["status"] for part in retried["parts"]] == ["complete", "complete"]
    assert journal.read_bytes() == before
    assert split_service.apple_music.writes == writes


def test_split_preview_skips_small_missing_or_invalid_sources(split_service):
    music = split_service.apple_music
    music.playlists[OTHER_ID]["tracks"] = ["0000000000000020"]
    plan = split_service.preview_playlist_splits([OTHER_ID, "0000000000000099", "invalid"])
    assert all(source["skip_reason"] for source in plan["sources"])
    assert all(source["parts"] == [] for source in plan["sources"])
    assert music.writes == []


class SeedMusic(SplitMusic):
    def __init__(self):
        super().__init__()
        self.library = [
            {"persistent_id": f"{i:016X}", "title": f"Song {i}", "name": f"Song {i}",
             "artist": "Artist", "genre": "Rock" if i < 30 else "Other"}
            for i in range(10, 50)
        ]
        self.reads = []

    def get_user_playlists_with_counts_strict(self):
        self.reads.append("sources")
        return [{"persistent_id": pid, "name": item["name"], "track_count": len(item["tracks"])}
                for pid, item in self.playlists.items()]

    def get_library_tracks_strict(self):
        self.reads.append("library")
        return deepcopy(self.library)

    def get_playlist_tracks_by_id(self, playlist_id):
        self.reads.append(playlist_id)
        records = {track["persistent_id"]: track for track in self.library}
        return [deepcopy(records[pid]) for pid in self.playlists[playlist_id]["tracks"]]


@pytest.fixture
def seed_service(tmp_path):
    return CurationService(apple_music=SeedMusic(), split_journal_path=tmp_path / "shared-journal")


def seed_preview(service, limit=30):
    return service.preview_seed_playlist(SOURCE_ID, "000000000000000A", limit=limit)


def test_seed_sources_and_preview_keep_real_identity_and_write_nothing(seed_service):
    sources = seed_service.get_seed_playlist_sources()
    assert sources[0]["name"] == sources[1]["name"] == "Same"
    assert sources[0]["persistent_id"] != sources[1]["persistent_id"]
    tracks = seed_service.get_seed_playlist_source_tracks(SOURCE_ID)
    assert len(tracks) == 101 and tracks[0] == tracks[5]
    plan = seed_preview(seed_service)
    assert plan["kind"] == "seed" and plan["candidate_scope"] == "existing_library"
    assert plan["ranking_basis"] == "recorded_metadata_only"
    assert plan["source"]["source_id"] == SOURCE_ID
    assert plan["source"]["track_ids"] == seed_service.apple_music.playlists[SOURCE_ID]["tracks"]
    assert plan["seed"]["title"] == "Song 10" and plan["seed"]["artist"] == "Artist"
    assert len(plan["candidates"]) == 40 and len(plan["tracks"]) == 30
    assert plan["tracks"][0]["persistent_id"] == "000000000000000A"
    assert "seed:missing_recorded_mood" in plan["warnings"]
    assert plan["tracks"][1]["reason"] == "genre_only_fallback"
    assert seed_service.apple_music.writes == []
    assert not seed_service.split_journal_path.exists()
    seed_service.apple_music.library.reverse()
    assert seed_preview(seed_service) == plan


@pytest.mark.parametrize("source,seed,limit", [
    ("bad", "000000000000000A", 30), (SOURCE_ID, "bad", 30),
    (SOURCE_ID, "0000000000000099", 30), (OTHER_ID, "000000000000000A", 30),
    ("0000000000000099", "000000000000000A", 30),
    (SOURCE_ID, "000000000000000A", True), (SOURCE_ID, "000000000000000A", 0),
    (SOURCE_ID, "000000000000000A", 31), (SOURCE_ID, "000000000000000A", 1.0),
])
def test_seed_preview_rejects_invalid_selection(seed_service, source, seed, limit):
    with pytest.raises((ValueError, KeyError)):
        seed_service.preview_seed_playlist(source, seed, limit=limit)
    assert seed_service.apple_music.writes == []


@pytest.mark.parametrize("change", ["rename", "order", "membership", "seed_metadata", "unselected_metadata", "remove_seed"])
def test_seed_fresh_inputs_required_before_any_write(seed_service, change):
    plan = seed_preview(seed_service, limit=2)
    seed_service.initialize_playlist_split_journal()
    music = seed_service.apple_music
    if change == "rename":
        music.playlists[SOURCE_ID]["name"] = "Renamed"
    elif change == "order":
        music.playlists[SOURCE_ID]["tracks"].reverse()
    elif change == "membership":
        music.playlists[SOURCE_ID]["tracks"].append("000000000000000A")
    elif change == "remove_seed":
        music.library = music.library[1:]
    else:
        music.library[0 if change == "seed_metadata" else -1]["genre"] = "Jazz"
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert music.writes == []


@pytest.mark.parametrize("confirmation", [False, 1, "yes", None])
def test_seed_confirmation_is_literal_and_does_not_read(seed_service, confirmation):
    plan = seed_preview(seed_service)
    seed_service.apple_music.reads.clear()
    assert not seed_service.apply_seed_playlist(plan, confirmed=confirmation)["success"]
    assert seed_service.apple_music.reads == [] and seed_service.apple_music.writes == []


@pytest.mark.parametrize("field", ["output", "tracks", "seed", "source", "candidate_scope", "limit", "extra"])
def test_seed_tampering_rejected_even_with_recomputed_hash(seed_service, field):
    from src.curation_service import _split_digest
    plan = seed_preview(seed_service)
    if field == "output":
        plan[field]["name"] = "Arbitrary"
    elif field == "tracks":
        plan[field].reverse()
    elif field == "seed":
        plan[field]["title"] = "Forged"
    elif field == "source":
        plan[field]["track_ids"].reverse()
    elif field == "limit":
        plan[field] = True
    else:
        plan[field] = "untrusted"
    plan["fingerprint"] = _split_digest({key: value for key, value in plan.items() if key != "fingerprint"})
    seed_service.initialize_playlist_split_journal()
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert seed_service.apple_music.writes == []


def test_seed_apply_preserves_sources_collision_and_completed_restart(seed_service):
    music = seed_service.apple_music
    plan = seed_preview(seed_service, limit=3)
    music.playlists["0000000000000003"]["name"] = plan["output"]["name"]
    original = deepcopy(music.playlists)
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    seed_service.initialize_playlist_split_journal()
    music.reads.clear()
    applied = seed_service.apply_seed_playlist(plan, confirmed=True)
    assert applied["success"] and "library" in music.reads and SOURCE_ID in music.reads
    output = applied["parts"][0]["playlist_id"]
    assert output not in original
    assert music.playlists[output]["tracks"] == plan["output"]["track_ids"]
    assert all(music.playlists[key] == value for key, value in original.items())
    writes = list(music.writes)
    restarted = CurationService(apple_music=music, split_journal_path=seed_service.split_journal_path)
    assert restarted.apply_seed_playlist(plan, confirmed=True)["success"]
    assert music.writes == writes


@pytest.mark.parametrize("first", ["seed", "split"])
@pytest.mark.parametrize("operation", ["create", "add"])
def test_seed_split_pending_intent_blocks_both_kinds(seed_service, first, operation):
    seed_service.initialize_playlist_split_journal()
    seed = seed_preview(seed_service, limit=3)
    split = seed_service.preview_playlist_splits([SOURCE_ID])
    music = seed_service.apple_music
    music.fail_create = operation == "create"
    music.fail_add_at = 2 if operation == "add" else None
    apply = seed_service.apply_seed_playlist if first == "seed" else seed_service.apply_playlist_splits
    assert not apply(seed if first == "seed" else split, confirmed=True)["success"]
    writes = list(music.writes)
    restarted = CurationService(apple_music=music, split_journal_path=seed_service.split_journal_path)
    for apply, plan in [(restarted.apply_seed_playlist, seed), (restarted.apply_playlist_splits, split)]:
        result = apply(plan, confirmed=True)
        assert not result["success"] and result["unresolved"]
    assert music.writes == writes


@pytest.mark.parametrize("first", ["seed", "split"])
def test_seed_split_recorded_outputs_cannot_be_sources(seed_service, first):
    seed_service.initialize_playlist_split_journal()
    apply = seed_service.apply_seed_playlist if first == "seed" else seed_service.apply_playlist_splits
    plan = seed_preview(seed_service, limit=3) if first == "seed" else seed_service.preview_playlist_splits([SOURCE_ID])
    output_id = apply(plan, confirmed=True)["parts"][0]["playlist_id"]
    journal = seed_service.split_journal_path / "journal.json"
    before, writes = journal.read_bytes(), list(seed_service.apple_music.writes)
    other_plan = (seed_service.preview_playlist_splits([output_id]) if first == "seed"
                  else seed_service.preview_seed_playlist(output_id, "000000000000000A", limit=3))
    other_apply = seed_service.apply_playlist_splits if first == "seed" else seed_service.apply_seed_playlist
    assert not other_apply(other_plan, confirmed=True)["success"]
    assert journal.read_bytes() == before and seed_service.apple_music.writes == writes


@pytest.mark.parametrize("damage", ["missing", "corrupt", "lock_missing"])
def test_seed_shared_journal_damage_fails_closed(seed_service, damage):
    plan = seed_preview(seed_service)
    seed_service.initialize_playlist_split_journal()
    target = seed_service.split_journal_path / ("lock" if damage == "lock_missing" else "journal.json")
    target.write_text("{") if damage == "corrupt" else target.unlink()
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert seed_service.apple_music.writes == []


@pytest.mark.parametrize("stage", ["before", "create", "add"])
def test_seed_failed_journal_save_stops_both_kinds(seed_service, stage):
    import os
    seed_service.initialize_playlist_split_journal()
    plan = seed_preview(seed_service, limit=3)
    replace = os.replace
    def fail_save(*args):
        writes = seed_service.apple_music.writes
        if stage == "before" or (writes and (stage == "create" or writes[-1][0] == "add")):
            raise OSError("disk full")
        return replace(*args)
    with patch("src.curation_service.os.replace", side_effect=fail_save):
        assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    writes = list(seed_service.apple_music.writes)
    if stage == "before":
        assert writes == []
    else:
        restarted = CurationService(apple_music=seed_service.apple_music, split_journal_path=seed_service.split_journal_path)
        assert not restarted.apply_seed_playlist(plan, confirmed=True)["success"]
        assert not restarted.apply_playlist_splits(restarted.preview_playlist_splits([SOURCE_ID]), confirmed=True)["success"]
        assert seed_service.apple_music.writes == writes


def test_seed_cross_kind_concurrency_uses_same_permanent_lock(seed_service):
    plan = seed_preview(seed_service, limit=3)
    seed_service.initialize_playlist_split_journal()
    other = CurationService(apple_music=seed_service.apple_music, split_journal_path=seed_service.split_journal_path)
    split = other.preview_playlist_splits([SOURCE_ID])
    nested = []
    seed_service.apple_music.before_create = lambda: nested.append(other.apply_playlist_splits(split, confirmed=True))
    assert seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert nested and all(not result["success"] for result in nested)


def test_seed_known_progress_resumes_after_restart_without_duplicate_append(seed_service):
    seed_service.initialize_playlist_split_journal()
    plan = seed_preview(seed_service, limit=4)
    music = seed_service.apple_music
    reader = music.get_playlist_tracks_by_id
    checks = []
    def transient_read(playlist_id):
        tracks = reader(playlist_id)
        if playlist_id not in (SOURCE_ID, OTHER_ID) and len(tracks) == 2:
            checks.append(playlist_id)
            if len(checks) == 2:
                raise RuntimeError("read failed before next intent")
        return tracks
    music.get_playlist_tracks_by_id = transient_read
    partial = seed_service.apply_seed_playlist(plan, confirmed=True)
    assert not partial["success"] and partial["parts"][0]["confirmed_count"] == 2
    music.get_playlist_tracks_by_id = reader
    restarted = CurationService(apple_music=music, split_journal_path=seed_service.split_journal_path)
    result = restarted.apply_seed_playlist(plan, confirmed=True)
    assert result["success"]
    assert [write[0] for write in music.writes].count("create") == 1
    assert music.playlists[result["parts"][0]["playlist_id"]]["tracks"] == plan["output"]["track_ids"]


def test_seed_and_legacy_split_records_coexist_without_migration(seed_service):
    seed_service.initialize_playlist_split_journal()
    split = seed_service.preview_playlist_splits([SOURCE_ID])
    assert seed_service.apply_playlist_splits(split, confirmed=True)["success"]
    journal = seed_service.split_journal_path / "journal.json"
    original = json.loads(journal.read_text())["payload"]
    assert "kind" not in original["plans"][split["fingerprint"]]["plan"]
    seed = seed_preview(seed_service, limit=2)
    assert seed_service.apply_seed_playlist(seed, confirmed=True)["success"]
    updated = json.loads(journal.read_text())["payload"]
    assert updated["version"] == original["version"] == 1
    assert updated["plans"][split["fingerprint"]] == original["plans"][split["fingerprint"]]
    writes, before = list(seed_service.apple_music.writes), journal.read_bytes()
    assert seed_service.apply_playlist_splits(split, confirmed=True)["success"]
    assert seed_service.apply_seed_playlist(seed, confirmed=True)["success"]
    assert seed_service.apple_music.writes == writes and journal.read_bytes() == before


@pytest.mark.parametrize("change", ["rename", "order", "extra_occurrence", "missing"])
def test_seed_modified_known_output_blocks_restart(seed_service, change):
    seed_service.initialize_playlist_split_journal()
    plan = seed_preview(seed_service, limit=3)
    applied = seed_service.apply_seed_playlist(plan, confirmed=True)
    output_id = applied["parts"][0]["playlist_id"]
    music = seed_service.apple_music
    if change == "rename":
        music.playlists[output_id]["name"] = "Edited"
    elif change == "order":
        music.playlists[output_id]["tracks"].reverse()
    elif change == "extra_occurrence":
        music.playlists[output_id]["tracks"].append(plan["output"]["track_ids"][0])
    else:
        del music.playlists[output_id]
    writes = list(music.writes)
    result = seed_service.apply_seed_playlist(plan, confirmed=True)
    assert not result["success"] and result["parts"][0]["playlist_id"] == output_id
    assert result["parts"][0]["status"] == "unresolved" and music.writes == writes


@pytest.mark.parametrize("returned_id", [SOURCE_ID, "0000000000000002", "invalid"])
def test_seed_create_identity_never_adopts_a_source_or_invalid_id(seed_service, returned_id):
    seed_service.initialize_playlist_split_journal()
    plan = seed_preview(seed_service, limit=2)
    # Record a second source across the common journal before creation.
    small = deepcopy(seed_service.apple_music.playlists[OTHER_ID])
    seed_service.apple_music.playlists[OTHER_ID]["tracks"] = []
    assert seed_service.apply_playlist_splits(seed_service.preview_playlist_splits([OTHER_ID]), confirmed=True)["success"]
    seed_service.apple_music.playlists[OTHER_ID] = small
    seed_service.apple_music.create_playlist = lambda name: returned_id
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert not seed_service.apply_playlist_splits(seed_service.preview_playlist_splits([SOURCE_ID]), confirmed=True)["success"]
    assert seed_service.apple_music.writes == []


@pytest.mark.parametrize("damage", ["seed_metadata", "count", "target_alias", "kind"])
def test_seed_invalid_checksummed_journal_blocks_both_kinds(seed_service, damage):
    from src.curation_service import _split_digest
    seed_service.initialize_playlist_split_journal()
    plan = seed_preview(seed_service, limit=2)
    assert seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    journal = seed_service.split_journal_path / "journal.json"
    envelope = json.loads(journal.read_text())
    entry = envelope["payload"]["plans"][plan["fingerprint"]]
    if damage == "seed_metadata":
        entry["plan"]["seed"]["title"] = "Forged"
    elif damage == "count":
        entry["parts"][0]["confirmed_count"] = True
    elif damage == "target_alias":
        entry["parts"][0]["playlist_id"] = SOURCE_ID
    else:
        entry["plan"]["kind"] = "unknown"
    envelope["checksum"] = _split_digest(envelope["payload"])
    journal.write_text(json.dumps(envelope))
    writes = list(seed_service.apple_music.writes)
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert not seed_service.apply_playlist_splits(seed_service.preview_playlist_splits([SOURCE_ID]), confirmed=True)["success"]
    assert seed_service.apple_music.writes == writes


def test_seed_create_cannot_reuse_a_recorded_output(seed_service):
    seed_service.initialize_playlist_split_journal()
    first = seed_preview(seed_service, limit=2)
    output_id = seed_service.apply_seed_playlist(first, confirmed=True)["parts"][0]["playlist_id"]
    second = seed_preview(seed_service, limit=3)
    writes = list(seed_service.apple_music.writes)
    seed_service.apple_music.create_playlist = lambda name: output_id
    assert not seed_service.apply_seed_playlist(second, confirmed=True)["success"]
    assert not seed_service.apply_seed_playlist(first, confirmed=True)["success"]
    assert seed_service.apple_music.writes == writes


@pytest.mark.parametrize("boundary", ["source_id", "library_duplicate", "native_metadata", "source_metadata"])
def test_seed_strict_boundaries_and_nonseed_source_metadata(seed_service, boundary):
    music = seed_service.apple_music
    plan = seed_preview(seed_service, limit=2)
    seed_service.initialize_playlist_split_journal()
    if boundary == "source_id":
        music.get_playlist_info_by_id = lambda pid: {"persistent_id": OTHER_ID, "name": "Same"}
    elif boundary == "library_duplicate":
        music.library.append(deepcopy(music.library[0]))
    elif boundary == "native_metadata":
        music.library[-1]["extra"] = (1, 2)
    else:
        reader = music.get_playlist_tracks_by_id
        def changed_metadata(pid):
            tracks = reader(pid)
            if pid == SOURCE_ID:
                tracks[1]["artist"] = "Changed source metadata"
            return tracks
        music.get_playlist_tracks_by_id = changed_metadata
    assert not seed_service.apply_seed_playlist(plan, confirmed=True)["success"]
    assert music.writes == []


class FakeAppleMusic:
    def get_favourite_tracks(self):
        return [
            {
                "persistent_id": "track-1",
                "name": "Track A",
                "artist": "Artist A",
                "genre": "Hip-Hop",
            },
            {
                "persistent_id": "track-2",
                "name": "Track B",
                "artist": "Artist B",
                "genre": "Electronic",
            },
        ]


class FakeTemperClassifier:
    def __init__(self):
        self.calls = []

    def classify_track(self, track):
        self.calls.append(track)
        return None


class StaticTemperClassifier:
    def classify_track(self, track):
        return None


class FakeApplier:
    def __init__(self):
        self.calls = []
        self.bulk_calls = []

    def apply_changes(self, changes, confirmed):
        changes = list(changes)
        self.calls.append((changes, confirmed))
        return {
            "success": False,
            "applied": 0,
            "failed": 0,
            "confirmed": confirmed,
        }

    def apply_fav_tracks_bulk(self, assignments, confirmed):
        assignments = list(assignments)
        self.bulk_calls.append((assignments, confirmed))
        return {
            "success": True,
            "applied": len(assignments),
            "failed": 0,
            "stdout": "SUCCESS copied=1 skipped=0 missing=0",
        }


class SuccessfulFakeApplier(FakeApplier):
    def apply_changes(self, changes, confirmed):
        result = super().apply_changes(changes, confirmed)
        result["success"] = True
        result["applied"] = len(result.get("preview", []) or list(changes))
        return result


class MiniTestAppleMusic:
    def get_favourite_tracks(self):
        return [
            {
                "persistent_id": "track-1",
                "name": "Track A",
                "artist": "Artist A",
                "genre": "Hip-Hop",
            }
        ]


class MiniTestApplier:
    def __init__(self):
        self.calls = []

    def run_smoke_test(self, track_id):
        self.calls.append(track_id)
        return {
            "success": True,
            "track_id": track_id,
            "copied": 1,
            "duplicate_skipped": True,
            "leftovers": {"root": 0, "genre": 0, "playlist": 0},
        }


class TracksWithoutStableId:
    def get_favourite_tracks(self):
        return [
            {
                "name": "Track Without ID",
                "artist": "Artist B",
                "genre": "Electronic",
            }
        ]


class AppleMusicWithGeneratedFavTracks(FakeAppleMusic):
    def get_generated_fav_song_tracks(self):
        return [
            {
                "persistent_id": "track-1",
                "name": "Track A",
                "artist": "Artist A",
                "target_playlist": "♥ Hip Hop & RnB",
            },
            {
                "persistent_id": "stale-track",
                "name": "Old Track",
                "artist": "Artist Old",
                "target_playlist": "♥ Hip Hop & RnB",
            },
        ]


class AppleMusicLikeTracks:
    def get_favourite_tracks(self):
        return [
            {
                "persistent_id": "apple-track-1",
                "title": "Apple Title",
                "artist": "Apple Artist",
                "genre": "Alt-Rock",
            }
        ]


class TracksWithMissingId:
    def get_favourite_tracks(self):
        return [
            {
                "persistent_id": "track-1",
                "title": "Track With ID",
                "artist": "Artist A",
                "genre": "Hip-Hop",
            },
            {
                "title": "Track Without ID",
                "artist": "Artist B",
                "genre": "Electronic",
            },
        ]


class RequestedMainGenreTracks:
    def get_favourite_tracks(self):
        genres = [
            "Rock",
            "Indie Rock",
            "House",
            "Techno",
            "Breakbeat",
            "IDM/Experimental",
            "Disco",
            "Funk",
            "Soul",
            "Jazz",
            "Blues",
            "Pop",
            "Lounge",
        ]
        return [
            {
                "persistent_id": f"track-{index}",
                "name": f"Track {index}",
                "artist": "Artist",
                "genre": genre,
            }
            for index, genre in enumerate(genres, start=1)
        ]


class FakeAppleMusicInterface(AppleMusicInterface):
    def __init__(self):
        self.requested_favourite_tracks = 0

    def get_favourite_tracks(self):
        self.requested_favourite_tracks += 1
        return [{"title": "Track A", "persistent_id": "track-a"}]

    def get_generated_fav_song_tracks(self):
        return []


class SelectedPlaylistTracks:
    def get_playlist_tracks(self, playlist_name):
        assert playlist_name in {"Morning", "Night"}
        return {
            "Morning": [
                {
                    "persistent_id": "track-1",
                    "name": "Happy House",
                    "artist": "DJ A",
                    "genre": "House",
                },
                {
                    "persistent_id": "morning-2",
                    "name": "Blue Jazz",
                    "artist": "Artist B",
                    "genre": "Jazz",
                },
            ],
            "Night": [
                {
                    "persistent_id": "night-1",
                    "name": "Dark Techno",
                    "artist": "Artist C",
                    "genre": "Techno",
                }
            ],
        }[playlist_name]


def test_fav_preview_builds_assignments_and_changes():
    classifier = FakeTemperClassifier()
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=classifier,
    )

    preview = service.preview_fav_songs()

    targets = [a["target_path"] for a in preview["assignments"]]
    assert ["Fav Songs", "♥ Hip Hop & RnB"] in targets
    assert ["Fav Songs", "♥ Electronic"] in targets
    assert preview["grouped"]["Hip Hop & RnB"][0]["item_id"] == "track-1"
    assert preview["grouped"]["Electronic"][0]["item_id"] == "track-2"
    assert "temperament" not in preview["assignments"][0]
    assert classifier.calls == []
    assert preview["changes"][0]["action"] == "ensure_folder"


@pytest.mark.skip(reason="playlist-temper curation was removed")
def test_selected_playlist_temper_preview_splits_tracks_by_genre_and_temper():
    service = CurationService(
        apple_music=SelectedPlaylistTracks(),
        temper_classifier=FakeTemperClassifier(),
    )

    preview = service.preview_playlist_tempers(["Morning", "Night"])

    targets = [assignment["target_path"] for assignment in preview["assignments"]]
    assert ["4 Tempers", "House Frolic"] in targets
    assert ["4 Tempers", "Jazz Dread"] in targets
    assert ["4 Tempers", "Techno Dread"] in targets
    assert preview["source_playlists"] == ["Morning", "Night"]
    assert preview["total_assignments"] == 3


@pytest.mark.skip(reason="playlist-temper curation was removed")
def test_playlist_temper_preview_reads_configured_sources(tmp_path):
    config_path = tmp_path / "curation_sources.json"
    config_path.write_text('{"temper_playlists": ["Morning"]}', encoding="utf-8")
    service = CurationService(
        apple_music=SelectedPlaylistTracks(),
        temper_classifier=FakeTemperClassifier(),
        sources_config_path=config_path,
    )

    preview = service.preview_playlist_tempers()

    assert preview["source_playlists"] == ["Morning"]
    assert preview["total_assignments"] == 2


@pytest.mark.skip(reason="playlist-temper curation was removed")
def test_playlist_temper_preview_uses_parallel_executor_for_multiple_playlists():
    service = CurationService(
        apple_music=SelectedPlaylistTracks(),
        temper_classifier=FakeTemperClassifier(),
    )

    called_with = []

    import src.worker_pool as wp
    original = wp.map_parallel

    def tracking_map(fn, items, workers=None, label="items"):
        called_with.append(list(items))
        return original(fn, items, workers=workers, label=label)

    with patch("src.curation_service.map_parallel", tracking_map):
        preview = service.preview_playlist_tempers(["Morning", "Night"])

    assert called_with == [["Morning", "Night"]]
    assert preview["source_playlists"] == ["Morning", "Night"]
    assert preview["total_assignments"] == 3


def test_fav_preview_uses_title_for_apple_music_track_names():
    service = CurationService(
        apple_music=AppleMusicLikeTracks(),
        temper_classifier=StaticTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    assert preview["assignments"][0]["item_name"] == "Apple Title"
    assert preview["assignments"][0]["target_path"] == [
        "Fav Songs",
        "♥ Alternative & Indie",
    ]


def test_fav_preview_groups_requested_main_genres_once():
    service = CurationService(
        apple_music=RequestedMainGenreTracks(),
        temper_classifier=StaticTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    assert set(preview["grouped"]) == {
        "Alternative & Indie",
        "Blues",
        "Breakbeat/Jungle",
        "Disco",
        "Funk",
        "House",
        "IDM",
        "Jazz",
        "Lounge",
        "Pop",
        "Rock",
        "Soul",
        "Techno",
    }
    targets = [assignment["target_path"] for assignment in preview["assignments"]]
    assert ["Fav Songs", "♥ Rock"] in targets
    assert ["Fav Songs", "♥ Alternative & Indie"] in targets
    assert ["Fav Songs", "♥ House"] in targets
    assert ["Fav Songs", "♥ Techno"] in targets
    assert ["Fav Songs", "♥ Breakbeat/Jungle"] in targets
    assert ["Fav Songs", "♥ IDM"] in targets
    assert ["Fav Songs", "♥ Disco"] in targets
    assert ["Fav Songs", "♥ Funk"] in targets
    assert ["Fav Songs", "♥ Soul"] in targets
    assert ["Fav Songs", "♥ Jazz"] in targets
    assert ["Fav Songs", "♥ Blues"] in targets
    assert ["Fav Songs", "♥ Pop"] in targets
    assert ["Fav Songs", "♥ Lounge"] in targets


def test_fav_preview_plans_stale_generated_track_removals():
    service = CurationService(
        apple_music=AppleMusicWithGeneratedFavTracks(),
        temper_classifier=FakeTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    remove_changes = [
        change for change in preview["changes"] if change["action"] == "remove_track"
    ]
    assert remove_changes == [
        {
            "action": "remove_track",
            "path": ["stale-track", "Fav Songs", "♥ Hip Hop & RnB"],
            "description": "Remove stale Old Track from ♥ Hip Hop & RnB",
        }
    ]


def test_fav_preview_skips_tracks_without_stable_id_and_reports_them():
    service = CurationService(
        apple_music=TracksWithMissingId(),
        temper_classifier=StaticTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    assert preview["total_assignments"] == 1
    assert preview["total_skipped"] == 1
    assert preview["skipped_tracks"] == [
        {
            "name": "Track Without ID",
            "artist": "Artist B",
            "genre": "Electronic",
            "reason": "missing_stable_id",
        }
    ]
    assert all(
        change["path"][0] != ""
        for change in preview["changes"]
        if change["action"] == "copy_track"
    )


def test_fav_preview_uses_favourite_tracks_interface():
    apple_music = FakeAppleMusicInterface()
    service = CurationService(
        apple_music=apple_music,
        temper_classifier=StaticTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    assert apple_music.requested_favourite_tracks == 1
    assert preview["assignments"][0]["item_name"] == "Track A"


def test_apply_fav_songs_delegates_to_applier_and_attaches_preview():
    applier = FakeApplier()
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_fav_songs(confirmed=False)

    assert applier.calls
    changes, confirmed = applier.calls[0]
    assert confirmed is False
    assert changes[0].action == "ensure_folder"
    assert result["preview"]["total_assignments"] == 2
    assert result["preview"]["total_changes"] == len(changes)


def test_apply_fav_songs_can_limit_tracks_for_small_apply():
    applier = FakeApplier()
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_fav_songs(confirmed=True, max_tracks=1)

    changes, confirmed = applier.calls[0]
    copy_changes = [change for change in changes if change.action == "copy_track"]
    assert confirmed is True
    assert result["preview"]["total_assignments"] == 1
    assert result["preview"]["assignments"][0]["item_id"] == "track-1"
    assert len(copy_changes) == 1
    assert copy_changes[0].path[0] == "track-1"


def test_apply_fav_songs_can_offset_limited_batches():
    applier = FakeApplier()
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_fav_songs(confirmed=True, max_tracks=1, offset=1)

    changes, confirmed = applier.calls[0]
    copy_changes = [change for change in changes if change.action == "copy_track"]
    assert confirmed is True
    assert result["preview"]["offset"] == 1
    assert result["preview"]["max_tracks"] == 1
    assert result["preview"]["assignments"][0]["item_id"] == "track-2"
    assert len(copy_changes) == 1
    assert copy_changes[0].path[0] == "track-2"


def test_apply_fav_songs_bulk_delegates_assignments_to_bulk_applier():
    applier = FakeApplier()
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_fav_songs_bulk(confirmed=True, max_tracks=1, offset=1)

    assignments, confirmed = applier.bulk_calls[0]
    assert confirmed is True
    assert result["success"] is True
    assert result["applied"] == 1
    assert assignments[0].item_id == "track-2"


def test_apply_fav_songs_bulk_full_run_removes_stale_tracks():
    applier = SuccessfulFakeApplier()
    service = CurationService(
        apple_music=AppleMusicWithGeneratedFavTracks(),
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_fav_songs_bulk(confirmed=True)

    remove_changes = [change for change in applier.calls[0][0] if change.action == "remove_track"]
    assert result["success"] is True
    assert result["stale_removal"]["success"] is True
    assert [change.path for change in remove_changes] == [
        ("stale-track", "Fav Songs", "♥ Hip Hop & RnB")
    ]


def test_apply_fav_songs_batched_reuses_one_preview_for_multiple_batches():
    applier = SuccessfulFakeApplier()
    apple_music = FakeAppleMusic()
    service = CurationService(
        apple_music=apple_music,
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_fav_songs_batched(confirmed=True, batch_size=1)

    assert result["success"] is True
    assert result["processed_tracks"] == 2
    assert [batch["offset"] for batch in result["batches"]] == [0, 1]
    assert len(applier.calls) == 2
    first_changes = [change for change in applier.calls[0][0] if change.action == "copy_track"]
    second_changes = [change for change in applier.calls[1][0] if change.action == "copy_track"]
    assert first_changes[0].path[0] == "track-1"
    assert second_changes[0].path[0] == "track-2"


@pytest.mark.skip(reason="playlist-temper curation was removed")
def test_apply_playlist_tempers_delegates_to_applier():
    applier = FakeApplier()
    service = CurationService(
        apple_music=SelectedPlaylistTracks(),
        temper_classifier=FakeTemperClassifier(),
        applier=applier,
    )

    result = service.apply_playlist_tempers(["Morning"], confirmed=True)

    changes, confirmed = applier.calls[0]
    assert confirmed is True
    assert result["preview"]["source_playlists"] == ["Morning"]
    assert any(change.action == "copy_track" for change in changes)


def test_mini_test_uses_first_favourite_track_and_reports_cleanup():
    applier = MiniTestApplier()
    service = CurationService(
        apple_music=MiniTestAppleMusic(),
        temper_classifier=StaticTemperClassifier(),
        applier=applier,
    )

    result = service.run_fav_songs_smoke_test()

    assert result["success"] is True
    assert result["duplicate_skipped"] is True
    assert result["leftovers"] == {"root": 0, "genre": 0, "playlist": 0}
    assert result["source_track"]["persistent_id"] == "track-1"
    assert result["source_track"]["name"] == "Track A"
    assert result["source_track"]["artist"] == "Artist A"
    assert applier.calls == ["track-1"]


def test_mini_test_reports_no_stable_id_without_calling_applier():
    applier = MiniTestApplier()
    service = CurationService(
        apple_music=TracksWithoutStableId(),
        temper_classifier=StaticTemperClassifier(),
        applier=applier,
    )

    result = service.run_fav_songs_smoke_test()

    assert result == {
        "success": False,
        "error": "No Favourite Songs track with a stable persistent ID was found",
        "copied": 0,
        "duplicate_skipped": False,
        "leftovers": {},
    }
    assert applier.calls == []


def test_fav_preview_applies_store_overrides_over_auto_assignments(tmp_path):
    store = CurationStore(tmp_path / "assignments.json")
    store.save_override(
        CurationAssignment(
            item_type=AssignmentType.FAV_TRACK,
            item_id="track-1",
            item_name="Track A",
            genre="ambient",
            source=AssignmentSource.MANUAL,
            confidence=1.0,
            manual_override=True,
        )
    )
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
        store=store,
    )

    preview = service.preview_fav_songs()

    overridden = next(a for a in preview["assignments"] if a["item_id"] == "track-1")
    assert overridden["target_path"] == ["Fav Songs", "♥ Ambient"]
    assert overridden["source"] == "manual"
    assert overridden["manual_override"] is True
