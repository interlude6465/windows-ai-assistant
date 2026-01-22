"""spectral.intelligent_retry

A small utility to manage retry loops in the code-generation/execution pipeline.

Goals:
- Provide a sensible default upper bound on retries (prevents infinite loops)
- Detect when we're stuck repeating the *same* error and stop early
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class RetryDecision:
    should_retry: bool
    reason: Optional[str] = None


class IntelligentRetryManager:
    def __init__(self, max_retries: int = 3, error_repeat_threshold: int = 2) -> None:
        if max_retries <= 0:
            raise ValueError("max_retries must be > 0")
        if error_repeat_threshold <= 1:
            raise ValueError("error_repeat_threshold must be > 1")

        self.max_retries = max_retries
        self.error_repeat_threshold = error_repeat_threshold

        self._attempts = 0
        self._recent_errors: deque[str] = deque(maxlen=5)

    @property
    def attempts(self) -> int:
        return self._attempts

    def next_attempt(self) -> int:
        """Increment and return the next attempt number (1-based)."""

        self._attempts += 1
        return self._attempts

    def record_error(self, error: str) -> None:
        normalized = self._normalize_error(error)
        if normalized:
            self._recent_errors.append(normalized)

    def should_retry(self) -> RetryDecision:
        if self._attempts >= self.max_retries:
            return RetryDecision(False, f"max_retries ({self.max_retries}) reached")

        if self._is_stuck_in_loop():
            return RetryDecision(False, "same error repeated")

        return RetryDecision(True, None)

    def _is_stuck_in_loop(self) -> bool:
        if len(self._recent_errors) < self.error_repeat_threshold:
            return False

        last = list(self._recent_errors)[-self.error_repeat_threshold :]
        return len(set(last)) == 1

    def _normalize_error(self, error: str) -> str:
        # Avoid trivial differences from causing retries to look "different".
        normalized = (error or "").strip()
        normalized = " ".join(normalized.split())
        return normalized
