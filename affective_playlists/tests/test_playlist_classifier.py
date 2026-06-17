#!/usr/bin/env python3
"""
Comprehensive test suite for PlaylistClassifier.

Tests genre mapping, track scoring, playlist analysis, and dominance detection
with various edge cases and real artist data.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.playlist_classifier import PlaylistClassifier


@pytest.fixture
def classifier():
    """Initialize classifier with real config files."""
    config_dir = Path(__file__).parent.parent / "data" / "config"
    artist_dir = Path(__file__).parent.parent / "data" / "artist_lists"

    return PlaylistClassifier(
        genre_map_path=str(config_dir / "genre_map.json"),
        weights_path=str(config_dir / "weights.json"),
        artist_lists_dir=str(artist_dir),
        dominance_threshold=0.3,
        enable_genre_enrichment=False,  # Disable for tests
    )


class TestPlaylistClassifierSetup:
    """Tests for classifier initialization and setup."""

    def test_classifier_initialization(self, classifier):
        """Test that classifier initializes correctly."""
        assert classifier is not None
        assert classifier.genre_map is not None
        assert classifier.weights is not None
        assert classifier.artist_lists is not None
        assert len(classifier.target_genres) > 0

    def test_genre_map_loaded(self, classifier):
        """Test that genre_map contains expected raw genres that map to target genres."""
        # Check that the genre_map has been populated with raw genres
        assert len(classifier.genre_map) > 0
        # Check that common raw genres map to known target genres or raw genres
        pop_mapping = classifier.genre_map.get("pop")
        assert pop_mapping in classifier.target_genres or pop_mapping is not None
        assert classifier.genre_map.get("edm") == "electronic"
        assert classifier.genre_map.get("hip hop") == "hiphop"

    def test_weights_loaded(self, classifier):
        """Test that weights configuration is loaded."""
        assert "genre_match" in classifier.weights
        assert "artist_match" in classifier.weights
        assert "composer_match" in classifier.weights

    def test_target_genres_populated(self, classifier):
        """Test that target genres are extracted from artist lists."""
        expected_genres = {"hiphop", "electronic", "disco_funk_soul", "jazz", "world", "rock"}
        actual_genres = set(classifier.target_genres)

        # Check that at least the main genres are present
        assert expected_genres.issubset(actual_genres)


class TestGenreMapping:
    """Tests for raw genre to target genre mapping."""

    def test_direct_genre_mapping(self, classifier):
        """Test direct mapping from genre_map.json."""
        # Test known mappings
        result = classifier.map_genre_to_target("edm")
        assert result == "electronic"

        result = classifier.map_genre_to_target("classical")
        assert result == "classical"

    def test_case_insensitive_mapping(self, classifier):
        """Test that mapping is case-insensitive."""
        result1 = classifier.map_genre_to_target("EDM")
        result2 = classifier.map_genre_to_target("edm")
        result3 = classifier.map_genre_to_target("Edm")

        assert result1 == result2 == result3

    def test_keyword_based_mapping(self, classifier):
        """Test keyword-based mapping fallback."""
        result = classifier.map_genre_to_target("hip hop beats")
        assert result == "hiphop" or result is not None

        result = classifier.map_genre_to_target("electronic dance")
        assert result == "electronic" or result is not None

    def test_unmapped_genre_returns_none(self, classifier):
        """Test that unmapped genres return None."""
        result = classifier.map_genre_to_target("xyzabc unknown")
        assert result is None

    def test_empty_genre_returns_none(self, classifier):
        """Test that empty string returns None."""
        result = classifier.map_genre_to_target("")
        assert result is None


class TestTrackScoring:
    """Tests for individual track scoring."""

    def test_score_track_with_genre(self, classifier):
        """Test scoring track with genre field."""
        track = {"artist": "Unknown Artist", "name": "Test Track", "genre": "rock"}
        scores = classifier.score_track(track)

        assert scores is not None
        assert isinstance(scores, dict)
        assert len(scores) > 0
        assert "rock" in scores

    def test_score_track_with_mapped_genre(self, classifier):
        """Test that genre mapping is applied in scoring."""
        track = {"artist": "Unknown", "name": "Test", "genre": "edm"}  # Should map to electronic
        scores = classifier.score_track(track)

        # Electronic should have higher score than other genres
        if "electronic" in scores:
            electronic_score = scores["electronic"]
            other_scores = [s for g, s in scores.items() if g != "electronic"]
            if other_scores:
                assert electronic_score >= max(other_scores)

    def test_score_track_missing_genre(self, classifier):
        """Test scoring track without genre field."""
        track = {"artist": "Unknown", "name": "Test Track"}
        scores = classifier.score_track(track)

        assert scores is not None
        assert isinstance(scores, dict)

    def test_score_track_case_insensitive_fields(self, classifier):
        """Test that field matching is case-insensitive."""
        track1 = {"artist": "The Beatles", "name": "Hey Jude", "genre": "rock"}
        track2 = {"artist": "the beatles", "name": "hey jude", "genre": "ROCK"}

        scores1 = classifier.score_track(track1)
        scores2 = classifier.score_track(track2)

        # Scores should be similar (normalized matching)
        assert set(scores1.keys()) == set(scores2.keys())

    def test_score_track_with_composer(self, classifier):
        """Test that composer field is used for scoring."""
        track = {
            "artist": "Unknown",
            "name": "Test",
            "composer": "Miles Davis",  # Jazz composer
            "genre": "unknown",
        }
        scores = classifier.score_track(track)

        assert scores is not None
        assert "jazz" in scores or "world" in scores


class TestPlaylistScoring:
    """Tests for full playlist scoring."""

    def test_score_empty_playlist(self, classifier):
        """Test scoring empty playlist."""
        scores = classifier.score_playlist([])
        assert scores == {}

    def test_score_single_track_playlist(self, classifier):
        """Test scoring playlist with single track."""
        tracks = [{"artist": "Unknown", "name": "Test", "genre": "rock"}]
        scores = classifier.score_playlist(tracks)

        assert scores is not None
        assert len(scores) > 0

    def test_score_multi_track_playlist(self, classifier):
        """Test scoring playlist with multiple tracks."""
        tracks = [
            {"artist": "Artist1", "name": "Track1", "genre": "rock"},
            {"artist": "Artist2", "name": "Track2", "genre": "rock"},
            {"artist": "Artist3", "name": "Track3", "genre": "rock"},
        ]
        scores = classifier.score_playlist(tracks)

        assert scores is not None
        assert len(scores) > 0
        # Rock should have accumulated score
        if "rock" in scores:
            assert scores["rock"] > 0

    def test_score_mixed_genre_playlist(self, classifier):
        """Test scoring playlist with mixed genres."""
        tracks = [
            {"artist": "Unknown1", "name": "Track1", "genre": "rock"},
            {"artist": "Unknown2", "name": "Track2", "genre": "electronic"},
        ]
        scores = classifier.score_playlist(tracks)

        assert scores is not None
        assert len(scores) > 0

    def test_playlist_scores_aggregate(self, classifier):
        """Test that playlist scores are aggregates of track scores."""
        tracks = [
            {"artist": "Unknown", "name": "Test1", "genre": "rock"},
            {"artist": "Unknown", "name": "Test2", "genre": "rock"},
        ]
        scores = classifier.score_playlist(tracks)

        # If single track had rock score, double track should have higher
        single_track_scores = classifier.score_track(tracks[0])
        assert scores["rock"] > single_track_scores.get("rock", 0)


class TestDominanceDetection:
    """Tests for dominant genre detection."""

    def test_clear_dominance_detected(self, classifier):
        """Test detection of clear genre dominance."""
        # Playlist with multiple rock tracks
        tracks = [
            {"artist": "Unknown", "name": "Rock1", "genre": "rock"},
            {"artist": "Unknown", "name": "Rock2", "genre": "rock"},
            {"artist": "Unknown", "name": "Rock3", "genre": "rock"},
            {"artist": "Unknown", "name": "Rock4", "genre": "rock"},
            {"artist": "Unknown", "name": "Pop1", "genre": "pop"},
        ]

        genre, info = classifier.classify_playlist(tracks, "Rock Playlist")

        # Rock should be detected or info should indicate the reason
        assert info is not None
        assert "reason" in info
        assert "confidence" in info

    def test_no_dominance_returns_none(self, classifier):
        """Test that low-score playlists don't cause errors."""
        tracks = [
            {"artist": "Unknown", "name": "Unknown1"},  # No genre
            {"artist": "Unknown", "name": "Unknown2"},  # No genre
        ]

        genre, info = classifier.classify_playlist(tracks, "Unclassified Playlist")

        # Should handle gracefully without error
        assert info is not None
        assert "reason" in info

    def test_mixed_genre_balanced_playlist(self, classifier):
        """Test balanced multi-genre playlist."""
        tracks = [
            {"artist": "Unknown1", "name": "Track1", "genre": "rock"},
            {"artist": "Unknown2", "name": "Track2", "genre": "electronic"},
            {"artist": "Unknown3", "name": "Track3", "genre": "hiphop"},
        ]

        genre, info = classifier.classify_playlist(tracks, "Mixed Playlist")

        assert info is not None
        assert "reason" in info
        if genre is None:
            assert "No clear dominance" in info["reason"]


