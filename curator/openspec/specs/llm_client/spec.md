# LLM Client Specifications

## Context & Implementation Guide

LLM Client provides abstract interface for music temperament classification using multiple LLM providers. The system supports OpenAI GPT, Anthropic Claude, and Mock keyword-based implementations, with configurable retry policies, timeout handling, and graceful fallback behavior.

### Core Features

- **Multiple provider support**: OpenAI (GPT), Anthropic (Claude), Mock (keyword-based)
- **Configurable API selection**: Environment-based provider selection
- **Retry policy**: Automatic retries with exponential backoff on transient failures
- **Timeout handling**: Configurable request timeouts with graceful degradation
- **Mock fallback**: Free keyword-based classification without API costs
- **Api key validation**: Early detection of missing credentials before client initialization
- **Streaming support**: Optional streaming responses for long-running operations
- **Cost tracking**: Optional usage tracking and rate limiting

### Implementation Files

- `src/llm_client.py` - LLM provider implementations (Mock, Anthropic)
- `src/temperament_analyzer.py` - OpenAI client and orchestration
- `src/prompts.py` - LLM prompt templates for temperament analysis
- `tests/test_temperament_analyzer_quick.py` - Client tests

### Configuration

- Environment variables:
  - `OPENAI_API_KEY` - OpenAI API key (required for GPT)
  - `ANTHROPIC_API_KEY` - Anthropic API key (required for Claude)
  - `LLM_PROVIDER` - Provider selection (mock, openai, anthropic, default: openai)
  - `LLM_TIMEOUT` - Request timeout in seconds (default: 30)
  - `LLM_MAX_RETRIES` - Maximum retry attempts (default: 3)
- `src/prompts.py` - Prompt templates for each temperament

### API Providers

- **OpenAI**: GPT-3.5-turbo / GPT-4 models
  - Requires: OPENAI_API_KEY from https://platform.openai.com/api-keys
  - Timeout: Configurable (default 30s)
  - Retry: Exponential backoff on rate limits and transient errors

- **Anthropic**: Claude models
  - Requires: ANTHROPIC_API_KEY
  - Timeout: Configurable
  - Retry: Exponential backoff

- **Mock**: Keyword-based heuristics
  - Free: No API key required
  - Fast: Immediate response
  - Deterministic: Pattern-based classification

### Deployment Constraints

- **API credentials required**: At least one LLM provider must be configured
- **Network required**: API providers need internet connectivity
- **Rate limits**: OpenAI rate limits apply (tracked per account)
- **Cost**: Production use incurs API costs for paid providers

### Related Domains

- **Temperament Analysis** (`temperament`) - Consumer of LLM client
- **Metadata Enrichment** (`metadata`) - Optional use for field-aware querying

---

## Overview

LLM Client SHALL provide abstract interface for music temperament classification with multiple providers, configurable retry policies, and graceful fallback behavior.

### Requirement: Provider Abstraction
The system MUST support multiple LLM providers through common interface.

#### Scenario: Classify track with OpenAI
- GIVEN OPENAI_API_KEY is configured
- WHEN classify_track() is called
- THEN the system SHALL call OpenAI API
- AND return ClassificationResult with temperament and confidence

#### Scenario: Classify track with Anthropic
- GIVEN ANTHROPIC_API_KEY is configured and LLM_PROVIDER=anthropic
- WHEN classify_track() is called
- THEN the system SHALL call Anthropic API
- AND return ClassificationResult with same schema

#### Scenario: Classify track with Mock provider
- GIVEN LLM_PROVIDER=mock
- WHEN classify_track() is called
- THEN the system SHALL use keyword-based heuristics
- AND return result immediately without API call

### Requirement: Credential Validation
The system MUST validate credentials before initializing client.

#### Scenario: Missing API key for selected provider
- GIVEN OPENAI_API_KEY is not set
- WHEN OpenAILLMClient is instantiated
- THEN the system MUST fail with clear error before making API call
- AND log configuration error
- AND suggest setup documentation

