"""
Deterministic identity helpers for tracks and playlists.
"""

from __future__ import annotations

import os
from typing import Optional


def normalize_text(value: Optional[str]) -> str:
    return " ".join(str(value or "").strip().lower().split())


def build_track_key(
    artist: Optional[str] = None,
    title: Optional[str] = None,
    album: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    filepath: Optional[str] = None,
) -> str:
    if filepath:
        return f"path:{os.path.abspath(os.path.expanduser(filepath))}"

    album_norm = normalize_text(album)
    artist_norm = normalize_text(artist)
    title_norm = normalize_text(title)
    duration = "" if duration_seconds is None else str(duration_seconds)
    return f"track:{artist_norm}|{title_norm}|{album_norm}|{duration}"
