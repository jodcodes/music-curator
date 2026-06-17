# Functional Specification: Temperament Analyzer (4 Tempers)

## Overview
AI-based playlist emotion classification system that categorizes playlists into one of four emotional temperaments based on their musical characteristics.

## Purpose
Automatically analyze and classify music playlists into emotional categories (Woe, Frolic, Dread, Malice) using AI analysis, enabling users to organize their music library by emotional resonance.

## Functional Requirements

### F1: Playlist Analysis
- Connect to Apple Music application
- Retrieve all playlists or user-selected playlists
- Extract track metadata (title, artist, album)

### F2: AI-Based Classification
- Send playlist information to OpenAI GPT
- Receive emotional temperament classification
- Support four temperament categories:
  - **Woe**: Sad, melancholic, introspective
  - **Frolic**: Happy, upbeat, energetic
  - **Dread**: Dark, ominous, intense
  - **Malice**: Aggressive, hostile, chaotic

### F3: Result Storage
- Store analysis results with metadata
- Log results for audit trail
- Handle previously analyzed playlists

### F4: Error Handling
- Gracefully handle missing API keys
- Manage authentication failures with Music.app
- Handle network timeouts with OpenAI API

## Technical Requirements

### T1: Dependencies
- OpenAI Python SDK (`openai`)
- Music.app integration via AppleScript
- Standard library: `json`, `logging`, `subprocess`

### T2: Environment Variables
- `OPENAI_API_KEY` - Required for GPT API access

### T3: Data Flow
1. User selects playlists in interactive mode
2. System authenticates with Music.app
3. Extract playlist tracks and metadata
4. Send to OpenAI for classification
5. Return results to user
6. Log results to file

### T4: API Integration
- **OpenAI**: GPT model for playlist analysis
- **Music.app**: AppleScript bridge for playlist access

### T5: Logging
- All operations logged to `temperament_analyzer.log`
- Include timestamps and error messages
- Track API calls and responses

## Input/Output

### Input
- Selected playlist name or list of playlists
- Playlist tracks with metadata (artist, title, album)

### Output
- Temperament classification (Woe, Frolic, Dread, Malice)
- Analysis confidence score
- Reasoning/explanation from GPT

## Configuration
- OpenAI API key in `.env` file
- Default model: GPT-3.5-turbo or GPT-4
- Max tokens per request: configurable

## Dependencies
- `openai` - OpenAI API client
- `subprocess` - AppleScript execution
- `logging` - Log management

## Implementation Details
- Source: `src/temperament_analyzer.py`
- Entry point: `main.py` → `run_temperament_analysis()`
- Related: `src/apple_music.py`, `src/logger.py`

## Error Scenarios
- Missing OPENAI_API_KEY → Error message and exit
- Cannot connect to Music.app → Retry or abort
- API rate limit exceeded → Queue for later processing
- Invalid playlist name → Prompt for selection

## Non-Functional Requirements

### Performance Requirements
- **Analysis Time**: < 30 seconds per playlist (excludes API latency)
- **Memory Usage**: < 200MB for typical playlist (500 tracks)
- **Throughput**: 1 playlist per minute (including API wait)
- **Concurrency**: Single-threaded (sequential playlist processing)
- **Max Playlist Size**: Support playlists with up to 10,000 tracks

### Reliability & Robustness
- **Retry Strategy**: Exponential backoff (1s, 2s, 4s, 8s) max 3 retries
- **API Timeout**: 30 seconds per request
- **Music.app Reconnect**: Retry up to 2 times with 2-second delay
- **Partial Failure**: Log failed playlists, continue with others
- **Rate Limiting**: Respect OpenAI rate limits (wait time provided in response)

### Security & Data Privacy
- Never log full playlist data to files
- Sanitize playlist names in logs (remove user identifiers)
- Store results without sensitive track information
- API key must be in .env (never in code/logs)
- Audit trail: Log timestamp, playlist, temperament result

## Data Models/Schemas

### PlaylistAnalysis Result Schema
```python
{
    "playlist_name": str,           # Playlist identifier
    "analysis_timestamp": str,      # ISO 8601 timestamp
    "temperament": str,             # One of: Woe, Frolic, Dread, Malice
    "confidence_score": float,      # 0.0-1.0 confidence level
    "reasoning": str,               # GPT explanation (max 500 chars)
    "track_count": int,             # Number of tracks analyzed
    "api_calls_used": int,          # OpenAI API calls
    "processing_time_seconds": float
}
```

## Acceptance Criteria
- ✓ Successfully classifies valid playlist into one of 4 temperaments
- ✓ Handles 500-track playlists without crashes
- ✓ Retries on API failures (OpenAI rate limit, timeout)
- ✓ Logs all operations with timestamps
- ✓ Gracefully handles missing OPENAI_API_KEY
- ✓ Skips playlists that cannot be accessed
- ✓ Returns meaningful error messages to user

## Constraints & Compatibility
- **Python Version**: 3.8+
- **macOS Version**: 10.13+ (Music.app requirement)
- **Disk Space**: 10MB for logs (configurable)
- **Network**: Requires internet for OpenAI API
- **API Key**: Must have active OpenAI account with API credits

## Test Strategy
### Unit Tests
- [ ] Mock OpenAI API responses
- [ ] Test all 4 temperament classifications
- [ ] Test retry logic (simulate failures)
- [ ] Test logging functionality
- [ ] Test invalid inputs (empty playlists, no API key)

### Integration Tests
- [ ] Full workflow with mock Music.app data
- [ ] API error scenarios (rate limit, timeout, network error)
- [ ] Results persistence and retrieval

### Test Data
- Mock playlists with 10, 50, 500 tracks
- Pre-recorded GPT responses for consistency
- Mock Music.app responses

## State Management
- **Result Storage**: JSON file in `data/logs/temperament_results.json`
- **State File Format**: Append-only log (one result per line)
- **Re-analysis**: Allow overwriting previous results with timestamp tracking
- **Concurrency**: Not thread-safe (single-threaded CLI only)
- **Recovery**: Results file survives CLI interruption (idempotent)

## Caching Strategy
- **Cache Type**: Simple memory cache during session
- **What to Cache**: GPT responses per playlist name
- **TTL**: Session-only (cleared on CLI exit)
- **Invalidation**: User can force re-analysis
- **Size Limit**: Max 50 cached results per session

## Backwards Compatibility
- Results JSON schema versioned (include `schema_version: 1`)
- Support reading old results format with migration
- API key format may change (validate format before use)
