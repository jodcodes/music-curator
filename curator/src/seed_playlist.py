"""Pure seed ranking from recorded metadata; no acoustic similarity is inferred."""

from copy import deepcopy
import json
import re

from src.models import Temperament


def _persistent_id(track: dict) -> str:
    value = track.get("persistent_id") if isinstance(track, dict) else None
    if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{16}", value):
        return value.upper()
    return ""


def _label(value) -> str:
    label = " ".join(value.casefold().split()) if isinstance(value, str) else ""
    return "" if label in {"unknown", "unspecified", "none", "n/a", "missing value"} else label


def _mood(track: dict) -> tuple[str, bool]:
    labels = set()
    for field in ("mood", "temperament"):
        label = _label(track.get(field))
        for temperament in Temperament:
            if label == temperament.value.casefold():
                label = temperament.name.casefold()
        if label:
            labels.add(label)
    return (next(iter(labels)), False) if len(labels) == 1 else ("", len(labels) > 1)


def _metadata_warnings(track: dict) -> list[str]:
    mood, conflict = _mood(track)
    warnings = []
    if not mood:
        warnings.append("conflicting_recorded_mood" if conflict else "missing_recorded_mood")
    if not _label(track.get("genre")):
        warnings.append("missing_genre")
    return warnings


def _is_json_native(value) -> bool:
    if type(value) is dict:
        return all(type(key) is str and _is_json_native(item) for key, item in value.items())
    if type(value) is list:
        return all(_is_json_native(item) for item in value)
    return value is None or type(value) in (str, int, float, bool)


def rank_seed_candidates(seed: dict, candidates: list[dict], limit: int = 30) -> dict:
    """Return ``tracks`` rows (ID, original ``track``, reason, warnings) and warnings.

    Require a selected seed with a 16-hex ``persistent_id`` and JSON-native metadata.
    Metadata permits plain dictionaries with string keys, lists, and JSON scalars.
    The explicit seed wins over pool copies; source membership is the caller's job.
    Compare recorded ``mood``/``temperament`` and ``genre`` labels only. Known full
    temperament names equal their short names; no other synonym inference occurs.
    Same mood+genre, mood, genre, then unmatched rows rank by stable ID within ties.
    Conflicting duplicate records use the lexically smallest canonical JSON record,
    without merging metadata, and emit a warning. Inputs and output are detached.
    """
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("limit must be an integer from 1 to 30")
    seed_id = _persistent_id(seed)
    if not seed_id:
        raise ValueError("seed must have a valid 16-hex persistent_id")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")

    def record_key(track):
        try:
            if not _is_json_native(track):
                raise ValueError("non-native JSON type")
            return json.dumps(track, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("seed and candidates must contain JSON-native metadata") from exc

    records = {seed_id: seed}
    keys = {seed_id: record_key(seed)}
    warnings = set()
    for candidate in candidates:
        candidate_id = _persistent_id(candidate)
        if not candidate_id:
            warnings.add("invalid_candidate_persistent_id")
            continue
        key = record_key(candidate)
        if candidate_id in records:
            if key != keys[candidate_id]:
                warnings.add(f"conflicting_duplicate_metadata:{candidate_id}")
            if candidate_id == seed_id or key >= keys[candidate_id]:
                continue
        records[candidate_id], keys[candidate_id] = candidate, key

    seed_mood, _ = _mood(seed)
    seed_genre = _label(seed.get("genre"))
    for warning in _metadata_warnings(seed):
        warnings.add(f"seed:{warning}")

    def matches(track):
        mood, _ = _mood(track)
        return bool(seed_mood and mood == seed_mood), bool(
            seed_genre and _label(track.get("genre")) == seed_genre
        )

    def ranking_key(pid):
        same_mood, same_genre = matches(records[pid])
        return not same_mood, not same_genre, pid

    candidate_ids = sorted((pid for pid in records if pid != seed_id), key=ranking_key)
    rows = []
    for pid in [seed_id, *candidate_ids[: limit - 1]]:
        track = records[pid]
        row_warnings = _metadata_warnings(track)
        same_mood, same_genre = matches(track)
        comparable_mood = bool(seed_mood and _mood(track)[0])
        if pid == seed_id:
            reason = "selected_seed"
        elif same_mood:
            reason = "same_recorded_mood_and_genre" if same_genre else "same_recorded_mood"
        elif same_genre:
            reason = "same_genre" if comparable_mood else "genre_only_fallback"
        else:
            reason = "no_recorded_match"
            if not comparable_mood:
                row_warnings.append("insufficient_metadata")
        rows.append(
            {
                "persistent_id": pid,
                "track": deepcopy(track),
                "reason": reason,
                "warnings": row_warnings,
            }
        )
    return {"tracks": rows, "warnings": sorted(warnings)}
