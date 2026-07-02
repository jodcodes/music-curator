"""
Tests for CLI UI module.

Tests for the fun and engaging CLI user interface components
including colors, progress bars, menus, and formatting utilities.
"""

import os
import sys
import unittest
from io import StringIO

from src.cli_ui import (
    Box,
    Color,
    Icon,
    Menu,
    ProgressBar,
    Spinner,
    Table,
    bold,
    colorize,
    dim,
    error,
    format_stats,
    info,
    print_footer,
    print_header,
    success,
    underline,
    warning,
)


class TestColorCodes(unittest.TestCase):
    """Test ANSI color codes."""

    def test_color_codes_exist(self):
        """Test that color codes are defined."""
        self.assertIsNotNone(Color.RED)
        self.assertIsNotNone(Color.GREEN)
        self.assertIsNotNone(Color.BLUE)

    def test_color_reset(self):
        """Test RESET code is defined (may be empty string if not TTY)."""
        self.assertIsNotNone(Color.RESET)
        self.assertIsInstance(Color.RESET, str)

    def test_colorize_function(self):
        """Test colorize wraps text with color."""
        result = colorize("test", Color.RED)
        self.assertIn("test", result)
        self.assertIn(Color.RED, result)
        self.assertIn(Color.RESET, result)

    def test_bold_function(self):
        """Test bold wraps text."""
        result = bold("test")
        self.assertIn("test", result)
        self.assertIn(Color.BOLD, result)

    def test_dim_function(self):
        """Test dim wraps text."""
        result = dim("test")
        self.assertIn("test", result)
        self.assertIn(Color.DIM, result)

    def test_underline_function(self):
        """Test underline wraps text."""
        result = underline("test")
        self.assertIn("test", result)
        self.assertIn(Color.UNDERLINE, result)


class TestStatusMessages(unittest.TestCase):
    """Test status message formatting."""

    def test_success_message(self):
        """Test success message includes icon and text."""
        result = success("All done")
        self.assertIn("All done", result)
        self.assertIn(Icon.SUCCESS, result)
        self.assertIn(Color.GREEN, result)

    def test_error_message(self):
        """Test error message includes icon and text."""
        result = error("Something failed")
        self.assertIn("Something failed", result)
        self.assertIn(Icon.ERROR, result)
        self.assertIn(Color.RED, result)

    def test_warning_message(self):
        """Test warning message includes icon and text."""
        result = warning("Be careful")
        self.assertIn("Be careful", result)
        self.assertIn(Icon.WARNING, result)
        self.assertIn(Color.YELLOW, result)

    def test_info_message(self):
        """Test info message includes icon and text."""
        result = info("FYI")
        self.assertIn("FYI", result)
        self.assertIn(Icon.INFO, result)
        self.assertIn(Color.CYAN, result)


class TestIcons(unittest.TestCase):
    """Test icon definitions."""

    def test_icons_exist(self):
        """Test that icons are defined."""
        self.assertIsNotNone(Icon.SUCCESS)
        self.assertIsNotNone(Icon.ERROR)
        self.assertIsNotNone(Icon.WARNING)

    def test_icon_values_are_strings(self):
        """Test icons are non-empty strings."""
        self.assertIsInstance(Icon.SUCCESS, str)
        self.assertGreater(len(Icon.SUCCESS), 0)

    def test_music_icons(self):
        """Test music-related icons."""
        self.assertIsNotNone(Icon.MUSIC_NOTE)
        self.assertIsNotNone(Icon.MUSIC_NOTES)


class TestBox(unittest.TestCase):
    """Test Box formatting."""

    def test_simple_box_has_borders(self):
        """Test simple box includes border characters."""
        result = Box.simple("content")
        self.assertIn(Icon.BOX_TL, result)
        self.assertIn(Icon.BOX_TR, result)
        self.assertIn(Icon.BOX_BL, result)
        self.assertIn(Icon.BOX_BR, result)
        self.assertIn("content", result)

    def test_simple_box_with_title(self):
        """Test simple box includes title."""
        result = Box.simple("content", title="Header")
        self.assertIn("Header", result)
        self.assertIn("content", result)

    def test_section_has_title(self):
        """Test section includes title."""
        result = Box.section("Title", "Content")
        self.assertIn("Title", result)
        self.assertIn("Content", result)
        self.assertIn(Icon.DIAMOND, result)


