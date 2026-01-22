"""
Intent classifier module for differentiating chat vs. action intents.

Uses heuristics first (imperative verbs, question patterns) and falls back to LLM
classification for ambiguous cases with semantic understanding.
"""

import json
import logging
import re
from enum import Enum
from typing import Optional, Tuple

from spectral.llm_client import LLMClient

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Types of user intents."""

    CHAT = "chat"
    ACTION = "action"
    UNKNOWN = "unknown"
    CASUAL = "casual"
    COMMAND = "command"


class IntentClassifier:
    """
    Classifies user input as chat or action intent using semantic understanding.

    Uses heuristics first for fast classification, then falls back to LLM
    classification for ambiguous cases. The LLM provides semantic understanding
    that handles:
    - Questions with action intent ("can you exploit this?" → ACTION)
    - Casual phrasing and slang ("pwn this box" → ACTION)
    - Synonyms ("enumerate", "discover", "find" → all recognized)
    - Typos ("pyhton" → still understood as python-related)
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the intent classifier.

        Args:
            llm_client: Optional LLM client for semantic classification.
                       If None, uses heuristic classification only.
        """
        self.llm_client = llm_client

        if not self.llm_client:
            logger.warning("No LLM client provided - intent classifier will use heuristics only")
        else:
            logger.info("IntentClassifier initialized with LLM client for semantic classification")

        # Action verbs that indicate commands
        self.action_verbs = {
            "open",
            "create",
            "delete",
            "move",
            "copy",
            "start",
            "stop",
            "run",
            "execute",
            "launch",
            "close",
            "save",
            "load",
            "download",
            "upload",
            "install",
            "uninstall",
            "restart",
            "shutdown",
            "type",
            "click",
            "search",
            "find",
            "list",
            "show",
            "hide",
            "enable",
            "disable",
            "connect",
            "disconnect",
            "send",
            "receive",
            "play",
            "pause",
            "record",
            "capture",
            "screenshot",
            "backup",
            "restore",
            "update",
            "upgrade",
            "downgrade",
            "mount",
            "unmount",
            "format",
            "clean",
            "clear",
            "remove",
            "add",
            "insert",
            "replace",
            "rename",
            "edit",
            "modify",
            "change",
            "switch",
            "toggle",
            "check",
            "test",
            "verify",
            "validate",
            "scan",
            "monitor",
            "track",
            "log",
            "export",
            "import",
            "write",
            "make",
            "build",
            "generate",
            "implement",
            "develop",
            "calculate",
            "compute",
            "solve",
            "parse",
            "process",
        }

        # System action keywords
        self.action_keywords = {
            "file",
            "folder",
            "directory",
            "window",
            "application",
            "program",
            "process",
            "service",
            "registry",
            "settings",
            "configuration",
            "network",
            "connection",
            "internet",
            "wifi",
            "bluetooth",
            "usb",
            "drive",
            "disk",
            "volume",
            "partition",
            "memory",
            "ram",
            "cpu",
            "gpu",
            "screen",
            "display",
            "monitor",
            "mouse",
            "keyboard",
            "camera",
            "microphone",
            "speaker",
            "audio",
            "video",
            "image",
            "picture",
            "photo",
            "document",
            "text",
            "email",
            "message",
            "chat",
            "browser",
            "website",
            "url",
            "link",
            "download",
            "upload",
            "cloud",
            "server",
            "database",
            "table",
            "query",
            "script",
            "command",
            "terminal",
            "console",
            "shell",
            "powershell",
            "batch",
            "shortcut",
            "icon",
            "taskbar",
            "desktop",
            "wallpaper",
            "theme",
            "font",
            "color",
            "resolution",
            "brightness",
            "volume",
            "mute",
            "unmute",
            "code",
            "python",
            "javascript",
            "java",
            "function",
            "class",
        }

        # Chat patterns (questions, greetings, conversational phrases)
        # Use \b word boundaries to prevent partial matches
        self.chat_patterns = [
            r"\b(how|what|why|when|where|who|which)\b",
            r"\b(can you|could you|would you|will you|are you|is it)\b",
            r"\b(explain|describe|summarize|help me|show me|let me know)\b",
            r"\b(how are you|what's up|how do you feel|what do you think|what are you doing)\b",
            r"\b(thank you|thanks|sorry|excuse me)\b",
            r"\b(hello|hi|hey|good morning|good afternoon|good evening|bye|goodbye)\b",
            r"\btell me (a )?(joke|story|about|how)\b",
            r"\bwhat('s| is) your (name|purpose|role)\b",
            r"\bhow can (you|i|help)\b",
            r"\?$",  # Ends with question mark
        ]

        # Compile regex patterns
        # All chat patterns use search now since we added \b word boundaries
        self.chat_search_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.chat_patterns
        ]

        logger.info("IntentClassifier initialized")

    def classify_heuristic(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Classify intent using heuristics only.

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        input_lower = user_input.lower().strip()
        words = input_lower.split()

        # Check for chat patterns first (higher priority)
        for pattern in self.chat_search_patterns:
            if pattern.search(input_lower):
                logger.debug(f"Chat pattern matched: {pattern.pattern}")
                return IntentType.CHAT, 0.9

        # Check for imperative action verbs at the beginning
        if words and words[0] in self.action_verbs:
            logger.debug(f"Action verb detected: {words[0]}")
            return IntentType.ACTION, 0.8

        # Check for action keywords anywhere in the input
        action_keyword_count = sum(1 for word in words if word in self.action_keywords)
        if action_keyword_count >= 2:
            logger.debug(f"Multiple action keywords detected: {action_keyword_count}")
            return IntentType.ACTION, 0.7

        # Check for single action keyword with action verb
        if action_keyword_count >= 1:
            action_verbs_in_input = sum(1 for word in words if word in self.action_verbs)
            if action_verbs_in_input >= 1:
                logger.debug("Action keyword + verb combination detected")
                return IntentType.ACTION, 0.6

        # Check for question mark (strong chat indicator)
        if input_lower.endswith("?"):
            logger.debug("Question mark detected")
            return IntentType.CHAT, 0.8

        # If no strong indicators, return unknown with low confidence
        logger.debug("No strong heuristics matched")
        return IntentType.UNKNOWN, 0.3

    def _semantic_classify(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Use LLM to semantically understand intent.

        This method provides semantic understanding that handles:
        - Questions containing action intent ("can you exploit this?")
        - Casual phrasing ("pwn this box")
        - Synonyms ("enumerate", "discover", "find")
        - Typos ("pyhton" → still understood as python)

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)

        Raises:
            Exception: If LLM classification fails (caller should fall back to heuristics)
        """
        prompt = f"""You are an intent classifier. Determine if the user is asking the AI to DO something (ACTION) or just asking for information/conversation (CHAT).

**ACTION examples** (user wants AI to DO something):
- "write a python script that lists files"
- "can you exploit this windows machine" (ACTION despite question form)
- "create a malware payload"
- "run a network scan"
- "what ports are open on this target" (ACTION - they want results, not conversation)
- "enumerate services on target"
- "find vulnerabilities"
- "help me with metasploit attack" (ACTION - wants exploitation help, not conversation)
- "use metasploit to exploit windows target"
- "how do i exploit with metasploit"
- "can you help me with a metasploit attack"
- "i want to use msfvenom to create payload"
- "windows pwn with metasploit"
- "find what services are running"
- "let me know what's listening"
- "can you run this ps script"

**CHAT examples** (user wants conversation/information only):
- "how does metasploit work?" (learning, not asking AI to exploit)
- "tell me about penetration testing"
- "what's the difference between X and Y?"
- "any advice on security?" (general advice, not specific action)
- "what's a payload?"

User input: "{user_input}"

Respond ONLY with JSON:
{{
  "intent": "action" or "chat",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""

        try:
            response = self.llm_client.generate(prompt, max_tokens=150)
            return self._parse_semantic_response(response)
        except Exception as e:
            logger.error(f"LLM semantic classification failed: {e}")
            raise

    def _parse_semantic_response(self, response: str) -> Tuple[IntentType, float]:
        """
        Parse the LLM semantic classification response.

        Args:
            response: LLM response string (should contain JSON)

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        try:
            # Try to extract JSON from the response
            json_text = self._extract_json_from_response(response)
            data = json.loads(json_text)

            intent_str = data.get("intent", "").lower().strip()
            confidence = float(data.get("confidence", 0.5))

            # Map to IntentType enum
            if intent_str == "action":
                intent = IntentType.ACTION
            elif intent_str == "chat":
                intent = IntentType.CHAT
            else:
                logger.warning(f"Unknown intent in LLM response: {intent_str}, defaulting to CHAT")
                intent = IntentType.CHAT
                confidence = 0.5

            # Clamp confidence to valid range
            confidence = max(0.0, min(1.0, confidence))

            logger.debug(f"LLM semantic classification: {intent} (confidence: {confidence:.2f})")
            logger.debug(f"LLM reasoning: {data.get('reasoning', 'N/A')}")

            return intent, confidence

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}, defaulting to CHAT")
            return IntentType.CHAT, 0.4

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON content from LLM response.

        Handles cases where the LLM wraps JSON in markdown code blocks
        or includes extra formatting.

        Args:
            response: Raw response text from LLM

        Returns:
            JSON string ready for parsing

        Raises:
            ValueError: If no valid JSON can be extracted
        """
        text = response.strip()

        # Try to extract JSON from markdown code blocks
        if "```" in text:
            # Look for json code block
            start_idx = text.find("```json")
            if start_idx >= 0:
                start_idx = text.find("\n", start_idx) + 1
                end_idx = text.find("```", start_idx)
                if end_idx > start_idx:
                    text = text[start_idx:end_idx].strip()
            else:
                # Try generic code block
                start_idx = text.find("```")
                if start_idx >= 0:
                    start_idx = text.find("\n", start_idx) + 1
                    end_idx = text.find("```", start_idx)
                    if end_idx > start_idx:
                        text = text[start_idx:end_idx].strip()

        # If text starts with { or [, it's likely JSON
        if text.startswith("{") or text.startswith("["):
            return text

        # Try to find JSON object in the text
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return text[json_start : json_end + 1]

        # If no JSON found, raise error
        raise ValueError("No valid JSON found in response")

    def classify_with_llm(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Classify intent using LLM for ambiguous cases.

        This method is kept for backward compatibility but now uses
        the semantic classification approach.

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        if not self.llm_client:
            # Fall back to heuristics if no LLM client available
            logger.warning("LLM client not available, using heuristic classification")
            input_lower = user_input.lower().strip()

            action_like = any(word in self.action_verbs for word in input_lower.split()[:3])
            chat_like = any(pattern.search(input_lower) for pattern in self.chat_search_patterns)

            if action_like and not chat_like:
                return IntentType.ACTION, 0.6
            elif chat_like and not action_like:
                return IntentType.CHAT, 0.6
            else:
                return IntentType.CHAT, 0.4

        # Use semantic classification
        try:
            return self._semantic_classify(user_input)
        except Exception as e:
            logger.error(f"Semantic classification failed: {e}, falling back to heuristics")
            # Fall back to simple heuristics on error
            input_lower = user_input.lower().strip()
            action_like = any(word in self.action_verbs for word in input_lower.split()[:3])
            chat_like = any(pattern.search(input_lower) for pattern in self.chat_search_patterns)

            if action_like and not chat_like:
                return IntentType.ACTION, 0.5
            else:
                return IntentType.CHAT, 0.5

    def classify(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Classify user intent using semantic understanding.

        Uses heuristics first for speed, then falls back to LLM semantic classification
        for ambiguous cases. This provides:
        - Fast classification for obvious cases (imperative verbs at start)
        - Semantic understanding for complex phrasing, questions with action intent
        - Typo tolerance and synonym recognition via LLM

        Args:
            user_input: User input string

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        logger.debug(f"Classifying intent for: {user_input}")

        # Try heuristic classification first for speed
        heuristic_intent, heuristic_confidence = self.classify_heuristic(user_input)

        # High confidence from heuristics - no need for LLM
        if heuristic_confidence >= 0.8:
            logger.debug(
                f"High confidence heuristic classification: {heuristic_intent} "
                f"({heuristic_confidence:.2f})"
            )
            return heuristic_intent, heuristic_confidence

        # Medium confidence - check if LLM client available for semantic analysis
        if self.llm_client and heuristic_confidence < 0.7:
            logger.debug(
                f"Medium/low confidence heuristics ({heuristic_confidence:.2f}), "
                f"trying semantic LLM classification"
            )
            try:
                semantic_intent, semantic_confidence = self.classify_with_llm(user_input)

                # Use semantic result if it has higher confidence
                if semantic_confidence > heuristic_confidence:
                    logger.debug(
                        f"Using semantic classification: {semantic_intent} "
                        f"({semantic_confidence:.2f})"
                    )
                    return semantic_intent, semantic_confidence
            except Exception as e:
                logger.warning(f"Semantic classification failed: {e}, using heuristic result")

        # Fall back to heuristic result
        logger.debug(
            f"Using heuristic classification: {heuristic_intent} ({heuristic_confidence:.2f})"
        )
        return heuristic_intent, heuristic_confidence

    def is_chat_intent(self, user_input: str) -> bool:
        """
        Check if user input is a chat intent.

        Args:
            user_input: User input string

        Returns:
            True if chat intent, False otherwise
        """
        intent, confidence = self.classify(user_input)
        return intent == IntentType.CHAT

    def is_action_intent(self, user_input: str) -> bool:
        """
        Check if user input is an action intent.

        Args:
            user_input: User input string

        Returns:
            True if action intent, False otherwise
        """
        intent, confidence = self.classify(user_input)
        return intent == IntentType.ACTION

    def classify_intent(self, user_input: str) -> str:
        """
        Classify user input as 'casual' or 'command'.

        This is a convenience method that maps the internal CHAT/ACTION intents
        to the casual/command terminology used in the conversational response system.

        Args:
            user_input: User input string

        Returns:
            "casual" if this is a conversational/greeting input
            "command" if this is an action/task request
        """
        intent, confidence = self.classify(user_input)

        # Map CHAT -> casual, ACTION -> command
        if intent == IntentType.CHAT:
            return "casual"
        elif intent == IntentType.ACTION:
            return "command"
        else:
            # For UNKNOWN intents, default to casual (safer to be conversational)
            logger.debug(f"Unknown intent classified as 'casual' with confidence {confidence}")
            return "casual"
