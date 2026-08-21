"""Strict indexing and exact matching of local audio tracks."""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

import mutagen


logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = frozenset(
    {".m4a", ".mp3", ".flac", ".aif", ".aiff", ".wav", ".aac", ".alac", ".ogg"}
)
DISALLOWED_VARIANT = re.compile(
    r"(?:\((?:remix(?:ed)?|live|remastered(?: \d{4})?|remaster(?: \d{4})?|cover)\)"
    r"|\[(?:remix(?:ed)?|live|remastered(?: \d{4})?|remaster(?: \d{4})?|cover)\]"
    r"|\s+-\s+(?:remix(?:ed)?|live|remastered(?: \d{4})?|remaster(?: \d{4})?|cover)$)"
)


class MusicClient(Protocol):
    def get_user_playlist_names(self) -> Optional[list[str]]: ...

    def get_playlist_tracks(self, playlist_name: str) -> Optional[list[dict]]: ...

    def import_local_track(self, filepath: Path) -> Optional[str]: ...

    def add_library_track_to_playlist(self, playlist_name: str, persistent_id: str) -> bool: ...

    def remove_playlist_track(self, playlist_name: str, persistent_id: str) -> bool: ...


@dataclass(frozen=True)
class LocalAudioTrack:
    path: Path
    artist: str
    title: str
    album: str | None = None


@dataclass(frozen=True)
class LocalizationResult:
    playlist: str
    old_persistent_id: str
    new_persistent_id: Optional[str]
    artist: str
    title: str
    album: Optional[str]
    status: str
    candidate_path: Optional[Path]


class MatchStatus(str, Enum):
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    PROHIBITED_VARIANT = "prohibited_variant"
    UNIQUE = "unique"


@dataclass(frozen=True)
class TrackMatch:
    status: MatchStatus
    candidates: tuple[LocalAudioTrack, ...]

    @property
    def unique(self) -> LocalAudioTrack | None:
        return self.candidates[0] if len(self.candidates) == 1 else None

    @property
    def is_ambiguous(self) -> bool:
        return self.status is MatchStatus.AMBIGUOUS


@dataclass(frozen=True)
class SkippedAudioFile:
    path: Path
    error_type: str
    message: str


