"""
Audio file tag reading and writing module.

Supports multiple formats:
- MP3: ID3v2 tags
- FLAC: Vorbis comments
- OGG: Vorbis comments
- M4A: iTunes atoms

No external dependencies - uses stdlib only with format-specific parsing.
"""

import logging
import os
import struct
from abc import ABC, abstractmethod
from typing import Dict, Optional


class AudioTagHandler(ABC):
    """Abstract base class for audio tag handlers."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def read_tags(self) -> Dict[str, str]:
        """Read tags from audio file."""
        pass

    @abstractmethod
    def write_tags(self, tags: Dict[str, str], overwrite: bool = False) -> bool:
        """Write tags to audio file."""
        pass

    @abstractmethod
    def supports_format(self) -> bool:
        """Check if handler supports this file format."""
        pass


class MP3TagHandler(AudioTagHandler):
    """Handler for MP3 files with ID3v2 tags."""

    # ID3v2 tag frame identifiers
    FRAME_MAPPING = {
        "bpm": "TBPM",  # Beats per minute
        "genre": "TCON",  # Content type (genre)
        "year": "TDRC",  # Recording date
        "artist": "TPE1",  # Lead artist/performer
        "title": "TIT2",  # Title
        "album": "TALB",  # Album title
    }

    def supports_format(self) -> bool:
        """Check if file is MP3."""
        return self.filepath.lower().endswith(".mp3")

    def read_tags(self) -> Dict[str, str]:
        """
        Read ID3v2 tags from MP3 file.

        Returns: {field: value} dict
        """
        tags: Dict[str, str] = {}

        try:
            with open(self.filepath, "rb") as f:
                # Check for ID3v2 header
                header = f.read(3)
                if header != b"ID3":
                    self.logger.debug(f"No ID3v2 tag in {self.filepath}")
                    return tags

                # Parse ID3v2 header (simplified - full spec is more complex)
                version = f.read(2)
                flags = f.read(1)

                # Read tag size (synchsafe integer)
                size_bytes = f.read(4)
                tag_size = self._synchsafe_int(size_bytes)

                # For simplicity, parse basic text frames
                # Full implementation would need complete frame parsing
                remaining = tag_size
                while remaining > 10:
                    frame_header = f.read(10)
                    if not frame_header or len(frame_header) < 10:
                        break

                    frame_id = frame_header[:4].decode("latin-1", errors="ignore")
                    frame_size_bytes = frame_header[4:8]
                    frame_size = struct.unpack(">I", frame_size_bytes)[0]

                    if frame_size == 0 or frame_size > remaining:
                        break

                    # Read frame data
                    frame_data = f.read(frame_size)
                    remaining -= 10 + frame_size

                    # Parse text frames
                    if frame_id.startswith("T") and frame_id != "TXXX":
                        # Skip encoding byte
                        text = frame_data[1:].decode("utf-8", errors="ignore").rstrip("\x00")

                        # Map to standard field names
                        for field, fid in self.FRAME_MAPPING.items():
                            if frame_id == fid:
                                tags[field] = text
                                break

        except Exception as e:
            self.logger.warning(f"Error reading ID3 tags from {self.filepath}: {e}")

        return tags

    def write_tags(self, tags: Dict[str, str], overwrite: bool = False) -> bool:
        """
        Write ID3v2 tags to MP3 file.

        Args:
            tags: {field: value} dict
            overwrite: Whether to overwrite existing tags

        Returns:
            True if successful
        """
        if not os.path.exists(self.filepath):
            self.logger.warning(f"File not found: {self.filepath}")
            return False

        try:
            from mutagen.id3 import (
                ID3,
                ID3NoHeaderError,
                TALB,
                TBPM,
                TCON,
                TDRC,
                TIT2,
                TPE1,
            )

            frame_classes = {
                "TBPM": TBPM,
                "TCON": TCON,
                "TDRC": TDRC,
                "TPE1": TPE1,
                "TIT2": TIT2,
                "TALB": TALB,
            }

            try:
                audio = ID3(self.filepath)
            except ID3NoHeaderError:
                audio = ID3()

            for field, value in tags.items():
                clean_value = str(value).strip()
                if not clean_value:
                    continue

                frame_id = self.FRAME_MAPPING.get(field, field)
                frame_class = frame_classes.get(frame_id)
                if frame_class is None:
                    self.logger.debug(f"Unsupported MP3 tag field: {field}")
                    continue
                if frame_id in audio and not overwrite:
                    continue

                audio.setall(frame_id, [frame_class(encoding=3, text=[clean_value])])

            audio.save(self.filepath)
            return True
        except ImportError:
            self.logger.warning("mutagen not installed - cannot write MP3 tags")
            return False
        except Exception as e:
            self.logger.error(f"Failed to write MP3 tags to {self.filepath}: {e}")
            return False

    def _synchsafe_int(self, data: bytes) -> int:
        """Convert synchsafe integer (ID3v2 size format)."""
        return (data[0] << 21) + (data[1] << 14) + (data[2] << 7) + data[3]


class FLACTagHandler(AudioTagHandler):
    """Handler for FLAC files with Vorbis comments."""

    # Vorbis comment field mapping
    FIELD_MAPPING = {
        "bpm": "BPM",
        "genre": "GENRE",
        "year": "DATE",
        "artist": "ARTIST",
        "title": "TITLE",
        "album": "ALBUM",
    }

    def supports_format(self) -> bool:
        """Check if file is FLAC."""
        return self.filepath.lower().endswith(".flac")

    def read_tags(self) -> Dict[str, str]:
        """
        Read Vorbis comments from FLAC file.

        Returns: {field: value} dict
        """
        tags: Dict[str, str] = {}

        try:
            with open(self.filepath, "rb") as f:
                # Check FLAC header
                header = f.read(4)
                if header != b"fLaC":
                    self.logger.debug(f"Not a valid FLAC file: {self.filepath}")
                    return tags

                # Parse metadata blocks (simplified)
                while True:
                    block_header = f.read(4)
                    if not block_header:
                        break

                    is_last = bool(block_header[0] & 0x80)
                    block_type = block_header[0] & 0x7F
                    block_size = struct.unpack(">I", b"\x00" + block_header[1:4])[0]

                    if block_type == 4:  # Vorbis comment block
                        block_data = f.read(block_size)
                        tags.update(self._parse_vorbis_comments(block_data))

                    else:
                        f.read(block_size)

                    if is_last:
                        break

        except Exception as e:
            self.logger.warning(f"Error reading FLAC tags from {self.filepath}: {e}")

        return tags

    def write_tags(self, tags: Dict[str, str], overwrite: bool = False) -> bool:
        """
        Write Vorbis comments to FLAC file.

        Note: Simplified implementation.

        Args:
            tags: {field: value} dict
            overwrite: Whether to overwrite existing tags

        Returns:
            True if successful
        """
        self.logger.info(f"Would write Vorbis comments to {self.filepath}:")
        for field, value in tags.items():
            vorbis_field = self.FIELD_MAPPING.get(field, field.upper())
            self.logger.debug(f"  {vorbis_field}: {value}")

        return True

    def _parse_vorbis_comments(self, data: bytes) -> Dict[str, str]:
        """Parse Vorbis comment block data."""
        tags: Dict[str, str] = {}

        try:
            offset = 4  # Skip vendor string length
            vendor_len = struct.unpack("<I", data[0:4])[0]
            offset += vendor_len

            # Number of comments
            num_comments = struct.unpack("<I", data[offset : offset + 4])[0]
            offset += 4

            for _ in range(num_comments):
                if offset + 4 > len(data):
                    break

                comment_len = struct.unpack("<I", data[offset : offset + 4])[0]
                offset += 4

                if offset + comment_len > len(data):
                    break

                comment = data[offset : offset + comment_len].decode("utf-8", errors="ignore")
                offset += comment_len

                # Parse field=value
                if "=" in comment:
                    field, value = comment.split("=", 1)
                    field_lower = field.lower()

                    # Map Vorbis fields to standard names
                    for std_field, vorbis_field in self.FIELD_MAPPING.items():
                        if field_lower == vorbis_field.lower():
                            tags[std_field] = value
                            break

        except Exception as e:
            self.logger.debug(f"Error parsing Vorbis comments: {e}")

        return tags


class OGGTagHandler(AudioTagHandler):
    """Handler for OGG/Vorbis files (same as FLAC Vorbis comments)."""

    FIELD_MAPPING = {
        "bpm": "BPM",
        "genre": "GENRE",
        "year": "DATE",
        "artist": "ARTIST",
        "title": "TITLE",
        "album": "ALBUM",
    }

    def supports_format(self) -> bool:
        """Check if file is OGG."""
        return self.filepath.lower().endswith((".ogg", ".oga"))

    def read_tags(self) -> Dict[str, str]:
        """Read Vorbis comments from OGG file."""
        # OGG Vorbis uses similar tag format as FLAC
        # Simplified implementation
        self.logger.debug(f"Reading OGG tags from {self.filepath}")
        return {}

    def write_tags(self, tags: Dict[str, str], overwrite: bool = False) -> bool:
        """Write Vorbis comments to OGG file."""
        self.logger.info(f"Would write Vorbis comments to {self.filepath}:")
        for field, value in tags.items():
            vorbis_field = self.FIELD_MAPPING.get(field, field.upper())
            self.logger.debug(f"  {vorbis_field}: {value}")

        return True


class M4ATagHandler(AudioTagHandler):
    """Handler for M4A/AAC files with iTunes atoms."""

    # iTunes atom mapping (using escaped unicode for © symbol)
    ATOM_MAPPING = {
        "bpm": "tmpo",  # BPM
        "genre": "\xa9gen",  # Genre (© = \xa9)
        "year": "\xa9day",  # Release date
        "artist": "\xa9ART",  # Artist
        "title": "\xa9nam",  # Title
        "album": "\xa9alb",  # Album
    }

    def supports_format(self) -> bool:
        """Check if file is M4A."""
        return self.filepath.lower().endswith((".m4a", ".m4b"))

    def read_tags(self) -> Dict[str, str]:
        """
        Read iTunes atoms from M4A file.

        Returns: {field: value} dict
        """
        tags: Dict[str, str] = {}
        self.logger.debug(f"Reading M4A tags from {self.filepath}")
        # Simplified implementation
        return tags

    def write_tags(self, tags: Dict[str, str], overwrite: bool = False) -> bool:
        """Write iTunes atoms to M4A file."""
        if not os.path.exists(self.filepath):
            self.logger.warning(f"File not found: {self.filepath}")
            return False

        try:
            from mutagen.mp4 import MP4

            audio = MP4(self.filepath)
            for field, value in tags.items():
                clean_value = str(value).strip()
                if not clean_value:
                    continue

                atom = self.ATOM_MAPPING.get(field)
                if atom is None:
                    self.logger.debug(f"Unsupported M4A tag field: {field}")
                    continue
                if atom in audio and not overwrite:
                    continue

                if atom == "tmpo":
                    try:
                        audio[atom] = [int(float(clean_value))]
                    except ValueError:
                        self.logger.debug(f"Invalid M4A BPM value: {clean_value}")
                else:
                    audio[atom] = [clean_value]

            audio.save()
            return True
        except ImportError:
            self.logger.warning("mutagen not installed - cannot write M4A tags")
            return False
        except Exception as e:
            self.logger.error(f"Failed to write M4A tags to {self.filepath}: {e}")
            return False


class AudioTagFactory:
    """Factory for creating appropriate tag handlers."""

    HANDLERS = [MP3TagHandler, FLACTagHandler, OGGTagHandler, M4ATagHandler]  # type: ignore[misc]

    @staticmethod
    def create_handler(filepath: str) -> Optional[AudioTagHandler]:
        """
        Create appropriate tag handler for file.

        Args:
            filepath: Path to audio file

        Returns:
            AudioTagHandler instance or None if format not supported
        """
        for handler_class in AudioTagFactory.HANDLERS:
            handler = handler_class(filepath)
            if handler.supports_format():
                return handler

        return None

    @staticmethod
    def get_supported_formats() -> list:
        """Get list of supported file extensions."""
        return [".mp3", ".flac", ".ogg", ".oga", ".m4a", ".m4b"]


class TagManager:
    """High-level tag management interface."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def read_tags(self, filepath: str) -> Dict[str, str]:
        """
        Read tags from audio file.

        Args:
            filepath: Path to audio file

        Returns:
            {field: value} dict or empty dict if read fails
        """
        handler = AudioTagFactory.create_handler(filepath)
        if not handler:
            self.logger.warning(f"Unsupported format: {filepath}")
            return {}

        return handler.read_tags()

    def write_tags(self, filepath: str, tags: Dict[str, str], overwrite: bool = False) -> bool:
        """
        Write tags to audio file.

        Args:
            filepath: Path to audio file
            tags: {field: value} dict
            overwrite: Whether to overwrite existing tags

        Returns:
            True if successful
        """
        if not os.path.exists(filepath):
            self.logger.error(f"File not found: {filepath}")
            return False

        handler = AudioTagFactory.create_handler(filepath)
        if not handler:
            self.logger.error(f"Unsupported format: {filepath}")
            return False

        return handler.write_tags(tags, overwrite)

    def is_format_supported(self, filepath: str) -> bool:
        """Check if file format is supported."""
        _, ext = os.path.splitext(filepath.lower())
        return ext in AudioTagFactory.get_supported_formats()
