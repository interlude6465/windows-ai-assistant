"""
PowerShell system action module.

Provides PowerShell command execution through subprocess while enforcing
dry-run semantics and safety checks.
"""

import logging
import subprocess
import sys
from typing import List

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class PowerShellActions:
    """
    PowerShell system actions.

    Executes PowerShell commands through subprocess with dry-run support
    and proper error handling.
    """

    def __init__(self, dry_run: bool = False, timeout: int = 30) -> None:
        """
        Initialize PowerShell actions.

        Args:
            dry_run: If True, preview commands without executing
            timeout: Command timeout in seconds
        """
        self.dry_run = dry_run
        self.timeout = timeout
        self.powershell_cmd = self._get_powershell_command()
        logger.info("PowerShellActions initialized")

    def _get_powershell_command(self) -> List[str]:
        """
        Get the appropriate PowerShell command for the current platform.

        Returns:
            List of command parts to execute PowerShell
        """
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
            # On Windows, try powershell.exe first, then fallback to pwsh.exe
            try:
                subprocess.run(
                    ["powershell.exe", "-Command", "Get-Host"],
                    capture_output=True,
                    timeout=5,
                    check=True,
                    creationflags=creation_flags,
                    stdin=subprocess.DEVNULL,
                )
                return ["powershell.exe", "-Command", "-"]
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                try:
                    subprocess.run(
                        ["pwsh.exe", "-Command", "Get-Host"],
                        capture_output=True,
                        timeout=5,
                        check=True,
                        creationflags=creation_flags,
                        stdin=subprocess.DEVNULL,
                    )
                    return ["pwsh.exe", "-Command", "-"]
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                    FileNotFoundError,
                ):
                    return ["powershell.exe", "-Command", "-"]  # Fallback
        else:
            # On non-Windows, try pwsh (PowerShell Core)
            try:
                subprocess.run(
                    ["pwsh", "-Command", "Get-Host"], capture_output=True, timeout=5, check=True
                )
                return ["pwsh", "-Command", "-"]
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                return ["pwsh", "-Command", "-"]  # Fallback

    def execute_command(
        self, command: str, capture_output: bool = True, shell: bool = False
    ) -> ActionResult:
        """
        Execute a PowerShell command.

        Args:
            command: PowerShell command to execute
            capture_output: Whether to capture stdout/stderr
            shell: Whether to use shell execution

        Returns:
            ActionResult with command output or error
        """
        logger.info(f"Executing PowerShell command: {command[:100]}...")

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="execute_command",
                message=f"[DRY-RUN] Would execute: {command}",
                data={
                    "command": command,
                    "capture_output": capture_output,
                    "shell": shell,
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
                    f"PowerShellActions: Calling subprocess.Popen (capture_output=True) "
                    f"with creationflags={creation_flags}"
                )
                process = subprocess.Popen(
                    self.powershell_cmd + [command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE if not shell else subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
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

                if not shell:
                    try:
                        if process.stdin:
                            process.stdin.write(command)
                            process.stdin.close()
                    except Exception as e:
                        logger.error(f"Error writing to powershell stdin: {e}")

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
                            raise subprocess.TimeoutExpired(command, self.timeout)

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
                        message=f"PowerShell command executed with return code {return_code}",
                        data={
                            "command": command,
                            "return_code": return_code,
                            "stdout": stdout,
                            "stderr": stderr,
                            "success": return_code == 0,
                        },
                        error=stderr if return_code != 0 else None,
                    )
                except Exception as e:
                    error_event.set()
                    if process.poll() is None:
                        process.terminate()
                    raise e
            else:
                # For non-captured output, run without capture
                logger.info(
                    f"PowerShellActions: Calling subprocess.Popen (capture_output=False) "
                    f"with creationflags={creation_flags}"
                )
                process = subprocess.Popen(
                    self.powershell_cmd + [command],
                    stdin=subprocess.PIPE if not shell else subprocess.DEVNULL,
                    stdout=None,
                    stderr=None,
                    text=True,
                    creationflags=creation_flags,
                )

                if not shell:
                    process.communicate(input=command, timeout=self.timeout)
                else:
                    process.wait(timeout=self.timeout)

                return ActionResult(
                    success=process.returncode == 0,
                    action_type="execute_command",
                    message=f"PowerShell command executed with return code {process.returncode}",
                    data={
                        "command": command,
                        "return_code": process.returncode,
                        "capture_output": False,
                    },
                )

        except subprocess.TimeoutExpired:
            logger.error(f"PowerShell command timed out: {command}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="PowerShell command timed out",
                error=f"Command exceeded timeout of {self.timeout} seconds",
            )
        except Exception as e:
            logger.error(f"Error executing PowerShell command: {e}")
            return ActionResult(
                success=False,
                action_type="execute_command",
                message="Failed to execute PowerShell command",
                error=str(e),
            )

    def execute_script(self, script_content: str) -> ActionResult:
        """
        Execute a PowerShell script.

        Args:
            script_content: PowerShell script content to execute

        Returns:
            ActionResult with script output or error
        """
        logger.info(f"Executing PowerShell script ({len(script_content)} characters)")

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="execute_script",
                message="[DRY-RUN] Would execute PowerShell script",
                data={
                    "script_content": (
                        script_content[:500] + "..."
                        if len(script_content) > 500
                        else script_content
                    ),
                    "script_length": len(script_content),
                    "dry_run": True,
                },
            )

        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            import queue
            import threading
            import time

            logger.info(
                f"PowerShellActions: Calling subprocess.Popen (execute_script) "
                f"with creationflags={creation_flags}"
            )
            process = subprocess.Popen(
                self.powershell_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
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

            try:
                if process.stdin:
                    process.stdin.write(script_content)
                    process.stdin.close()
            except Exception as e:
                logger.error(f"Error writing to powershell stdin: {e}")

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
                        raise subprocess.TimeoutExpired("PowerShell script", self.timeout)

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
                    action_type="execute_script",
                    message=f"PowerShell script executed with return code {return_code}",
                    data={
                        "script_length": len(script_content),
                        "return_code": return_code,
                        "stdout": stdout,
                        "stderr": stderr,
                        "success": return_code == 0,
                    },
                    error=stderr if return_code != 0 else None,
                )
            except Exception as e:
                error_event.set()
                if process.poll() is None:
                    process.terminate()
                raise e

        except subprocess.TimeoutExpired:
            logger.error("PowerShell script timed out")
            return ActionResult(
                success=False,
                action_type="execute_script",
                message="PowerShell script timed out",
                error=f"Script exceeded timeout of {self.timeout} seconds",
            )
        except Exception as e:
            logger.error(f"Error executing PowerShell script: {e}")
            return ActionResult(
                success=False,
                action_type="execute_script",
                message="Failed to execute PowerShell script",
                error=str(e),
            )

    def get_system_info(self) -> ActionResult:
        """
        Get system information using PowerShell.

        Returns:
            ActionResult with system information or error
        """
        logger.info("Getting system information via PowerShell")

        command = """
        Get-ComputerInfo | Select-Object OsName, OsVersion, OsArchitecture, TotalPhysicalMemory,
        CsProcessors, CsSystemType, WindowsRegisteredOwner, WindowsRegisteredOrganization
        """

        return self.execute_command(command)

    def get_running_processes(self) -> ActionResult:
        """
        Get list of running processes using PowerShell.

        Returns:
            ActionResult with process list or error
        """
        logger.info("Getting running processes via PowerShell")

        command = """
        Get-Process | Select-Object Name, Id, CPU, WorkingSet, StartTime |
        Sort-Object CPU -Descending | Select-Object -First 50
        """

        return self.execute_command(command)

    def get_services(self, status: str = "running") -> ActionResult:
        """
        Get list of services using PowerShell.

        Args:
            status: Service status to filter (running, stopped, etc.)

        Returns:
            ActionResult with service list or error
        """
        logger.info(f"Getting {status} services via PowerShell")

        command = f"""
        Get-Service | Where-Object {{$_.Status -eq '{status}'}} |
        Select-Object Name, DisplayName, Status, StartType | Sort-Object Name
        """

        return self.execute_command(command)

    def get_installed_programs(self) -> ActionResult:
        """
        Get list of installed programs using PowerShell.

        Returns:
            ActionResult with program list or error
        """
        logger.info("Getting installed programs via PowerShell")

        command = """
        Get-WmiObject -Class Win32_Product | Select-Object Name, Version, Vendor | Sort-Object Name
        """

        return self.execute_command(command)

    def check_file_hash(self, file_path: str, algorithm: str = "SHA256") -> ActionResult:
        """
        Calculate file hash using PowerShell.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm (MD5, SHA1, SHA256, SHA384, SHA512)

        Returns:
            ActionResult with file hash or error
        """
        logger.info(f"Calculating {algorithm} hash for {file_path}")

        command = f"""
        Get-FileHash -Path "{file_path}" -Algorithm {algorithm} | Select-Object Hash, Algorithm
        """

        return self.execute_command(command)
