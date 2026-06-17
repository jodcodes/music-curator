# Browser Frontend - Quick Start Guide

## Installation

```bash
# Install Flask dependency
python -m pip install -e ".[dev]"
pip install flask>=3.0.0
```

## Running the Server

```bash
# Start web server on 127.0.0.1:4000
./venv/bin/python -m src.web_server

# Or with custom port
WEB_PORT=8000 python -m src.web_server

# With debug mode
WEB_DEBUG=true python -m src.web_server
```

Then open `http://127.0.0.1:4000` in your browser.

## Features

- **Dashboard** - Overview of playlists and recent activity
- **Playlists** - View, search, and classify playlists by genre
- **Enrich** - Metadata enrichment with progress tracking
- **Analyze** - Mood/temperament analysis with visual results
- **Organize** - Dry-run preview before moving playlists (macOS only)

## Dark/Light Theme

Click the ☀️/🌙 button in navbar to toggle theme. Preference is saved in localStorage.

## API Endpoints

See [openspec/changes/browser-frontend/spec.md](../../openspec/changes/browser-frontend/spec.md) for full API documentation.

## Environment Variables

- `WEB_HOST` - Bind address (default: 127.0.0.1)
- `WEB_PORT` - Server port (default: 4000)
- `WEB_DEBUG` - Debug mode (default: false)

## Architecture

- **Backend**: Flask REST API (`src/web_server.py`)
- **Frontend**: Single-page app (vanilla JS, no frameworks)
- **State**: Client-side localStorage + in-memory state
- **Communication**: JSON over HTTP

## Browser Support

Modern browsers with ES6+ support (Chrome, Firefox, Safari, Edge).
