"""
Conversation context module for context-aware responses.

Maintains conversation history, tracks context, and enables
intelligent, context-aware responses.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single conversation turn (user + assistant)."""

    user_message: str
    assistant_response: str
    timestamp: datetime
    intent: Optional[str] = None
    task_type: Optional[str] = None


class ConversationContext:
    """
    Maintains conversation history and context for intelligent responses.

    Features:
    - Store recent messages (configurable limit)
    - Track conversation theme/topic
    - Detect continuation requests ("another one", "tell me more")
    - Provide context for response generation
    """

    def __init__(self, max_history: int = 10) -> None:
        """
        Initialize conversation context.

        Args:
            max_history: Maximum number of conversation turns to keep
        """
        self.max_history = max_history
        self.history: List[ConversationTurn] = []
        self.current_theme: Optional[str] = None
        self.conversation_start_time: datetime = datetime.now()

        logger.info(f"ConversationContext initialized with max_history={max_history}")

    def add_turn(
        self,
        user_message: str,
        assistant_response: str,
        intent: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> None:
        """
        Add a conversation turn to history.

        Args:
            user_message: User's message
            assistant_response: Assistant's response
            intent: Detected intent (casual, command, etc.)
            task_type: Type of task (if applicable)
        """
        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
            timestamp=datetime.now(),
            intent=intent,
            task_type=task_type,
        )

        self.history.append(turn)

        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

        logger.debug(f"Added conversation turn (total: {len(self.history)})")

    def get_recent_user_messages(self, count: int = 5) -> List[str]:
        """
        Get recent user messages.

        Args:
            count: Number of messages to retrieve

        Returns:
            List of recent user messages (newest first)
        """
        recent = self.history[-count:]
        return [turn.user_message for turn in reversed(recent)]

    def get_recent_responses(self, count: int = 5) -> List[str]:
        """
        Get recent assistant responses.

        Args:
            count: Number of responses to retrieve

        Returns:
            List of recent responses (newest first)
        """
        recent = self.history[-count:]
        return [turn.assistant_response for turn in reversed(recent)]

    def get_conversation_context(self, max_turns: int = 3) -> str:
        """
        Get formatted conversation context for LLM prompting.

        Args:
            max_turns: Number of recent turns to include

        Returns:
            Formatted context string
        """
        recent = self.history[-max_turns:]

        context_parts = []
        for turn in recent:
            context_parts.append(f"User: {turn.user_message}")
            context_parts.append(f"Assistant: {turn.assistant_response}")

        return "\n".join(context_parts)

    def detect_continuation_request(self, user_message: str) -> bool:
        """
        Detect if user is asking to continue previous interaction.

        Args:
            user_message: User's current message

        Returns:
            True if continuation detected, False otherwise
        """
        message_lower = user_message.lower()

        continuation_phrases = [
            "another",
            "another one",
            "more",
            "tell me more",
            "keep going",
            "continue",
            "again",
            "one more",
            "what else",
            "do another",
        ]

        return any(phrase in message_lower for phrase in continuation_phrases)

    def get_continuation_context(self, user_message: str) -> Optional[dict]:
        """
        Get context for a continuation request.

        Args:
            user_message: User's continuation message

        Returns:
            Context dictionary with previous interaction details
        """
        if not self.detect_continuation_request(user_message):
            return None

        if not self.history:
            return None

        # Get most recent turn
        last_turn = self.history[-1]

        return {
            "previous_user_message": last_turn.user_message,
            "previous_response": last_turn.assistant_response,
            "previous_intent": last_turn.intent,
            "previous_task_type": last_turn.task_type,
        }

    def get_theme(self) -> Optional[str]:
        """
        Get current conversation theme/topic.

        Returns:
            Theme string or None
        """
        return self.current_theme

    def update_theme(self, theme: str) -> None:
        """
        Update conversation theme.

        Args:
            theme: New theme
        """
        self.current_theme = theme
        logger.debug(f"Updated conversation theme: {theme}")

    def clear(self) -> None:
        """Clear conversation history."""
        self.history.clear()
        self.current_theme = None
        self.conversation_start_time = datetime.now()
        logger.info("Conversation context cleared")

    def get_stats(self) -> dict:
        """
        Get conversation statistics.

        Returns:
            Dictionary with conversation stats
        """
        if not self.history:
            return {
                "total_turns": 0,
                "duration_seconds": 0,
                "theme": None,
            }

        duration = (datetime.now() - self.conversation_start_time).total_seconds()

        return {
            "total_turns": len(self.history),
            "duration_seconds": round(duration, 2),
            "theme": self.current_theme,
            "last_activity": self.history[-1].timestamp.isoformat() if self.history else None,
        }
