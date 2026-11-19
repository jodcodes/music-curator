from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
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
from src.playlist_sizing import balanced_parts
from src.seed_playlist import rank_seed_candidates


def _split_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _split_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{16}", value):
        raise ValueError("Invalid persistent ID")
    return value.upper()


def _split_source(source_id: str, name: str, tracks: list[str], reason: Optional[str] = None) -> dict:
    reason = reason or ("within_limit" if len(tracks) <= 100 else None)
    return {
        "source_id": source_id,
        "source_name": name,
        "track_ids": tracks,
        "skip_reason": reason,
        "parts": [] if reason else [
            {"name": f"{name} · {index:02d}", "track_ids": part}
            for index, part in enumerate(balanced_parts(tracks), start=1)
        ],
    }


def _validate_split_plan(plan: Any) -> None:
    if not isinstance(plan, dict) or set(plan) != {"version", "sources", "fingerprint"}:
        raise ValueError("Invalid split plan")
    if type(plan["version"]) is not int or plan["version"] != 1 or not isinstance(plan["sources"], list):
        raise ValueError("Invalid split plan version or sources")
    seen = set()
    for source in plan["sources"]:
        if not isinstance(source, dict) or set(source) != {"source_id", "source_name", "track_ids", "skip_reason", "parts"}:
            raise ValueError("Invalid source plan")
        source_id, name, tracks, reason = (source[key] for key in ("source_id", "source_name", "track_ids", "skip_reason"))
        if not isinstance(source_id, str) or source_id in seen or not isinstance(name, str) or not isinstance(tracks, list):
            raise ValueError("Invalid source inputs")
        seen.add(source_id)
        if reason not in (None, "within_limit", "invalid_source_id", "source_unreadable", "invalid_membership", "invalid_source_name"):
            raise ValueError("Invalid source skip")
        if reason not in ("invalid_source_id", "source_unreadable", "invalid_membership", "invalid_source_name"):
            if _split_id(source_id) != source_id or any(_split_id(item) != item for item in tracks):
                raise ValueError("Noncanonical source IDs")
            if not name.strip() or any(ord(char) < 32 or ord(char) == 127 for char in name):
                raise ValueError("Invalid source name")
            expected = _split_source(source_id, name, tracks)
        else:
            expected = _split_source(source_id, "", [], reason)
        if source != expected:
            raise ValueError("Split membership or names differ from deterministic plan")
    payload = {key: plan[key] for key in ("version", "sources")}
    if plan["fingerprint"] != _split_digest(payload):
        raise ValueError("Split plan fingerprint mismatch")


def _seed_records(tracks: Any, *, unique: bool = False) -> list[dict]:
    if not isinstance(tracks, list):
        raise ValueError("Invalid track records")
    records, seen = [], set()
    for track in tracks:
        if not isinstance(track, dict):
            raise ValueError("Invalid track metadata")
        pid = _split_id(track.get("persistent_id"))
        title = track.get("title") or track.get("name")
        if not isinstance(title, str) or not title.strip() or not isinstance(track.get("artist"), str):
            raise ValueError("Missing track title or artist metadata")
        if unique and pid in seen:
            raise ValueError("Ambiguous library track ID")
        seen.add(pid)
        records.append({**track, "persistent_id": pid})
    if records:
        # Reuse the ranker's JSON-native boundary before making a detached copy.
        rank_seed_candidates(records[0], records, limit=1)
    return json.loads(json.dumps(records, allow_nan=False))


