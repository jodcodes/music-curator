# Code Quality Standards - Python Development

This document establishes quality standards for all Python code in the affective_playlists project.

## Type Hints

**Requirement**: All function signatures must include type hints.

### Rules
- Use standard typing module for complex types: `List`, `Dict`, `Optional`, `Union`, `Tuple`
- Use built-in types for Python 3.9+: `list`, `dict` instead of `List`, `Dict`
- Always annotate return types
- Use `Optional[T]` for nullable values instead of `Union[T, None]`
- Use `Any` only as a last resort and document why

### Examples

**Good:**
```python
def process_playlist(name: str, tracks: list[dict]) -> dict[str, Any]:
    """Process a playlist and return metadata."""
    pass

def validate_input(value: Optional[str]) -> bool:
    """Check if input is valid."""
    pass
```

**Bad:**
```python
def process_playlist(name, tracks):  # Missing types
    pass

def validate_input(value: Union[str, None]):  # Use Optional instead
    pass
```

## Docstrings

**Requirement**: All public functions, classes, and modules must have docstrings.

### Format: Google Style

```python
def analyze_temperament(
    playlist_name: str,
    llm_client: OpenAILLMClient
) -> dict[str, str]:
    """Analyze emotional temperament of a playlist using AI.
    
    Classifies tracks in the playlist into four temperament categories:
    Woe, Frolic, Dread, and Malice using OpenAI API.
    
    Args:
        playlist_name: Name of the playlist to analyze
        llm_client: OpenAI client instance
        
    Returns:
        Dictionary mapping track IDs to temperament labels
        
    Raises:
        ValueError: If playlist not found
        TimeoutError: If API request exceeds timeout
        
    Example:
        >>> analyzer = TemperamentAnalyzer(music_client, llm_client)
        >>> results = analyzer.analyze_temperament("My Playlist", llm_client)
        >>> print(results)
        {'track_1': 'Frolic', 'track_2': 'Dread'}
    """
    pass
```

### Docstring Components
1. **Summary line**: Single sentence describing what the function does
2. **Extended description** (if needed): More detailed explanation
3. **Args**: Parameters with types and descriptions
4. **Returns**: Return value type and description
5. **Raises**: Exceptions that may be raised
6. **Examples** (for public APIs): Typical usage patterns

## Error Handling

**Requirement**: Never use bare `except:` clauses. Always handle specific exceptions.

### Pattern

```python
from logger import setup_logger

logger = setup_logger(__name__)

try:
    result = risky_operation()
except FileNotFoundError as e:
    logger.error(f"Configuration file not found: {e}")
    raise ValueError("Config file required") from e
except TimeoutError as e:
    logger.warning(f"API timeout after retry: {e}")
    # Graceful degradation if appropriate
    result = default_value
```

### Rules
- Log the exception using `logger` before re-raising
- Include context in log messages (what operation, what resource)
- Use `from e` to chain exceptions and preserve stack trace
- Avoid catching `Exception` unless absolutely necessary
- Never silently ignore errors

## Logging

**Requirement**: Use `logger` module, never use `print()` for operational messages.

### Setup
```python
from logger import setup_logger

logger = setup_logger(__name__)  # One per module
```

### Levels

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Development info | `logger.debug(f"Processing {file_count} files")` |
| INFO  | State changes, confirmations | `logger.info("Analysis complete")` |
| WARNING | Recoverable issues | `logger.warning("API rate limited, retrying...")` |
| ERROR | Failure that needs attention | `logger.error(f"Failed to parse: {e}")` |

### Rules
- Use f-strings for message formatting
- Include relevant context (IDs, counts, paths)
- Don't log sensitive data (API keys, tokens)
- Use appropriate level - don't over-log

### Examples

**Good:**
```python
logger.info(f"Processing playlist: {playlist_name}")
logger.debug(f"Found {track_count} tracks")
logger.warning(f"Skipping invalid track: {track_id}")
logger.error(f"Failed to authenticate: {error_msg}")
```

**Bad:**
```python
print("Processing...")  # Use logger instead
print(f"API key: {api_key}")  # Never log secrets
logger.debug("OK")  # Not specific enough
```

## Code Organization

### Imports

```python
"""Module docstring describing the module's purpose."""

# Standard library
import os
import sys
from pathlib import Path
from typing import Optional

# Third-party
import requests
from dotenv import load_dotenv

# Local
from logger import setup_logger
from config import load_config

logger = setup_logger(__name__)
```

