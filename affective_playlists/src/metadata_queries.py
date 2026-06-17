"""
Database query modules for metadata enrichment (Data Layer).

LAYER: Data Layer - Query Orchestration
ROLE: Unified interface for querying multiple music databases
ARCHITECTURE: See src/README.md for full architecture

Queries external music databases in priority order with "exact missing fields" strategy:
1. Discogs - Genre, release year, catalog info (vinyl database) - FIRST
2. Last.fm - Genre tags, popularity, user classifications (user-generated)
3. Wikidata - Genre, year, artist/track relationships (structured data)
4. MusicBrainz - Track metadata, BPM, year, MBID lookup
5. AcousticBrainz - Audio analysis (BPM, key, tempo from MusicBrainz ID) - LAST

For each MISSING FIELD (fields not already present in track):
- Uses first source that has the field
- Skips that field in subsequent sources (already have highest-priority version)
- Skips fields already present (don't re-enrich existing metadata)
- Continues through all sources to find remaining missing fields
- NO SONGS SKIPPED - searches all sources for missing metadata

Example (Track missing: BPM, Year. Already has: Genre):
- Discogs returns: Genre, Year → skip Genre (have it), collect Year
- Last.fm returns: Genre, Tags → skip all (Genre present, Tags not a field)
- MusicBrainz returns: BPM, Year → skip Year (found), collect BPM
- Result: Year (Discogs), BPM (MusicBrainz), Genre (unchanged)

"""

import json
import urllib.parse
from typing import Dict, List, Optional, Tuple
import logging
import time
from abc import ABC, abstractmethod
from src.metadata_enrichment import MetadataField, DatabaseSource, MetadataEntry
from src.http_utils import HttpClient


