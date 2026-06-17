#!/usr/bin/env python3
"""
Quick Test Script

Tests the temperament analyzer with sample data to ensure everything works
before connecting to real Apple Music library.
"""

import os
import sys
from typing import Dict, List

from src.temperament_analyzer import (
    ClassificationResult,
    LLMClient,
    MusicLibraryClient,
    Playlist,
    Temperament,
    TemperamentAnalyzer,
    Track,
)


class MockMusicClient(MusicLibraryClient):
    """Mock music client for testing"""

    def authenticate(self) -> bool:
        print("✓ Mock authentication successful")
        return True

    def get_playlists(self) -> List[Playlist]:
        """Return sample playlists"""
        return [
            Playlist(
                playlist_id="pl.001",
                name="Sad Songs",
                tracks=[
                    Track("1", "Tears in Heaven", "Eric Clapton"),
                    Track("2", "Hurt", "Johnny Cash"),
                    Track("3", "Yesterday", "The Beatles"),
                ],
                description="Songs for melancholic moments",
            ),
            Playlist(
                playlist_id="pl.002",
                name="Party Mix",
                tracks=[
                    Track("4", "Happy", "Pharrell Williams", genre="Pop"),
                    Track("5", "Uptown Funk", "Mark Ronson ft. Bruno Mars", genre="Funk"),
                    Track("6", "Can't Stop the Feeling", "Justin Timberlake", genre="Pop"),
                ],
                description="Upbeat party songs",
            ),
        ]

    def create_folder(self, folder_name: str) -> str:
        print(f"✓ Mock folder created: {folder_name}")
        return f"mock_folder_{folder_name}"

    def move_playlist_to_folder(self, playlist_id: str, folder_id: str) -> bool:
        print(f"✓ Mock move: {playlist_id} → {folder_id}")
        return True


class MockLLMClient(LLMClient):
    """Mock LLM client with simple keyword matching"""

    SAD_WORDS = ["sad", "tears", "hurt", "yesterday", "blue", "lonely"]
    HAPPY_WORDS = ["happy", "party", "funk", "dance", "fun", "uptown"]

    def classify_track(self, track: Track) -> ClassificationResult:
        """Simple keyword-based classification"""
        text = f"{track.name} {track.artist}".lower()

        if any(word in text for word in self.SAD_WORDS):
            return ClassificationResult(
                temperament=Temperament.WOE,
                confidence=0.8,
                reasoning=f"Detected sad keywords in '{track.name}'",
            )
        elif any(word in text for word in self.HAPPY_WORDS):
            return ClassificationResult(
                temperament=Temperament.FROLIC,
                confidence=0.8,
                reasoning=f"Detected happy keywords in '{track.name}'",
            )
        else:
            return ClassificationResult(
                temperament=Temperament.FROLIC, confidence=0.5, reasoning="Default classification"
            )

    def classify_playlist(
        self, playlist: Playlist, track_classifications: List[ClassificationResult]
    ) -> ClassificationResult:
        """Majority vote from track classifications"""
        from collections import Counter

        counts = Counter([c.temperament for c in track_classifications])
        dominant = counts.most_common(1)[0][0]
        confidence = counts[dominant] / len(track_classifications)

        return ClassificationResult(
            temperament=dominant, confidence=confidence, reasoning=f"Majority vote: {dict(counts)}"
        )


def main():
    """Run quick test"""
    print("=" * 60)
    print("Temperament Analyzer - Quick Test")
    print("=" * 60)
    print()
    print("This test uses mock data and doesn't require API keys.")
    print()

    try:
        # Create mock clients
        music_client = MockMusicClient()
        llm_client = MockLLMClient()

        # Create analyzer
        analyzer = TemperamentAnalyzer(music_client, llm_client)

        # Run analysis
        print("Starting analysis...")
        print()
        success = analyzer.analyze_and_organize(batch_size=5)

        if success:
            print()
            print("=" * 60)
            print("✓ TEST SUCCESSFUL!")
            print("=" * 60)
            print()
            print("The script is working correctly!")
            print("Next steps:")
            print("  1. Set up your API credentials (see SETUP.md)")
            print("  2. Run: python temperament_analyzer.py")
            print()
        else:
            print()
            print("✗ Test failed")
            sys.exit(1)

    except Exception as e:
        print()
        print("=" * 60)
        print("✗ ERROR")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
