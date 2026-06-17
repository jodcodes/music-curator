from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
    TemperBucket,
)
from src.apple_music import AppleMusicInterface
from src.curation_service import CurationService
from src.curation_store import CurationStore


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
    def classify_track(self, track):
        return (
            TemperBucket.FROLIC
            if track["persistent_id"] == "track-1"
            else TemperBucket.DREAD
        )


class StaticTemperClassifier:
    def classify_track(self, track):
        return TemperBucket.FROLIC


class FakeApplier:
    def __init__(self):
        self.calls = []

    def apply_changes(self, changes, confirmed):
        changes = list(changes)
        self.calls.append((changes, confirmed))
        return {
            "success": False,
            "applied": 0,
            "failed": 0,
            "confirmed": confirmed,
        }


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


def test_fav_preview_builds_assignments_and_changes():
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    targets = [a["target_path"] for a in preview["assignments"]]
    assert ["Fav Songs", "Hip Hop & RnB", "Fav Hip Hop & RnB Frolic"] in targets
    assert ["Fav Songs", "Electronic", "Fav Electronic Dread"] in targets
    assert set(preview["grouped"]["Hip Hop & RnB"]) == {
        "Woe",
        "Frolic",
        "Dread",
        "Malice",
    }
    assert preview["grouped"]["Hip Hop & RnB"]["Frolic"][0]["item_id"] == "track-1"
    assert preview["grouped"]["Electronic"]["Dread"][0]["item_id"] == "track-2"
    assert preview["changes"][0]["action"] == "ensure_folder"


def test_fav_preview_uses_title_for_apple_music_track_names():
    service = CurationService(
        apple_music=AppleMusicLikeTracks(),
        temper_classifier=StaticTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    assert preview["assignments"][0]["item_name"] == "Apple Title"
    assert preview["assignments"][0]["target_path"] == [
        "Fav Songs",
        "Alternative & Indie",
        "Fav Alternative & Indie Frolic",
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
    assert ["Fav Songs", "Rock", "Fav Rock Frolic"] in targets
    assert [
        "Fav Songs",
        "Alternative & Indie",
        "Fav Alternative & Indie Frolic",
    ] in targets
    assert ["Fav Songs", "House", "Fav House Frolic"] in targets
    assert ["Fav Songs", "Techno", "Fav Techno Frolic"] in targets
    assert ["Fav Songs", "Breakbeat/Jungle", "Fav Breakbeat/Jungle Frolic"] in targets
    assert ["Fav Songs", "IDM", "Fav IDM Frolic"] in targets
    assert ["Fav Songs", "Disco", "Fav Disco Frolic"] in targets
    assert ["Fav Songs", "Funk", "Fav Funk Frolic"] in targets
    assert ["Fav Songs", "Soul", "Fav Soul Frolic"] in targets
    assert ["Fav Songs", "Jazz", "Fav Jazz Frolic"] in targets
    assert ["Fav Songs", "Blues", "Fav Blues Frolic"] in targets
    assert ["Fav Songs", "Pop", "Fav Pop Frolic"] in targets
    assert ["Fav Songs", "Lounge", "Fav Lounge Frolic"] in targets


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
            temperament=TemperBucket.WOE,
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
    assert overridden["target_path"] == ["Fav Songs", "Ambient", "Fav Ambient Woe"]
    assert overridden["source"] == "manual"
    assert overridden["manual_override"] is True
