"""Tests for genre_groups pattern loading from JSON config."""

import json
from pathlib import Path

from src.genre_groups import canonical_genre_label, load_genre_patterns


def test_load_genre_patterns_returns_list_of_label_pattern_pairs():
    patterns = load_genre_patterns()
    assert isinstance(patterns, list)
    assert len(patterns) >= 20
    for entry in patterns:
        assert "label" in entry
        assert "pattern" in entry
        assert isinstance(entry["label"], str)
        assert isinstance(entry["pattern"], str)


def test_load_genre_patterns_matches_json_file_content():
    config_path = Path(__file__).resolve().parent.parent / "data" / "config" / "genre_groups.json"
    with open(config_path) as f:
        expected = json.load(f)
    patterns = load_genre_patterns()
    assert patterns == expected


def test_canonical_genre_label_uses_loaded_patterns():
    """Verify that a label from the JSON file is returned correctly."""
    patterns = load_genre_patterns()
    first_label = patterns[0]["label"]
    first_pattern = patterns[0]["pattern"]
    # Use the pattern itself as a test genre — it should map to its label
    import re

    text = first_pattern.replace("\\b", "").split("|")[0]
    assert canonical_genre_label(text) == first_label


def test_canonical_genre_label_lounge_takes_precedence_over_pop():
    """Lounge must be matched before Pop (order matters in JSON)."""
    assert canonical_genre_label("lounge") == "Lounge"
    assert canonical_genre_label("pop") == "Pop"


def test_canonical_genre_label_reggae_group_covers_dub_ska_dancehall():
    """Dub, Ska, Dancehall, Reggae, Roots Reggae must all map to 'Reggae'."""
    assert canonical_genre_label("Dub") == "Reggae"
    assert canonical_genre_label("Ska") == "Reggae"
    assert canonical_genre_label("Modern Dancehall") == "Reggae"
    assert canonical_genre_label("Reggae") == "Reggae"
    assert canonical_genre_label("Roots Reggae") == "Reggae"


def test_canonical_genre_label_dancehall_not_electronic():
    """'Modern Dancehall' must NOT match the Electronic group via 'dance'."""
    assert canonical_genre_label("Modern Dancehall") != "Electronic"
    assert canonical_genre_label("Dance") == "Electronic"


def test_canonical_genre_label_reggae_not_latin():
    """Reggae must NOT be in 'Latin & Brasileiro' anymore."""
    assert canonical_genre_label("Reggae") != "Latin & Brasileiro"


def test_canonical_genre_label_step4_mappings():
    """Genres added in step 4 — clear assignments based on library audit."""
    assert canonical_genre_label("Americana") == "Folk & Singer-Songwriter"
    assert canonical_genre_label("Arabic") == "African & World"
    assert canonical_genre_label("Asia") == "African & World"
    assert canonical_genre_label("Japan") == "African & World"
    assert canonical_genre_label("Axé") == "Latin & Brasileiro"
    assert canonical_genre_label("Motown") == "Soul"
    assert canonical_genre_label("Industrial") == "Rock"
    assert canonical_genre_label("Elektro") == "Electronic"
    assert canonical_genre_label("Healing") == "Ambient"


def test_canonical_genre_label_edge_cases_stay_sonstige():
    """Edge-case genres with no clear musical genre fall back to Sonstige."""
    for genre in ("Christian", "Spoken Word", "Instrumental", "Music",
                  "w", "1996", "2021", "Musik zum Fest",
                  "Contemporary Era", "Religiöse Musik", "Science"):
        assert canonical_genre_label(genre) == "Sonstige", f"{genre} should be Sonstige"


def test_canonical_genre_label_unknown_falls_back_to_sonstige():
    assert canonical_genre_label("zzz_unknown_genre") == "Sonstige"
    assert canonical_genre_label("") == "Sonstige"
    assert canonical_genre_label("other") == "Sonstige"
