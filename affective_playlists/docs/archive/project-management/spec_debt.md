# Spec Debt

This file tracks implemented behavior not yet codified in `openspec/specs/`.

## Seeded This Iteration (Priority 3)
- ✅ `src/apple_music.py`: AppleScript invocation behavior and failure modes
  → Spec: openspec/specs/apple_music/spec.md (12 scenarios)
- ✅ `src/llm_client.py`: retries, timeout strategy, and provider fallback behavior
  → Spec: openspec/specs/llm_client/spec.md (11 scenarios)

## Critical (Seed Before Major Changes)
- `src/metadata_fill.py`: interactive flow and enrichment orchestration details
- `src/playlist_manager.py`: move/organization rules and safety constraints

## High (Next Iteration)
- `src/playlist_classifier.py`: scoring thresholds and fallback classification behavior
- `src/track_metadata.py`: external source query order and data normalization constraints

## Medium (Backlog)
- `src/cover_art.py`: cover-art retrieval and embedding edge-cases
- `src/audio_tags.py`: tag writing behavior per file format
- `src/result_utils.py`: output/reporting contracts

## Explicitly Deferred
- `tests/test_e2e.py.bak`: archived test artifact, not active behavior
