"""Personality profile mixin for the Social Matching Service."""

from typing import Dict, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

from education_system.university_system.modules.domain.student_affairs.social_matching.services.constants import PERSONALITY_TYPES, GROUP_SIZE_PREFERENCES, ACTIVITY_LEVELS


class PersonalityMixin:
    """Methods for managing user personality profiles."""

    def set_personality_profile(self, user_id: str, personality_type: str,
                               extroversion_score: int, openness_score: int,
                               social_preference: str, group_size_pref: str,
                               activity_level: str) -> bool:
        """
        Set or update a user's personality profile.

        Args:
            user_id: User identifier
            personality_type: Personality type
            extroversion_score: Score 1-10
            openness_score: Score 1-10
            social_preference: Social preference description
            group_size_pref: Preferred group size
            activity_level: Preferred activity level

        Returns:
            True if successful
        """
        if personality_type not in PERSONALITY_TYPES:
            raise ValueError(f"Invalid personality type. Must be one of: {PERSONALITY_TYPES}")

        if group_size_pref not in GROUP_SIZE_PREFERENCES:
            raise ValueError(f"Invalid group size. Must be one of: {GROUP_SIZE_PREFERENCES}")

        if activity_level not in ACTIVITY_LEVELS:
            raise ValueError(f"Invalid activity level. Must be one of: {ACTIVITY_LEVELS}")

        with transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_personality
                (user_id, personality_type, extroversion_score, openness_score,
                 social_preference, group_size_preference, activity_level, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, personality_type, extroversion_score, openness_score,
                  social_preference, group_size_pref, activity_level))

        log_activity('update', 'personality_profile', user_id=user_id)
        return True

    def get_personality_profile(self, user_id: str) -> Optional[Dict]:
        """Get a user's personality profile."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT personality_type, extroversion_score, openness_score,
                       social_preference, group_size_preference, activity_level, updated_at
                FROM user_personality
                WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'personality_type': row[0],
                    'extroversion_score': row[1],
                    'openness_score': row[2],
                    'social_preference': row[3],
                    'group_size_preference': row[4],
                    'activity_level': row[5],
                    'updated_at': row[6]
                }
        return None
