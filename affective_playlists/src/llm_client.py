#!/usr/bin/env python3
"""
LLM Client Implementations

Provides different LLM providers for music temperament classification:
- MockLLMClient: Keyword-based heuristics (free, no API key needed)
- AnthropicLLMClient: Claude AI (requires ANTHROPIC_API_KEY)
- OpenAILLMClient: (from temperament_analyzer.py)
"""

import random
from typing import List

from src.temperament_analyzer import ClassificationResult, LLMClient, Playlist, Temperament, Track


class MockLLMClient(LLMClient):
    """
    Mock LLM client for testing without API costs.
    Uses keyword-based heuristics instead of actual AI.
    """

    # Keyword patterns for each temperament
    PATTERNS = {
        Temperament.WOE: [
            "sad",
            "blue",
            "lonely",
            "tears",
            "heartbreak",
            "melancholy",
            "sorrow",
            "goodbye",
        ],
        Temperament.FROLIC: [
            "happy",
            "joy",
            "dance",
            "party",
            "fun",
            "celebration",
            "sunshine",
            "smile",
        ],
        Temperament.DREAD: ["dark", "fear", "nightmare", "horror", "anxiety", "shadow", "haunted"],
        Temperament.MALICE: [
            "rage",
            "anger",
            "fight",
            "war",
            "hate",
            "destroy",
            "metal",
            "punk",
            "kill",
        ],
    }

    def classify_track(self, track: Track) -> ClassificationResult:
        """Classify track using keyword matching"""

        # Combine all track metadata into lowercase string
        text = f"{track.name} {track.artist} {track.album or ''} {track.genre or ''}".lower()

        # Count matches for each temperament
        scores = {}
        for temperament, keywords in self.PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            scores[temperament] = score

        # Find best match
        if max(scores.values()) > 0:
            best_temperament = max(scores, key=lambda x: scores[x])
            confidence = min(0.9, scores[best_temperament] * 0.3 + 0.5)  # Scale confidence
        else:
            # Default to random if no keywords match
            best_temperament = random.choice(list(Temperament))
            confidence = 0.3

        reasoning = f"Keyword analysis: {scores}. Text: '{text[:50]}...'"

        return ClassificationResult(
            temperament=best_temperament, confidence=confidence, reasoning=reasoning
        )

    def classify_playlist(
        self, playlist: Playlist, track_classifications: List[ClassificationResult]
    ) -> ClassificationResult:
        """Classify playlist using majority vote from tracks"""

        from collections import Counter

        # Count temperaments from track classifications
        temperament_counts = Counter([c.temperament for c in track_classifications])

        # Get dominant temperament
        if temperament_counts:
            dominant = temperament_counts.most_common(1)[0][0]
            count = temperament_counts[dominant]
            total = len(track_classifications)
            confidence = count / total
        else:
            dominant = Temperament.FROLIC
            confidence = 0.3

        reasoning = f"Mock analysis - majority vote from {len(track_classifications)} tracks: {dict(temperament_counts)}"

        return ClassificationResult(
            temperament=dominant, confidence=confidence, reasoning=reasoning
        )


class AnthropicLLMClient(LLMClient):
    """
    Example Anthropic Claude integration.

    To use this:
    1. pip install anthropic
    2. Set ANTHROPIC_API_KEY environment variable
    3. Replace OpenAILLMClient with AnthropicLLMClient in main()
    """

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        import os

        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        # Import anthropic only if this client is used
        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

    def classify_track(self, track: Track) -> ClassificationResult:
        """Classify track using Claude"""

        prompt = f"""Analyze this music track and classify it into ONE category:
1. Woe (Melancholic) - sadness
2. Frolic (Sanguine) - joy
3. Dread (Phlegmatic) - fear
4. Malice (Choleric) - rage

Track: {track.get_metadata_string()}

Respond ONLY with JSON:
{{"temperament": "Woe"|"Frolic"|"Dread"|"Malice", "confidence": 0.0-1.0, "reasoning": "brief"}}"""

        try:
            message = self.client.messages.create(
                model=self.model, max_tokens=200, messages=[{"role": "user", "content": prompt}]
            )

            import json

            response_text = message.content[0].text  # type: ignore[union-attr]

            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_str = response_text[start:end]

            result = json.loads(json_str)

            temp_map = {
                "Woe": Temperament.WOE,
                "Frolic": Temperament.FROLIC,
                "Dread": Temperament.DREAD,
                "Malice": Temperament.MALICE,
            }

            return ClassificationResult(
                temperament=temp_map.get(result["temperament"], Temperament.FROLIC),
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", "No reasoning"),
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Claude API error: {e}")
            return ClassificationResult(
                temperament=Temperament.FROLIC, confidence=0.1, reasoning=f"Error: {str(e)}"
            )

    def classify_playlist(
        self, playlist: Playlist, track_classifications: List[ClassificationResult]
    ) -> ClassificationResult:
        """Classify playlist using Claude"""

        from collections import Counter

        temperament_counts = Counter([c.temperament for c in track_classifications])

        prompt = f"""Classify this playlist into ONE category based on track analysis:

Playlist: {playlist.get_metadata_string()}
Tracks: {len(playlist.tracks)}

Track analysis summary:
{dict(temperament_counts)}

Categories:
1. Woe (Melancholic) - sadness
2. Frolic (Sanguine) - joy  
3. Dread (Phlegmatic) - fear
4. Malice (Choleric) - rage

Respond ONLY with JSON:
{{"temperament": "Woe"|"Frolic"|"Dread"|"Malice", "confidence": 0.0-1.0, "reasoning": "brief"}}"""

        try:
            message = self.client.messages.create(
                model=self.model, max_tokens=200, messages=[{"role": "user", "content": prompt}]
            )

            import json

            response_text = message.content[0].text  # type: ignore[union-attr]

            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_str = response_text[start:end]

            result = json.loads(json_str)

            temp_map = {
                "Woe": Temperament.WOE,
                "Frolic": Temperament.FROLIC,
                "Dread": Temperament.DREAD,
                "Malice": Temperament.MALICE,
            }

            return ClassificationResult(
                temperament=temp_map.get(result["temperament"], Temperament.FROLIC),
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", "No reasoning"),
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Claude API error: {e}")
            # Fallback to majority vote
            dominant = (
                temperament_counts.most_common(1)[0][0]
                if temperament_counts
                else Temperament.FROLIC
            )
            return ClassificationResult(
                temperament=dominant, confidence=0.3, reasoning=f"Fallback due to error: {str(e)}"
            )
