"""
Memory models for persistent conversation and execution tracking.

Defines data models for storing conversations, executions, and related metadata
to enable Spectral to remember past interactions across sessions.
"""

import logging
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ExecutionMemory(BaseModel):
    """Records what was created and where during execution."""

    execution_id: str = Field(description="Unique identifier for this execution")
    timestamp: datetime = Field(description="When the execution occurred")
    user_request: str = Field(description="Original user request")
    description: str = Field(description="Semantic description of what was executed")
    code_generated: str = Field(description="Code that was generated and executed")
    file_locations: List[str] = Field(default_factory=list, description="Where files were created")
    output: str = Field(description="Execution output")
    success: bool = Field(description="Whether execution succeeded")

    @field_validator("file_locations", mode="before")
    @classmethod
    def _normalize_file_locations(cls, v: Any) -> List[str]:
        if v is None:
            return []

        if isinstance(v, str):
            return [v] if v else []

        if isinstance(v, (list, tuple)):
            cleaned: List[str] = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str):
                    if item:
                        cleaned.append(item)
                    continue
                try:
                    item_str = str(item)
                except Exception:
                    continue
                if item_str:
                    cleaned.append(item_str)
            return cleaned

        return []

    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization: web_scraper, file_io, etc.",
    )
    execution_time_ms: Optional[int] = Field(
        default=None, description="Execution time in milliseconds"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if execution failed"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversationMemory(BaseModel):
    """Full conversation turn with execution history."""

    turn_id: str = Field(description="Unique identifier for this turn")
    timestamp: datetime = Field(description="When this turn occurred")
    user_message: str = Field(description="User's message")
    assistant_response: str = Field(description="Assistant's response")
    execution_history: List[ExecutionMemory] = Field(
        default_factory=list, description="Executions performed during this turn"
    )
    context_tags: List[str] = Field(
        default_factory=list, description="Tags for context categorization"
    )
    embedding: Optional[List[float]] = Field(
        default=None, description="Embedding vector for semantic search"
    )
    session_id: Optional[str] = Field(default=None, description="Optional session identifier")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
