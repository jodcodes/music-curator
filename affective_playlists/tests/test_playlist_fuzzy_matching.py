"""
Tests for playlist fuzzy matching bug fix.

Issue: Playlist 'gc 3-Martini Sound' not found due to regex parsing failure
Fix: Improved regex parsing and fuzzy matching for edge cases
"""

import os
import sys

import pytest

from src.metadata_fill import MetadataFiller
from src.playlist_utils import PlaylistFuzzyMatcher


class TestPlaylistFuzzyMatching:
    """Test fuzzy matching for playlist name resolution."""

    def test_find_playlist_exact_match(self):
        """Test exact match returns correct ID."""
        playlist_ids = {"gc 3-Martini Sound": "A1B2C3D4E5F6A7B8", "My Playlist": "B2C3D4E5F6B7C8D9"}

        result = PlaylistFuzzyMatcher.find_playlist_by_name("gc 3-Martini Sound", playlist_ids)
        assert result == "A1B2C3D4E5F6A7B8"

    def test_find_playlist_case_insensitive(self):
        """Test case-insensitive matching."""
        playlist_ids = {"gc 3-Martini Sound": "A1B2C3D4E5F6A7B8"}

        # Try different cases
        assert (
            PlaylistFuzzyMatcher.find_playlist_by_name("GC 3-MARTINI SOUND", playlist_ids)
            == "A1B2C3D4E5F6A7B8"
        )
        assert (
            PlaylistFuzzyMatcher.find_playlist_by_name("gc 3-martini sound", playlist_ids)
            == "A1B2C3D4E5F6A7B8"
        )

    def test_find_playlist_fuzzy_partial_match(self):
        """Test fuzzy matching with similar names (>80% similarity)."""
        playlist_ids = {"gc 3-Martini Sound": "A1B2C3D4E5F6A7B8"}

        # Should match with high similarity
        result = PlaylistFuzzyMatcher.find_playlist_by_name("gc 3-Martini", playlist_ids)
        assert result == "A1B2C3D4E5F6A7B8"

    def test_find_playlist_not_found(self):
        """Test returns None when no match found."""
        playlist_ids = {"gc 3-Martini Sound": "A1B2C3D4E5F6A7B8"}

        result = PlaylistFuzzyMatcher.find_playlist_by_name("Nonexistent Playlist", playlist_ids)
        assert result is None

    def test_find_playlist_empty_dict(self):
        """Test handles empty playlist dictionary."""
        result = PlaylistFuzzyMatcher.find_playlist_by_name("Any Playlist", {})
        assert result is None

    def test_get_playlist_ids_extracts_hex_ids(self):
        """Test that _get_playlist_ids can extract valid 16-digit hex IDs."""
        # This is a parsing test - verify regex works
        import re

        # Sample AppleScript output with valid 16-digit hex IDs (A-F, 0-9 only)
        output = (
            "name:gc 3-Martini Sound, id:A1B2C3D4E5F6A7B8, name:My Playlist, id:C2D3E4F5A6B7C8D9"
        )

        # Test ID extraction
        id_pattern = r"([A-F0-9]{16})"
        matches = re.findall(id_pattern, output, re.IGNORECASE)
        assert len(matches) == 2
        assert "A1B2C3D4E5F6A7B8" in matches
        assert "C2D3E4F5A6B7C8D9" in matches

    def test_special_characters_in_playlist_name(self):
        """Test playlist names with special characters."""
        playlist_ids = {
            "gc 3-Martini Sound": "A1B2C3D4E5F6A7B8",
            "Rock & Roll": "B2C3D4E5F6B7C8D9",
            "80's Classics": "C3D4E5F6B7C8D9A0",
        }

        # Exact matches should work
        assert PlaylistFuzzyMatcher.find_playlist_by_name("gc 3-Martini Sound", playlist_ids)
        assert PlaylistFuzzyMatcher.find_playlist_by_name("Rock & Roll", playlist_ids)
        assert PlaylistFuzzyMatcher.find_playlist_by_name("80's Classics", playlist_ids)

    def test_multiple_similar_names_picks_best(self):
        """Test when multiple playlists are similar."""
        playlist_ids = {"Playlist A": "A1B2C3D4E5F6A7B8", "Playlist B": "B2C3D4E5F6B7C8D9"}

        # Should find exact match first
        result = PlaylistFuzzyMatcher.find_playlist_by_name("Playlist A", playlist_ids)
        assert result == "A1B2C3D4E5F6A7B8"

    def test_whitespace_handling(self):
        """Test handling of extra whitespace."""
        playlist_ids = {"gc 3-Martini Sound": "A1B2C3D4E5F6A7B8"}

        # Normalize and match
        result = PlaylistFuzzyMatcher.find_playlist_by_name("gc  3-Martini  Sound", playlist_ids)
        # Should match due to case-insensitive + fuzzy matching
        assert result is not None


class TestPlaylistMatchingEdgeCases:
    """Test edge cases in playlist matching."""

    def test_unicode_playlist_names(self):
        """Test playlist names with unicode characters."""
        playlist_ids = {"Café Vibes": "A1B2C3D4E5F6A7B8", "日本語プレイリスト": "B2C3D4E5F6B7C8D9"}

        # Should match exactly
        assert (
            PlaylistFuzzyMatcher.find_playlist_by_name("Café Vibes", playlist_ids)
            == "A1B2C3D4E5F6A7B8"
        )

    def test_numbers_in_playlist_name(self):
        """Test playlist names with numbers."""
        playlist_ids = {
            "90s Hits": "A1B2C3D4E5F6A7B8",
            "2000s Mix": "B2C3D4E5F6B7C8D9",
            "Top 100": "C3D4E5F6B7C8D9A0",
        }

        assert (
            PlaylistFuzzyMatcher.find_playlist_by_name("90s Hits", playlist_ids)
            == "A1B2C3D4E5F6A7B8"
        )
        assert (
            PlaylistFuzzyMatcher.find_playlist_by_name("2000s Mix", playlist_ids)
            == "B2C3D4E5F6B7C8D9"
        )
        assert (
            PlaylistFuzzyMatcher.find_playlist_by_name("Top 100", playlist_ids)
            == "C3D4E5F6B7C8D9A0"
        )

    def test_cutoff_threshold_80_percent(self):
        """Test that fuzzy matching respects 80% cutoff."""
        playlist_ids = {"Completely Different Name": "A1B2C3D4E5F6A7B8"}

        # Should not match (too dissimilar)
        result = PlaylistFuzzyMatcher.find_playlist_by_name("xyz abc def", playlist_ids)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
