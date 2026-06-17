# CLI/TUI Interface Specifications

## Context & Implementation Guide

CLI Interface provides an interactive command-line user experience for users to navigate between affective_playlists features (temperament analysis, metadata enrichment, playlist organization). The system features colored output, progress indicators, interactive menus, and input validation.

### Core Features

- **Interactive menus**: Multi-level command selection with numbered options
- **Colored terminal output**: Color-coded results, warnings, errors for visual clarity
- **Progress tracking**: Progress bars for long-running operations
- **Input validation**: Safe user input handling with retry logic
- **Keyboard navigation**: Support for arrow keys and enter/quit shortcuts
- **Confirmation workflows**: Explicit user confirmation before destructive operations
- **Error reporting**: User-friendly error messages with remediation guidance
- **Help text**: Built-in help for each command and option
- **Cross-platform compatibility**: Works on macOS, Linux, and Windows terminals

### Implementation Files

- `src/cli_ui.py` - Core CLI interface, menu rendering, input handling
- `src/config.py` - Configuration loading and validation
- `main.py` - Application entrypoint and orchestration
- `tests/test_cli_ui.py` - CLI interaction tests

### Configuration

- Environment variables:
  - `AFFECTIVE_INTERACTIVE_MODE` - Enable interactive menus (default: true)
  - `AFFECTIVE_COLOR_ENABLED` - Enable color output (default: true)
  - `AFFECTIVE_PROGRESS_ENABLED` - Show progress bars (default: true)
- Configuration files:
  - `src/config.json` - Application settings
  - `data/config/playlist_folders.json` - CLI workflow context

### Related Domains

- **Metadata Enrichment** (`metadata`) - Enrichment operations trigger via CLI
- **Temperament Analysis** (`temperament`) - Analysis operations via CLI
- **Playlist Organization** (`playlists`) - Organization operations via CLI
- **Browser Frontend** - Alternative to CLI (users choose interface)

---

## Overview

CLI Interface SHALL provide an interactive, user-friendly command-line experience for accessing all affective_playlists features with clear feedback and confirmation workflows.

### Requirement: Main Menu Navigation
The system MUST display an interactive menu at startup allowing users to select available features.

#### Scenario: Display main menu
- GIVEN user starts the application via `python main.py`
- WHEN the main menu loads
- THEN the system SHALL display:
  - Title and version information
  - Numbered list of available commands
  - Help text or instructions
  - Quit option

#### Scenario: Invalid menu selection
- GIVEN user selects invalid menu number
- WHEN input is processed
- THEN the system SHALL:
  - Display error message
  - Redisplay menu
  - Allow retry without exiting

### Requirement: Feature Selection Workflow
The system MUST guide users through feature-specific workflows with clear steps.

#### Scenario: Enrichment workflow
- GIVEN user selects "Metadata Enrichment" option
- WHEN enrichment workflow starts
- THEN the system SHALL:
  - Prompt for target library or folder
  - Show configuration summary
  - Ask for confirmation
  - Execute enrichment (with progress bar)
  - Display results summary

#### Scenario: Temperament analysis workflow
- GIVEN user selects "Temperament Analysis"
- WHEN analysis workflow starts
- THEN the system SHALL:
  - List available playlists from Music.app
  - Allow user to select target playlists
  - Show estimated time
  - Ask for confirmation
  - Execute analysis (with progress bar)
  - Display results summary

#### Scenario: Playlist organization workflow
- GIVEN user selects "Playlist Organization"
- WHEN organization workflow starts
- THEN the system SHALL:
  - Show available playlists with current genres
  - Display intended folder moves in dry-run preview
  - Ask for confirmation
  - Execute moves (with progress bar)
  - Display operation summary

### Requirement: User Input Validation
The system MUST validate all user inputs safely and reject invalid data.

#### Scenario: Numeric input validation
- GIVEN user is prompted for numeric input (menu choice, count, etc.)
- WHEN non-numeric input is entered
- THEN the system SHALL:
  - Display error message
  - Show valid input format
  - Re-prompt for input

