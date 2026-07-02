# Documentation Standards

## Organizational Rules

### Rule 1: Folder Organization Structure
```
docs/
├── rules/                          # All organizational and style rules
├── requirements/                   # All functional & technical requirements
│   ├── SPEC_*.md                  # Functional specifications
│   ├── TECH_REQ_*.md              # Technical requirements
│   └── README.md                   # Requirements index
├── summary/                        # All reports and summaries
│   ├── *_REPORT.md                # Implementation reports
│   ├── *_SUMMARY.md               # Project summaries
│   └── README.md                   # Summary index
└── OVERVIEW.md                     # Project overview
```

### Rule 2: Test Folder Organization
```
tests/
├── __init__.py                     # Python package marker
├── test_*.py                       # Test modules (one per feature)
├── fixtures/                       # Test data and fixtures
│   └── *.json                      # Mock API responses
├── conftest.py                     # Pytest configuration
└── README.md                        # Testing guide
```

**Standards**:
- All test files must be named `test_*.py`
- Each major feature gets its own test file
- Test classes organized by functionality
- Use descriptive test method names: `test_<feature>_<scenario>`

### Rule 3: Reports and Summaries Folder
```
docs/summary/
├── README.md                       # Summary index
├── IMPLEMENTATION_REPORTS/
│   ├── *_REPORT.md                # Feature implementation reports
│   ├── TEST_RESULTS_REPORT.md     # Test execution summaries
│   └── PERFORMANCE_REPORT.md      # Performance analysis
├── PROJECT_SUMMARIES/
│   ├── *_SUMMARY.md               # Phase/milestone summaries
│   ├── STATUS_SUMMARY.md          # Current project status
│   └── PROGRESS_SUMMARY.md        # Development progress
└── QUICK_REFERENCE/
    ├── TESTING_QUICK_REFERENCE.md
    ├── SETUP_QUICK_REFERENCE.md
    └── API_QUICK_REFERENCE.md
```

**Standards**:
- All reports must end with `_REPORT.md`
- All summaries must end with `_SUMMARY.md`
- All quick references must end with `_QUICK_REFERENCE.md`
- Include date created and status in header
- Include table of contents for files > 500 lines

---

## Rule: All Functional Specifications and Technical Requirements

All functional specifications and technical requirements documents must follow these standards:

### File Naming Convention
- Functional Specifications: `SPEC_*.md` (e.g., `SPEC_TEMPERAMENT_ANALYZER.md`)
- Technical Requirements: `TECH_REQ_*.md` (e.g., `TECH_REQ_METADATA_FILL.md`)

### File Location
All specifications must be stored in the `docs/requirements/` folder.

### Document Structure

Each specification file should include:

#### Core Sections (Required)
1. **Overview** - Brief description of the component
2. **Purpose** - What problem does it solve
3. **Functional Requirements** - What the component must do
4. **Technical Requirements** - How it should be implemented
5. **Dependencies** - External libraries, APIs, services
6. **Input/Output** - Data format and flow
7. **Error Handling** - Expected errors and how to handle them
8. **Configuration** - Required config files and environment variables

#### Non-Functional Requirements (Required)
9. **Performance Requirements**
   - Execution time targets
   - Throughput (items/sec, requests/sec)
   - Memory/disk usage limits
   - Scalability limits (max playlists, max tracks)

10. **Reliability & Robustness**
    - Retry strategy (max retries, backoff algorithm)
    - Timeout thresholds
    - Failure recovery mechanism
    - Partial failure handling

11. **Security & Data Privacy**
    - Data encryption requirements
    - API key/credential handling
    - User data protection
    - Audit trail requirements

#### Specification & Validation (Required)
12. **Data Models/Schemas**
    - Define all data structures
    - Field types and constraints
    - Validation rules
    - Storage format

13. **Acceptance Criteria**
    - Definition of "done"
    - Success metrics
    - Test scenarios
    - Edge cases that must work

14. **Constraints & Compatibility**
    - Minimum Python version (e.g., 3.8+, 3.10+)
    - Minimum macOS version (e.g., 10.15+)
    - Library version ranges
    - Resource requirements (disk, RAM)

#### Testing (Required)
15. **Test Strategy**
    - Unit test coverage expectations
    - Integration test scenarios
    - Mock/fixture requirements
    - Test data specifications
    - Edge case tests

#### System Behavior (Required for features with state)
16. **State Management**
    - How state is tracked and persisted
    - Recovery from interruptions
    - Concurrency model (threads, async)
    - Race condition prevention

17. **Caching Strategy** (if applicable)
    - What to cache
    - Cache TTL/invalidation rules
    - Storage location
    - Size limits

18. **Backwards Compatibility**
    - API versioning strategy
    - Data migration paths
    - Deprecation policy

### Related Source Files

Reference the relevant source files from `src/` directory:
- Example: See implementation in `src/temperament_analyzer.py`
- Example: See main entry point in `main.py`

### Version Control
- Update specifications when implementing new features
- Keep specs in sync with actual implementation
- Use git commits to track specification changes

### Review Process
- All specifications must be reviewed before implementation
- Update docs folder when code changes affect functionality

### Required File Locations
- **Functional Specifications**: `docs/requirements/SPEC_*.md`
- **Technical Requirements**: `docs/requirements/TECH_REQ_*.md`
- **Implementation Reports**: `docs/summary/IMPLEMENTATION_REPORTS/*_REPORT.md`
- **Project Summaries**: `docs/summary/PROJECT_SUMMARIES/*_SUMMARY.md`
- **Quick References**: `docs/summary/QUICK_REFERENCE/*_QUICK_REFERENCE.md`
- **Test Files**: `tests/test_*.py`
- **Test Fixtures**: `tests/fixtures/*.json`
