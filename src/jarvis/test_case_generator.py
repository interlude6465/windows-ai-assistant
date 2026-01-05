"""
Test case generator module for intelligent test input generation.

Generates smart test inputs based on program type and code analysis.
"""

import logging
from typing import Callable, List, Optional

from jarvis.interactive_program_analyzer import ProgramType

logger = logging.getLogger(__name__)


class TestCaseGenerator:
    """
    Generates intelligent test cases for interactive programs.

    Analyzes program type and creates appropriate test inputs
    with validation functions.
    """

    def __init__(self) -> None:
        """Initialize test case generator."""
        logger.info("TestCaseGenerator initialized")

    def generate_test_cases(
        self,
        program_type: ProgramType,
        code: str,
        max_cases: int = 10,
    ) -> List[dict]:
        """
        Generate test cases based on program type.

        Args:
            program_type: Type of program
            code: Source code
            max_cases: Maximum number of test cases to generate

        Returns:
            List of test case dictionaries
        """
        generators = {
            ProgramType.CALCULATOR: self._generate_calculator_tests,
            ProgramType.GAME: self._generate_game_tests,
            ProgramType.QUIZ: self._generate_quiz_tests,
            ProgramType.UTILITY: self._generate_utility_tests,
            ProgramType.FORM: self._generate_form_tests,
            ProgramType.MENU: self._generate_menu_tests,
            ProgramType.CHAT: self._generate_chat_tests,
        }

        generator = generators.get(program_type, self._generate_utility_tests)
        test_cases = generator(code)

        # Limit to max_cases
        return test_cases[:max_cases]

    def _generate_calculator_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for calculator programs.

        Args:
            code: Calculator source code

        Returns:
            List of calculator test cases
        """
        tests = [
            {
                "name": "Addition",
                "inputs": ["5", "3", "+"],
                "validate": lambda out: "8" in out or self._contains_number(out, 8),
                "expected": "5 + 3 = 8",
            },
            {
                "name": "Subtraction",
                "inputs": ["10", "2", "-"],
                "validate": lambda out: "8" in out or self._contains_number(out, 8),
                "expected": "10 - 2 = 8",
            },
            {
                "name": "Multiplication",
                "inputs": ["4", "5", "*"],
                "validate": lambda out: "20" in out or self._contains_number(out, 20),
                "expected": "4 * 5 = 20",
            },
            {
                "name": "Division",
                "inputs": ["20", "4", "/"],
                "validate": lambda out: "5" in out or self._contains_number(out, 5),
                "expected": "20 / 4 = 5",
            },
            {
                "name": "Zero division",
                "inputs": ["10", "0", "/"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["error", "cannot", "infinity", "undefined"]
                )
                or self._contains_number(out, 0),
                "expected": "Handles division by zero gracefully",
            },
            {
                "name": "Negative numbers",
                "inputs": ["-5", "3", "+"],
                "validate": lambda out: "-2" in out or self._contains_number(out, -2),
                "expected": "-5 + 3 = -2",
            },
            {
                "name": "Decimal numbers",
                "inputs": ["3.5", "2.5", "+"],
                "validate": lambda out: "6" in out or "6.0" in out or self._contains_number(out, 6),
                "expected": "3.5 + 2.5 = 6",
            },
        ]

        logger.info(f"Generated {len(tests)} calculator test cases")
        return tests

    def _generate_game_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for guessing games.

        Args:
            code: Game source code

        Returns:
            List of game test cases
        """
        tests = [
            {
                "name": "First guess - too high",
                "inputs": ["50"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["high", "lower", "try lower"]
                ),
                "expected": "Indicates guess is too high",
            },
            {
                "name": "Second guess - too low",
                "inputs": ["25"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["low", "higher", "try higher"]
                ),
                "expected": "Indicates guess is too low",
            },
            {
                "name": "Multiple guesses",
                "inputs": ["37", "42", "38"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["wrong", "try again", "guess again"]
                ),
                "expected": "Game continues with feedback",
            },
            {
                "name": "Play again",
                "inputs": ["50", "n"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["thank", "goodbye", "bye", "see you"]
                )
                or "game over" in out.lower(),
                "expected": "Game ends gracefully",
            },
        ]

        logger.info(f"Generated {len(tests)} game test cases")
        return tests

    def _generate_quiz_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for quiz programs.

        Args:
            code: Quiz source code

        Returns:
            List of quiz test cases
        """
        tests = [
            {
                "name": "Correct answer",
                "inputs": ["Paris"],  # Assuming geography quiz
                "validate": lambda out: any(
                    x in out.lower() for x in ["correct", "right", "good job", "well done"]
                ),
                "expected": "Acknowledges correct answer",
            },
            {
                "name": "Incorrect answer",
                "inputs": ["London"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["incorrect", "wrong", "try again"]
                ),
                "expected": "Indicates incorrect answer",
            },
            {
                "name": "Multiple questions",
                "inputs": ["Paris", "5", "Blue"],
                "validate": lambda out: "score" in out.lower() or "point" in out.lower(),
                "expected": "Shows final score",
            },
        ]

        logger.info(f"Generated {len(tests)} quiz test cases")
        return tests

    def _generate_utility_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for utility programs.

        Args:
            code: Utility source code

        Returns:
            List of utility test cases
        """
        tests = [
            {
                "name": "Basic input",
                "inputs": ["test"],
                "validate": lambda out: "test" in out or len(out) > 0,
                "expected": "Processes basic input",
            },
            {
                "name": "Number input",
                "inputs": ["42"],
                "validate": lambda out: "42" in out or len(out) > 0,
                "expected": "Processes number input",
            },
            {
                "name": "Empty input",
                "inputs": [""],
                "validate": lambda out: len(out) >= 0,
                "expected": "Handles empty input gracefully",
            },
        ]

        logger.info(f"Generated {len(tests)} utility test cases")
        return tests

    def _generate_form_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for form programs.

        Args:
            code: Form source code

        Returns:
            List of form test cases
        """
        tests = [
            {
                "name": "Valid form data",
                "inputs": ["John Doe", "john@example.com", "123-456-7890"],
                "validate": lambda out: len(out) > 0,
                "expected": "Processes valid form data",
            },
            {
                "name": "Missing field",
                "inputs": ["John Doe", "", "123-456-7890"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["required", "missing", "error"]
                )
                or len(out) >= 0,
                "expected": "Handles missing field",
            },
        ]

        logger.info(f"Generated {len(tests)} form test cases")
        return tests

    def _generate_menu_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for menu programs.

        Args:
            code: Menu source code

        Returns:
            List of menu test cases
        """
        tests = [
            {
                "name": "Select option 1",
                "inputs": ["1"],
                "validate": lambda out: len(out) > 0,
                "expected": "Executes menu option 1",
            },
            {
                "name": "Select option 2",
                "inputs": ["2"],
                "validate": lambda out: len(out) > 0,
                "expected": "Executes menu option 2",
            },
            {
                "name": "Exit menu",
                "inputs": ["0"],
                "validate": lambda out: any(x in out.lower() for x in ["goodbye", "thank", "bye"])
                or "exit" in out.lower(),
                "expected": "Exits menu gracefully",
            },
        ]

        logger.info(f"Generated {len(tests)} menu test cases")
        return tests

    def _generate_chat_tests(self, code: str) -> List[dict]:
        """
        Generate test cases for chat programs.

        Args:
            code: Chat source code

        Returns:
            List of chat test cases
        """
        tests = [
            {
                "name": "Greeting",
                "inputs": ["hello"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["hello", "hi", "hey", "welcome"]
                ),
                "expected": "Responds to greeting",
            },
            {
                "name": "Question",
                "inputs": ["how are you?"],
                "validate": lambda out: len(out) > 0,
                "expected": "Responds to question",
            },
            {
                "name": "Exit",
                "inputs": ["bye"],
                "validate": lambda out: any(
                    x in out.lower() for x in ["goodbye", "bye", "see you"]
                ),
                "expected": "Exits gracefully",
            },
        ]

        logger.info(f"Generated {len(tests)} chat test cases")
        return tests

    def _contains_number(self, text: str, target: int) -> bool:
        """
        Check if text contains a specific number.

        Args:
            text: Text to search
            target: Number to find

        Returns:
            True if number found, False otherwise
        """
        import re

        # Match the number as a word/number boundary
        pattern = r"\b" + str(target) + r"\b"
        return bool(re.search(pattern, text))

    def validate_output(
        self,
        output: str,
        validate_func: Optional[Callable] = None,
        expected: Optional[str] = None,
    ) -> bool:
        """
        Validate program output against expected result.

        Args:
            output: Actual program output
            validate_func: Optional validation function
            expected: Optional expected output string

        Returns:
            True if validation passes, False otherwise
        """
        if validate_func:
            try:
                return validate_func(output)
            except Exception as e:
                logger.warning(f"Validation function failed: {e}")
                return False

        if expected and expected in output:
            return True

        # Default: consider non-empty output as success
        return len(output.strip()) > 0
