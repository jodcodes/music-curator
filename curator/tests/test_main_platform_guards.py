"""
Unit tests for platform guard functionality in main.py.

Tests the require_macos() function to ensure platform constraints
are properly enforced.
"""

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest


class TestRequireMacOS:
    """Tests for macOS platform guard."""

    def test_require_macos_on_darwin_returns_true(self):
        """On macOS (darwin), require_macos should return True."""
        with patch("sys.platform", "darwin"):
            # Import inside patch to get the mocked platform
            import main

            result = main.require_macos("Test Feature")
            assert result is True

    def test_require_macos_on_non_darwin_returns_false(self):
        """On non-macOS, require_macos should return False."""
        with patch("sys.platform", "linux"):
            # Reload to get fresh platform check
            import importlib

            import main

            importlib.reload(main)
            result = main.require_macos("Test Feature")
            assert result is False

    def test_require_macos_prints_error_on_non_darwin(self, capsys):
        """On non-macOS, require_macos should print error message."""
        with patch("sys.platform", "linux"):
            import importlib

            import main

            importlib.reload(main)

            main.require_macos("Temperament Analysis")
            captured = capsys.readouterr()

            # Check that error message was printed
            assert "Temperament Analysis" in captured.out
            assert "macOS" in captured.out
            assert "Music.app" in captured.out

    def test_require_macos_prints_tip_on_non_darwin(self, capsys):
        """On non-macOS, require_macos should suggest alternative (folder enrichment)."""
        with patch("sys.platform", "linux"):
            import importlib

            import main

            importlib.reload(main)

            main.require_macos("Playlist enrichment")
            captured = capsys.readouterr()

            # Check for helpful tip
            assert "Folder" in captured.out or "folder" in captured.out.lower()

    @patch("sys.platform", "win32")
    def test_require_macos_on_windows_returns_false(self):
        """On Windows, require_macos should return False."""
        import importlib

        import main

        importlib.reload(main)
        result = main.require_macos("Test Feature")
        assert result is False
