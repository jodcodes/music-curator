# Contributing to affective_playlists

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Getting Started

### Prerequisites
- Python 3.10+
- macOS (currently Apple Music-specific)
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/jodcodes/affective_playlists.git
   cd affective_playlists
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies with dev tools**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (required for full testing)
   ```

5. **Verify setup**
   ```bash
   pytest tests/ -v
   ```

## Development Workflow

### Before Starting
1. Check open issues and pull requests to avoid duplicate work
2. Create an issue to discuss major changes before starting work
3. Fork the repo if you're an external contributor

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or for bug fixes:
   git checkout -b fix/issue-description
   ```

2. **Follow code style**
   - Use Black for formatting: `black src/ tests/`
   - Use isort for imports: `isort src/ tests/`
   - Follow PEP 8 conventions
   - Run type checking: `mypy src/`
   - Run linting: `pylint src/`

3. **Write tests**
   - Add tests for new functionality in `tests/`
   - Ensure all tests pass: `pytest`
   - Aim for >80% code coverage on new code

4. **Commit with clear messages**
   ```bash
   git commit -m "feat: add new feature" -m "Detailed description of changes"
   ```
   Use conventional commit format:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation
   - `refactor:` - Code refactor
   - `test:` - Test additions/fixes
   - `perf:` - Performance improvements

### Submitting a Pull Request

1. **Push to your fork/branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a pull request** with:
   - Clear title describing the change
   - Description of what was changed and why
   - Reference to related issues (e.g., "Closes #123")
   - Screenshot/output if applicable (especially for UI/metadata changes)

3. **Ensure CI passes**
   - GitHub Actions will run tests, linting, and type checks
   - Address any failures before review

4. **Code review**
   - Respond to reviewer feedback promptly
   - Push new commits for changes (don't force-push)
   - Approval required before merge

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_metadata_enrichment.py

# Run with coverage report
pytest --cov=src tests/

# Run with verbose output
pytest -v

# Run specific test function
pytest tests/test_metadata_enrichment.py::test_specific_function
```

## Code Quality Tools

```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Linting
pylint src/

# All checks in one go
black src/ tests/ && isort src/ tests/ && mypy src/ && pylint src/
```

## Project Structure

- **`src/`** - Main application code
  - `main.py` - CLI entry point
  - `cli_ui.py` - User interface
  - `temperament_analyzer.py` - Emotion classification
  - `metadata_enrichment.py` - Metadata filling
  - `playlist_classifier.py` - Genre classification
  - `db.py` - Database models and initialization
  - `tasks.py` - Background job definitions

- **`tests/`** - Test suite

- **`docs/`** - Documentation and architecture guides

- **`data/`** - Configuration, caches, and logs
  - `config/` - JSON configuration files
  - `cache/` - API response caches
  - `logs/` - Application logs

- **`web/`** - Web frontend (Flask application)

## Architecture Notes

- **Async Jobs**: Uses Celery + Redis for background processing
- **Database**: SQLite for job persistence (can be configured to PostgreSQL)
- **APIs**: Integrates with multiple music metadata sources
- **CLI**: Built with interactive menu system

See `docs/architecture/README.md` for detailed architecture documentation.

## Reporting Issues

### Bug Reports
Include:
- Clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Environment (macOS version, Python version)
- Relevant logs or error messages

### Feature Requests
Include:
- Clear description of the desired feature
- Use case / motivation
- Proposed implementation (optional)
- Any alternative approaches considered

## API Key Policy

- **Never commit API keys** - use `.env` (git-ignored)
- Use `.env.example` to document required/optional keys
- Test with dummy keys when possible
- For PRs, mention which APIs were tested

## Documentation

- Update docstrings for new/modified functions
- Add comments for complex logic
- Update README.md for user-facing changes
- Update docs/ for architectural changes

## Release Process

- Releases follow semantic versioning: `vMAJOR.MINOR.PATCH`
- Version is defined in `pyproject.toml`
- Maintainers create release tags and GitHub releases

## Questions?

- Check existing issues and discussions
- Open a GitHub discussion for questions
- Review project documentation in `docs/`

## Code of Conduct

Be respectful, inclusive, and considerate. We're all here to build something great together.

---

**Thank you for contributing!** 🎵
