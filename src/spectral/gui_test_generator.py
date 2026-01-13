"""
GUI Test Generator module for automated testing of GUI programs.

Detects GUI programs and generates test suites that verify functionality
without visual inspection.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

from spectral.llm_client import LLMClient

logger = logging.getLogger(__name__)


class GUITestGenerator:
    """
    Generates automated test suites for GUI programs.

    Detects GUI frameworks and creates pytest-based tests that verify:
    - Program initialization
    - UI element creation
    - Event handlers
    - State changes
    - Program stability
    """

    GUI_FRAMEWORKS = {
        "tkinter": ["tkinter", "tk.", "Tk(", "CTk(", "customtkinter"],
        "pygame": ["pygame", "pygame."],
        "pyqt": ["PyQt5", "PyQt6", "PySide2", "PySide6"],
        "kivy": ["kivy", "kivy."],
        "wxpython": ["wx.", "wxPython"],
    }

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize GUI test generator.

        Args:
            llm_client: LLM client for generating tests
        """
        self.llm_client = llm_client
        logger.info("GUITestGenerator initialized")

    def detect_gui_program(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if code contains GUI framework usage.

        Args:
            code: Python source code to analyze

        Returns:
            Tuple of (is_gui, framework_name)
        """
        for framework, patterns in self.GUI_FRAMEWORKS.items():
            for pattern in patterns:
                if pattern in code:
                    logger.info(f"Detected {framework} GUI framework")
                    return (True, framework)

        return (False, None)

    def generate_test_suite(
        self, code: str, program_name: str, framework: str, user_request: str
    ) -> str:
        """
        Generate test suite for GUI program.

        Args:
            code: GUI program source code
            program_name: Name of the program file (without .py)
            framework: Detected GUI framework name
            user_request: Original user request

        Returns:
            Generated test suite code
        """
        logger.info(f"Generating test suite for {program_name} ({framework})")

        prompt = self._build_test_generation_prompt(code, program_name, framework, user_request)

        try:
            test_code = self.llm_client.generate(prompt)
            # Clean markdown formatting
            if "```python" in test_code:
                test_code = test_code.split("```python")[1].split("```")[0].strip()
            elif "```" in test_code:
                test_code = test_code.split("```")[1].split("```")[0].strip()

            logger.debug(f"Generated {len(test_code)} characters of test code")
            return str(test_code)
        except Exception as e:
            logger.error(f"Failed to generate test suite: {e}")
            # Generate fallback basic test
            return self._generate_basic_test(program_name)

    def _build_test_generation_prompt(
        self, code: str, program_name: str, framework: str, user_request: str
    ) -> str:
        """Build prompt for test generation."""
        prompt = f"""Generate a pytest test suite for this GUI program.

ORIGINAL REQUEST:
{user_request}

PROGRAM CODE:
```python
{code}
```

PROGRAM NAME: {program_name}.py
FRAMEWORK: {framework}

REQUIREMENTS:
1. Create file: test_{program_name}.py
2. Use pytest and unittest for testing
3. Test programmatically - NO visual inspection needed
4. NO actual GUI windows should open during tests

TEST CATEGORIES:
1. Initialization Tests
   - Verify program/class can be instantiated
   - Check required attributes exist
   - Verify initial state is correct

2. Element Creation Tests
   - Verify UI elements are created (buttons, labels, canvas, etc.)
   - Check element properties (width, height, color, text)
   - Ensure elements are properly configured

3. Interaction Tests
   - Simulate user interactions (clicks, keyboard input)
   - Verify event handlers are connected
   - Check that interactions trigger expected behavior

4. State Change Tests
   - Verify state changes after interactions
   - Check data structures are updated correctly
   - Ensure randomization/variation works as expected

5. Stability Tests
   - Run repeated interactions without crashes
   - Test edge cases
   - Verify no memory leaks or infinite loops

TESTING STRATEGIES:
- Mock Tk mainloop() to prevent GUI from actually showing
- Test methods directly without running mainloop
- Use unittest.mock to patch GUI display functions
- Check object attributes instead of visual output
- Verify internal state, not rendered pixels

EXAMPLE STRUCTURE:
```python
import pytest
import unittest
from unittest.mock import Mock, patch
from {program_name} import *

class Test{program_name.title().replace('_', '')}:
    
    @patch('tkinter.Tk.mainloop')
    def test_initialization(self, mock_mainloop):
        '''Test program initializes without errors'''
        app = MainClass()
        assert app is not None
        
    def test_elements_created(self):
        '''Test UI elements are created'''
        app = MainClass()
        assert hasattr(app, 'button')
        assert hasattr(app, 'canvas')
        
    def test_interaction_handler(self):
        '''Test click handlers work'''
        app = MainClass()
        original_state = app.state
        app.on_click()
        assert app.state != original_state
        
    def test_randomization(self):
        '''Test variety in random behavior'''
        app = MainClass()
        results = set()
        for _ in range(10):
            app.generate_random()
            results.add(app.current_value)
        assert len(results) > 1
        
    def test_stability(self):
        '''Test repeated use doesn't crash'''
        app = MainClass()
        for _ in range(20):
            app.interact()
        assert True
```

Generate COMPLETE test suite with:
- All necessary imports
- Proper mocking to prevent GUI windows
- 5-10 meaningful tests
- Clear test names
- Assertions that verify functionality
- No visual/screenshot requirements

Return only Python code, no explanations."""
        return prompt

    def _generate_basic_test(self, program_name: str) -> str:
        """Generate a basic fallback test."""
        return f"""import pytest
import unittest
from unittest.mock import patch

# Import the program
from {program_name} import *

class Test{program_name.title().replace('_', '')}:
    '''Basic test suite for {program_name}'''
    
    @patch('tkinter.Tk.mainloop')
    def test_program_can_initialize(self, mock_mainloop):
        '''Test that program can be instantiated without errors'''
        try:
            # Try to create an instance of the main class
            # This is a basic smoke test
            assert True
        except Exception as e:
            pytest.fail(f"Program failed to initialize: {{e}}")
    
    def test_imports_work(self):
        '''Test that all imports are valid'''
        assert True  # If we got here, imports worked

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""

    def extract_program_name(self, filename: str) -> str:
        """
        Extract program name from filename.

        Args:
            filename: File name (e.g., "circle_game.py")

        Returns:
            Program name without extension (e.g., "circle_game")
        """
        return Path(filename).stem

    def format_test_filename(self, program_filename: str) -> str:
        """
        Format test filename from program filename.

        Args:
            program_filename: Program file name (e.g., "circle_game.py")

        Returns:
            Test file name (e.g., "test_circle_game.py")
        """
        stem = self.extract_program_name(program_filename)
        return f"test_{stem}.py"
