from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
    TemperBucket,
    fav_playlist_name,
    normalize_fav_genre_label,
    normalize_genre_label,
)


def test_normalize_genre_label_keeps_short_names_readable():
    assert normalize_genre_label("hiphop") == "Hiphop"
    assert normalize_genre_label("disco_funk_soul") == "Disco Funk Soul"
    assert normalize_genre_label("Electronic") == "Electronic"


def test_normalize_genre_label_handles_empty_and_hyphenated_values():
    assert normalize_genre_label("") == "Other"
    assert normalize_genre_label("alt-rock") == "Alt Rock"


def test_normalize_fav_genre_label_collapses_requested_main_genres():
    assert normalize_fav_genre_label("alt-rock") == "Alternative & Indie"
    assert normalize_fav_genre_label("indie_rock") == "Alternative & Indie"
    assert normalize_fav_genre_label("rock_y_alternativo") == "Rock"
    assert normalize_fav_genre_label("house") == "House"
    assert normalize_fav_genre_label("techno") == "Techno"
    assert normalize_fav_genre_label("breakbeat") == "Breakbeat/Jungle"
    assert normalize_fav_genre_label("jungle") == "Breakbeat/Jungle"
    assert normalize_fav_genre_label("idm/experimental") == "IDM"
    assert normalize_fav_genre_label("trip-hop") == "Trip-Hop"
    assert normalize_fav_genre_label("trip hop") == "Trip-Hop"
    assert normalize_fav_genre_label("ambient") == "Ambient"
    assert normalize_fav_genre_label("disco") == "Disco"
    assert normalize_fav_genre_label("funk") == "Funk"
    assert normalize_fav_genre_label("soul") == "Soul"
    assert normalize_fav_genre_label("jazz") == "Jazz"
    assert normalize_fav_genre_label("fusion") == "Jazz"
    assert normalize_fav_genre_label("blues") == "Blues"
    assert normalize_fav_genre_label("pop") == "Pop"
    assert normalize_fav_genre_label("lounge") == "Lounge"
    assert normalize_fav_genre_label("classical") == "Classical"
    assert normalize_fav_genre_label("klassik") == "Classical"
    assert normalize_fav_genre_label("klassische musik") == "Classical"
    assert normalize_fav_genre_label("barock") == "Classical"
    assert normalize_fav_genre_label("karaoke") == "Sonstige"


def test_fav_playlist_name_uses_requested_format():
    assert fav_playlist_name("hiphop", TemperBucket.FROLIC) == "Fav Hip Hop & RnB Frolic"
    assert fav_playlist_name("electronic", TemperBucket.DREAD) == "Fav Electronic Dread"
    assert fav_playlist_name("house", TemperBucket.DREAD) == "Fav House Dread"


def test_assignment_serializes_for_api():
    assignment = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-1",
        item_name="Track A",
        genre="hiphop",
        temperament=TemperBucket.FROLIC,
        source=AssignmentSource.AUTO,
        confidence=0.91,
    )

    assert assignment.to_dict() == {
        "item_type": "fav_track",
        "item_id": "track-1",
        "item_name": "Track A",
        "genre": "hiphop",
        "genre_label": "Hip Hop & RnB",
        "temperament": "Frolic",
        "source": "auto",
        "confidence": 0.91,
        "manual_override": False,
        "target_path": [
            "Fav Songs",
            "Hip Hop & RnB",
            "Fav Hip Hop & RnB Frolic",
        ],
    }


def test_playlist_assignment_target_path_uses_canonical_genre_and_temperament():
    assignment = CurationAssignment(
        item_type=AssignmentType.PLAYLIST,
        item_id="playlist-1",
        item_name="Playlist A",
        genre="disco-funk-soul",
        temperament=TemperBucket.MALICE,
        source=AssignmentSource.AUTO,
        confidence=0.8,
    )

    assert assignment.target_path() == ["Disco", "Malice"]


def test_playlist_assignment_uses_shared_canonical_genres_for_tempers():
    assignment = CurationAssignment(
        item_type=AssignmentType.PLAYLIST,
        item_id="playlist-2",
        item_name="Playlist B",
        genre="indie-rock",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.AUTO,
        confidence=0.8,
    )

    assert assignment.to_dict()["genre_label"] == "Alternative & Indie"
    assert assignment.target_path() == ["Alternative & Indie", "Woe"]


def test_assignment_serialization_rounds_confidence():
    assignment = CurationAssignment(
        item_type=AssignmentType.FAV_TRACK,
        item_id="track-2",
        item_name="Track B",
        genre="electronic",
        temperament=TemperBucket.DREAD,
        source=AssignmentSource.AUTO,
        confidence=0.912345,
    )

    assert assignment.to_dict()["confidence"] == 0.9123


def test_assignment_from_dict_round_trips_enums_and_manual_override():
    original = CurationAssignment(
        item_type=AssignmentType.PLAYLIST,
        item_id="playlist-2",
        item_name="Playlist B",
        genre="ambient",
        temperament=TemperBucket.WOE,
        source=AssignmentSource.MANUAL,
        confidence=0.7,
        manual_override=True,
    )

    assignment = CurationAssignment.from_dict(original.to_dict())

    assert assignment == original
    assert assignment.item_type is AssignmentType.PLAYLIST
    assert assignment.temperament is TemperBucket.WOE
    assert assignment.source is AssignmentSource.MANUAL
    assert assignment.manual_override is True
