"""
Metadata enrichment module for downloaded audio tracks (Data Layer).

LAYER: Data Layer - Data Structures and Models
ROLE: Core data classes for metadata enrichment pipeline
ARCHITECTURE: See src/README.md for full architecture

Enriches incomplete metadata (BPM, Genre, Year) for locally stored audio files
by querying external music databases with "exact missing fields" strategy.

Flow:
1. Detect downloaded tracks (local filesystem presence)
2. Check which metadata fields are MISSING/incomplete
3. Query sources in priority order ONLY FOR MISSING FIELDS: Discogs → Last.fm → Wikidata → MusicBrainz → AcousticBrainz
4. For each MISSING FIELD: use first source that has it, skip other sources for that field
5. Skip searching for fields already present (don't re-enrich existing metadata)
6. Continue through all sources until all missing fields found or sources exhausted
7. **No songs skipped** - searches all sources for missing metadata
8. Write tags back to audio files with source tracking (including which fields were added)

Key Classes:
- MetadataField: Enum of available metadata fields
- DatabaseSource: Enum of available metadata sources
- MetadataEntry: Single metadata result (value, source, confidence)
- EnrichedMetadata: Collection of metadata entries for a track
- TrackIdentifier: Track identification data (artist, title, duration)
"""

import json
import logging
import os
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.audio_tags import TagManager


class MetadataField(Enum):
    """Metadata fields that can be enriched."""

    BPM = "bpm"
    GENRE = "genre"
    YEAR = "year"
    COMPOSER = "composer"
    COVER_ART = "cover_art"


class DatabaseSource(Enum):
    """External music databases in priority order."""

    MUSICBRAINZ = 1
    ACOUSTICBRAINZ = 2
    DISCOGS = 3
    WIKIDATA = 4
    LASTFM = 5


@dataclass
class TrackIdentifier:
    """Identifier for a track (artist + title + duration)."""

    artist: str
    title: str
    duration_seconds: Optional[int] = None
    album: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "artist": self.artist,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "album": self.album,
        }

    def is_complete(self) -> bool:
        """Check if identifier has enough info for matching."""
        return bool(self.artist and self.title)


@dataclass
class MetadataEntry:
    """Single metadata field with source tracking."""

    field: MetadataField
    value: str
    source: DatabaseSource
    confidence: float = 1.0  # 0.0-1.0: exact match=1.0, partial=0.5-0.8
    timestamp: str = dataclass_field(default_factory=lambda: datetime.now().isoformat())  # type: ignore[misc]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field.value,
            "value": self.value,
            "source": self.source.name,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class EnrichedMetadata:
    """Complete enriched metadata for a track."""

    track_id: TrackIdentifier
    filepath: str
    entries: Dict[MetadataField, MetadataEntry] = dataclass_field(default_factory=dict)
    existing_metadata: Dict[str, str] = dataclass_field(default_factory=dict)
    skipped_fields: Dict[MetadataField, str] = dataclass_field(default_factory=dict)

    def add_entry(self, entry: MetadataEntry) -> None:
        """Add a metadata entry, keeping highest confidence version."""
        if entry.field in self.entries:
            existing = self.entries[entry.field]
            if entry.confidence > existing.confidence:
                self.entries[entry.field] = entry
        else:
            self.entries[entry.field] = entry

    def mark_skipped(self, field: MetadataField, reason: str) -> None:
        """Mark a field as skipped with reason."""
        self.skipped_fields[field] = reason

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id.to_dict(),
            "filepath": self.filepath,
            "enriched_fields": {k.value: v.to_dict() for k, v in self.entries.items()},
            "skipped_fields": {k.value: v for k, v in self.skipped_fields.items()},
            "existing_metadata": self.existing_metadata,
        }


