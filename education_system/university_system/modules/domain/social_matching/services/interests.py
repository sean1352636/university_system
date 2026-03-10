"""Interest management mixin for the Social Matching Service."""

from education_system.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

from .constants import INTEREST_CATEGORIES


class InterestMixin:
    """Methods for managing user interests."""

    def add_user_interest(self, user_id: str, category: str, interest_name: str,
                         interest_level: int = 5, is_public: bool = True) -> bool:
        """
        Add an interest to a user's profile.

        Args:
            user_id: User identifier
            category: Interest category
            interest_name: Name of the interest
            interest_level: Interest level (1-10)
            is_public: Whether interest is public

        Returns:
            True if successful
        """
        if category not in INTEREST_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {INTEREST_CATEGORIES}")

        if not 1 <= interest_level <= 10:
            raise ValueError("Interest level must be between 1 and 10")

        try:
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO user_interests
                    (user_id, interest_category, interest_name, interest_level, is_public)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, category, interest_name, interest_level, 1 if is_public else 0))

            log_activity('create', 'user_interest', user_id=user_id,
                        details={'category': category, 'interest': interest_name})
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_user_interest(self, user_id: str, interest_id: int) -> bool:
        """Remove an interest from a user's profile."""
        with transaction() as conn:
            cursor = conn.execute("""
                DELETE FROM user_interests
                WHERE interest_id = ? AND user_id = ?
            """, (interest_id, user_id))

            if cursor.rowcount > 0:
                log_activity('delete', 'user_interest', user_id=user_id,
                           details={'interest_id': interest_id})
                return True
        return False

    def get_user_interests(self, user_id: str) -> List[Dict]:
        """Get all interests for a user."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT interest_id, interest_category, interest_name,
                       interest_level, is_public, created_at
                FROM user_interests
                WHERE user_id = ?
                ORDER BY interest_category, interest_name
            """, (user_id,))

            interests = []
            for row in cursor.fetchall():
                interests.append({
                    'interest_id': row[0],
                    'category': row[1],
                    'name': row[2],
                    'level': row[3],
                    'is_public': bool(row[4]),
                    'created_at': row[5]
                })
            return interests

    def update_interest_level(self, user_id: str, interest_id: int, new_level: int) -> bool:
        """Update the level of an existing interest."""
        if not 1 <= new_level <= 10:
            raise ValueError("Interest level must be between 1 and 10")

        with transaction() as conn:
            cursor = conn.execute("""
                UPDATE user_interests
                SET interest_level = ?
                WHERE interest_id = ? AND user_id = ?
            """, (new_level, interest_id, user_id))

            return cursor.rowcount > 0
