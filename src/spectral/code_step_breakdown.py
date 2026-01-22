"""
Code step breakdown module for complex requests.

Parses complex code requirements into logical CodeStep objects with
dependencies and validation methods.
"""

import json
import logging
import re
from typing import List, Optional

from spectral.execution_models import CodeStep
from spectral.llm_client import LLMClient

logger = logging.getLogger(__name__)


class CodeStepBreakdown:
    """
    Breaks down complex code requests into logical CodeStep objects.

    Example:
    Input: "Build a web scraper that downloads images, handles errors, and logs progress"
    Output: List of CodeStep objects with dependencies and validation methods
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize code step breakdown.

        Args:
            llm_client: LLM client for generating step breakdowns
        """
        self.llm_client = llm_client
        self._step_counter = 0
        logger.info("CodeStepBreakdown initialized")

    def breakdown_request(self, user_request: str) -> List[CodeStep]:
        """
        Break down complex request into CodeStep objects.

        Args:
            user_request: User's natural language request

        Returns:
            List of CodeStep objects
        """
        logger.info(f"Breaking down request: {user_request}")

        # Check if request is complex enough to warrant breakdown
        if not self._is_complex_request(user_request):
            logger.info("Request appears simple, returning single step")
            return self._create_simple_step(user_request)

        try:
            # Generate step breakdown using LLM
            breakdown = self._generate_breakdown(user_request)
            steps = self._parse_breakdown(breakdown, user_request)

            # Validate steps
            steps = self._validate_steps(steps)
            logger.info(f"Created {len(steps)} steps")
            return steps
        except Exception as e:
            logger.error(f"Failed to breakdown request: {e}")
            # Fallback to simple step
            return self._create_simple_step(user_request)

    def _is_complex_request(self, user_request: str) -> bool:
        """
        Check if request is complex enough to warrant breakdown.

        Args:
            user_request: User's natural language request

        Returns:
            True if request is complex
        """
        complexity_indicators = [
            "with",
            "and",
            "then",
            "also",
            "including",
            "plus",
            "multi",
            "step",
            "phase",
            "stage",
            "pipeline",
            "workflow",
            "error handling",
            "logging",
            "testing",
            "validation",
            "database",
            "api",
            "web",
            "server",
            "client",
        ]

        input_lower = user_request.lower()
        count = sum(1 for indicator in complexity_indicators if indicator in input_lower)
        word_count = len(user_request.split())

        return count >= 2 or word_count > 10

    def _create_simple_step(self, user_request: str) -> List[CodeStep]:
        """
        Create a single step for simple requests.

        Args:
            user_request: User's natural language request

        Returns:
            List with single CodeStep
        """
        self._step_counter += 1
        return [
            CodeStep(
                step_number=1,
                description=user_request,
                code=None,  # Will be generated later
                is_code_execution=True,
                validation_method="output_pattern",
                timeout_seconds=30,
            )
        ]

    def _generate_breakdown(self, user_request: str) -> str:
        """
        Generate step breakdown using LLM.

        Args:
            user_request: User's natural language request

        Returns:
            LLM response with step breakdown
        """
        prompt = self._build_breakdown_prompt(user_request)
        logger.debug(f"Breakdown prompt length: {len(prompt)} characters")

        try:
            response = str(self.llm_client.generate(prompt))
            logger.debug(f"Breakdown response received: {len(response)} characters")
            return response
        except Exception as e:
            logger.error(f"Failed to generate breakdown: {e}")
            raise

    def _build_breakdown_prompt(self, user_request: str) -> str:
        """Build prompt for step breakdown."""
        prompt = f"""Break down this request into logical code execution steps:

{user_request}

═══════════════════════════════════════════════════════════════════════════════
🎯 STEP PLANNING GUIDELINES
═══════════════════════════════════════════════════════════════════════════════

The user has FULL SYSTEM ACCESS. Plan steps with these capabilities in mind:
- Filesystem access, network operations, subprocess, raw sockets
- Missing packages will be auto-installed
- No sandbox restrictions

Requirements:
1. Create FOCUSED, SUBSTANTIAL steps (maximum 4 steps for complex tasks)
2. Each step should accomplish something meaningful and testable
3. Avoid trivial setup-only steps (like "install package" - that's automatic)
4. Combine related operations into single steps
5. Each step will be executed immediately with full system access
6. Generated code must be COMPLETE, WORKING, and include timeouts

Guidelines for reducing steps:
- Package installation happens automatically - don't create steps for it
- Don't separate "prepare URL" from "fetch data"
- Combine validation into execution steps
- Error handling is part of each step's code, not separate
- Include timeout and exit condition requirements in step descriptions

Step descriptions should emphasize:
- COMPLETE implementation (not partial)
- Proper timeouts (for network, threads, I/O)
- Error handling (try/except blocks)
- No infinite loops (clear exit conditions)
- Hard-coded test values (no input() calls)

═══════════════════════════════════════════════════════════════════════════════
📤 OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

CRITICAL: You MUST respond with VALID JSON only, no additional text.

Format:
{{
  "steps": [
    {{
      "step_number": 1,
      "description": (
        "Clear description of what this step does "
        "(emphasize completeness and timeouts)"
      ),
      "code_needed": true/false,
      "is_code_execution": true/false,
      "validation_method": "output_pattern" | "file_exists" | "syntax_check" | "manual",
      "expected_output_pattern": "regex pattern (if validation_method is output_pattern)",
      "dependencies": [],
      "timeout_seconds": 30,
      "max_retries": null
    }}
  ]
}}

Rules:
- No text before or after JSON
- Use double quotes only (not single quotes)
- No trailing commas
- All strings properly escaped
- Steps should be in logical order
- MAXIMUM 4 steps for complex tasks
- Each step should be substantial (not just "prepare" or "setup")
- Dependencies should reference earlier step numbers only
- Informational steps (prepare, format, reply) should have is_code_execution=false
- Code steps should have is_code_execution=true
- max_retries can be a number or null (null means unlimited retries)
- Keep descriptions clear and actionable
- Example: Web scraper should be 2-3 steps (fetch + process + save), not 7

Return only valid JSON, no other text."""
        return prompt

    def _parse_breakdown(self, breakdown: str, user_request: str) -> List[CodeStep]:
        """
        Parse LLM response into CodeStep objects with robust JSON parsing.

        Args:
            breakdown: LLM response string
            user_request: Original user request

        Returns:
            List of CodeStep objects
        """
        logger.info("Starting robust JSON parsing")
        logger.debug(f"Raw response: {breakdown[:500]}...")

        try:
            # First, try strict JSON parsing
            json_text = self._extract_json_from_response(breakdown)
            logger.debug(f"Extracted JSON text: {json_text[:300]}...")
            data = json.loads(json_text)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Strict JSON parsing failed: {e}")

            # Try to fix common JSON issues and parse again
            try:
                fixed_json = self._fix_common_json_issues(breakdown)
                logger.debug(f"Fixed JSON: {fixed_json[:300]}...")
                data = json.loads(fixed_json)
            except (json.JSONDecodeError, ValueError) as e2:
                logger.warning(f"Fixed JSON parsing also failed: {e2}")

                # Final fallback: extract steps using regex
                logger.warning("Falling back to regex-based step extraction")
                return self._extract_steps_with_regex(breakdown, user_request)

        steps_data = data.get("steps", [])
        if not steps_data:
            logger.warning("No steps in breakdown response, using fallback")
            return self._create_simple_step(user_request)

        steps: List[CodeStep] = []
        for step_data in steps_data:
            try:
                step = CodeStep(
                    step_number=step_data.get("step_number", len(steps) + 1),
                    description=step_data.get("description", ""),
                    code=None,  # Code will be generated later
                    is_code_execution=step_data.get("is_code_execution", True),
                    validation_method=step_data.get("validation_method", "output_pattern"),
                    expected_output_pattern=step_data.get("expected_output_pattern"),
                    dependencies=step_data.get("dependencies", []),
                    timeout_seconds=step_data.get("timeout_seconds", 30),
                    max_retries=self._sanitize_max_retries(step_data.get("max_retries")),
                    status="pending",
                )
                steps.append(step)
            except Exception as e:
                logger.warning(f"Failed to parse step: {e}")
                continue

        if not steps:
            logger.warning("No valid steps parsed, using fallback")
            return self._create_simple_step(user_request)

        return steps

    def _fix_common_json_issues(self, text: str) -> str:
        """
        Fix common JSON formatting issues in LLM responses.

        Args:
            text: Raw text that should be JSON

        Returns:
            Fixed JSON string
        """
        # Remove any markdown code block indicators
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"\s*```", "", text)

        # Extract just the JSON part if there's extra text
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            text = text[json_start : json_end + 1]

        # Fix single quotes to double quotes
        text = re.sub(r"'([^']*)':", r'"\1":', text)  # Keys
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)  # String values
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)  # More string values

        # Remove trailing commas in objects and arrays
        text = re.sub(r",(\s*[}\]])", r"\1", text)

        # Fix unescaped newlines in strings (basic fix)
        text = re.sub(r'"([^"]*)"([^,}\]])', r'"\1"\2', text)

        return text

    def _extract_steps_with_regex(self, text: str, user_request: str) -> List[CodeStep]:
        """
        Extract steps using regex when JSON parsing fails completely.

        Args:
            text: Raw response text
            user_request: Original user request

        Returns:
            List of CodeStep objects
        """
        logger.info("Using regex fallback for step extraction")

        steps = []
        step_patterns = [
            r"Step\s*(\d+):\s*([^\n]+)",
            r"(\d+)\.\s*([^\n]+)",
            r"Step\s*(\d+)\s*-\s*([^\n]+)",
            r"(\d+)\)\s*([^\n]+)",
        ]

        found_steps = []
        for pattern in step_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                found_steps = matches
                break

        if found_steps:
            for i, (step_num, description) in enumerate(found_steps):
                try:
                    step = CodeStep(
                        step_number=int(step_num) if step_num.isdigit() else i + 1,
                        description=description.strip(),
                        code=None,
                        is_code_execution=True,
                        validation_method="output_pattern",
                        dependencies=[],
                        timeout_seconds=30,
                        max_retries=None,
                        status="pending",
                    )
                    steps.append(step)
                except Exception as e:
                    logger.warning(f"Failed to create step from regex match: {e}")
                    continue

        if not steps:
            logger.warning("No steps found via regex, creating simple step")
            return self._create_simple_step(user_request)

        logger.info(f"Extracted {len(steps)} steps via regex")
        return steps

    def _sanitize_max_retries(self, value: object) -> Optional[int]:
        if value is None:
            return None

        # Prevent bool from being treated as int
        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            n = value
        elif isinstance(value, str):
            try:
                n = int(value.strip())
            except ValueError:
                return None
        else:
            return None

        if n <= 0:
            return None

        return n

    def _validate_steps(self, steps: List[CodeStep]) -> List[CodeStep]:
        """
        Validate and fix step numbers and dependencies.

        Args:
            steps: List of CodeStep objects

        Returns:
            Validated list of CodeStep objects
        """
        # Fix step numbers
        for i, step in enumerate(steps):
            step.step_number = i + 1

        # Validate dependencies
        for step in steps:
            valid_deps = []
            for dep in step.dependencies:
                if 1 <= dep <= len(steps) and dep < step.step_number:
                    valid_deps.append(dep)
                else:
                    logger.warning(f"Invalid dependency {dep} in step {step.step_number}")
            step.dependencies = valid_deps

        return steps

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response."""
        text = response.strip()

        # Try to find JSON in markdown code blocks
        if "```" in text:
            start_idx = text.find("```json")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

            # Try generic code block
            start_idx = text.find("```")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    return text[start_idx:end_idx].strip()

        # Try to find JSON object
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        raise ValueError("No valid JSON found in response")
