"""
Track Metadata Clients

Fetches enriched track information from online databases/APIs.
Supports multiple providers: Spotify, MusicBrainz, etc.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, cast

import requests

logger = logging.getLogger(__name__)


@dataclass
class EnrichedTrackInfo:
    """Extended track information from online sources"""

    name: str
    artist: str
    album: Optional[str] = None
    genre: Optional[str] = None
    mood: Optional[str] = None
    energy: Optional[float] = None  # 0-1
    popularity: Optional[float] = None  # 0-1
    release_year: Optional[int] = None
    danceability: Optional[float] = None  # 0-1
    explicit: Optional[bool] = None
    preview_url: Optional[str] = None


class TrackMetadataClient(ABC):
    """Abstract interface for fetching track metadata from online sources"""

    @abstractmethod
    def get_track_info(self, track_name: str, artist_name: str) -> Optional[EnrichedTrackInfo]:
        """Fetch enriched track information"""
        pass


class SpotifyTrackMetadataClient(TrackMetadataClient):
    """Fetch track metadata from Spotify API"""

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        import os

        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
        self.access_token = None
        self.base_url = "https://api.spotify.com/v1"

        if self.client_id and self.client_secret:
            self._authenticate()
        else:
            logger.warning(
                "Spotify credentials not set. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET"
            )

    def _authenticate(self):
        """Get Spotify API access token"""
        try:
            auth_url = "https://accounts.spotify.com/api/token"
            response = requests.post(
                auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            self.access_token = response.json()["access_token"]
            logger.info("Spotify authentication successful")
        except Exception as e:
            logger.error(f"Spotify authentication failed: {e}")
            self.access_token = None

    def get_track_info(self, track_name: str, artist_name: str) -> Optional[EnrichedTrackInfo]:
        """Fetch track info from Spotify"""
        if not self.access_token:
            return None

        try:
            # Search for track
            headers = {"Authorization": f"Bearer {self.access_token}"}
            search_query = f"{track_name} artist:{artist_name}"

            response = requests.get(
                f"{self.base_url}/search",
                headers=headers,
                params={"q": search_query, "type": "track", "limit": 1},
            )
            response.raise_for_status()

            results = response.json()
            if not results["tracks"]["items"]:
                return None

            track = results["tracks"]["items"][0]

            # Get audio features
            audio_features = None
            try:
                af_response = requests.get(
                    f"{self.base_url}/audio-features/{track['id']}", headers=headers
                )
                af_response.raise_for_status()
                audio_features = af_response.json()
            except:
                pass

            return EnrichedTrackInfo(
                name=track["name"],
                artist=track["artists"][0]["name"] if track["artists"] else artist_name,
                album=track["album"]["name"],
                genre=None,  # Spotify tracks don't have genre; need to get from artist
                energy=audio_features.get("energy") if audio_features else None,
                danceability=audio_features.get("danceability") if audio_features else None,
                popularity=track["popularity"] / 100,
                release_year=(
                    int(track["album"]["release_date"].split("-")[0])
                    if track["album"]["release_date"]
                    else None
                ),
                explicit=track["explicit"],
                preview_url=track["preview_url"],
            )

        except Exception as e:
            logger.debug(f"Failed to get Spotify info for {track_name} by {artist_name}: {e}")
            return None


class MusicBrainzTrackMetadataClient(TrackMetadataClient):
    """Fetch track metadata from MusicBrainz API (free, no auth required)"""

    def __init__(self):
        self.base_url = "https://musicbrainz.org/ws/2"
        self.headers = {
            "User-Agent": "TemperamentAnalyzer/1.0 (https://github.com/yourusername/4tempers)"
        }

    def get_track_info(self, track_name: str, artist_name: str) -> Optional[EnrichedTrackInfo]:
        """Fetch track info from MusicBrainz"""
        try:
            search_query = f'"{track_name}" AND artist:"{artist_name}"'

            response = requests.get(
                f"{self.base_url}/recording",
                headers=self.headers,
                params={"query": search_query, "limit": 1, "fmt": "json"},  # type: ignore[arg-type]
            )
            response.raise_for_status()

            results = response.json()
            if not results["recordings"]:
                return None

            recording = results["recordings"][0]

            # Get release info
            release_year = None
            if recording.get("releases"):
                release = recording["releases"][0]
                if release.get("date"):
                    release_year = int(release["date"].split("-")[0])

            return EnrichedTrackInfo(
                name=recording["title"],
                artist=(
                    recording["artist-credit"][0]["name"]
                    if recording.get("artist-credit")
                    else artist_name
                ),
                album=recording["releases"][0]["title"] if recording.get("releases") else None,
                release_year=release_year,
                genre=None,  # MusicBrainz doesn't expose genre via this API
            )

        except Exception as e:
            logger.debug(f"Failed to get MusicBrainz info for {track_name} by {artist_name}: {e}")
            return None


class MockTrackMetadataClient(TrackMetadataClient):
    """Mock metadata client for testing without external APIs"""

    def get_track_info(self, track_name: str, artist_name: str) -> Optional[EnrichedTrackInfo]:
        """Return mock enriched track info"""
        return EnrichedTrackInfo(
            name=track_name, artist=artist_name, energy=0.6, danceability=0.5, popularity=0.7
        )
