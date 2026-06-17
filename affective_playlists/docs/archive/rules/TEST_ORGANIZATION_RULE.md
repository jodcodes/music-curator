# Rule: Test Folder Organization

## Overview

All tests for the affective_playlists project must be organized in the `tests/` folder following a consistent structure and naming convention.

## Directory Structure

```
tests/
├── __init__.py                     # Makes tests a Python package
├── README.md                        # Testing guide and quick start
├── conftest.py                      # Pytest configuration (optional)
├── test_*.py                        # Test modules (one per feature)
├── fixtures/                        # Test data and mock responses
│   ├── __init__.py
│   ├── mock_data.json
│   ├── spotify_responses.json
│   ├── musicbrainz_responses.json
│   └── applescript_outputs.txt
└── integration/                     # Integration tests (optional)
    ├── __init__.py
    └── test_*.py
```

## File Naming Convention

### Test Files
- **Format**: `test_<feature>.py`
- **Examples**:
  - `test_metadata_enrichment.py`
  - `test_playlist_organization.py`
  - `test_temperament_analyzer.py`
  - `test_apple_music_interface.py`

### Test Classes
- **Format**: `Test<Feature>`
- **Examples**:
  - `TestMetadataEnrichment`
  - `TestPlaylistOrganization`
  - `TestTrackIdentifier` (for data structures)

### Test Methods
- **Format**: `test_<scenario>` or `test_<feature>_<scenario>`
- **Examples**:
  - `test_basic_track_identifier`
  - `test_bpm_validation_valid_range`
  - `test_conflict_resolution_higher_confidence_wins`
  - `test_mock_enrichment_single_field`

## Test Organization Rules

### Rule 1: One Test File Per Feature
Each major feature or module gets its own test file:

```python
# test_metadata_enrichment.py
class TestTrackIdentifier(unittest.TestCase):
    """Tests for TrackIdentifier data structure"""
    
class TestMetadataEntry(unittest.TestCase):
    """Tests for MetadataEntry data structure"""
    
class TestConflictResolution(unittest.TestCase):
    """Tests for conflict resolution algorithm"""
```

### Rule 2: Logical Test Grouping
Group related tests into test classes:

```python
class TestDataValidation(unittest.TestCase):
    """Test BPM, Year, Genre validation"""
    
    def test_bpm_validation_valid_range(self):
        """Test BPM: 30-300"""
        
    def test_year_validation_valid_range(self):
        """Test Year: 1900-2100"""
```

### Rule 3: Descriptive Test Names
Test names must clearly indicate what is being tested:

✓ Good:
- `test_bpm_validation_valid_range`
- `test_conflict_resolution_higher_confidence_wins`
- `test_metadata_entry_creation`

✗ Bad:
- `test_bpm`
- `test_conflict`
- `test_entry`

### Rule 4: Test Documentation
Every test must have a docstring explaining what it tests:

```python
def test_bpm_median_conflict_resolution(self):
    """Test BPM conflict: use median of all sources."""
    # Implementation
    
def test_genre_weighted_vote(self):
    """Test genre conflict: use weighted vote by confidence."""
    # Implementation
```

### Rule 5: Fixtures and Mock Data
Store test fixtures in `tests/fixtures/`:

```
tests/fixtures/
├── spotify_responses.json       # Spotify API responses
├── musicbrainz_responses.json  # MusicBrainz API responses
├── applescript_outputs.txt     # AppleScript mock outputs
└── mock_playlists.json         # Sample playlist data
```

Load fixtures in tests:

```python
def setUp(self):
    """Load test fixtures"""
    with open('tests/fixtures/mock_playlists.json') as f:
        self.mock_playlists = json.load(f)
```

### Rule 6: Test Coverage By Category

Each test file should organize tests into these categories:

1. **Data Structure Tests** (if applicable)
   - Creation and initialization
   - Serialization
   - Validation

2. **Functional Tests**
   - Happy path (normal operation)
   - Error cases
   - Edge cases

3. **Integration Tests**
   - Multiple components
   - External APIs (mocked)
   - End-to-end workflows

4. **Performance Tests**
   - Speed benchmarks
   - Memory usage
   - Scalability

5. **Security Tests**
   - Input validation
   - Error message safety
   - Data privacy

### Rule 7: Test Execution Standards

```bash
# Run all tests
python3 -m unittest discover tests -v

# Run specific test file
python3 -m unittest tests.test_metadata_enrichment -v

# Run specific test class
python3 -m unittest tests.test_metadata_enrichment.TestDataValidation -v

# Run single test
python3 -m unittest tests.test_metadata_enrichment.TestDataValidation.test_bpm_validation_valid_range -v
```

### Rule 8: Test Success Criteria

