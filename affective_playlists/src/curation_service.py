from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.apple_music import AppleMusicInterface
from src.apple_music_structure import (
    AppleMusicStructureApplier,
    AppleMusicStructurePlanner,
)
from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
    TemperBucket,
)
from src.curation_snapshot import CurationSnapshotStore
from src.curation_store import CurationStore


class KeywordTemperClassifier:
    def classify_track(self, track: Dict[str, Any]) -> TemperBucket:
        text = " ".join(
            str(track.get(field) or "")
            for field in ("name", "title", "artist", "genre")
        ).lower()

        if any(
            keyword in text
            for keyword in ("dark", "dread", "night", "bass", "industrial")
        ):
            return TemperBucket.DREAD
        if any(
            keyword in text for keyword in ("sad", "lonely", "melancholy", "blue")
        ):
            return TemperBucket.WOE
        if any(
            keyword in text for keyword in ("rage", "hard", "aggressive", "drill")
        ):
            return TemperBucket.MALICE
        return TemperBucket.FROLIC


class CurationService:
    def __init__(
        self,
        apple_music: Optional[AppleMusicInterface] = None,
        temper_classifier: Optional[KeywordTemperClassifier] = None,
        store: Optional[CurationStore] = None,
        snapshot_store: Optional[CurationSnapshotStore] = None,
        planner: Optional[AppleMusicStructurePlanner] = None,
        applier: Optional[AppleMusicStructureApplier] = None,
    ) -> None:
        self.apple_music = apple_music or AppleMusicInterface()
        self.temper_classifier = temper_classifier or KeywordTemperClassifier()
        self.store = store or CurationStore()
        self.snapshot_store = snapshot_store or CurationSnapshotStore()
        self.planner = planner or AppleMusicStructurePlanner()
        self.applier = applier or AppleMusicStructureApplier()

    def preview_fav_songs(self) -> Dict[str, Any]:
        tracks = self.apple_music.get_favourite_tracks()
        assignments: List[CurationAssignment] = []
        skipped_tracks: List[Dict[str, str]] = []

        for track in tracks:
            item_id = str(track.get("persistent_id") or track.get("id") or "").strip()
            item_name = str(track.get("name") or track.get("title") or "Unknown Track")
            if not item_id:
                skipped_tracks.append(
                    {
                        "name": item_name,
                        "artist": str(track.get("artist") or ""),
                        "genre": str(track.get("genre") or ""),
                        "reason": "missing_stable_id",
                    }
                )
                continue

            raw_genre = str(track.get("genre") or "other").strip() or "other"
            assignments.append(
                CurationAssignment(
                    item_type=AssignmentType.FAV_TRACK,
                    item_id=item_id,
                    item_name=item_name,
                    genre=raw_genre.lower().replace(" ", "_"),
                    temperament=self.temper_classifier.classify_track(track),
                    source=AssignmentSource.AUTO,
                    confidence=0.75,
                )
            )

        assignments = self.store.apply_overrides(assignments)
        changes = self.planner.plan_fav_tracks(assignments)

        assignment_dicts = [assignment.to_dict() for assignment in assignments]
        grouped = self._group_assignments(assignment_dicts)

        return {
            "assignments": assignment_dicts,
            "grouped": grouped,
            "changes": [change.to_dict() for change in changes],
            "total_assignments": len(assignments),
            "total_changes": len(changes),
            "skipped_tracks": skipped_tracks,
            "total_skipped": len(skipped_tracks),
        }

    def get_fav_songs_snapshot(self) -> Dict[str, Any]:
        return self.snapshot_store.load_snapshot("fav_songs")

    def refresh_fav_songs_snapshot(self) -> Dict[str, Any]:
        preview = self.preview_fav_songs()
        payload = self._snapshot_payload(preview)
        return self.snapshot_store.save_snapshot("fav_songs", payload)

    def run_fav_songs_smoke_test(self) -> Dict[str, Any]:
        tracks = self.apple_music.get_favourite_tracks()
        for track in tracks:
            track_id = str(track.get("persistent_id") or track.get("id") or "").strip()
            if not track_id:
                continue

            result = self.applier.run_smoke_test(track_id)
            result["source_track"] = {
                "persistent_id": track_id,
                "name": str(track.get("name") or track.get("title") or "Unknown Track"),
                "artist": str(track.get("artist") or ""),
            }
            return result

        return {
            "success": False,
            "error": "No Favourite Songs track with a stable persistent ID was found",
            "copied": 0,
            "duplicate_skipped": False,
            "leftovers": {},
        }

    def _snapshot_payload(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        grouped = preview.get("grouped") or {}
        changes = preview.get("changes") or []
        skipped_tracks = preview.get("skipped_tracks") or []
        return {
            "scope": "fav_songs",
            "total_assignments": int(preview.get("total_assignments") or 0),
            "total_genres": len(grouped),
            "total_changes": int(
                preview["total_changes"]
                if "total_changes" in preview
                else len(changes)
            ),
            "total_skipped": int(
                preview["total_skipped"]
                if "total_skipped" in preview
                else len(skipped_tracks)
            ),
            "grouped": grouped,
            "changes": changes,
            "skipped_tracks": skipped_tracks,
        }

    def _group_assignments(
        self, assignments: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for assignment in assignments:
            genre = str(assignment.get("genre_label") or "Other")
            temperament = str(assignment.get("temperament") or TemperBucket.FROLIC.value)
            grouped.setdefault(
                genre,
                {temper.value: [] for temper in TemperBucket},
            )
            grouped[genre].setdefault(temperament, []).append(assignment)
        return grouped

    def apply_fav_songs(
        self, confirmed: bool, max_tracks: Optional[int] = None
    ) -> Dict[str, Any]:
        if max_tracks is not None and max_tracks < 1:
            raise ValueError("max_tracks must be a positive integer")

        preview = self.preview_fav_songs()
        assignment_dicts = list(preview["assignments"])
        if max_tracks is not None:
            assignment_dicts = assignment_dicts[:max_tracks]

        assignments = [
            CurationAssignment.from_dict(assignment)
            for assignment in assignment_dicts
        ]
        changes = self.planner.plan_fav_tracks(assignments)
        preview = {
            **preview,
            "assignments": assignment_dicts,
            "grouped": self._group_assignments(assignment_dicts),
            "changes": [change.to_dict() for change in changes],
            "total_assignments": len(assignments),
            "total_changes": len(changes),
        }
        if max_tracks is not None:
            preview["max_tracks"] = max_tracks

        result = self.applier.apply_changes(changes, confirmed=confirmed)
        result["preview"] = preview
        return result