### Rules
- Group imports: stdlib, third-party, local (separated by blank lines)
- Avoid `from module import *`
- Import at module level, not inside functions
- Use absolute imports: `from src.logger import setup_logger`
- Organize functions by public API first, then helpers

### Module Structure

```python
"""Module docstring."""

# Imports
from logger import setup_logger

logger = setup_logger(__name__)

# Constants
DEFAULT_TIMEOUT = 30
VALID_GENRES = {"rock", "jazz", "pop"}

# Classes (public first)
class PublicAPI:
    pass

class HelperClass:
    pass

# Functions (public first)
def public_function() -> str:
    pass

def _helper_function() -> None:
    pass
```

## Performance & Optimization

### General Rules
1. Profile before optimizing - measure actual bottlenecks
2. Prefer clarity over micro-optimizations
3. Use generators for large data: `yield` instead of building large lists
4. Cache expensive operations (API calls, file reads)
5. Use list comprehensions over `map()`/`filter()`

### Example: Efficient Data Processing

```python
def process_large_playlist(playlist: list[dict]) -> list[dict]:
    """Process items with filtering and mapping."""
    # Use list comprehension instead of map/filter
    return [
        process_track(track)
        for track in playlist
        if track.get("valid", False)
    ]

def stream_large_file(filepath: str) -> Generator[str, None, None]:
    """Stream file line by line instead of loading all at once."""
    with open(filepath) as f:
        for line in f:
            yield line.strip()
```

## Testing Standards

- All public functions should have test coverage
- Use descriptive test names: `test_validate_playlist_name_rejects_empty_string`
- Follow AAA pattern: Arrange, Act, Assert
- Use fixtures for common setup

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Variables | snake_case | `playlist_name`, `track_count` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT`, `MAX_RETRIES` |
| Classes | PascalCase | `TemperamentAnalyzer`, `PlaylistManager` |
| Functions | snake_case | `process_playlist()`, `validate_input()` |
| Private | Leading underscore | `_helper_function()`, `_internal_state` |

## Common Anti-Patterns to Avoid

### Anti-Pattern 1: Bare Exception
```python
# BAD
try:
    data = risky_operation()
except:
    data = None
```

**Fix:**
```python
# GOOD
try:
    data = risky_operation()
except TimeoutError:
    logger.error("Operation timed out")
    data = None
```

### Anti-Pattern 2: Missing Error Context
```python
# BAD
except Exception as e:
    print("Error occurred")
    raise
```

**Fix:**
```python
# GOOD
except FileNotFoundError as e:
    logger.error(f"Configuration file not found at {filepath}: {e}")
    raise ValueError(f"Missing config: {filepath}") from e
```

### Anti-Pattern 3: Silent Failures
```python
# BAD
if not authenticate():
    pass  # Silently fail
```

**Fix:**
```python
# GOOD
if not authenticate():
    logger.error("Authentication failed")
    raise RuntimeError("Cannot authenticate with API")
```

### Anti-Pattern 4: Magic Numbers
```python
# BAD
if len(playlist) > 100:
    batch_size = 10
```

**Fix:**
```python
# GOOD
MAX_PLAYLIST_SIZE = 100
BATCH_SIZE = 10

if len(playlist) > MAX_PLAYLIST_SIZE:
    process_in_batches(playlist, BATCH_SIZE)
```

### Anti-Pattern 5: Runtime sys.path Manipulation
```python
# BAD - NEVER DO THIS IN COMMITTED CODE
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from logger import setup_logger  # Fragile - depends on sys.path hack
```

**Fix:**
```python
# GOOD - Use proper package imports
from src.logger import setup_logger

# Or (in installed package context):
from logger import setup_logger  # Works after pip install -e .
```

**Why**: 
- sys.path manipulation breaks when code is run from different directories
- Makes imports brittle and hard to understand
- Hides real import dependencies
- Prevents proper package discovery
- Breaks when installed via pip

**Rule: No `sys.path.insert()` in committed source code.**

## Review Checklist

Before submitting code for review:
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] No bare `except:` clauses
- [ ] No `sys.path.insert()` calls in source code
- [ ] Uses `logger` for all operational output
- [ ] No hardcoded values (use constants)
- [ ] Imports properly organized
- [ ] Tests added or updated
- [ ] No unused imports
- [ ] No print() statements (except in CLI output)

---

**Last Updated**: January 4, 2026  
**Version**: 1.0