class TrackLocalizer:
    """Build an immutable local index and perform strict metadata matches."""

    def __init__(self, source: str | Path, music_client: Optional[MusicClient] = None):
        self.source = Path(source)
        if self.source.suffix == ".musiclibrary":
            sibling_music_folder = self.source.parent / "Music"
            if sibling_music_folder.is_dir():
                self.source = sibling_music_folder
        self.music = music_client
        if not self.source.is_dir() or not os.access(self.source, os.R_OK):
            raise ValueError(f"source must exist and be a readable directory: {self.source}")
        self._skipped_files: list[SkippedAudioFile] = []
        self._tracks = self._build_index()

    @property
    def tracks(self) -> tuple[LocalAudioTrack, ...]:
        return self._tracks

    @property
    def skipped_files(self) -> tuple[SkippedAudioFile, ...]:
        return tuple(self._skipped_files)

    @staticmethod
    def canonicalize(value: str) -> str:
        text = unicodedata.normalize("NFKC", value).casefold()
        text = "".join(
            "-" if unicodedata.category(character) == "Pd" else character
            for character in text
        )
        return " ".join(text.split())

    def match(self, artist: str, title: str, album: str | None = None) -> TrackMatch:
        artist_key = self.canonicalize(artist)
        title_key = self.canonicalize(title)
        if DISALLOWED_VARIANT.search(title_key):
            return TrackMatch(MatchStatus.PROHIBITED_VARIANT, ())
        album_key = self.canonicalize(album) if album else None
        candidates = tuple(
            track
            for track in self.tracks
            if not DISALLOWED_VARIANT.search(self.canonicalize(track.title))
            and self.canonicalize(track.artist) == artist_key
            and self.canonicalize(track.title) == title_key
            and (
                album_key is None
                or (track.album is not None and self.canonicalize(track.album) == album_key)
            )
        )
        if len(candidates) == 1:
            status = MatchStatus.UNIQUE
        elif candidates:
            status = MatchStatus.AMBIGUOUS
        else:
            status = MatchStatus.NOT_FOUND
        return TrackMatch(status, candidates)

    def apply_replacement(
        self, playlist_name: str, old_track: dict, candidate: LocalAudioTrack
    ) -> LocalizationResult:
        if self.music is None:
            raise RuntimeError("music client is required to apply a replacement")
        old_id = old_track["persistent_id"]
        result_fields = {
            "playlist": playlist_name,
            "old_persistent_id": old_id,
            "artist": old_track.get("artist", ""),
            "title": old_track.get("title", ""),
            "album": old_track.get("album", ""),
            "candidate_path": candidate.path,
        }
        new_track_id = self.music.import_local_track(candidate.path)
        if not new_track_id:
            return LocalizationResult(
                new_persistent_id=None, status="import_failed", **result_fields
            )
        if not self.music.add_library_track_to_playlist(playlist_name, new_track_id):
            return LocalizationResult(
                new_persistent_id=new_track_id,
                status="playlist_add_failed",
                **result_fields,
            )
        if not self.music.remove_playlist_track(playlist_name, old_id):
            return LocalizationResult(
                new_persistent_id=new_track_id,
                status="old_track_remove_failed",
                **result_fields,
            )
        return LocalizationResult(
            new_persistent_id=new_track_id, status="replaced", **result_fields
        )

    def scan(
        self, playlist_name: Optional[str] = None, apply: bool = False
    ) -> list[LocalizationResult]:
        if self.music is None:
            raise RuntimeError("music client is required to scan playlists")

        playlist_names = (
            [playlist_name]
            if playlist_name is not None
            else (self.music.get_user_playlist_names() or [])
        )
        results: list[LocalizationResult] = []
        for current_playlist in playlist_names:
            try:
                playlist_tracks = self.music.get_playlist_tracks(current_playlist) or []
            except Exception:
                logger.exception("Failed to retrieve tracks for playlist %r", current_playlist)
                continue
            for track in playlist_tracks:
                try:
                    old_id = track["persistent_id"]
                    artist = track.get("artist", "")
                    title = track.get("title") or track.get("name", "")
                    album = track.get("album") or None
                    filepath = track.get("filepath")
                    fields = {
                        "playlist": current_playlist,
                        "old_persistent_id": old_id,
                        "new_persistent_id": None,
                        "artist": artist,
                        "title": title,
                        "album": album,
                    }
                    if filepath and Path(filepath).is_file():
                        results.append(
                            LocalizationResult(
                                status="already_local", candidate_path=None, **fields
                            )
                        )
                        continue

                    match = self.match(artist, title, album)
                    if match.status is MatchStatus.UNIQUE:
                        candidate = match.unique
                        assert candidate is not None
                        if apply:
                            normalized_track = dict(track)
                            normalized_track["title"] = title
                            results.append(
                                self.apply_replacement(
                                    current_playlist, normalized_track, candidate
                                )
                            )
                        else:
                            results.append(
                                LocalizationResult(
                                    status="would_replace",
                                    candidate_path=candidate.path,
                                    **fields,
                                )
                            )
                    else:
                        results.append(
                            LocalizationResult(
                                status=match.status.value, candidate_path=None, **fields
                            )
                        )
                except Exception:
                    logger.exception("Failed to localize track in playlist %r", current_playlist)
                    results.append(
                        LocalizationResult(
                            playlist=current_playlist,
                            old_persistent_id=track.get("persistent_id") or "",
                            new_persistent_id=None,
                            artist=track.get("artist") or "",
                            title=track.get("title") or track.get("name") or "",
                            album=track.get("album") or None,
                            status="error",
                            candidate_path=None,
                        )
                    )
        return results

    @staticmethod
    def write_report(report_path: Path, results: list[LocalizationResult]) -> None:
        payload = []
        for result in results:
            item = asdict(result)
            if item["candidate_path"] is not None:
                item["candidate_path"] = str(item["candidate_path"])
            payload.append(item)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _build_index(self) -> tuple[LocalAudioTrack, ...]:
        tracks = []
        for path in sorted(self.source.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                audio = mutagen.File(path, easy=True)
                artist = self._tag(audio, "artist")
                title = self._tag(audio, "title")
                album = self._tag(audio, "album")
            except (OSError, mutagen.MutagenError) as error:
                self._skipped_files.append(
                    SkippedAudioFile(
                        path=path,
                        error_type=type(error).__name__,
                        message=str(error),
                    )
                )
                continue
            if not artist or not title:
                missing = " and ".join(
                    name for name, value in (("artist", artist), ("title", title)) if not value
                )
                self._skipped_files.append(
                    SkippedAudioFile(
                        path=path,
                        error_type="MissingMetadata",
                        message=f"missing required {missing} metadata",
                    )
                )
                continue
            tracks.append(LocalAudioTrack(path=path, artist=artist, title=title, album=album))
        return tuple(tracks)

    @staticmethod
    def _tag(audio: Any, name: str) -> str | None:
        if audio is None or audio.tags is None:
            return None
        value = audio.tags.get(name)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value is None:
            return None
        text = str(value).strip()
        return text or None
