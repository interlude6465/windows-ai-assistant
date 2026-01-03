"""
Subprocess system action module.

Provides general subprocess command execution while enforcing
dry-run semantics and safety checks.
"""

import logging
import subprocess
import sys
from typing import Dict, List, Optional, Union

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class SubprocessActions:
    """
    Subprocess system actions.

    Executes system commands through subprocess with dry-run support
    and proper error handling.
    """

    def __init__(self, dry_run: bool = False, timeout: int = 30) -> None:
        """
        Initialize subprocess actions.

        Args:
            dry_run: If True, preview commands without executing
            timeout: Command timeout in seconds
        """
        self.dry_run = dry_run
        self.timeout = timeout
        logger.info("SubprocessActions initialized")

    def execute_command(
        self,
        command: Union[str, List[str]],
        shell: bool = True,
        capture_output: bool = True,
        working_directory: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ActionResult:
        """
        Execute a system command.

        Args:
            command: Command to execute (string or list)
            shell: Whether to use shell execution
            capture_output: Whether to capture stdout/stderr
            working_directory: Working directory for command execution
            env: Environment variables for command

        Returns:
            ActionResult with command output or error
        """
        cmd_str = command if isinstance(command, str) else " ".join(command)
        logger.info(f"Executing command: {cmd_str[:100]}...")

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="execute_command",
                message=f"[DRY-RUN] Would execute: {cmd_str}",
                data={
                    "command": command,
                    "shell": shell,
                    "capture_output": capture_output,
                    "working_directory": working_directory,
                    "env": env,
                    "dry_run": True,
                },
                execution_time_ms=0.0,
            )

        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            if capture_output:
                import queue
                import threading
                import time

                logger.info(
                    f"SubprocessActions: Calling subprocess.Popen (capture_output=True) "
                    f"with creationflags={creation_flags}"
                )
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=working_directory,
                    env=env,
                    creationflags=creation_flags,
                )

                stdout_queue: queue.Queue = queue.Queue()
                stderr_queue: queue.Queue = queue.Queue()
                error_event = threading.Event()

                def read_output(pipe, queue_obj):
                    try:
                        for line in iter(pipe.readline, ""):
                            if line:
                                queue_obj.put(line)
                            if error_event.is_set():
                                break
                    except Exception as e:
                        logger.debug(f"Pipe read error: {e}")
                    finally:
                        queue_obj.put(None)

                stdout_thread = threading.Thread(
                    target=read_output, args=(process.stdout, stdout_queue), daemon=True
                )
                stderr_thread = threading.Thread(
                    target=read_output, args=(process.stderr, stderr_queue), daemon=True
                )

                stdout_thread.start()
                stderr_thread.start()

                all_stdout = []
                all_stderr = []
                stdout_done = False
                stderr_done = False
                start_time = time.time()

                try:
                    while not (stdout_done and stderr_done):
                        if time.time() - start_time > self.timeout:
                            error_event.set()
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                            raise subprocess.TimeoutExpired(cmd_str, self.timeout)

                        try:
                            item = stdout_queue.get_nowait()
                            if item is None:
                                stdout_done = True
                            else:
                                all_stdout.append(item)
                        except queue.Empty:
                            pass

                        try:
                            item = stderr_queue.get_nowait()
                            if item is None:
                                stderr_done = True
                            else:
                                all_stderr.append(item)
                        except queue.Empty:
                            pass

                        time.sleep(0.01)

                    process.wait()
                    return_code = process.returncode
                    stdout = "".join(all_stdout).strip()
                    stderr = "".join(all_stderr).strip()

                    return ActionResult(
                        success=return_code == 0,
                        action_type="execute_command",
                        message=f"Command executed with return code {return_code}",
                        data={
                            "command": command,
                            "shell": shell,
                            "return_code": return_code,
                            "stdout": stdout,
                            "stderr": stderr,
                            "working_directory": working_directory,
                            "success": return_code == 0,
                        },
                        error=stderr if return_code != 0 else None,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )

                except Exception as e:
                    error_event.set()
                    if process.poll() is None:
                        process.terminate()
                    raise e
            else:
                # For non-captured output, run without capture
                logger.info(
                    f"SubprocessActions: Calling subprocess.Popen (capture_output=False) "
                    f"with creationflags={creation_flags}"
                )
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=None,
                    stderr=None,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    cwd=working_directory,
                    env=env,
                    creationflags=creation_flags,
                )

                process.wait(timeout=self.timeout)

                return ActionResult(
                    success=process.returncode == 0,
                    action_type="execute_command",
                    message=f"Command executed with return code {process.returncode}",
                    execution_time_ms=0.0,
                    data={
                        "command": command,
                        "shell": shell,
                        "return_code": process.returncode,
                        "capture_output": False,
                        "working_directory": working_directory,
                    },
                )

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {cmd_str}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="Command timed out",
                error=f"Command exceeded timeout of {self.timeout} seconds",
                execution_time_ms=self.timeout * 1000,
            )
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="Failed to execute command",
                error=str(e),
                execution_time_ms=0.0,
            )

    def open_application(
        self, application_path: str, arguments: Optional[str] = None
    ) -> ActionResult:
        """
        Open an application with optional arguments.

        Args:
            application_path: Path to the application executable
            arguments: Optional command line arguments

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Opening application: {application_path}")

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="open_application",
                message=f"[DRY-RUN] Would open application: {application_path}",
                data={
                    "application_path": application_path,
                    "arguments": arguments,
                    "dry_run": True,
                },
                execution_time_ms=0.0,
            )

        try:
            if sys.platform == "win32":
                # On Windows, use os.startfile for simple cases
                if not arguments:
                    import os

                    os.startfile(application_path)
                    return ActionResult(
                        success=True,
                        action_type="open_application",
                        message=f"Opened application: {application_path}",
                        data={"application_path": application_path, "arguments": arguments},
                        execution_time_ms=0.0,
                    )
                else:
                    # With arguments, use subprocess
                    command = f'"{application_path}" {arguments}'
            elif sys.platform == "darwin":
                # On macOS, use open command
                command = f'open "{application_path}"'
                if arguments:
                    command += f" --args {arguments}"
            else:
                # On Linux, just execute directly
                command = f'"{application_path}"'
                if arguments:
                    command += f" {arguments}"

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            result = subprocess.run(
                command,
                shell=True,
                timeout=self.timeout,
                creationflags=creation_flags,
                stdin=subprocess.DEVNULL,
            )

            return ActionResult(
                success=result.returncode == 0,
                action_type="open_application",
                message=f"Opened application: {application_path}",
                data={
                    "application_path": application_path,
                    "arguments": arguments,
                    "return_code": result.returncode,
                },
                execution_time_ms=0.0,
            )

        except Exception as e:
            logger.error(f"Error opening application: {e}")
            return ActionResult(
                success=False,
                action_type="open_application",
                message="Failed to open application",
                error=str(e),
                execution_time_ms=0.0,
            )

    def ping_host(self, host: str, count: int = 4) -> ActionResult:
        """
        Ping a host to check connectivity.

        Args:
            host: Host to ping
            count: Number of ping packets to send

        Returns:
            ActionResult with ping results or error
        """
        logger.info(f"Pinging host: {host}")

        if sys.platform == "win32":
            command = f"ping -n {count} {host}"
        else:
            command = f"ping -c {count} {host}"

        return self.execute_command(command, shell=True, capture_output=True)

    def get_network_interfaces(self) -> ActionResult:
        """
        Get network interface information.

        Returns:
            ActionResult with network interface data or error
        """
        logger.info("Getting network interfaces")

        if sys.platform == "win32":
            command = "ipconfig /all"
        elif sys.platform == "darwin":
            command = "ifconfig -a"
        else:
            command = "ip addr show"

        return self.execute_command(command, shell=True, capture_output=True)

    def get_disk_usage(self, path: str = ".") -> ActionResult:
        """
        Get disk usage information for a path.

        Args:
            path: Path to check disk usage for

        Returns:
            ActionResult with disk usage data or error
        """
        logger.info(f"Getting disk usage for: {path}")

        if sys.platform == "win32":
            command = f'dir "{path}" /-c'
        else:
            command = f"du -sh '{path}'"

        return self.execute_command(command, shell=True, capture_output=True)

    def get_environment_variables(self) -> ActionResult:
        """
        Get environment variables.

        Returns:
            ActionResult with environment variables or error
        """
        logger.info("Getting environment variables")

        if sys.platform == "win32":
            command = "set"
        else:
            command = "env"

        return self.execute_command(command, shell=True, capture_output=True)

    def kill_process(self, process_id: int, force: bool = False) -> ActionResult:
        """
        Kill a process by ID.

        Args:
            process_id: Process ID to kill
            force: Whether to force kill the process

        Returns:
            ActionResult indicating success or failure
        """
        logger.info(f"Killing process: {process_id}")

        if sys.platform == "win32":
            command = f"taskkill /PID {process_id}"
            if force:
                command += " /F"
        else:
            command = f"kill {process_id}"
            if force:
                command = f"kill -9 {process_id}"

        return self.execute_command(command, shell=True, capture_output=True)

    def list_processes(self) -> ActionResult:
        """
        List running processes.

        Returns:
            ActionResult with process list or error
        """
        logger.info("Listing processes")

        if sys.platform == "win32":
            command = "tasklist"
        else:
            command = "ps aux"

        return self.execute_command(command, shell=True, capture_output=True)
