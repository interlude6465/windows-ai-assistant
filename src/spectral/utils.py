"""
Utility functions for Spectral.
"""

import ast
import logging
import re
from typing import List, Tuple

AUTONOMOUS_CODE_REQUIREMENT = """
⚠️ CRITICAL: Generate FULLY AUTONOMOUS code with NO interactive input() calls.

The code will be executed in a non-interactive environment with NO stdin available.
If the code calls input(), it will FAIL immediately.

✅ REQUIRED:
1. Hard-code ALL input values (numbers, strings, file paths, choices)
2. NEVER use input() or similar interactive functions
3. For programs needing parameters, embed them directly in the code
4. The program must execute and produce output without waiting

❌ FORBIDDEN:
- input()
- input("prompt")
- sys.stdin.read()
- Any other interactive input mechanism

Examples of WRONG vs RIGHT:

❌ WRONG (Will fail):
```python
name = input("Enter name: ")
print(f"Hello {name}")
```

✅ RIGHT (Will work):
```python
name = "John"  # Hard-coded
print(f"Hello {name}")
```

❌ WRONG (Interactive):
```python
def calculator():
    num1 = input("First number: ")
    num2 = input("Second number: ")
    print(int(num1) + int(num2))
calculator()
```

✅ RIGHT (Autonomous):
```python
def calculator():
    num1 = 42
    num2 = 8
    result = num1 + num2
    print(f"{num1} + {num2} = {result}")
calculator()
```

❌ WRONG (Asks for choice):
```python
import random
choices = ['rock', 'paper', 'scissors']
player = input("Choose: ")
computer = random.choice(choices)
# ...game logic...
```

✅ RIGHT (Hard-coded choice):
```python
import random
choices = ['rock', 'paper', 'scissors']
player = 'rock'  # Hard-coded
computer = random.choice(choices)
# ...game logic...
```

Now generate the code:
"""


class SmartInputHandler:
    """Intelligently detects and handles input() calls in programs."""

    def detect_and_inject_inputs(self, code: str) -> tuple[str, List[str]]:
        """
        Analyzes code for input() calls and returns auto-generated test inputs.

        Returns:
            (modified_code, test_inputs) - code with input() calls stubbed, and test values
        """
        import re

        # Find all input() calls and their prompts
        input_pattern = r'(\w+)\s*=\s*input\s*\(\s*["\']([^"\']*)["\']'
        matches = list(re.finditer(input_pattern, code))

        if not matches:
            return code, []

        test_inputs = []

        # Analyze each input() call
        for match in matches:
            var_name = match.group(1)
            prompt = match.group(2).lower()

            # Intelligently map prompts to test values
            test_value = self._generate_smart_input(prompt, var_name)
            test_inputs.append(test_value)

        return code, test_inputs

    def _generate_smart_input(self, prompt: str, var_name: str = "") -> str:
        """Generate appropriate test input based on prompt content."""

        prompt_lower = prompt.lower()

        # Numbers
        if any(
            word in prompt_lower for word in ["number", "count", "amount", "length", "size", "age"]
        ):
            return "42"

        # Choices
        if any(
            word in prompt_lower
            for word in ["choice", "option", "select", "choose", "rock paper scissors"]
        ):
            if "rock" in prompt_lower:
                return "rock"
            elif "yes" in prompt_lower or "no" in prompt_lower:
                return "yes"
            else:
                return "option1"

        # Files
        if any(word in prompt_lower for word in ["file", "path", "filename", "csv", "txt"]):
            if "csv" in prompt_lower:
                return "data.csv"
            else:
                return "test.txt"

        # Names/Text
        if any(word in prompt_lower for word in ["name", "text", "input", "string", "message"]):
            if "email" in prompt_lower:
                return "test@example.com"
            elif "password" in prompt_lower:
                return "TestPassword123"
            else:
                return "TestUser"

        # Operators
        if any(word in prompt_lower for word in ["operator", "+", "-", "*", "/"]):
            return "+"

        # Default
        return "test"

    def inject_test_inputs(self, code: str, test_inputs: List[str]) -> str:
        """Inject test inputs into code by replacing input() calls."""
        import re

        modified_code = code

        for test_input in test_inputs:
            # Replace first input() call with hard-coded value
            pattern = r"(\w+)\s*=\s*input\s*\([^)]*\)"
            replacement = f'\\1 = "{test_input}"'
            modified_code = re.sub(pattern, replacement, modified_code, count=1)

        return modified_code


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


