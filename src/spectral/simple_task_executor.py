"""spectral.simple_task_executor

This module implements a *simple task* detector that routes very common, immediate
user requests to small, purpose-built Python snippets.

Important design goal:
- SimpleTaskExecutor MUST NOT execute tasks itself.
- It only detects if it can handle a request and returns Python code to be
  executed by the code execution system.

This avoids brittle, hardcoded parsing/formatting logic in the assistant and
instead lets Python produce the raw output naturally.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class SimpleTaskExecutor:
    """Detect and generate Python code for simple tasks."""

    def __init__(self) -> None:
        self.ip_address_patterns = [
            "ip",
            "ipconfig",
            "address",
            "network",
            "wifi",
            "connection",
        ]
        self.list_files_patterns = ["list", "files", "folder", "directory", "show me"]
        self.read_file_patterns = ["read", "open", "show", "display", "view"]
        self.run_command_patterns = ["run", "execute", "command"]

        logger.info("SimpleTaskExecutor initialized")

    def can_handle(self, user_input: str) -> bool:
        """Return True if the input should be handled as a simple task."""

        user_lower = user_input.lower()

        # Exclude code-generation/development tasks
        complex_keywords = [
            "write",
            "create",
            "generate",
            "build",
            "program",
            "app",
            "application",
            "script",
            "code",
            "develop",
            "implement",
        ]

        if any(keyword in user_lower for keyword in complex_keywords):
            return False

        # IP / network configuration queries
        if self._matches_pattern(user_input, self.ip_address_patterns):
            return True

        # List files queries
        if self._matches_pattern(user_input, self.list_files_patterns):
            if any(folder in user_lower for folder in ["desktop", "downloads", "documents"]):
                return True

        # Read file queries
        if self._matches_pattern(user_input, self.read_file_patterns):
            if "file" in user_lower or self._detect_file_path(user_input):
                return True

        # Run command queries
        if self._matches_pattern(user_input, self.run_command_patterns):
            if re.search(r"\b(?:run|execute|command)\b\s+\S+", user_input, re.IGNORECASE):
                return True

        return False

    def get_code_for_task(self, user_input: str) -> Optional[str]:
        """Return Python code for the detected simple task, or None."""

        user_lower = user_input.lower()

        if self._matches_pattern(user_input, self.ip_address_patterns):
            return self._generate_ipconfig_code(user_input)

        if self._matches_pattern(user_input, self.list_files_patterns) and any(
            folder in user_lower for folder in ["desktop", "downloads", "documents"]
        ):
            return self._generate_list_files_code(user_input)

        if self._matches_pattern(user_input, self.read_file_patterns) and (
            "file" in user_lower or self._detect_file_path(user_input)
        ):
            return self._generate_read_file_code(user_input)

        if self._matches_pattern(user_input, self.run_command_patterns):
            return self._generate_run_command_code(user_input)

        return None

    def _generate_ipconfig_code(self, user_input: str) -> str:
        user_lower = user_input.lower()
        full = any(k in user_lower for k in ["full", "all", "/all"])
        windows_cmd = ["ipconfig", "/all"] if full else ["ipconfig"]

        return rf"""import platform
import shutil
import subprocess
import sys

system = platform.system()

if system == "Windows":
    cmd = {windows_cmd!r}
else:
    if shutil.which("ip"):
        cmd = ["ip", "addr", "show"]
    elif shutil.which("ifconfig"):
        cmd = ["ifconfig", "-a"]
    else:
        cmd = ["hostname", "-I"]

result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)

if result.stdout:
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
if result.stderr:
    print(result.stderr, file=sys.stderr)
"""

    def _generate_list_files_code(self, user_input: str) -> str:
        escaped_input = user_input.replace("\\", "\\\\").replace('"', '\\"')

        return rf"""from pathlib import Path

user_input = "{escaped_input}"
text = user_input.lower()

home = Path.home()

folder = None
folder_name = None

if "desktop" in text:
    folder = home / "Desktop"
    folder_name = "Desktop"
elif "downloads" in text:
    folder = home / "Downloads"
    folder_name = "Downloads"
