from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config" / "genre_groups.json"


@lru_cache(maxsize=1)
def load_genre_patterns() -> List[dict]:
    """Load genre group patterns from the shared JSON config file (cached)."""
    with open(_CONFIG_PATH) as f:
        return json.load(f)


def display_genre_label(genre: str) -> str:
    parts = genre.replace("_", " ").replace("-", " ").strip().split()
    if not parts:
        return "Other"
    return " ".join(part.capitalize() for part in parts)


def _genre_search_text(genre: str) -> str:
    text = genre.replace("_", " ").replace("-", " ").strip().lower()
    return re.sub(r"\s+", " ", text)


def canonical_genre_label(genre: str) -> str:
    text = _genre_search_text(genre)
    if not text:
        return "Sonstige"

    for entry in load_genre_patterns():
        if re.search(entry["pattern"], text):
            return entry["label"]
    if text in {"other", "sonstige"}:
        return "Sonstige"
    return "Sonstige"