def _seed_plan(source: dict, seed_id: str, candidates: list[dict], limit: int) -> dict:
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("limit must be an integer from 1 to 30")
    if not isinstance(source, dict) or set(source) != {"source_id", "source_name", "track_ids", "tracks"}:
        raise ValueError("Invalid seed source")
    source_id, seed_id = _split_id(source["source_id"]), _split_id(seed_id)
    if not isinstance(source["source_name"], str) or not source["source_name"].strip():
        raise ValueError("Invalid source name")
    source_tracks = _seed_records(source["tracks"])
    membership = [track["persistent_id"] for track in source_tracks]
    if source["track_ids"] != membership:
        raise ValueError("Source membership mismatch")
    selected = [track for track in source_tracks if track["persistent_id"] == seed_id]
    if not selected or any(track != selected[0] for track in selected):
        raise ValueError("Seed is missing or has ambiguous source metadata")
    pool = sorted(_seed_records(candidates, unique=True), key=lambda track: track["persistent_id"])
    if not any(track["persistent_id"] == seed_id for track in pool):
        raise ValueError("Seed is missing from the existing library")
    ranked = rank_seed_candidates(selected[0], pool, limit=limit)
    title = selected[0].get("title") or selected[0]["name"]
    safe_title = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", title).split())
    plan = {
        "version": 1, "kind": "seed", "candidate_scope": "existing_library",
        "ranking_basis": "recorded_metadata_only", "limit": limit,
        "source": {"source_id": source_id, "source_name": source["source_name"],
                   "track_ids": membership, "tracks": source_tracks},
        "seed": selected[0], "candidates": pool, **ranked,
        "output": {"name": f"Seed · {safe_title}",
                   "track_ids": [track["persistent_id"] for track in ranked["tracks"]]},
    }
    return {**plan, "fingerprint": _split_digest(plan)}


def _validate_seed_plan(plan: Any) -> None:
    if not isinstance(plan, dict) or type(plan.get("version")) is not int:
        raise ValueError("Invalid seed plan")
    expected = _seed_plan(plan["source"], plan["seed"]["persistent_id"], plan["candidates"], plan["limit"])
    if plan != expected:
        raise ValueError("Seed plan differs from deterministic inputs/results")


def _plan_sources(plan: dict) -> list[dict]:
    return [plan["source"]] if plan.get("kind") == "seed" else plan["sources"]


def _plan_parts(plan: dict) -> list[tuple[dict, dict]]:
    if plan.get("kind") == "seed":
        return [(plan["source"], plan["output"])]
    return [(source, part) for source in plan["sources"] for part in source["parts"]]


