from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.genre_groups import canonical_genre_label, display_genre_label


FAV_ROOT_FOLDER = "Fav Songs"


class AssignmentType(Enum):
    FAV_TRACK = "fav_track"


class AssignmentSource(Enum):
    AUTO = "auto"
    MANUAL = "manual"


def normalize_genre_label(genre: str) -> str:
    return display_genre_label(genre)


def normalize_fav_genre_label(genre: str) -> str:
    return canonical_genre_label(genre)


def fav_playlist_name(genre: str) -> str:
    return f"♥ {normalize_fav_genre_label(genre)}"


@dataclass(frozen=True)
class CurationAssignment:
    item_type: AssignmentType
    item_id: str
    item_name: str
    genre: str
    source: AssignmentSource
    confidence: float
    manual_override: bool = False

    def target_path(self) -> list[str]:
        return [FAV_ROOT_FOLDER, fav_playlist_name(self.genre)]

    def to_dict(self) -> dict[str, Any]:
        genre_label = normalize_fav_genre_label(self.genre)
        result = {
            "item_type": self.item_type.value,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "genre": self.genre,
            "genre_label": genre_label,
            "source": self.source.value,
            "confidence": round(self.confidence, 4),
            "manual_override": self.manual_override,
            "target_path": self.target_path(),
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurationAssignment:
        return cls(
            item_type=AssignmentType(data["item_type"]),
            item_id=data["item_id"],
            item_name=data["item_name"],
            genre=data["genre"],
            source=AssignmentSource(data["source"]),
            confidence=float(data["confidence"]),
            manual_override=bool(data.get("manual_override", False)),
        )
