# Genre Classification Specifications

## Context & Implementation Guide

Genre Classification provides deterministic genre assignment for playlists using weighted scoring of track metadata (artist genres, tags, metadata). The system includes fallback to TF-IDF keyword matching when metadata is insufficient and supports multiple classification strategies.

### Core Features

- **Metadata-based scoring**: Weighted scoring across artist genres, track tags, and metadata
- **Six-genre taxonomy**: Hip-Hop, Electronic, Jazz, Rock, Disco/Funk/Soul, World
- **Artist database classification**: Compare playlist artists against pre-compiled genre lists
- **Fuzzy artist matching**: Handle artist name variations through normalized comparison
- **Configuration-driven weights**: Adjustable weights for different scoring signals
- **Confidence scoring**: Return classification confidence (0-100)
- **TF-IDF fallback**: Keyword extraction and matching when metadata insufficient
- **Genre mapping configuration**: Extensible mapping from data sources to canonical genres

### Implementation Files

- `src/playlist_classifier.py` - Core classification orchestration and scoring
- `src/playlist_utils.py` - Artist matching utilities (fuzzy matching, ID resolution)
- `data/artist_lists/` - Pre-compiled genre-specific artist lists (JSON)
  - `hip_hop.json` - Hip-Hop artists
  - `electronic.json` - Electronic artists
  - `jazz.json` - Jazz artists
  - `rock.json` - Rock artists
  - `disco_funk_soul.json` - Disco/Funk/Soul artists
  - `world.json` - World music artists
- `data/config/genre_map.json` - Genre mapping and weights
- `tests/test_playlist_classifier.py` - Classification accuracy tests

### Configuration

- `data/config/genre_map.json` schema:
  ```json
  {
    "genres": ["hip-hop", "electronic", "jazz", "rock", "disco-funk-soul", "world"],
    "weights": {
      "artist_direct_match": 5.0,
      "artist_fuzzy_match": 2.0,
      "track_metadata_genre": 1.5,
      "track_tags": 1.0,
      "tfidf_keyword_match": 0.5
    },
    "confidence_threshold": 0.6,
    "fuzzy_match_threshold": 0.85,
    "tfidf_min_score": 0.3
  }
  ```

### Related Domains

- **Metadata Enrichment** (`metadata`) - Provides enriched track metadata (genre, tags)
- **Playlist Organization** (`playlists`) - Uses classification to organize playlists
- **Text Normalization** - Normalizes artist names for fuzzy matching

---

## Overview

Genre Classification SHALL assign each playlist to one of six canonical genres using weighted metadata scoring with configurable confidence thresholds.

### Requirement: Canonical Genre Set
The system MUST classify playlists into exactly six genres.

#### Scenario: Genre enumeration
- GIVEN the classification system initializes
- WHEN available genres are requested
- THEN system SHALL return exactly these six:
  - hip-hop
  - electronic
  - jazz
  - rock
  - disco-funk-soul
  - world

#### Scenario: Out-of-schema genre in metadata
- GIVEN track metadata contains genre "classical" (not in canonical set)
- WHEN classification runs
- THEN system SHALL:
  - Map "classical" to closest canonical genre using genre_map.json
  - Apply weight according to mapping confidence
  - Document mapping in results

### Requirement: Metadata-Based Scoring
The system MUST score playlists using weighted artist and track metadata.

#### Scenario: Artist direct match
- GIVEN playlist contains artists "Eminem" and "Drake"
- WHEN classification runs
- THEN system SHALL:
  - Check artist names against pre-compiled artist_lists/hip_hop.json
  - Award points for direct matches (default weight: 5.0 per match)
  - Total score for hip-hop increases significantly
  - Confidence increases proportionally

#### Scenario: Fuzzy artist match
- GIVEN playlist contains artist "The Beatles" (in genre list as "Beatles")
- WHEN artist matching uses fuzzy comparison
- THEN system SHALL:
  - Normalize both names: "The Beatles" and "Beatles"
  - Calculate similarity (fuzzy_match_threshold: 0.85)
  - Award partial points if similarity >= threshold
  - Award weight defined in config (default: 2.0)

#### Scenario: Track metadata genre field
- GIVEN track has populated genre field "Jazz" or "Soul"
- WHEN classification scores track
- THEN system SHALL:
  - Award points for metadata genre (default weight: 1.5)
  - Map to canonical genre if necessary
  - Consider as supporting signal to artist-based classification

#### Scenario: Track tags scoring
- GIVEN track has user tags like "upbeat", "electronic", "synth"
- WHEN classification scores tags
- THEN system SHALL:
  - Award points for tag matches to genre keywords
  - Use configured weight (default: 1.0)
  - Accumulate across all tracks in playlist

### Requirement: Confidence Scoring
The system MUST return confidence value (0-100) for each classification.

#### Scenario: High confidence classification
- GIVEN playlist of 50 tracks, 45 artists match hip-hop genre list
- WHEN confidence is calculated
- THEN system SHALL:
  - Accumulate high score from artist matches
  - Calculate confidence = (score / max_possible_score) * 100
  - Return confidence >= 0.85 (85%)

#### Scenario: Low confidence classification
- GIVEN playlist with mixed artists, no strong genre signal
- WHEN confidence is calculated
- THEN system SHALL:
  - Accumulate low total score
  - Return confidence < 0.60 (60%)
  - Mark as "unclassified" or "ambiguous" in results

#### Scenario: Unclassified threshold
- GIVEN classification produces confidence below threshold (default: 0.60)
- WHEN classification completes
- THEN system SHALL:
  - NOT assign a genre
  - Return result as "unclassified"
  - Report confidence value
  - Flag for manual review or enrichment