#### Scenario: File path validation
- GIVEN user is prompted for file or folder path
- WHEN path does not exist or is not accessible
- THEN the system SHALL:
  - Display error message
  - List valid options if available
  - Allow retry

### Requirement: Colored Output & Visual Feedback
The system MUST use colors for different message types to improve clarity.

#### Scenario: Color-coded message types
- GIVEN messages of different types are displayed
- THEN colors SHALL be:
  - Green for success messages
  - Yellow for warnings
  - Red for errors
  - Blue for informational messages
  - Cyan for prompts
- When `AFFECTIVE_COLOR_ENABLED=false`, output SHALL render plain text

#### Scenario: Progress indication
- GIVEN a long-running operation starts
- WHEN `AFFECTIVE_PROGRESS_ENABLED=true`
- THEN system SHALL display:
  - Progress bar with percentage
  - Current operation description
  - Estimated time remaining (if available)
  - Stop gracefully on user Ctrl+C

### Requirement: Confirmation Workflows
The system MUST require explicit confirmation before destructive operations.

#### Scenario: Before playlist moves
- GIVEN playlist organization is about to execute
- WHEN dry-run preview is shown
- THEN user SHALL be prompted:
  - "Review the moves above. Continue? (yes/no)"
  - Only "yes" or "y" confirms; all others cancel

#### Scenario: Before metadata deletion
- GIVEN user selects to clear metadata
- WHEN operation requires confirmation
- THEN system SHALL:
  - Show warning message in red
  - List what will be deleted
  - Require explicit "yes" confirmation
  - Abort on anything other than explicit "yes"

### Requirement: Platform Constraints Handling
The system MUST detect non-macOS platform and guide users appropriately.

#### Scenario: Non-macOS platform detection
- GIVEN application runs on Windows or Linux
- WHEN user selects temperament analysis or playlist organization
- THEN system SHALL:
  - Display platform-specific message
  - Explain why feature is unavailable (requires Music.app)
  - Suggest alternatives (e.g., folder-based enrichment)
  - Return to main menu without executing

#### Scenario: macOS availability check
- GIVEN application runs on macOS
- WHEN user selects Apple Music-dependent feature
- THEN system SHALL:
  - Pre-check Music.app availability
  - If unavailable, display error with recovery steps
  - Show which features revert to folder mode

### Requirement: Error Handling & Recovery
The system MUST handle errors gracefully with user-friendly messages.

#### Scenario: API credential missing
- GIVEN operation requires external API (OpenAI, MusicBrainz, etc.)
- WHEN API key is not configured
- THEN system SHALL:
  - Display configuration error message
  - Provide setup link (e.g., https://platform.openai.com/api-keys)
  - Suggest configuration method (environment variable, config file)
  - Return to main menu without failing

#### Scenario: Network error during operation
- GIVEN operation fails due to network connectivity
- WHEN operation is interrupted
- THEN system SHALL:
  - Display error message with retry suggestion
  - Save partial progress if possible
  - Offer to retry or cancel
  - Return to main menu on final failure

### Requirement: Help & Documentation
The system MUST provide contextual help within the interface.

#### Scenario: Feature help
- GIVEN user is in the main menu
- WHEN user selects help option or presses 'h'
- THEN system SHALL display:
  - Description of each available feature
  - Time estimate for each operation
  - Prerequisites (API keys, Music.app, etc.)
  - Link to full documentation

#### Scenario: Inline help
- GIVEN user is prompted for input
- WHEN user enters '?' or 'help'
- THEN system SHALL:
  - Display format instructions
  - Show example valid inputs
  - List available options if applicable

### Requirement: Session History & Logging
The system MUST track operations and provide access to operation history.

#### Scenario: View operation history
- GIVEN user completes operations
- WHEN user selects "View History" or views logs
- THEN system SHALL display:
  - List of recent operations with timestamps
  - Operation status (success, partial, failed)
  - Results summary for each operation
  - Option to export history
