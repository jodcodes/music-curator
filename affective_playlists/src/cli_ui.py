"""
Fun and engaging CLI UI utilities for affective_playlists.

This module provides a collection of CLI UI components that make
interacting with the application more engaging and user-friendly.
Includes colored output, progress bars, spinners, and interactive menus.
"""

import os
import sys
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Color:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @staticmethod
    def disable():
        """Disable colors for non-TTY output."""
        Color.RESET = ""
        Color.BOLD = ""
        Color.DIM = ""
        Color.ITALIC = ""
        Color.UNDERLINE = ""
        Color.RED = ""
        Color.GREEN = ""
        Color.YELLOW = ""
        Color.BLUE = ""
        Color.MAGENTA = ""
        Color.CYAN = ""
        Color.WHITE = ""
        Color.BRIGHT_RED = ""
        Color.BRIGHT_GREEN = ""
        Color.BRIGHT_YELLOW = ""
        Color.BRIGHT_BLUE = ""
        Color.BRIGHT_MAGENTA = ""
        Color.BRIGHT_CYAN = ""
        Color.BG_RED = ""
        Color.BG_GREEN = ""
        Color.BG_YELLOW = ""
        Color.BG_BLUE = ""


# Disable colors if not a TTY
if not sys.stdout.isatty():
    Color.disable()


class Icon:
    """Unicode icons for CLI output."""

    # Music
    MUSIC_NOTE = "♪"
    MUSIC_NOTES = "♫"

    # Status indicators
    SUCCESS = "✓"
    ERROR = "✗"
    WARNING = "⚠"
    INFO = "ℹ"
    QUESTION = "?"

    # Progress
    STAR = "★"
    EMPTY_STAR = "☆"
    CIRCLE = "●"
    EMPTY_CIRCLE = "○"
    DIAMOND = "◆"

    # Arrows
    ARROW_RIGHT = "→"
    ARROW_LEFT = "←"
    ARROW_UP = "↑"
    ARROW_DOWN = "↓"

    # Lines
    BOX_H = "─"
    BOX_V = "│"
    BOX_TL = "┌"
    BOX_TR = "┐"
    BOX_BL = "└"
    BOX_BR = "┘"
    BOX_CROSS = "┼"

    # Other
    CLOCK = "⏱"
    FIRE = "🔥"
    SPARKLES = "✨"
    TADA = "🎉"
    THUMBS_UP = "👍"


