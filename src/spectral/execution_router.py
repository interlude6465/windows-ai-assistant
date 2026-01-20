"""
Execution router module for dual execution mode.

Classifies incoming requests as DIRECT, PLANNING, RESEARCH, or RESEARCH_AND_ACT
based on complexity and intent.
"""

import logging
import re
from typing import Optional, Tuple

from spectral.execution_models import ExecutionMode

logger = logging.getLogger(__name__)

# Common Python stdlib modules that don't need research
PYTHON_STDLIB = {
    "os", "sys", "re", "json", "datetime", "time", "math", "random",
    "collections", "itertools", "functools", "operator", "string",
    "pathlib", "typing", "enum", "abc", "copy", "io", "logging",
    "warnings", "threading", "multiprocessing", "subprocess", "socket",
    "http", "urllib", "email", "html", "xml", "csv", "configparser",
    "hashlib", "hmac", "secrets", "ssl", "base64", "binascii",
    "struct", "codecs", "unicodedata", "locale", "gettext",
}


class ExecutionRouter:
    """
    Routes user requests to appropriate execution mode.

    DIRECT mode: Simple code gen/execution requests
    PLANNING mode: Complex multi-step requests requiring structured planning
    RESEARCH mode: Information gathering from the web
    RESEARCH_AND_ACT mode: Research then execute based on findings
    """

    def __init__(self) -> None:
        """Initialize the execution router."""
        # Direct mode keywords (simple, single-action requests)
        self.direct_keywords = {
            "write",
            "code",
            "program",
            "script",
            "run",
            "execute",
            "create",
            "generate",
            "build",
            "make",
            "implement",
            "develop",
            "search",
        }

        # Planning mode keywords (complex, multi-step requests)
        self.planning_keywords = {
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
            "system",
            "framework",
            "application",
            "platform",
            "architecture",
            "setup",
            "configure",
            "deploy",
            "integrate",
            "connect",
            "chain",
        }

        # Complexity indicators (suggest planning mode)
        self.complexity_indicators = {
            "error handling",
            "logging",
            "testing",
            "validation",
            "authentication",
            "database",
            "api",
            "web",
            "server",
            "client",
            "frontend",
            "backend",
            "scraper",
            "parser",
            "processor",
            "manager",
            "controller",
            "service",
        }

        # Research keywords (information gathering)
        self.research_keywords = {
            "how do i",
            "how to",
            "what is",
            "what does",
            "does it support",
            "can i",
            "install",
            "set up",
            "configure",
            "error",
            "problem",
            "issue",
            "troubleshoot",
            "fix",
            "solve",
            "find out",
            "learn",
            "understand",
            "explain",
            "guide",
            "tutorial",
        }

        logger.info("ExecutionRouter initialized")

    def should_research(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user input requires research before code generation.

        Detects patterns like "how to use X" where X is an external tool/library.

        Args:
            user_input: User's natural language request

        Returns:
            Tuple of (should_research, tool_name)
        """
        input_lower = user_input.lower().strip()

        # Research-needed patterns
        research_patterns = [
            r"how to use\s+(\w+)",
            r"how do i use\s+(\w+)",
            r"show me how to use\s+(\w+)",
            r"demonstrate\s+(\w+)",
            r"example of\s+using\s+(\w+)",
            r"teach me\s+(\w+)",
            r"learn\s+(\w+)",
            r"how can i use\s+(\w+)",
            r"what's the way to use\s+(\w+)",
        ]

        for pattern in research_patterns:
            match = re.search(pattern, input_lower)
            if match:
                tool_name = match.group(1)

                # Don't research common Python stdlib modules
                if tool_name in PYTHON_STDLIB:
                    continue

                logger.info(f"Research needed for tool: {tool_name}")
                return True, tool_name

        return False, None

    def classify(self, user_input: str) -> Tuple[ExecutionMode, float]:
        """
        Classify user input into execution mode.

        Args:
            user_input: User's natural language request

        Returns:
            Tuple of (ExecutionMode, confidence_score)
        """
        logger.debug(f"Classifying execution mode for: {user_input}")

        input_lower = user_input.lower().strip()
        words = input_lower.split()

        # EARLY EXIT: Exclude self-referential questions (about Spectral itself)
        self_ref_patterns = [
            "what is your",
            "what are you",
            "who are you",
            "what can you",
            "what do you",
            "what's your",
            "whats your",
            "tell me about you",
            "tell me about yourself",
            "your name",
        ]
        if any(pattern in input_lower for pattern in self_ref_patterns):
            logger.debug("Self-referential question detected, skipping research")
            # Route to casual conversation (use direct mode with low confidence)
            return ExecutionMode.DIRECT, 0.3

        # EARLY EXIT: Exclude greetings and casual openers
        greetings = [
            "hello",
            "hi",
            "hey",
            "greetings",
            "good morning",
            "good afternoon",
            "good evening",
            "whats up",
            "what's up",
            "sup",
            "how are you",
            "how are you doing",
            "how do you do",
            "what's good",
            "whats good",
        ]
        # Check if input is primarily a greeting
        if any(
            greeting == input_lower or input_lower.startswith(greeting + " ")
            for greeting in greetings
        ):
            logger.debug("Greeting detected, skipping research")
            return ExecutionMode.DIRECT, 0.3

        # EARLY EXIT: Very short inputs (< 4 words) unlikely to be research queries
        # unless they contain strong technical keywords
        if len(words) < 4:
            strong_tech_keywords = ["error", "exception", "install", "setup", "configure", "deploy"]
            has_strong_tech = any(keyword in input_lower for keyword in strong_tech_keywords)
            if not has_strong_tech:
                logger.debug("Short input without strong technical keywords, skipping research")
                return ExecutionMode.DIRECT, 0.4

        # EARLY EXIT: Exclude creation commands from research
        creation_keywords = ["write", "create", "build", "generate", "implement", "make", "develop"]
        if any(input_lower.startswith(kw) for kw in creation_keywords):
            logger.debug(
                "Creation command detected, routing to DIRECT/PLANNING instead of RESEARCH"
            )
            # Determine between DIRECT and PLANNING
            direct_keyword_count = sum(1 for word in words if word in self.direct_keywords)
            planning_keyword_count = sum(1 for word in words if word in self.planning_keywords)
            if planning_keyword_count > direct_keyword_count or len(words) > 10:
                return ExecutionMode.PLANNING, 0.8
            return ExecutionMode.DIRECT, 0.8

        # EARLY EXIT: Exclude meta-prompts from research
        meta_prompts = ["on purpose", "intentionally", "as an example", "for demonstration"]
        if any(pattern in input_lower for pattern in meta_prompts):
            logger.debug("Meta-prompt detected, avoiding research")
            return ExecutionMode.DIRECT, 0.7

        # Count indicators for each mode
        direct_score = 0.0
        planning_score = 0.0
        research_score = 0.0

        # Check for research patterns (strong signals)
        explicit_research_queries = [
            "how to",
            "what is",
            "find out",
            "explain",
            "look up",
            "how do i",
        ]
        for pattern in explicit_research_queries:
            if pattern in input_lower:
                research_score += 1.0

        # Questions are usually research
        if input_lower.startswith(("how", "what", "why", "when", "where", "can", "does", "is")):
            research_score += 0.6

        # Question marks also indicate research
        if "?" in input_lower:
            research_score += 0.3

        # Error messages suggest research
        if any(word in input_lower for word in ["error", "failed", "exception", "traceback"]):
            research_score += 0.6

        # Check for direct mode keywords
        direct_keyword_count = sum(1 for word in words if word in self.direct_keywords)
        direct_score += direct_keyword_count * 0.3

        # Check for planning mode keywords
        planning_keyword_count = sum(1 for word in words if word in self.planning_keywords)
        planning_score += planning_keyword_count * 0.4

        # Check for complexity indicators (strong planning signal)
        complexity_count = sum(1 for phrase in self.complexity_indicators if phrase in input_lower)
        planning_score += complexity_count * 0.5

        # Length penalty: longer requests tend to be planning mode
        word_count = len(words)
        if word_count > 15:
            planning_score += 0.2
        elif word_count > 10:
            planning_score += 0.1

        # Check for conjunctions (suggests multi-step)
        conjunctions = ["and", "with", "then", "also", "plus", "including"]
        conjunction_count = sum(1 for word in words if word in conjunctions)
        if conjunction_count >= 2:
            planning_score += 0.3

        # Determine mode based on scores
        confidence = 0.0

        # If research score is high, decide between RESEARCH and RESEARCH_AND_ACT
        if research_score >= 0.9:
            # If also has action keywords, use RESEARCH_AND_ACT
            has_action_intent = direct_score > 0.5 or planning_score > 0.5
            if has_action_intent:
                mode = ExecutionMode.RESEARCH_AND_ACT
                confidence = min(0.95, 0.6 + research_score * 0.2)
            else:
                mode = ExecutionMode.RESEARCH
                confidence = min(0.95, 0.6 + research_score * 0.2)
        elif planning_score > direct_score and planning_score > research_score:
            mode = ExecutionMode.PLANNING
            confidence = min(0.95, 0.5 + (planning_score - direct_score) * 0.3)
        elif direct_score > planning_score and direct_score > research_score:
            mode = ExecutionMode.DIRECT
            confidence = min(0.95, 0.5 + (direct_score - planning_score) * 0.3)
        else:
            # Tiebreaker: default to planning for safety
            mode = ExecutionMode.PLANNING
            confidence = 0.5

        logger.info(f"Classified as {mode.value} mode with confidence {confidence:.2f}")
        logger.debug(
            f"Scores - Direct: {direct_score:.2f}, Planning: {planning_score:.2f}, "
            f"Research: {research_score:.2f}"
        )

        return mode, confidence

    def is_direct_mode(self, user_input: str) -> bool:
        """
        Check if user input should use direct execution mode.

        Args:
            user_input: User's natural language request

        Returns:
            True if direct mode, False otherwise
        """
        mode, confidence = self.classify(user_input)
        return mode == ExecutionMode.DIRECT and confidence >= 0.6

    def is_planning_mode(self, user_input: str) -> bool:
        """
        Check if user input should use planning execution mode.

        Args:
            user_input: User's natural language request

        Returns:
            True if planning mode, False otherwise
        """
        mode, confidence = self.classify(user_input)
        return mode == ExecutionMode.PLANNING and confidence >= 0.6
