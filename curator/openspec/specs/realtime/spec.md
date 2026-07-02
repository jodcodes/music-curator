# Real-Time Updates (WebSocket) Specifications

## Context & Implementation Guide

Real-Time Updates provides WebSocket-based bidirectional communication for live progress updates on long-running operations. This replaces polling with push-based notifications, reducing latency and server load.

### Core Features

- **WebSocket Server**: Flask-SocketIO with fallback to long-polling
- **Real-Time Progress**: Instant updates on job status changes
- **Bi-Directional Communication**: Server can push updates without polling
- **Connection Management**: Automatic reconnection with exponential backoff
- **Message Compression**: Messages compressed for bandwidth efficiency
- **Connection Pooling**: Support for multiple concurrent client connections
- **Graceful Degradation**: Automatic fallback to HTTP polling if WebSocket unavailable
- **Event Broadcasting**: Multiple clients receive same updates
- **Heartbeat/Ping-Pong**: Keep-alive mechanism to detect stale connections

### Implementation Files

- `src/realtime.py` - WebSocket event handlers and connection management
- `src/websocket_app.py` - Flask-SocketIO initialization
- `web/static/js/realtime.js` - Frontend WebSocket client
- `tests/test_realtime.py` - WebSocket integration tests
- `requirements.txt` - Add: flask-socketio>=5.3.0, python-socketio>=5.9.0

### Configuration

- Environment variables:
  - `WEBSOCKET_ENABLED` - Enable WebSocket (default: true)
  - `WEBSOCKET_HEARTBEAT_INTERVAL` - Ping-pong interval in seconds (default: 30)
  - `WEBSOCKET_MESSAGE_COMPRESSION` - Enable compression (default: true)
  - `WEBSOCKET_CONNECT_TIMEOUT` - Client connection timeout (default: 30)
- WebSocket events:
  - `connect` - Client connects
  - `job:progress` - Job progress update
  - `job:completed` - Job finished
  - `job:failed` - Job failed
  - `job:cancelled` - Job was cancelled
  - `disconnect` - Client disconnects

### Related Domains

- **Background Jobs** - Job execution triggers WebSocket messages
- **Job Persistence** - Job state changes trigger broadcasts
- **Browser Frontend** - Listens to WebSocket events

---

## Overview

Real-Time Updates SHALL provide WebSocket-based push notifications for live job status with automatic fallback to polling.

### Requirement: WebSocket Connection
Clients MUST be able to establish WebSocket connection to server.

#### Scenario: WebSocket handshake succeeds
- GIVEN client opens WebSocket to ws://127.0.0.1:4000/socket.io/
- WHEN connection handshake occurs
- THEN server SHALL:
  - Accept connection with 101 Switching Protocols
  - Assign unique session_id to client
  - Send welcome message: `{"type": "connect", "session_id": "sid-123..."}`
  - Start heartbeat: ping every 30 seconds
- AND client SHALL be ready to receive events

#### Scenario: WebSocket unavailable, fallback to polling
- GIVEN WebSocket is disabled or unavailable
- WHEN client attempts connection
- THEN client SHALL:
  - Detect WebSocket ENOTFOUND error
  - Fall back to HTTP polling
  - Poll /api/jobs/{job_id}/status every 2 seconds
  - Log: "Using HTTP polling fallback (WebSocket unavailable)"

#### Scenario: Client reconnect after network interruption
- GIVEN WebSocket connection is open
- WHEN network is interrupted for 5 seconds
- THEN client SHALL:
  - Detect disconnect (no pings received)
  - Automatically attempt reconnection
  - Exponential backoff: 1s, 2s, 4s, 8s, 16s max
  - On reconnection: request job state refresh
  - Display "Reconnecting..." then "Connected" status

### Requirement: Real-Time Progress Events
Server MUST push progress updates via WebSocket.

#### Scenario: Enrichment task progress broadcast
- GIVEN enrichment task is running
- WHEN task updates progress in database
- THEN server SHALL broadcast to all connected clients:
  ```json
  {
    "event": "job:progress",
    "job_id": "enrichment-123...",
    "progress": 45,
    "current_track": 9,
    "total_tracks": 20,
    "current_operation": "Processing track: Song Name",
    "elapsed_seconds": 120,
    "eta_seconds": 146,
    "timestamp": "2026-03-09T15:30:00Z"
  }
  ```
- AND all frontend tabs showing this job MUST update UI instantly

