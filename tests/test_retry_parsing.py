"""Tests for retry limit parsing."""

from typing import Optional

import pytest

from spectral.retry_parsing import parse_retry_limit


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("max 5 attempts", 5),
        ("maximum 2", 2),
        ("give up after 3 tries", 3),
        ("5 retries", 5),
        ("but max 2", 2),
        ("if it fails more than 3 times just give up", 3),
        ("write me something", None),
    ],
)
def test_parse_retry_limit(text: str, expected: Optional[int]) -> None:
    assert parse_retry_limit(text) == expected
