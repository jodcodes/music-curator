"""
LLM Prompts and Temperament Definitions

Contains all system prompts and user prompts for music temperament classification.
"""

import logging

logger = logging.getLogger(__name__)

# ==================== TEMPERAMENT DEFINITIONS ====================

TEMPERAMENTS = {
    "Woe": {
        "display": "Woe (Melancholic)",
        "emoji": "🌧️",
        "description": "Melancholic - representing sadness, sorrow, loneliness, and introspection",
        "characteristics": [
            "Sad or melancholic tone",
            "Minor keys and slow tempos",
            "Emotional vulnerability",
            "Introspective lyrics about loss or heartbreak",
            "Themes of isolation or depression",
        ],
    },
    "Frolic": {
        "display": "Frolic (Sanguine)",
        "emoji": "☀️",
        "description": "Sanguine - representing joy, happiness, celebration, and optimism",
        "characteristics": [
            "Upbeat and energetic",
            "Major keys and faster tempos",
            "Positive and uplifting lyrics",
            "Themes of love, celebration, or success",
            "Infectious rhythms for dancing",
        ],
    },
    "Dread": {
        "display": "Dread (Phlegmatic)",
        "emoji": "😰",
        "description": "Phlegmatic - representing fear, anxiety, tension, and unease",
        "characteristics": [
            "Tense and suspenseful atmosphere",
            "Dark or ominous soundscapes",
            "Themes of fear, anxiety, or horror",
            "Dissonant chords or unsettling tones",
            "Slow builds or sudden climaxes",
        ],
    },
    "Malice": {
        "display": "Malice (Choleric)",
        "emoji": "🔥",
        "description": "Choleric - representing anger, rage, intensity, and aggression",
        "characteristics": [
            "Aggressive or intense energy",
            "Heavy drums and distorted instruments",
            "Themes of anger, rebellion, or conflict",
            "Fast tempos and powerful vocals",
            "Confrontational or rebellious lyrics",
        ],
    },
}

# ==================== SYSTEM PROMPTS ====================

SYSTEM_PROMPT_TRACK = """You are a music emotion analyst with expertise in music psychology and emotional classification.

Your task is to classify individual music tracks into one of four temperament categories based on their emotional content and characteristics.

Each temperament represents a distinct emotional spectrum:
- Woe (Melancholic): Sadness, sorrow, introspection, loneliness
- Frolic (Sanguine): Joy, happiness, celebration, optimism  
- Dread (Phlegmatic): Fear, anxiety, tension, unease
- Malice (Choleric): Anger, rage, intensity, aggression

Consider:
1. Track name and artist style
2. Genre conventions and typical emotions
3. Album context and release year
4. Any explicit emotional indicators in metadata

Be decisive and confident in your classification. Choose the PRIMARY emotion that best captures the track's overall mood."""

SYSTEM_PROMPT_PLAYLIST = """You are a music emotion analyst specializing in playlist curation and emotional classification.

Your task is to classify entire playlists into one of four temperament categories based on:
1. Individual track classifications and their confidence scores
2. Overall playlist name and description
3. The dominant emotional theme across all tracks
4. The intended listening context and mood

The four temperament categories:
- Woe (Melancholic): Sadness, sorrow, introspection, loneliness
- Frolic (Sanguine): Joy, happiness, celebration, optimism
- Dread (Phlegmatic): Fear, anxiety, tension, unease
- Malice (Choleric): Anger, rage, intensity, aggression

Make a holistic judgment that reflects the PRIMARY emotional experience of the playlist as a whole.
Use the track classifications as supporting evidence, but also consider the playlist's overall theme and name."""

# ==================== USER PROMPTS ====================


def get_track_classification_prompt(track_metadata: str) -> str:
    """Generate prompt for classifying a single track"""
    logger.info("Generating track classification prompt")

    prompt = f"""Analyze the following music track and classify it into ONE of these four temperament categories:

1. **Woe (Melancholic)** - Sadness, melancholy, sorrow, despair, loneliness, introspection
   Examples: Sad ballads, breakup songs, lonely piano pieces, introspective folk

2. **Frolic (Sanguine)** - Joy, happiness, excitement, celebration, optimism, energy
   Examples: Dance tracks, upbeat pop, celebratory anthems, feel-good party music

3. **Dread (Phlegmatic)** - Fear, anxiety, tension, unease, horror, suspense
   Examples: Dark ambient, horror soundtracks, tense orchestral, unsettling electronic

4. **Malice (Choleric)** - Anger, rage, aggression, intensity, rebellion, conflict
   Examples: Heavy metal, aggressive rap, punk, intense rock, confrontational music

Track Information:
{track_metadata}

Consider the track name, artist style, genre, and any emotional indicators.

Respond in JSON format:
{{
    "temperament": "Woe" | "Frolic" | "Dread" | "Malice",
    "confidence": 0.0-1.0,
    "reasoning": "Explain why you classified this track as [temperament]"
}}"""

    return prompt


def get_playlist_classification_prompt(
    playlist_metadata: str, track_summary: str, sample_tracks: str
) -> str:
    """Generate prompt for classifying a playlist"""
    logger.info("Generating playlist classification prompt")

    prompt = f"""Analyze this playlist and classify it into ONE of these four temperament categories:

1. **Woe (Melancholic)** - Sadness, melancholy, sorrow, despair, loneliness, introspection
2. **Frolic (Sanguine)** - Joy, happiness, excitement, celebration, optimism, energy
3. **Dread (Phlegmatic)** - Fear, anxiety, tension, unease, horror, suspense
4. **Malice (Choleric)** - Anger, rage, aggression, intensity, rebellion, conflict

Playlist Information:
{playlist_metadata}

Track-Level Analysis Summary:
{track_summary}

Sample Tracks (First 5):
{sample_tracks}

Consider:
- The overall playlist name and description
- The distribution of track classifications
- The dominant emotional theme
- The intended listening experience

Respond in JSON format:
{{
    "temperament": "Woe" | "Frolic" | "Dread" | "Malice",
    "confidence": 0.0-1.0,
    "reasoning": "Explain why the playlist is primarily [temperament] based on the tracks and theme"
}}"""

    return prompt


def log_temperament_info():
    """Log all temperament definitions for debugging"""
    logger.info("=" * 60)
    logger.info("TEMPERAMENT DEFINITIONS")
    logger.info("=" * 60)
    for temp_key, temp_info in TEMPERAMENTS.items():
        logger.info(f"\n{temp_info['emoji']} {temp_info['display']}")
        logger.info(f"   Description: {temp_info['description']}")
        logger.info(f"   Characteristics:")
        for char in temp_info["characteristics"]:
            logger.info(f"     - {char}")
    logger.info("=" * 60)