elif "documents" in text:
    folder = home / "Documents"
    folder_name = "Documents"

if folder is None:
    print("Please specify which folder to list: Desktop, Downloads, or Documents.")
    raise SystemExit(0)

if not folder.exists():
    print(f"Folder not found: {{folder}}")
    raise SystemExit(0)

entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

if not entries:
    print(f"The {{folder_name}} folder is empty.")
    raise SystemExit(0)

for p in entries:
    try:
        if p.is_dir():
            print(f"[DIR]  {{p.name}}")
        else:
            size = p.stat().st_size
            print(f"{{p.name}} ({{size}} bytes)")
    except Exception as e:
        print(f"{{p.name}} (error reading metadata: {{e}})")
"""

    def _generate_read_file_code(self, user_input: str) -> str:
        escaped_input = user_input.replace("\\", "\\\\").replace('"', '\\"')

        return rf"""import os
import re

user_input = "{escaped_input}"


def extract_path(text: str):
    # 1) Quoted path
    m = re.search(r"[\"']([^\"']+)[\"']", text)
    if m:
        return m.group(1)

    # 2) Windows path with drive letter + extension (allows spaces)
    m = re.search(r"([A-Za-z]:[\\/][^\r\n]+?[.][A-Za-z0-9]{{1,8}})", text)
    if m:
        return m.group(1).rstrip(".,);")

    # 3) Unix-ish absolute/relative path with extension
    m = re.search(r"((?:~|[.]/|/)[^\s]+?[.][A-Za-z0-9]{{1,8}})", text)
    if m:
        return m.group(1).rstrip(".,);")

    return None


path = extract_path(user_input)
if not path:
    print("Please provide the file path you'd like me to read.")
    raise SystemExit(0)

path = os.path.expanduser(path)

try:
    with open(path, "r", encoding="utf-8") as f:
        print(f.read(), end="")
except UnicodeDecodeError:
    with open(path, "r", encoding="latin-1") as f:
        print(f.read(), end="")
except Exception as e:
    print(f"Error reading file: {{e}}")
"""

    def _generate_run_command_code(self, user_input: str) -> str:
        """Generate code to run a command."""
        import re as regex

        # Try to extract command after "run" or "execute" keyword
        # Patterns: "run whoami", "run dir", "execute ipconfig", etc.
        patterns = [
            r'run\s+(\w+)',           # "run whoami", "run dir"
            r'execute\s+(\w+)',       # "execute ipconfig"
            r'(?:run|execute)\s+(\w+)',  # Either run or execute
        ]

        command = None
        for pattern in patterns:
            match = regex.search(pattern, user_input, regex.IGNORECASE)
            if match:
                command = match.group(1).strip()
                break

        if command:
            escaped_command = command.replace("\\", "\\\\").replace('"', '\\"')
            return rf'''import subprocess
import sys

try:
    result = subprocess.run(["{escaped_command}"], capture_output=True, text=True, timeout=30)
    print(result.stdout)

    if result.returncode != 0:
        print(f"Error: {{result.stderr}}", file=sys.stderr)
        sys.exit(result.returncode)
except Exception as e:
    print(f"Error running command: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
'''

        return '''print("Please specify a command to run.")
print("Example: whoami, dir, tasklist, systeminfo")'''

    def _detect_file_path(self, user_input: str) -> bool:
        """Detect if user input contains a file path (by file extension)."""

        extensions = [
            r"\.(txt|md|py|js|html|css|json|xml|csv|log|yaml|yml|ini|cfg|conf)",
            r"\.(pdf|doc|docx|xls|xlsx|ppt|pptx)",
            r"\.(jpg|jpeg|png|gif|bmp|svg|ico)",
            r"\.(mp3|mp4|avi|mov|wav|flac)",
            r"\.(zip|tar|gz|rar|7z)",
        ]

        user_lower = user_input.lower()
        return any(re.search(ext_pattern, user_lower) for ext_pattern in extensions)

    def _matches_pattern(self, user_input: str, keywords: list[str]) -> bool:
        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in keywords)
