# Text Normalization Specifications

## Context & Implementation Guide

Text Normalization provides consistent, deterministic string processing for track metadata, artist names, and playlist names across the system. This ensures reliable matching, deduplication, and consistent presentation across different data sources.

### Core Features

- **Unicode normalization**: Convert Unicode strings to consistent form (NFC, NFD, NFKC, NFKD)
- **Whitespace handling**: Strip leading/trailing spaces, normalize internal whitespace
- **Case normalization**: Convert to lowercase/uppercase consistently
- **Special character handling**: Remove or normalize diacritics, ligatures, quotes
- **Duplicate detection**: Identify near-duplicate strings accounting for minor variations
- **String comparison**: Fuzzy matching with configurable thresholds
- **Accent removal**: Strip accents while preserving base characters (café → cafe)
- **Quote normalization**: Normalize curly quotes, apostrophes to ASCII equivalents
- **Whitespace deduplication**: Collapse multiple spaces to single space
- **Encoding safety**: Ensure strings remain valid UTF-8 throughout

### Implementation Files

- `src/normalizer.py` - Core normalization functions
- `src/playlist_utils.py` - Uses normalizer for artist/track matching
- `tests/test_normalizer.py` - Normalization test suite
- `tests/test_playlist_fuzzy_matching.py` - Fuzzy matching tests

### Configuration

- Normalization forms: NFC (default), NFD, NFKC, NFKD
- Character mappings: Custom replacements for special characters
- Fuzzy matching threshold: Configurable similarity percentage (default: 0.85)
- Accent removal: Enabled by default, can be disabled per operation

### Related Domains

- **Metadata Enrichment** (`metadata`) - Uses normalizer for database query matching
- **Playlist Organization** (`playlists`) - Uses fuzzy matching for artist classification
- **Audio Tags** - Normalizes tag data before write-back

---

## Overview

Text Normalization SHALL provide deterministic string processing for consistent metadata matching, deduplication, and presentation across systems.

### Requirement: Unicode Normalization
The system MUST convert Unicode strings to a consistent, canonical form.

#### Scenario: NFC normalization (default)
- GIVEN input strings with combining characters (e.g., café with separate accent)
- WHEN normalize(text) is called without form argument
- THEN system SHALL:
  - Convert to NFC (Canonical Decomposition, followed by Canonical Composition)
  - Return single character for precomposed forms (é as single codepoint)
  - Ensure consistent byte representation for later comparison

#### Scenario: NFD normalization (decomposed)
- GIVEN input strings with precomposed characters (é as single codepoint)
- WHEN normalize(text, form='NFD') is called
- THEN system SHALL:
  - Decompose to base character + combining mark (e + ´)
  - Return canonical decomposed form
  - Enable accent-stripping operations downstream

#### Scenario: NFKC compatibility normalization
- GIVEN input with ligatures, width variants, or compatibility characters (ﬁ, ℌ, ™)
- WHEN normalize(text, form='NFKC') is called
- THEN system SHALL:
  - Convert ligatures to separated characters (ﬁ → fi)
  - Convert compatibility variants to canonical equivalents
  - Perform composition after conversion (NFKC = K + C)

### Requirement: Whitespace Handling
The system MUST normalize whitespace consistently.

#### Scenario: Leading/trailing whitespace
- GIVEN text with leading/trailing spaces ("  artist name  ")
- WHEN normalize_whitespace(text) is called
- THEN system SHALL remove leading/trailing spaces → "artist name"

#### Scenario: Internal whitespace normalization
- GIVEN text with multiple internal spaces ("artist  name")
- WHEN normalize_whitespace(text, collapse=True) is called
- THEN system SHALL collapse multiple spaces to single space → "artist name"

#### Scenario: Newline/tab handling
- GIVEN text with newlines or tabs ("artist\n\tname")
- WHEN normalize_whitespace(text, normalize_newlines=True) is called
- THEN system SHALL:
  - Convert newlines/tabs to spaces
  - Collapse to single space
  - Return "artist name"

### Requirement: Case Normalization
The system MUST support consistent case conversion.

#### Scenario: Lowercase normalization
- GIVEN mixed-case input ("The Beatles")
- WHEN normalize_case(text, case='lower') is called
- THEN system SHALL return "the beatles"

#### Scenario: Title case normalization
- GIVEN all-caps input ("PINK FLOYD")
- WHEN normalize_case(text, case='title') is called
- THEN system SHALL return "Pink Floyd" (preserve capital letters appropriately)

### Requirement: Accent & Diacritic Removal
The system MUST remove accents while preserving base characters.