### Requirement: Fuzzy Artist Matching
The system MUST match artist names accounting for variations.

#### Scenario: Name normalization
- GIVEN artists with variations: "The Beatles", "Beatles, The", "Beatles"
- WHEN fuzzy matching normalizer is applied
- THEN system SHALL:
  - Strip articles ("The")
  - Remove punctuation
  - Convert to consistent case
  - Compare normalized forms

#### Scenario: Matching threshold configuration
- GIVEN fuzzy_match_threshold = 0.85
- WHEN artist "The Rolling Stones" is compared to "Rolling Stones"
- THEN system SHALL:
  - Calculate similarity ratio >= 0.85
  - Consider it a match
  - Award points according to config weight

#### Scenario: Typo tolerance
- GIVEN artist name with typo "Beatle" vs "Beatles" in database
- WHEN fuzzy match uses Levenshtein distance
- THEN system SHALL:
  - Calculate edit distance
  - Evaluate against threshold (0.85)
  - Match or reject based on calculation

### Requirement: TF-IDF Fallback
The system MUST support keyword-based classification when metadata insufficient.

#### Scenario: Metadata enrichment insufficient
- GIVEN playlist with few artist matches and no metadata genres
- WHEN artist-based scoring is exhausted
- THEN system SHALL:
  - Extract keywords from track names (TF-IDF)
  - Compare against genre keyword lists
  - Award partial points (default weight: 0.5)
  - Contribute to confidence calculation

#### Scenario: TF-IDF keyword matching
- GIVEN track name "Syntwave Dreams"
- WHEN TF-IDF extracts keywords ["synthwave", "dreams"]
- THEN system SHALL:
  - Search keyword matches to genre lexicons
  - Award points for "synthwave" → electronic genre mapping
  - Consider context and frequency

#### Scenario: TF-IDF minimum score threshold
- GIVEN tfidf_min_score = 0.3 in configuration
- WHEN TF-IDF keyword match score falls below 0.3
- THEN system SHALL:
  - Ignore keyword match (too weak signal)
  - Not contribute to genre score
  - Continue with other signals

### Requirement: Scoring Aggregation
The system MUST aggregate weighted signals into final score and genre.

#### Scenario: Score calculation
- GIVEN:
  - 10 artist direct matches (weight 5.0 each) = 50 points
  - 5 artist fuzzy matches (weight 2.0 each) = 10 points
  - 20 track metadata genres (weight 1.5 each) = 30 points
  - Total = 90 points
- WHEN final score is calculated
- THEN system SHALL:
  - Normalize score (90 / max_possible) = confidence percentage
  - Select genre with highest accumulated score
  - Return genre assignment with confidence

#### Scenario: Multi-genre contention
- GIVEN scores:
  - Hip-hop: 65 points
  - Funk-disco: 60 points
- WHEN final classification selected
- THEN system SHALL:
  - Select hip-hop (highest score)
  - Report confidence based on score (e.g., 65%)
  - Note runner-up genre in results for edge cases

#### Scenario: No clear winner
- GIVEN scores:
  - Hip-hop: 45 points
  - Electronic: 40 points
  - Rock: 38 points
- WHEN none exceed confidence_threshold (0.60)
- THEN system SHALL:
  - Return "unclassified"
  - Report all confidence scores
  - Flag for human review or metadata enrichment

### Requirement: Genre Configuration
The system MUST support customizable genre weights and mappings.

#### Scenario: Adjust artist_direct_match weight
- GIVEN weight configuration change: artist_direct_match = 8.0 (vs default 5.0)
- WHEN classification runs
- THEN system SHALL:
  - Apply new weight to artist direct matches
  - Increase emphasis on artist-based classification
  - Affect downstream results and confidence

#### Scenario: Genre mapping for unmapped source
- GIVEN track metadata contains "Dance" (unmapped genre)
- WHEN genre_map.json includes: {"Dance": "electronic"}
- THEN system SHALL:
  - Map "Dance" to "electronic"
  - Award points to electronic genre
  - Track mapping decision in results

### Requirement: Batch Processing
The system MUST efficiently classify multiple playlists.

#### Scenario: Classify playlist collection
- GIVEN 100 playlists to classify
- WHEN classify_batch(playlists) is called
- THEN system SHALL:
  - Process all playlists efficiently
  - Return list of classifications with confidence
  - Complete within reasonable time (< 10s for 100 playlists)
  - Log any playlists that result in "unclassified"

#### Scenario: Parallel classification
- GIVEN multi-core system and 100 playlists
- WHEN parallel classification enabled
- THEN system SHALL:
  - Distribute across available cores
  - Maintain deterministic results (same as serial)
  - Improve performance by factor of available cores

### Requirement: Result Reporting
The system MUST provide detailed classification results.

#### Scenario: Classification result format
- GIVEN successful classification
- THEN system SHALL return:
  ```
  {
    "playlist_id": "uuid",
    "playlist_name": "Summer Hits",
    "genre": "disco-funk-soul",
    "confidence": 0.87,
    "scoring_breakdown": {
      "hip-hop": 10,
      "electronic": 15,
      "disco-funk-soul": 65,
      ...
    },
    "signals": [
      {"type": "artist_direct", "count": 10, "weight": 5.0},
      {"type": "artist_fuzzy", "count": 3, "weight": 2.0},
      ...
    ]
  }
  ```

#### Scenario: Unclassified result format
- GIVEN classification results in unclassified
- THEN system SHALL return:
  ```
  {
    "playlist_id": "uuid",
    "playlist_name": "Mixed Playlist",
    "genre": null,
    "confidence": 0.45,
    "reason": "Confidence below threshold 0.60",
    "scoring_breakdown": { ... },
    "recommendation": "Enrich metadata for better classification"
  }
  ```