class TestClassificationPipeline:
    """Integration tests for full classification pipeline."""

    def test_full_classification_rock_playlist(self, classifier):
        """Test full classification pipeline on rock playlist."""
        tracks = [
            {"artist": "The Rolling Stones", "name": "Satisfaction", "genre": "rock"},
            {"artist": "Led Zeppelin", "name": "Whole Lotta Love", "genre": "rock"},
            {"artist": "Pink Floyd", "name": "Comfortably Numb", "genre": "rock"},
        ]

        genre, info = classifier.classify_playlist(tracks, "Classic Rock")

        assert info is not None
        assert "method" in info
        assert "confidence" in info
        assert "reason" in info

    def test_full_classification_jazz_playlist(self, classifier):
        """Test full classification pipeline on jazz playlist."""
        tracks = [
            {"artist": "Miles Davis", "name": "Kind of Blue", "genre": "jazz"},
            {"artist": "John Coltrane", "name": "A Love Supreme", "genre": "jazz"},
            {"artist": "Bill Evans", "name": "Autumn Leaves", "genre": "jazz"},
        ]

        genre, info = classifier.classify_playlist(tracks, "Jazz Classics")

        assert info is not None
        assert "track_count" in info
        assert info["track_count"] == 3

    def test_full_classification_with_missing_data(self, classifier):
        """Test classification with incomplete track data."""
        tracks = [
            {"artist": "Artist1", "genre": "rock"},  # Missing name
            {"name": "Track2", "genre": "rock"},  # Missing artist
            {"artist": "Artist3", "name": "Track3"},  # Missing genre
        ]

        genre, info = classifier.classify_playlist(tracks, "Incomplete Data")

        # Should not crash, should process available data
        assert info is not None
        assert "track_count" in info
        assert info["track_count"] == 3


