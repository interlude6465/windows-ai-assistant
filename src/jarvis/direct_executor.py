"""
Direct executor module for simple code generation and execution.

Handles DIRECT mode requests: generate code, write to file, execute immediately.
"""

import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Generator, Optional

from jarvis.llm_client import LLMClient

logger = logging.getLogger(__name__)


class DirectExecutor:
    """
    Executes simple code generation requests directly.

    Flow:
    1. Generate code from user request
    2. Write to file
    3. Execute and stream output
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize direct executor.

        Args:
            llm_client: LLM client for code generation
        """
        self.llm_client = llm_client
        logger.info("DirectExecutor initialized")

    def generate_code(self, user_request: str, language: str = "python") -> str:
        """
        Generate code from user request.

        Args:
            user_request: User's natural language request
            language: Programming language (default: python)

        Returns:
            Generated code as string
        """
        logger.info(f"Generating {language} code for: {user_request}")

        prompt = self._build_code_generation_prompt(user_request, language)

        try:
            code = self.llm_client.generate(prompt)
            logger.debug(f"Generated code length: {len(code)} characters")
            return str(code)
        except Exception as e:
            logger.error(f"Failed to generate code: {e}")
            raise

    def write_execution_script(
        self, code: str, filename: Optional[str] = None, directory: Optional[Path] = None
    ) -> Path:
        """
        Write generated code to a file.

        Args:
            code: Code content to write
            filename: Optional filename (auto-generated if not provided)
            directory: Optional directory (uses temp dir if not provided)

        Returns:
            Path to the written file
        """
        if directory is None:
            directory = Path(tempfile.gettempdir())

        if filename is None:
            # Auto-generate filename with timestamp
            import time

            timestamp = int(time.time())
            filename = f"jarvis_script_{timestamp}.py"

        file_path = directory / filename
        file_path = file_path.resolve()

        logger.info(f"Writing script to: {file_path}")

        try:
            # Create directory if it doesn't exist
            directory.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            logger.info(f"Successfully wrote script to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to write script: {e}")
            raise

    def stream_execution(self, script_path: Path, timeout: int = 30) -> Generator[str, None, None]:
        """
        Execute script and stream output in real-time.

        Windows-compatible implementation using threading for non-blocking reads.

        Args:
            script_path: Path to the script to execute
            timeout: Execution timeout in seconds

        Yields:
            Output lines as they arrive
        """
        logger.info(f"Streaming execution of {script_path}")

        try:
            # Windows-specific subprocess creation
            import queue
            import threading
            import time

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=creation_flags,
            )

            # Use threading for non-blocking reads
            stdout_queue = queue.Queue()  # type: ignore[var-annotated]
            stderr_queue = queue.Queue()  # type: ignore[var-annotated]
            error_event = threading.Event()

            def read_output(pipe, queue_obj):
                """Read from pipe and put lines into queue."""
                try:
                    for line in iter(pipe.readline, ""):
                        if line:
                            queue_obj.put(line)
                        if error_event.is_set():
                            break
                except Exception as e:
                    logger.error(f"Error reading from pipe: {e}")
                finally:
                    queue_obj.put(None)  # Signal end of stream

            # Start reader threads
            stdout_thread = threading.Thread(
                target=read_output, args=(process.stdout, stdout_queue), daemon=True
            )
            stderr_thread = threading.Thread(
                target=read_output, args=(process.stderr, stderr_queue), daemon=True
            )

            stdout_thread.start()
            stderr_thread.start()

            stdout_lines = []
            stderr_lines = []
            stdout_done = False
            stderr_done = False

            start_time = time.time()
            while not (stdout_done and stderr_done):
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Script execution timeout after {timeout}s")
                    error_event.set()
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    yield f"\n❌ Error: Execution timed out after {timeout} seconds"
                    return

                # Try to get output from stdout queue (non-blocking)
                try:
                    if not stdout_done:
                        item = stdout_queue.get_nowait()
                        if item is None:
                            stdout_done = True
                        else:
                            line = item
                            stdout_lines.append(line)
                            logger.debug(f"STDOUT: {line.rstrip()}")
                            yield line
                except queue.Empty:
                    pass

                # Try to get output from stderr queue (non-blocking)
                try:
                    if not stderr_done:
                        item = stderr_queue.get_nowait()
                        if item is None:
                            stderr_done = True
                        else:
                            line = item
                            stderr_lines.append(line)
                            logger.debug(f"STDERR: {line.rstrip()}")
                            yield line
                except queue.Empty:
                    pass

                time.sleep(0.01)  # Small sleep to prevent busy waiting

            # Wait for process to complete
            process.wait()
            exit_code = process.returncode
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                stderr_output = "".join(stderr_lines)
                logger.warning(f"Script failed with exit code {exit_code}: {stderr_output}")

        except Exception as e:
            logger.error(f"Failed to stream execution: {e}")
            yield f"\n❌ Error: {str(e)}"

    def execute_request(
        self, user_request: str, language: str = "python", timeout: int = 30
    ) -> Generator[str, None, None]:
        """
        Execute a user request end-to-end.

        Args:
            user_request: User's natural language request
            language: Programming language (default: python)
            timeout: Execution timeout in seconds

        Yields:
            Status updates and output as execution progresses
        """
        yield "📝 Generating code...\n"
        logger.info(f"Executing request: {user_request}")

        try:
            # Generate code
            code = self.generate_code(user_request, language)
            yield "   ✓ Code generated\n\n"

            # Write to file
            yield "📄 Writing to file...\n"
            script_path = self.write_execution_script(code)
            yield f"   ✓ Written to {script_path}\n\n"

            # Execute and stream output
            yield "▶️ Executing script...\n"
            yield "\n"

            for output_line in self.stream_execution(script_path, timeout):
                yield output_line

            yield "\n\n✅ Execution complete\n"

        except Exception as e:
            logger.error(f"Failed to execute request: {e}")
            yield f"\n❌ Error: {str(e)}\n"

    def _build_code_generation_prompt(self, user_request: str, language: str) -> str:
        """
        Build prompt for code generation.

        Args:
            user_request: User's natural language request
            language: Programming language

        Returns:
            Formatted prompt string
        """
        prompt = f"""Write a {language} script that does the following:

{user_request}

Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just the code

Return only the code, no markdown formatting, no explanations."""
        return prompt