class DatabaseQuery(ABC):
    """Abstract base class for database queries."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.http = HttpClient(
            logger=self.logger, user_agent="metad-fill/1.0 (metadata enrichment)"
        )

    @abstractmethod
    def query(
        self, artist: str, title: str, duration: Optional[int] = None
    ) -> Dict[MetadataField, Tuple[str, float]]:
        """
        Query database for metadata.

        Args:
            artist: Artist name
            title: Track title
            duration: Duration in seconds (optional, for matching)

        Returns:
            {MetadataField: (value, confidence), ...}
        """
        pass

    def _fetch_url(self, url: str, timeout: int = 5) -> Optional[str]:
        """
        Fetch content from URL.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            Response body or None if failed
        """
        return self.http.fetch_text(url, timeout=timeout)


class MusicBrainzQuery(DatabaseQuery):
    """Query MusicBrainz for metadata."""

    BASE_URL = "https://musicbrainz.org/ws/2"

    def query(
        self, artist: str, title: str, duration: Optional[int] = None
    ) -> Dict[MetadataField, Tuple[str, float]]:
        """
        Query MusicBrainz for track metadata.

        Returns: {field: (value, confidence), ...}
        """
        results = {}

        # Search for recording by artist and title
        recording = self._search_recording(artist, title)
        if not recording:
            return results

        self.logger.debug(f"Found MusicBrainz recording: {recording.get('id')}")

        # Extract year from release date
        if "first-release-date" in recording:
            year = recording["first-release-date"].split("-")[0]
            results[MetadataField.YEAR] = (year, 0.9)

        # Get genre from release if available
        if "releases" in recording and recording["releases"]:
            release = recording["releases"][0]
            genre = self._extract_genre_from_release(release)
            if genre:
                results[MetadataField.GENRE] = (genre, 0.7)

        return results

    def _search_recording(self, artist: str, title: str) -> Optional[dict]:
        """Search for recording in MusicBrainz."""
        query_str = f'artist:"{artist}" recording:"{title}"'
        params = urllib.parse.urlencode({"query": query_str, "limit": 5, "fmt": "json"})

        url = f"{self.BASE_URL}/recording?{params}"
        response = self._fetch_url(url)

        if not response:
            return None

        try:
            data = json.loads(response)
            recordings = data.get("recordings", [])

            if recordings:
                return recordings[0]
        except json.JSONDecodeError as e:
            self.logger.debug("event=musicbrainz_parse_failed error=%s", e)

        return None

    def _extract_genre_from_release(self, release: dict) -> Optional[str]:
        """Extract genre from MusicBrainz release."""
        # MusicBrainz doesn't have explicit genre field in older API
        # Check for tags or other genre indicators
        if "tags" in release:
            tags = release["tags"]
            if isinstance(tags, list) and tags:
                return tags[0].get("name")

        return None


class AcousticBrainzQuery(DatabaseQuery):
    """Query AcousticBrainz for BPM and audio features."""

    BASE_URL = "https://acousticbrainz.org/api/v1"

    def __init__(
        self,
        musicbrainz_query: Optional["MusicBrainzQuery"] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize with optional MusicBrainz query for MBID lookup."""
        super().__init__(logger)
        self.musicbrainz_query = musicbrainz_query

    def query(
        self, artist: str, title: str, duration: Optional[int] = None
    ) -> Dict[MetadataField, Tuple[str, float]]:
        """
        Query AcousticBrainz for audio features (primarily BPM).

        First looks up MBID from MusicBrainz, then queries AcousticBrainz.

        Returns: {field: (value, confidence), ...}
        """
        results = {}

        # Step 1: Get MBID from MusicBrainz
        mbid = self._get_mbid(artist, title)
        if not mbid:
            self.logger.debug(
                f"Could not find MBID for {artist} - {title}, skipping AcousticBrainz"
            )
            return results

        # Step 2: Query AcousticBrainz with MBID
        ab_data = self.query_by_mbid(mbid)
        if not ab_data:
            self.logger.debug(f"No AcousticBrainz data for MBID {mbid}")
            return results

        # Step 3: Extract BPM
        bpm_result = self.extract_bpm(ab_data)
        if bpm_result:
            results[MetadataField.BPM] = bpm_result
            self.logger.debug(f"Found BPM from AcousticBrainz: {bpm_result[0]}")

        return results

    def _get_mbid(self, artist: str, title: str) -> Optional[str]:
        """Get MusicBrainz ID for a track."""
        query_str = f'artist:"{artist}" recording:"{title}"'
        params = urllib.parse.urlencode({"query": query_str, "limit": 1, "fmt": "json"})

        url = f"https://musicbrainz.org/ws/2/recording?{params}"
        response = self._fetch_url(url, timeout=5)

        if not response:
            return None

        try:
            data = json.loads(response)
            recordings = data.get("recordings", [])
            if recordings:
                return recordings[0].get("id")
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            self.logger.debug("event=acousticbrainz_mbid_parse_failed error=%s", e)

        return None

    def query_by_mbid(self, mbid: str) -> Optional[Dict]:
        """
        Query AcousticBrainz by MusicBrainz ID.

        Args:
            mbid: MusicBrainz recording ID

        Returns:
            AcousticBrainz data or None
        """
        url = f"{self.BASE_URL}/{mbid}"
        response = self._fetch_url(url, timeout=5)

        if not response:
            return None

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return None

    def extract_bpm(self, acousticbrainz_data: dict) -> Optional[Tuple[str, float]]:
        """Extract BPM from AcousticBrainz data."""
        try:
            # BPM is in highlevel.rhythm section
            highlevel = acousticbrainz_data.get("highlevel", {})
            rhythm = highlevel.get("rhythm", {})

            if isinstance(rhythm, dict) and "bpm" in rhythm:
                bpm_val = rhythm["bpm"]
                if isinstance(bpm_val, (int, float)):
                    return (str(int(bpm_val)), 0.95)
        except (KeyError, ValueError, TypeError) as e:
            self.logger.debug("event=acousticbrainz_bpm_parse_failed error=%s", e)

        return None


