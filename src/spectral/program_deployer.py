"""
Program deployer module for autonomous file deployment.

Handles auto-detection of save locations, meaningful filename generation,
and direct file writing without user intervention.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProgramDeployer:
    """
    Deploys generated programs to appropriate locations.

    Features:
    - Auto-detect save location (Desktop, Documents, Downloads)
    - Generate meaningful filenames
    - Direct file writing (no dialogs)
    - Create README with usage instructions
    """

    def __init__(self) -> None:
        """Initialize program deployer."""
        self.home = Path.home()
        logger.info("ProgramDeployer initialized")

    def detect_save_location(self, user_request: str) -> Path:
        """
        Detect appropriate save location from user request.

        Args:
            user_request: User's original request

        Returns:
            Path to save location (default: Desktop)
        """
        request_lower = user_request.lower()

        # Check for keywords
        if "desktop" in request_lower:
            return self.home / "Desktop"
        elif "documents" in request_lower or "my documents" in request_lower:
            return self.home / "Documents"
        elif "downloads" in request_lower:
            return self.home / "Downloads"
        elif "desktop" in request_lower:
            return self.home / "Desktop"

        # Default to Desktop
        return self.home / "Desktop"

    def generate_filename(self, code: str, user_request: str, language: str = "python") -> str:
        """
        Generate a meaningful filename based on code content.

        Args:
            code: Generated code
            user_request: User's original request
            language: Programming language

        Returns:
            Generated filename with extension
        """
        # Analyze code to determine purpose
        code_lower = code.lower()
        request_lower = user_request.lower()

        # Check for specific program types
        filename_map = {
            "calculator": "calculator",
            "guessing game": "guessing_game",
            "number game": "number_game",
            "quiz": "quiz",
            "math quiz": "math_quiz",
            "todo": "todo_app",
            "to-do": "todo_app",
            "temperature converter": "temperature_converter",
            "converter": "converter",
            "password generator": "password_generator",
            "random generator": "random_generator",
            "notepad": "notepad",
            "text editor": "text_editor",
            "chatbot": "chatbot",
            "simple ai": "simple_ai",
        }

        for keyword, filename in filename_map.items():
            if keyword in code_lower or keyword in request_lower:
                return f"{filename}.{self._get_extension(language)}"

        # Extract potential name from request
        # Look for "create a X" or "make a X" patterns
        create_pattern = r"(?:create|make|write|build)\s+(?:a\s+)?(\w+)"
        match = re.search(create_pattern, request_lower)
        if match:
            name = match.group(1).replace(" ", "_")
            return f"{name}.{self._get_extension(language)}"

        # Default: generate timestamped filename
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"program_{timestamp}.{self._get_extension(language)}"

    def _get_extension(self, language: str) -> str:
        """
        Get file extension for language.

        Args:
            language: Programming language name

        Returns:
            File extension (with dot)
        """
        extensions = {
            "python": "py",
            "javascript": "js",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "ruby": "rb",
            "go": "go",
            "rust": "rs",
        }

        lang_lower = language.lower()
        ext = extensions.get(lang_lower, "txt")
        return f".{ext}"

    def deploy_program(
        self,
        code: str,
        user_request: str,
        save_location: Optional[Path] = None,
        filename: Optional[str] = None,
        language: str = "python",
        create_readme: bool = True,
    ) -> dict:
        """
        Deploy program to file system.

        Args:
            code: Generated code
            user_request: User's original request
            save_location: Override save location (optional)
            filename: Override filename (optional)
            language: Programming language
            create_readme: Whether to create README file

        Returns:
            Dictionary with deployment details
        """
        # Detect save location if not provided
        if save_location is None:
            save_location = self.detect_save_location(user_request)

        # Generate filename if not provided
        if filename is None:
            filename = self.generate_filename(code, user_request, language)

        # Create save directory if it doesn't exist
        save_location.mkdir(parents=True, exist_ok=True)

        # Write program file
        file_path = save_location / filename
        file_path.write_text(code, encoding="utf-8")

        logger.info(f"Deployed program to: {file_path}")

        result = {
            "file_path": str(file_path),
            "filename": filename,
            "save_location": str(save_location),
            "file_size": len(code),
            "language": language,
        }

        # Create README if requested
        if create_readme:
            readme_path = self._create_readme(file_path, code, user_request)
            result["readme_path"] = str(readme_path)

        return result

    def _create_readme(
        self,
        program_path: Path,
        code: str,
        user_request: str,
    ) -> Path:
        """
        Create README file with usage instructions.

        Args:
            program_path: Path to program file
            code: Program code
            user_request: User's original request

        Returns:
            Path to README file
        """
        import datetime

        readme_path = program_path.parent / f"{program_path.stem}_README.txt"

        # Extract program description
        description = self._extract_description(code, user_request)

        # Get timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generate README content
        readme_lines = [
            description,
            "",
            "Generated by Spectral AI Assistant",
            "",
            "Original Request:",
            user_request,
            "",
            "Usage:",
            "1. Make sure Python is installed: https://python.org/downloads/",
            "2. Run from terminal/command prompt:",
            f"   python {program_path.name}",
            "",
            "Requirements:",
            "- Python 3.6 or higher",
            "- Standard library only (no external packages required)",
            "",
            "File Location:",
            str(program_path),
            "",
            f"Generated: {timestamp}",
        ]

        readme_content = "\n".join(readme_lines)

        readme_path.write_text(readme_content, encoding="utf-8")
        logger.info(f"Created README: {readme_path}")

        return readme_path

    def _extract_description(self, code: str, user_request: str) -> str:
        """
        Extract program description from code and request.

        Args:
            code: Program code
            user_request: User's original request

        Returns:
            Program description
        """
        # Look for docstring in code
        docstring_match = re.search(r'"""(.*?)"""', code, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            if len(docstring) > 10:
                return docstring

        # Look for single-line docstring
        docstring_match = re.search(r"'''(.*?)'''", code, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            if len(docstring) > 10:
                return docstring

        # Use user request as description
        return f"A program that: {user_request}"

    def get_deployment_summary(self, deployment: dict) -> str:
        """
        Get human-readable deployment summary.

        Args:
            deployment: Deployment result dictionary

        Returns:
            Summary string
        """
        summary = f"✅ Program saved to: {deployment['file_path']}\n"
        summary += f"   File size: {deployment['file_size']} bytes\n"

        if "readme_path" in deployment:
            summary += f"   README: {deployment['readme_path']}\n"

        return summary