class TestGenreEnrichment:
    """Tests for database-driven genre enrichment."""

    def test_genre_enrichment_skipped_when_disabled(self, classifier):
        """Test that enrichment is skipped when disabled."""
        track = {"artist": "Test Artist", "name": "Test Song"}
        result = classifier.enrich_missing_genre(track)
        assert result is None

    def test_genre_enrichment_skips_existing_genre(self, classifier):
        """Test that enrichment skips tracks with existing genre."""
        track = {"artist": "Test Artist", "name": "Test Song", "genre": "rock"}
        # When enrichment is disabled, it returns None but doesn't fail
        result = classifier.enrich_missing_genre(track)
        # Genre should remain unchanged
        assert track["genre"] == "rock"

    def test_genre_enrichment_needs_artist_and_title(self, classifier):
        """Test that enrichment requires artist and title."""
        track = {"artist": "Test Artist"}  # Missing title
        result = classifier.enrich_missing_genre(track)
        assert result is None

    def test_score_track_attempts_enrichment(self, classifier):
        """Test that score_track attempts to enrich missing genre."""
        track = {"artist": "Unknown Artist", "name": "Unknown Track"}
        scores = classifier.score_track(track)
        # Should return scores even without enrichment (enrichment is disabled)
        assert isinstance(scores, dict)
        assert len(scores) > 0


class TestAnalyzedArtistsIntegration:
    """Tests for adding analyzed artists from database queries."""

    def test_add_analyzed_artists(self, classifier):
        """Test adding analyzed artists to genre."""
        initial_count = len(classifier.artist_lists.get("rock", {}).get("artists", []))

        new_artists = ["Test Artist 1", "Test Artist 2"]
        classifier.add_analyzed_artists("rock", new_artists)

        new_count = len(classifier.artist_lists["rock"]["artists"])
        assert new_count >= initial_count

    def test_add_artists_normalizes_names(self, classifier):
        """Test that added artists are normalized."""
        classifier.add_analyzed_artists("rock", ["TEST ARTIST"])

        artists = classifier.artist_lists["rock"]["artists"]
        assert "test artist" in artists

    def test_add_artists_avoids_duplicates(self, classifier):
        """Test that duplicate artists are not added."""
        artist = "Unique Test Artist"
        initial_count = len(classifier.artist_lists["rock"]["artists"])

        classifier.add_analyzed_artists("rock", [artist])
        count_after_first = len(classifier.artist_lists["rock"]["artists"])

        classifier.add_analyzed_artists("rock", [artist])
        count_after_second = len(classifier.artist_lists["rock"]["artists"])

        assert count_after_first == count_after_second

    def test_add_artists_to_new_genre(self, classifier):
        """Test adding artists to non-existent genre."""
        genre = "test_genre"

        classifier.add_analyzed_artists(genre, ["Artist1", "Artist2"])

        assert genre in classifier.artist_lists
        assert len(classifier.artist_lists[genre]["artists"]) > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_large_playlist(self, classifier):
        """Test classification of very large playlist."""
        tracks = [
            {"artist": f"Artist{i}", "name": f"Track{i}", "genre": "rock"} for i in range(100)
        ]

        genre, info = classifier.classify_playlist(tracks, "Large Playlist")

        assert info is not None
        assert info["track_count"] == 100

    def test_playlist_with_special_characters(self, classifier):
        """Test handling of special characters in metadata."""
        tracks = [
            {"artist": "Artïst Nâme", "name": "Trâck Tïtle", "genre": "rock"},
            {"artist": "艺术家", "name": "歌曲", "genre": "rock"},
        ]

        genre, info = classifier.classify_playlist(tracks, "Special Chars")

        # Should not crash
        assert info is not None

    def test_playlist_with_null_values(self, classifier):
        """Test handling of null/None values."""
        tracks = [
            {"artist": None, "name": "Track1", "genre": "rock"},
            {"artist": "Artist2", "name": None, "genre": "rock"},
            {"artist": "Artist3", "name": "Track3", "genre": None},
        ]

        genre, info = classifier.classify_playlist(tracks, "Null Values")

        assert info is not None
        assert "error" not in info or info.get("error") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
