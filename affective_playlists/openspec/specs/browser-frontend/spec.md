# Browser Frontend Specifications

## Context & Implementation Guide

Browser Frontend replaces the CLI TUI with a lightweight, responsive HTML5 web interface running on the loopback interface. The system communicates with the Python backend via REST API and provides real-time feedback, interactive workflows, and persistent state management. The interface prioritizes speed and clarity over complex styling while remaining visually engaging.

### Core Features

- **Web-based interface**: Single-page application served on loopback (default: http://127.0.0.1:4000)
- **REST API communication**: Clean HTTP endpoints for all backend operations
- **Dashboard view**: Overview of library statistics, recent actions, and system status
- **Playlist management**: View, classify, organize, and move playlists with visual feedback
- **Metadata enrichment**: Interactive enrichment with preview and confirmation workflows
- **Temperament analysis**: Track-level and playlist-level mood classification with results display
- **Dry-run preview**: Visual diff showing intended playlist movements before confirmation
- **Real-time progress**: WebSocket or polling for long-running operations (enrichment, analysis)
- **Dark/Light theme toggle**: User preference persistence with localStorage
- **Responsive design**: Works on desktop (primary), tablet, and mobile viewports
- **Lightweight stack**: Vanilla JavaScript (no heavy frameworks), minimal CSS, semantic HTML5

### Implementation Files

- `src/web_server.py` - Flask/FastAPI server with REST endpoint handlers
- `src/api_handlers.py` - API endpoint implementations and request routing
- `web/index.html` - Main HTML template
- `web/static/css/style.css` - Stylesheet for all pages
- `web/static/js/app.js` - Main application logic and state management
- `web/static/js/api.js` - API client wrapper for HTTP requests
- `tests/test_web_server.py` - Server integration tests
- `tests/test_api_endpoints.py` - Endpoint behavior tests

### Configuration

- Environment variables:
  - `WEB_HOST` - Server bind address (default: 127.0.0.1)
  - `WEB_PORT` - Server port (default: 4000)
  - `WEB_DEBUG` - Debug mode (default: false in production)
- Browser localStorage keys:
  - `affective_theme` - 'dark' | 'light'
  - `affective_view` - Last active view (dashboard, playlists, etc.)
  - `affective_settings` - User preferences JSON

### REST API Endpoints

Core endpoints for frontend communication:

**Playlists**
- `GET /api/playlists` - List all playlists with metadata
- `GET /api/playlists/<id>` - Playlist details and tracks
- `POST /api/playlists/<id>/classify` - Classify playlist by genre
- `POST /api/playlists/organize` - Dry-run organization
- `POST /api/playlists/move` - Execute playlist moves (requires confirmation)

**Metadata**
- `GET /api/enrichment/status` - Check enrichment queue and progress
- `POST /api/enrichment/start` - Begin metadata enrichment process
- `GET /api/enrichment/results` - Completed enrichment results
- `POST /api/enrichment/cancel` - Cancel in-progress enrichment

**Temperament Analysis**
- `POST /api/temperament/classify` - Classify tracks by mood
- `GET /api/temperament/results` - Historical classification results
- `POST /api/temperament/batch` - Classify multiple tracks

**System**
- `GET /api/health` - Server health and library status
- `GET /api/config` - Frontend configuration
- `POST /api/settings` - Save user preferences

### Deployment Constraints

- **Python backend required**: Server process must be running before accessing frontend
- **Localhost only**: No remote access in default configuration (CORS disabled)
- **Single browser instance**: State stored in localStorage (no cross-browser sync)
- **Modern browser**: Requires ES6+ JavaScript support (no IE11)
- **Port availability**: Default port 5000 must be available

### Related Domains

- **Playlists** (`playlists`) - Classification and organization logic
- **Metadata Enrichment** (`metadata`) - Track metadata operations
- **Temperament Analysis** (`temperament`) - Mood classification
- **LLM Client** (`llm_client`) - API provider abstractions

---

## Overview

Browser Frontend SHALL provide lightweight web-based interface for all affective_playlists operations with real-time feedback, clear workflows, and persistent user preferences.

### Requirement: Server Startup
The system MUST start web server on loopback with predictable port.

#### Scenario: Server starts successfully
- GIVEN Python backend is installed and dependencies available
- WHEN frontend server is started (via `python -m src.web_server` or similar)
- THEN the system SHALL bind to configured host:port (default 127.0.0.1:4000)
- AND serve index.html at root URL
- AND all static assets (CSS, JS) MUST be accessible

#### Scenario: Port already in use
- GIVEN port 5000 is occupied by another process
- WHEN server startup is attempted
- THEN the system MUST fail with clear error message
- AND suggest checking for other instances or changing WEB_PORT

#### Scenario: Missing backend dependencies
- GIVEN Flask/FastAPI is not installed
- WHEN server is started
- THEN the system MUST fail with helpful error
- AND suggest running `pip install -e ".[dev]"`

### Requirement: Dashboard View
The frontend MUST display library overview with key metrics and quick actions.

#### Scenario: Dashboard loads on startup
- GIVEN user opens browser to 127.0.0.1:4000
- WHEN page loads
- THEN dashboard SHALL show:
  - Total playlists count
  - Total tracks count
  - Recent actions (last 5 enrichments/classifications)
  - System status (backend healthy, Apple Music connected on macOS)
  - Quick action buttons: Classify, Enrich, Analyze

#### Scenario: Dashboard refreshes periodically
- GIVEN dashboard is viewed
- WHEN 30 seconds elapse
- THEN the system SHALL fetch updated stats via /api/health
- AND refresh display without full page reload
- AND persist user's current scroll position

### Requirement: Playlist Classification View
The system MUST display playlists and allow genre classification with confirmation.

#### Scenario: List playlists with metadata
- GIVEN user navigates to Playlists view
- WHEN view loads
- THEN the system SHALL fetch /api/playlists
- AND display table with columns: Name, Track Count, Genre (if classified), Status
- AND sort by name alphabetically
- AND show pagination if > 20 playlists (10 per page)

#### Scenario: Classify single playlist
- GIVEN playlist is selected
- WHEN user clicks "Classify" button
- THEN UI SHALL show loading spinner
- AND POST to /api/playlists/<id>/classify
- AND display result: Genre, Confidence %, Reasoning (if available)
- AND mark playlist as classified in table

#### Scenario: Classification error handling
- GIVEN classification API fails (backend error or timeout)
- WHEN result comes back with error status
- THEN UI SHALL display error message in red banner
- AND show "Retry" button
- AND not change playlist state in table
- AND log error to browser console (dev mode)

### Requirement: Metadata Enrichment Workflow
The system MUST provide interactive enrichment with progress feedback and result display.

#### Scenario: Start enrichment process
- GIVEN user clicks "Enrich Metadata" in dashboard or Metadata view
- WHEN enrichment begins
- THEN UI SHALL show:
  - Progress bar (%), current operation ("Enriching track X of Y...")
  - Cancel button (enabled while running)
  - Estimated time remaining (if available)
- AND poll /api/enrichment/status every 2 seconds
- AND update progress bar and current operation text

#### Scenario: Enrichment completes
- GIVEN enrichment process finishes
- WHEN final status is fetched
- THEN UI SHALL display:
  - Success summary (tracks enriched, fields added, time taken)
  - Table of enriched tracks (name, added fields, source)
  - "View Results" link to detailed report (if available)
- AND mark Metadata view as "Up to Date"

#### Scenario: Cancel enrichment
- GIVEN enrichment is running and user clicks Cancel
- WHEN cancel is clicked
- THEN POST /api/enrichment/cancel
- AND show confirmation: "Enrichment cancelled"
- AND allow user to restart or view partial results
- AND restore UI to pre-enrichment state

### Requirement: Temperament Analysis Display
The system MUST show mood-based classification results with visual indicators.

#### Scenario: Classify tracks for temperament
- GIVEN user selects playlist and clicks "Analyze Mood"
- WHEN analysis starts
- THEN show loading state with progress
- AND POST /api/temperament/batch with playlist tracks
- AND fetch results from /api/temperament/results

#### Scenario: Display temperament results
- GIVEN analysis completes
- WHEN results are fetched
- THEN display for each track:
  - Track name
  - Primary temperament (with color code: red=energetic, blue=calm, etc.)
  - Confidence % (0-100)
  - Secondary temperaments (if applicable)
- AND sort by temperament for visual grouping
- AND allow export to CSV or JSON

### Requirement: Playlist Organization with Dry-Run
The system MUST preview moves before executing and require explicit confirmation.

#### Scenario: Review organization plan
- GIVEN user navigates to Organize view
- WHEN they select playlists and click "Review Changes"
- THEN POST /api/playlists/organize with dry-run=true
- AND display table showing:
  - Playlist Name | Current Location | Proposed Location | Genre | Status
- AND highlight proposed changes in blue/highlighted row
- AND show total count: "Move 5 playlists to 3 folders"

#### Scenario: Platform constraint warning
- GIVEN user is on non-macOS system
- WHEN Organize view loads
- THEN display info banner: "Playlist organization requires macOS. Metadata enrichment available."
- AND disable Move buttons
- AND allow enrichment operations

#### Scenario: User confirms moves
- GIVEN dry-run preview is displayed
- WHEN user clicks "Confirm & Execute"
- THEN show confirmation dialog: "This will move 5 playlists. Continue?"
- AND POST /api/playlists/move with confirmed=true
- AND show progress: "Moving playlist 2 of 5..."
- AND display completion: "✓ 5 playlists moved successfully"

#### Scenario: User cancels moves
- GIVEN preview is displayed
- WHEN user clicks "Cancel"
- THEN return to Organize view with preview cleared
- AND do not make any /api/playlists/move call

### Requirement: Real-Time Progress Updates
The system MUST provide immediate feedback for long-running operations.

#### Scenario: WebSocket fallback to polling
- GIVEN browser supports WebSocket
- WHEN long operation starts
- THEN establish WebSocket connection to /ws/progress
- AND receive real-time progress updates
- ELSE polling every 2 seconds to /api/enrichment/status

#### Scenario: Progress display updates
- GIVEN operation is running
- WHEN progress update received
- THEN update UI elements WITHOUT full page reload:
  - Progress bar percentage
  - Current step description
  - Elapsed time
  - Est. completion time (if available)

### Requirement: Theme Persistence
The system MUST support dark/light mode toggle with localStorage persistence.

#### Scenario: Toggle theme
- GIVEN user clicks theme toggle button (☀️/🌙 icon)
- WHEN toggle clicked
- THEN switch all CSS variables to alternate theme
- AND save preference: localStorage.setItem('affective_theme', 'dark'|'light')
- AND show visual confirmation (button state changes)

#### Scenario: Load saved theme on return visit
- GIVEN user visits browser to 127.0.0.1:4000
- WHEN page loads
- THEN check localStorage for 'affective_theme'
- AND apply saved theme (or default to 'light' if not set)
- AND load theme CSS before rendering (prevent flash of wrong theme)

### Requirement: Error Resilience
The system MUST handle network errors and backend unavailability gracefully.

#### Scenario: Backend server offline
- GIVEN user has browser open
- WHEN backend becomes unavailable (server stops)
- AND next API call is attempted
- THEN catch connection error and display banner:
  "Backend is offline. Please start the server and refresh."
- AND disable interactive buttons
- AND show "Retry Connection" button

#### Scenario: Network timeout on API request
- GIVEN API request timeout is set to 30 seconds
- WHEN request exceeds timeout
- THEN show error message: "Request timed out. Please try again."
- AND disable affected UI section
- AND allow retry

### Requirement: Responsive Design
The system MUST work across device sizes without layout breaking.

#### Scenario: Desktop view (1200px+)
- GIVEN browser width >= 1200px
- WHEN page renders
- THEN display multi-column layout:
  - Sidebar navigation (fixed)
  - Main content area
  - Optional info panel (right side)

#### Scenario: Tablet/Mobile view (<1200px)
- GIVEN browser width < 1200px
- WHEN page renders
- THEN display single-column layout:
  - Hamburger menu for navigation
  - Full-width content
  - Stacked information panels
- AND all buttons and inputs remain touchable (48px minimum)

### Requirement: Performance Optimization
The system MUST load quickly and remain responsive.

#### Scenario: Initial page load
- GIVEN user opens 127.0.0.1:4000 in new tab
- WHEN page loads
- THEN HTML + CSS + JS bundle MUST load in < 3 seconds
- AND dashboard MUST be interactive within 5 seconds (with API calls)
- AND no render-blocking resources

#### Scenario: View switching
- GIVEN user navigates between views (Dashboard → Playlists → Analyze)
- WHEN view changes
- THEN transition MUST complete within 500ms
- AND no full page reload required
- AND spinner shown for any necessary API calls

### Requirement: Accessibility Basics
The system MUST provide necessary a11y features for keyboard and screen reader users.

#### Scenario: Keyboard navigation
- GIVEN keyboard user navigates with Tab key
- WHEN Tab is pressed
- THEN focus MUST move through interactive elements in logical order
- AND all buttons, links, and inputs reachable via keyboard
- AND Escape key closes modals and dialogs

#### Scenario: Screen reader support
- GIVEN user with screen reader opens page
- WHEN page loads
- THEN semantic HTML (buttons, labels, headings) used throughout
- AND form fields have associated labels
- AND dynamic updates announced via ARIA live regions
