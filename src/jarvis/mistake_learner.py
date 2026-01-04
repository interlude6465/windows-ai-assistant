"""
Mistake learner module for persisting and retrieving learned fixes.

Stores error patterns and their fixes to a SQLite database, enabling Jarvis
to learn from mistakes and apply fixes to future code generation.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LearnedFix(BaseModel):
    """Represents a learned fix pattern."""

    id: Optional[int] = Field(default=None, description="Database ID")
    error_type: str = Field(description="Type of error (e.g., ImportError, SyntaxError)")
    error_pattern: str = Field(description="Pattern or description of the error")
    fix_strategy: str = Field(
        description="Strategy used to fix (e.g., regenerate_code, add_retry_logic)"
    )
    code_snippet: str = Field(description="Code snippet of the fix")
    context: str = Field(default="", description="Additional context about when fix applies")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    success_count: int = Field(default=1, description="Number of times this fix worked")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class MistakeLearner:
    """
    Learns from code execution mistakes and stores fixes.

    Maintains a database of error patterns and their fixes, allowing Jarvis
    to inject learned patterns into future code generation.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize mistake learner.

        Args:
            db_path: Path to SQLite database file (defaults to ~/.jarvis/data/mistakes.db)
        """
        if db_path is None:
            db_path = Path.home() / ".jarvis" / "data" / "mistakes.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"MistakeLearner initialized with database: {self.db_path}")
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema if not exists."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_fixes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT NOT NULL,
                    error_pattern TEXT NOT NULL,
                    fix_strategy TEXT NOT NULL,
                    code_snippet TEXT NOT NULL,
                    context TEXT,
                    tags TEXT,
                    success_count INTEGER DEFAULT 1,
                    timestamp TEXT NOT NULL
                )
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_error_type ON learned_fixes(error_type)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tags ON learned_fixes(tags)
            """
            )
            conn.commit()
            logger.debug("Database schema initialized")
        finally:
            conn.close()

    def store_fix(
        self,
        error_type: str,
        error_pattern: str,
        fix_strategy: str,
        code_snippet: str,
        context: str = "",
        tags: Optional[List[str]] = None,
    ) -> int:
        """
        Store a learned fix in the database.

        Args:
            error_type: Type of error that occurred
            error_pattern: Pattern or description of the error
            fix_strategy: Strategy used to fix the error
            code_snippet: Code snippet that fixed the issue
            context: Additional context about when the fix applies
            tags: Tags for categorization (e.g., ["file_ops", "windows"])

        Returns:
            Database ID of stored fix
        """
        if tags is None:
            tags = []

        learned_fix = LearnedFix(
            error_type=error_type,
            error_pattern=error_pattern,
            fix_strategy=fix_strategy,
            code_snippet=code_snippet,
            context=context,
            tags=tags,
        )

        logger.info(
            f"Storing learned fix: {error_type} -> {fix_strategy} "
            f"(tags: {', '.join(tags) if tags else 'none'})"
        )

        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            cursor = conn.cursor()

            # Check if similar fix already exists
            cursor.execute(
                """
                SELECT id, success_count FROM learned_fixes
                WHERE error_type = ? AND error_pattern = ?
                LIMIT 1
            """,
                (error_type, error_pattern),
            )
            existing = cursor.fetchone()

            if existing:
                # Increment success count for existing fix
                fix_id, success_count = existing
                cursor.execute(
                    """
                    UPDATE learned_fixes
                    SET success_count = ?, code_snippet = ?, timestamp = ?
                    WHERE id = ?
                """,
                    (success_count + 1, code_snippet, learned_fix.timestamp, fix_id),
                )
                logger.info(f"Updated existing fix #{fix_id} (success count: {success_count + 1})")
                conn.commit()
                return int(fix_id)
            else:
                # Insert new fix
                cursor.execute(
                    """
                    INSERT INTO learned_fixes
                    (error_type, error_pattern, fix_strategy, code_snippet,
                     context, tags, success_count, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        learned_fix.error_type,
                        learned_fix.error_pattern,
                        learned_fix.fix_strategy,
                        learned_fix.code_snippet,
                        learned_fix.context,
                        json.dumps(learned_fix.tags),
                        learned_fix.success_count,
                        learned_fix.timestamp,
                    ),
                )
                conn.commit()
                fix_id = cursor.lastrowid
                logger.info(f"Stored new learned fix #{fix_id}")
                return int(fix_id) if fix_id is not None else 0
        finally:
            conn.close()

    def retrieve_fixes(
        self,
        error_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[LearnedFix]:
        """
        Retrieve relevant learned fixes from database.

        Args:
            error_type: Filter by error type (optional)
            tags: Filter by tags (optional)
            limit: Maximum number of fixes to retrieve

        Returns:
            List of LearnedFix objects, sorted by success count (descending)
        """
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            cursor = conn.cursor()

            query = """
                SELECT id, error_type, error_pattern, fix_strategy, code_snippet,
                       context, tags, success_count, timestamp
                FROM learned_fixes
                WHERE 1=1
            """
            params: list = []

            if error_type:
                query += " AND error_type = ?"
                params.append(error_type)

            if tags:
                # Match any of the provided tags
                tag_conditions = " OR ".join(["tags LIKE ?" for _ in tags])
                query += f" AND ({tag_conditions})"
                params.extend([f"%{tag}%" for tag in tags])

            query += " ORDER BY success_count DESC, timestamp DESC LIMIT ?"
            params.append(str(limit))

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            fixes = []
            for row in rows:
                fix = LearnedFix(
                    id=row[0],
                    error_type=row[1],
                    error_pattern=row[2],
                    fix_strategy=row[3],
                    code_snippet=row[4],
                    context=row[5],
                    tags=json.loads(row[6]) if row[6] else [],
                    success_count=row[7],
                    timestamp=row[8],
                )
                fixes.append(fix)

            logger.debug(
                f"Retrieved {len(fixes)} learned fixes " f"(error_type={error_type}, tags={tags})"
            )
            return fixes
        finally:
            conn.close()

    def get_all_fixes(self, limit: int = 100) -> List[LearnedFix]:
        """
        Get all learned fixes.

        Args:
            limit: Maximum number of fixes to retrieve

        Returns:
            List of all LearnedFix objects
        """
        return self.retrieve_fixes(limit=limit)

    def clear_database(self) -> None:
        """Clear all learned fixes from database."""
        logger.warning("Clearing all learned fixes from database")
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM learned_fixes")
            conn.commit()
            logger.info("Database cleared")
        finally:
            conn.close()

    def format_fixes_for_prompt(
        self,
        fixes: List[LearnedFix],
        max_fixes: int = 3,
    ) -> str:
        """
        Format learned fixes for injection into LLM prompts.

        Args:
            fixes: List of LearnedFix objects
            max_fixes: Maximum number of fixes to include

        Returns:
            Formatted string for prompt injection
        """
        if not fixes:
            return ""

        fixes_to_use = fixes[:max_fixes]

        prompt_text = "\n\n**LEARNED PATTERNS FROM PREVIOUS FIXES:**\n"
        for i, fix in enumerate(fixes_to_use, 1):
            prompt_text += f"\n{i}. {fix.error_type} ({fix.fix_strategy})\n"
            prompt_text += f"   Problem: {fix.error_pattern}\n"
            if fix.context:
                prompt_text += f"   Context: {fix.context}\n"
            prompt_text += f"   Solution pattern:\n```python\n{fix.code_snippet[:300]}\n```\n"
            if fix.success_count > 1:
                prompt_text += f"   (This pattern has worked {fix.success_count} times)\n"

        prompt_text += "\nApply these learned patterns when relevant to avoid repeating mistakes.\n"
        return prompt_text
