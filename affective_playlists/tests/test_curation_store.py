from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
    TemperBucket,
)
from src.curation_store import CurationStore


class CountingCurationStore(CurationStore):
    def __init__(self, path):
        super().__init__(path)
        self.load_count = 0

    def _load(self):
        self.load_count += 1
        return super()._load()


def test_store_round_trips_manual_override(tmp_path):
    store = CurationStore(tmp_path / "assignments.json")
    assignment = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.MANUAL,
        confidence=1.0,
        manual_override=True,
    )

    store.save_override(assignment)
    loaded = store.get_override(AssignmentType.FAV_TRACK, "track-1")

    assert loaded == assignment


def test_store_merges_overrides_over_auto_assignments(tmp_path):
    store = CurationStore(tmp_path / "assignments.json")
    auto = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="electronic",
        temperament=TemperBucket.FROLIC,
        source=AssignmentSource.AUTO,
        confidence=0.7,
    )
    manual = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.MANUAL,
        confidence=1.0,
        manual_override=True,
    )

    store.save_override(manual)

    assert store.apply_overrides([auto]) == [manual]


def test_store_apply_overrides_loads_existing_data_once(tmp_path):
    store = CountingCurationStore(tmp_path / "assignments.json")
    manual = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.MANUAL,
        confidence=1.0,
        manual_override=True,
    )
    auto_override = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="electronic",
        temperament=TemperBucket.FROLIC,
        source=AssignmentSource.AUTO,
        confidence=0.7,
    )
    auto_unchanged = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-2",
        item_name="Track B",
        genre="electronic",
        temperament=TemperBucket.DREAD,
        source=AssignmentSource.AUTO,
        confidence=0.7,
    )

    store.save_override(manual)
    store.load_count = 0

    assert store.apply_overrides([auto_override, auto_unchanged]) == [
        manual,
        auto_unchanged,
    ]
    assert store.load_count == 1
