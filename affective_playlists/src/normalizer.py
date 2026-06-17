"""
Core text normalization utilities for all subprojects.

Handles lowercase conversion, whitespace trimming, deduplication, and special character normalization.
Used by: plsort, 4tempers, metad_enr
"""

import re
from typing import Dict, List, Optional, Set


class TextNormalizer:
    """Normalize text fields for consistent comparison."""

    def __init__(
        self,
        lowercase: bool = True,
        trim: bool = True,
        dedupe: bool = True,
        normalize_chars: bool = True,
    ):
        """
        Initialize text normalizer.

        Args:
            lowercase: Convert text to lowercase
            trim: Remove leading/trailing whitespace
            dedupe: Remove duplicate entries
            normalize_chars: Normalize special characters
        """
        self.lowercase = lowercase
        self.trim = trim
        self.dedupe = dedupe
        self.normalize_chars = normalize_chars

    def normalize(self, text: str) -> str:
        """Normalize a single text string."""
        if not text:
            return ""

        if self.lowercase:
            text = text.lower()

        if self.normalize_chars:
            # Normalize special characters
            text = re.sub(r"[&]", "and", text)
            text = re.sub(r"[^\w\s-]", "", text)
            text = re.sub(r"[-]+", "-", text)

        if self.trim:
            text = text.strip()
            text = re.sub(r"\s+", " ", text)

        return text

    def normalize_list(self, items: List[str]) -> List[str]:
        """Normalize a list of strings and optionally deduplicate."""
        normalized = [self.normalize(item) for item in items if item]

        if self.dedupe:
            seen: Set[str] = set()
            unique = []
            for item in normalized:
                if item and item not in seen:
                    seen.add(item)
                    unique.append(item)
            return unique

        return normalized

    def normalize_dict_values(self, d: dict, keys: Optional[List[str]] = None) -> dict:
        """Normalize specific dictionary values."""
        result = d.copy()
        keys_to_normalize = keys if keys else [k for k, v in d.items() if isinstance(v, str)]

        for key in keys_to_normalize:
            if key in result and isinstance(result[key], str):
                result[key] = self.normalize(result[key])

        return result
