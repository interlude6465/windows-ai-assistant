"""
Execution debugger module for deep debugging and logging.

Provides comprehensive logging for debugging execution issues,
particularly hangs and timeouts.
"""

import json
import logging
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionDebugger:
    """
    Provides deep debugging capabilities for code execution.

    Logs EVERY step with timestamps for diagnosing:
    - 30-second hangs
    - Subprocess issues
    - Code generation problems
    - Markdown stripping issues
    """

    def __init__(self, log_dir: Optional[Path] = None, enabled: bool = False) -> None:
        """
        Initialize execution debugger.

        Args:
            log_dir: Directory for debug logs
            enabled: Whether debugging is enabled
        """
        if log_dir is None:
            from jarvis.config import JarvisConfig

            config = JarvisConfig()
            log_dir = config.storage.logs_dir

        self.log_dir = log_dir
        self.enabled = enabled
        self.log_file = log_dir / "execution_debug.log"

        if self.enabled:
            log_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"ExecutionDebugger initialized, logging to: {self.log_file}")

    def log(self, event: str, data: Optional[dict] = None) -> None:
        """
        Log an event with timestamp.

        Args:
            event: Event name/description
            data: Optional event data
        """
        if not self.enabled:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data or {},
        }

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write debug log: {e}")

    def log_code_generation(self, code: str, request: str, log_id: str) -> None:
        """
        Log code generation details.

        Args:
            code: Generated code
            request: User request
            log_id: Log identifier
        """
        self.log(
            "code_generation_start",
            {
                "log_id": log_id,
                "request": request,
                "code_length": len(code),
                "code_preview": code[:200],
            },
        )

    def log_code_cleaning(self, before: str, after: str, log_id: str) -> None:
        """
        Log code cleaning process.

        Args:
            before: Code before cleaning
            after: Code after cleaning
            log_id: Log identifier
        """
        self.log(
            "code_cleaning",
            {
                "log_id": log_id,
                "before_length": len(before),
                "after_length": len(after),
                "before_preview": before[:200],
                "after_preview": after[:200],
                "reduction_percent": (
                    round((1 - len(after) / len(before)) * 100, 2) if before else 0
                ),
            },
        )

    def log_subprocess_start(self, command: list, cwd: str, log_id: str) -> None:
        """
        Log subprocess creation.

        Args:
            command: Command list
            cwd: Working directory
            log_id: Log identifier
        """
        self.log(
            "subprocess_start",
            {
                "log_id": log_id,
                "command": " ".join(str(c) for c in command),
                "cwd": cwd,
            },
        )

    def log_subprocess_pid(self, pid: int, log_id: str) -> None:
        """
        Log subprocess PID.

        Args:
            pid: Process ID
            log_id: Log identifier
        """
        self.log(
            "subprocess_pid",
            {
                "log_id": log_id,
                "pid": pid,
            },
        )

    def log_subprocess_output(self, output: str, log_id: str) -> None:
        """
        Log subprocess output.

        Args:
            output: Output text
            log_id: Log identifier
        """
        self.log(
            "subprocess_output",
            {
                "log_id": log_id,
                "output_length": len(output),
                "output_preview": output[:200],
            },
        )

    def log_subprocess_end(self, return_code: int, elapsed: float, log_id: str) -> None:
        """
        Log subprocess termination.

        Args:
            return_code: Return code
            elapsed: Elapsed time in seconds
            log_id: Log identifier
        """
        self.log(
            "subprocess_end",
            {
                "log_id": log_id,
                "return_code": return_code,
                "elapsed_seconds": round(elapsed, 2),
            },
        )

    def log_stdin_sent(self, input_data: str, log_id: str) -> None:
        """
        Log stdin data sent to subprocess.

        Args:
            input_data: Input data
            log_id: Log identifier
        """
        self.log(
            "stdin_sent",
            {
                "log_id": log_id,
                "input_length": len(input_data),
                "input_preview": input_data[:100],
            },
        )

    def log_test_case(
        self,
        test_num: int,
        inputs: list,
        output: str,
        elapsed: float,
        passed: bool,
        log_id: str,
    ) -> None:
        """
        Log test case execution.

        Args:
            test_num: Test case number
            inputs: Input values
            output: Program output
            elapsed: Elapsed time
            passed: Whether test passed
            log_id: Log identifier
        """
        self.log(
            "test_case",
            {
                "log_id": log_id,
                "test_num": test_num,
                "inputs": inputs,
                "output_length": len(output),
                "output_preview": output[:200],
                "elapsed_seconds": round(elapsed, 2),
                "passed": passed,
            },
        )

    def log_error(self, error: str, traceback_str: Optional[str] = None, log_id: str = "") -> None:
        """
        Log an error.

        Args:
            error: Error message
            traceback_str: Optional traceback
            log_id: Log identifier
        """
        self.log(
            "error",
            {
                "log_id": log_id,
                "error": error,
                "traceback": traceback_str,
            },
        )

    def log_warning(self, warning: str, log_id: str = "") -> None:
        """
        Log a warning.

        Args:
            warning: Warning message
            log_id: Log identifier
        """
        self.log(
            "warning",
            {
                "log_id": log_id,
                "warning": warning,
            },
        )

    def log_hang_detected(self, last_output_time: float, timeout: float, log_id: str) -> None:
        """
        Log when a hang is detected.

        Args:
            last_output_time: Time since last output
            timeout: Timeout threshold
            log_id: Log identifier
        """
        self.log(
            "hang_detected",
            {
                "log_id": log_id,
                "seconds_since_output": round(last_output_time, 2),
                "timeout_threshold": timeout,
            },
        )

    def log_retry_attempt(
        self,
        attempt: int,
        strategy: str,
        error: str,
        log_id: str,
    ) -> None:
        """
        Log a retry attempt.

        Args:
            attempt: Attempt number
            strategy: Fix strategy being used
            error: Error being fixed
            log_id: Log identifier
        """
        self.log(
            "retry_attempt",
            {
                "log_id": log_id,
                "attempt": attempt,
                "strategy": strategy,
                "error": error,
            },
        )

    def start_session(self, request: str) -> str:
        """
        Start a new debug session.

        Args:
            request: User request

        Returns:
            Session ID
        """
        session_id = f"session_{int(time.time() * 1000)}"
        self.log(
            "session_start",
            {
                "session_id": session_id,
                "request": request,
            },
        )
        return session_id

    def end_session(self, session_id: str, success: bool, summary: dict) -> None:
        """
        End a debug session.

        Args:
            session_id: Session ID
            success: Whether execution succeeded
            summary: Execution summary
        """
        self.log(
            "session_end",
            {
                "session_id": session_id,
                "success": success,
                "summary": summary,
            },
        )

    def get_session_logs(self, session_id: str) -> list[dict]:
        """
        Get all logs for a session.

        Args:
            session_id: Session ID

        Returns:
            List of log entries
        """
        if not self.log_file.exists():
            return []

        logs = []
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        # Check if this entry belongs to the session
                        data = entry.get("data", {})
                        if data.get("session_id") == session_id or data.get("log_id") == session_id:
                            logs.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to read session logs: {e}")

        return logs

    def analyze_session(self, session_id: str) -> dict:
        """
        Analyze a debug session for issues.

        Args:
            session_id: Session ID

        Returns:
            Analysis results
        """
        logs = self.get_session_logs(session_id)

        analysis = {
            "total_events": len(logs),
            "code_generation_time": 0,
            "execution_time": 0,
            "errors": [],
            "warnings": [],
            "hangs": [],
            "retries": [],
        }

        for entry in logs:
            event = entry.get("event", "")
            data = entry.get("data", {})

            if event == "error":
                analysis["errors"].append(data.get("error", "Unknown error"))
            elif event == "warning":
                analysis["warnings"].append(data.get("warning", "Unknown warning"))
            elif event == "hang_detected":
                analysis["hangs"].append(
                    {
                        "seconds": data.get("seconds_since_output"),
                        "timeout": data.get("timeout_threshold"),
                    }
                )
            elif event == "retry_attempt":
                analysis["retries"].append(
                    {
                        "attempt": data.get("attempt"),
                        "strategy": data.get("strategy"),
                    }
                )

        return analysis