class _SplitJournal:
    """Local POSIX journal; its permanent lock must never be replaced or reset."""

    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.mkdir(mode=0o700)  # Exclusive reservation, including interrupted first use.
        with (self.path / "lock").open("x") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        self.save({"version": 1, "plans": {}})
        self._sync_directory(self.path.parent)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def __enter__(self):
        self.lock = (self.path / "lock").open("r+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close()
            raise
        return self

    def __exit__(self, *_args):
        self.lock.close()

    def load(self) -> dict:
        with (self.path / "journal.json").open(encoding="utf-8") as handle:
            envelope = json.load(handle)
        if set(envelope) != {"payload", "checksum"} or envelope["checksum"] != _split_digest(envelope["payload"]):
            raise ValueError("Corrupt split journal")
        data = envelope["payload"]
        if set(data) != {"version", "plans"} or type(data["version"]) is not int or data["version"] != 1 or not isinstance(data["plans"], dict):
            raise ValueError("Invalid split journal")
        output_ids = set()
        source_ids = set()
        for fingerprint, entry in data["plans"].items():
            if set(entry) != {"plan", "parts"}:
                raise ValueError("Invalid journal entry")
            (_validate_seed_plan if entry["plan"].get("kind") == "seed" else _validate_split_plan)(entry["plan"])
            source_ids.update(source["source_id"] for source in _plan_sources(entry["plan"]))
            if fingerprint != entry["plan"]["fingerprint"]:
                raise ValueError("Journal plan mismatch")
            parts = [part for _, part in _plan_parts(entry["plan"])]
            if not isinstance(entry["parts"], list) or len(parts) != len(entry["parts"]):
                raise ValueError("Journal parts mismatch")
            for part, state in zip(parts, entry["parts"]):
                if set(state) != {"playlist_id", "confirmed_count", "pending"}:
                    raise ValueError("Invalid journal part")
                output_id, count, pending = (state[key] for key in ("playlist_id", "confirmed_count", "pending"))
                if type(count) is not int or not 0 <= count <= len(part["track_ids"]) or pending not in (None, "create", "add"):
                    raise ValueError("Invalid journal progress")
                if output_id is None:
                    if count or pending == "add":
                        raise ValueError("Journal progress without target")
                else:
                    if _split_id(output_id) != output_id or output_id in output_ids or pending == "create" or (pending == "add" and count == len(part["track_ids"])):
                        raise ValueError("Invalid journal target")
                    output_ids.add(output_id)
        if output_ids & source_ids:
            raise ValueError("Journal output aliases a source")
        return data

    def save(self, data: dict) -> None:
        temporary = ""
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path, delete=False) as handle:
                temporary = handle.name
                json.dump({"payload": data, "checksum": _split_digest(data)}, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path / "journal.json")
            self._sync_directory(self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


class CurationService:
    def __init__(
        self,
        apple_music: Optional[AppleMusicInterface] = None,
        store: Optional[CurationStore] = None,
        snapshot_store: Optional[CurationSnapshotStore] = None,
        planner: Optional[AppleMusicStructurePlanner] = None,
        applier: Optional[AppleMusicStructureApplier] = None,
        split_journal_path: Optional[Path] = None,
        **_ignored: Any,
    ) -> None:
        self.apple_music = apple_music or AppleMusicInterface()
        self.store = store or CurationStore()
        self.snapshot_store = snapshot_store or CurationSnapshotStore()
        self.planner = planner or AppleMusicStructurePlanner()
        self.applier = applier or AppleMusicStructureApplier()
        self.split_journal_path = (
            Path(split_journal_path).resolve() if split_journal_path is not None
            else Path(__file__).resolve().parent.parent / "data/curation/playlist_split_journal"
        )

    def initialize_playlist_split_journal(self) -> None:
        """Explicit local-only first-use provisioning; never reset an existing directory."""
        _SplitJournal(self.split_journal_path).initialize()

    def preview_playlist_splits(self, playlist_ids: list[str]) -> dict:
        """Read source IDs and ordered occurrences; perform no local or Music writes."""
        if not isinstance(playlist_ids, list) or any(not isinstance(item, str) for item in playlist_ids):
            raise ValueError("playlist_ids must be a list of strings")
        sources = []
        seen = set()
        for raw_id in playlist_ids:
            try:
                source_id = _split_id(raw_id)
            except ValueError:
                source_id = raw_id
            if source_id in seen:
                continue
            seen.add(source_id)
            try:
                _split_id(source_id)
            except ValueError:
                sources.append(_split_source(source_id, "", [], "invalid_source_id"))
                continue
            try:
                info = self.apple_music.get_playlist_info_by_id(source_id)
                tracks = self.apple_music.get_playlist_tracks_by_id(source_id)
                if _split_id(info["persistent_id"]) != source_id:
                    raise ValueError("Source ID mismatch")
            except Exception:
                sources.append(_split_source(source_id, "", [], "source_unreadable"))
                continue
            name = info.get("name")
            if not isinstance(name, str) or not name.strip() or any(ord(char) < 32 or ord(char) == 127 for char in name):
                sources.append(_split_source(source_id, "", [], "invalid_source_name"))
                continue
            try:
                track_ids = [_split_id(track["persistent_id"]) for track in tracks]
            except (TypeError, KeyError, ValueError):
                sources.append(_split_source(source_id, "", [], "invalid_membership"))
                continue
            sources.append(_split_source(source_id, name, track_ids))
        plan = {"version": 1, "sources": sources}
        return {**plan, "fingerprint": _split_digest(plan)}

    def apply_playlist_splits(self, plan: dict, confirmed: bool = False) -> dict:
        """Apply reviewed parts by ID, stopping on uncertain writes without retrying them."""
        return self._apply_playlist_plan(plan, confirmed, kind="split")

    def get_seed_playlist_sources(self) -> list[dict]:
        """Read eligible source IDs without collapsing duplicate names."""
        rows = self.apple_music.get_user_playlists_with_counts_strict()
        if not isinstance(rows, list):
            raise ValueError("Invalid source listing")
        seen, sources = set(), []
        for row in rows:
            pid = _split_id(row["persistent_id"])
            if (pid in seen or not isinstance(row["name"], str) or not row["name"].strip()
                    or type(row["track_count"]) is not int or row["track_count"] < 0):
                raise ValueError("Invalid source listing")
            seen.add(pid)
            sources.append({"persistent_id": pid, "name": row["name"], "track_count": row["track_count"]})
        return sources

    def get_seed_playlist_source_tracks(self, playlist_id: str) -> list[dict]:
        return _seed_records(self.apple_music.get_playlist_tracks_by_id(_split_id(playlist_id)))

    def preview_seed_playlist(self, playlist_id: str, seed_track_id: str, limit: int = 30) -> dict:
        """Read source/library metadata only; no journal provisioning or writes."""
        playlist_id, seed_track_id = _split_id(playlist_id), _split_id(seed_track_id)
        if type(limit) is not int or not 1 <= limit <= 30:
            raise ValueError("limit must be an integer from 1 to 30")
        if playlist_id not in {row["persistent_id"] for row in self.get_seed_playlist_sources()}:
            raise ValueError("Selected source is missing or ineligible")
        info = self.apple_music.get_playlist_info_by_id(playlist_id)
        if _split_id(info["persistent_id"]) != playlist_id:
            raise ValueError("Source ID mismatch")
        tracks = self.get_seed_playlist_source_tracks(playlist_id)
        source = {"source_id": playlist_id, "source_name": info["name"], "tracks": tracks,
                  "track_ids": [track["persistent_id"] for track in tracks]}
        return _seed_plan(source, seed_track_id, self.apple_music.get_library_tracks_strict(), limit)

    def apply_seed_playlist(self, plan: dict, confirmed: bool = False) -> dict:
        return self._apply_playlist_plan(plan, confirmed, kind="seed")

    def _apply_playlist_plan(self, plan: dict, confirmed: bool, *, kind: str) -> dict:
        result = {"success": False, "confirmed": confirmed is True, "parts": []}
        if confirmed is not True:
            return {**result, "error": "Explicit confirmation required"}
        try:
            if kind == "seed":
                _validate_seed_plan(plan)
            # Own a JSON copy so caller mutation cannot alter an in-flight apply.
            plan = json.loads(json.dumps(plan))
            (_validate_seed_plan if kind == "seed" else _validate_split_plan)(plan)
            planned_parts = [(source["source_id"], part) for source, part in _plan_parts(plan)]
            result["parts"] = [
                {"source_id": source_id, "name": part["name"], "playlist_id": None, "confirmed_count": 0, "status": "not_started"}
                for source_id, part in planned_parts
            ]
            with _SplitJournal(self.split_journal_path) as journal:
                data = journal.load()
                entry = data["plans"].get(plan["fingerprint"])
                if entry is not None:
                    if entry["plan"] != plan:
                        raise ValueError("Journal plan differs from submitted plan")
                    for (_, part), state, report in zip(planned_parts, entry["parts"], result["parts"]):
                        report.update(playlist_id=state["playlist_id"], confirmed_count=state["confirmed_count"])
                        report["status"] = (
                            "unresolved" if state["pending"] else
                            "complete" if state["confirmed_count"] == len(part["track_ids"]) else
                            "partial" if state["playlist_id"] else "not_started"
                        )
                unresolved = [
                    {"fingerprint": fingerprint, "playlist_id": state["playlist_id"], "confirmed_count": state["confirmed_count"], "action": state["pending"], "source_id": source["source_id"], "name": part["name"]}
                    for fingerprint, record in data["plans"].items()
                    for (source, part), state in zip(
                        _plan_parts(record["plan"]), record["parts"]
                    ) if state["pending"]
                ]
                if unresolved:
                    result["unresolved"] = unresolved
                    raise ValueError("Unresolved write intent; manual recovery required")
                fresh = (self.preview_seed_playlist(plan["source"]["source_id"], plan["seed"]["persistent_id"], plan["limit"])
                         if kind == "seed" else self.preview_playlist_splits([source["source_id"] for source in plan["sources"]]))
                if fresh != plan:
                    raise ValueError("Source changed or plan was modified; preview again")
                known_ids = {state["playlist_id"] for record in data["plans"].values() for state in record["parts"] if state["playlist_id"]}
                if known_ids & {source["source_id"] for source in _plan_sources(plan)}:
                    raise ValueError("Selected source is a recorded split output; journal unchanged")
                if entry is None:
                    entry = {"plan": plan, "parts": [{"playlist_id": None, "confirmed_count": 0, "pending": None} for _ in planned_parts]}
                    data["plans"][plan["fingerprint"]] = entry
                    journal.save(data)
                # Preflight every known output before permitting any new side effect.
                for (source_id, part), state, report in zip(planned_parts, entry["parts"], result["parts"]):
                    report.update(playlist_id=state["playlist_id"], confirmed_count=state["confirmed_count"])
                    if state["pending"]:
                        report["status"] = "unresolved"
                        raise ValueError("Unresolved write intent; manual recovery required")
                    if state["playlist_id"]:
                        try:
                            self._verify_split_output(state["playlist_id"], part, state["confirmed_count"])
                        except Exception:
                            report["status"] = "unresolved"
                            raise
                        report["status"] = "complete" if state["confirmed_count"] == len(part["track_ids"]) else "partial"
                source_ids = {source["source_id"] for record in data["plans"].values() for source in _plan_sources(record["plan"])}
                for (source_id, part), state, report in zip(planned_parts, entry["parts"], result["parts"]):
                    if state["playlist_id"] is None:
                        state["pending"] = "create"
                        report["status"] = "unresolved"
                        journal.save(data)
                        output_id = _split_id(self.apple_music.create_playlist(part["name"]))
                        if output_id in known_ids or output_id in source_ids:
                            raise ValueError("Created ID aliases an existing target or source")
                        self._verify_split_output(output_id, part, 0)
                        state.update(playlist_id=output_id, pending=None)
                        journal.save(data)
                        known_ids.add(output_id)
                        report.update(playlist_id=output_id, status="partial")
                    while state["confirmed_count"] < len(part["track_ids"]):
                        self._verify_split_output(state["playlist_id"], part, state["confirmed_count"])
                        state["pending"] = "add"
                        report["status"] = "unresolved"
                        journal.save(data)
                        track_id = part["track_ids"][state["confirmed_count"]]
                        if self.apple_music.add_library_track_to_playlist_by_id(state["playlist_id"], track_id) is not True:
                            raise RuntimeError("Add result uncertain; manual recovery required")
                        self._verify_split_output(state["playlist_id"], part, state["confirmed_count"] + 1)
                        state.update(confirmed_count=state["confirmed_count"] + 1, pending=None)
                        journal.save(data)
                        report.update(confirmed_count=state["confirmed_count"], status="partial")
                    report["status"] = "complete"
                result["success"] = True
        except Exception as exc:
            result["error"] = str(exc)
        return result

    def _verify_split_output(self, playlist_id: str, part: dict, count: int) -> None:
        info = self.apple_music.get_playlist_info_by_id(playlist_id)
        tracks = self.apple_music.get_playlist_tracks_by_id(playlist_id)
        if (_split_id(info["persistent_id"]) != playlist_id or info["name"] != part["name"]
                or [_split_id(track["persistent_id"]) for track in tracks] != part["track_ids"][:count]):
            raise ValueError("Known output changed; manual recovery required")

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
