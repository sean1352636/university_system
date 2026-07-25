"""Privacy settings mixin for the Social Matching Service."""

from typing import Dict

from education_system.systems.university.infrastructure.database.db import get_connection, transaction


class PrivacyMixin:
    """Methods for managing user privacy settings."""

    def set_privacy_settings(self, user_id: str, allow_matching: bool = True,
                            show_profile: bool = True, allow_messages: bool = True,
                            show_interests: bool = True, show_in_search: bool = True,
                            match_same_major: bool = False,
                            match_same_year: bool = False) -> bool:
        """Set privacy settings for a user."""
        with transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_privacy_settings
                (user_id, allow_matching, show_profile, allow_messages, show_interests,
                 show_in_search, match_same_major, match_same_year, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, allow_matching, show_profile, allow_messages, show_interests,
                  show_in_search, match_same_major, match_same_year))

        return True

    def get_privacy_settings(self, user_id: str) -> Dict:
        """Get privacy settings for a user."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT allow_matching, show_profile, allow_messages, show_interests,
                       show_in_search, match_same_major, match_same_year
                FROM user_privacy_settings
                WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'allow_matching': bool(row[0]),
                    'show_profile': bool(row[1]),
                    'allow_messages': bool(row[2]),
                    'show_interests': bool(row[3]),
                    'show_in_search': bool(row[4]),
                    'match_same_major': bool(row[5]),
                    'match_same_year': bool(row[6])
                }

        # Return defaults if no settings exist
        return {
            'allow_matching': True,
            'show_profile': True,
            'allow_messages': True,
            'show_interests': True,
            'show_in_search': True,
            'match_same_major': False,
            'match_same_year': False
        }
