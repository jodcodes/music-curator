"""Tests for balanced, order-preserving playlist partitioning."""

import pytest

from src.playlist_sizing import balanced_parts


@pytest.mark.parametrize(
    ("count", "expected_lengths"),
    [
        (0, []),
        (1, [1]),
        (49, [49]),
        (50, [50]),
        (100, [100]),
        (101, [51, 50]),
        (150, [75, 75]),
        (199, [100, 99]),
        (200, [100, 100]),
        (201, [67, 67, 67]),
    ],
)
def test_balanced_parts_preserves_order_and_balances_sizes(count, expected_lengths):
    track_ids = [str(index) for index in range(count)]
    original = track_ids.copy()

    parts = balanced_parts(track_ids)

    assert [len(part) for part in parts] == expected_lengths
    assert [track_id for part in parts for track_id in part] == original
    assert track_ids == original


def test_balanced_parts_preserves_duplicate_occurrences():
    track_ids = ["a", "b", "a", "a", "c"]

    assert balanced_parts(track_ids, maximum=3) == [["a", "b", "a"], ["a", "c"]]
    assert track_ids == ["a", "b", "a", "a", "c"]


@pytest.mark.parametrize(
    ("maximum", "expected"),
    [
        (1, [["a"], ["b"], ["c"], ["d"], ["e"]]),
        (2, [["a", "b"], ["c", "d"], ["e"]]),
        (5, [["a", "b", "c", "d", "e"]]),
        (10, [["a", "b", "c", "d", "e"]]),
    ],
)
def test_balanced_parts_respects_custom_maximum(maximum, expected):
    assert balanced_parts(["a", "b", "c", "d", "e"], maximum=maximum) == expected


@pytest.mark.parametrize("maximum", [0, -1, -100])
@pytest.mark.parametrize("track_ids", [[], ["a"]])
def test_balanced_parts_rejects_nonpositive_maximum(track_ids, maximum):
    with pytest.raises(ValueError):
        balanced_parts(track_ids, maximum=maximum)