class DiscogsQuery(DatabaseQuery):
    """Query Discogs for metadata."""

    BASE_URL = "https://api.discogs.com"

    def __init__(self, token: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """Initialize with Discogs API token."""
        super().__init__(logger)
        self.token = token

    def query(
        self, artist: str, title: str, duration: Optional[int] = None
    ) -> Dict[MetadataField, Tuple[str, float]]:
        """
        Query Discogs for track metadata (genre, release year).

        Note: Discogs API requires token. Register at:
        https://www.discogs.com/settings/developers

        Returns: {field: (value, confidence), ...}
        """
        results = {}

        if not self.token:
            self.logger.debug("Discogs token not provided, skipping Discogs query")
            return results

        # Step 1: Search for release
        release = self._search_release(artist, title)
        if not release:
            self.logger.debug(f"No Discogs release found for {artist} - {title}")
            return results

        self.logger.debug(f"Found Discogs release: {release.get('id')}")

        # Step 2: Get detailed release info
        release_detail = self._get_release_detail(release.get("id"))
        if not release_detail:
            self.logger.debug(f"Could not fetch Discogs release details")
            return results

        # Step 3: Extract metadata
        # Genre
        genres = release_detail.get("genres", [])
        if genres:
            genre = genres[0]  # Primary genre
            results[MetadataField.GENRE] = (genre, 0.75)
            self.logger.debug(f"Found genre from Discogs: {genre}")

        # Release year
        year = release_detail.get("year")
        if year:
            results[MetadataField.YEAR] = (str(year), 0.85)
            self.logger.debug(f"Found year from Discogs: {year}")

        return results

    def _search_release(self, artist: str, title: str) -> Optional[dict]:
        """Search for a release on Discogs."""
        # Search for recording (track)
        params = urllib.parse.urlencode(
            {"artist": artist, "release_title": title, "token": self.token, "type": "release"}
        )

        url = f"{self.BASE_URL}/database/search?{params}"
        response = self._fetch_url(url, timeout=10)

        if not response:
            return None

        try:
            data = json.loads(response)
            results = data.get("results", [])

            if results:
                # Return first release result
                return results[0]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            self.logger.debug("event=discogs_search_parse_failed error=%s", e)

        return None

    def _get_release_detail(self, release_id: int) -> Optional[dict]:
        """Get detailed information about a Discogs release."""
        params = urllib.parse.urlencode({"token": self.token})
        url = f"{self.BASE_URL}/releases/{release_id}?{params}"

        response = self._fetch_url(url, timeout=10)

        if not response:
            return None

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return None


class WikidataQuery(DatabaseQuery):
    """Query Wikidata for metadata."""

    BASE_URL = "https://www.wikidata.org/w/api.php"

    def query(
        self, artist: str, title: str, duration: Optional[int] = None
    ) -> Dict[MetadataField, Tuple[str, float]]:
        """
        Query Wikidata for release date and genre.

        Returns: {field: (value, confidence), ...}
        """
        results = {}

        # Search for musical work/song
        entity = self._search_entity(title)
        if not entity:
            return results

        self.logger.debug(f"Found Wikidata entity: {entity}")

        # Query entity for metadata
        metadata = self._get_entity_metadata(entity)
        if not metadata:
            return results

        # Extract year
        if "publication_date" in metadata:
            year = metadata["publication_date"].split("-")[0]
            results[MetadataField.YEAR] = (year, 0.8)

        # Extract genre
        if "genre" in metadata:
            results[MetadataField.GENRE] = (metadata["genre"], 0.6)

        return results

    def _search_entity(self, title: str) -> Optional[str]:
        """Search for entity in Wikidata."""
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "search": title,
                "srsearch": f"haswbstatement:P31=Q7366",  # Instance of: musical work
            }
        )

        url = f"{self.BASE_URL}?{params}"
        response = self._fetch_url(url, timeout=10)

        if not response:
            return None

        try:
            data = json.loads(response)
            search_results = data.get("query", {}).get("search", [])
            if search_results:
                return search_results[0]["title"]
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.debug("event=wikidata_parse_failed error=%s", e)

        return None

    def _get_entity_metadata(self, entity_title: str) -> Optional[dict]:
        """Get metadata for entity."""
        # Simplified - would query entity properties
        return None


