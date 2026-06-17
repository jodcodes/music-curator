# Installation Guide - affective_playlists

## Quick Installation

### Option 1: Editable Install (Recommended for Development)

```bash
cd /path/to/affective_playlists
pip install -e .
```

Then use from anywhere:
```bash
affective-playlists
affective_playlists
```

### Option 2: Development with Virtual Environment

```bash
# Set up virtual environment
source activate.sh

# Install in editable mode
pip install -e .

# Now you can use the command from anywhere (while venv is active)
affective-playlists
```

### Option 3: Manual Installation

```bash
# Install dependencies
source activate.sh
pip install -r requirements.txt

# Create an alias (add to ~/.zshrc or ~/.bash_profile)
alias affective-playlists="python /path/to/affective_playlists/main.py"
```

## What Gets Installed

The installation creates command-line entry points:
- `affective-playlists` - Primary command
- `affective_playlists` - Alternative (underscore version)

Both execute `/path/to/affective_playlists/main.py`

## Usage After Installation

### Interactive Menu
```bash
affective-playlists
```

### Run Specific Feature
```bash
affective-playlists temperament   # AI emotion analysis
affective-playlists enrich         # Metadata enrichment
affective-playlists organize       # Genre-based organization
```

### Verbose Mode
```bash
affective-playlists -v
affective-playlists temperament -v
```

### Show Version
```bash
affective-playlists --version
```

### Show Help
```bash
affective-playlists --help
```

## System Requirements

- **Python**: 3.10 or higher
- **macOS**: 10.13 or higher (for Apple Music integration)
- **Dependencies**: Automatically installed via pip

## Verification

After installation, verify the command works:

```bash
# Check version
affective-playlists --version

# Check help
affective-playlists --help

# Try interactive mode
affective-playlists
```

## Uninstalling

To uninstall and remove the command:

```bash
pip uninstall affective-playlists
```

Or restore the alias:
```bash
# Remove from ~/.zshrc or ~/.bash_profile, then:
source ~/.zshrc  # or ~/.bash_profile
```

## Troubleshooting

### Command not found
If `affective-playlists` is not found after installation:

1. **Check installation**:
   ```bash
   pip show affective-playlists
   ```

2. **Reinstall**:
   ```bash
   pip uninstall affective-playlists
   pip install -e .
   ```

3. **Check virtualenv is active**:
   ```bash
   which python  # Should show path inside venv
   ```

### Python version error
Ensure you're using Python 3.10+:
```bash
python --version
python3.10 --version  # or python3.11, python3.12
```

### ModuleNotFoundError
If you get import errors:
```bash
# Reinstall with dependencies
pip install -e .[dev]  # Includes dev tools too
```

## Development Installation

For development with linting, testing, and formatting:

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Now you have access to:
pytest          # Run tests
black           # Format code
pylint          # Lint code
mypy            # Type checking
isort           # Sort imports
```

Example:
```bash
# Format code
black src/

# Check types
mypy src/

# Run tests
pytest tests/ -v
```

---

**Last Updated**: January 4, 2026
