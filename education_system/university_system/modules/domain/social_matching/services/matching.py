"""Interest matching mixin for the Social Matching Service."""

import json
from typing import Dict, List, Tuple

from education_system.university_system.infrastructure.database.db import get_connection, transaction


class MatchingMixin:
    """Methods for interest-based matching and study abroad buddy finding."""

    def calculate_compatibility_score(self, user1_id: str, user2_id: str) -> Tuple[float, List[str]]:
        """
        Calculate compatibility score between two users based on interests.

        Returns:
            Tuple of (score, shared_interests)
        """
        with get_connection() as conn:
            # Get interests for both users
            cursor1 = conn.execute("""
                SELECT interest_category, interest_name, interest_level
                FROM user_interests
                WHERE user_id = ? AND is_public = 1
            """, (user1_id,))
            interests1 = {(row[0], row[1]): row[2] for row in cursor1.fetchall()}

            cursor2 = conn.execute("""
                SELECT interest_category, interest_name, interest_level
                FROM user_interests
                WHERE user_id = ? AND is_public = 1
            """, (user2_id,))
            interests2 = {(row[0], row[1]): row[2] for row in cursor2.fetchall()}

        if not interests1 or not interests2:
            return 0.0, []

        # Find shared interests
        shared = set(interests1.keys()) & set(interests2.keys())
        shared_interests = [f"{cat}: {name}" for cat, name in shared]

        if not shared:
            return 0.0, []

        # Calculate score based on shared interests and their levels
        score = 0.0
        for interest in shared:
            level1 = interests1[interest]
            level2 = interests2[interest]
            # Weight by average level and similarity
            avg_level = (level1 + level2) / 2
            similarity = 1 - abs(level1 - level2) / 10
            score += avg_level * similarity

        # Normalize score to 0-100
        max_possible = len(shared) * 10
        normalized_score = (score / max_possible) * 100 if max_possible > 0 else 0

        return round(normalized_score, 2), shared_interests

    def find_interest_matches(self, user_id: str, min_score: float = 30.0,
                             max_results: int = 20) -> List[Dict]:
        """
        Find users with similar interests.

        Args:
            user_id: User to find matches for
            min_score: Minimum compatibility score
            max_results: Maximum number of results

        Returns:
            List of matches with compatibility scores
        """
        # Get user's privacy settings
        privacy = self.get_privacy_settings(user_id)
        if not privacy['allow_matching']:
            return []

        matches = []
        with get_connection() as conn:
            # Get all users with public interests (excluding self)
            cursor = conn.execute("""
                SELECT DISTINCT user_id
                FROM user_interests
                WHERE is_public = 1 AND user_id != ?
            """, (user_id,))

            potential_matches = [row[0] for row in cursor.fetchall()]

        # Calculate compatibility for each potential match
        for other_user_id in potential_matches:
            # Check other user's privacy settings
            other_privacy = self.get_privacy_settings(other_user_id)
            if not other_privacy['allow_matching'] or not other_privacy['show_in_search']:
                continue

            score, shared_interests = self.calculate_compatibility_score(user_id, other_user_id)

            if score >= min_score:
                matches.append({
                    'user_id': other_user_id,
                    'compatibility_score': score,
                    'shared_interests': shared_interests,
                    'shared_count': len(shared_interests)
                })

        # Sort by score and limit results
        matches.sort(key=lambda x: x['compatibility_score'], reverse=True)
        return matches[:max_results]

    def save_match(self, user1_id: str, user2_id: str, score: float,
                   shared_interests: List[str], reason: str = "") -> int:
        """Save a calculated match to the database."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO interest_matches
                (user1_id, user2_id, compatibility_score, shared_interests,
                 match_reason, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user1_id, user2_id, score, json.dumps(shared_interests), reason))

            return cursor.lastrowid

    def get_saved_matches(self, user_id: str, status: str = 'suggested') -> List[Dict]:
        """Get saved matches for a user."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT match_id, user2_id, compatibility_score, shared_interests,
                       match_reason, match_status, created_at
                FROM interest_matches
                WHERE user1_id = ? AND match_status = ?
                ORDER BY compatibility_score DESC
            """, (user_id, status))

            matches = []
            for row in cursor.fetchall():
                matches.append({
                    'match_id': row[0],
                    'user_id': row[1],
                    'score': row[2],
                    'shared_interests': json.loads(row[3]) if row[3] else [],
                    'reason': row[4],
                    'status': row[5],
                    'created_at': row[6]
                })
            return matches

    def find_study_abroad_buddies(self, user_id: str, destination: str,
                                  semester: str = "") -> List[Dict]:
        """
        Find students interested in the same study abroad destination.

        Args:
            user_id: User searching
            destination: Study abroad destination
            semester: Optional semester filter

        Returns:
            List of potential buddies
        """
        buddies = []

        with get_connection() as conn:
            # Find users with "Travel" or "Study Abroad" interests
            cursor = conn.execute("""
                SELECT DISTINCT ui.user_id
                FROM user_interests ui
                WHERE ui.is_public = 1
                AND ui.user_id != ?
                AND (ui.interest_category = 'Travel'
                     OR ui.interest_name LIKE '%Study Abroad%'
                     OR ui.interest_name LIKE '%' || ? || '%')
            """, (user_id, destination))

            potential_buddies = [row[0] for row in cursor.fetchall()]

        # Calculate compatibility and filter
        for buddy_id in potential_buddies:
            privacy = self.get_privacy_settings(buddy_id)
            if not privacy['show_in_search']:
                continue

            score, shared = self.calculate_compatibility_score(user_id, buddy_id)

            buddies.append({
                'user_id': buddy_id,
                'destination': destination,
                'compatibility_score': score,
                'shared_interests': shared
            })

        buddies.sort(key=lambda x: x['compatibility_score'], reverse=True)
        return buddies
