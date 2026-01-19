"""
Adaptive fixing engine module for in-place error correction.

Diagnoses failures, generates fixes, and retries failed steps without
re-running successful ones.
"""

import logging
import subprocess
import sys
from typing import List, Optional, Tuple, TypedDict

from spectral.execution_models import CodeStep, FailureDiagnosis
from spectral.llm_client import LLMClient
from spectral.mistake_learner import LearningPattern, MistakeLearner
from spectral.retry_parsing import format_attempt_progress
from spectral.utils import AUTONOMOUS_CODE_REQUIREMENT, clean_code

logger = logging.getLogger(__name__)


# Common package name mappings (module_name -> pip_package_name)
PACKAGE_NAME_MAPPING = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "requests": "requests",
    "beautifulsoup4": "beautifulsoup4",
    "tensorflow": "tensorflow",
    "torch": "torch",
    "keras": "keras",
    "seaborn": "seaborn",
    "plotly": "plotly",
    "flask": "flask",
    "django": "django",
    "fastapi": "fastapi",
    "sqlalchemy": "sqlalchemy",
    "pymongo": "pymongo",
    "redis": "redis",
    "celery": "celery",
    "pytest": "pytest",
    "unittest-xml-reporting": "unittest-xml-reporting",
    "pygame": "pygame",
    "tkinter": None,  # Built-in, don't try to install
    "os": None,  # Built-in, don't try to install
    "sys": None,  # Built-in, don't try to install
    "json": None,  # Built-in, don't try to install
    "re": None,  # Built-in, don't try to install
    "datetime": None,  # Built-in, don't try to install
    "pathlib": None,  # Built-in, don't try to install
    "subprocess": None,  # Built-in, don't try to install
    "threading": None,  # Built-in, don't try to install
    "multiprocessing": None,  # Built-in, don't try to install
    "queue": None,  # Built-in, don't try to install
    "logging": None,  # Built-in, don't try to install
    "tempfile": None,  # Built-in, don't try to install
    "shutil": None,  # Built-in, don't try to install
    "glob": None,  # Built-in, don't try to install
    "urllib": None,  # Built-in, don't try to install
    "http": None,  # Built-in, don't try to install
    "email": None,  # Built-in, don't try to install
    "xml": None,  # Built-in, don't try to install
    "sqlite3": None,  # Built-in, don't try to install
    "csv": None,  # Built-in, don't try to install
    "configparser": None,  # Built-in, don't try to install
    "argparse": None,  # Built-in, don't try to install
    "getpass": None,  # Built-in, don't try to install
    "platform": None,  # Built-in, don't try to install
    "uuid": None,  # Built-in, don't try to install
    "hashlib": None,  # Built-in, don't try to install
    "hmac": None,  # Built-in, don't try to install
    "secrets": None,  # Built-in, don't try to install
    "base64": None,  # Built-in, don't try to install
    "binascii": None,  # Built-in, don't try to install
    "struct": None,  # Built-in, don't try to install
    "codecs": None,  # Built-in, don't try to install
    "io": None,  # Built-in, don't try to install
    "collections": None,  # Built-in, don't try to install
    "itertools": None,  # Built-in, don't try to install
    "functools": None,  # Built-in, don't try to install
    "operator": None,  # Built-in, don't try to install
    "pickle": None,  # Built-in, don't try to install
    "copy": None,  # Built-in, don't try to install
    "pprint": None,  # Built-in, don't try to install
    "reprlib": None,  # Built-in, don't try to install
    "enum": None,  # Built-in, don't try to install
    "abc": None,  # Built-in, don't try to install
    "contextlib": None,  # Built-in, don't try to install
    "weakref": None,  # Built-in, don't try to install
    "types": None,  # Built-in, don't try to install
    "copyreg": None,  # Built-in, don't try to install
    "typing": None,  # Built-in, don't try to install
    "warnings": None,  # Built-in, don't try to install
    "dataclasses": None,  # Built-in, don't try to install
    "ast": None,  # Built-in, don't try to install
    "dis": None,  # Built-in, don't try to install
    "inspect": None,  # Built-in, don't try to install
    "traceback": None,  # Built-in, don't try to install
    "linecache": None,  # Built-in, don't try to install
    "tokenize": None,  # Built-in, don't try to install
    "keyword": None,  # Built-in, don't try to install
    "symtable": None,  # Built-in, don't try to install
    "tabnanny": None,  # Built-in, don't try to install
    "py_compile": None,  # Built-in, don't try to install
    "compileall": None,  # Built-in, don't try to install
    "filecmp": None,  # Built-in, don't try to install
    "fnmatch": None,  # Built-in, don't try to install
    "netrc": None,  # Built-in, don't try to install
    "plistlib": None,  # Built-in, don't try to install
    "mailcap": None,  # Built-in, don't try to install
    "mimetypes": None,  # Built-in, don't try to install
    "calendar": None,  # Built-in, don't try to install
    "decimal": None,  # Built-in, don't try to install
    "fractions": None,  # Built-in, don't try to install
    "random": None,  # Built-in, don't try to install
    "statistics": None,  # Built-in, don't try to install
    "bisect": None,  # Built-in, don't try to install
    "heapq": None,  # Built-in, don't try to install
    "array": None,  # Built-in, don't try to install
    "sched": None,  # Built-in, don't try to install
    "email.mime": None,  # Built-in, don't try to install
    "html": None,  # Built-in, don't try to install
    "xml.etree.ElementTree": None,  # Built-in, don't try to install
    "xml.dom": None,  # Built-in, don't try to install
    "xml.sax": None,  # Built-in, don't try to install
    "mailbox": None,  # Built-in, don't try to install
    "msilib": None,  # Built-in, don't try to install
    "audioop": None,  # Built-in, don't try to install
    "colorsys": None,  # Built-in, don't try to install
    "imghdr": None,  # Built-in, don't try to install
    "sndhdr": None,  # Built-in, don't try to install
    "string": None,  # Built-in, don't try to install
    "textwrap": None,  # Built-in, don't try to install
    "unicodedata": None,  # Built-in, don't try to install
    "locale": None,  # Built-in, don't try to install
}


