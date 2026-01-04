"""
Mistake learner module for persisting and applying learned fixes.

Stores error patterns and successful fixes in a database for reuse,
preventing the same errors from happening twice.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jarvis.config import JarvisConfig

logger = logging.getLogger(__name__)


class LearningPattern:
    """Represents a learned pattern from a fix."""

    def __init__(
        self,
        error_type: str,
        error_pattern: str,
        fix_applied: str,
        code_snippet: str,
        tags: List[str],
        source_language: str = "python",
    ):
        self.error_type = error_type
        self.error_pattern = error_pattern
        self.fix_applied = fix_applied
        self.code_snippet = code_snippet
        self.tags = tags
        self.source_language = source_language
        self.timestamp = datetime.now()
        self.priority = 0.5  # Base priority for sorting

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "error_type": self.error_type,
            "error_pattern": self.error_pattern,
            "fix_applied": self.fix_applied,
            "code_snippet": self.code_snippet,
            "tags": self.tags,
            "source_language": self.source_language,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
        }


class MistakeLearner:
    """Learn from mistakes and store fixes for future use."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize mistake learner.

        Args:
            db_path: Path to learning database (default: ~/.jarvis/data/mistakes.db)
        """
        if db_path is None:
            config = JarvisConfig()
            db_path = config.storage.data_dir / "mistakes.db"

        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_database()
        logger.info(f"MistakeLearner initialized with database: {db_path}")

    def _init_database(self) -> None:
        """Initialize SQLite database with learning patterns table."""
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT NOT NULL,
                    error_pattern TEXT NOT NULL,
                    fix_applied TEXT NOT NULL,
                    code_snippet TEXT,
                    tags TEXT,  -- JSON array stored as string
                    source_language TEXT DEFAULT 'python',
                    timestamp TEXT NOT NULL,
                    priority REAL DEFAULT 0.5,
                    usage_count INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 1.0,
                    last_used TEXT
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_error_type ON learned_patterns(error_type)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tags ON learned_patterns(tags)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp ON learned_patterns(timestamp DESC)
            """
            )

            conn.commit()
            conn.close()

    def store_pattern(self, pattern: LearningPattern) -> int:
        """
        Store a learned pattern from a fix.

        Args:
            pattern: LearningPattern to store

        Returns:
            Pattern ID in database
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO learned_patterns (
                        error_type, error_pattern, fix_applied, code_snippet, tags,
                        source_language, timestamp, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pattern.error_type,
                        pattern.error_pattern,
                        pattern.fix_applied,
                        pattern.code_snippet,
                        json.dumps(pattern.tags),
                        pattern.source_language,
                        pattern.timestamp.isoformat(),
                        pattern.priority,
                    ),
                )

                pattern_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Stored learning pattern {pattern_id}: {pattern.error_type}")
                return pattern_id

            except Exception as e:
                logger.error(f"Failed to store pattern: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def query_patterns(
        self,
        error_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        min_priority: float = 0.3,
    ) -> List[Dict]:
        """
        Query learned patterns from database.

        Args:
            error_type: Filter by error type (e.g., "FileNotFoundError")
            tags: Filter by tags (e.g., ["file_ops", "windows"])
            limit: Maximum number of patterns to return
            min_priority: Minimum priority threshold (0.0-1.0)

        Returns:
            List of pattern dictionaries sorted by relevance
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()

            try:
                query = """
                    SELECT
                        id, error_type, error_pattern, fix_applied, code_snippet,
                        tags, source_language, timestamp, priority, usage_count, success_rate
                    FROM learned_patterns
                    WHERE priority >= ?
                """
                params = [min_priority]

                if error_type:
                    query += " AND error_type = ?"
                    params.append(error_type)

                if tags:
                    for tag in tags:
                        query += " AND tags LIKE ?"
                        params.append(f"%{tag}%")

                query += " ORDER BY success_rate DESC, priority DESC, timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                patterns = []
                for row in rows:
                    pattern = {
                        "id": row[0],
                        "error_type": row[1],
                        "error_pattern": row[2],
                        "fix_applied": row[3],
                        "code_snippet": row[4],
                        "tags": json.loads(row[5]),
                        "source_language": row[6],
                        "timestamp": row[7],
                        "priority": row[8],
                        "usage_count": row[9],
                        "success_rate": row[10],
                    }
                    patterns.append(pattern)

                logger.debug(f"Found {len(patterns)} relevant patterns")
                return patterns

            except Exception as e:
                logger.error(f"Failed to query patterns: {e}")
                return []
            finally:
                conn.close()

    def get_patterns_for_generation(
        self,
        tags: List[str] = None,
        error_hints: List[str] = None,
    ) -> List[Dict]:
        """
        Get patterns to inject into code generation prompts.

        Args:
            tags: Primary tags to match (e.g., ["file_ops", "windows"])
            error_hints: Error types to prioritize (e.g., ["FileNotFoundError"])

        Returns:
            Relevant pattern suggestions
        """
        if tags is None:
            tags = ["general"]

        patterns = []

        # Query by error hints first
        if error_hints:
            for error_type in error_hints:
                patterns.extend(self.query_patterns(error_type=error_type, tags=tags, limit=5))

        # Query by tags
        patterns.extend(self.query_patterns(tags=tags, limit=10))

        # Remove duplicates and sort by success_rate
        seen_ids = set()
        unique_patterns = []
        for pattern in patterns:
            if pattern["id"] not in seen_ids:
                seen_ids.add(pattern["id"])
                unique_patterns.append(pattern)

        unique_patterns.sort(key=lambda x: x["success_rate"], reverse=True)

        return unique_patterns[:10]  # Return top 10

    def increment_usage(self, pattern_id: int, success: bool) -> None:
        """
        Update usage statistics for a pattern.

        Args:
            pattern_id: Pattern ID
            success: Whether the pattern led to success
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    UPDATE learned_patterns
                    SET
                        usage_count = usage_count + 1,
                        success_rate = (success_rate * (usage_count - 1) + ?) / NULLIF(usage_count, 0),
                        last_used = ?
                    WHERE id = ?
                """,
                    (
                        1.0 if success else 0.0,
                        datetime.now().isoformat(),
                        pattern_id,
                    ),
                )

                conn.commit()

                logger.debug(f"Updated usage stats for pattern {pattern_id}")

            except Exception as e:
                logger.error(f"Failed to update usage stats: {e}")
                conn.rollback()
            finally:
                conn.close()

    def get_pattern_summary(self) -> Dict:
        """
        Get summary statistics of learned patterns.

        Returns:
            Dictionary with summary statistics
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT COUNT(*) FROM learned_patterns")
                total_patterns = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT error_type, COUNT(*) FROM learned_patterns GROUP BY error_type"
                )
                error_type_counts = dict(cursor.fetchall())

                cursor.execute(
                    "SELECT AVG(success_rate), MAX(success_rate), MIN(success_rate) FROM learned_patterns"
                )
                success_stats = cursor.fetchone()

                return {
                    "total_patterns": total_patterns,
                    "error_types": error_type_counts,
                    "average_success_rate": success_stats[0] or 0.0,
                    "max_success_rate": success_stats[1] or 0.0,
                    "min_success_rate": success_stats[2] or 0.0,
                }

            except Exception as e:
                logger.error(f"Failed to get pattern summary: {e}")
                return {}
            finally:
                conn.close()
