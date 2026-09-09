from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.apple_music import AppleMusicInterface
from src.apple_music_structure import (
    AppleMusicChange,
    AppleMusicStructureApplier,
    AppleMusicStructurePlanner,
)
from src.curation_models import (
    AssignmentSource,
    AssignmentType,
    CurationAssignment,
)
from src.curation_snapshot import CurationSnapshotStore
from src.curation_store import CurationStore
class CurationService:
    def __init__(
        self,
        apple_music: Optional[AppleMusicInterface] = None,
        store: Optional[CurationStore] = None,
        snapshot_store: Optional[CurationSnapshotStore] = None,
        planner: Optional[AppleMusicStructurePlanner] = None,
        applier: Optional[AppleMusicStructureApplier] = None,
        **_ignored: Any,
    ) -> None:
        self.apple_music = apple_music or AppleMusicInterface()
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
                    source=AssignmentSource.AUTO,
                    confidence=0.75,
                )
            )

        assignments = self.store.apply_overrides(assignments)
        changes = self.planner.plan_fav_tracks(assignments)
        desired_track_ids = [assignment.item_id for assignment in assignments]
        existing_tracks = self._get_generated_fav_song_tracks()
        stale_changes = self.planner.plan_stale_fav_track_removals(
            existing_tracks, desired_track_ids
        )
        changes.extend(stale_changes)

        assignment_dicts = [assignment.to_dict() for assignment in assignments]
        grouped = self._group_fav_assignments(assignment_dicts)

        return {
            "assignments": assignment_dicts,
            "grouped": grouped,
            "changes": [change.to_dict() for change in changes],
            "total_assignments": len(assignments),
            "total_changes": len(changes),
            "skipped_tracks": skipped_tracks,
            "total_skipped": len(skipped_tracks),
        }

    def _get_generated_fav_song_tracks(self) -> List[Dict[str, Any]]:
        getter = getattr(self.apple_music, "get_generated_fav_song_tracks", None)
        if type(self.apple_music) is not AppleMusicInterface:
            return [] if getter is None else list(getter())
        return self.apple_music.get_generated_fav_song_tracks()

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

    def _group_fav_assignments(
        self, assignments: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for assignment in assignments:
            genre = str(assignment.get("genre_label") or "Other")
            grouped.setdefault(genre, []).append(assignment)
        return grouped

    def apply_fav_songs(
        self,
        confirmed: bool,
        max_tracks: Optional[int] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        if max_tracks is not None and max_tracks < 1:
            raise ValueError("max_tracks must be a positive integer")
        if offset < 0:
            raise ValueError("offset must be zero or positive")

        preview = self.preview_fav_songs()
        return self._apply_fav_songs_preview(
            preview,
            confirmed=confirmed,
            max_tracks=max_tracks,
            offset=offset,
        )

    def _apply_fav_songs_preview(
        self,
        preview: Dict[str, Any],
        confirmed: bool,
        max_tracks: Optional[int] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        preview_changes = list(preview["changes"])
        assignment_dicts = list(preview["assignments"])
        if offset:
            assignment_dicts = assignment_dicts[offset:]
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
            "grouped": self._group_fav_assignments(assignment_dicts),
            "changes": [change.to_dict() for change in changes],
            "total_assignments": len(assignments),
            "total_changes": len(changes),
        }
        if offset:
            preview["offset"] = offset
        if max_tracks is not None:
            preview["max_tracks"] = max_tracks
        else:
            remove_changes = [
                AppleMusicChange(
                    str(change["action"]),
                    list(change["path"]),
                    str(change["description"]),
                )
                for change in preview_changes
                if change.get("action") == "remove_track"
            ]
            changes.extend(remove_changes)
            preview["changes"] = [change.to_dict() for change in changes]
            preview["total_changes"] = len(changes)

        result = self.applier.apply_changes(changes, confirmed=confirmed)
        result["preview"] = preview
        return result

    def apply_fav_songs_bulk(
        self,
        confirmed: bool,
        offset: int = 0,
        max_tracks: Optional[int] = None,
    ) -> Dict[str, Any]:
        if offset < 0:
            raise ValueError("offset must be zero or positive")
        if max_tracks is not None and max_tracks < 1:
            raise ValueError("max_tracks must be a positive integer")

        preview = self.preview_fav_songs()
        assignment_dicts = list(preview["assignments"])
        if offset:
            assignment_dicts = assignment_dicts[offset:]
        if max_tracks is not None:
            assignment_dicts = assignment_dicts[:max_tracks]
        assignments = [CurationAssignment.from_dict(item) for item in assignment_dicts]
        result = self.applier.apply_fav_tracks_bulk(assignments, confirmed=confirmed)
        if result.get("success") and offset == 0 and max_tracks is None:
            remove_changes = [
                AppleMusicChange(
                    str(change["action"]),
                    list(change["path"]),
                    str(change["description"]),
                )
                for change in preview["changes"]
                if change.get("action") == "remove_track"
            ]
            if remove_changes:
                removal_result = self.applier.apply_changes(
                    remove_changes, confirmed=confirmed
                )
                result["stale_removal"] = removal_result
                result["success"] = bool(removal_result.get("success"))
                result["applied"] = int(result.get("applied") or 0) + int(
                    removal_result.get("applied") or 0
                )
                result["failed"] = int(result.get("failed") or 0) + int(
                    removal_result.get("failed") or 0
                )
        result["preview"] = {
            **preview,
            "assignments": assignment_dicts,
            "total_assignments": len(assignments),
            "offset": offset,
            "max_tracks": max_tracks,
        }
        return result

    def apply_fav_songs_batched(
        self,
        confirmed: bool,
        batch_size: int,
        offset: int = 0,
        max_tracks: Optional[int] = None,
    ) -> Dict[str, Any]:
        if batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if offset < 0:
            raise ValueError("offset must be zero or positive")
        if max_tracks is not None and max_tracks < 1:
            raise ValueError("max_tracks must be a positive integer")

        preview = self.preview_fav_songs()
        total_available = len(preview["assignments"])
        remaining = total_available - offset
        if max_tracks is not None:
            remaining = min(remaining, max_tracks)
        remaining = max(0, remaining)

        batches: List[Dict[str, Any]] = []
        applied = 0
        failed = 0
        current_offset = offset
        processed = 0

        while processed < remaining:
            current_size = min(batch_size, remaining - processed)
            result = self._apply_fav_songs_preview(
                preview,
                confirmed=confirmed,
                max_tracks=current_size,
                offset=current_offset,
            )
            batch = {
                "offset": current_offset,
                "limit": current_size,
                "success": bool(result.get("success")),
                "applied": int(result.get("applied") or 0),
                "failed": int(result.get("failed") or 0),
            }
            batches.append(batch)
            applied += batch["applied"]
            failed += batch["failed"]
            if not batch["success"]:
                return {
                    "success": False,
                    "applied": applied,
                    "failed": failed,
                    "processed_tracks": processed,
                    "total_available": total_available,
                    "batches": batches,
                    "error": "Batch failed",
                    "failed_result": result,
                }
            processed += current_size
            current_offset += current_size

        return {
            "success": True,
            "applied": applied,
            "failed": failed,
            "processed_tracks": processed,
            "total_available": total_available,
            "batches": batches,
        }
