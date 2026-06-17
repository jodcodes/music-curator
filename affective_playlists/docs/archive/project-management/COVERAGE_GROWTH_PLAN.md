# Coverage Growth Test Plan

## Overview
This document outlines the test scenarios needed to improve coverage for enrichment edge-cases and fallback paths.

## Critical Coverage Gaps (Priority Order)

### 1. Metadata Enrichment Fallbacks
**Module**: `src/metadata_enrichment.py` + `src/metadata_queries.py`

- [ ] **Test**: Multi-source fallback when first source fails
  - Setup: Configure sources [A, B, C]
  - Arrange: A returns error, B succeeds
  - Assert: Field uses value from B, continues
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_source_fallback_on_first_failure`

- [ ] **Test**: Exhaustion of all sources without match
  - Setup: BPM field missing from all sources
  - Arrange: All sources queried
  - Assert: Field remains empty, enrich_once stops querying
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_exhausted_sources`

- [ ] **Test**: Per-track error isolation in batch
  - Setup: 5 tracks, track #3 fails at write-back
  - Arrange: Batch enrichment runs
  - Assert: Tracks 1,2,4,5 succeed; track 3 logged, continues
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_batch_error_isolation`

- [ ] **Test**: Apple Music cover-art guard
  - Setup: Track from Apple Music, cover-art embedding requested
  - Arrange: System detects Apple Music source
  - Assert: Skip embedding, log reason
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_apple_music_cover_art_guard`

### 2. Network & API Failures
**Module**: `src/metadata_queries.py` + `src/llm_client.py`

- [ ] **Test**: Timeout on API query
  - Setup: Slow metadata source (timeout < response time)
  - Arrange: Query with timeout
  - Assert: Timeout caught, move to next source
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_source_timeout_fallback`

- [ ] **Test**: Rate limit handling (429 response)
  - Setup: Source returns 429
  - Arrange: Retry logic active
  - Assert: Exponential backoff, retry succeeds or move to next
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_rate_limit_retry`

- [ ] **Test**: Invalid API key detection
  - Setup: Bad API key for Spotify/MusicBrainz
  - Arrange: Query executes
  - Assert: 401/403 caught early, skip source
  - File: `tests/test_metadata_enrichment_fallbacks.py::test_invalid_api_key_detection`

- [ ] **Test**: LLM timeout with retry
  - Setup: OpenAI request times out
  - Arrange: Retry max_retries=3
  - Assert: Attempt 3x, then fail with log
  - File: `tests/test_temperament_analyzer_fallbacks.py::test_llm_timeout_retry`

### 3. Playlist Organization Safeguards
**Module**: `src/playlist_classifier.py` + `src/playlist_manager.py`

- [ ] **Test**: Unclassified playlist not moved
  - Setup: Playlist with insufficient metadata
  - Arrange: Classification confidence < threshold
  - Assert: Marked unclassified, not in move list
  - File: `tests/test_playlist_classifier_fallbacks.py::test_unclassified_not_moved`

- [ ] **Test**: Dry-run does not modify playlists
  - Setup: Dry-run mode active
  - Arrange: Move operation requested
  - Assert: Reports intended moves, no changes made
  - File: `tests/test_playlist_manager_fallbacks.py::test_dryrun_no_modifications`

- [ ] **Test**: User cancel prevents moves
  - Setup: Confirmation requested
  - Arrange: User declines
  - Assert: No playlists moved, exit cleanly
  - File: `tests/test_playlist_manager_fallbacks.py::test_user_cancel_prevents_moves`

- [ ] **Test**: Folder creation on move
  - Setup: Target folder does not exist
  - Arrange: Move operation initiated
  - Assert: Create folder, then move
  - File: `tests/test_playlist_manager_fallbacks.py::test_create_folder_on_move`

### 4. Temperament Analysis Resilience
**Module**: `src/temperament_analyzer.py`

- [ ] **Test**: Per-playlist error isolation
  - Setup: 3 playlists, playlist #2 fails LLM call
  - Arrange: Batch analysis runs
  - Assert: Playlists 1,3 complete; #2 logged, continues
  - File: `tests/test_temperament_analyzer_fallbacks.py::test_playlist_error_isolation`

- [ ] **Test**: Missing OPENAI_API_KEY early detection
  - Setup: OPENAI_API_KEY not set
  - Arrange: TemperamentAnalyzer instantiation
  - Assert: Fail before client init, print setup help
  - File: `tests/test_temperament_analyzer_fallbacks.py::test_missing_api_key_early`

- [ ] **Test**: Music.app unavailability
  - Setup: Music.app not accessible (or non-macOS)
  - Arrange: Analysis starts
  - Assert: Detect unavailability, return auth error
  - File: `tests/test_temperament_analyzer_fallbacks.py::test_music_app_unavailable`

- [ ] **Test**: Mock provider fallback
  - Setup: OpenAI API fails, Mock configured as fallback
  - Arrange: Classification with Mock active
  - Assert: Use keyword matching, continue
  - File: `tests/test_temperament_analyzer_fallbacks.py::test_mock_provider_fallback`

### 5. Configuration & State
**Module**: `src/config.py` + environment handling

- [ ] **Test**: Missing whitelist file
  - Setup: whitelist.json path invalid
  - Arrange: Load config
  - Assert: Log warning, continue without whitelist
  - File: `tests/test_config_fallbacks.py::test_missing_whitelist_loading`

- [ ] **Test**: Corrupted JSON config
  - Setup: weights.json has syntax error
  - Arrange: Load config
  - Assert: Catch JSON error, use defaults
  - File: `tests/test_config_fallbacks.py::test_corrupted_json_config`

- [ ] **Test**: Environment variable override
  - Setup: Config value + ENV VAR
  - Arrange: Both set
  - Assert: ENV VAR takes precedence
  - File: `tests/test_config_fallbacks.py::test_env_var_override`

## Test Organization

### New Test Files
- `tests/test_metadata_enrichment_fallbacks.py` — Enrichment edge-cases (8 tests)
- `tests/test_playlist_classifier_fallbacks.py` — Classification fallbacks (2 tests)
- `tests/test_playlist_manager_fallbacks.py` — Organization safeguards (3 tests)
- `tests/test_temperament_analyzer_fallbacks.py` — LLM resilience (5 tests)
- `tests/test_config_fallbacks.py` — Configuration edge-cases (3 tests)

**Total new tests**: ~21 tests

## Implementation Priority

1. **Phase 1**: Metadata enrichment fallbacks (highest impact)
   - Covers critical production paths
   - High failure probability (network, APIs)
   - Affects data quality

2. **Phase 2**: Temperament & LLM fallbacks
   - API cost implications
   - User experience (timeouts, retries)

3. **Phase 3**: Organization & config edge-cases
   - Safety critical (user safeguards)
   - Configuration robustness

## Metrics

- Current test count: 169 tests
- Target additional tests: 21 tests
- Target coverage: 85%+ for src/ (focus on fallback paths)

## Verification

After implementing tests:
- [ ] Run: `pytest tests/ -v --cov=src --cov-report=html`
- [ ] Check coverage report for remaining gaps
- [ ] Ensure all fallback branches have ≥ 1 test case
- [ ] Verify no "except: pass" patterns remain untested
