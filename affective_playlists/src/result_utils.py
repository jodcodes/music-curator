"""
Unified result handling and persistence utilities.

Consolidates result saving, logging, and reporting across all three features:
- Temperament Analyzer (4tempers)
- Metadata Enrichment (metad_enr)
- Playlist Organization (plsort)

Previously scattered across individual modules.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger import setup_logger
from src.models import OperationResult

logger = setup_logger(__name__)


class ResultWriter:
    """Unified result writing and persistence."""

    def __init__(self, output_dir: str = "data/logs", operation_type: str = "operation"):
        """Initialize result writer.

        Args:
            output_dir: Directory where results will be saved
            operation_type: Type of operation (temperament, enrich, organize)
        """
        self.output_dir = Path(output_dir)
        self.operation_type = operation_type
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """Ensure output directory exists."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Result output directory: {self.output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory: {e}")

    def save_results(
        self, results: List[Dict[str, Any]], filename: str, pretty: bool = True
    ) -> bool:
        """Save results to JSON file.

        Args:
            results: List of result dictionaries
            filename: Output filename (will be saved in output_dir)
            pretty: Whether to format JSON for readability

        Returns:
            True if successful, False otherwise
        """
        if not results:
            logger.warning(f"No results to save for {filename}")
            return False

        try:
            output_path = self.output_dir / filename

            with open(output_path, "w") as f:
                if pretty:
                    json.dump(results, f, indent=2)
                else:
                    json.dump(results, f)

            logger.info(f"Results saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save results to {filename}: {e}")
            return False

    def save_jsonl(self, results: List[Dict[str, Any]], filename: str) -> bool:
        """Save results to JSONL file (one JSON object per line).

        Useful for streaming large result sets without loading all into memory.

        Args:
            results: List of result dictionaries
            filename: Output filename (will be saved in output_dir)

        Returns:
            True if successful, False otherwise
        """
        if not results:
            logger.warning(f"No results to save for {filename}")
            return False

        try:
            output_path = self.output_dir / filename

            with open(output_path, "w") as f:
                for result in results:
                    f.write(json.dumps(result) + "\n")

            logger.info(f"Results saved to {output_path} ({len(results)} lines)")
            return True

        except Exception as e:
            logger.error(f"Failed to save JSONL results to {filename}: {e}")
            return False

    def append_result(self, result: Dict[str, Any], filename: str) -> bool:
        """Append a single result to JSONL file (creates if doesn't exist).

        Args:
            result: Result dictionary to append
            filename: Output filename (will be saved in output_dir)

        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = self.output_dir / filename

            # Add timestamp if not present
            if "timestamp" not in result:
                result["timestamp"] = datetime.now().isoformat()

            with open(output_path, "a") as f:
                f.write(json.dumps(result) + "\n")

            logger.debug(f"Result appended to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to append result to {filename}: {e}")
            return False


class ResultSummary:
    """Generate and print operation summaries."""

    @staticmethod
    def print_temperament_summary(results: List[Dict[str, Any]]) -> None:
        """Print summary of temperament analysis results.

        Args:
            results: List of temperament classification results
        """
        if not results:
            print("No results to summarize")
            return

        print("\n" + "=" * 60)
        print("TEMPERAMENT ANALYSIS SUMMARY")
        print("=" * 60)

        # Count by temperament
        temperament_counts: Dict[str, int] = {}
        total_confidence = 0.0

        for result in results:
            temp = result.get("temperament", "Unknown")
            temperament_counts[temp] = temperament_counts.get(temp, 0) + 1
            total_confidence += result.get("confidence", 0.0)

        # Print counts
        total = len(results)
        for temperament, count in sorted(temperament_counts.items()):
            percentage = (count / total * 100) if total > 0 else 0
            print(f"  {temperament:25s}: {count:3d} playlists ({percentage:5.1f}%)")

        avg_confidence = total_confidence / total if total > 0 else 0
        print(f"\nTotal playlists analyzed: {total}")
        print(f"Average confidence: {avg_confidence:.2f}")
        print("=" * 60 + "\n")

    @staticmethod
    def print_enrichment_summary(result: Dict[str, Any]) -> None:
        """Print summary of metadata enrichment results.

        Args:
            result: Result dictionary from enrichment operation
        """
        print("\n" + "=" * 60)
        print("METADATA ENRICHMENT SUMMARY")
        print("=" * 60)

        processed = result.get("processed", 0)
        enriched = result.get("enriched", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors", 0)

        print(f"Processed: {processed}")
        print(f"Enriched:  {enriched}")
        print(f"Skipped:   {skipped}")
        print(f"Errors:    {errors}")

        if processed > 0:
            enriched_pct = enriched / processed * 100
            print(f"\nEnrichment rate: {enriched_pct:.1f}%")

        print("=" * 60 + "\n")

    @staticmethod
    def print_organization_summary(results: Dict[str, bool]) -> None:
        """Print summary of playlist organization results.

        Args:
            results: Dictionary mapping playlist names to success booleans
        """
        if not results:
            print("No playlists were organized")
            return

        print("\n" + "=" * 60)
        print("PLAYLIST ORGANIZATION SUMMARY")
        print("=" * 60)

        successful = sum(1 for v in results.values() if v)
        total = len(results)
        success_rate = (successful / total * 100) if total > 0 else 0

        print(f"Total playlists: {total}")
        print(f"Successfully organized: {successful}")
        print(f"Failed: {total - successful}")
        print(f"Success rate: {success_rate:.1f}%")

        print("=" * 60 + "\n")


class BatchProcessor:
    """Helper for batch processing with batching and throttling."""

    @staticmethod
    def process_in_batches(
        items: List[Any],
        process_func,
        batch_size: int = 10,
        delay_between_batches: float = 1.0,
        delay_between_items: float = 0.0,
    ) -> List[Any]:
        """Process items in batches with optional delays.

        Useful for API rate limiting and progress tracking.

        Args:
            items: Items to process
            process_func: Function to call on each item (must return result)
            batch_size: Number of items per batch before delay
            delay_between_batches: Seconds to wait between batches
            delay_between_items: Seconds to wait between individual items

        Returns:
            List of results from process_func
        """
        import time

        results = []

        for idx, item in enumerate(items, 1):
            try:
                result = process_func(item)
                results.append(result)

                # Delay between items if specified
                if delay_between_items > 0:
                    time.sleep(delay_between_items)

                # Delay between batches if specified
                if idx % batch_size == 0 and idx < len(items) and delay_between_batches > 0:
                    time.sleep(delay_between_batches)

            except Exception as e:
                logger.error(f"Error processing item {idx}: {e}")
                results.append(None)

        return results


# Re-export for convenience
__all__ = [
    "ResultWriter",
    "ResultSummary",
    "BatchProcessor",
]
