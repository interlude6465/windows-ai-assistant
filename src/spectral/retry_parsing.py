"""Retry limit parsing utilities.

These helpers extract user-specified retry/attempt limits from natural language.

Default behavior across the code execution pipeline is unlimited retries unless
an explicit maximum is provided by the user.
"""

from __future__ import annotations

import re
from typing import Optional


def parse_retry_limit(user_message: str) -> Optional[int]:
    """Extract a max retry/attempt limit from user text.

    Returns:
        The maximum number of attempts if specified, otherwise None (unlimited).

    Examples:
        - "max 5 attempts" -> 5
        - "maximum 2" -> 2
        - "give up after 3 tries" -> 3
        - "5 retries" -> 5
        - "if it fails more than 3 times just give up" -> 3
        - No keywords -> None
    """

    text = user_message.lower().strip()

    patterns = [
        # "max 5", "maximum 5", "max 5 attempts"
        r"\bmax(?:imum)?\s+(?:of\s+)?(?P<n>\d+)\b(?:\s*(?:retries?|attempts?|tries?|times))?",
        # "no more than 3 attempts"
        r"\bno\s+more\s+than\s+(?P<n>\d+)\b(?:\s*(?:retries?|attempts?|tries?|times))?",
        # "give up after 3 tries"
        r"\bgive\s+up\s+after\s+(?P<n>\d+)\b(?:\s*(?:retries?|attempts?|tries?|times))?",
        # "stop after 3 attempts"
        r"\bstop\s+after\s+(?P<n>\d+)\b(?:\s*(?:retries?|attempts?|tries?|times))?",
        # "fails more than 3 times" / "fails over 3"
        (
            r"\bfail(?:s|ed|ing)?\s+(?:more\s+than|over)\s+(?P<n>\d+)\b"
            r"(?:\s*(?:times|attempts?|tries?))?"
        ),
        # "3 retries" / "3 attempts" / "3 tries"
        r"\b(?P<n>\d+)\s+(?:retries?|attempts?|tries?)\b",
        # "but max 2" / "but 2"
        r"\bbut\s+(?:max(?:imum)?\s+)?(?P<n>\d+)\b(?:\s*(?:retries?|attempts?|tries?|times))?\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        try:
            n = int(match.group("n"))
        except Exception:
            continue

        if n <= 0:
            return None

        return n

    return None


def format_attempt_progress(attempt: int, max_attempts: Optional[int]) -> str:
    """Format attempt progress as "Attempt X/∞" or "Attempt X/Y"."""

    if max_attempts is None:
        return f"Attempt {attempt}/∞"
    return f"Attempt {attempt}/{max_attempts}"