def colorize(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{Color.RESET}"


def bold(text: str) -> str:
    """Make text bold."""
    return f"{Color.BOLD}{text}{Color.RESET}"


def dim(text: str) -> str:
    """Make text dim/faint."""
    return f"{Color.DIM}{text}{Color.RESET}"


def underline(text: str) -> str:
    """Underline text."""
    return f"{Color.UNDERLINE}{text}{Color.RESET}"


def success(text: str) -> str:
    """Format success message."""
    return f"{Color.GREEN}{Icon.SUCCESS}{Color.RESET} {text}"


def error(text: str) -> str:
    """Format error message."""
    return f"{Color.RED}{Icon.ERROR}{Color.RESET} {text}"


def warning(text: str) -> str:
    """Format warning message."""
    return f"{Color.YELLOW}{Icon.WARNING}{Color.RESET} {text}"


def info(text: str) -> str:
    """Format info message."""
    return f"{Color.CYAN}{Icon.INFO}{Color.RESET} {text}"


class Box:
    """Draw a box around text."""

    @staticmethod
    def simple(text: str, title: Optional[str] = None, color: str = Color.CYAN) -> str:
        """Draw a simple box around text."""
        lines = text.split("\n")
        width = max(len(line) for line in lines) + 4

        # Add title if provided
        if title:
            width = max(width, len(title) + 6)

        result = []

        # Top border
        if title:
            padding = (width - len(title) - 4) // 2
            title_line = (
                (Icon.BOX_H * padding)
                + f" {title} "
                + (Icon.BOX_H * (width - len(title) - 4 - padding))
            )
            result.append(colorize(f"{Icon.BOX_TL}{title_line}{Icon.BOX_TR}", color))
        else:
            result.append(colorize(f"{Icon.BOX_TL}{Icon.BOX_H * (width - 2)}{Icon.BOX_TR}", color))

        # Content
        for line in lines:
            padding = width - len(line) - 4
            result.append(
                colorize(Icon.BOX_V, color) + f" {line:<{width-4}} " + colorize(Icon.BOX_V, color)
            )

        # Bottom border
        result.append(colorize(f"{Icon.BOX_BL}{Icon.BOX_H * (width - 2)}{Icon.BOX_BR}", color))

        return "\n".join(result)

    @staticmethod
    def section(title: str, content: str = "") -> str:
        """Create a section header."""
        result = f"\n{colorize(Icon.DIAMOND + ' ' + bold(title), Color.BRIGHT_CYAN)}"
        if content:
            result += f"\n{content}"
        return result


class ProgressBar:
    """Simple ASCII progress bar."""

    def __init__(self, total: int, label: str = "", width: int = 40):
        """Initialize progress bar."""
        self.total = total
        self.current = 0
        self.label = label
        self.width = width
        self.start_time = time.time()

    def update(self, amount: int = 1) -> None:
        """Update progress bar."""
        self.current = min(self.current + amount, self.total)
        self._draw()

    def set(self, current: int) -> None:
        """Set progress to specific value."""
        self.current = min(current, self.total)
        self._draw()

    def _draw(self) -> None:
        """Draw the progress bar."""
        if self.total == 0:
            return

        percentage = self.current / self.total
        filled = int(self.width * percentage)

        bar = colorize("█" * filled, Color.GREEN) + colorize("░" * (self.width - filled), Color.DIM)
        label_str = f"{self.label:<20}" if self.label else ""
        elapsed = time.time() - self.start_time

        eta = ""
        if self.current > 0 and self.current < self.total:
            rate = self.current / elapsed
            remaining = (self.total - self.current) / rate
            eta = f" ETA: {remaining:.0f}s"

        line = f"\r{label_str}[{bar}] {self.current}/{self.total}{eta}"
        sys.stdout.write(line)
        sys.stdout.flush()

        if self.current >= self.total:
            print()  # New line when complete


class Spinner:
    """Animated spinner for long-running tasks."""

    SPINNERS = {
        "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        "line": ["-", "\\", "|", "/"],
        "arrow": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
        "star": ["✶", "✸", "✹", "✺", "✹", "✷"],
    }

    def __init__(self, label: str, spinner_type: str = "dots", delay: float = 0.1):
        """Initialize spinner."""
        self.label = label
        self.spinner_type = spinner_type
        self.delay = delay
        self.active = False
        self.index = 0

    def start(self) -> None:
        """Start the spinner."""
        self.active = True
        self.index = 0
        self._draw()

    def stop(self, final_message: str = "") -> None:
        """Stop the spinner."""
        self.active = False
        if final_message:
            sys.stdout.write(f"\r{final_message}\n")
        else:
            sys.stdout.write("\r" + " " * (len(self.label) + 15) + "\r")
        sys.stdout.flush()

    def _draw(self) -> None:
        """Draw one frame of the spinner."""
        if not self.active:
            return

        frames = self.SPINNERS.get(self.spinner_type, self.SPINNERS["dots"])
        frame = frames[self.index % len(frames)]
        sys.stdout.write(f"\r{colorize(frame, Color.CYAN)} {self.label}")
        sys.stdout.flush()

        self.index += 1
        sys.stdout.flush()


class Menu:
    """Interactive menu."""

    @staticmethod
    def select(title: str, options: List[str], default_index: int = 0) -> int:
        """Show a selection menu."""
        print(f"\n{bold(title)}")
        print()

        for i, option in enumerate(options):
            prefix = "→ " if i == default_index else "  "
            print(f"{colorize(prefix, Color.CYAN)}{i+1}. {option}")

        print()
        while True:
            try:
                prompt_text = f"Choose option [1-{len(options)}]: "
                choice = input(colorize(prompt_text, Color.BRIGHT_CYAN))
                index = int(choice) - 1
                if 0 <= index < len(options):
                    return index
            except ValueError:
                pass
            print(colorize("Invalid choice. Try again.", Color.RED))

    @staticmethod
    def confirm(prompt: str, default: bool = True) -> bool:
        """Show a confirmation prompt."""
        default_str = "[Y/n]" if default else "[y/N]"
        prompt_str = f"{prompt} {colorize(default_str, Color.BRIGHT_YELLOW)}: "

        response = input(prompt_str).strip().lower()

        if not response:
            return default

        return response in ("y", "yes")

    @staticmethod
    def input_text(prompt: str, default: str = "") -> str:
        """Get user text input."""
        default_str = f" [{default}]" if default else ""
        prompt_str = f"{colorize(prompt + default_str + ': ', Color.BRIGHT_CYAN)}"

        response = input(prompt_str).strip()
        return response if response else default


class Table:
    """Simple ASCII table."""

    def __init__(self, headers: List[str], title: Optional[str] = None):
        """Initialize table."""
        self.headers = headers
        self.rows: List[tuple] = []
        self.title = title

    def add_row(self, *values) -> None:
        """Add a row to the table."""
        self.rows.append(values)

    def print(self) -> None:
        """Print the table."""
        if not self.rows:
            return

        # Calculate column widths
        widths = [len(h) for h in self.headers]
        for row in self.rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(str(val)))

        # Print title if provided
        if self.title:
            total_width = sum(widths) + (len(self.headers) * 3) + 1
            print(f"\n{bold(self.title)}")

        # Print header
        header_row = " | ".join(
            colorize(h.center(w), Color.CYAN) for h, w in zip(self.headers, widths)
        )
        print(f" {header_row} ")

        # Print separator
        separator = "-" * (sum(widths) + (len(self.headers) * 3) + 1)
        print(colorize(separator, Color.DIM))

        # Print rows
        for row in self.rows:
            row_str = " | ".join(str(v).ljust(w) for v, w in zip(row, widths))
            print(f" {row_str} ")


