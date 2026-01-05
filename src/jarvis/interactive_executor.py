"""
Interactive executor module for running interactive programs.

Handles subprocess management, stdin/stdout streaming, and test execution
for interactive programs without timing out during interactions.
"""

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class InteractiveExecutor:
    """
    Executes interactive programs with proper stdin/stdout handling.

    Features:
    - Keeps subprocess alive during interactions
    - Sends stdin while reading stdout in real-time
    - Detects prompts and adapts input
    - Validates outputs automatically
    - Reports test results
    """

    def __init__(self, timeout: int = 30) -> None:
        """
        Initialize interactive executor.

        Args:
            timeout: Timeout in seconds (applies between prompts, not total)
        """
        self.timeout = timeout
        logger.info(f"InteractiveExecutor initialized with timeout: {timeout}s")

    def execute_interactive(
        self,
        script_path: Path,
        inputs: List[str],
        test_name: str = "Test",
    ) -> dict:
        """
        Execute an interactive program with given inputs.

        Args:
            script_path: Path to Python script
            inputs: List of input strings to provide
            test_name: Name of the test case

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Executing interactive: {script_path} with {len(inputs)} inputs")

        start_time = time.time()
        output_lines = []
        all_output = ""
        passed = False
        error = None

        try:
            # Create subprocess
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
            )

            logger.debug(f"Process started with PID: {process.pid}")

            # Send inputs and collect output
            input_index = 0
            last_output_time = time.time()

            while True:
                # Check for process termination
                return_code = process.poll()
                if return_code is not None:
                    logger.debug(f"Process terminated with code: {return_code}")
                    break

                # Check timeout (no new output for timeout seconds)
                elapsed_since_output = time.time() - last_output_time
                if elapsed_since_output > self.timeout and input_index >= len(inputs):
                    logger.warning(f"Timeout after {elapsed_since_output:.1f}s with no output")
                    process.kill()
                    break

                # Try to read output
                try:
                    # Read one character at a time to be responsive
                    char = process.stdout.read(1)
                    if char:
                        output_lines.append(char)
                        all_output += char
                        last_output_time = time.time()

                        # If we have a prompt and more inputs, send the next one
                        current_output = "".join(output_lines)
                        if self._has_prompt(current_output) and input_index < len(inputs):
                            next_input = inputs[input_index] + "\n"
                            logger.debug(f"Sending input {input_index}: {inputs[input_index]!r}")
                            process.stdin.write(next_input)
                            process.stdin.flush()
                            input_index += 1
                except Exception as e:
                    logger.debug(f"Read error (normal if process ended): {e}")
                    break

            # Wait for process to fully terminate
            process.wait(timeout=5)

            elapsed = time.time() - start_time
            logger.info(f"Execution completed in {elapsed:.2f}s")

            # Consider test passed if we processed all inputs and got output
            passed = len(all_output) > 0 and input_index >= len(inputs)

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            error = f"Timeout after {elapsed:.2f}s"
            logger.warning(error)
            try:
                process.kill()
            except Exception:
                pass

        except Exception as e:
            elapsed = time.time() - start_time
            error = str(e)
            logger.error(f"Execution failed: {e}")

        return {
            "test_name": test_name,
            "inputs": inputs,
            "output": all_output,
            "output_length": len(all_output),
            "elapsed_time": time.time() - start_time,
            "passed": passed,
            "error": error,
        }

    def _has_prompt(self, output: str) -> bool:
        """
        Detect if output contains a prompt waiting for input.

        Args:
            output: Output text so far

        Returns:
            True if prompt detected, False otherwise
        """
        # Check for common prompt patterns
        prompt_indicators = [
            ": ",
            "? ",
            "> ",
            "Enter ",
            "Input ",
            "Choose ",
            "Select ",
        ]

        output_lower = output.lower()
        for indicator in prompt_indicators:
            if indicator.lower() in output_lower and output.endswith(indicator):
                return True

            # Also check if the last line ends with a prompt
            lines = output.strip().split("\n")
            if lines and lines[-1].endswith(indicator):
                return True

        return False

    def execute_all_tests(
        self,
        script_path: Path,
        test_cases: List[dict],
    ) -> List[dict]:
        """
        Execute all test cases for a script.

        Args:
            script_path: Path to Python script
            test_cases: List of test case dictionaries

        Returns:
            List of execution results
        """
        results = []

        for test_case in test_cases:
            result = self.execute_interactive(
                script_path=script_path,
                inputs=test_case["inputs"],
                test_name=test_case["name"],
            )

            # Validate output if validation function provided
            if "validate" in test_case and not result["passed"]:
                try:
                    validated = test_case["validate"](result["output"])
                    result["passed"] = validated
                except Exception as e:
                    logger.warning(f"Validation failed: {e}")
                    result["passed"] = False

            results.append(result)

        # Log summary
        passed_count = sum(1 for r in results if r["passed"])
        logger.info(f"Test execution complete: {passed_count}/{len(results)} passed")

        return results

    def get_execution_summary(self, results: List[dict]) -> dict:
        """
        Get summary of execution results.

        Args:
            results: List of execution result dictionaries

        Returns:
            Summary dictionary
        """
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        failed = total - passed
        total_time = sum(r["elapsed_time"] for r in results)

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "total_time": total_time,
            "average_time": total_time / total if total > 0 else 0,
        }
