"""
Utility functions for Jarvis.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# Enhanced code cleaning function that uses CodeCleaner class
def clean_code(code: str, raise_on_empty: bool = True) -> str:
    """
    Strip markdown code formatting from generated code.

    Removes markdown backticks (```) and language specifiers from code,
    returning only the raw executable code.

    Args:
        code: Code string that may contain markdown formatting
        raise_on_empty: Whether to raise ValueError if code is empty

    Returns:
        Cleaned code string without markdown formatting

    Raises:
        ValueError: If code is empty and raise_on_empty is True
    """
    if not code:
        if raise_on_empty:
            raise ValueError("Generated code is empty!")
        return ""

    text = code.strip()

    # Remove markdown code blocks with language specifiers
    # Pattern 1: ```python\n...\n```
    # Pattern 2: ```\n...\n```
    # Pattern 3: ```python ... ```

    # Match code blocks with language specifier
    code_block_pattern = r"```(?:\w+)?\s*\n([\s\S]*?)```"
    match = re.search(code_block_pattern, text)

    if match:
        logger.debug("Extracted code from markdown code block")
        return match.group(1).strip()

    # If no code block found, try to remove standalone ``` markers
    # This handles cases like ```code```
    text = re.sub(r"^```\w*\s*", "", text)  # Remove opening ```
    text = re.sub(r"\s*```$", "", text)  # Remove closing ```

    # Clean up any remaining whitespace
    cleaned = text.strip()

    # Detect empty code
    if not cleaned or cleaned.isspace():
        if raise_on_empty:
            raise ValueError("Generated code is empty!")
        return ""

    return cleaned


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length of truncated text
        suffix: Suffix to add if text is truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
