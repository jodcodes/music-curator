# Temperament Specifications

## Context & Implementation Guide

Temperament analysis uses language models to interpret track metadata and playlist context, classifying each playlist into exactly one of four emotional categories. The system includes resilient processing, API credential validation, and platform-specific constraints.

### Four Temperaments

| Temperament | Mood Profile | Example Traits |
|-------------|--------------|----------------|
| **Woe** | Sad, melancholic, introspective | Ballads, acoustic, emotional vocals |
| **Frolic** | Happy, upbeat, energetic | Pop, dance, uplifting rhythms |
| **Dread** | Dark, ominous, intense | Industrial, metal, atmospheric tension |
| **Malice** | Aggressive, hostile, chaotic | Punk, noise, confrontational energy |

### Core Features

- **Four-category classification**: Woe (sad), Frolic (happy), Dread (dark), Malice (aggressive)
- **LLM-based interpretation**: Uses OpenAI GPT to analyze playlist mood
- **Music.app authentication**: Requires valid Music.app access on macOS
- **Early credential validation**: Detects missing API keys before client initialization
- **Per-playlist error handling**: Graceful failure with clear logging on API timeouts
- **Platform constraints**: Requires macOS for Music.app access; skips on non-macOS with guidance

### Implementation Files

- `src/temperament_analyzer.py` - Core analysis orchestration
- `src/llm_client.py` - OpenAI API integration
- `src/prompts.py` - LLM prompt templates
- `tests/test_temperament_analyzer_quick.py` - Test suite

### Configuration

- Environment variable: `OPENAI_API_KEY` - Required for GPT integration
- `src/config.py` - Core configuration handling

### API Integration

- **Provider**: OpenAI (GPT models)
- **Authentication**: API key via environment variable
- **Timeout**: Configurable with retry policy
- **Fallback**: Non-zero exit code on exhausted retries with detailed logging

### Deployment Constraints

- **macOS required**: Temperament analysis requires Music.app access via AppleScript
- **API credentials required**: OPENAI_API_KEY must be set in environment
- **Non-macOS**: System exits gracefully with platform guidance; alternative workflows still available

### Related Domains

- **Metadata Enrichment** (`metadata`) - Provides enriched metadata as input context
- **Playlist Organization** (`playlists`) - Alternative classification based on genre

---

## Overview
Temperament analysis SHALL classify playlists into one of four temperaments using LLM-based interpretation of track/playlist metadata.

### Requirement: Four-Category Classification
The system MUST classify each analyzed playlist into exactly one category: Woe, Frolic, Dread, or Malice.

#### Scenario: Successful classification
- GIVEN a valid playlist with accessible tracks
- WHEN analysis completes without API error
- THEN the system SHALL return exactly one temperament label

#### Scenario: Missing API credentials
- GIVEN no valid LLM API key is configured
- WHEN temperament analysis starts
- THEN the system MUST fail fast with a user-facing configuration error

### Requirement: Music.app Access
The system MUST authenticate against Music.app before attempting playlist analysis.

#### Scenario: Authentication failure
- GIVEN Music.app is unavailable or inaccessible
- WHEN analysis starts
- THEN the system SHALL stop and return an authentication error

#### Scenario: Non-macOS execution
- GIVEN the command runs on a non-macOS platform (Linux, Windows)
- WHEN the user selects temperament analysis or playlist organization
- THEN the CLI MUST reject execution with platform-specific message
- AND the system SHALL suggest workarounds (e.g., folder enrichment for non-macOS)
- AND exit code SHALL be 1

#### Scenario: Missing API credentials (early validation)
- GIVEN OPENAI_API_KEY is not set in environment
- WHEN temperament analysis starts
- THEN the system MUST detect missing key BEFORE client initialization
- AND SHALL print setup link to https://platform.openai.com/api-keys
- AND SHALL log configuration error to structured logger
- AND exit code SHALL be 1

### Requirement: Resilient Processing
The system MUST handle per-playlist or per-request failures with clear logging.

#### Scenario: API timeout during analysis
- GIVEN the LLM request times out
- WHEN retry policy is exhausted
- THEN the system SHALL log the failure context and return a non-zero exit code