class LastfmQuery(DatabaseQuery):
    """Query Last.fm for metadata (requires API key)."""

    BASE_URL = "http://ws.audioscrobbler.com/2.0"

    def __init__(self, api_key: Optional[str] = None, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.api_key = api_key

    def query(
        self, artist: str, title: str, duration: Optional[int] = None
    ) -> Dict[MetadataField, Tuple[str, float]]:
        """
        Query Last.fm for metadata.

        Note: Requires API key. Returns user-generated tags.

        Returns: {field: (value, confidence), ...}
        """
        if not self.api_key:
            self.logger.debug("Last.fm API key not provided")
            return {}

        results = {}

        # Query track info
        track_info = self._get_track_info(artist, title)
        if not track_info:
            return results

        # Extract tags (user-generated genre equivalents)
        if "tags" in track_info:
            tags = track_info["tags"]
            if isinstance(tags, list) and tags:
                genre = tags[0]  # Most popular tag
                results[MetadataField.GENRE] = (genre, 0.5)

        return results

    def _get_track_info(self, artist: str, title: str) -> Optional[dict]:
        """Get track info from Last.fm."""
        params = urllib.parse.urlencode(
            {
                "method": "track.getInfo",
                "artist": artist,
                "track": title,
                "api_key": self.api_key,
                "format": "json",
            }
        )

        url = f"{self.BASE_URL}?{params}"
        response = self._fetch_url(url, timeout=10)

        if not response:
            return None

        try:
            data = json.loads(response)
            return data.get("track")
        except json.JSONDecodeError as e:
            self.logger.debug("event=lastfm_parse_failed error=%s", e)

        return None


class MetadataQueryOrchestrator:
    """Orchestrate queries across all databases in priority order."""

    # Priority order for queries
    # User-specified hierarchy: Discogs → Last.fm → Wikidata → MusicBrainz → AcousticBrainz
    # CoverArtArchive is only used for cover art (separate flow)
    QUERY_ORDER = [
        (DatabaseSource.DISCOGS, DiscogsQuery),
        (DatabaseSource.LASTFM, LastfmQuery),
        (DatabaseSource.WIKIDATA, WikidataQuery),
        (DatabaseSource.MUSICBRAINZ, MusicBrainzQuery),
        (DatabaseSource.ACOUSTICBRAINZ, AcousticBrainzQuery),
    ]

    def __init__(
        self,
        lastfm_api_key: Optional[str] = None,
        discogs_token: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.lastfm_api_key = lastfm_api_key
        self.discogs_token = discogs_token
        self.query_cache: Dict[Tuple, List[MetadataEntry]] = {}
        self.max_cache_entries = 1000

    def _build_cache_key(
        self,
        artist: str,
        title: str,
        duration: Optional[int],
        enrich_once: bool,
        missing_fields: List[MetadataField],
    ) -> Tuple:
        return (
            artist.strip().lower(),
            title.strip().lower(),
            duration,
            enrich_once,
            tuple(sorted(field.value for field in missing_fields)),
        )

    def _set_cache(self, key: Tuple, value: List[MetadataEntry]) -> None:
        if key in self.query_cache:
            self.query_cache[key] = value
            return
        if len(self.query_cache) >= self.max_cache_entries:
            oldest_key = next(iter(self.query_cache))
            self.query_cache.pop(oldest_key)
        self.query_cache[key] = value

    def query_all_sources(
        self,
        artist: str,
        title: str,
        duration: Optional[int] = None,
        enrich_once: bool = True,
        missing_fields: Optional[List[MetadataField]] = None,
    ) -> List[MetadataEntry]:
        """
        Query available sources for specific metadata fields.

        Queries are performed in deterministic priority order.
        If enrich_once=True, searches only for missing fields from highest-priority sources.
        If enrich_once=False, queries all sources for comparison.

        With enrich_once=True and missing_fields specified:
        - Only search for specified missing fields
        - Discogs returns Genre + Year (from missing_fields) → collect
        - Skip fields already found from other sources
        - Continue to next source looking for remaining missing fields
        - Stops when all missing fields found OR all sources exhausted

        This ensures:
        - NO SONGS ARE SKIPPED (searches all sources for missing fields)
        - EFFICIENT QUERIES (only queries for fields that are actually missing)
        - ACCURATE ENRICHMENT (uses highest-priority sources for each field)

        Args:
            artist: Artist name
            title: Track title
            duration: Duration in seconds
            enrich_once: Search for missing fields from priority sources (default: True)
            missing_fields: List of fields that need enrichment (default: None - search all)

        Returns:
            List of MetadataEntry objects with sources
        """
        entries = []
        found_fields: Dict[MetadataField, bool] = {}  # Track which fields have been found

        # If missing_fields not specified, assume we're looking for all field types
        if missing_fields is None:
            missing_fields = list(MetadataField)

        # Check cache with full query semantics.
        cache_key = self._build_cache_key(artist, title, duration, enrich_once, missing_fields)
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]

        for source, query_class in self.QUERY_ORDER:
            # With enrich_once: check if all missing fields have been found
            if enrich_once and missing_fields:
                all_found = all(field in found_fields for field in missing_fields)
                if all_found:
                    self.logger.debug(f"All missing fields found. Skipping remaining sources.")
                    break

            if source == DatabaseSource.LASTFM:
                # LastFM requires API key
                if not self.lastfm_api_key:
                    continue
                querier = query_class(api_key=self.lastfm_api_key, logger=self.logger)
            elif source == DatabaseSource.DISCOGS:
                # Discogs requires token (optional)
                querier = query_class(token=self.discogs_token, logger=self.logger)
            else:
                querier = query_class(logger=self.logger)

            self.logger.debug(f"Querying {source.name} for {artist} - {title}")
            self.logger.debug(
                f"  Looking for missing fields: {[f.name for f in missing_fields if f not in found_fields]}"
            )

            results = querier.query(artist, title, duration)

            if results:
                for field, (value, confidence) in results.items():
                    # Only collect if:
                    # 1. This field is in our missing_fields list
                    # 2. We haven't already found this field
                    if field in missing_fields and field not in found_fields:
                        entry = MetadataEntry(
                            field=field, value=value, source=source, confidence=confidence
                        )
                        entries.append(entry)
                        found_fields[field] = True
                        self.logger.debug(
                            f"  ✓ Found {field.name} from {source.name}: {value} (conf: {confidence})"
                        )
                    elif field in found_fields:
                        self.logger.debug(
                            f"  ✗ Skipping {field.name} from {source.name} (already have from {self._get_field_source(entries, field).name})"
                        )
                    else:
                        self.logger.debug(
                            f"  ✗ Skipping {field.name} from {source.name} (not in missing fields)"
                        )

            # Add rate limiting between queries
            time.sleep(0.5)

        # Cache results
        self._set_cache(cache_key, entries)

        return entries

    def _get_field_source(
        self, entries: List[MetadataEntry], field: MetadataField
    ) -> Optional["DatabaseSource"]:
        """Get the source that provided a specific field."""
        for entry in entries:
            if entry.field == field:
                return entry.source
        return None

    def clear_cache(self) -> None:
        """Clear query cache."""
        self.query_cache.clear()
        self.logger.debug("Cleared metadata query cache")
