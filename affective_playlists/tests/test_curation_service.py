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
                "target_playlist": "Hip Hop & RnB",
            },
            {
                "persistent_id": "stale-track",
                "name": "Old Track",
                "artist": "Artist Old",
                "target_playlist": "Hip Hop & RnB",
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
    service = CurationService(
        apple_music=FakeAppleMusic(),
        temper_classifier=FakeTemperClassifier(),
    )

    preview = service.preview_fav_songs()

    targets = [a["target_path"] for a in preview["assignments"]]
    assert ["Fav Songs", "Hip Hop & RnB"] in targets
    assert ["Fav Songs", "Electronic"] in targets
    assert set(preview["grouped"]["Hip Hop & RnB"]) == {
        "Woe",
        "Frolic",
        "Dread",
        "Malice",
    }
    assert preview["grouped"]["Hip Hop & RnB"]["Frolic"][0]["item_id"] == "track-1"
    assert preview["grouped"]["Electronic"]["Dread"][0]["item_id"] == "track-2"
    assert preview["changes"][0]["action"] == "ensure_folder"


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
    assert ["Fav Songs", "Rock"] in targets
    assert ["Fav Songs", "Alternative & Indie"] in targets
    assert ["Fav Songs", "House"] in targets
    assert ["Fav Songs", "Techno"] in targets
    assert ["Fav Songs", "Breakbeat/Jungle"] in targets
    assert ["Fav Songs", "IDM"] in targets
    assert ["Fav Songs", "Disco"] in targets
    assert ["Fav Songs", "Funk"] in targets
    assert ["Fav Songs", "Soul"] in targets
    assert ["Fav Songs", "Jazz"] in targets
    assert ["Fav Songs", "Blues"] in targets
    assert ["Fav Songs", "Pop"] in targets
    assert ["Fav Songs", "Lounge"] in targets


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
            "path": ["stale-track", "Fav Songs", "Hip Hop & RnB"],
            "description": "Remove stale Old Track from Hip Hop & RnB",
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
    assert overridden["target_path"] == ["Fav Songs", "Ambient"]
    assert overridden["source"] == "manual"
    assert overridden["manual_override"] is True
