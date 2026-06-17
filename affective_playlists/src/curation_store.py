from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.curation_models import AssignmentType, CurationAssignment


class CurationStore:
    def __init__(self, path: Path | str = "data/curation/assignments.json"):
        self.path = Path(path)

    def _key(self, item_type: AssignmentType, item_id: str) -> str:
        return f"{item_type.value}:{item_id}"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        with self.path.open() as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {}

        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        tmp_path.replace(self.path)

    def save_override(self, assignment: CurationAssignment) -> None:
        data = self._load()
        data[self._key(assignment.item_type, assignment.item_id)] = assignment.to_dict()
        self._save(data)

    def get_override(
        self, item_type: AssignmentType, item_id: str
    ) -> CurationAssignment | None:
        payload = self._load().get(self._key(item_type, item_id))
        if payload is None:
            return None
        return CurationAssignment.from_dict(payload)

    def apply_overrides(
        self, assignments: list[CurationAssignment]
    ) -> list[CurationAssignment]:
        data = self._load()
        merged: list[CurationAssignment] = []
        for assignment in assignments:
            payload = data.get(self._key(assignment.item_type, assignment.item_id))
            if payload is None:
                merged.append(assignment)
                continue
            merged.append(CurationAssignment.from_dict(payload))
        return merged
