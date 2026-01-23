"""
Semantic Intent Classifier using LLM-based classification.

Replaces rigid keyword matching with semantic understanding for:
- Code Intent: "make python keylogger" / "pyhton keylogger" / "create keylogger script"
- Exploitation Intent: "remote access windows with metasploit" / "get shell on windows target"
- Reconnaissance Intent: "find open ports" / "scan for services" / "enumerate target"
- Research Intent: "what vulnerabilities in Apache 2.4.41" / "research CVE-2021-41773"
- Chat Intent: Regular conversation

Features:
- Typo-tolerant: "pyhton" → "python"
- Phrasing-agnostic: synonyms and variations work
- Confidence scoring: asks for clarification when intent is unclear
"""

import logging
from enum import Enum
from typing import Optional, Tuple

from spectral.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SemanticIntent(str, Enum):
    """Semantic intent types for intelligent routing."""

    CODE = "code"  # Code generation, scripting, programming tasks
    EXPLOITATION = "exploitation"  # Penetration testing, exploits, attacks
    RECONNAISSANCE = "reconnaissance"  # Scanning, enumeration, discovery
    RESEARCH = "research"  # Information gathering, vulnerability lookup
    CHAT = "chat"  # Casual conversation


class SemanticIntentClassifier:
    """
    LLM-based semantic intent classifier.

    Uses semantic understanding instead of keyword matching to classify
    user intents with typo tolerance and phrasing flexibility.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the semantic intent classifier.

        Args:
            llm_client: LLM client for semantic classification
        """
        self.llm_client = llm_client

        if not self.llm_client:
            logger.warning("No LLM client provided - semantic classifier will use fallback")

        logger.info("SemanticIntentClassifier initialized")

    def classify(self, user_input: str) -> Tuple[SemanticIntent, float]:
        """
        Classify user input using semantic understanding.

        Args:
            user_input: User's natural language input

        Returns:
            Tuple of (SemanticIntent, confidence_score)
        """
        if not self.llm_client:
            logger.debug("No LLM client - using fallback heuristic classification")
            return self._fallback_classify(user_input)

        try:
            classification_prompt = self._build_classification_prompt(user_input)

            response = self.llm_client.generate(classification_prompt, max_tokens=100)

            return self._parse_classification_response(response)

        except Exception as e:
            logger.error(f"LLM classification failed: {e}, using fallback")
            return self._fallback_classify(user_input)

    def _build_classification_prompt(self, user_input: str) -> str:
        """Build the classification prompt for the LLM."""

        prompt = f"""Classify the following user request into one of these intents:

**CODE**: Code generation, programming, scripting, creating software,
writing functions/classes
- Examples: "make python keylogger", "write a script", "create function",
"build program"

**EXPLOITATION**: Penetration testing, exploiting vulnerabilities,
gaining access, attacks, metasploit
- Examples: "remote access windows with metasploit", "get shell on target",
"exploit SSH", "RCE attack"

**RECONNAISSANCE**: Scanning, enumeration, discovering services/ports,
target analysis
- Examples: "find open ports", "scan for services", "enumerate target",
"what services are running"

**RESEARCH**: Information gathering, vulnerability lookup, CVE research,
technical questions
- Examples: "what vulnerabilities in Apache 2.4.41",
"research CVE-2021-41773", "explain EternalBlue"

**CHAT**: Casual conversation, greetings, general questions,
unrelated to technical tasks
- Examples: "hello", "how are you", "what's the weather", "tell me a joke"

**User Request:**
{user_input}

**Output Format:**
Intent: [CODE|EXPLOITATION|RECONNAISSANCE|RESEARCH|CHAT]
Confidence: [0.0-1.0]
Reason: [brief explanation]"""

        return prompt

    def _parse_classification_response(self, response: str) -> Tuple[SemanticIntent, float]:
        """
        Parse the LLM classification response.

        Args:
            response: LLM response string

        Returns:
            Tuple of (SemanticIntent, confidence_score)
        """
        import json
        import re

        logger.debug(f"Raw classification response: {response}")

        # Clean markdown code blocks if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```"):
            lines = cleaned_response.split("\n")
            # Remove lines that start with ```
            cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned_response = "\n".join(cleaned_lines).strip()

        # Try to parse as JSON first
        try:
            # Try to extract JSON from the response if it's wrapped in text
            json_match = re.search(r"\{[^{}]*\}", cleaned_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))

                # Extract intent
                intent_str = data.get("intent", data.get("Intent", "chat")).lower()
                intent = SemanticIntent.CHAT
                for intent_enum in SemanticIntent:
                    if intent_enum.value.lower() == intent_str.lower():
                        intent = intent_enum
                        break

                # Extract confidence
                confidence = float(data.get("confidence", data.get("Confidence", 0.5)))
                confidence = max(0.0, min(1.0, confidence))

                logger.info(f"Classified as {intent.value} with confidence {confidence:.2f}")
                return intent, confidence
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Failed to parse as JSON: {e}")

        # Fall back to line-by-line parsing
        lines = cleaned_response.split("\n")

        intent = SemanticIntent.CHAT
        confidence = 0.5

        for line in lines:
            line = line.strip()

            if line.lower().startswith("intent:"):
                try:
                    intent_str = line.split(":", 1)[1].strip().upper()
                    # Handle various phrasing variations
                    intent_str = intent_str.replace(" ", "_")

                    # Try to match enum value
                    for intent_enum in SemanticIntent:
                        if intent_enum.value.upper() == intent_str:
                            intent = intent_enum
                            break
                except Exception:
                    logger.debug(f"Failed to parse intent from line: {line}")

            elif line.lower().startswith("confidence:"):
                try:
                    confidence_str = line.split(":", 1)[1].strip()
                    confidence = float(confidence_str)
                    # Clamp to valid range
                    confidence = max(0.0, min(1.0, confidence))
                except (ValueError, IndexError):
                    logger.debug(f"Failed to parse confidence from line: {line}")

        # If we still have default confidence, try keyword matching as last resort
        if confidence == 0.5:
            response_lower = cleaned_response.lower()
            code_keywords = ["code", "script", "program", "write", "create"]
            if any(keyword in response_lower for keyword in code_keywords):
                intent = SemanticIntent.CODE
                confidence = 0.7
            elif any(
                keyword in response_lower
                for keyword in ["exploit", "metasploit", "attack", "compromise"]
            ):
                intent = SemanticIntent.EXPLOITATION
                confidence = 0.7
            elif any(
                keyword in response_lower for keyword in ["scan", "enumerate", "reconnaissance"]
            ):
                intent = SemanticIntent.RECONNAISSANCE
                confidence = 0.7
            elif any(keyword in response_lower for keyword in ["research", "vulnerability", "cve"]):
                intent = SemanticIntent.RESEARCH
                confidence = 0.7

        logger.info(f"Classified as {intent.value} with confidence {confidence:.2f}")
        return intent, confidence

    def _fallback_classify(self, user_input: str) -> Tuple[SemanticIntent, float]:
        """
        Fallback heuristic classification when LLM is unavailable.

        This is less accurate but provides basic functionality.

        Args:
            user_input: User's natural language input

        Returns:
            Tuple of (SemanticIntent, confidence_score)
        """
        input_lower = user_input.lower().strip()

        # Heuristic keywords for each intent
        # Include common typos and variations
        code_keywords = {
            "write",
            "create",
            "make",
            "build",
            "generate",
            "implement",
            "develop",
            "code",
            "script",
            "program",
            "function",
            "class",
            "keylogger",  # Keylogger is a coding task
            # Typos
            "pyhton",  # python
            "javascritp",  # javascript
            "javascipt",  # javascript
        }

        exploitation_keywords = {
            "exploit",
            "hack",
            "crack",
            "attack",
            "metasploit",
            "payload",
            "reverse shell",
            "backdoor",
            "rce",
            "remote code",
            "privesc",
            "privilege escalation",
            "pentest",
            "penetration",
            "shell",
            "compromise",  # Added for "compromise windows machine"
            "get shell",  # Common phrasing
            # Typos
            "winndows",  # windows
        }

        reconnaissance_keywords = {
            "scan",
            "nmap",
            "enumerate",
            "discover",
            "find service",
            "open port",
            # Typos
            "scann",  # scan
        }

        research_keywords = {
            "vulnerabilit",
            "cve",
            "research",
            "explain",
            "how does",
            "what is",
            "tutorial",
        }

        # "target" is too generic - only match if it's part of a pentest context
        # We'll handle this specially below

        # Count matches for each intent
        code_score = sum(1 for kw in code_keywords if kw in input_lower)
        exploitation_score = sum(1 for kw in exploitation_keywords if kw in input_lower)
        reconnaissance_score = sum(1 for kw in reconnaissance_keywords if kw in input_lower)
        research_score = sum(1 for kw in research_keywords if kw in input_lower)

        # Determine intent based on highest score
        scores = {
            SemanticIntent.CODE: code_score,
            SemanticIntent.EXPLOITATION: exploitation_score,
            SemanticIntent.RECONNAISSANCE: reconnaissance_score,
            SemanticIntent.RESEARCH: research_score,
            SemanticIntent.CHAT: 0,
        }

        max_score = max(scores.values())

        if max_score == 0:
            return SemanticIntent.CHAT, 0.3

        # Get intent with highest score
        intent = max(scores, key=lambda k: scores[k])
        confidence = min(0.7, 0.4 + max_score * 0.1)

        logger.info(
            f"Fallback classification: {intent.value} "
            f"(score: {max_score}, confidence: {confidence:.2f})"
        )

        return intent, confidence

    def requires_clarification(self, user_input: str) -> bool:
        """
        Check if user input requires clarification before routing.

        Args:
            user_input: User's natural language input

        Returns:
            True if clarification is needed
        """
        intent, confidence = self.classify(user_input)

        # Low confidence indicates unclear intent
        if confidence < 0.6:
            return True

        # Check for ambiguous keywords
        ambiguous_patterns = ["it", "that", "this", "the target", "the machine"]
        input_lower = user_input.lower().strip()

        has_ambiguous_reference = any(pattern in input_lower for pattern in ambiguous_patterns)

        if has_ambiguous_reference:
            return True

        return False

    def get_clarification_question(self, user_input: str) -> str:
        """
        Generate a clarification question for ambiguous user input.

        Args:
            user_input: User's natural language input

        Returns:
            Clarification question string
        """
        intent, confidence = self.classify(user_input)

        if confidence < 0.6:
            return (
                "I'm not entirely sure what you're trying to do. "
                "Could you provide more details? For example:\n"
                "- Are you looking to generate code?\n"
                "- Are you trying to test or exploit a target?\n"
                "- Do you want to scan or enumerate something?\n"
                "- Are you researching a vulnerability or tool?\n"
                "- Or just having a casual conversation?"
            )

        # Handle ambiguous references
        ambiguous_patterns = ["it", "that", "this", "the target", "the machine"]
        input_lower = user_input.lower().strip()

        if any(pattern in input_lower for pattern in ambiguous_patterns):
            return (
                f"I think you want to {intent.value} something, but I'm not "
                f"sure what you're referring to. "
                f"Could you provide more specific details? For example:\n"
                f"- What target are you working with?\n"
                f"- What service or system are you referring to?\n"
                f"- What's the goal you're trying to achieve?"
            )

        return "Could you please clarify what you'd like me to do?"

    def classify_with_clarification(
        self, user_input: str
    ) -> Tuple[SemanticIntent, float, Optional[str]]:
        """
        Classify intent and optionally return a clarification question.

        Args:
            user_input: User's natural language input

        Returns:
            Tuple of (SemanticIntent, confidence_score, clarification_question)
            clarification_question is None if no clarification needed
        """
        intent, confidence = self.classify(user_input)

        if self.requires_clarification(user_input):
            clarification = self.get_clarification_question(user_input)
            return intent, confidence, clarification

        return intent, confidence, None
