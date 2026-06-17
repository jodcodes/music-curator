"""
Real-time updates via WebSocket and Server-Sent Events (SSE).

Provides real-time progress updates, job completion events, and status broadcasts.

References: openspec/specs/realtime/spec.md
"""

import json
import time
from typing import Dict, Optional, Set

from flask import request

from src.db import utc_now
from src.logger import setup_logger

logger = setup_logger(__name__)


class RealtimeManager:
    """Manages real-time connections and event broadcasting."""

    def __init__(self):
        """Initialize realtime manager."""
        # Active connections: {job_id: {clients: set()}}
        self._connections: Dict[str, Set[str]] = {}
        # Client subscriptions: {client_id: {job_ids: set()}}
        self._subscriptions: Dict[str, Set[str]] = {}
        # Heartbeat tracking
        self._last_heartbeat: Dict[str, float] = {}
        # Event history for late-joining clients (limited)
        self._event_history: Dict[str, list] = {}
        self._max_history = 10  # Keep last 10 events per job

    def subscribe(self, client_id: str, job_id: str) -> None:
        """Subscribe client to job updates.

        Args:
            client_id: Unique client identifier (session ID, WebSocket ID, etc.)
            job_id: Job to monitor
        """
        if job_id not in self._connections:
            self._connections[job_id] = set()
            self._event_history[job_id] = []

        self._connections[job_id].add(client_id)

        if client_id not in self._subscriptions:
            self._subscriptions[client_id] = set()

        self._subscriptions[client_id].add(job_id)
        logger.debug(f"Client {client_id} subscribed to job {job_id}")

    def unsubscribe(self, client_id: str, job_id: Optional[str] = None) -> None:
        """Unsubscribe client from job updates.

        Args:
            client_id: Client identifier
            job_id: Job to stop monitoring (all jobs if None)
        """
        if job_id is None:
            # Unsubscribe from all
            if client_id in self._subscriptions:
                for jid in list(self._subscriptions[client_id]):
                    self.unsubscribe(client_id, jid)
            return

        if job_id in self._connections:
            self._connections[job_id].discard(client_id)

        if client_id in self._subscriptions:
            self._subscriptions[client_id].discard(job_id)

        logger.debug(f"Client {client_id} unsubscribed from job {job_id}")

    def broadcast_progress(
        self,
        job_id: str,
        progress: int,
        current_track: int,
        total_tracks: int,
        current_operation: str = "",
        elapsed_seconds: int = 0,
        eta_seconds: Optional[int] = None,
    ) -> None:
        """Broadcast progress update to all clients monitoring job.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            current_track: Current track being processed
            total_tracks: Total tracks
            current_operation: Description of current operation
            elapsed_seconds: Elapsed time
            eta_seconds: Estimated remaining time
        """
        event = {
            "event": "job:progress",
            "job_id": job_id,
            "progress": progress,
            "current_track": current_track,
            "total_tracks": total_tracks,
            "current_operation": current_operation,
            "elapsed_seconds": elapsed_seconds,
            "eta_seconds": eta_seconds,
            "timestamp": utc_now().isoformat(),
        }

        self._broadcast(job_id, event)

    def broadcast_completion(
        self,
        job_id: str,
        duration_seconds: int,
        result_summary: Optional[Dict] = None,
    ) -> None:
        """Broadcast job completion event.

        Args:
            job_id: Job identifier
            duration_seconds: Total execution time
            result_summary: Summary of results
        """
        event = {
            "event": "job:completed",
            "job_id": job_id,
            "status": "completed",
            "duration_seconds": duration_seconds,
            "result_summary": result_summary or {},
            "timestamp": utc_now().isoformat(),
        }

        self._broadcast(job_id, event)

    def broadcast_failure(
        self,
        job_id: str,
        error_message: str,
        error_code: str,
        duration_seconds: int = 0,
    ) -> None:
        """Broadcast job failure event.

        Args:
            job_id: Job identifier
            error_message: Error description
            error_code: Error code
            duration_seconds: How long job ran before failing
        """
        event = {
            "event": "job:failed",
            "job_id": job_id,
            "status": "failed",
            "error_message": error_message,
            "error_code": error_code,
            "duration_seconds": duration_seconds,
            "timestamp": utc_now().isoformat(),
        }

        self._broadcast(job_id, event)

    def broadcast_cancellation(
        self,
        job_id: str,
        progress: int = 0,
    ) -> None:
        """Broadcast job cancellation event.

        Args:
            job_id: Job identifier
            progress: Progress when cancelled
        """
        event = {
            "event": "job:cancelled",
            "job_id": job_id,
            "status": "cancelled",
            "progress": progress,
            "timestamp": utc_now().isoformat(),
        }

        self._broadcast(job_id, event)

    def send_heartbeat(self, client_id: str) -> None:
        """Send heartbeat/ping to client.

        Args:
            client_id: Client to ping
        """
        event = {
            "event": "heartbeat",
            "timestamp": utc_now().isoformat(),
        }
        # Note: In real implementation with SocketIO, this would send
        # Logger for now
        self._last_heartbeat[client_id] = time.time()

    def get_job_subscribers(self, job_id: str) -> Set[str]:
        """Get list of clients monitoring a job.

        Args:
            job_id: Job identifier

        Returns:
            Set of client IDs
        """
        return self._connections.get(job_id, set()).copy()

    def get_client_subscriptions(self, client_id: str) -> Set[str]:
        """Get jobs a client is monitoring.

        Args:
            client_id: Client identifier

        Returns:
            Set of job IDs
        """
        return self._subscriptions.get(client_id, set()).copy()

    def _broadcast(self, job_id: str, event: Dict) -> None:
        """Internal: broadcast event to all subscribers.

        Args:
            job_id: Job identifier
            event: Event dictionary
        """
        if job_id not in self._connections:
            return

        clients = self._connections[job_id]
        logger.debug(f"Broadcasting {event['event']} to {len(clients)} clients: {job_id}")

        # Store in history
        if job_id in self._event_history:
            self._event_history[job_id].append(event)
            # Keep only recent events
            if len(self._event_history[job_id]) > self._max_history:
                self._event_history[job_id] = self._event_history[job_id][-self._max_history :]

        # In real implementation with SocketIO:
        # socketio.emit('job:progress', event, room=job_id, skip_sid=None)
        # For now, just log for demonstration

    def get_event_history(self, job_id: str, limit: int = 10) -> list:
        """Get recent events for a job (for late-joining clients).

        Args:
            job_id: Job identifier
            limit: Max events to return

        Returns:
            List of events
        """
        events = self._event_history.get(job_id, [])
        return events[-limit:] if limit else events

    def cleanup_old_connections(self, timeout_seconds: int = 3600) -> int:
        """Remove inactive connections to prevent memory leak.

        Args:
            timeout_seconds: Consider inactive if not heard from for N seconds

        Returns:
            Number of connections cleaned up
        """
        now = time.time()
        inactive_clients = [
            cid
            for cid, last_time in self._last_heartbeat.items()
            if now - last_time > timeout_seconds
        ]

        for cid in inactive_clients:
            self.unsubscribe(cid)
            if cid in self._last_heartbeat:
                del self._last_heartbeat[cid]

        logger.debug(f"Cleaned up {len(inactive_clients)} inactive connections")
        return len(inactive_clients)


# Global instance
_realtime_manager = None


def get_realtime_manager() -> RealtimeManager:
    """Get realtime manager singleton."""
    global _realtime_manager
    if _realtime_manager is None:
        _realtime_manager = RealtimeManager()
    return _realtime_manager


def simulate_sse_stream(job_id: str):
    """Simulate Server-Sent Events stream for a job.

    This is a generator for Flask's streaming response.
    Real implementation would use actual SSE format.

    Args:
        job_id: Job to stream events for
    """
    manager = get_realtime_manager()
    client_id = f"sse-{job_id}-{time.time()}"

    try:
        manager.subscribe(client_id, job_id)

        # Send initial reply
        yield f"data: {json.dumps({'status': 'connected'})}\n\n"

        # Get event history
        for event in manager.get_event_history(job_id):
            yield f"data: {json.dumps(event)}\n\n"

        # In real implementation, would continuously stream new events
        # For now, end stream
        yield "data: {}\n\n"

    finally:
        manager.unsubscribe(client_id, job_id)
