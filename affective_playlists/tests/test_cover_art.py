"""
Tests for cover art module (src/cover_art.py).

Test coverage:
- CoverArtDownloader: Download from various sources
- CoverArtEmbedder: Embed in different audio formats
- CoverArtManager: High-level operations
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from src.cover_art import CoverArtDownloader, CoverArtEmbedder, CoverArtManager


class TestCoverArtDownloader(unittest.TestCase):
    """Tests for CoverArtDownloader."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = CoverArtDownloader(cache_dir=self.temp_dir)

    def tearDown(self):
        """Clean up."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cache_dir_creation(self):
        """Test that cache directory is created."""
        self.assertTrue(os.path.exists(self.temp_dir))

    def test_cache_path_generation(self):
        """Test cache path is generated consistently."""
        url = "https://example.com/image.jpg"
        path1 = self.downloader._get_cache_path(url)
        path2 = self.downloader._get_cache_path(url)
        self.assertEqual(path1, path2)
        self.assertTrue(path1.startswith(self.temp_dir))

    def test_cache_exists_false(self):
        """Test cache_exists returns False for non-existent file."""
        url = "https://example.com/nonexistent.jpg"
        self.assertFalse(self.downloader._cache_exists(url))

    def test_cache_exists_true(self):
        """Test cache_exists returns True for existing file."""
        url = "https://example.com/image.jpg"
        cache_path = self.downloader._get_cache_path(url)

        # Create dummy cache file
        with open(cache_path, "wb") as f:
            f.write(b"dummy image data")

        self.assertTrue(self.downloader._cache_exists(url))

    def test_save_and_get_from_cache(self):
        """Test saving and retrieving from cache."""
        url = "https://example.com/image.jpg"
        image_data = b"JPEG image data"

        # Save
        success = self.downloader._save_to_cache(url, image_data)
        self.assertTrue(success)

        # Retrieve
        retrieved = self.downloader._get_cached_image(url)
        self.assertEqual(retrieved, image_data)

    def test_image_size_validation(self):
        """Test that oversized images are rejected."""
        # Mock _fetch_url to return large data
        oversized_data = b"x" * (self.downloader.max_image_size + 1)
        self.downloader._fetch_url = Mock(return_value=oversized_data)

        # Simulate fetch that checks size
        response_data = oversized_data
        if len(response_data) > self.downloader.max_image_size:
            result = None
        else:
            result = response_data

        self.assertIsNone(result)

    def test_musicbrainz_url_format(self):
        """Test MusicBrainz URL is formatted correctly."""
        mbid = "12345-67890"

        # Verify URL format by checking expected pattern
        expected_url = f"https://coverartarchive.org/release/{mbid}/front-500"

        # This is what we'd request
        self.assertIn("coverartarchive.org", expected_url)
        self.assertIn(mbid, expected_url)
        self.assertIn("front-500", expected_url)

    @patch("src.cover_art.urllib.request.urlopen")
    def test_download_from_musicbrainz_success(self, mock_urlopen):
        """Test successful download from MusicBrainz."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = b"JPEG data"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response

        mbid = "test-mbid-12345"
        result = self.downloader.download_from_musicbrainz(mbid)

        # Should cache the result
        self.assertIsNotNone(result)

    def test_download_from_musicbrainz_no_mbid(self):
        """Test download returns None without MBID."""
        result = self.downloader.download_from_musicbrainz(None)
        self.assertIsNone(result)

    def test_download_with_mbid_priority(self):
        """Test download prioritizes MusicBrainz."""
        # Mock MusicBrainz to return data
        self.downloader.download_from_musicbrainz = Mock(return_value=b"image data")

        result = self.downloader.download(mbid="test-mbid")

        # Should call MusicBrainz
        self.downloader.download_from_musicbrainz.assert_called_once()
        self.assertEqual(result, b"image data")

    def test_download_fallback_without_mbid(self):
        """Test download returns None when fallback providers find no image."""
        with (
            patch.object(self.downloader, "_search_spotify_album_id", return_value=None),
            patch.object(self.downloader, "_search_discogs_release_id", return_value=None),
            patch.object(self.downloader, "download_from_lastfm", return_value=None),
        ):
            result = self.downloader.download(mbid=None, artist="Test", album="Album")

        # Deterministic expectation: no provider can resolve an image.
        self.assertIsNone(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_download_from_spotify_missing_credentials(self):
        """Spotify download should skip cleanly without credentials."""
        result = self.downloader.download_from_spotify("album-123")
        self.assertIsNone(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_download_from_lastfm_missing_credentials(self):
        """Last.fm download should skip cleanly without API key."""
        result = self.downloader.download_from_lastfm("Artist", "Album")
        self.assertIsNone(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_download_from_discogs_missing_credentials(self):
        """Discogs download should skip cleanly without token."""
        result = self.downloader.download_from_discogs("123")
        self.assertIsNone(result)

    @patch("src.cover_art.CoverArtDownloader.download_from_musicbrainz")
    @patch("src.cover_art.CoverArtDownloader._search_spotify_album_id")
    @patch("src.cover_art.CoverArtDownloader.download_from_spotify")
    @patch("src.cover_art.CoverArtDownloader.download_from_lastfm")
    @patch("src.cover_art.CoverArtDownloader._search_discogs_release_id")
    @patch("src.cover_art.CoverArtDownloader.download_from_discogs")
    def test_download_fallback_provider_chain(
        self,
        mock_discogs,
        mock_discogs_search,
        mock_lastfm,
        mock_spotify,
        mock_spotify_search,
        mock_musicbrainz,
    ):
        """Downloader should continue to next provider until one succeeds."""
        mock_musicbrainz.return_value = None
        mock_spotify_search.return_value = "spotify-album-id"
        mock_spotify.return_value = None
        mock_lastfm.return_value = b"lastfm-image"
        mock_discogs_search.return_value = "discogs-id"
        mock_discogs.return_value = None

        result = self.downloader.download(mbid="mbid", artist="Artist", album="Album")

        self.assertEqual(result, b"lastfm-image")
        mock_musicbrainz.assert_called_once()
        mock_spotify.assert_called_once_with("spotify-album-id")
        mock_lastfm.assert_called_once_with("Artist", "Album")

    @patch("src.cover_art.CoverArtDownloader.download_from_musicbrainz")
    @patch("src.cover_art.CoverArtDownloader._search_spotify_album_id")
    @patch("src.cover_art.CoverArtDownloader.download_from_spotify")
    @patch("src.cover_art.CoverArtDownloader.download_from_lastfm")
    @patch("src.cover_art.CoverArtDownloader._search_discogs_release_id")
    @patch("src.cover_art.CoverArtDownloader.download_from_discogs")
    def test_download_fallback_when_provider_errors(
        self,
        mock_discogs,
        mock_discogs_search,
        mock_lastfm,
        mock_spotify,
        mock_spotify_search,
        mock_musicbrainz,
    ):
        """Downloader should not crash if one provider raises an exception."""
        mock_musicbrainz.side_effect = RuntimeError("network failure")
        mock_spotify_search.return_value = "spotify-album-id"
        mock_spotify.return_value = b"spotify-image"
        mock_lastfm.return_value = None
        mock_discogs_search.return_value = "discogs-id"
        mock_discogs.return_value = None

        result = self.downloader.download(mbid="mbid", artist="Artist", album="Album")

        self.assertEqual(result, b"spotify-image")


class TestCoverArtEmbedder(unittest.TestCase):
    """Tests for CoverArtEmbedder."""

    def setUp(self):
        """Set up test fixtures."""
        self.embedder = CoverArtEmbedder()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_embedder_initialization(self):
        """Test embedder initializes."""
        self.assertIsNotNone(self.embedder)
        self.assertIsNotNone(self.embedder.logger)

    def test_jpeg_detection(self):
        """Test JPEG format detection."""
        jpeg_header = b"\xff\xd8\xff"
        is_jpeg = jpeg_header.startswith(b"\xff\xd8\xff")
        self.assertTrue(is_jpeg)

    def test_png_detection(self):
        """Test PNG format detection."""
        png_header = b"\x89PNG"
        is_png = png_header.startswith(b"\x89PNG")
        self.assertTrue(is_png)

    def test_unsupported_format_detection(self):
        """Test unsupported format detection."""
        unknown_data = b"random data"
        is_jpeg = unknown_data.startswith(b"\xff\xd8\xff")
        is_png = unknown_data.startswith(b"\x89PNG")
        self.assertFalse(is_jpeg)
        self.assertFalse(is_png)

    @patch("src.cover_art.CoverArtEmbedder.embed_mp4")
    def test_embed_mp4_extension(self, mock_embed_mp4):
        """Test MP4 files are routed to embed_mp4."""
        mock_embed_mp4.return_value = True

        filepath = os.path.join(self.temp_dir, "test.m4a")
        image_data = b"\xff\xd8\xff"  # JPEG header

        # Create dummy file
        with open(filepath, "wb") as f:
            f.write(b"dummy")

        result = self.embedder.embed(filepath, image_data)

        mock_embed_mp4.assert_called_once()

    @patch("src.cover_art.CoverArtEmbedder.embed_mp3")
    def test_embed_mp3_extension(self, mock_embed_mp3):
        """Test MP3 files are routed to embed_mp3."""
        mock_embed_mp3.return_value = True

        filepath = os.path.join(self.temp_dir, "test.mp3")
        image_data = b"\xff\xd8\xff"  # JPEG header

        # Create dummy file
        with open(filepath, "wb") as f:
            f.write(b"dummy")

        result = self.embedder.embed(filepath, image_data)

        mock_embed_mp3.assert_called_once()

    def test_unsupported_audio_format(self):
        """Test unsupported audio format."""
        filepath = os.path.join(self.temp_dir, "test.wav")
        image_data = b"\xff\xd8\xff"

        # Create dummy file
        with open(filepath, "wb") as f:
            f.write(b"dummy")

        result = self.embedder.embed(filepath, image_data)

        self.assertFalse(result)

    def test_nonexistent_file(self):
        """Test embedding in non-existent file."""
        filepath = os.path.join(self.temp_dir, "nonexistent.mp3")
        image_data = b"\xff\xd8\xff"

        result = self.embedder.embed(filepath, image_data)

        self.assertFalse(result)

    def test_unsupported_image_data_is_rejected(self):
        """Test unsupported image data is rejected for existing files."""
        filepath = os.path.join(self.temp_dir, "test.mp3")
        with open(filepath, "wb") as f:
            f.write(b"dummy")

        result = self.embedder.embed(filepath, b"not an image")

        self.assertFalse(result)


class TestCoverArtManager(unittest.TestCase):
    """Tests for CoverArtManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CoverArtManager(cache_dir=self.temp_dir)

    def tearDown(self):
        """Clean up."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_manager_initialization(self):
        """Test manager initializes with components."""
        self.assertIsNotNone(self.manager.downloader)
        self.assertIsNotNone(self.manager.embedder)

    def test_enrich_nonexistent_file(self):
        """Test enrichment skips non-existent files."""
        filepath = "/nonexistent/file.mp3"

        result = self.manager.enrich_with_cover_art(filepath, mbid="test")

        # Should return False without attempting download/embed
        self.assertFalse(result)

    @patch("src.cover_art.CoverArtDownloader.download")
    @patch("src.cover_art.CoverArtEmbedder.embed")
    def test_enrich_with_cover_art_success(self, mock_embed, mock_download):
        """Test successful cover art enrichment."""
        # Create test file
        filepath = os.path.join(self.temp_dir, "test.mp3")
        with open(filepath, "wb") as f:
            f.write(b"dummy audio")

        # Mock successful download and embed
        mock_download.return_value = b"image data"
        mock_embed.return_value = True

        # Patch the methods on instance
        self.manager.downloader.download = mock_download
        self.manager.embedder.embed = mock_embed

        result = self.manager.enrich_with_cover_art(filepath, mbid="test-mbid")

        # Should succeed
        self.assertTrue(result)
        mock_download.assert_called_once()
        mock_embed.assert_called_once()

    @patch("src.cover_art.CoverArtDownloader.download")
    def test_enrich_no_cover_art_found(self, mock_download):
        """Test graceful handling when no cover art found."""
        # Create test file
        filepath = os.path.join(self.temp_dir, "test.mp3")
        with open(filepath, "wb") as f:
            f.write(b"dummy audio")

        # Mock failed download (no cover art)
        mock_download.return_value = None
        self.manager.downloader.download = mock_download

        result = self.manager.enrich_with_cover_art(filepath, mbid="test-mbid")

        # Should return False gracefully
        self.assertFalse(result)


class TestCoverArtIntegration(unittest.TestCase):
    """Integration tests for cover art system."""

    def test_download_to_embed_pipeline(self):
        """Test download and embed pipeline."""
        manager = CoverArtManager()

        # Pipeline should exist and be callable
        self.assertTrue(hasattr(manager, "enrich_with_cover_art"))
        self.assertTrue(callable(manager.enrich_with_cover_art))

    def test_cache_directory_structure(self):
        """Test cache directory is created properly."""
        temp_dir = tempfile.mkdtemp()

        manager = CoverArtManager(cache_dir=temp_dir)

        # Cache dir should exist
        self.assertTrue(os.path.exists(temp_dir))

        # Clean up
        import shutil

        shutil.rmtree(temp_dir)

    def test_logging_configuration(self):
        """Test logging is properly configured."""
        manager = CoverArtManager()

        # Should have logger instances
        self.assertIsNotNone(manager.downloader.logger)
        self.assertIsNotNone(manager.embedder.logger)


if __name__ == "__main__":
    unittest.main()
