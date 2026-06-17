"""
Unified data models for all three features (4tempers, metad_enr, plsort).

This module provides shared data structures used across:
- Temperament Analyzer (4tempers)
- Metadata Enrichment (metad_enr)
- Playlist Organization (plsort)

Extracted from individual modules to eliminate duplication and ensure
consistency across the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Temperament(Enum):
    """Four temperament categories from 4tempers feature."""

    WOE = "Woe (Melancholic)"
    FROLIC = "Frolic (Sanguine)"
    DREAD = "Dread (Phlegmatic)"
    MALICE = "Malice (Choleric)"


@dataclass
class Track:
    """Represents a music track - used by all three features.

    Attributes:
        track_id: Persistent ID from Music.app (hex format)
        name: Track title
        artist: Artist name
        album: Album name (optional)
        genre: Genre classification (optional)
        year: Release year (optional)
        bpm: Beats per minute (optional)
    """

    track_id: str
    name: str
    artist: str
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    bpm: Optional[int] = None

    def get_metadata_string(self) -> str:
        """Return track metadata as a formatted string for LLM analysis.

        Returns:
            String representation of track metadata
        """
        parts = [f"Track: {self.name}", f"Artist: {self.artist}"]
        if self.album:
            parts.append(f"Album: {self.album}")
        if self.genre:
            parts.append(f"Genre: {self.genre}")
        if self.year:
            parts.append(f"Year: {self.year}")
        if self.bpm:
            parts.append(f"BPM: {self.bpm}")
        return " | ".join(parts)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Track:
        """Create Track from dictionary (from Apple Music API).

        Args:
            data: Dictionary with track metadata

        Returns:
            Track instance
        """
        return Track(
            track_id=data.get("persistent_id", data.get("id", "")),
            name=data.get("name", ""),
            artist=data.get("artist", ""),
            album=data.get("album"),
            genre=data.get("genre"),
            year=data.get("year"),
            bpm=data.get("bpm"),
        )


@dataclass
class Playlist:
    """Represents a music playlist - used by all three features.

    Attributes:
        playlist_id: Persistent ID from Music.app (hex format)
        name: Playlist name
        tracks: List of tracks in playlist
        folder_path: Path in Music.app folder structure (optional)
        description: Playlist description (optional)
        track_count: Number of tracks (cached for performance)
    """

    playlist_id: str
    name: str
    tracks: List[Track] = field(default_factory=list)
    folder_path: Optional[str] = None
    description: Optional[str] = None
    track_count: int = 0

    def __post_init__(self):
        """Validate and set track_count after initialization."""
        if not self.track_count and self.tracks:
            self.track_count = len(self.tracks)

    def get_metadata_string(self) -> str:
        """Return playlist metadata as a formatted string.

        Returns:
            String representation of playlist metadata
        """
        parts = [f"Playlist: {self.name}"]
        if self.folder_path:
            parts.append(f"Folder: {self.folder_path}")
        if self.description:
            parts.append(f"Description: {self.description}")
        parts.append(f"Tracks: {self.track_count}")
        return " | ".join(parts)

    @staticmethod
    def from_dict(data: Dict[str, Any], tracks: Optional[List[Track]] = None) -> Playlist:
        """Create Playlist from dictionary (from Apple Music API).

        Args:
            data: Dictionary with playlist metadata
            tracks: Optional list of Track objects

        Returns:
            Playlist instance
        """
        return Playlist(
            playlist_id=data.get("persistent_id", data.get("id", "")),
            name=data.get("name", ""),
            tracks=tracks or [],
            folder_path=data.get("folder_path"),
            description=data.get("description"),
            track_count=data.get("track_count", len(tracks or [])),
        )


@dataclass
class ClassificationResult:
    """Result of temperament classification (from 4tempers feature).

    Attributes:
        temperament: Temperament category assigned
        confidence: Confidence score (0.0 to 1.0)
        reasoning: Explanation for the classification
    """

    temperament: Temperament
    confidence: float
    reasoning: str


@dataclass
class GenreClassificationResult:
    """Result of genre classification (from plsort feature).

    Attributes:
        genre: Genre assigned (hip-hop, electronic, jazz, etc)
        confidence: Confidence score (0.0 to 1.0)
        method: Method used for classification
        scores: Dictionary of genre scores
    """

    genre: str
    confidence: float
    method: str
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class MetadataEnrichmentResult:
    """Result of metadata enrichment operation (from metad_enr feature).

    Attributes:
        success: Whether operation completed successfully
        track_id: ID of enriched track
        fields_added: Which metadata fields were added/updated
        source: Which API source provided the data
        error: Error message if operation failed
    """

    success: bool
    track_id: str
    fields_added: List[str] = field(default_factory=list)
    source: Optional[str] = None
    error: Optional[str] = None


@dataclass
class OperationResult:
    """Unified result structure for all features.

    Attributes:
        success: Overall success of operation
        target: Playlist or folder name that was processed
        operation_type: Type of operation (temperament, enrich, organize)
        processed: Count of items processed
        enriched: Count of items successfully enriched
        skipped: Count of items skipped
        errors: Count of items with errors
        details: Additional operation-specific details
    """

    success: bool
    target: str
    operation_type: str  # 'temperament', 'enrich', 'organize'
    processed: int = 0
    enriched: int = 0
    skipped: int = 0
    errors: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization.

        Returns:
            Dictionary representation of result
        """
        return {
            "success": self.success,
            "target": self.target,
            "operation_type": self.operation_type,
            "processed": self.processed,
            "enriched": self.enriched,
            "skipped": self.skipped,
            "errors": self.errors,
            "details": self.details,
        }
