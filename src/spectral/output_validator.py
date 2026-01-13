"""
Output validator module for test result validation.

Validates program outputs against expected results using multiple
validation modes: exact, contains, numeric, pattern, and callable.
"""

import logging
import re
from typing import Callable, Optional, Union

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    Validates test outputs against expected results.

    Supports multiple validation modes:
    - exact: Exact string match
    - contains: String contains expected
    - numeric: Extract and compare numbers
    - pattern: Regex pattern matching
    - callable: Custom validation function
    """

    def __init__(self) -> None:
        """Initialize output validator."""
        logger.info("OutputValidator initialized")

    def validate(
        self,
        output: str,
        expected: Union[str, int, float, Callable],
        mode: str = "contains",
        case_sensitive: bool = False,
    ) -> bool:
        """
        Validate output against expected result.

        Args:
            output: Actual program output
            expected: Expected value (string, number, or callable)
            mode: Validation mode (exact, contains, numeric, pattern, callable)
            case_sensitive: Whether string comparison is case-sensitive

        Returns:
            True if validation passes, False otherwise
        """
        output = str(output).strip()

        if mode == "exact":
            return self._validate_exact(output, expected, case_sensitive)
        elif mode == "contains":
            return self._validate_contains(output, expected, case_sensitive)
        elif mode == "numeric":
            return self._validate_numeric(output, expected)
        elif mode == "pattern":
            return self._validate_pattern(output, expected)
        elif mode == "callable":
            return self._validate_callable(output, expected)
        else:
            logger.warning(f"Unknown validation mode: {mode}")
            return False

    def _validate_exact(self, output: str, expected: str, case_sensitive: bool = False) -> bool:
        """
        Validate exact string match.

        Args:
            output: Actual output
            expected: Expected string
            case_sensitive: Case sensitivity flag

        Returns:
            True if exact match
        """
        if not case_sensitive:
            output = output.lower()
            expected = str(expected).lower()

        result = output == expected
        logger.debug(f"Exact validation: {result} ({output!r} == {expected!r})")
        return result

    def _validate_contains(self, output: str, expected: str, case_sensitive: bool = False) -> bool:
        """
        Validate that output contains expected string.

        Args:
            output: Actual output
            expected: Expected substring
            case_sensitive: Case sensitivity flag

        Returns:
            True if output contains expected
        """
        if not case_sensitive:
            output = output.lower()
            expected = str(expected).lower()

        result = expected in output
        logger.debug(f"Contains validation: {result} ({expected!r} in {output!r})")
        return result

    def _validate_numeric(self, output: str, expected: Union[int, float]) -> bool:
        """
        Validate that output contains expected number.

        Args:
            output: Actual output
            expected: Expected number

        Returns:
            True if number found and matches
        """
        # Extract all numbers from output
        numbers = re.findall(r"-?\d+\.?\d*", output)

        if not numbers:
            logger.debug("Numeric validation: No numbers found")
            return False

        # Convert to float
        numbers_float = [float(n) for n in numbers]

        # Check if expected number is present
        result = any(abs(n - float(expected)) < 0.001 for n in numbers_float)

        logger.debug(f"Numeric validation: {result} ({expected} in {numbers_float})")
        return result

    def _validate_pattern(self, output: str, pattern: str) -> bool:
        """
        Validate output against regex pattern.

        Args:
            output: Actual output
            pattern: Regex pattern

        Returns:
            True if pattern matches
        """
        try:
            result = bool(re.search(pattern, output))
            logger.debug(f"Pattern validation: {result} ({pattern} matches)")
            return result
        except re.error as e:
            logger.warning(f"Invalid regex pattern: {e}")
            return False

    def _validate_callable(self, output: str, validate_func: Callable) -> bool:
        """
        Validate using custom callable function.

        Args:
            output: Actual output
            validate_func: Validation function

        Returns:
            True if function returns True
        """
        try:
            result = bool(validate_func(output))
            logger.debug(f"Callable validation: {result}")
            return result
        except Exception as e:
            logger.warning(f"Validation function error: {e}")
            return False

    def validate_multiple(self, output: str, validations: list[dict]) -> tuple[bool, list[dict]]:
        """
        Validate output against multiple criteria.

        Args:
            output: Actual output
            validations: List of validation dicts with 'expected', 'mode', etc.

        Returns:
            Tuple of (all_passed, results_list)
        """
        results = []

        for validation in validations:
            passed = self.validate(
                output=output,
                expected=validation.get("expected"),
                mode=validation.get("mode", "contains"),
                case_sensitive=validation.get("case_sensitive", False),
            )

            results.append(
                {
                    "validation": validation,
                    "passed": passed,
                }
            )

        all_passed = all(r["passed"] for r in results)
        logger.info(f"Multiple validation: {all_passed} ({len(results)} checks)")

        return all_passed, results

    def validate_score(self, output: str, validations: list[dict]) -> dict:
        """
        Validate output and calculate success score.

        Args:
            output: Actual output
            validations: List of validation dicts

        Returns:
            Dict with score and details
        """
        results = []

        for validation in validations:
            passed = self.validate(
                output=output,
                expected=validation.get("expected"),
                mode=validation.get("mode", "contains"),
                case_sensitive=validation.get("case_sensitive", False),
            )

            results.append(
                {
                    "validation": validation,
                    "passed": passed,
                    "weight": validation.get("weight", 1.0),
                }
            )

        # Calculate weighted score
        total_weight = sum(r["weight"] for r in results)
        passed_weight = sum(r["weight"] for r in results if r["passed"])
        score = (passed_weight / total_weight * 100) if total_weight > 0 else 0

        logger.info(f"Validation score: {score:.1f}% ({passed_weight}/{total_weight})")

        return {
            "score": score,
            "total_validations": len(results),
            "passed_validations": sum(1 for r in results if r["passed"]),
            "results": results,
        }
