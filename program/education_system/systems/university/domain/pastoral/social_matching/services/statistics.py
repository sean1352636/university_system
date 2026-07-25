"""Statistics and analytics mixin for the Social Matching Service."""

from typing import Dict

from education_system.systems.university.infrastructure.database.db import get_connection


class StatisticsMixin:
    """Methods for user social matching statistics."""

    def get_user_statistics(self, user_id: str) -> Dict:
        """Get statistics for a user's social matching activity."""
        with get_connection() as conn:
            stats = {}

            # Total interests
            cursor = conn.execute("""
                SELECT COUNT(*) FROM user_interests WHERE user_id = ?
            """, (user_id,))
            stats['total_interests'] = cursor.fetchone()[0]

            # Total matches
            cursor = conn.execute("""
                SELECT COUNT(*) FROM interest_matches
                WHERE user1_id = ? AND compatibility_score >= 30
            """, (user_id,))
            stats['total_matches'] = cursor.fetchone()[0]

            # Buddy requests sent/received
            cursor = conn.execute("""
                SELECT COUNT(*) FROM buddy_requests WHERE sender_id = ?
            """, (user_id,))
            stats['requests_sent'] = cursor.fetchone()[0]

            cursor = conn.execute("""
                SELECT COUNT(*) FROM buddy_requests WHERE receiver_id = ?
            """, (user_id,))
            stats['requests_received'] = cursor.fetchone()[0]

            # Teams joined
            cursor = conn.execute("""
                SELECT COUNT(*) FROM team_members WHERE user_id = ?
            """, (user_id,))
            stats['teams_joined'] = cursor.fetchone()[0]

            # Activities joined
            cursor = conn.execute("""
                SELECT COUNT(*) FROM activity_participants WHERE user_id = ?
            """, (user_id,))
            stats['activities_joined'] = cursor.fetchone()[0]

            return stats