class DownloadedTrackDetector:
    """Detect downloaded (local) tracks vs cloud-only tracks."""

    def __init__(self, library_paths: Optional[List[str]] = None):
        """
        Initialize detector with local library paths.

        Args:
            library_paths: Paths to local music libraries
                          (e.g., ~/Music/Music Library.musiclibrary)
        """
        self.library_paths = library_paths or self._get_default_paths()
        self.logger = logging.getLogger(__name__)

    def _get_default_paths(self) -> List[str]:
        """Get default local music library paths."""
        paths = []

        # macOS Music app library
        home = os.path.expanduser("~")
        music_lib = os.path.join(home, "Music", "Music Media")
        if os.path.exists(music_lib):
            paths.append(music_lib)

        # Common music folders
        for folder in ["Music", "Downloads", "Documents"]:
            folder_path = os.path.join(home, folder)
            if os.path.exists(folder_path):
                paths.append(folder_path)

        return paths

    def is_downloaded(self, filepath: Optional[str]) -> bool:
        """
        Determine if a track is downloaded (local file exists).

        Args:
            filepath: Absolute path to audio file

        Returns:
            True if file exists locally and is readable
        """
        if not filepath:
            return False

        expanded_path = os.path.expanduser(filepath)

        # Check if file exists and is readable
        is_local = os.path.exists(expanded_path) and os.path.isfile(expanded_path)

        if is_local and not os.access(expanded_path, os.R_OK):
            self.logger.warning(f"File exists but not readable: {filepath}")
            return False

        return is_local

    def is_in_library(self, filepath: Optional[str]) -> bool:
        """
        Check if file is within a known local library path.

        Args:
            filepath: Absolute path to audio file

        Returns:
            True if file is in one of the configured library paths
        """
        if not filepath:
            return False

        expanded_path = os.path.expanduser(filepath)
        expanded_path = os.path.abspath(expanded_path)

        for lib_path in self.library_paths:
            lib_path = os.path.expanduser(lib_path)
            lib_path = os.path.abspath(lib_path)
            if expanded_path.startswith(lib_path):
                return True

        return False

    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio file formats."""
        return [".mp3", ".flac", ".ogg", ".m4a", ".aiff", ".wav"]

    def is_audio_file(self, filepath: str) -> bool:
        """Check if file is a supported audio format."""
        _, ext = os.path.splitext(filepath.lower())
        return ext in self.get_supported_formats()


class MetadataRequirements:
    """Define which metadata fields are required or optional per genre."""

    # These fields must be present for enrichment to work
    # (They're used for database matching, not enriched)
    CRITICAL_FIELDS_RAW = {"artist", "title"}

    ENRICHABLE_FIELDS = {
        MetadataField.BPM: "Beats per minute (preferably from AcousticBrainz)",
        MetadataField.GENRE: "Genre classification (from multiple sources)",
        MetadataField.YEAR: "Release year (from MusicBrainz/Discogs/Wikidata)",
        MetadataField.COMPOSER: "Composer/Songwriter information",
    }

    def check_metadata_completeness(
        self, metadata: Dict[str, str]
    ) -> Tuple[List[MetadataField], List[MetadataField]]:
        """
        Check which fields are present and which are missing.

        Returns:
            (complete_fields, missing_fields)
        """
        complete = []
        missing = []

        for field in MetadataField:
            # Consider a field complete only if it has a non-empty value
            # Special handling: 0 or "0" values mean the field is missing
            value = str(metadata.get(field.value, "")).strip()
            if value and value not in ["0", "0.0"]:
                complete.append(field)
            else:
                missing.append(field)

        return complete, missing

    def should_enrich(
        self, missing_fields: List[MetadataField], skip_complete: bool = True
    ) -> bool:
        """
        Determine if enrichment is worthwhile.

        Args:
            missing_fields: Fields that are missing/incomplete
            skip_complete: Skip if all enrichable fields present

        Returns:
            True if enrichment should proceed
        """
        if not missing_fields:
            return False

        enrichable_missing = [f for f in missing_fields if f in self.ENRICHABLE_FIELDS]

        return bool(enrichable_missing)


class MetadataEnricher:
    """Main orchestrator for metadata enrichment workflow."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        tag_manager: Optional[TagManager] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.track_detector = DownloadedTrackDetector()
        self.requirements = MetadataRequirements()
        self.tag_manager = tag_manager or TagManager()
        self.enrichment_history: List[EnrichedMetadata] = []

    def enrich_track(
        self,
        filepath: str,
        existing_metadata: Dict[str, str],
        track_id: TrackIdentifier,
        force: bool = False,
    ) -> EnrichedMetadata:
        """
        Enrich metadata for a single downloaded track.

        Args:
            filepath: Path to audio file
            existing_metadata: Current metadata from file
            track_id: Artist+Title+Duration identifier
            force: Overwrite existing metadata without confirmation

        Returns:
            EnrichedMetadata object with enriched fields
        """
        self.logger.info(f"Enriching: {track_id.artist} - {track_id.title}")

        # Verify it's a downloaded track
        if not self.track_detector.is_downloaded(filepath):
            self.logger.warning(f"File not found locally: {filepath}")
            enriched = EnrichedMetadata(track_id, filepath, existing_metadata=existing_metadata)
            enriched.mark_skipped(MetadataField.BPM, "File not found locally")
            return enriched

        # Check completeness
        complete, missing = self.requirements.check_metadata_completeness(existing_metadata)

        enriched = EnrichedMetadata(
            track_id=track_id, filepath=filepath, existing_metadata=existing_metadata.copy()
        )

        # Skip if all enrichable fields present and not forcing
        if not self.requirements.should_enrich(missing) and not force:
            self.logger.info(f"  Metadata complete, skipping: {track_id.title}")
            for field in missing:
                if field in self.requirements.ENRICHABLE_FIELDS:
                    enriched.mark_skipped(field, "Already present in file")
            return enriched

        # Log what's missing
        self.logger.debug(f"  Complete fields: {[f.value for f in complete]}")
        self.logger.debug(f"  Missing fields: {[f.value for f in missing]}")

        # Return enriched metadata (actual database queries handled separately)
        return enriched

    def enrich_batch(
        self, tracks: List[Tuple[str, Dict, TrackIdentifier]], force: bool = False
    ) -> List[EnrichedMetadata]:
        """
        Enrich metadata for multiple tracks.

        Args:
            tracks: List of (filepath, metadata, track_id) tuples
            force: Overwrite existing metadata

        Returns:
            List of EnrichedMetadata objects
        """
        results = []
        for filepath, metadata, track_id in tracks:
            result = self.enrich_track(filepath, metadata, track_id, force)
            results.append(result)
            self.enrichment_history.append(result)

        return results

    def write_enriched_metadata(
        self, enriched: EnrichedMetadata, overwrite: bool = False
    ) -> Dict[str, Any]:
        """Write enriched metadata fields back to the audio file."""
        result: Dict[str, Any] = {
            "filepath": enriched.filepath,
            "applied_fields": [],
            "skipped_fields": {},
            "failed_fields": {},
        }
        tag_values: Dict[str, str] = {}

        for metadata_field, entry in enriched.entries.items():
            if metadata_field == MetadataField.COVER_ART:
                result["skipped_fields"][metadata_field.value] = (
                    "Use CoverArtManager for binary cover art writes"
                )
                continue
            tag_values[metadata_field.value] = entry.value

        if not tag_values:
            return result

        if self.tag_manager.write_tags(enriched.filepath, tag_values, overwrite):
            result["applied_fields"].extend(tag_values.keys())
            return result

        for field_name in tag_values:
            result["failed_fields"][field_name] = "Tag write failed"
        return result

    def get_enrichment_summary(self) -> Dict:
        """Get summary of enrichment session."""
        total = len(self.enrichment_history)
        enriched = sum(1 for e in self.enrichment_history if e.entries)
        skipped = sum(1 for e in self.enrichment_history if not e.entries)

        fields_enriched = {}
        for enriched_meta in self.enrichment_history:
            for field, entry in enriched_meta.entries.items():
                if field not in fields_enriched:
                    fields_enriched[field.value] = 0
                fields_enriched[field.value] += 1

        return {
            "total_tracks": total,
            "enriched_tracks": enriched,
            "skipped_tracks": skipped,
            "fields_enriched": fields_enriched,
        }

    def export_results(self, output_file: str) -> bool:
        """Export enrichment results to JSON."""
        try:
            results = {
                "timestamp": datetime.now().isoformat(),
                "summary": self.get_enrichment_summary(),
                "tracks": [e.to_dict() for e in self.enrichment_history],
            }

            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)

            self.logger.info(f"Exported results to {output_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to export results: {e}")
            return False
