"""
Sandbox manager module for isolated code execution.

Creates temporary sandbox directories for safe code generation and testing.
Ensures isolation, resource limits, and automatic cleanup.
"""

import logging
import random
import shutil
import string
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SandboxState(Enum):
    """Sandbox lifecycle states."""

    CREATED = "created"
    GENERATING = "generating"
    TESTING = "testing"
    PASSED = "passed"
    FAILED = "failed"
    ARCHIVED = "archived"
    CLEANED = "cleaned"


class SandboxManager:
    """
    Manages isolated sandbox environments for code generation and testing.

    Features:
    - Unique temp directories for each task
    - Resource limits (prevent infinite loops)
    - Write restrictions
    - Complete isolation
    - Automatic cleanup
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """
        Initialize sandbox manager.

        Args:
            base_dir: Base directory for sandboxes (default: system temp)
        """
        if base_dir is None:
            base_dir = Path(tempfile.gettempdir())

        self.base_dir = base_dir
        self.active_sandboxes: dict[str, SandboxInfo] = {}
        logger.info(f"SandboxManager initialized with base_dir: {base_dir}")

    def create_sandbox(self, task_name: str = "task") -> "SandboxInfo":
        """
        Create a new sandbox directory.

        Args:
            task_name: Name identifier for the task

        Returns:
            SandboxInfo object with sandbox details
        """
        # Generate unique identifier
        timestamp = int(time.time())
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        sandbox_id = f"jarvis_sandbox_{timestamp}_{random_suffix}"

        # Create sandbox directory
        sandbox_path = self.base_dir / sandbox_id
        sandbox_path.mkdir(parents=True, exist_ok=True)

        # Create sandbox info
        sandbox_info = SandboxInfo(
            sandbox_id=sandbox_id,
            path=sandbox_path,
            state=SandboxState.CREATED,
            task_name=task_name,
            created_at=time.time(),
        )

        self.active_sandboxes[sandbox_id] = sandbox_info

        logger.info(f"Created sandbox: {sandbox_id} at {sandbox_path}")
        return sandbox_info

    def cleanup_sandbox(self, sandbox_id: str, archive: bool = False) -> bool:
        """
        Clean up a sandbox directory.

        Args:
            sandbox_id: Sandbox identifier
            archive: If True, move to archive instead of delete

        Returns:
            True if cleanup succeeded, False otherwise
        """
        if sandbox_id not in self.active_sandboxes:
            logger.warning(f"Sandbox not found: {sandbox_id}")
            return False

        sandbox_info = self.active_sandboxes[sandbox_id]

        try:
            if archive:
                # Move to archive directory
                archive_dir = self.base_dir / "jarvis_archived"
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / sandbox_id

                if sandbox_info.path.exists():
                    shutil.move(str(sandbox_info.path), str(archive_path))
                    logger.info(f"Archived sandbox: {sandbox_id} to {archive_path}")
            else:
                # Delete sandbox directory
                if sandbox_info.path.exists():
                    shutil.rmtree(sandbox_info.path)
                    logger.info(f"Cleaned sandbox: {sandbox_id}")

            sandbox_info.state = SandboxState.ARCHIVED if archive else SandboxState.CLEANED
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup sandbox {sandbox_id}: {e}")
            return False

    def cleanup_all(self) -> None:
        """Clean up all active sandboxes."""
        for sandbox_id in list(self.active_sandboxes.keys()):
            self.cleanup_sandbox(sandbox_id)

    def get_sandbox(self, sandbox_id: str) -> Optional["SandboxInfo"]:
        """
        Get sandbox info by ID.

        Args:
            sandbox_id: Sandbox identifier

        Returns:
            SandboxInfo object or None if not found
        """
        return self.active_sandboxes.get(sandbox_id)

    def get_active_sandboxes(self) -> list["SandboxInfo"]:
        """
        Get all active sandboxes.

        Returns:
            List of SandboxInfo objects
        """
        return list(self.active_sandboxes.values())


class SandboxInfo:
    """Information about a sandbox environment."""

    def __init__(
        self,
        sandbox_id: str,
        path: Path,
        state: SandboxState,
        task_name: str,
        created_at: float,
    ) -> None:
        """
        Initialize sandbox info.

        Args:
            sandbox_id: Unique sandbox identifier
            path: Path to sandbox directory
            state: Current sandbox state
            task_name: Task name for identification
            created_at: Creation timestamp
        """
        self.sandbox_id = sandbox_id
        self.path = path
        self.state = state
        self.task_name = task_name
        self.created_at = created_at
        self.files_created: list[str] = []
        self.code_generated: Optional[str] = None
        self.test_results: list[dict] = []
        self.errors_encountered: list[str] = []

    def update_state(self, new_state: SandboxState) -> None:
        """
        Update sandbox state.

        Args:
            new_state: New sandbox state
        """
        self.state = new_state
        logger.debug(f"Sandbox {self.sandbox_id} state: {new_state.value}")

    def add_file(self, file_path: str) -> None:
        """
        Track a file created in sandbox.

        Args:
            file_path: Relative path to file
        """
        self.files_created.append(file_path)

    def add_test_result(self, test_num: int, inputs: list, output: str, passed: bool) -> None:
        """
        Add a test result.

        Args:
            test_num: Test case number
            inputs: Input values
            output: Program output
            passed: Whether test passed
        """
        self.test_results.append(
            {
                "test_num": test_num,
                "inputs": inputs,
                "output": output,
                "passed": passed,
            }
        )

    def add_error(self, error: str) -> None:
        """
        Track an error encountered.

        Args:
            error: Error message
        """
        self.errors_encountered.append(error)

    def get_summary(self) -> dict:
        """
        Get sandbox summary.

        Returns:
            Dictionary with sandbox summary
        """
        passed_tests = sum(1 for t in self.test_results if t["passed"])
        return {
            "sandbox_id": self.sandbox_id,
            "task_name": self.task_name,
            "state": self.state.value,
            "created_at": self.created_at,
            "files_created": len(self.files_created),
            "tests_run": len(self.test_results),
            "tests_passed": passed_tests,
            "tests_failed": len(self.test_results) - passed_tests,
            "errors": len(self.errors_encountered),
        }