class RetryHistoryEntry(TypedDict):
    count: int
    last_fix_strategy: Optional[str]


class AdaptiveFixEngine:
    """
    Diagnoses and fixes failures during code execution.

    When a step fails:
    1. Captures the exact error
    2. Diagnoses root cause
    3. Generates a fix
    4. Re-executes ONLY that step
    5. Continues to next step
    6. Stores successful fixes for future learning
    """

    def __init__(
        self, llm_client: LLMClient, mistake_learner: Optional[MistakeLearner] = None
    ) -> None:
        """
        Initialize adaptive fix engine.

        Args:
            llm_client: LLM client for diagnosis and fix generation
            mistake_learner: Mistake learner for storing and retrieving patterns
        """
        self.llm_client = llm_client
        self.mistake_learner = mistake_learner or MistakeLearner()
        self.default_max_retries: Optional[int] = None
        self.retry_history: dict[str, RetryHistoryEntry] = {}
        # Track installation attempts to prevent infinite loops
        self.install_history: dict[str, int] = {}
        logger.info("AdaptiveFixEngine initialized with unlimited retries by default")

    def install_missing_package(self, module_name: str) -> bool:
        """
        Install missing package using pip.

        Args:
            module_name: Name of the missing module

        Returns:
            True if installation succeeded, False otherwise
        """
        # Check if we've tried this package too many times
        if module_name in self.install_history and self.install_history[module_name] >= 2:
            logger.warning(f"Skipping {module_name} - already attempted 2+ times")
            return False

        # Get the pip package name
        pip_package = PACKAGE_NAME_MAPPING.get(module_name)
        if pip_package is None:
            # Check if it's a common pattern or just use the module name
            if module_name in PACKAGE_NAME_MAPPING:
                logger.info(f"Module {module_name} is built-in, no installation needed")
                return False
            else:
                # Try to install using the module name as-is
                pip_package = module_name

        # Track this installation attempt
        if module_name not in self.install_history:
            self.install_history[module_name] = 0
        self.install_history[module_name] += 1

        logger.info(f"Installing package: {pip_package} for module {module_name}")

        try:
            # Install the package
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_package],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for installations
            )

            if result.returncode == 0:
                logger.info(f"Successfully installed {pip_package}")
                # Verify the module can now be imported
                try:
                    __import__(module_name)
                    logger.info(f"Verified {module_name} can be imported after installation")
                    return True
                except ImportError:
                    logger.warning(
                        f"Module {module_name} still cannot be imported after installation"
                    )
                    return False
            else:
                logger.error(f"Failed to install {pip_package}: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Installation timeout for {pip_package}")
            return False
        except Exception as e:
            logger.error(f"Error installing {pip_package}: {e}")
            return False

    def diagnose_failure(
        self,
        step: CodeStep,
        error_type: str,
        error_details: str,
        original_output: str,
    ) -> FailureDiagnosis:
        """
        Use LLM to understand failure and suggest fix.

        Args:
            step: The failed CodeStep
            error_type: Type of error (e.g., ImportError, SyntaxError)
            error_details: Detailed error message
            original_output: Full output from failed execution

        Returns:
            FailureDiagnosis with root cause and suggested fix
        """
        logger.info(f"Diagnosing failure for step {step.step_number}: {error_type}")

        # Handle ModuleNotFoundError and ImportError with auto-installation
        if error_type in ["ModuleNotFoundError", "ImportError"]:
            module_name = self._extract_module_name_from_error(error_details)
            if module_name:
                logger.info(f"Detected missing module: {module_name}")

                # Try to install the package
                install_success = self.install_missing_package(module_name)

                if install_success:
                    logger.info(f"Successfully installed {module_name}, retrying execution")
                    return FailureDiagnosis(
                        error_type=error_type,
                        error_details=error_details,
                        root_cause=f"Missing module '{module_name}' - now installed",
                        suggested_fix="Module installed, retry original code",
                        fix_strategy="retry_after_install",
                        confidence=0.9,
                    )
                else:
                    logger.warning(f"Failed to install {module_name}")
                    return FailureDiagnosis(
                        error_type=error_type,
                        error_details=error_details,
                        root_cause=f"Missing module '{module_name}' - installation failed",
                        suggested_fix=f"Manual installation required: pip install {module_name}",
                        fix_strategy="manual",
                        confidence=0.8,
                    )

        prompt = self._build_diagnosis_prompt(step, error_type, error_details, original_output)

        try:
            response = self.llm_client.generate(prompt)
            logger.debug(f"Diagnosis response received: {len(response)} characters")

            # Parse response into FailureDiagnosis
            diagnosis = self._parse_diagnosis_response(response, error_type, error_details)
            logger.info(f"Diagnosis complete: {diagnosis.root_cause}")

            # Path error detection (Part 4)
            is_path_error = (
                "filenotfounderror" in error_details.lower()
                or "winerror 3" in error_details.lower()
                or "winerror 2" in error_details.lower()
            )

            if is_path_error:
                import getpass

                username = getpass.getuser()
                unix_patterns = ["/path/to", "/usr/bin", "/home/", "/var/"]
                has_unix_path = (
                    any(p in original_output or p in step.code for p in unix_patterns)
                    if step.code
                    else False
                )

                if has_unix_path:
                    logger.warning("Detected Unix paths in Windows environment during path error")
                    diagnosis.root_cause += " (Detected Unix-style paths on Windows)"
                    diagnosis.suggested_fix = (
                        "Replace Unix paths with Windows paths. "
                        f"Use C:\\Users\\{username}\\Desktop instead of /path/to/start."
                    )
                    diagnosis.fix_strategy = "regenerate_code"
                    diagnosis.confidence = 0.95

            # Override incorrect diagnoses for Windows socket errors
            if (
                "winerror" in error_details.lower() or "socket" in error_details.lower()
            ) and "posix" in diagnosis.root_cause.lower():
                logger.warning("Overriding incorrect POSIX diagnosis for Windows socket error")
                return FailureDiagnosis(
                    error_type=error_type,
                    error_details=error_details,
                    root_cause="Windows subprocess pipe handling issue",
                    suggested_fix="Ensure subprocess pipes are properly created and handled",
                    fix_strategy="manual",
                    confidence=0.9,
                )

            return diagnosis
        except Exception as e:
            logger.error(f"Failed to diagnose failure: {e}")
            # Return fallback diagnosis
            return FailureDiagnosis(
                error_type=error_type,
                error_details=error_details,
                root_cause=f"Unable to diagnose: {str(e)}",
                suggested_fix="Manual intervention required",
                fix_strategy="manual",
                confidence=0.3,
            )

    def _extract_module_name_from_error(self, error_details: str) -> Optional[str]:
        """
        Extract module name from ImportError or ModuleNotFoundError details.

        Args:
            error_details: Error details string

        Returns:
            Module name if found, None otherwise
        """
        import re

        # Common patterns for missing module errors
        patterns = [
            r"No module named ['\"]([^'\"]+)['\"]",
            r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
            r"ImportError: No module named ['\"]([^'\"]+)['\"]",
            r"No module named '([^']+)'",
            r"No module named \"([^\"]+)\"",
            r"Module '([^']+)' not found",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_details)
            if match:
                module_name = match.group(1)
                # Remove dotted module prefix to get the base package name
                if "." in module_name:
                    module_name = module_name.split(".")[0]
                return module_name

        return None

    def generate_fix(self, step: CodeStep, diagnosis: FailureDiagnosis, retry_count: int) -> str:
        """
        Generate fixed code based on diagnosis.

        Args:
            step: Original CodeStep that failed
            diagnosis: FailureDiagnosis with suggested fix
            retry_count: Current retry attempt number

        Returns:
            Fixed code string
        """
        logger.info(f"Generating fix for step {step.step_number} (attempt {retry_count + 1})")

        prompt = self._build_fix_prompt(step, diagnosis, retry_count)

        try:
            raw_code = self.llm_client.generate(prompt)
            # Clean markdown formatting from generated code
            fixed_code = clean_code(str(raw_code))
            logger.debug(f"Generated fix length: {len(fixed_code)} characters")
            return str(fixed_code)
        except Exception as e:
            logger.error(f"Failed to generate fix: {e}")
            raise

    def learn_from_success(
        self, step: CodeStep, diagnosis: FailureDiagnosis, fixed_code: str
    ) -> None:
        """
        Store successful fix in learning database.

        Args:
            step: Original CodeStep that failed
            diagnosis: FailureDiagnosis with error details
            fixed_code: The fixed code that worked
        """
        try:
            pattern = LearningPattern(
                error_type=diagnosis.error_type,
                error_pattern=diagnosis.error_details,
                fix_applied=diagnosis.suggested_fix,
                code_snippet=fixed_code,
                tags=self._extract_tags_from_step(step),
                source_language="python",
            )
            self.mistake_learner.store_pattern(pattern)
            logger.info(f"Learned from successful fix of {diagnosis.error_type}")
        except Exception as e:
            logger.warning(f"Failed to save learning pattern: {e}")

    def should_abort_retry(
        self,
        step_number: int,
        error_type: str,
        retry_count: int,
        fix_strategy: str,
        max_retries: Optional[int] = None,
    ) -> bool:
        """Determine if we should abort retry attempts.

        Always tracks repeated errors to prevent infinite loops, even when max_retries is None.
        """
        # Track repeated errors regardless of max_retries
        key = f"{step_number}:{error_type}"
        if key not in self.retry_history:
            self.retry_history[key] = {"count": 0, "last_fix_strategy": None}

        self.retry_history[key]["count"] += 1
        self.retry_history[key]["last_fix_strategy"] = fix_strategy

        # Abort if same error repeats 3+ times
        if self.retry_history[key]["count"] >= 3:
            logger.warning(
                f"Same error ({error_type}) repeated 3+ times on step {step_number}, aborting"
            )
            return True

        # Hard limit: never exceed 25 retries even if max_retries is None
        if retry_count >= 25:
            logger.warning(f"Hard limit of 25 retries exceeded for step {step_number}")
            return True

        # Check user-specified max_retries if provided
        effective_max = self.default_max_retries if max_retries is None else max_retries
        if effective_max is not None and retry_count >= effective_max:
            logger.warning(f"Max retries ({effective_max}) exceeded for step {step_number}")
            return True

        return False

    def get_next_fix_strategy(self, retry_count: int, error_type: str) -> str:
        """
        Get the next fix strategy based on retry count.

        Rotates through different strategies to maximize success probability.

        Args:
            retry_count: Current retry attempt number
            error_type: Type of error

        Returns:
            Fix strategy to try
        """
        strategies = [
            "regenerate_code",
            "add_error_handling",
            "add_input_validation",
            "simplify_code",
            "adjust_parameters",
            "add_retry_logic",
            "add_documentation",
            "refactor_logic",
            "add_comments",
            "stdlib_fallback",
            "install_package",
        ]

        # Choose strategy based on retry count
        strategy_index = retry_count % len(strategies)
        return strategies[strategy_index]

    def _extract_tags_from_step(self, step: CodeStep) -> List[str]:
        """
        Extract relevant tags from step for learning.

        Args:
            step: CodeStep

        Returns:
            List of tags
        """
        tags = ["general"]

        description_lower = step.description.lower()

        if any(word in description_lower for word in ["file", "write", "read", "save"]):
            tags.append("file_ops")
        if any(word in description_lower for word in ["desktop", "path", "directory"]):
            tags.append("desktop")
        if any(word in description_lower for word in ["error", "exception", "handling"]):
            tags.append("error_handling")
        if any(word in description_lower for word in ["network", "connection", "http", "api"]):
            tags.append("network")
        if "windows" in description_lower or "win32" in description_lower:
            tags.append("windows")

        return tags

    def retry_step_with_fix(
        self,
        step: CodeStep,
        fixed_code: str,
        max_retries: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Execute fixed code and retry until success or max attempts.

        Args:
            step: CodeStep to retry
            fixed_code: The fixed code to execute
            max_retries: Max attempts (None = unlimited). Timeout still applies per attempt.

        Returns:
            Tuple of (success, output, error_if_failed)
        """

        import os
        import subprocess
        import sys
        import tempfile

        attempt = 1
        last_output = ""

        while True:
            if max_retries is not None and attempt > max_retries:
                error_msg = f"Max {max_retries} attempts exceeded"
                logger.warning(
                    "Max user-specified retries (%s) exceeded for step %s",
                    max_retries,
                    step.step_number,
                )
                return False, last_output, error_msg

            progress = format_attempt_progress(attempt, max_retries)
            logger.info(f"Step {step.step_number}: {progress}")

            # Write fixed code to temp file for this attempt
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(fixed_code)
                temp_file = f.name

            try:
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

                process = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=step.timeout_seconds,
                    creationflags=creation_flags,
                )

                output = ""
                if process.stdout:
                    output += process.stdout
                if process.stderr:
                    output += process.stderr

                last_output = output

                if process.returncode == 0:
                    logger.info(f"Step {step.step_number} succeeded on {progress}")
                    return True, output, None

                logger.warning(f"Step {step.step_number} failed on {progress}: {output[:200]}")

                attempt += 1
                continue

            except subprocess.TimeoutExpired:
                error_msg = f"Timeout after {step.timeout_seconds} seconds"
                logger.error(f"Step {step.step_number} timeout on {progress}")
                return False, last_output, error_msg
            except Exception as e:
                last_output = str(e)
                logger.error(f"Step {step.step_number} error on {progress}: {e}")
                attempt += 1
                continue
            finally:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

    def _build_diagnosis_prompt(
        self,
        step: CodeStep,
        error_type: str,
        error_details: str,
        original_output: str,
    ) -> str:
        """Build prompt for failure diagnosis."""
        import getpass

        username = getpass.getuser()

        # Check for Windows socket errors
        is_windows_socket_error = (
            "winerror" in error_details.lower()
            or "socket" in error_details.lower()
            or "wsaenotsock" in error_details.lower()
        )

        if is_windows_socket_error:
            prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

A subprocess execution failed on Windows with this error:

Step Description: {step.description}

Original Code:
```python
{step.code or "No code provided"}
```

Error Type: {error_type}

Error Details:
{error_details}

Full Output:
{original_output[:1000]}

This is likely a Windows subprocess/pipe issue, NOT a POSIX compatibility issue.

Suggest a fix that:
1. Adds proper error handling for this specific error
2. Works specifically on Windows
3. Does NOT try to make the code POSIX-compatible (that's not the issue)

Provide your diagnosis in this JSON format:
{{
  "root_cause": "Clear explanation of what went wrong",
  "suggested_fix": "Specific fix to apply",
  "fix_strategy": "one of: regenerate_code, add_retry_logic, "
                 "install_package, adjust_parameters, or manual",
  "confidence": 0.0 to 1.0
}}

Common fix strategies:
- regenerate_code: Rewrite the code to fix bugs
- add_retry_logic: Add retry logic with backoff
- install_package: Install missing dependencies
- adjust_parameters: Change parameters or configuration
- manual: Requires human intervention

Return only valid JSON, no other text."""
        else:
            prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

Analyze this code execution failure and provide a detailed diagnosis.

IMPORTANT: You are running on Windows.
- Home directory: C:\\Users\\{username}
- Desktop: C:\\Users\\{username}\\Desktop

If the error is FileNotFoundError or WinError 3, check if the code is trying to
use Unix paths (e.g., /path/to/..., /home/...) and suggest replacing them with
correct Windows paths.

Step Description: {step.description}

Original Code:
```python
{step.code or "No code provided"}
```

Error Type: {error_type}

Error Details:
{error_details}

Full Output:
{original_output[:1000]}

Provide your diagnosis in this JSON format:
{{
  "root_cause": "Clear explanation of what went wrong",
  "suggested_fix": "Specific fix to apply",
  "fix_strategy": "one of: regenerate_code, add_retry_logic, "
                  "stdlib_fallback, install_package, adjust_parameters, or manual",
  "confidence": 0.0 to 1.0
}}

Common fix strategies:
- regenerate_code: Rewrite the code to fix bugs
- add_retry_logic: Add retry logic with backoff
- stdlib_fallback: Rewrite using only Python standard library (preferred for simple tasks)
- install_package: Install missing dependencies (only for complex tasks requiring external packages)
- adjust_parameters: Change parameters or configuration
- manual: Requires human intervention

IMPORTANT:
- For simple tasks (calculators, basic scripts), prefer stdlib_fallback over install_package
- Only use install_package strategy for genuinely complex requirements
- Python has built-in eval(), math, re, os, sys, json, subprocess - use these first

Return only valid JSON, no other text."""
        return prompt

    def _build_fix_prompt(
        self, step: CodeStep, diagnosis: FailureDiagnosis, retry_count: int
    ) -> str:
        """Build prompt for generating fixed code."""
        # Add stdlib-only requirement for ImportError cases
        stdlib_requirement = ""
        if diagnosis.fix_strategy == "stdlib_fallback" or "ImportError" in diagnosis.error_type:
            stdlib_requirement = """

CRITICAL: Use ONLY Python standard library modules (no external packages like asteval,
numpy, pandas, etc.).
For simple tasks like calculators, use built-in functions like eval() with proper validation.
Use built-in modules like re, math, os, sys, json, subprocess, etc. but NO external
dependencies."""

        prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

Generate fixed code for this failed step.

Step Description: {step.description}

Original Code:
```python
{step.code or "No code provided"}
```

Diagnosis:
- Root Cause: {diagnosis.root_cause}
- Suggested Fix: {diagnosis.suggested_fix}
- Fix Strategy: {diagnosis.fix_strategy}{stdlib_requirement}

This is retry attempt {retry_count + 1}.

Requirements:
1. Fix the issue identified in the diagnosis
2. Follow the suggested fix strategy
3. Add better error handling
4. Make the code more robust
5. Use hard-coded inputs instead of input()
6. Return only the code, no explanations or markdown formatting
7. Ensure the code is complete and executable
8. For simple tasks (calculators, basic scripts), use stdlib-only solutions

Return only the fixed code, no other text."""
        return prompt

    def _parse_diagnosis_response(
        self, response: str, error_type: str, error_details: str
    ) -> FailureDiagnosis:
        """Parse LLM response into FailureDiagnosis."""
        import json

        try:
            # Try to extract JSON from response
            json_text = self._extract_json_from_response(response)
            data = json.loads(json_text)

            return FailureDiagnosis(
                error_type=error_type,
                error_details=error_details,
                root_cause=data.get("root_cause", "Unknown"),
                suggested_fix=data.get("suggested_fix", "No suggestion"),
                fix_strategy=data.get("fix_strategy", "manual"),
                confidence=float(data.get("confidence", 0.5)),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse diagnosis response: {e}")
            # Return fallback diagnosis
            return FailureDiagnosis(
                error_type=error_type,
                error_details=error_details,
                root_cause="Failed to parse diagnosis",
                suggested_fix=response[:200],
                fix_strategy="manual",
                confidence=0.4,
            )

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response."""
        text = response.strip()

        # Try to find JSON in markdown code blocks
        if "```" in text:
            start_idx = text.find("```json")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

            # Try generic code block
            start_idx = text.find("```")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

        # Try to find JSON object
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        raise ValueError("No valid JSON found in response")
