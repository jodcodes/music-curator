"""
Cover art downloading and embedding module for metadata enrichment.

LAYER: Data Layer - Cover Art Management
ROLE: Download and embed cover art for tracks
ARCHITECTURE: See src/README.md for full architecture

Sources for cover art:
1. MusicBrainz (via CoverArtArchive API)
2. Spotify (via album artwork)
3. Last.fm (via album images)
4. Discogs (via album covers)

Features:
- Download cover art from multiple sources
- Cache downloaded images to avoid re-downloads
- Embed artwork in audio files (MP4, MP3)
- Validate image format and size
- Handle fallback sources gracefully
"""

import urllib.request
import urllib.parse
import os
import json
import hashlib
import base64
import logging
from typing import Optional, Tuple
from src.http_utils import HttpClient


class CoverArtDownloader:
    """Download cover art from multiple sources."""

    def __init__(
        self, cache_dir: str = "data/cache/cover_art", logger: Optional[logging.Logger] = None
    ):
        """
        Initialize CoverArtDownloader.

        Args:
            cache_dir: Directory to cache downloaded images
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.http = HttpClient(logger=self.logger, user_agent="metad-fill/1.0")
        self.cache_dir = cache_dir
        self._ensure_cache_dir()

        # Config
        self.max_image_size = 5_000_000  # 5MB max
        self.timeout = 10  # seconds
        self.valid_formats = {".jpg", ".jpeg", ".png", ".gif"}

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        os.makedirs(self.cache_dir, exist_ok=True)

    def _fetch_url(self, url: str) -> Optional[bytes]:
        """Fetch binary content from URL."""
        data = self.http.fetch_bytes(url, timeout=self.timeout)
        if data is None:
            self.logger.debug(f"Failed to fetch {url}")
            return None
        if len(data) > self.max_image_size:
            self.logger.warning(f"Image too large: {len(data)} bytes, max {self.max_image_size}")
            return None
        return data

    def _fetch_json(
        self, url: str, headers: Optional[dict] = None, data: Optional[bytes] = None
    ) -> Optional[dict]:
        """Fetch and decode JSON from URL."""
        parsed = self.http.fetch_json(url, timeout=self.timeout, headers=headers, data=data)
        if parsed is None:
            self.logger.debug(f"event=cover_art_json_fetch_failed url={url}")
        return parsed

    def _get_cache_path(self, url: str) -> str:
        """Generate cache file path from URL hash."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.jpg")

    def _cache_exists(self, url: str) -> bool:
        """Check if cover art is cached."""
        return os.path.exists(self._get_cache_path(url))

    def _get_cached_image(self, url: str) -> Optional[bytes]:
        """Get cached image bytes."""
        cache_path = self._get_cache_path(url)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    return f.read()
            except Exception as e:
                self.logger.debug(f"Failed to read cache: {e}")
        return None

    def _save_to_cache(self, url: str, data: bytes) -> bool:
        """Save image to cache."""
        try:
            cache_path = self._get_cache_path(url)
            with open(cache_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            self.logger.debug(f"Failed to save to cache: {e}")
            return False

    def download_from_musicbrainz(self, mbid: str) -> Optional[bytes]:
        """
        Download cover art from CoverArtArchive (MusicBrainz).

        Args:
            mbid: MusicBrainz release ID

        Returns:
            Image bytes or None if not found
        """
        if not mbid:
            return None

        url = f"https://coverartarchive.org/release/{mbid}/front-500"

        # Check cache
        if self._cache_exists(url):
            return self._get_cached_image(url)

        # Download
        self.logger.debug(f"Downloading cover art from MusicBrainz: {mbid}")
        data = self._fetch_url(url)

        if data:
            self._save_to_cache(url, data)
            return data

        return None

    def download_from_spotify(self, album_id: str) -> Optional[bytes]:
        """
        Download cover art from Spotify.

        Args:
            album_id: Spotify album ID

        Returns:
            Image bytes or None if not found
        """
        if not album_id:
            return None

        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            self.logger.debug(
                "event=cover_art_provider_skipped provider=spotify reason=missing_credentials "
                "missing=SPOTIFY_CLIENT_ID,SPOTIFY_CLIENT_SECRET"
            )
            return None

        auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
        token_data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        token_json = self._fetch_json(
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=token_data,
        )
        if not token_json or not token_json.get("access_token"):
            self.logger.debug(
                "event=cover_art_provider_failed provider=spotify reason=token_fetch_failed"
            )
            return None

        album_json = self._fetch_json(
            f"https://api.spotify.com/v1/albums/{urllib.parse.quote(album_id)}",
            headers={"Authorization": f"Bearer {token_json['access_token']}"},
        )
        if not album_json:
            self.logger.debug(
                "event=cover_art_provider_failed provider=spotify reason=album_fetch_failed"
            )
            return None

        images = album_json.get("images", [])
        if not images:
            self.logger.debug("event=cover_art_provider_failed provider=spotify reason=no_images")
            return None

        image_url = images[0].get("url")
        if not image_url:
            return None

        if self._cache_exists(image_url):
            return self._get_cached_image(image_url)

        data = self._fetch_url(image_url)
        if data:
            self._save_to_cache(image_url, data)
            return data

        return None

    def download_from_lastfm(self, artist: str, album: str) -> Optional[bytes]:
        """
        Download cover art from Last.fm.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            Image bytes or None if not found
        """
        if not artist or not album:
            return None

        api_key = os.environ.get("LASTFM_API_KEY")
        if not api_key:
            self.logger.debug(
                "event=cover_art_provider_skipped provider=lastfm reason=missing_credentials missing=LASTFM_API_KEY"
            )
            return None

        query = urllib.parse.urlencode(
            {
                "method": "album.getinfo",
                "api_key": api_key,
                "artist": artist,
                "album": album,
                "format": "json",
            }
        )
        data = self._fetch_json(f"https://ws.audioscrobbler.com/2.0/?{query}")
        if not data:
            self.logger.debug(
                "event=cover_art_provider_failed provider=lastfm reason=api_request_failed"
            )
            return None

        images = data.get("album", {}).get("image", [])
        image_url = None
        for entry in reversed(images):
            url = entry.get("#text")
            if url:
                image_url = url
                break

        if not image_url:
            self.logger.debug("event=cover_art_provider_failed provider=lastfm reason=no_images")
            return None

        if self._cache_exists(image_url):
            return self._get_cached_image(image_url)

        image_data = self._fetch_url(image_url)
        if image_data:
            self._save_to_cache(image_url, image_data)
            return image_data

        return None

    def download_from_discogs(self, discogs_id: str) -> Optional[bytes]:
        """
        Download cover art from Discogs.

        Args:
            discogs_id: Discogs release ID

        Returns:
            Image bytes or None if not found
        """
        if not discogs_id:
            return None

        token = os.environ.get("DISCOGS_TOKEN")
        if not token:
            self.logger.debug(
                "event=cover_art_provider_skipped provider=discogs reason=missing_credentials missing=DISCOGS_TOKEN"
            )
            return None

        release = self._fetch_json(
            f"https://api.discogs.com/releases/{urllib.parse.quote(str(discogs_id))}",
            headers={"Authorization": f"Discogs token={token}"},
        )
        if not release:
            self.logger.debug(
                "event=cover_art_provider_failed provider=discogs reason=release_fetch_failed"
            )
            return None

        image_url = None
        images = release.get("images", [])
        if images:
            image_url = images[0].get("uri") or images[0].get("uri150")

        if not image_url:
            self.logger.debug("event=cover_art_provider_failed provider=discogs reason=no_images")
            return None

        if self._cache_exists(image_url):
            return self._get_cached_image(image_url)

        image_data = self._fetch_url(image_url)
        if image_data:
            self._save_to_cache(image_url, image_data)
            return image_data

        return None

    def _search_spotify_album_id(self, artist: str, album: str) -> Optional[str]:
        """Best-effort Spotify album lookup by artist+album name."""
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret or not artist or not album:
            return None

        auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
        token_data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        token_json = self._fetch_json(
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=token_data,
        )
        access_token = token_json.get("access_token") if token_json else None
        if not access_token:
            return None

        query = urllib.parse.quote(f"album:{album} artist:{artist}")
        search = self._fetch_json(
            f"https://api.spotify.com/v1/search?q={query}&type=album&limit=1",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        items = search.get("albums", {}).get("items", []) if search else []
        if not items:
            return None
        return items[0].get("id")

    def _search_discogs_release_id(self, artist: str, album: str) -> Optional[str]:
        """Best-effort Discogs release lookup by artist+album."""
        token = os.environ.get("DISCOGS_TOKEN")
        if not token or not artist or not album:
            return None

        query = urllib.parse.urlencode(
            {"artist": artist, "release_title": album, "type": "release", "per_page": 1}
        )
        search = self._fetch_json(
            f"https://api.discogs.com/database/search?{query}",
            headers={"Authorization": f"Discogs token={token}"},
        )
        results = search.get("results", []) if search else []
        if not results:
            return None
        return str(results[0].get("id")) if results[0].get("id") else None

    def download(
        self,
        mbid: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        spotify_album_id: Optional[str] = None,
        discogs_id: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Download cover art using priority order.

        Priority:
        1. MusicBrainz (CoverArtArchive) - Most reliable
        2. Spotify - Better quality
        3. Last.fm - User community
        4. Discogs - Vinyl database

        Args:
            mbid: MusicBrainz release ID (best option)
            artist: Artist name
            album: Album name

        Returns:
            Image bytes or None
        """
        providers = []

        if mbid:
            providers.append(("musicbrainz", lambda: self.download_from_musicbrainz(mbid)))

        resolved_spotify_album_id = spotify_album_id or self._search_spotify_album_id(
            artist or "", album or ""
        )
        if resolved_spotify_album_id:
            providers.append(
                ("spotify", lambda: self.download_from_spotify(resolved_spotify_album_id))
            )

        if artist and album:
            providers.append(("lastfm", lambda: self.download_from_lastfm(artist, album)))

        resolved_discogs_id = discogs_id or self._search_discogs_release_id(
            artist or "", album or ""
        )
        if resolved_discogs_id:
            providers.append(("discogs", lambda: self.download_from_discogs(resolved_discogs_id)))

        for provider_name, provider_fn in providers:
            try:
                data = provider_fn()
                if data:
                    self.logger.debug(f"event=cover_art_provider_success provider={provider_name}")
                    return data
                self.logger.debug(f"event=cover_art_provider_no_result provider={provider_name}")
            except Exception as e:
                self.logger.warning(
                    f"event=cover_art_provider_failed provider={provider_name} error={e}"
                )

        self.logger.debug("event=cover_art_provider_exhausted reason=no_provider_returned_image")
        return None


class CoverArtEmbedder:
    """Embed cover art in audio files."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize CoverArtEmbedder."""
        self.logger = logger or logging.getLogger(__name__)

    def embed_mp4(self, filepath: str, image_data: bytes) -> bool:
        """
        Embed cover art in MP4/M4A file.

        Args:
            filepath: Path to audio file
            image_data: Image bytes to embed

        Returns:
            True if successful
        """
        try:
            from mutagen.mp4 import MP4

            audio = MP4(filepath)

            # Import needed for MP4 cover art
            from mutagen.mp4 import MP4Cover

            # Determine format
            if image_data.startswith(b"\xff\xd8\xff"):  # JPEG
                cover_format = MP4Cover.FORMAT_JPEG
            elif image_data.startswith(b"\x89PNG"):  # PNG
                cover_format = MP4Cover.FORMAT_PNG
            else:
                self.logger.warning(f"Unknown image format for {filepath}")
                return False

            # Set cover art
            audio["covr"] = [MP4Cover(image_data, cover_format)]
            audio.save()

            self.logger.debug(f"Embedded cover art in MP4: {filepath}")
            return True

        except ImportError:
            self.logger.warning("mutagen not installed - cannot embed MP4 cover art")
            return False
        except Exception as e:
            self.logger.error(f"Failed to embed cover art in MP4: {e}")
            return False

    def embed_mp3(self, filepath: str, image_data: bytes) -> bool:
        """
        Embed cover art in MP3 file.

        Args:
            filepath: Path to audio file
            image_data: Image bytes to embed

        Returns:
            True if successful
        """
        try:
            from mutagen.id3 import ID3, APIC

            # Load or create ID3 tags
            try:
                audio = ID3(filepath)
            except Exception as e:
                self.logger.debug(f"event=id3_load_failed filepath={filepath} error={e}")
                audio = ID3()

            # Determine format
            if image_data.startswith(b"\xff\xd8\xff"):  # JPEG
                mime_type = "image/jpeg"
            elif image_data.startswith(b"\x89PNG"):  # PNG
                mime_type = "image/png"
            else:
                self.logger.warning(f"Unknown image format for {filepath}")
                return False

            # Add picture frame
            audio["APIC"] = APIC(
                encoding=3, mime=mime_type, type=3, desc="Cover", data=image_data  # Cover (front)
            )

            audio.save(filepath)
            self.logger.debug(f"Embedded cover art in MP3: {filepath}")
            return True

        except ImportError:
            self.logger.warning("mutagen not installed - cannot embed MP3 cover art")
            return False
        except Exception as e:
            self.logger.error(f"Failed to embed cover art in MP3: {e}")
            return False

    def embed(self, filepath: str, image_data: bytes) -> bool:
        """
        Embed cover art in audio file.

        Args:
            filepath: Path to audio file
            image_data: Image bytes

        Returns:
            True if successful
        """
        if not os.path.exists(filepath):
            self.logger.warning(f"File not found: {filepath}")
            return False

        ext = os.path.splitext(filepath)[1].lower()

        if ext in {".m4a", ".mp4"}:
            return self.embed_mp4(filepath, image_data)
        elif ext in {".mp3"}:
            return self.embed_mp3(filepath, image_data)
        else:
            self.logger.warning(f"Unsupported audio format: {ext}")
            return False


class CoverArtManager:
    """High-level cover art management."""

    def __init__(
        self, cache_dir: str = "data/cache/cover_art", logger: Optional[logging.Logger] = None
    ):
        """Initialize CoverArtManager."""
        self.logger = logger or logging.getLogger(__name__)
        self.downloader = CoverArtDownloader(cache_dir, logger)
        self.embedder = CoverArtEmbedder(logger)

    def enrich_with_cover_art(
        self,
        filepath: str,
        mbid: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
    ) -> bool:
        """
        Download and embed cover art.

        Args:
            filepath: Path to audio file
            mbid: MusicBrainz release ID
            artist: Artist name (for fallback)
            album: Album name (for fallback)

        Returns:
            True if cover art was successfully embedded
        """
        if not os.path.exists(filepath):
            self.logger.warning(f"File not found: {filepath}")
            return False

        # Download cover art
        image_data = self.downloader.download(mbid, artist, album)
        if not image_data:
            self.logger.debug(f"No cover art found for {filepath}")
            return False

        # Embed in audio file
        success = self.embedder.embed(filepath, image_data)
        if success:
            self.logger.debug(f"Cover art enriched for {filepath}")

        return success
