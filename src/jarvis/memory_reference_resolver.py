"""
Memory reference resolver module.

Handles user references to past executions, enabling natural language
queries like "run that program" or "the web scraper we made earlier".
"""

import logging
import re
from typing import List, Optional

from jarvis.memory_models import ExecutionMemory

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """Resolve user references to past executions."""

    def __init__(self) -> None:
        """Initialize the reference resolver."""
        # Patterns for different reference types
        self.patterns = {
            "most_recent_program": r"(?:run|execute|start|open|launch|the)?\s*that\s*(?:program|code|script|file)",
            "the_named_program": r"(?:run|execute|start|open|launch)?\s*the\s+(\w+(?:\s+\w+)*)\s*(?:program|code|script|file)?",
            "the_named_item": r"the\s+(\w+(?:\s+\w+)*)\s+we\s+(?:made|created|built|wrote)",
            "the_named_any": r"the\s+(\w+(?:\s+\w+)*)",
            "earlier_reference": r"(?:run|execute|start|open|launch)?\s*(?:it|earlier|before|previously)",
            "location_reference": r"(?:where|find|locate)\s+(?:the\s+)?(\w+(?:\s+\w+)*)",
            "similarity_request": r"(?:make|create|build)\s+(?:something\s+)?like\s+(?:the\s+)?(\w+(?:\s+\w+)*)",
        }

    def resolve_reference(
        self, user_message: str, recent_executions: List[ExecutionMemory]
    ) -> Optional[ExecutionMemory]:
        """
        Resolve references like:
        - "that program" → most recent program
        - "the web scraper" → execution with "web scraper" in description
        - "the file we made" → most recent file creation
        - "earlier" → most recent execution
        - "where is the scraper" → find location of scraper

        Args:
            user_message: User's natural language message
            recent_executions: List of recent executions to search

        Returns:
            The referenced execution or None
        """
        if not recent_executions:
            logger.debug("No recent executions available for reference resolution")
            return None

        user_message_lower = user_message.lower()

        # Try each pattern
        for pattern_type, pattern in self.patterns.items():
            match = re.search(pattern, user_message_lower)
            if match:
                logger.info(f"Matched reference pattern: {pattern_type}")
                if pattern_type == "most_recent_program":
                    return self._resolve_most_recent(recent_executions, is_program=True)
                elif pattern_type == "the_named_program":
                    subject = match.group(1)
                    return self._resolve_by_name(recent_executions, subject)
                elif pattern_type == "the_named_item":
                    subject = match.group(1)
                    return self._resolve_by_name(recent_executions, subject)
                elif pattern_type == "earlier_reference":
                    return self._resolve_most_recent(recent_executions)
                elif pattern_type == "location_reference":
                    subject = match.group(1)
                    return self._resolve_by_name(recent_executions, subject)
                elif pattern_type == "similarity_request":
                    subject = match.group(1)
                    return self._resolve_by_name(recent_executions, subject)

        logger.debug("No reference pattern matched")
        return None

    def _resolve_most_recent(
        self, executions: List[ExecutionMemory], is_program: bool = False
    ) -> Optional[ExecutionMemory]:
        """
        Get the most recent execution.

        Args:
            executions: List of executions
            is_program: If True, filter for program-like executions

        Returns:
            Most recent execution or None
        """
        # Sort by timestamp descending
        sorted_executions = sorted(executions, key=lambda e: e.timestamp, reverse=True)

        if is_program:
            # Filter for program-like executions (code generated + file created)
            program_executions = [
                e
                for e in sorted_executions
                if e.code_generated and (e.file_locations or "script" in e.tags)
            ]
            if program_executions:
                logger.debug(f"Found most recent program: {program_executions[0].description}")
                return program_executions[0]

        if sorted_executions:
            logger.debug(f"Found most recent execution: {sorted_executions[0].description}")
            return sorted_executions[0]

        return None

    def _resolve_by_name(
        self, executions: List[ExecutionMemory], name: str
    ) -> Optional[ExecutionMemory]:
        """
        Resolve reference by searching for name in descriptions/tags.

        Args:
            executions: List of executions
            name: Name to search for

        Returns:
            Matching execution or None
        """
        name_lower = name.lower()

        # Search in descriptions
        matches = []
        for execution in executions:
            if (
                name_lower in execution.description.lower()
                or any(name_lower in tag.lower() for tag in execution.tags)
                or any(name_lower in file.lower() for file in execution.file_locations)
            ):
                matches.append(execution)

        if matches:
            # Return most recent match
            sorted_matches = sorted(matches, key=lambda e: e.timestamp, reverse=True)
            logger.debug(f"Found {len(matches)} matches for '{name}', using most recent")
            return sorted_matches[0]

        logger.debug(f"No matches found for name: {name}")
        return None

    def extract_subject(self, user_message: str) -> Optional[str]:
        """
        Extract the subject being referenced from the user message.

        Args:
            user_message: User's message

        Returns:
            Extracted subject or None
        """
        # Try to extract what they're referring to
        for pattern_type, pattern in self.patterns.items():
            match = re.search(pattern, user_message.lower())
            if match and match.groups():
                return match.group(1)

        return None

    def is_reference_query(self, user_message: str) -> bool:
        """
        Check if user message contains a reference to past work.

        Args:
            user_message: User's message

        Returns:
            True if message contains a reference
        """
        user_message_lower = user_message.lower()
        for pattern in self.patterns.values():
            if re.search(pattern, user_message_lower):
                return True
        return False
