"""Recorded metadata ranking, without Music.app or model calls."""

from copy import deepcopy
from itertools import permutations

import pytest


def rank(seed, candidates, limit=30):
    from src.seed_playlist import rank_seed_candidates

    return rank_seed_candidates(seed, candidates, limit)


def track(number, **metadata):
    return {"persistent_id": f"{number:016X}", **metadata}


def ids(result):
    return [row["persistent_id"] for row in result["tracks"]]


def test_seed_is_first_even_if_not_in_candidates():
    seed = track(9, mood="Woe", genre="Rock")
    result = rank(seed, [track(1, mood="Woe", genre="Rock")])
    assert ids(result) == ["0000000000000009", "0000000000000001"]
    assert result["tracks"][0]["reason"] == "selected_seed"


def test_recorded_mood_then_genre_then_stable_id_order():
    seed = track(9, temperament="Woe (Melancholic)", genre="Rock")
    result = rank(
        seed,
        [
            track(1, mood="Frolic", genre="Rock"),
            track(3, mood="Woe", genre="Jazz"),
            track(2, mood="  woe ", genre="ROCK"),
            track(4, temperament="Woe", genre="Jazz"),
            track(5, mood="Malice", genre="Pop"),
        ],
    )
    assert ids(result) == [f"{number:016X}" for number in [9, 2, 3, 4, 1, 5]]
    assert [row["reason"] for row in result["tracks"]] == [
        "selected_seed",
        "same_recorded_mood_and_genre",
        "same_recorded_mood",
        "same_recorded_mood",
        "same_genre",
        "no_recorded_match",
    ]


@pytest.mark.parametrize("limit, count", [(1, 1), (30, 30)])
def test_limit_includes_seed(limit, count):
    result = rank(track(99), [track(number) for number in range(40)], limit)
    assert len(result["tracks"]) == count
    assert len(set(ids(result))) == count


@pytest.mark.parametrize("limit", [0, 31, -1, 1.5, "2", None, True])
def test_invalid_limits_are_rejected(limit):
    with pytest.raises(ValueError, match="limit"):
        rank(track(1), [], limit)


@pytest.mark.parametrize(
    "seed",
    [None, {}, [], {"persistent_id": ""}, {"persistent_id": "not-an-id"}, {"persistent_id": 1}],
)
def test_absent_or_invalid_seed_is_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        rank(seed, [])


def test_underfilled_results_are_not_padded():
    assert ids(rank(track(9), [])) == ["0000000000000009"]
    assert ids(rank(track(9), [track(1)])) == ["0000000000000009", "0000000000000001"]


def test_duplicates_collapse_and_conflicting_metadata_is_deterministic():
    seed = track(15, mood="Woe", genre="Rock", name="User selection")
    candidates = [
        track(1, mood="Woe", genre="Rock", name="B"),
        track(1, mood="Frolic", genre="Jazz", name="A"),
        {**seed, "persistent_id": "000000000000000f", "name": "Other snapshot"},
    ]
    expected = rank(seed, candidates)
    for order in permutations(candidates):
        assert rank(seed, list(order)) == expected
    assert ids(expected) == ["000000000000000F", "0000000000000001"]
    assert expected["tracks"][0]["track"]["name"] == "User selection"
    assert expected["tracks"][1]["track"]["name"] == "A"
    assert "conflicting_duplicate_metadata:0000000000000001" in expected["warnings"]
    assert "conflicting_duplicate_metadata:000000000000000F" in expected["warnings"]


def test_equal_metadata_ranking_uses_ids_across_input_order():
    candidates = [track(number, mood="Woe") for number in [3, 1, 2]]
    for order in permutations(candidates):
        assert ids(rank(track(9, mood="Woe"), list(order))) == [
            "0000000000000009",
            "0000000000000001",
            "0000000000000002",
            "0000000000000003",
        ]


@pytest.mark.parametrize("seed_has_mood", [False, True])
def test_missing_mood_labels_genre_only_fallback(seed_has_mood):
    seed = track(9, genre="Rock", **({"mood": "Woe"} if seed_has_mood else {}))
    row = rank(seed, [track(1, genre="Rock")])["tracks"][1]
    assert row["reason"] == "genre_only_fallback"
    assert "missing_recorded_mood" in row["warnings"]


def test_missing_mood_without_matching_genre_warns_insufficient_metadata():
    row = rank(track(9), [track(1)])["tracks"][1]
    assert row["reason"] == "no_recorded_match"
    assert "insufficient_metadata" in row["warnings"]
    assert "missing_recorded_mood" in row["warnings"]
    assert "missing_genre" in row["warnings"]


def test_conflicting_recorded_mood_is_not_claimed_as_same_mood():
    row = rank(
        track(9, mood="Woe", genre="Rock"),
        [
            track(1, mood="Woe", temperament="Frolic", genre="Rock"),
        ],
    )["tracks"][1]
    assert row["reason"] == "genre_only_fallback"
    assert "conflicting_recorded_mood" in row["warnings"]


def test_missing_or_non_string_metadata_is_not_invented():
    result = rank(
        track(9, mood="unknown", genre="unknown"),
        [
            track(1, mood="unknown", genre="unknown"),
            track(2, mood=[], genre=1),
        ],
    )
    assert all(row["reason"] == "no_recorded_match" for row in result["tracks"][1:])
    assert all("insufficient_metadata" in row["warnings"] for row in result["tracks"][1:])


def test_original_metadata_and_inputs_are_preserved_and_detached():
    seed = track(9, mood=" Woe ", genre="ROCK", extra={"tags": ["original"]})
    candidates = [track(1, mood="Woe", genre="rock")]
    before = deepcopy((seed, candidates))
    result = rank(seed, candidates)
    assert (seed, candidates) == before
    assert result["tracks"][0]["track"] == before[0]
    result["tracks"][0]["track"]["extra"]["tags"].append("changed")
    assert (seed, candidates) == before


def test_invalid_candidate_ids_are_skipped_with_warning():
    result = rank(track(9), [{}, {"persistent_id": "bad"}, None, track(1)])
    assert ids(result) == ["0000000000000009", "0000000000000001"]
    assert "invalid_candidate_persistent_id" in result["warnings"]


def test_candidate_container_is_validated():
    with pytest.raises(ValueError, match="candidates"):
        rank(track(9), None)


def test_duplicate_list_tuple_collision_is_rejected_in_every_order():
    candidates = [track(1, extra=[1]), track(1, extra=(1,))]
    for order in permutations(candidates):
        with pytest.raises(ValueError, match="JSON"):
            rank(track(9), list(order))


@pytest.mark.parametrize(
    "extra", [(1,), {"nested": [(1,)]}, {1: "value"}, float("nan"), float("inf"), {1}, b"value"]
)
@pytest.mark.parametrize("position", ["seed", "candidate"])
def test_non_json_native_metadata_is_rejected(extra, position):
    seed = track(9, extra=extra) if position == "seed" else track(9)
    candidates = [track(1, extra=extra)] if position == "candidate" else []
    with pytest.raises(ValueError, match="JSON"):
        rank(seed, candidates)


def test_json_native_nested_metadata_preserves_types_and_values():
    extra = {"list": [None, True, 1, 1.0, "value", {"nested": []}]}
    result = rank(track(9, extra=extra), [])
    copied = result["tracks"][0]["track"]["extra"]
    assert copied == extra
    assert type(copied["list"][2]) is int
    assert type(copied["list"][3]) is float
