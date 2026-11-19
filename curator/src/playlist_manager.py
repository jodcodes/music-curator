"""
Playlist Manager for Apple Music Integration

Handles creation of playlist folders and moving playlists between folders.
Integrates with AppleScript for actual Apple Music operations.
"""

import copy
import hashlib
import json
import math
import re
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src import apple_music as music_adapter
from src.apple_music import AppleMusicInterface
from src.logger import setup_logger

logger = setup_logger(__name__)


class PlaylistManager:
    """
    Manager for Apple Music playlist operations including folder creation and playlist moving.
    """

    def __init__(self, dry_run: bool = True, scripts_dir: str = "scripts"):
        """
        Initialize playlist manager.

        Args:
            dry_run: If True, only log operations without executing them
            scripts_dir: Directory containing AppleScript files
        """
        self.dry_run = dry_run
        self.scripts_dir = Path(scripts_dir) if isinstance(scripts_dir, str) else scripts_dir
        self.apple_music = AppleMusicInterface(str(self.scripts_dir))

        # Cache for folder information
        self._folder_cache: Dict[str, str] = {}
        self._playlist_cache: Dict[str, Dict[str, str]] = {}

        logger.info(f"Initialized PlaylistManager (dry_run: {dry_run})")

    def _run_applescript_file(
        self, script_name: str, args: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Run an AppleScript file with arguments.

        Args:
            script_name: Name of the script file (without .applescript extension)
            args: List of arguments to pass to the script

        Returns:
            Tuple of (success, output/error_message)
        """
        script_path = self.scripts_dir / f"{script_name}.applescript"

        if not script_path.exists():
            return False, f"Script not found: {script_path}"

        try:
            cmd = ["osascript", str(script_path)]
            if args:
                cmd.extend(args)

            if self.dry_run:
                logger.info(f"[DRY-RUN] Would execute: {' '.join(cmd)}")
                return True, "DRY-RUN: Command not executed"

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "Script execution timed out"
        except Exception as e:
            return False, f"Script execution failed: {str(e)}"

    def _run_applescript_inline(self, script_content: str) -> Tuple[bool, str]:
        """
        Run inline AppleScript content.

        Args:
            script_content: AppleScript code to execute

        Returns:
            Tuple of (success, output/error_message)
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would execute inline script")
                return True, "DRY-RUN: Script not executed"

            process = subprocess.Popen(
                ["osascript", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(input=script_content, timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                return False, "Script execution timed out"

            if process.returncode == 0:
                return True, stdout.strip()
            else:
                return False, stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "Script execution timed out"
        except Exception as e:
            return False, f"Script execution failed: {str(e)}"

    def get_existing_folders(self) -> Dict[str, str]:
        """
        Get existing playlist folders in Apple Music.

        Returns:
            Dictionary mapping folder names to persistent IDs
        """
        if self._folder_cache:
            return self._folder_cache

        # Reads remain real adapter reads even when legacy mutations are dry-run.
        try:
            folders = {row["name"]: row["persistent_id"]
                       for row in self.apple_music.get_playlist_topology_strict()
                       if row["kind"] == "folder"}
        except Exception as exc:
            logger.error("Failed to get existing folders: %s", exc)
            return {}

        self._folder_cache = folders
        logger.info(f"Found {len(folders)} existing playlist folders")
        return folders

    def create_folder(self, folder_name: str) -> Tuple[bool, Optional[str]]:
        """
        Create a new playlist folder in Apple Music.

        Args:
            folder_name: Name of the folder to create

        Returns:
            Tuple of (success, folder_persistent_id)
        """
        logger.info(f"Creating playlist folder: {folder_name}")

        # Check if folder already exists
        existing_folders = self.get_existing_folders()
        if folder_name in existing_folders:
            logger.info(f"Folder '{folder_name}' already exists")
            return True, existing_folders[folder_name]

        if self.dry_run:
            logger.info("[DRY-RUN] Would create folder: %s", folder_name)
            return False, None

        script = f"""
tell application "Music"
    try
        set newFolder to make new playlist with properties {{name:"{folder_name}"}}
        set folderID to persistent ID of newFolder
        return folderID
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
"""

        success, output = self._run_applescript_inline(script)

        if success and not output.startswith("ERROR:") and output != "DRY-RUN: Script not executed":
            folder_id = output.strip()
            # Update cache
            self._folder_cache[folder_name] = folder_id
            logger.info(f"Successfully created folder '{folder_name}' with ID: {folder_id}")
            return True, folder_id
        else:
            error_msg = (
                output if output.startswith("ERROR:") else f"Failed to create folder: {output}"
            )
            logger.error(error_msg)
            return False, None

    def get_playlist_info(self, playlist_name: str) -> Optional[Dict[str, str]]:
        """
        Get information about a specific playlist.

        Args:
            playlist_name: Name of the playlist

        Returns:
            Dictionary with playlist info (name, persistent_id) or None
        """
        if playlist_name in self._playlist_cache:
            return self._playlist_cache[playlist_name]

        try:
            matches = [row for row in self.apple_music.get_playlist_topology_strict()
                       if row["kind"] == "playlist" and row["name"] == playlist_name]
        except Exception as exc:
            logger.warning("Could not read playlist %s: %s", playlist_name, exc)
            return None
        if len(matches) != 1:
            logger.warning("Missing or ambiguous playlist name: %s", playlist_name)
            return None
        playlist_info = {"name": matches[0]["name"], "persistent_id": matches[0]["persistent_id"]}
        self._playlist_cache[playlist_name] = playlist_info
        return playlist_info

    def move_playlist_to_folder(self, playlist_name: str, folder_name: str) -> bool:
        """
        Move a playlist to a specific folder.

        Args:
            playlist_name: Name of the playlist to move
            folder_name: Name of the target folder

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Moving playlist '{playlist_name}' to folder '{folder_name}'")

        # Get playlist information
        playlist_info = self.get_playlist_info(playlist_name)
        if not playlist_info:
            logger.error(f"Playlist not found: {playlist_name}")
            return False

        # Get or create target folder
        existing_folders = self.get_existing_folders()

        if folder_name not in existing_folders:
            logger.info(f"Folder '{folder_name}' doesn't exist, creating it...")
            success, folder_id = self.create_folder(folder_name)
            if not success or folder_id is None:
                logger.error(f"Failed to create folder: {folder_name}")
                return False
        else:
            folder_id = existing_folders[folder_name]

        # Move playlist using the move script
        playlist_id = playlist_info["persistent_id"]

        if self.dry_run:
            logger.info(
                f"[DRY-RUN] Would move playlist '{playlist_name}' (ID: {playlist_id}) "
                f"to folder '{folder_name}' (ID: {folder_id})"
            )
            return True

        success, output = self._run_applescript_file(
            "move_playlist_to_folder", [playlist_id, folder_id]
        )

        if success and "SUCCESS" in output:
            logger.info(f"Successfully moved playlist '{playlist_name}' to folder '{folder_name}'")
            return True
        else:
            logger.error(f"Failed to move playlist: {output}")
            return False

    def ensure_genre_folders_exist(self, target_genres: List[str]) -> Dict[str, bool]:
        """
        Ensure all target genre folders exist in Apple Music.

        Args:
            target_genres: List of genre folder names to create

        Returns:
            Dictionary mapping genre names to creation success status
        """
        logger.info(f"Ensuring {len(target_genres)} genre folders exist")

        results = {}
        existing_folders = self.get_existing_folders()

        for genre in target_genres:
            if genre in existing_folders:
                logger.info(f"Genre folder '{genre}' already exists")
                results[genre] = True
            else:
                logger.info(f"Creating genre folder: {genre}")
                success, _ = self.create_folder(genre)
                results[genre] = success

        return results

    def organize_playlists(self, playlist_assignments: Dict[str, str]) -> Dict[str, bool]:
        """
        Organize multiple playlists into their assigned folders.

        Args:
            playlist_assignments: Dictionary mapping playlist names to target folder names

        Returns:
            Dictionary mapping playlist names to move success status
        """
        logger.info(f"Organizing {len(playlist_assignments)} playlists")

        results = {}

        # Get all target folders
        target_folders = set(playlist_assignments.values())

        # Ensure all target folders exist
        folder_results = self.ensure_genre_folders_exist(list(target_folders))

        # Move playlists
        for playlist_name, folder_name in playlist_assignments.items():
            if not folder_results.get(folder_name, False):
                logger.error(
                    f"Cannot move playlist '{playlist_name}' - target folder '{folder_name}' unavailable"
                )
                results[playlist_name] = False
                continue

            success = self.move_playlist_to_folder(playlist_name, folder_name)
            results[playlist_name] = success

        # Summary
        successful_moves = sum(1 for success in results.values() if success)
        logger.info(
            f"Playlist organization complete: {successful_moves}/{len(playlist_assignments)} successful"
        )

        return results

    @staticmethod
    def _organization_digest(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _selected_organization_ids(playlist_ids: List[str]) -> List[str]:
        if not isinstance(playlist_ids, list) or not playlist_ids:
            raise ValueError("Select a nonempty list of stable playlist IDs")
        selected = [music_adapter.AppleMusicInterface._validate_persistent_id(pid)
                    for pid in playlist_ids]
        if len(set(selected)) != len(selected):
            raise ValueError("Selected playlist IDs must be unique")
        return selected

    def _load_genre_folders(self) -> Dict[str, str]:
        """Read the existing configuration without splitting literal slashes in labels."""
        path = Path(__file__).resolve().parent.parent / "data" / "config" / "playlist_folders.json"
        with path.open(encoding="utf-8") as stream:
            mapping = json.load(stream)["genre_folders"]
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("Invalid genre folder mapping")
        for genre, label in mapping.items():
            if (not isinstance(genre, str) or not genre or not isinstance(label, str)
                    or not label.strip() or re.search(r"[\x00-\x1f\x7f]", label)):
                raise ValueError("Invalid genre folder component")
        return mapping

    def _organization_topology(self) -> List[dict]:
        rows = music_adapter.AppleMusicInterface._validate_playlist_topology(
            self.apple_music.get_playlist_topology_strict())
        return sorted(rows, key=lambda row: row["persistent_id"])

    @staticmethod
    def _folder_components(items: dict, parent_id: Optional[str]) -> List[str]:
        components = []
        while parent_id is not None:
            parent = items[parent_id]
            components.append(parent["name"])
            parent_id = parent["parent_id"]
        return list(reversed(components))

    @staticmethod
    def _organization_target(items: dict, components: List[str]) -> Tuple[List[Optional[str]], bool]:
        chain = []
        parent = None
        missing = False
        for component in components:
            if missing:
                chain.append(None)
                continue
            matches = [row for row in items.values()
                       if row["parent_id"] == parent and row["name"] == component]
            if not matches:
                missing = True
                chain.append(None)
            elif len(matches) != 1 or matches[0]["kind"] != "folder" or not matches[0]["modifiable"]:
                return chain, True
            else:
                parent = matches[0]["persistent_id"]
                chain.append(parent)
        return chain, False

    @staticmethod
    def _organization_tracks(tracks: List[dict]) -> List[dict]:
        if not isinstance(tracks, list) or any(not isinstance(track, dict) for track in tracks):
            raise ValueError("Malformed strict playlist membership")
        snapshot = copy.deepcopy(tracks)
        for track in snapshot:
            track["persistent_id"] = music_adapter.AppleMusicInterface._validate_persistent_id(
                track.get("persistent_id"))
        # Full ordered metadata/membership snapshot, including repeated track occurrences.
        PlaylistManager._organization_digest({"tracks": snapshot})
        return snapshot

    def _organization_operation(self, pid: str, items: dict, mapping: dict,
                                tracks=None, genre=None, confidence=None,
                                read_error=None, classification_error=None) -> dict:
        source = items.get(pid)
        operation = {
            "source_id": pid, "source": copy.deepcopy(source),
            "current_parent_id": source["parent_id"] if source else None,
            "current_components": self._folder_components(items, source["parent_id"]) if source else [],
            "target_components": [], "target_chain_ids": [],
            "tracks": copy.deepcopy(tracks), "genre": genre, "confidence": confidence,
            "read_error": read_error, "classification_error": classification_error,
            "action": "skip", "reason": "missing_source",
        }
        if not source:
            return operation
        if source["kind"] != "playlist" or not source["modifiable"]:
            operation["reason"] = "ineligible_source"
        elif read_error is not None:
            operation["reason"] = "tracks_unavailable"
        elif not tracks:
            operation["reason"] = "empty_playlist"
        elif classification_error is not None:
            operation["reason"] = "classification_failed"
        elif genre is None:
            operation["reason"] = "unclassified"
        elif genre not in mapping:
            operation["reason"] = "unknown_genre"
        else:
            operation["target_components"] = ["Genre", mapping[genre]]
            chain, collision = self._organization_target(items, operation["target_components"])
            operation["target_chain_ids"] = chain
            if collision:
                operation["reason"] = "target_collision"
            elif chain[-1] is not None and source["parent_id"] == chain[-1]:
                operation["reason"] = "already_correct"
            else:
                operation["action"] = "move"
                operation["reason"] = "genre_assignment"
        return operation

    def preview_playlist_organization(self, playlist_ids: List[str], classifier) -> dict:
        """Build a JSON-safe versioned plan using selected stable IDs; perform zero writes.

        The injected classifier must be local (provider enrichment disabled). All
        strict source reads precede classification, which receives copies of tracks.
        """
        selected = self._selected_organization_ids(playlist_ids)
        if getattr(classifier, "enable_genre_enrichment", False):
            raise ValueError("Playlist organization requires provider enrichment disabled")
        mapping = self._load_genre_folders()
        topology = self._organization_topology()
        items = {row["persistent_id"]: row for row in topology}
        snapshots, errors = {}, {}
        for pid in selected:
            source = items.get(pid)
            if source and source["kind"] == "playlist" and source["modifiable"]:
                try:
                    snapshots[pid] = self._organization_tracks(self.apple_music.get_playlist_tracks_by_id(pid))
                except Exception as exc:
                    errors[pid] = str(exc) or type(exc).__name__
        operations = []
        for pid in selected:
            tracks = snapshots.get(pid)
            genre, confidence, classification_error = None, None, None
            if tracks:
                try:
                    genre, details = classifier.classify_playlist(copy.deepcopy(tracks), pid)
                    if genre is not None and not isinstance(genre, str):
                        raise ValueError("Invalid classified genre")
                    confidence = details.get("confidence")
                    if confidence is not None and (type(confidence) not in (int, float)
                                                   or not math.isfinite(confidence) or confidence < 0):
                        raise ValueError("Invalid classification confidence")
                except Exception as exc:
                    genre, confidence = None, None
                    classification_error = str(exc) or type(exc).__name__
            operations.append(self._organization_operation(
                pid, items, mapping, tracks, genre, confidence, errors.get(pid), classification_error))
        payload = {"version": 1, "selected_ids": selected, "topology": topology,
                   "genre_folders": mapping, "operations": operations}
        return dict(payload, fingerprint=self._organization_digest(payload))

    def _validate_organization_plan(self, plan: dict) -> None:
        keys = {"version", "selected_ids", "topology", "genre_folders", "operations", "fingerprint"}
        if not isinstance(plan, dict) or set(plan) != keys or type(plan["version"]) is not int or plan["version"] != 1:
            raise ValueError("Invalid playlist organization plan schema/version")
        payload = {key: value for key, value in plan.items() if key != "fingerprint"}
        if not isinstance(plan["fingerprint"], str) or plan["fingerprint"] != self._organization_digest(payload):
            raise ValueError("Playlist organization plan fingerprint mismatch")
        selected = self._selected_organization_ids(plan["selected_ids"])
        if selected != plan["selected_ids"]:
            raise ValueError("Plan IDs are not normalized")
        topology = sorted(music_adapter.AppleMusicInterface._validate_playlist_topology(plan["topology"]),
                          key=lambda row: row["persistent_id"])
        if topology != plan["topology"]:
            raise ValueError("Invalid normalized topology snapshot")
        mapping = self._load_genre_folders()
        if plan["genre_folders"] != mapping:
            raise ValueError("Genre folder mapping changed or was tampered with")
        operations = plan["operations"]
        if not isinstance(operations, list) or len(operations) != len(selected):
            raise ValueError("Every selected ID must have exactly one operation")
        items = {row["persistent_id"]: row for row in topology}
        for pid, op in zip(selected, operations):
            if not isinstance(op, dict) or op.get("source_id") != pid:
                raise ValueError("Invalid selected source operation")
            for key in ("read_error", "classification_error"):
                if op.get(key) is not None and (not isinstance(op[key], str) or not op[key]):
                    raise ValueError("Invalid operation error snapshot")
            genre, confidence = op.get("genre"), op.get("confidence")
            if genre is not None and not isinstance(genre, str):
                raise ValueError("Invalid operation genre")
            if confidence is not None and (type(confidence) not in (int, float)
                                           or not math.isfinite(confidence) or confidence < 0):
                raise ValueError("Invalid operation confidence")
            tracks = op.get("tracks")
            if tracks is not None and self._organization_tracks(tracks) != tracks:
                raise ValueError("Invalid normalized track snapshot")
            source = items.get(pid)
            eligible = source is not None and source["kind"] == "playlist" and source["modifiable"]
            if not eligible:
                if any(op.get(key) is not None for key in ("tracks", "genre", "confidence", "read_error", "classification_error")):
                    raise ValueError("Ineligible sources cannot have classification snapshots")
            elif op.get("read_error") is not None:
                if any(op.get(key) is not None for key in ("tracks", "genre", "confidence", "classification_error")):
                    raise ValueError("Read failures cannot have classification snapshots")
            elif tracks is None:
                raise ValueError("Eligible sources require strict membership snapshots")
            if (not tracks or op.get("classification_error") is not None) and (genre is not None or confidence is not None):
                raise ValueError("Invalid classification snapshot")
            expected = self._organization_operation(pid, items, mapping, tracks, genre, confidence,
                                                    op.get("read_error"), op.get("classification_error"))
            if self._organization_digest(op) != self._organization_digest(expected):
                raise ValueError("Tampered source, target components, chain or action")
            if op["reason"] == "target_collision":
                raise ValueError("Colliding target folder components")

    @staticmethod
    def _organization_result(op: dict, status: str, reason: str, target_id=None) -> dict:
        source = op.get("source")
        return {"source_id": op.get("source_id"),
                "source_name": source.get("name") if isinstance(source, dict) else None,
                "current_parent_id": op.get("current_parent_id"),
                "current_components": copy.deepcopy(op.get("current_components", [])),
                "target_components": copy.deepcopy(op.get("target_components", [])),
                "target_id": target_id, "status": status, "reason": reason}

    @staticmethod
    def _organization_report(results: List[dict], error=None) -> dict:
        moved = sum(result["status"] == "moved" for result in results)
        failed = sum(result["status"] == "failed" for result in results)
        skipped = sum(result["status"] == "skipped" for result in results)
        return {"moved": moved, "applied": moved, "failed": failed, "skipped": skipped,
                "success": bool(moved) and not failed and not skipped and not error,
                "results": results, "error": error}

    def apply_playlist_organization(self, plan: dict, confirmed: bool = False) -> dict:
        """Apply only a confirmed, intact, globally fresh plan; never classify here.

        Explicit confirmation owns these ID writes independently of legacy dry_run.
        After every writer, require the exact expected topology transition; any
        failure/uncertainty stops all further writes, with no adoption or retry.
        """
        # Even rejected plans receive an outcome for each supplied selected ID.
        selected = plan.get("selected_ids", []) if isinstance(plan, dict) else []
        operations = plan.get("operations", []) if isinstance(plan, dict) else []
        rejected_ops = []
        if isinstance(selected, list):
            for index, pid in enumerate(selected):
                op = operations[index] if isinstance(operations, list) and index < len(operations) else {}
                op = op if isinstance(op, dict) else {}
                rejected_ops.append(dict(op, source_id=pid))
        if confirmed is not True:
            return self._organization_report([
                self._organization_result(op, "skipped", "confirmation_required") for op in rejected_ops],
                "Explicit literal true confirmation is required")
        preflight_source = None
        try:
            # Freeze caller-owned dictionaries before any reads or writes.
            plan = copy.deepcopy(plan)
            self._validate_organization_plan(plan)
            topology = self._organization_topology()
            if topology != plan["topology"]:
                raise ValueError("Stale playlist organization topology/source snapshot")
            for op in plan["operations"]:
                if op["tracks"] is not None:
                    preflight_source = op["source_id"]
                    actual = self._organization_tracks(self.apple_music.get_playlist_tracks_by_id(op["source_id"]))
                    if self._organization_digest({"tracks": actual}) != self._organization_digest({"tracks": op["tracks"]}):
                        raise ValueError(f"Stale track snapshot for {op['source_id']}")
            preflight_source = None
            # Guard against structural changes during the sequence of track reads.
            if self._organization_topology() != topology:
                raise ValueError("Playlist topology changed during preflight")
        except Exception as exc:
            message = str(exc) or type(exc).__name__
            failed_index = next((index for index, op in enumerate(rejected_ops)
                                 if op.get("source_id") == preflight_source), 0)
            return self._organization_report([
                self._organization_result(op, "failed" if index == failed_index else "skipped",
                                          f"preflight_failed: {message}" if index == failed_index else "preflight_aborted")
                for index, op in enumerate(rejected_ops)], message)

        results, stopped = [], False
        for op in plan["operations"]:
            if stopped:
                results.append(self._organization_result(op, "skipped", "stopped_after_failure"))
                continue
            if op["action"] == "skip":
                existing_target = op["target_chain_ids"][-1] if op["reason"] == "already_correct" else None
                results.append(self._organization_result(op, "skipped", op["reason"], existing_target))
                continue
            target_id, resolved_target_id = None, None
            try:
                items = {row["persistent_id"]: row for row in topology}
                chain, collision = self._organization_target(items, op["target_components"])
                if collision:
                    raise RuntimeError("Target folder collision before write")
                for index, component in enumerate(op["target_components"]):
                    if chain[index] is not None:
                        target_id = chain[index]
                        continue
                    if self._organization_topology() != topology:
                        raise RuntimeError("Topology changed before folder creation")
                    created_id = music_adapter.AppleMusicInterface._validate_persistent_id(
                        self.apple_music.create_playlist_folder_by_id(component, target_id))
                    if created_id in items:
                        raise RuntimeError("Folder creation returned an existing ID")
                    after = self._organization_topology()
                    created = {"persistent_id": created_id, "name": component, "kind": "folder",
                               "parent_id": target_id, "modifiable": True}
                    expected = sorted(topology + [created], key=lambda row: row["persistent_id"])
                    if after != expected:
                        raise RuntimeError("Failed or uncertain folder identity/name/parent verification")
                    items[created_id] = created
                    verified_chain, collision = self._organization_target(items, op["target_components"])
                    if collision or verified_chain[index] != created_id:
                        raise RuntimeError("Created target folder is ambiguous")
                    topology, target_id = after, created_id
                    chain[index] = created_id
                resolved_target_id = target_id
                if self._organization_topology() != topology:
                    raise RuntimeError("Topology changed before playlist move")
                actual_tracks = self._organization_tracks(self.apple_music.get_playlist_tracks_by_id(op["source_id"]))
                if self._organization_digest({"tracks": actual_tracks}) != self._organization_digest({"tracks": op["tracks"]}):
                    raise RuntimeError("Source tracks changed before playlist move")
                if self.apple_music.move_playlist_by_id(op["source_id"], target_id) is not True:
                    raise RuntimeError("Failed or uncertain playlist move")
                after = self._organization_topology()
                expected = [dict(row, parent_id=target_id) if row["persistent_id"] == op["source_id"] else row
                            for row in topology]
                if after != expected:
                    raise RuntimeError("Failed or uncertain moved-parent verification")
                topology = after
                results.append(self._organization_result(op, "moved", "verified_move", target_id))
                self.clear_cache()
            except Exception as exc:
                stopped = True
                results.append(self._organization_result(op, "failed", str(exc) or type(exc).__name__, resolved_target_id))
                self.clear_cache()
        return self._organization_report(results)

    def _make_playlist_id(self, playlist_name: str) -> str:
        """Create a stable API-safe ID when Music persistent IDs are unavailable."""
        normalized = playlist_name.strip().lower().replace(" ", "-")
        normalized = "".join(ch for ch in normalized if ch.isalnum() or ch in {"-", "_"})
        return normalized or "unknown"

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """Return playlists in a shape expected by the web frontend API."""
        playlist_rows = self.apple_music.get_user_playlists_with_counts() or []
        playlist_ids = self.apple_music.get_playlist_ids() or {}
        playlists: List[Dict[str, Any]] = []
        excluded_names = {
            "music",
            "music videos",
            "favourite songs",
            "favorite songs",
        }

        # Fallback for older interface behavior: names without precomputed counts.
        if not playlist_rows:
            playlist_rows = [
                {"name": name, "track_count": 0}
                for name in (self.apple_music.get_user_playlist_names() or [])
            ]

        for row in playlist_rows:
            playlist_name = str(row.get("name", "")).strip()
            if not playlist_name:
                continue
            if playlist_name.lower() in excluded_names:
                continue
            track_count = int(row.get("track_count", 0) or 0)

            playlists.append(
                {
                    # Prefer persistent IDs from AppleScript files for stable identity.
                    "id": playlist_ids.get(playlist_name, self._make_playlist_id(playlist_name)),
                    "name": playlist_name,
                    "track_count": track_count,
                    "genre": None,
                    "created_date": None,
                }
            )

        return playlists

    def get_playlist_details(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Return detailed playlist data for a frontend playlist ID."""
        all_playlists = self.get_all_playlists()
        target = next((p for p in all_playlists if p.get("id") == playlist_id), None)

        if not target:
            return None

        playlist_name = str(target.get("name", "")).strip()
        tracks = self.apple_music.get_playlist_tracks(playlist_name) or []

        normalized_tracks = []
        for idx, track in enumerate(tracks, start=1):
            if not isinstance(track, dict):
                continue
            normalized_tracks.append(
                {
                    "id": f"{playlist_id}-track-{idx}",
                    "name": track.get("title") or track.get("name") or "Unknown Track",
                    "artist": track.get("artist") or "Unknown Artist",
                    "metadata": {
                        "album": track.get("album"),
                        "genre": track.get("genre"),
                        "bpm": track.get("bpm"),
                        "year": track.get("year"),
                        "composer": track.get("composer"),
                        "duration": track.get("duration"),
                    },
                }
            )

        return {
            "id": playlist_id,
            "name": playlist_name,
            "track_count": len(normalized_tracks),
            "genre": target.get("genre"),
            "tracks": normalized_tracks,
        }

    def clear_cache(self):
        """Clear internal caches for folders and playlists."""
        self._folder_cache.clear()
        self._playlist_cache.clear()
        logger.debug("Cleared playlist and folder caches")
