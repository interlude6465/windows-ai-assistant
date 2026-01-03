"""
Execution monitor module for real-time code execution monitoring.

Streams subprocess output, detects failures during execution, and validates
step output against expected patterns.
"""

import logging
import queue
import re
import subprocess
import sys
import threading
import time
from typing import Generator, List, Optional, Tuple

from jarvis.execution_models import CodeStep

logger = logging.getLogger(__name__)


class ExecutionMonitor:
    """
    Monitors code execution in real-time.

    Detects failures DURING execution (not after) and validates output.
    """

    # Error keywords to detect in output
    ERROR_KEYWORDS = [
        "Error",
        "Exception",
        "Traceback",
        "Failed",
        "failed",
        "error",
        "exception",
        "traceback",
        "SyntaxError",
        "ImportError",
        "RuntimeError",
        "TypeError",
        "ValueError",
        "NameError",
        "AttributeError",
        "KeyError",
        "ConnectionError",
        "TimeoutError",
        "PermissionError",
        "FileNotFoundError",
        "ModuleNotFoundError",
    ]

    def __init__(self) -> None:
        """Initialize the execution monitor."""
        logger.info("ExecutionMonitor initialized")

    def stream_subprocess_output(
        self,
        command: List[str],
        timeout: int = 30,
        capture_stderr: bool = True,
    ) -> Generator[Tuple[str, str, bool], None, None]:
        """
        Execute subprocess and yield (output_line, source, is_error) tuples in real-time.

        Windows-compatible implementation using proper pipe handling with threading.

        Args:
            command: Command to execute (as list of strings)
            timeout: Execution timeout in seconds
            capture_stderr: Whether to capture stderr

        Yields:
            Tuples of (line, source, is_error) where:
            - line: Output line
            - source: "stdout" or "stderr"
            - is_error: Whether this line indicates an error
        """
        logger.info(f"Streaming subprocess output for: {' '.join(command)}")

        try:
            # Windows-specific subprocess creation
            # Use CREATE_NEW_PROCESS_GROUP on Windows to avoid socket issues
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,  # Line buffering
                universal_newlines=True,
                creationflags=creation_flags,
            )

            # Use threading for non-blocking reads on Windows
            stdout_queue = queue.Queue()  # type: ignore[var-annotated]
            stderr_queue = queue.Queue()  # type: ignore[var-annotated]
            error_event = threading.Event()

            def read_output(pipe, queue_obj, source):
                """Read from pipe and put lines into queue."""
                try:
                    for line in iter(pipe.readline, ""):
                        if line:
                            queue_obj.put((line.rstrip(), source))
                        if error_event.is_set():
                            break
                except Exception as e:
                    logger.error(f"Error reading {source}: {e}")
                finally:
                    queue_obj.put(None)  # Signal end of stream

            # Start reader threads
            stdout_thread = threading.Thread(
                target=read_output, args=(process.stdout, stdout_queue, "stdout"), daemon=True
            )
            stderr_thread = (
                threading.Thread(
                    target=read_output, args=(process.stderr, stderr_queue, "stderr"), daemon=True
                )
                if capture_stderr
                else None
            )

            stdout_thread.start()
            if stderr_thread:
                stderr_thread.start()

            # Yield output as it arrives
            stdout_done = False
            stderr_done = False

            start_time = time.time()
            while not (stdout_done and (stderr_done or not capture_stderr)):
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Subprocess execution timeout after {timeout}s")
                    error_event.set()
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    yield ("", "error", True)
                    return

                # Try to get output from queues (non-blocking)
                try:
                    if not stdout_done:
                        item = stdout_queue.get_nowait()
                        if item is None:
                            stdout_done = True
                        else:
                            output, source = item
                            is_error = (
                                "error" in output.lower()
                                or "exception" in output.lower()
                                or "traceback" in output.lower()
                            )
                            logger.debug(f"{source}: {output}")
                            yield (output, source, is_error)
                except queue.Empty:
                    pass

                try:
                    if capture_stderr and not stderr_done:
                        item = stderr_queue.get_nowait()
                        if item is None:
                            stderr_done = True
                        else:
                            output, source = item
                            logger.debug(f"{source}: {output}")
                            yield (output, source, True)  # stderr is always error
                except queue.Empty:
                    pass

                time.sleep(0.01)  # Small sleep to prevent busy waiting

            # Wait for process to complete
            process.wait()

            # If process exited with error code, report it
            if process.returncode != 0:
                yield (f"Process exited with code {process.returncode}", "error", True)

        except Exception as e:
            logger.error(f"Error executing subprocess: {e}", exc_info=True)
            yield (f"Execution error: {str(e)}", "error", True)

    def validate_step_output(self, output: str, step: CodeStep) -> Tuple[bool, Optional[str]]:
        """
        Validate step output against expected patterns.

        Args:
            output: Combined output from step execution
            step: CodeStep with expected_output_pattern

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug(f"Validating output for step {step.step_number}")

        # If no pattern specified, assume valid
        if not step.expected_output_pattern:
            return True, None

        try:
            pattern = re.compile(step.expected_output_pattern)
            if pattern.search(output):
                logger.debug(f"Step {step.step_number} output matches pattern")
                return True, None
            else:
                error_msg = (
                    f"Output does not match expected pattern: {step.expected_output_pattern}"
                )
                logger.warning(f"Step {step.step_number} validation failed: {error_msg}")
                return False, error_msg
        except re.error as e:
            logger.error(f"Invalid regex pattern in step {step.step_number}: {e}")
            return False, f"Invalid validation pattern: {e}"

    def parse_error_from_output(self, output: str) -> Tuple[str, str]:
        """
        Parse failure reason from combined stdout/stderr.
        Windows-compatible error parsing.

        Args:
            output: Combined output from execution

        Returns:
            Tuple of (error_type, error_details)
        """
        logger.debug("Parsing error from output")

        output_lower = output.lower()

        # Windows-specific error patterns
        if "winerror" in output_lower or "error:" in output_lower:
            # Extract WinError details
            winerror_match = re.search(r"\[WinError (\d+)\] (.*?)(?:\n|$)", output)
            if winerror_match:
                error_code = winerror_match.group(1)
                error_msg = winerror_match.group(2)
                return ("WinError", f"Error {error_code}: {error_msg}")

        # Common Python errors
        if "importerror" in output_lower:
            return ("ImportError", output.split("\n")[-2] if "\n" in output else output)
        if "syntaxerror" in output_lower:
            return ("SyntaxError", output.split("\n")[-2] if "\n" in output else output)
        if "typeerror" in output_lower:
            return ("TypeError", output.split("\n")[-2] if "\n" in output else output)
        if "attributeerror" in output_lower:
            return ("AttributeError", output.split("\n")[-2] if "\n" in output else output)
        if "permissionerror" in output_lower:
            return ("PermissionError", output.split("\n")[-2] if "\n" in output else output)
        if "timeout" in output_lower or "timed out" in output_lower:
            return ("TimeoutError", "Operation timed out")
        if "connectionerror" in output_lower or "connection" in output_lower:
            return ("ConnectionError", output.split("\n")[-2] if "\n" in output else output)

        # Generic error keywords
        if "traceback" in output_lower:
            lines = output.split("\n")
            return ("RuntimeError", lines[-2] if len(lines) > 1 else output)
        if "exception" in output_lower:
            lines = output.split("\n")
            return ("Exception", lines[-2] if len(lines) > 1 else output)
        if "failed" in output_lower:
            lines = output.split("\n")
            return ("ExecutionError", lines[-2] if len(lines) > 1 else output)

        return ("Error", output[:200])  # First 200 chars as fallback

    def _is_error_line(self, line: str) -> bool:
        """
        Check if a line indicates an error.

        Args:
            line: Output line to check

        Returns:
            True if line indicates an error
        """
        line_lower = line.lower()
        for keyword in self.ERROR_KEYWORDS:
            if keyword.lower() in line_lower:
                return True
        return False

    def execute_step(
        self, step: CodeStep, timeout: Optional[int] = None
    ) -> Generator[Tuple[str, bool, Optional[str]], None, None]:
        """
        Execute a single step with monitoring.

        Args:
            step: CodeStep to execute
            timeout: Optional timeout override

        Yields:
            Tuples of (output_line, is_error, error_message_if_any)
        """
        if timeout is None:
            timeout = step.timeout_seconds

        logger.info(f"Executing step {step.step_number}: {step.description}")

        if step.code:
            # Execute code (write to temp file and run)
            import os
            import tempfile

            # Write code to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(step.code)
                temp_file = f.name

            try:
                command = [sys.executable, temp_file]
                for line, source, is_error in self.stream_subprocess_output(
                    command, timeout=timeout
                ):
                    yield (line, is_error, None)
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

        elif step.command:
            # Execute shell command
            for line, source, is_error in self.stream_subprocess_output(
                step.command, timeout=timeout
            ):
                yield (line, is_error, None)
        else:
            error_msg = f"Step {step.step_number} has no code or command to execute"
            logger.error(error_msg)
            yield (error_msg, True, error_msg)
