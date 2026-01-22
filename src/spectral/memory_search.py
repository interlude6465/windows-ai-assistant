"""
Memory search module.

Provides search capabilities for past conversations and executions,
including semantic search using keyword matching (with future support for embeddings).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from spectral.llm_client import LLMClient
from spectral.memory_models import ConversationMemory, ExecutionMemory

logger = logging.getLogger(__name__)


class MemorySearch:
    """Search capabilities for memory system."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize memory search.

        Args:
            llm_client: Optional LLM client for enhanced semantic search
        """
        self.llm_client = llm_client
        logger.info("MemorySearch initialized")

    def search_by_description(
        self, query: str, executions: List[ExecutionMemory], limit: int = 5
    ) -> List[ExecutionMemory]:
        """
        Find past executions by semantic search.

        Uses keyword matching and LLM-assisted semantic understanding.

        Args:
            query: Search query (e.g., "web scraper")
            executions: List of executions to search
            limit: Maximum number of results to return

        Returns:
            List of matching executions, sorted by relevance
        """
        # Load any metadata-based executions that aren't already in the list
        all_executions = list(executions)
        metadata_executions = self.load_execution_metadata()

        # Merge, avoiding duplicates by ID
        existing_ids = {e.execution_id for e in all_executions}
        for me in metadata_executions:
            if me.execution_id not in existing_ids:
                all_executions.append(me)

        logger.info(f"Searching {len(all_executions)} executions for: {query}")
        query_lower = query.lower()

        # Score each execution based on multiple factors
        scored_executions = []
        for execution in all_executions:
            score = self._calculate_relevance_score(query_lower, execution)
            if score > 0:
                scored_executions.append((score, execution))

        # Sort by score descending and return top N
        scored_executions.sort(key=lambda x: x[0], reverse=True)
        results = [e for score, e in scored_executions[:limit]]

        logger.info(f"Found {len(results)} matching executions")
        return results

    def load_execution_metadata(self) -> List[ExecutionMemory]:
        """
        Load execution metadata from ~/.spectral/execution_metadata/

        Returns:
            List of ExecutionMemory objects
        """
        metadata_dir = Path.home() / ".spectral" / "execution_metadata"
        if not metadata_dir.exists():
            return []

        executions = []
        for meta_file in metadata_dir.glob("*.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Map metadata fields to ExecutionMemory
                # Metadata: run_id, timestamp, prompt, filename, desktop_path,
                # sandbox_path, code, execution_status, execution_output,
                # execution_error, attempts, last_error

                # ExecutionMemory: execution_id, timestamp, user_request,
                # description, code_generated, file_locations, output,
                # success, tags, execution_time_ms, error_message

                raw_file_locations = data.get("file_locations")
                if not raw_file_locations:
                    raw_file_locations = [data.get("desktop_path"), data.get("sandbox_path")]

                if isinstance(raw_file_locations, (list, tuple)):
                    file_locations = [str(loc) for loc in raw_file_locations if loc]
                else:
                    file_locations = [str(raw_file_locations)] if raw_file_locations else []

                exec_mem = ExecutionMemory(
                    execution_id=data.get("run_id", meta_file.stem),
                    timestamp=datetime.fromisoformat(
                        data.get("timestamp", datetime.now().isoformat())
                    ),
                    user_request=data.get("prompt", ""),
                    description=f"Generated {data.get('filename', 'main.py')}",
                    code_generated=data.get("code", ""),
                    file_locations=file_locations,
                    output=data.get("execution_output", ""),
                    success=data.get("execution_status") == "success",
                    tags=["metadata_load"],
                    error_message=data.get("execution_error") or data.get("last_error"),
                )

                # Optional self-heal: persist cleaned file_locations back to disk
                if data.get("file_locations") != file_locations:
                    try:
                        data["file_locations"] = file_locations
                        with open(meta_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                    except Exception:
                        pass

                executions.append(exec_mem)
            except Exception as e:
                logger.warning(f"Failed to load execution metadata from {meta_file}: {e}")

        return executions

    def search_conversations(
        self, query: str, conversations: List[ConversationMemory], limit: int = 5
    ) -> List[ConversationMemory]:
        """
        Search past conversations.

        Args:
            query: Search query
            conversations: List of conversations to search
            limit: Maximum number of results

        Returns:
            List of matching conversations
        """
        logger.info(f"Searching {len(conversations)} conversations for: {query}")
        query_lower = query.lower()

        scored_conversations = []
        for conv in conversations:
            score = self._calculate_conversation_score(query_lower, conv)
            if score > 0:
                scored_conversations.append((score, conv))

        scored_conversations.sort(key=lambda x: x[0], reverse=True)
        results = [c for score, c in scored_conversations[:limit]]

        logger.info(f"Found {len(results)} matching conversations")
        return results

    def _calculate_relevance_score(self, query: str, execution: ExecutionMemory) -> float:
        """
        Calculate relevance score for an execution.

        Args:
            query: Lowercase search query
            execution: Execution to score

        Returns:
            Relevance score (higher = more relevant)
        """
        score = 0.0

        # Exact match in description
        if query in execution.description.lower():
            score += 10.0

        # Partial match in description (word-level)
        query_words = query.split()
        desc_words = execution.description.lower().split()
        if any(word in desc_words for word in query_words):
            score += 5.0

        # Match in tags
        for tag in execution.tags:
            if query in tag.lower():
                score += 7.0

        # Match in user request
        if query in execution.user_request.lower():
            score += 8.0

        # Match in file locations
        for file_loc in execution.file_locations:
            if query in file_loc.lower():
                score += 6.0

        # Match in code (lower weight)
        if query in execution.code_generated.lower():
            score += 3.0

        # Time decay: more recent executions get slight boost
        # This can be adjusted based on requirements

        return score

    def _calculate_conversation_score(self, query: str, conversation: ConversationMemory) -> float:
        """
        Calculate relevance score for a conversation.

        Args:
            query: Lowercase search query
            conversation: Conversation to score

        Returns:
            Relevance score
        """
        score = 0.0

        # Check user message
        if query in conversation.user_message.lower():
            score += 10.0

        # Check assistant response
        if query in conversation.assistant_response.lower():
            score += 8.0

        # Check context tags
        for tag in conversation.context_tags:
            if query in tag.lower():
                score += 7.0

        # Check execution descriptions
        for exec_mem in conversation.execution_history:
            if query in exec_mem.description.lower():
                score += 6.0

        return score

    def find_similar_executions(
        self, execution: ExecutionMemory, all_executions: List[ExecutionMemory], limit: int = 3
    ) -> List[ExecutionMemory]:
        """
        Find executions similar to a given execution.

        Args:
            execution: Reference execution
            all_executions: All executions to search
            limit: Maximum number of results

        Returns:
            List of similar executions
        """
        logger.info(f"Finding executions similar to: {execution.description}")

        # Use description as query
        similar = self.search_by_description(
            execution.description,
            [e for e in all_executions if e.execution_id != execution.execution_id],
            limit,
        )

        logger.info(f"Found {len(similar)} similar executions")
        return similar

    def get_recent_context(
        self, conversations: List[ConversationMemory], num_turns: int = 5
    ) -> str:
        """
        Get recent conversation context for injection.

        Args:
            conversations: List of conversations
            num_turns: Number of recent turns to include

        Returns:
            Formatted context string
        """
        # Sort by timestamp descending
        sorted_convos = sorted(conversations, key=lambda c: c.timestamp, reverse=True)
        recent = sorted_convos[:num_turns]

        if not recent:
            return ""

        context_parts = []
        for conv in reversed(recent):  # Oldest first for chronological order
            context_parts.append(f"User: {conv.user_message}")
            context_parts.append(f"Assistant: {conv.assistant_response}")

            if conv.execution_history:
                for exec_mem in conv.execution_history:
                    if exec_mem.description:
                        context_parts.append(f"  - Executed: {exec_mem.description}")

        return "\n".join(context_parts)
