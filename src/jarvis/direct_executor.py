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
from jarvis.mistake_learner import MistakeLearner
from jarvis.utils import clean_code

logger = logging.getLogger(__name__)


class DirectExecutor:
    """
    Executes simple code generation requests directly.

    Flow:
    1. Generate code from user request
    2. Write to file
    3. Execute and stream output
    """

    def __init__(
        self, llm_client: LLMClient, mistake_learner: Optional[MistakeLearner] = None
    ) -> None:
        """
        Initialize direct executor.

        Args:
            llm_client: LLM client for code generation
            mistake_learner: Optional MistakeLearner for retrieving learned patterns
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()
        logger.info("DirectExecutor initialized with mistake learner")

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
            # Clean markdown formatting from generated code
            cleaned_code = clean_code(str(code))
            logger.debug(f"Generated code length: {len(cleaned_code)} characters")
            return str(cleaned_code)
        except Exception as e:
            logger.error(f"Failed to generate code: {e}")
            raise

    def write_execution_script(
        self,
        code: str,
        filename: Optional[str] = None,
        directory: Optional[Path] = None,
        auto_save_to_desktop: bool = True,
    ) -> Path:
        """
        Write generated code to a file.

        Args:
            code: Code content to write
            filename: Optional filename (auto-generated if not provided)
            directory: Optional directory (defaults to Desktop if auto_save_to_desktop=True)
            auto_save_to_desktop: If True and directory is None, save to Desktop

        Returns:
            Path to the written file
        """
        if directory is None:
            if auto_save_to_desktop:
                # Auto-save to Desktop without dialogs
                desktop_path = self._get_desktop_path()
                directory = desktop_path / "JarvisScripts"
                logger.info("Auto-saving to Desktop/JarvisScripts")
            else:
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

    def _get_desktop_path(self) -> Path:
        """
        Get the path to the user's Desktop directory.

        Works on Windows, macOS, and Linux.

        Returns:
            Path to Desktop directory
        """
        import os

        if sys.platform == "win32":
            # Windows
            desktop = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
        elif sys.platform == "darwin":
            # macOS
            desktop = Path.home() / "Desktop"
        else:
            # Linux and others
            desktop = Path.home() / "Desktop"

        if not desktop.exists():
            logger.warning(f"Desktop path not found: {desktop}, falling back to home directory")
            desktop = Path.home()

        return desktop

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

{user_request}"""

        # Inject relevant learned fixes
        learned_fixes = self.mistake_learner.retrieve_fixes(limit=3)
        if learned_fixes:
            prompt += "\n\n" + self.mistake_learner.format_fixes_for_prompt(learned_fixes)

        prompt += """

Requirements:
- Write complete, executable code
- Include proper error handling
- Add comments explaining the code
- Make it production-ready
- No extra text or explanations, just the code

Return only the code, no markdown formatting, no explanations."""
        return prompt
