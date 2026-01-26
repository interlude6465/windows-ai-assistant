"""
Execution Monitor - Tracks active sessions and listeners for metasploit operations.

Monitors:
- Active metasploit sessions
- Running listeners/handlers
- Command execution history
- Session lifecycle events
- Real-time status updates
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from spectral.metasploit_executor import ListenerInfo, SessionInfo

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """States of a metasploit session."""

    CREATING = "creating"
    ACTIVE = "active"
    IDLE = "idle"
    CLOSING = "closing"
    CLOSED = "closed"


class ListenerState(Enum):
    """States of a metasploit listener."""

    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class TrackedSession:
    """Tracked metasploit session with state and metadata."""

    session_info: SessionInfo
    state: SessionState = SessionState.CREATING
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    command_count: int = 0
    success_count: int = 0
    error_count: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class TrackedListener:
    """Tracked metasploit listener with state and metadata."""

    listener_info: ListenerInfo
    state: ListenerState = ListenerState.STARTING
    created_at: float = field(default_factory=time.time)
    connection_count: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutionEvent:
    """Event in the execution history."""

    timestamp: float
    event_type: str  # "session_created", "session_closed", "listener_started", etc.
    event_data: Dict[str, str]
    description: str


class ExecutionMonitor:
    """
    Monitors and tracks metasploit execution state.

    Features:
    - Real-time session tracking
    - Listener monitoring
    - Event history
    - State management
    - Status callbacks
    """

    def __init__(self):
        """Initialize the execution monitor."""
        self.active_sessions: Dict[str, TrackedSession] = {}
        self.active_listeners: Dict[str, TrackedListener] = {}
        self.execution_history: List[ExecutionEvent] = []
        self.status_callbacks: List[Callable[[str, Dict], None]] = []
        self.gui_callback: Optional[Callable[[str, dict], None]] = None

        # Threading
        self._monitoring = False
        self._monitor_thread = None
        self._lock = threading.RLock()

        logger.info("ExecutionMonitor initialized")

    def add_status_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """
        Add a callback for status updates.

        Args:
            callback: Function to call with status updates
        """
        with self._lock:
            self.status_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """
        Remove a status callback.

        Args:
            callback: Callback to remove
        """
        with self._lock:
            if callback in self.status_callbacks:
                self.status_callbacks.remove(callback)

    def set_gui_callback(self, callback: Optional[Callable[[str, dict], None]]) -> None:
        """
        Set the GUI callback for sandbox viewer events.

        Args:
            callback: Optional callback function that receives event_type and data
        """
        self.gui_callback = callback

    def _emit_gui_event(self, event_type: str, data: dict) -> None:
        """Emit event to GUI callback."""
        if self.gui_callback:
            try:
                self.gui_callback(event_type, data)
            except Exception as e:
                logger.debug(f"GUI callback error: {e}")

    def start_monitoring(self) -> None:
        """Start the monitoring thread."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("Execution monitoring started")

    def stop_monitoring(self) -> None:
        """Stop the monitoring thread."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

        logger.info("Execution monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                self._update_session_states()
                self._check_for_inactive_sessions()
                self._emit_status_update()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5.0)  # Wait longer on error

    def _update_session_states(self) -> None:
        """Update states of active sessions."""
        current_time = time.time()

        with self._lock:
            for session_id, tracked_session in self.active_sessions.items():
                # Update last activity
                if tracked_session.state == SessionState.ACTIVE:
                    # Check if session is still responsive (simplified check)
                    # In real implementation, would ping the session
                    if current_time - tracked_session.last_activity > 300:  # 5 minutes
                        tracked_session.state = SessionState.IDLE

    def _check_for_inactive_sessions(self) -> None:
        """Check for sessions that should be marked as closed."""
        current_time = time.time()

        with self._lock:
            sessions_to_close = []

            for session_id, tracked_session in self.active_sessions.items():
                # Close sessions that have been idle for too long
                if (
                    tracked_session.state == SessionState.IDLE
                    and current_time - tracked_session.last_activity > 1800
                ):  # 30 minutes
                    sessions_to_close.append(session_id)

            # Close the identified sessions
            for session_id in sessions_to_close:
                self._close_session(session_id, reason="timeout")

    def _emit_status_update(self) -> None:
        """Emit status update to all callbacks."""
        with self._lock:
            status_data = {
                "active_sessions": len(self.active_sessions),
                "active_listeners": len(self.active_listeners),
                "sessions": {
                    sid: {
                        "type": ts.session_info.session_type,
                        "target": ts.session_info.target_ip,
                        "state": ts.state.value,
                        "age": time.time() - ts.created_at,
                    }
                    for sid, ts in self.active_sessions.items()
                },
                "listeners": {
                    lid: {
                        "payload": tl.listener_info.payload,
                        "endpoint": f"{tl.listener_info.lhost}:{tl.listener_info.lport}",
                        "state": tl.state.value,
                        "connections": tl.connection_count,
                    }
                    for lid, tl in self.active_listeners.items()
                },
            }

        # Emit to callbacks
        for callback in self.status_callbacks:
            try:
                callback("status_update", status_data)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def track_session_created(self, session_info: SessionInfo) -> str:
        """
        Track a newly created session.

        Args:
            session_info: Information about the created session

        Returns:
            Session ID
        """
        session_id = session_info.session_id

        with self._lock:
            tracked_session = TrackedSession(session_info=session_info)
            self.active_sessions[session_id] = tracked_session

            # Add to history
            event = ExecutionEvent(
                timestamp=time.time(),
                event_type="session_created",
                event_data={
                    "session_id": session_id,
                    "session_type": session_info.session_type,
                    "target_ip": session_info.target_ip,
                },
                description=f"Session {session_id} created ({session_info.session_type})",
            )
            self.execution_history.append(event)

            # Emit callback
            self._emit_event_callback(
                "session_created",
                {"session_id": session_id, "session_info": session_info.__dict__},
            )

        logger.info(f"Tracking session {session_id} ({session_info.session_type})")
        return session_id

    def track_session_closed(self, session_id: str, reason: str = "unknown") -> bool:
        """
        Track a closed session.

        Args:
            session_id: ID of the closed session
            reason: Reason for closure

        Returns:
            True if session was tracked and closed
        """
        with self._lock:
            if session_id not in self.active_sessions:
                return False

            tracked_session = self.active_sessions[session_id]
            tracked_session.state = SessionState.CLOSED

            # Add to history
            event = ExecutionEvent(
                timestamp=time.time(),
                event_type="session_closed",
                event_data={
                    "session_id": session_id,
                    "reason": reason,
                    "lifetime": time.time() - tracked_session.created_at,
                    "command_count": tracked_session.command_count,
                },
                description=f"Session {session_id} closed ({reason})",
            )
            self.execution_history.append(event)

            # Remove from active sessions
            del self.active_sessions[session_id]

            # Emit callback
            self._emit_event_callback(
                "session_closed", {"session_id": session_id, "reason": reason}
            )

        logger.info(f"Closed tracking for session {session_id}")
        return True

    def track_listener_started(self, listener_info: ListenerInfo) -> str:
        """
        Track a newly started listener.

        Args:
            listener_info: Information about the started listener

        Returns:
            Listener ID
        """
        listener_id = listener_info.handler_id

        with self._lock:
            tracked_listener = TrackedListener(listener_info=listener_info)
            self.active_listeners[listener_id] = tracked_listener

            # Add to history
            event = ExecutionEvent(
                timestamp=time.time(),
                event_type="listener_started",
                event_data={
                    "listener_id": listener_id,
                    "payload": listener_info.payload,
                    "endpoint": f"{listener_info.lhost}:{listener_info.lport}",
                },
                description=f"Listener {listener_id} started ({listener_info.payload})",
            )
            self.execution_history.append(event)

            # Emit callback
            self._emit_event_callback(
                "listener_started",
                {"listener_id": listener_id, "listener_info": listener_info.__dict__},
            )

        logger.info(f"Tracking listener {listener_id} ({listener_info.payload})")
        return listener_id

    def track_listener_stopped(self, listener_id: str, reason: str = "unknown") -> bool:
        """
        Track a stopped listener.

        Args:
            listener_id: ID of the stopped listener
            reason: Reason for stopping

        Returns:
            True if listener was tracked and stopped
        """
        with self._lock:
            if listener_id not in self.active_listeners:
                return False

            tracked_listener = self.active_listeners[listener_id]
            tracked_listener.state = ListenerState.STOPPED

            # Add to history
            event = ExecutionEvent(
                timestamp=time.time(),
                event_type="listener_stopped",
                event_data={
                    "listener_id": listener_id,
                    "reason": reason,
                    "lifetime": time.time() - tracked_listener.created_at,
                    "connection_count": tracked_listener.connection_count,
                },
                description=f"Listener {listener_id} stopped ({reason})",
            )
            self.execution_history.append(event)

            # Remove from active listeners
            del self.active_listeners[listener_id]

            # Emit callback
            self._emit_event_callback(
                "listener_stopped", {"listener_id": listener_id, "reason": reason}
            )

        logger.info(f"Stopped tracking listener {listener_id}")
        return True

    def update_session_activity(
        self, session_id: str, command_executed: bool = True, success: bool = True
    ) -> bool:
        """
        Update session activity and statistics.

        Args:
            session_id: ID of the session
            command_executed: Whether a command was executed
            success: Whether the command was successful

        Returns:
            True if session was found and updated
        """
        with self._lock:
            if session_id not in self.active_sessions:
                return False

            tracked_session = self.active_sessions[session_id]
            tracked_session.last_activity = time.time()

            if command_executed:
                tracked_session.command_count += 1
                if success:
                    tracked_session.success_count += 1
                else:
                    tracked_session.error_count += 1

            # Update state based on activity
            if tracked_session.state == SessionState.IDLE:
                tracked_session.state = SessionState.ACTIVE

            return True

    def increment_listener_connections(self, listener_id: str) -> bool:
        """
        Increment connection count for a listener.

        Args:
            listener_id: ID of the listener

        Returns:
            True if listener was found and updated
        """
        with self._lock:
            if listener_id not in self.active_listeners:
                return False

            tracked_listener = self.active_listeners[listener_id]
            tracked_listener.connection_count += 1

            return True

    def get_active_sessions(self) -> Dict[str, TrackedSession]:
        """Get all active sessions."""
        with self._lock:
            return self.active_sessions.copy()

    def get_active_listeners(self) -> Dict[str, TrackedListener]:
        """Get all active listeners."""
        with self._lock:
            return self.active_listeners.copy()

    def get_execution_history(self, limit: int = 100) -> List[ExecutionEvent]:
        """
        Get execution history.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of execution events
        """
        with self._lock:
            return self.execution_history[-limit:]

    def get_session_summary(self) -> Dict[str, any]:
        """
        Get a summary of all tracked sessions.

        Returns:
            Summary dictionary
        """
        with self._lock:
            total_sessions = len(self.active_sessions)
            total_commands = sum(
                ts.command_count for ts in self.active_sessions.values()
            )
            total_success = sum(
                ts.success_count for ts in self.active_sessions.values()
            )
            total_errors = sum(ts.error_count for ts in self.active_sessions.values())

            return {
                "active_sessions": total_sessions,
                "total_commands": total_commands,
                "successful_commands": total_success,
                "failed_commands": total_errors,
                "success_rate": (total_success / max(total_commands, 1)) * 100,
            }

    def get_listener_summary(self) -> Dict[str, any]:
        """
        Get a summary of all tracked listeners.

        Returns:
            Summary dictionary
        """
        with self._lock:
            total_listeners = len(self.active_listeners)
            total_connections = sum(
                tl.connection_count for tl in self.active_listeners.values()
            )

            return {
                "active_listeners": total_listeners,
                "total_connections": total_connections,
            }

    def _emit_event_callback(self, event_type: str, event_data: Dict[str, str]) -> None:
        """Emit event to status callbacks."""
        for callback in self.status_callbacks:
            try:
                callback(event_type, event_data)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def cleanup_all(self) -> None:
        """Cleanup all tracked sessions and listeners."""
        with self._lock:
            # Close all active sessions
            session_ids = list(self.active_sessions.keys())
            for session_id in session_ids:
                self.track_session_closed(session_id, reason="cleanup")

            # Stop all active listeners
            listener_ids = list(self.active_listeners.keys())
            for listener_id in listener_ids:
                self.track_listener_stopped(listener_id, reason="cleanup")

            # Stop monitoring
            self.stop_monitoring()

        logger.info("Execution monitor cleanup completed")
