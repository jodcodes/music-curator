import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from apple_music import AppleMusicInterface


class TestAppleMusicFolderStructure(unittest.TestCase):
    def setUp(self):
        self.client = AppleMusicInterface()
        self.fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures")

    def _read_fixture(self, name: str) -> str:
        path = os.path.join(self.fixture_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @patch.object(AppleMusicInterface, "_run_applescript")
    def test_get_playlist_folder_structure_valid(self, mock_run):
        mock_run.return_value = (True, self._read_fixture("apple_music_folder_structure_valid.txt"))

        result = self.client.get_playlist_folder_structure()

        self.assertEqual(
            result,
            {
                "Focus": ["Morning Chill", "Late Night Mix"],
                "Workout": ["Cardio Hits"],
                "Empty Folder": [],
            },
        )

    @patch.object(AppleMusicInterface, "_run_applescript")
    def test_get_playlist_folder_structure_empty(self, mock_run):
        mock_run.return_value = (True, "")

        result = self.client.get_playlist_folder_structure()

        self.assertEqual(result, {})

    @patch.object(AppleMusicInterface, "_run_applescript")
    def test_get_playlist_folder_structure_malformed(self, mock_run):
        mock_run.return_value = (
            True,
            self._read_fixture("apple_music_folder_structure_malformed.txt"),
        )

        result = self.client.get_playlist_folder_structure()

        self.assertIsNone(result)

    @patch.object(AppleMusicInterface, "_run_applescript")
    def test_get_favourite_tracks_normalizes_track_identity(self, mock_run):
        captured = {}

        def fake_run(script):
            captured["script"] = script
            return (
                True,
                "ABC123\tTrack A\tArtist A\tHip-Hop\nDEF456\tTrack B\tArtist B\t",
            )

        mock_run.side_effect = fake_run

        result = self.client.get_favourite_tracks()

        script = " ".join(captured["script"].split())
        self.assertIn(
            'set targetPlaylist to playlist "Favourite Songs"',
            script,
        )
        self.assertIn("persistent ID of every track of targetPlaylist", script)
        self.assertIn("name of every track of targetPlaylist", script)
        self.assertNotIn("repeat with trk in tracks of targetPlaylist", script)
        self.assertNotIn("composer of trk", script)
        self.assertNotIn("duration of trk", script)
        self.assertEqual(result[0]["title"], "Track A")
        self.assertEqual(result[0]["name"], "Track A")
        self.assertEqual(result[0]["persistent_id"], "ABC123")
        self.assertEqual(result[1]["genre"], "")

    @patch.object(AppleMusicInterface, "_run_applescript")
    def test_get_regular_playlist_tracks_raises_on_applescript_failure(self, mock_run):
        mock_run.return_value = (False, "AppleScript execution timed out after 120s")

        with self.assertRaisesRegex(RuntimeError, "timed out"):
            self.client._get_regular_playlist_tracks("Favourite Songs")


if __name__ == "__main__":
    unittest.main()
