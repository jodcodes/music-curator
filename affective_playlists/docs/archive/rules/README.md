# Documentation & Development Rules

This folder contains organizational rules and standards for the affective_playlists project.

## Rules Overview

### 1. SETUP_RULE.md - Virtual Environment & Development Setup

**Key Rule: Always run `source activate.sh` before any development work**

Covers:
- Virtual environment activation
- Dependency installation
- PYTHONPATH configuration
- Python development standards
- Troubleshooting venv issues

**Quick Reference:**
```bash
source activate.sh  # Always do this first
python main.py      # Then run your commands
```

### 2. DOCUMENTATION_STANDARDS.md - Specification & Documentation Standards

Covers:
- How to write functional specifications
- How to write technical requirements
- Required sections for each document
- Non-functional requirements (NFRs)
- Data models and schemas
- Testing standards
- Naming conventions
- File organization for docs

**Structure:**
- Functional specs: `docs/requirements/SPEC_*.md`
- Technical requirements: `docs/requirements/TECH_REQ_*.md`
- Reports: `docs/summary/IMPLEMENTATION_REPORTS/*_REPORT.md`
- Summaries: `docs/summary/PROJECT_SUMMARIES/*_SUMMARY.md`
- Quick references: `docs/summary/QUICK_REFERENCE/*_QUICK_REFERENCE.md`

### 3. TEST_ORGANIZATION_RULE.md - Test File Organization

Covers:
- How to organize test files
- Naming conventions for tests
- Test file structure
- Test fixtures and data organization

**Structure:**
```
tests/
├── __init__.py                     # Python package marker
├── test_*.py                       # Test modules (one per feature)
├── fixtures/                       # Test data and fixtures
│   └── *.json                      # Mock data
├── conftest.py                     # Pytest configuration
└── README.md                        # Testing guide
```

### 4. MARKDOWN_FILE_ORGANIZATION.md - Documentation File Organization

Covers:
- Where to place markdown documentation
- Naming conventions for documentation files
- Folder structure for docs
- Index file requirements
- Archiving old documentation

**Structure:**
```
docs/
├── rules/                          # All organizational rules
├── requirements/                   # Functional & technical specs
├── summary/                        # Reports and summaries
└── OVERVIEW.md                     # Architecture overview
```

**Root Level (Only these allowed):**
- `README.md` - Project overview
- `QUICKSTART.md` - Quick start guide
- `SETUP_COMPLETE.md` - Setup verification

## Using These Rules

### For Development
Start with **SETUP_RULE.md** - ensure your environment is configured correctly.

### For Documentation
- Follow **DOCUMENTATION_STANDARDS.md** when creating or updating specifications
- Follow **MARKDOWN_FILE_ORGANIZATION.md** when creating new documentation files

### For Testing
Follow **TEST_ORGANIZATION_RULE.md** when creating or running tests.

### For File Organization
Follow **MARKDOWN_FILE_ORGANIZATION.md** for where to place all documentation.

### 5. CODE_QUALITY_STANDARDS.md - Python Development Standards

Covers:
- Type hints and static typing expectations
- Docstring standards (Google/NumPy format)
- Error handling patterns
- Logging best practices
- Code organization and imports
- Performance and optimization guidelines

## Quick Checklist

Before starting work:
- [ ] Run `source activate.sh`
- [ ] Verify `(venv)` appears in your shell prompt
- [ ] Verify PYTHONPATH is set: `echo $PYTHONPATH`
- [ ] Run `python main.py --version` to verify setup

Before committing code:
- [ ] Ensure all tests pass
- [ ] Follow documentation standards for any spec changes
- [ ] Update `requirements.txt` if dependencies changed
- [ ] Add/update type hints in modified functions
- [ ] Add comprehensive docstrings to new functions
- [ ] Run pylint or formatter if available
- [ ] Verify no unused imports
- [ ] Check logging uses `logger` not `print()`

---

**Last Updated**: January 4, 2026