#### Scenario: Invalid API key
- GIVEN OPENAI_API_KEY is set but invalid
- WHEN first API call is made
- THEN the system SHALL detect authentication failure
- AND return error status
- AND NOT retry invalid credentials

### Requirement: Retry Policy
The system MUST implement exponential backoff on transient failures.

#### Scenario: Rate limit hit
- GIVEN API provider returns 429 (too many requests)
- WHEN request completes
- THEN the system SHALL wait exponentially (2^attempt seconds)
- AND retry up to LLM_MAX_RETRIES times
- AND return error if retries exhausted

#### Scenario: Transient network error
- GIVEN network timeout or temporary unavailability (5xx)
- WHEN request is attempted
- THEN the system SHALL retry with exponential backoff
- AND succeed if connection restored within retry window

#### Scenario: Permanent error (4xx non-auth)
- GIVEN API returns 400 Bad Request (invalid prompt, etc.)
- WHEN error is returned
- THEN the system SHALL NOT retry
- AND return error immediately

### Requirement: Timeout Handling
The system MUST enforce timeouts and handle gracefully.

#### Scenario: Request exceeds timeout
- GIVEN LLM_TIMEOUT is set (default 30s)
- WHEN API request exceeds timeout
- THEN the system SHALL cancel request
- AND return error status
- AND NOT block subsequent requests

#### Scenario: Timeout with retries remaining
- GIVEN first request times out and retries remain
- WHEN timeout occurs
- THEN the system SHALL retry with same or longer timeout
- AND return error if retries exhausted

### Requirement: Playlist vs Track Classification
The system MUST support both individual and aggregate classification.

#### Scenario: Classify single track
- GIVEN track metadata is available
- WHEN classify_track(track) is called
- THEN the system SHALL return single ClassificationResult
- AND include temperament, confidence, and reasoning

#### Scenario: Classify playlist from track classifications
- GIVEN multiple track classifications exist
- WHEN classify_playlist(playlist, track_results) is called
- THEN the system SHALL aggregate results
- AND use majority voting or weighted approach
- AND return single playlist ClassificationResult

#### Scenario: Mixed track/playlist modes
- GIVEN some tracks may be classified individually, others as playlist
- WHEN both modes are used
- THEN results MUST be consistent
- AND same aggregation strategy applies

### Requirement: Mock Provider Behavior
The system MUST provide fast keyword-based fallback.

#### Scenario: Keyword pattern matching
- GIVEN MockLLMClient is active
- WHEN classify_track() is called
- THEN the system SHALL search track metadata for keywords
- AND match against predefined patterns for Woe, Frolic, Dread, Malice

#### Scenario: No keywords matched
- GIVEN track metadata contains no matching keywords
- WHEN classification runs
- THEN the system SHALL return random temperament
- AND set low confidence (0.3+)
- AND include reason in classification result

#### Scenario: Multiple keywords match
- GIVEN track metadata matches multiple patterns
- WHEN classification runs
- THEN the system SHALL return most-matched temperament
- AND scale confidence by match count

### Requirement: Error Resilience
The system MUST not interrupt playlist analysis on per-track failure.

#### Scenario: API error during playlist analysis
- GIVEN one track fails during classification
- WHEN playlist analysis continues
- THEN the system SHALL log failure
- AND skip that track
- AND complete analysis for remaining tracks

#### Scenario: Provider unavailable mid-batch
- GIVEN API provider goes down during batch operation
- WHEN requests start failing
- THEN the system SHALL detect pattern
- AND return partial results with error context
- AND suggest retry or fallback provider

### Requirement: Prompt Management
The system MUST use configurable prompts for LLM requests.

#### Scenario: Load prompt template
- GIVEN prompt template exists in src/prompts.py
- WHEN classify_track() prepares request
- THEN the system SHALL load and interpolate template
- AND inject track metadata
- AND send to LLM

#### Scenario: Prompt version compatibility
- GIVEN LLM provider version changes
- WHEN prompts need updating
- THEN system MUST support multiple prompt versions
- AND select based on model or configuration
