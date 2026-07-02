# Installation Guide - curator

## Quick Installation

### Option 1: Editable Install (Recommended for Development)

```bash
cd /path/to/curator
pip install -e .
```

Then use from anywhere:
```bash
curator
curator
```

### Option 2: Development with Virtual Environment

```bash
# Set up virtual environment
source activate.sh

# Install in editable mode
pip install -e .

# Now you can use the command from anywhere (while venv is active)
curator
```

### Option 3: Manual Installation

```bash
# Install dependencies
source activate.sh
pip install -r requirements.txt

# Create an alias (add to ~/.zshrc or ~/.bash_profile)
alias curator="python /path/to/curator/main.py"
```

## What Gets Installed

The installation creates command-line entry points:
- `curator` - Primary command
- `curator` - Alternative (underscore version)

Both execute `/path/to/curator/main.py`

## Usage After Installation

### Interactive Menu
```bash
curator
```

### Run Specific Feature
```bash
curator temperament   # AI emotion analysis
curator enrich         # Metadata enrichment
curator organize       # Genre-based organization
```

### Verbose Mode
```bash
curator -v
curator temperament -v
```

### Show Version
```bash
curator --version
```

### Show Help
```bash
curator --help
```

## System Requirements

- **Python**: 3.10 or higher
- **macOS**: 10.13 or higher (for Apple Music integration)
- **Dependencies**: Automatically installed via pip

## Verification

After installation, verify the command works:

```bash
# Check version
curator --version

# Check help
curator --help

# Try interactive mode
curator
```

## Uninstalling

To uninstall and remove the command:

```bash
pip uninstall curator
```

Or restore the alias:
```bash
# Remove from ~/.zshrc or ~/.bash_profile, then:
source ~/.zshrc  # or ~/.bash_profile
```

## Troubleshooting

### Command not found
If `curator` is not found after installation:

1. **Check installation**:
   ```bash
   pip show curator
   ```

2. **Reinstall**:
   ```bash
   pip uninstall curator
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