def print_header(text: str, subtitle: str = "") -> None:
    """Print a fancy header."""
    width = max(len(text), len(subtitle)) + 4

    print()
    print(colorize(Icon.BOX_TL + Icon.BOX_H * (width - 2) + Icon.BOX_TR, Color.BRIGHT_MAGENTA))
    print(
        colorize(Icon.BOX_V, Color.BRIGHT_MAGENTA)
        + f" {bold(text.center(width-4))} "
        + colorize(Icon.BOX_V, Color.BRIGHT_MAGENTA)
    )

    if subtitle:
        print(
            colorize(Icon.BOX_V, Color.BRIGHT_MAGENTA)
            + f" {dim(subtitle.center(width-4))} "
            + colorize(Icon.BOX_V, Color.BRIGHT_MAGENTA)
        )

    print(colorize(Icon.BOX_BL + Icon.BOX_H * (width - 2) + Icon.BOX_BR, Color.BRIGHT_MAGENTA))
    print()


def print_footer() -> None:
    """Print a fancy footer."""
    footer_text = f"{Icon.SPARKLES} All done! {Icon.TADA}"
    print()
    print(colorize(f"{Icon.BOX_H * (len(footer_text) + 4)}", Color.DIM))
    print(f"  {colorize(footer_text, Color.GREEN)}")
    print(colorize(f"{Icon.BOX_H * (len(footer_text) + 4)}", Color.DIM))
    print()


def format_stats(title: str, stats: Dict[str, int]) -> str:
    """Format statistics in a nice way."""
    lines = [f"\n{bold(title)}"]

    total = sum(stats.values())
    for key, value in stats.items():
        percentage = (value / total * 100) if total > 0 else 0
        bar_width = int(percentage / 5)
        bar = colorize("█" * bar_width, Color.GREEN)
        lines.append(f"  {key:<15} {value:>5} ({percentage:>5.1f}%) {bar}")

    return "\n".join(lines)


def main():
    """Demo of CLI UI components."""
    print_header("Metadata Enrichment", "🎵 Making your library complete")

    # Demo info message
    print(info("Starting metadata enrichment process..."))
    print()

    # Demo progress bar
    print("Processing tracks...")
    prog = ProgressBar(10, "Tracks")
    for i in range(10):
        time.sleep(0.1)
        prog.update()

    # Demo menu
    print()
    choice = Menu.select("Select a database", ["Discogs", "Last.fm", "MusicBrainz", "Wikidata"])
    databases = ["Discogs", "Last.fm", "MusicBrainz", "Wikidata"]
    print(success(f"Selected: {databases[choice]}"))

    # Demo confirm
    print()
    if Menu.confirm("Continue with enrichment?"):
        print(success("Continuing..."))

    # Demo table
    print()
    table = Table(["Field", "Source", "Value", "Confidence"], title="Enriched Fields")
    table.add_row("Genre", "Discogs", "Electronic", "0.95")
    table.add_row("Year", "MusicBrainz", "2020", "0.98")
    table.add_row("BPM", "AcousticBrainz", "128", "0.87")
    table.print()

    # Demo stats
    stats = {"Enriched": 45, "Skipped": 5, "Errors": 0}
    print(format_stats("Summary", stats))

    print_footer()


if __name__ == "__main__":
    main()