#### Scenario: Multiple jobs update simultaneously
- GIVEN 2 enrichment jobs and 1 analysis job running
- WHEN multiple tasks emit progress updates
- THEN server SHALL:
  - Broadcast each event to interested clients
  - Client receives: `job:progress` event for specific job_id
  - UI updates only relevant sections
  - No blocking between different job updates

#### Scenario: Job completion event broadcast
- GIVEN enrichment task completes
- WHEN task finishes with results
- THEN server SHALL broadcast:
  ```json
  {
    "event": "job:completed",
    "job_id": "enrichment-123...",
    "status": "completed",
    "tracks_enriched": 20,
    "duration_seconds": 267,
    "results": {...},
    "timestamp": "2026-03-09T15:30:00Z"
  }
  ```
- AND frontend SHALL display completion banner with results

#### Scenario: Job failure event broadcast
- GIVEN task fails after all retries
- WHEN job reaches failed state
- THEN server SHALL broadcast:
  ```json
  {
    "event": "job:failed",
    "job_id": "enrichment-123...",
    "status": "failed",
    "error_message": "Maximum retries exceeded: API unavailable",
    "error_code": "SERVICE_UNAVAILABLE",
    "last_attempt": "2026-03-09T15:30:45Z",
    "timestamp": "2026-03-09T15:30:00Z"
  }
  ```
- AND frontend SHALL show error banner with retry button

### Requirement: Server-Sent Events (SSE) Fallback
System MUST support Server-Sent Events if WebSocket unavailable.

#### Scenario: SSE fallback for progress updates
- GIVEN WebSocket not available
- WHEN client can't connect to WebSocket
- THEN client SHALL establish SSE connection to /api/jobs/{job_id}/stream
- AND server SHALL:
  - Send progress updates via SSE (text/event-stream)
  - Keep connection open for job lifetime
  - Send heartbeat `:ping` every 30 seconds
  - Close connection when job completes

#### Scenario: SSE message format
- GIVEN SSE connection active
- WHEN task updates progress
- THEN server SHALL send:
  ```
  event: progress
  data: {"progress": 45, "current_track": 9, ...}
  
  ```
- AND client JavaScript SHALL parse and handle

### Requirement: Heartbeat & Keep-Alive
System MUST detect stale connections.

#### Scenario: Ping-pong heartbeat
- GIVEN WebSocket connection established
- WHEN 30 seconds elapse with no activity
- THEN server SHALL send PING frame
- AND client SHALL respond with PONG
- AND connection remains open

#### Scenario: Dead connection detection
- GIVEN client network suddenly dies (e.g., WiFi drop)
- WHEN client doesn't respond to 3 consecutive PINGs
- THEN server SHALL:
  - Close connection
  - Log: "Client connection died (no PONG)"
  - Release resources
- AND next client poll/reconnect SHALL get fresh state

#### Scenario: Client-side timeout
- GIVEN client hasn't received PING for 60 seconds
- WHEN timeout elapses
- THEN client SHALL:
  - Mark connection as "stale"
  - Close WebSocket
  - Log: "Connection stale, reconnecting..."
  - Attempt reconnection

### Requirement: Message Efficiency
System MUST minimize message size and frequency.

#### Scenario: Progress update batching
- GIVEN task updates progress every 1 second (internal)
- WHEN rapid progress changes
- THEN server SHALL batch updates:
  - Collect changes for 2 seconds
  - Send single update with latest state
  - Reduce message rate: 1 per 2 seconds vs 1 per second
  - Bandwidth reduction: ~50%

#### Scenario: Message compression
- GIVEN large result objects (>5KB)
- WHEN completion event is broadcast
- THEN system SHALL:
  - Compress message with gzip
  - Add header: `Content-Encoding: gzip`
  - Client transforms decompress automatically
  - Reduction: ~70% smaller messages

### Requirement: Broadcasting to Multiple Clients
Multiple frontend tabs/windows MUST stay synchronized.

#### Scenario: Two browser tabs monitoring same job
- GIVEN browser has 2 tabs open on same job
- WHEN task progress updates
- THEN server SHALL broadcast to both clients
- AND both tabs update in real-time
- AND users don't need manual refresh

#### Scenario: Different jobs on different tabs
- GIVEN tab A monitoring enrichment, tab B monitoring analysis
- WHEN both jobs update
- THEN each tab receives only relevant events
- AND each tab updates independently

---

## Related Specifications

- **Background Jobs** - Source of real-time events
- **Job Persistence** - State changes trigger broadcasts
- **Browser Frontend** - Consumes WebSocket events
