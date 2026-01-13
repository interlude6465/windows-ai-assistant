"""
Interactive program analyzer module for program type detection.

Analyzes code to detect if it's interactive and determines program type
(calculator, game, quiz, utility, chat, etc.).
"""

import ast
import logging
import re
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class ProgramType(Enum):
    """Types of interactive programs."""

    CALCULATOR = "calculator"
    GAME = "game"
    QUIZ = "quiz"
    UTILITY = "utility"
    CHAT = "chat"
    FORM = "form"
    MENU = "menu"
    UNKNOWN = "unknown"


class InteractiveProgramAnalyzer:
    """
    Analyzes code to detect program type and input requirements.

    Detects:
    - Program type (calculator, game, quiz, etc.)
    - Input patterns
    - Expected input types
    - Interaction complexity
    """

    def __init__(self) -> None:
        """Initialize interactive program analyzer."""
        self.input_patterns = {
            "input": r"input\s*\(",
            "raw_input": r"raw_input\s*\(",
            "stdin": r"sys\.stdin",
        }
        logger.info("InteractiveProgramAnalyzer initialized")

    def is_interactive(self, code: str) -> bool:
        """
        Check if code contains interactive input calls.

        Args:
            code: Python source code

        Returns:
            True if code is interactive, False otherwise
        """
        # Check for input(), raw_input(), or sys.stdin
        for pattern_name, pattern in self.input_patterns.items():
            if re.search(pattern, code):
                logger.debug(f"Found interactive pattern: {pattern_name}")
                return True

        # Check AST for Input nodes
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ["input", "raw_input"]:
                        return True
                    if isinstance(node.func, ast.Attribute):
                        if hasattr(node.func, "attr") and node.func.attr == "readline":
                            # Check if it's sys.stdin.readline()
                            if isinstance(node.func.value, ast.Attribute):
                                if node.func.value.attr == "stdin":
                                    return True
        except Exception as e:
            logger.debug(f"AST parsing failed: {e}")

        return False

    def detect_program_type(self, code: str, description: str = "") -> ProgramType:
        """
        Detect the type of interactive program.

        Args:
            code: Python source code
            description: Optional description of what the program does

        Returns:
            Detected ProgramType
        """
        code_lower = code.lower()
        desc_lower = description.lower()

        # Check for calculator keywords
        calc_keywords = [
            "calculator",
            "add",
            "subtract",
            "multiply",
            "divide",
            "+",
            "-",
            "*",
            "/",
            "operation",
            "operator",
            "number1",
            "number2",
            "num1",
            "num2",
        ]
        if any(kw in code_lower or kw in desc_lower for kw in calc_keywords):
            logger.debug("Detected program type: CALCULATOR")
            return ProgramType.CALCULATOR

        # Check for game keywords
        game_keywords = [
            "guess",
            "game",
            "higher",
            "lower",
            "number",
            "secret",
            "score",
            "player",
            "computer",
            "random",
            "play again",
        ]
        if any(kw in code_lower or kw in desc_lower for kw in game_keywords):
            logger.debug("Detected program type: GAME")
            return ProgramType.GAME

        # Check for quiz keywords
        quiz_keywords = [
            "quiz",
            "question",
            "answer",
            "correct",
            "incorrect",
            "score",
            "true",
            "false",
            "multiple choice",
        ]
        if any(kw in code_lower or kw in desc_lower for kw in quiz_keywords):
            logger.debug("Detected program type: QUIZ")
            return ProgramType.QUIZ

        # Check for chat keywords
        chat_keywords = [
            "chat",
            "message",
            "conversation",
            "bot",
            "assistant",
            "hello",
            "goodbye",
            "respond",
        ]
        if any(kw in code_lower or kw in desc_lower for kw in chat_keywords):
            logger.debug("Detected program type: CHAT")
            return ProgramType.CHAT

        # Check for menu keywords
        menu_keywords = [
            "menu",
            "option",
            "select",
            "choose",
            "1.",
            "2.",
            "3.",
            "enter choice",
            "press 1",
            "press 2",
        ]
        if any(kw in code_lower or kw in desc_lower for kw in menu_keywords):
            logger.debug("Detected program type: MENU")
            return ProgramType.MENU

        # Check for form keywords
        form_keywords = [
            "name",
            "email",
            "address",
            "phone",
            "form",
            "register",
            "sign up",
            "enter your",
        ]
        if any(kw in code_lower or kw in desc_lower for kw in form_keywords):
            logger.debug("Detected program type: FORM")
            return ProgramType.FORM

        # Default to utility if interactive
        if self.is_interactive(code):
            logger.debug("Detected program type: UTILITY")
            return ProgramType.UTILITY

        logger.debug("Detected program type: UNKNOWN")
        return ProgramType.UNKNOWN

    def extract_input_prompts(self, code: str) -> List[str]:
        """
        Extract input prompts from code.

        Args:
            code: Python source code

        Returns:
            List of prompt strings found
        """
        prompts = []

        # Look for input("prompt") patterns
        input_pattern = r'input\s*\(\s*["\']([^"\']*)["\']\s*\)'
        matches = re.findall(input_pattern, code)
        prompts.extend(matches)

        # Look for f-strings in input()
        fstring_pattern = r'input\s*\(\s*f["\']([^"\']*)["\']\s*\)'
        matches = re.findall(fstring_pattern, code)
        prompts.extend(matches)

        logger.debug(f"Found {len(prompts)} input prompts")
        return prompts

    def classify_input_types(self, code: str) -> List[str]:
        """
        Classify expected input types based on code context.

        Args:
            code: Python source code

        Returns:
            List of input type strings (int, float, str, etc.)
        """
        input_types = []

        # Check for int() after input
        if re.search(r"int\s*\(\s*input\s*\(", code):
            input_types.append("int")

        # Check for float() after input
        if re.search(r"float\s*\(\s*input\s*\(", code):
            input_types.append("float")

        # Check for str() or no conversion
        if re.search(r"str\s*\(\s*input\s*\(", code) or not input_types:
            input_types.append("str")

        logger.debug(f"Detected input types: {input_types}")
        return input_types

    def estimate_interaction_complexity(self, code: str) -> str:
        """
        Estimate how complex the interaction is.

        Args:
            code: Python source code

        Returns:
            Complexity level: "simple", "moderate", "complex"
        """
        input_count = len(re.findall(r"input\s*\(", code))
        if_count = len(re.findall(r"\bif\s+", code))
        loop_count = len(re.findall(r"\b(for|while)\s+", code))
        function_count = len(re.findall(r"def\s+\w+\s*\(", code))

        # Calculate complexity score
        complexity_score = input_count * 1 + if_count * 0.5 + loop_count * 1 + function_count * 0.5

        if complexity_score < 3:
            return "simple"
        elif complexity_score < 7:
            return "moderate"
        else:
            return "complex"

    def analyze_program(self, code: str, description: str = "") -> dict:
        """
        Perform complete analysis of interactive program.

        Args:
            code: Python source code
            description: Optional program description

        Returns:
            Dictionary with analysis results
        """
        return {
            "is_interactive": self.is_interactive(code),
            "program_type": self.detect_program_type(code, description).value,
            "input_prompts": self.extract_input_prompts(code),
            "input_types": self.classify_input_types(code),
            "complexity": self.estimate_interaction_complexity(code),
            "input_count": len(re.findall(r"input\s*\(", code)),
        }