class TestProgressBar(unittest.TestCase):
    """Test ProgressBar functionality."""

    def test_progress_bar_creation(self):
        """Test progress bar can be created."""
        prog = ProgressBar(10, "Test")
        self.assertEqual(prog.total, 10)
        self.assertEqual(prog.current, 0)
        self.assertEqual(prog.label, "Test")

    def test_progress_bar_update(self):
        """Test progress bar update increments."""
        prog = ProgressBar(10)
        self.assertEqual(prog.current, 0)
        prog.update()
        self.assertEqual(prog.current, 1)
        prog.update(5)
        self.assertEqual(prog.current, 6)

    def test_progress_bar_set(self):
        """Test progress bar set."""
        prog = ProgressBar(10)
        prog.set(5)
        self.assertEqual(prog.current, 5)

    def test_progress_bar_capped_at_total(self):
        """Test progress bar is capped at total."""
        prog = ProgressBar(10)
        prog.set(20)
        self.assertEqual(prog.current, 10)
        prog.update(5)
        self.assertEqual(prog.current, 10)


class TestTable(unittest.TestCase):
    """Test Table formatting."""

    def test_table_creation(self):
        """Test table can be created."""
        table = Table(["Col1", "Col2"], title="Test")
        self.assertEqual(table.headers, ["Col1", "Col2"])
        self.assertEqual(table.title, "Test")

    def test_table_add_row(self):
        """Test table rows can be added."""
        table = Table(["Col1", "Col2"])
        self.assertEqual(len(table.rows), 0)
        table.add_row("A", "B")
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0], ("A", "B"))

    def test_table_multiple_rows(self):
        """Test multiple rows."""
        table = Table(["Col1", "Col2"])
        table.add_row("A", "B")
        table.add_row("C", "D")
        table.add_row("E", "F")
        self.assertEqual(len(table.rows), 3)


class TestFormatStats(unittest.TestCase):
    """Test statistics formatting."""

    def test_format_stats_includes_title(self):
        """Test format_stats includes title."""
        stats = {"Processed": 10, "Skipped": 5}
        result = format_stats("Test Stats", stats)
        self.assertIn("Test Stats", result)

    def test_format_stats_includes_values(self):
        """Test format_stats includes all values."""
        stats = {"Processed": 10, "Skipped": 5}
        result = format_stats("Stats", stats)
        self.assertIn("Processed", result)
        self.assertIn("Skipped", result)
        self.assertIn("10", result)
        self.assertIn("5", result)

    def test_format_stats_percentage(self):
        """Test format_stats calculates percentages."""
        stats = {"A": 1, "B": 1}  # 50/50
        result = format_stats("Stats", stats)
        # Should show ~50% for each
        self.assertIn("50", result)

    def test_format_stats_empty(self):
        """Test format_stats with empty dict."""
        stats = {}
        result = format_stats("Stats", stats)
        self.assertIsInstance(result, str)


class TestColorDisable(unittest.TestCase):
    """Test color disabling."""

    def setUp(self):
        """Save original colors."""
        self.original_red = Color.RED

    def tearDown(self):
        """Restore colors."""
        Color.RED = self.original_red

    def test_color_disable(self):
        """Test color disable sets empty strings."""
        Color.disable()
        self.assertEqual(Color.RED, "")
        self.assertEqual(Color.GREEN, "")
        self.assertEqual(Color.BOLD, "")

    def test_colorize_without_colors(self):
        """Test colorize works with colors disabled."""
        Color.disable()
        result = colorize("test", Color.RED)
        self.assertEqual(result, "test")


class TestIconDictionary(unittest.TestCase):
    """Test icon definitions are consistent."""

    def test_all_icons_are_strings(self):
        """Test all icon attributes are strings."""
        for attr in dir(Icon):
            if not attr.startswith("_"):
                value = getattr(Icon, attr)
                if isinstance(value, str):
                    self.assertGreater(len(value), 0)


class TestMenuConfirm(unittest.TestCase):
    """Test Menu.confirm is callable (without actual input)."""

    def test_confirm_method_exists(self):
        """Test confirm method exists."""
        self.assertTrue(hasattr(Menu, "confirm"))
        self.assertTrue(callable(Menu.confirm))


if __name__ == "__main__":
    unittest.main()