#### Scenario: Accent stripping
- GIVEN input with diacritics ("José María")
- WHEN strip_accents(text) is called
- THEN system SHALL return "Jose Maria" (accents removed, base preserved)

#### Scenario: Special character handling
- GIVEN input with diacritics and special chars ("Björk Guðmundsdóttir")
- WHEN strip_accents(text) is called
- THEN system SHALL return "Bjork Gudmundsdottir"

### Requirement: Quote Normalization
The system MUST normalize different quote types to ASCII equivalents.

#### Scenario: Curly quote conversion
- GIVEN input with smart quotes ("artist 'name'" or "song "title"")
- WHEN normalize_quotes(text) is called
- THEN system SHALL:
  - Convert left double quote (" U+201C) → ASCII "
  - Convert right double quote (" U+201D) → ASCII "
  - Convert left single quote (' U+2018) → ASCII '
  - Convert right single quote (' U+2019) → ASCII '
  - Return: 'artist "name"' → 'artist "name"'

#### Scenario: Apostrophe handling
- GIVEN input with Unicode apostrophe ("don't")
- WHEN normalize_quotes(text) is called
- THEN system SHALL convert Unicode apostrophe to ASCII ' → "don't"

### Requirement: Fuzzy String Matching
The system MUST support fuzzy matching with configurable thresholds.

#### Scenario: High similarity match
- GIVEN two strings that are nearly identical ("The Beatles" vs "The Beatles ")
- WHEN fuzzy_match(str1, str2, threshold=0.85) is called
- THEN system SHALL:
  - Normalize both strings
  - Calculate similarity ratio (Levenshtein or similar)
  - Return True (similarity >= threshold)

#### Scenario: Low similarity rejection
- GIVEN two strings that differ significantly ("The Beatles" vs "The Rolling Stones")
- WHEN fuzzy_match(str1, str2, threshold=0.85) is called
- THEN system SHALL:
  - Calculate similarity ratio
  - Return False (similarity < threshold)

#### Scenario: Configurable threshold
- GIVEN fuzzy match function with threshold parameter
- WHEN threshold is set to 0.95 (strict) vs 0.7 (loose)
- THEN behavior SHALL:
  - 0.95: Only near-identical strings match (conservative)
  - 0.7: Minor typos and variations match (permissive)
  - 0.85: Balanced matching (default)

### Requirement: Deduplication
The system MUST identify and flag near-duplicate strings.

#### Scenario: Exact duplicate detection
- GIVEN duplicate artist names after normalization ("Frank Sinatra", "frank sinatra")
- WHEN find_duplicates(text_list) is called
- THEN system SHALL:
  - Normalize all strings
  - Identify exact matches after normalization
  - Return groups of duplicates with original variants
  - Example: {group_0: ["Frank Sinatra", "frank sinatra"]}

#### Scenario: Near-duplicate detection
- GIVEN similar but not identical strings ("The Beatles", "Beatles, The")
- WHEN find_near_duplicates(text_list, threshold=0.85) is called
- THEN system SHALL:
  - Normalize all strings
  - Calculate pairwise similarity
  - Group strings above threshold
  - Flag for human review with confidence score

### Requirement: Safe String Operations
The system MUST ensure all strings remain valid UTF-8 throughout normalization.

#### Scenario: Invalid UTF-8 handling
- GIVEN text with invalid UTF-8 sequences
- WHEN normalize(text) is called
- THEN system SHALL:
  - Replace invalid bytes with replacement character (U+FFFD)
  - Log warning about invalid sequence
  - Continue processing without raising exception
  - Return valid UTF-8 string

#### Scenario: Encoding detection
- GIVEN text potentially in wrong encoding (e.g., Latin-1 misinterpreted as UTF-8)
- WHEN decode_and_normalize(raw_bytes) is called
- THEN system SHALL:
  - Attempt to detect encoding
  - Convert to UTF-8 safely
  - Log encoding assumption
  - Return normalized UTF-8 string

### Requirement: Performance & Caching
The system MUST handle large batches of strings efficiently.

#### Scenario: Batch normalization
- GIVEN list of 10,000 strings to normalize
- WHEN normalize_batch(string_list) is called
- THEN system SHALL:
  - Normalize in parallel or efficiently
  - Complete within acceptable timeout (< 1s for typical 10k batch)
  - Return normalized list in same order

#### Scenario: Caching of normalized forms
- GIVEN same strings normalized multiple times
- WHEN normalize() is called with caching enabled
- THEN system SHALL:
  - Cache normalized forms (default: LRU, 10k entries)
  - Return cached result on subsequent calls
  - Improve performance by 100x+ for repeated strings