Each test file should meet these criteria:

- [ ] All tests pass (100% pass rate)
- [ ] Execution time < 5 seconds total
- [ ] No external API calls (all mocked)
- [ ] Clear failure messages
- [ ] Descriptive docstrings
- [ ] Proper setUp/tearDown
- [ ] No side effects

### Rule 9: Test Fixtures Location

Store mock data in `tests/fixtures/`:

```python
# In test file
import json
import os

class TestMetadata(unittest.TestCase):
    def setUp(self):
        fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
        with open(os.path.join(fixtures_dir, 'spotify_responses.json')) as f:
            self.spotify_mocks = json.load(f)
```

### Rule 10: Integration Tests Organization

For integration tests involving multiple modules:

```
tests/integration/
├── __init__.py
├── test_metadata_enrichment_workflow.py
├── test_playlist_organization_workflow.py
└── test_full_system_integration.py
```

## Test Coverage Targets

By Feature:
- **Core data structures**: 100% coverage
- **Validation logic**: 100% coverage
- **Business logic**: 90%+ coverage
- **Error handling**: 85%+ coverage
- **API integration**: 70% coverage (mocked)

Overall Target: **70%+ code coverage**

## Writing Quality Tests

### Anti-patterns to Avoid

✗ Brittle tests (dependent on exact output):
```python
# Bad: Fails if error message changes
self.assertEqual(error_msg, "Exact error text")

# Better: Check error type
self.assertIsInstance(error, ValueError)
```

✗ Tests that test multiple things:
```python
# Bad: Tests two features at once
def test_metadata_enrichment_and_conflict_resolution(self):
    
# Better: Separate tests
def test_conflict_resolution_bpm(self):
def test_conflict_resolution_genre(self):
```

✗ Tests that require manual setup:
```python
# Bad: Requires external data
def test_playlist_enrichment(self):
    # Need to manually select playlist

# Better: Use fixtures
def test_playlist_enrichment(self):
    playlist = self.mock_playlist_data
```

### Best Practices

✓ Test one thing per test:
```python
def test_bpm_validation_valid_range(self):
    """Test only BPM validation"""
```

✓ Use descriptive assertions:
```python
self.assertGreaterEqual(match_ratio, 0.8, 
                       "Fuzzy match must be 80%+")
```

✓ Organize with setUp/tearDown:
```python
def setUp(self):
    """Initialize test fixtures"""
    self.track = TrackIdentifier("Artist", "Title")

def tearDown(self):
    """Clean up resources"""
    # Release resources
```

## Pytest Configuration (Optional)

For pytest, create `tests/conftest.py`:

```python
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

@pytest.fixture
def mock_playlist():
    """Fixture for mock playlist data"""
    return {
        "name": "Test Playlist",
        "tracks": 10
    }

@pytest.fixture
def mock_track():
    """Fixture for mock track data"""
    return {
        "title": "Test Track",
        "artist": "Test Artist"
    }
```

## Test Execution Checklist

Before committing tests:

- [ ] All tests pass (100%)
- [ ] No import errors
- [ ] No external API calls
- [ ] All mocks work correctly
- [ ] Tests are deterministic (no randomness)
- [ ] Tests are independent (can run in any order)
- [ ] Setup/teardown works correctly
- [ ] Docstrings are complete
- [ ] Test names are descriptive

## Required Test Documentation

Each test file must have:

```markdown
# Test for Feature Name

## Overview
Brief description of what is tested

## Test Coverage
- Data structures: 8 tests
- Validation: 5 tests
- Conflict resolution: 5 tests
Total: 18 tests

## Running Tests
python3 -m unittest tests.test_module -v

## Fixtures Used
- mock_playlists.json
- spotify_responses.json
```

## Test Organization Checklist

- [ ] Test files in `tests/` folder
- [ ] Named `test_*.py`
- [ ] `__init__.py` in tests folder
- [ ] Fixtures in `tests/fixtures/`
- [ ] Test classes clearly named
- [ ] Test methods descriptive
- [ ] All tests have docstrings
- [ ] README.md in tests folder
- [ ] Setup/teardown properly used
- [ ] No external API calls
- [ ] 100% test pass rate
- [ ] Clear failure messages

## Test Files Status

Current test files in `tests/`:
- `test_metadata_enrichment.py` - 31 tests ✓
- `test_cover_art.py` - 26 tests ✓
- `test_integration.py` - Integration tests
- `test_e2e.py` - End-to-end tests
- `test_metadata_enrichment_interactive.py` - Interactive tests
- `test_temperament_analyzer_quick.py` - Quick tests

**Total**: 57+ unit tests passing

---

**Last Updated**: January 3, 2026  
**Status**: Required for all tests