def extract_input_calls(code: str) -> List[ast.Call]:
    """
    Extract all input() calls from code using AST parsing.

    Args:
        code: Python source code

    Returns:
        List of input Call nodes with their line numbers
    """
    input_calls: List[ast.Call] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return input_calls

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "input":
                input_calls.append(node)

    return input_calls


def detect_input_calls(code: str) -> Tuple[int, List[str]]:
    """
    Detect input() calls in code and extract their prompts.

    Args:
        code: Python source code

    Returns:
        Tuple of (count of input calls, list of prompts)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0, []

    input_count = 0
    prompts = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "input":
                input_count += 1
                # Extract prompt if present
                prompt = ""
                if node.args and isinstance(node.args[0], ast.Constant):
                    prompt = str(node.args[0].value)
                elif node.args and isinstance(node.args[0], ast.Str):  # Python 3.7/3.8
                    prompt = str(node.args[0].s)
                prompts.append(prompt)

    return input_count, prompts


def generate_test_inputs(prompts: List[str]) -> List[str]:
    """
    Generate test inputs based on prompt context.

    Args:
        prompts: List of prompt strings from input() calls

    Returns:
        List of test input values
    """
    test_inputs = []

    for i, prompt in enumerate(prompts):
        prompt_lower = prompt.lower()

        # Pattern matching for common input types
        # IMPORTANT: Check more specific patterns before general ones
        if any(name in prompt_lower for name in ["name", "user", "username", "who"]):
            test_inputs.append("TestUser")
        elif any(word in prompt_lower for word in ["age", "years", "old"]):
            test_inputs.append("25")
        elif any(word in prompt_lower for word in ["first", "num1", "value1"]):
            test_inputs.append("10")
        elif any(word in prompt_lower for word in ["second", "num2", "value2"]):
            test_inputs.append("20")
        elif any(
            word in prompt_lower
            for word in ["number", "num", "count", "quantity", "length", "size"]
        ):
            test_inputs.append("42")
        elif any(word in prompt_lower for word in ["email", "address"]):
            test_inputs.append("test@example.com")
        elif any(word in prompt_lower for word in ["phone", "tel"]):
            test_inputs.append("555-1234")
        elif any(word in prompt_lower for word in ["city", "location", "where"]):
            test_inputs.append("New York")
        elif any(word in prompt_lower for word in ["country", "nation"]):
            test_inputs.append("USA")
        elif any(word in prompt_lower for word in ["date", "when"]):
            test_inputs.append("2024-01-15")
        elif any(word in prompt_lower for word in ["price", "cost", "amount"]):
            test_inputs.append("99.99")
        elif any(word in prompt_lower for word in ["yes", "confirm", "ok"]):
            test_inputs.append("y")
        elif any(word in prompt_lower for word in ["no", "cancel"]):
            test_inputs.append("n")
        elif any(word in prompt_lower for word in ["choice", "select", "option"]):
            test_inputs.append("1")
        elif any(word in prompt_lower for word in ["color", "colour"]):
            test_inputs.append("blue")
        elif any(word in prompt_lower for word in ["food", "eat"]):
            test_inputs.append("pizza")
        elif any(word in prompt_lower for word in ["animal", "pet"]):
            test_inputs.append("dog")
        elif any(word in prompt_lower for word in ["movie", "film"]):
            test_inputs.append("action")
        elif any(word in prompt_lower for word in ["music", "song"]):
            test_inputs.append("rock")
        elif any(word in prompt_lower for word in ["sport", "game"]):
            test_inputs.append("football")
        elif any(word in prompt_lower for word in ["hobby", "interest"]):
            test_inputs.append("reading")
        else:
            # Generic test input based on position
            ordinal = ["first", "second", "third", "fourth", "fifth"][min(i, 4)]
            test_inputs.append(f"test_{ordinal}_value")

    return test_inputs


def has_input_calls(code: str) -> bool:
    """
    Check if code contains any input() calls.

    Args:
        code: Python source code

    Returns:
        True if code contains input() calls
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name == "input":
                return True

    return False
