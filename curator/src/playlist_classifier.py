import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from src.logger import setup_logger
from src.metadata_enrichment import MetadataField
from src.metadata_queries import MetadataQueryOrchestrator
from src.normalizer import TextNormalizer

logger = setup_logger(__name__)


class PlaylistClassifier:
    """
    Comprehensive playlist classifier that uses weighted scoring, genre mapping,
    artist lookup, BPM matching, and TF-IDF fallback for playlist classification.
    """

    def __init__(
        self,
        genre_map_path: str,
        weights_path: str,
        artist_lists_dir: str,
        dominance_threshold: float = 0.3,
        lastfm_api_key: Optional[str] = None,
        discogs_token: Optional[str] = None,
        enable_genre_enrichment: bool = True,
    ):
        """
        Initialize the playlist classifier.

        Args:
            genre_map_path: Path to genre mapping JSON file
            weights_path: Path to scoring weights JSON file
            artist_lists_dir: Path to directory containing artist lists JSON files
            dominance_threshold: Minimum score ratio required for genre dominance
            lastfm_api_key: Optional Last.fm API key for metadata enrichment
            discogs_token: Optional Discogs API token for metadata enrichment
            enable_genre_enrichment: Enable querying databases for missing genre metadata
        """
        # Initialize normalizer first
        self.normalizer = TextNormalizer()

        # Load configuration
        self.genre_map = self.load_json(genre_map_path)
        self.weights = self.load_json(weights_path)
        self.artist_lists = self.load_artist_lists(artist_lists_dir)
        self.dominance_threshold = dominance_threshold
        self.enable_genre_enrichment = enable_genre_enrichment

        # Initialize metadata query orchestrator for genre enrichment
        self.metadata_orchestrator: Optional[MetadataQueryOrchestrator] = None
        if enable_genre_enrichment:
            try:
                self.metadata_orchestrator = MetadataQueryOrchestrator(
                    lastfm_api_key=lastfm_api_key, discogs_token=discogs_token, logger=logger
                )
                logger.info("Initialized metadata query orchestrator for genre enrichment")
            except Exception as e:
                logger.warning(f"Failed to initialize metadata orchestrator: {e}")

        # Extract target genres from artist lists
        self.target_genres = list(self.artist_lists.keys())
        logger.info(f"Initialized classifier for genres: {self.target_genres}")

    def load_json(self, path: str) -> Dict[str, Any]:
        """Load JSON configuration files."""
        try:
            with open(path, "r", encoding="utf-8") as file:
                return cast(Dict[str, Any], json.load(file))
        except Exception as e:
            logger.error(f"Failed to load JSON from {path}: {e}")
            return {}

    def load_artist_lists(self, directory: str) -> Dict[str, Dict]:
        """Load artist lists from JSON files in directory."""
        artist_lists = {}
        artist_dir = Path(directory)

        if not artist_dir.exists():
            logger.error(f"Artist lists directory not found: {directory}")
            return {}

        for file_path in artist_dir.glob("*.json"):
            genre = file_path.stem
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Normalize artist names to lowercase for matching
                    if "artists" in data:
                        data["artists"] = [
                            self.normalizer.normalize(artist) for artist in data["artists"]
                        ]
                    if "keywords" in data:
                        data["keywords"] = [
                            self.normalizer.normalize(kw) for kw in data["keywords"]
                        ]
                    artist_lists[genre] = data
                    logger.debug(
                        f"Loaded {len(data.get('artists', []))} artists for genre: {genre}"
                    )
            except Exception as e:
                logger.warning(f"Failed to load artist list for {genre}: {e}")

        return artist_lists

    def add_analyzed_artists(self, genre: str, artists: List[str]) -> None:
        """
        Add analyzed artists to a genre from database queries.

        Args:
            genre: Target genre to add artists to
            artists: List of artist names to add
        """
        if genre not in self.artist_lists:
            self.artist_lists[genre] = {"artists": [], "keywords": []}

        # Normalize and add artists if not already present
        existing_artists = set(self.artist_lists[genre].get("artists", []))
        for artist in artists:
            normalized_artist = self.normalizer.normalize(artist)
            if normalized_artist not in existing_artists:
                self.artist_lists[genre]["artists"].append(normalized_artist)
                existing_artists.add(normalized_artist)

        logger.debug(f"Added {len(artists)} analyzed artists to genre: {genre}")

    def enrich_missing_genre(self, track: Dict[str, Any]) -> Optional[str]:
        """
        Enrich missing genre metadata by querying external databases.

        If track lacks a genre field, queries MusicBrainz, Last.fm, Discogs, etc.
        in priority order to find genre information. Applies the most reliable
        genre found to the track dictionary.

        Args:
            track: Track metadata dictionary (will be modified in-place if enriched)

        Returns:
            Enriched genre string if found, None otherwise
        """
        # Skip if enrichment disabled
        if not self.enable_genre_enrichment or not self.metadata_orchestrator:
            return None

        # Skip if track already has genre
        existing_genre = track.get("genre")
        if existing_genre and isinstance(existing_genre, str) and existing_genre.strip():
            return cast(str, existing_genre.strip())

        # Extract artist and title
        artist = track.get("artist", "").strip()
        title = track.get("name", "").strip()

        if not artist or not title:
            logger.debug(f"Cannot enrich genre: missing artist or title")
            return None

        try:
            # Query databases looking specifically for genre field
            logger.debug(f"Enriching missing genre for: {artist} - {title}")
            entries = self.metadata_orchestrator.query_all_sources(
                artist=artist, title=title, enrich_once=True, missing_fields=[MetadataField.GENRE]
            )

            if entries:
                # Use first (highest-priority) genre found
                genre_entry = entries[0]
                enriched_genre = genre_entry.value
                track["genre"] = enriched_genre
                logger.debug(f"Enriched genre from {genre_entry.source.name}: {enriched_genre}")
                return enriched_genre

        except Exception as e:
            logger.warning(f"Failed to enrich genre for {artist} - {title}: {e}")

        return None

    def map_genre_to_target(self, raw_genre: str) -> Optional[str]:
        """
        Map raw genre string to target genre cluster using enhanced mapping.

        Args:
            raw_genre: Original genre string from track metadata

        Returns:
            Mapped target genre or None if no mapping found
        """
        if not raw_genre:
            return None

        raw_genre_norm = self.normalizer.normalize(raw_genre)

        # Direct mapping check
        if raw_genre_norm in self.genre_map:
            return cast(str, self.genre_map[raw_genre_norm])

        # Keyword-based mapping
        genre_keywords = {
            "hiphop": [
                "hip hop",
                "rap",
                "trap",
                "drill",
                "gangsta rap",
                "conscious rap",
                "old school",
            ],
            "electronic": [
                "electronic",
                "edm",
                "techno",
                "house",
                "trance",
                "dubstep",
                "ambient",
                "electro",
                "synth",
                "dance",
                "dnb",
                "drum and bass",
                "hardcore",
            ],
            "disco_funk_soul": ["disco", "funk", "soul", "motown", "r&b", "groove", "boogie"],
            "jazz": ["jazz", "bebop", "fusion", "cool jazz", "smooth jazz", "avant-garde", "swing"],
            "world": [
                "world",
                "folk",
                "traditional",
                "ethnic",
                "african",
                "latin",
                "reggae",
                "caribbean",
                "middle eastern",
                "asian",
                "indian",
            ],
            "rock": [
                "rock",
                "metal",
                "punk",
                "indie",
                "alternative",
                "grunge",
                "hard rock",
                "progressive",
                "classic rock",
                "pop rock",
            ],
        }

        for target_genre, keywords in genre_keywords.items():
            if any(keyword in raw_genre_norm for keyword in keywords):
                return cast(str, target_genre)

        return None

    def score_track(self, track: Dict[str, Any]) -> Dict[str, float]:
        """
        Score a single track against all target genres.

        Enriches missing genre metadata from external databases before scoring.

        Args:
            track: Track metadata dictionary

        Returns:
            Dictionary mapping genre names to scores
        """
        genre_scores = defaultdict(float)

        # Enrich missing genre from databases
        track_genre_raw = track.get("genre", "")
        if not (isinstance(track_genre_raw, str) and track_genre_raw.strip()):
            self.enrich_missing_genre(track)
            track_genre_raw = track.get("genre", "")

        # Extract fields
        track_genre = track_genre_raw
        if isinstance(track_genre, str):
            track_genre = self.normalizer.normalize(track_genre)

        track_artist = track.get("artist", "")
        if isinstance(track_artist, str):
            track_artist = self.normalizer.normalize(track_artist)

        track_composer = track.get("composer", "")
        if isinstance(track_composer, str):
            track_composer = self.normalizer.normalize(track_composer)

        for target_genre in self.target_genres:
            genre_data = self.artist_lists.get(target_genre, {})
            score = 0.0

            # Genre match scoring
            mapped_genre = self.map_genre_to_target(track_genre)
            if mapped_genre == target_genre:
                score += self.weights.get("genre_match", 3)

            # Artist match scoring
            if track_artist and "artists" in genre_data:
                if track_artist in genre_data["artists"]:
                    score += self.weights.get("artist_match", 2)

            # Keyword match scoring (for partial artist matches)
            if track_artist and "keywords" in genre_data:
                for keyword in genre_data["keywords"]:
                    if keyword in track_artist:
                        score += self.weights.get("artist_match", 2) * 0.5  # Partial match
                        break

            # Composer match scoring (especially for jazz/world)
            if track_composer and target_genre in ["jazz", "world"]:
                if "artists" in genre_data and track_composer in genre_data["artists"]:
                    score += self.weights.get("composer_match", 1)

            genre_scores[target_genre] = score

        return dict(genre_scores)

    def score_playlist(self, tracks: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Score entire playlist by aggregating track scores.

        Args:
            tracks: List of track metadata dictionaries

        Returns:
            Dictionary mapping genre names to total playlist scores
        """
        if not tracks:
            return {}

        playlist_scores: defaultdict[str, float] = defaultdict(float)
        track_count = len(tracks)

        logger.debug(f"Scoring playlist with {track_count} tracks")

        for i, track in enumerate(tracks):
            track_scores = self.score_track(track)

            for genre, score in track_scores.items():
                playlist_scores[genre] += score

            if logger.isEnabledFor(10):  # DEBUG level is 10
                max_genre = (
                    max(track_scores.items(), key=lambda x: x[1]) if track_scores else ("none", 0)
                )
                logger.debug(
                    f"Track {i+1}: {track.get('artist', 'Unknown')} - "
                    f"{track.get('name', 'Unknown')} -> {max_genre[0]} ({max_genre[1]})"
                )

        return dict(playlist_scores)

    def calculate_tfidf_scores(self, tracks: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate TF-IDF based genre scores as fallback method.

        Args:
            tracks: List of track metadata dictionaries

        Returns:
            Dictionary mapping genre names to TF-IDF scores
        """
        if not tracks:
            return {}

        # Collect all genre strings from tracks
        track_genres = []
        for track in tracks:
            genre = track.get("genre", "")
            if genre:
                track_genres.append(self.normalizer.normalize(genre))

        if not track_genres:
            return {}

        # Calculate term frequencies for each target genre
        tfidf_scores = {}
        genre_terms = []

        # Build corpus of genre keywords
        for target_genre in self.target_genres:
            genre_data = self.artist_lists.get(target_genre, {})
            keywords = genre_data.get("keywords", [])
            genre_terms.extend(keywords)

        # Calculate TF-IDF for each target genre
        for target_genre in self.target_genres:
            genre_data = self.artist_lists.get(target_genre, {})
            keywords = genre_data.get("keywords", [])

            if not keywords:
                tfidf_scores[target_genre] = 0.0
                continue

            # Term frequency: how often target keywords appear in track genres
            tf_score = 0.0
            for genre_str in track_genres:
                for keyword in keywords:
                    if keyword in genre_str:
                        tf_score += 1.0

            # Normalize by number of tracks
            tf_score = tf_score / len(track_genres) if track_genres else 0.0

            # Simple IDF approximation (could be enhanced with larger corpus)
            idf_score = 1.0 + math.log(len(self.target_genres) / max(1, len(keywords)))

            tfidf_scores[target_genre] = tf_score * idf_score

        return tfidf_scores

    def determine_dominant_genre(
        self,
        playlist_scores: Dict[str, float],
        tracks: List[Dict[str, Any]],
        playlist_name: str = "",
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Determine the dominant genre for a playlist with detailed reasoning.

        Args:
            playlist_scores: Genre scores from weighted rules
            tracks: Original track data for fallback analysis
            playlist_name: Name of playlist for logging

        Returns:
            Tuple of (dominant_genre, decision_info)
        """
        decision_info = {
            "playlist_name": playlist_name,
            "track_count": len(tracks),
            "scores": playlist_scores.copy(),
            "method": "weighted_rules",
            "confidence": 0.0,
            "reason": "",
            "fallback_used": False,
        }

        if not playlist_scores:
            decision_info["reason"] = "No scores calculated"
            return None, decision_info

        # Find highest scoring genre
        max_score = max(playlist_scores.values())
        if max_score == 0:
            # Use TF-IDF fallback
            logger.debug(f"No weighted scores for {playlist_name}, using TF-IDF fallback")
            tfidf_scores = self.calculate_tfidf_scores(tracks)

            if tfidf_scores:
                decision_info["tfidf_scores"] = tfidf_scores
                decision_info["fallback_used"] = True
                decision_info["method"] = "tfidf_fallback"

                max_tfidf_score = max(tfidf_scores.values())
                if max_tfidf_score > 0:
                    dominant_genre = max(tfidf_scores, key=lambda x: tfidf_scores[x])
                    decision_info["confidence"] = max_tfidf_score
                    decision_info["reason"] = f"TF-IDF fallback selected {dominant_genre}"
                    return dominant_genre, decision_info

            decision_info["reason"] = "No significant scores in weighted rules or TF-IDF"
            return None, decision_info

        # Calculate dominance
        total_score = sum(playlist_scores.values())
        dominance_ratio = max_score / total_score if total_score > 0 else 0.0

        decision_info["confidence"] = dominance_ratio

        if dominance_ratio >= self.dominance_threshold:
            dominant_genre = max(playlist_scores, key=lambda x: playlist_scores[x])
            decision_info["reason"] = f"Clear dominance: {dominant_genre} ({dominance_ratio:.2f})"
            return dominant_genre, decision_info
        else:
            decision_info["reason"] = (
                f"No clear dominance (max: {dominance_ratio:.2f}, threshold: {self.dominance_threshold})"
            )
            return None, decision_info

    def classify_playlist(
        self, tracks: List[Dict[str, Any]], playlist_name: str = ""
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Main method to classify a playlist into a target genre.

        Args:
            tracks: List of track metadata dictionaries
            playlist_name: Name of playlist for logging

        Returns:
            Tuple of (assigned_genre, classification_details)
        """
        logger.info(f"Classifying playlist: {playlist_name} ({len(tracks)} tracks)")

        if not tracks:
            return None, {"error": "No tracks provided", "playlist_name": playlist_name}

        # Calculate weighted scores
        playlist_scores = self.score_playlist(tracks)

        # Determine dominant genre
        dominant_genre, decision_info = self.determine_dominant_genre(
            playlist_scores, tracks, playlist_name
        )

        logger.info(
            f"Classification result for '{playlist_name}': "
            f"{dominant_genre or 'unclassified'} ({decision_info['method']}, "
            f"confidence: {decision_info['confidence']:.2f})"
        )

        return dominant_genre, decision_info
