from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class CurationSnapshotStore:
    def __init__(
        self,
        path: Optional[Path] = None,
        ttl_seconds: int = 3600,
    ) -> None:
        self.path = Path(path) if path is not None else Path("data/curation_snapshots.json")
        self.ttl_seconds = ttl_seconds

    def save_snapshot(self, scope: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        snapshots = self._read_all()
        snapshot = {
            **payload,
            "scope": scope,
            "available": True,
            "fresh": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshots[scope] = snapshot
        self._write_all(snapshots)
        return snapshot

    def load_snapshot(self, scope: str) -> Dict[str, Any]:
        snapshot = self._read_all().get(scope)
        if not isinstance(snapshot, dict):
            return self._empty_snapshot(scope)

        loaded = dict(snapshot)
        loaded["scope"] = scope
        loaded["available"] = True
        loaded["fresh"] = self._is_fresh(loaded.get("created_at"))
        return loaded

    def _read_all(self) -> Dict[str, Dict[str, Any]]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}
        return data

    def _write_all(self, snapshots: Dict[str, Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                json.dump(snapshots, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temp_name, self.path)
        finally:
            if temp_name:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass

    def _is_fresh(self, created_at: Any) -> bool:
        if not isinstance(created_at, str):
            return False
        try:
            created = datetime.fromisoformat(created_at)
        except ValueError:
            return False
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - created.astimezone(timezone.utc)
        return age.total_seconds() <= self.ttl_seconds

    def _empty_snapshot(self, scope: str) -> Dict[str, Any]:
        return {
            "scope": scope,
            "available": False,
            "fresh": False,
            "created_at": None,
            "total_assignments": 0,
            "total_genres": 0,
            "total_changes": 0,
            "total_skipped": 0,
            "grouped": {},
            "changes": [],
            "skipped_tracks": [],
        }
