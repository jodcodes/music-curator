from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.genre_groups import canonical_genre_label, display_genre_label


FAV_ROOT_FOLDER = "Fav Songs"
TEMPERS_ROOT_FOLDER = "4 Tempers"


class TemperBucket(Enum):
    WOE = "Woe"
    FROLIC = "Frolic"
    DREAD = "Dread"
    MALICE = "Malice"


class AssignmentType(Enum):
    PLAYLIST = "playlist"
    FAV_TRACK = "fav_track"
    TEMPER_TRACK = "temper_track"


class AssignmentSource(Enum):
    AUTO = "auto"
    MANUAL = "manual"


def normalize_genre_label(genre: str) -> str:
    return display_genre_label(genre)


def normalize_fav_genre_label(genre: str) -> str:
    return canonical_genre_label(genre)


def fav_playlist_name(genre: str, temperament: TemperBucket) -> str:
    return f"Fav {normalize_fav_genre_label(genre)} {temperament.value}"


def temper_playlist_name(genre: str, temperament: TemperBucket) -> str:
    return f"{normalize_fav_genre_label(genre)} {temperament.value}"


@dataclass(frozen=True)
class CurationAssignment:
    item_type: AssignmentType
    item_id: str
    item_name: str
    genre: str
    temperament: TemperBucket
    source: AssignmentSource
    confidence: float
    manual_override: bool = False

    def target_path(self) -> list[str]:
        if self.item_type == AssignmentType.FAV_TRACK:
            genre_label = normalize_fav_genre_label(self.genre)
            return [
                FAV_ROOT_FOLDER,
                genre_label,
            ]
        genre_label = normalize_fav_genre_label(self.genre)
        if self.item_type == AssignmentType.TEMPER_TRACK:
            return [
                TEMPERS_ROOT_FOLDER,
                temper_playlist_name(self.genre, self.temperament),
            ]
        return [TEMPERS_ROOT_FOLDER, temper_playlist_name(self.genre, self.temperament)]

    def to_dict(self) -> dict[str, Any]:
        genre_label = normalize_fav_genre_label(self.genre)
        return {
            "item_type": self.item_type.value,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "genre": self.genre,
            "genre_label": genre_label,
            "temperament": self.temperament.value,
            "source": self.source.value,
            "confidence": round(self.confidence, 4),
            "manual_override": self.manual_override,
            "target_path": self.target_path(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurationAssignment:
        return cls(
            item_type=AssignmentType(data["item_type"]),
            item_id=data["item_id"],
            item_name=data["item_name"],
            genre=data["genre"],
            temperament=TemperBucket(data["temperament"]),
            source=AssignmentSource(data["source"]),
            confidence=float(data["confidence"]),
            manual_override=bool(data.get("manual_override", False)),
        )
