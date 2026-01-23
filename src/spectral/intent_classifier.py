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
            # Security/pentesting oriented "do something" verbs (used in test suite)
            "exploit",
            "attack",
            "enumerate",
            "recon",
            "pwn",
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
            "services",
            "port",
            "ports",
            "listening",
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
        # Normalize tokens (strip punctuation) so "what's" -> ["what", "s"]
        words = re.findall(r"[a-z0-9]+", input_lower)

        if not words:
            logger.debug("Empty input")
            return IntentType.UNKNOWN, 0.3

        # Strong social/casual chat signals with word boundaries
        strong_chat_full_phrases = [
            "how are you",
            "what's up",
            "whats up",
            "good morning",
            "good afternoon",
            "good evening",
            "thank you",
            "tell me a joke",
            "tell me a story",
            "tell me about you",
            "tell me about yourself",
            "who are you",
            "your name",
        ]
        # Single word greetings need word boundaries
        strong_chat_words = ["hello", "hi", "hey", "bye", "goodbye", "thanks", "sorry"]

        if any(phrase in input_lower for phrase in strong_chat_full_phrases):
            logger.debug("Strong chat phrase detected")
            return IntentType.CHAT, 0.9

        # Check single-word greetings with word boundaries
        for word in strong_chat_words:
            if re.search(rf"\b{word}\b", input_lower):
                logger.debug(f"Strong chat word detected: {word}")
                return IntentType.CHAT, 0.9

        starts_with_request = input_lower.startswith(
            (
                "can you",
                "could you",
                "would you",
                "will you",
                "can u",
                "could u",
                "would u",
                "will u",
                "please ",
                "pls ",
            )
        )
        has_question_word = bool(re.search(r"\b(how|what|why|when|where|who|which)\b", input_lower))
        has_question_mark = input_lower.endswith("?")
        has_question_form = starts_with_request or has_question_word or has_question_mark

        # Action signals
        action_keyword_count = sum(1 for word in words if word in self.action_keywords)

        # Treat some verbs as context-sensitive (e.g., "ports are open" shouldn't be parsed
        # as a file "open" command, but it IS an action request overall). We'll still
        # count "open" as an action verb when it clearly appears as a verb.
        action_verbs_in_input = []
        for i, word in enumerate(words):
            if word not in self.action_verbs:
                continue
            if word in {"open", "close"} and i > 0 and words[i - 1] in {"is", "are", "was", "were"}:
                continue
            action_verbs_in_input.append(word)

        starts_with_action_verb = words[0] in self.action_verbs

        # Extra action-like question patterns (especially common in recon/pentesting)
        action_question_phrases = [
            "what ports are open",
            "what services are running",
            "what is listening",
            "what's listening",
            "let me know what's listening",
            "let me know what is listening",
            "can you run",
            "can you execute",
            "port scan",
            "network scan",
            "scan a",
            "scan the",
        ]

        # Polite action requests - question form but clearly wanting execution
        polite_action_patterns = [
            "can you run",
            "can you execute",
            "could you run",
            "would you run",
            "will you run",
            "can you help me with",
            "can you help with",
            "run this",
            "execute this",
        ]
        has_polite_action_request = any(phrase in input_lower for phrase in polite_action_patterns)

        has_action_signals = (
            starts_with_action_verb
            or bool(action_verbs_in_input)
            or action_keyword_count >= 2
            or any(phrase in input_lower for phrase in action_question_phrases)
            or has_polite_action_request
        )

        # Informational/learning style requests
        informational_phrases = [
            "how does ",
            "what is ",
            "whats ",
            "what's ",
            "tell me about",
            "explain ",
            "describe ",
            "summarize ",
            "difference between",
        ]
        is_informational = any(phrase in input_lower for phrase in informational_phrases)

        # Brief tool invocations (casual action requests like "powershell please")
        brief_tool_invocations = [
            "powershell please",
            "python please",
            "use powershell",
            "use python",
            "powershell to do",
            "python to do",
        ]
        is_brief_tool_invocation = any(phrase in input_lower for phrase in brief_tool_invocations)

        # Brief tool invocations (casual action requests)
        if is_brief_tool_invocation:
            logger.debug("Brief tool invocation detected")
            return IntentType.ACTION, 0.85

        # Clear imperative action (no question/request framing)
        if starts_with_action_verb and not has_question_form:
            logger.debug(f"Action verb detected: {words[0]}")
            return IntentType.ACTION, 0.85

        # Polite action requests (question form but clear execution intent)
        if has_polite_action_request and has_action_signals:
            logger.debug("Polite action request detected")
            return IntentType.ACTION, 0.80

        # Question/request form + action signals -> ACTION, but with lower confidence so
        # semantic classification (LLM) can resolve do-vs-learn nuances.
        if has_question_form and has_action_signals:
            logger.debug("Question form with action signals detected")
            return IntentType.ACTION, 0.70

        # Non-question action signals
        if has_action_signals:
            if action_keyword_count >= 2:
                logger.debug(f"Multiple action keywords detected: {action_keyword_count}")
                return IntentType.ACTION, 0.7
            if action_keyword_count >= 1 and action_verbs_in_input:
                logger.debug("Action keyword + verb combination detected")
                return IntentType.ACTION, 0.6
            if starts_with_action_verb:
                return IntentType.ACTION, 0.75
            return IntentType.ACTION, 0.55

        # Informational/learning request -> CHAT
        if is_informational:
            logger.debug("Informational request detected")
            return IntentType.CHAT, 0.85

        # Generic question/request form is often chat, but keep confidence medium so semantic
        # classification can override when appropriate.
        if has_question_form:
            logger.debug("Generic question/request form detected")
            return IntentType.CHAT, 0.6

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
        prompt = f"""You are an intent classifier. Determine if the user is asking the
AI to DO something (ACTION) or asking for information/conversation (CHAT).

CRITICAL DISTINCTION:
- CHAT: The user wants information, explanations, definitions, or learning.
  Examples:
  - "how does metasploit work?" (user learning)
  - "tell me about exploitation" (user learning)
  - "what's a payload?" (user learning)

- ACTION: The user wants the AI to perform an action/task and provide results.
  IMPORTANT: Question form can still be ACTION.
  Examples:
  - "how do I exploit with metasploit" (wants help - action)
  - "can you help me with metasploit attack" (wants help - action)
  - "run a network scan" (user wants execution)
  - "find what services are running" (user wants results)
  - "what ports are open on 192.168.1.1" (wants check - action)
  - "can you run this ps script" (user wants execution)

KEY RULE:
- If the user is asking the AI to DO something
  (run/execute/scan/find/check/list/search/etc.), classify as ACTION.
- If the user is asking to LEARN/UNDERSTAND, classify as CHAT.

User input: "{user_input}"

Respond ONLY with JSON:
{{
  "intent": "action" or "chat",
  "confidence": 0.0-1.0,
  "reasoning": "Is the user asking the AI to DO something or asking to LEARN?"
}}"""

        try:
            if self.llm_client is None:
                raise Exception("LLM client not available")
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
