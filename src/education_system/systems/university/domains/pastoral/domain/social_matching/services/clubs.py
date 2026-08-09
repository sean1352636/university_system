"""Club recommendation mixin for the Social Matching Service."""

from typing import Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction


class ClubMixin:
    """Methods for club recommendations."""

    def generate_club_recommendations(self, user_id: str) -> List[Dict]:
        """
        Generate personalized club recommendations based on interests.

        Returns:
            List of recommended clubs with match scores
        """
        # Get user interests
        interests = self.get_user_interests(user_id)
        if not interests:
            return []

        # Sample club database (in production, this would be a real table)
        clubs = [
            {'name': 'Intramural Basketball League', 'category': 'Sports', 'tags': ['Basketball', 'Sports']},
            {'name': 'Campus Running Club', 'category': 'Sports', 'tags': ['Running', 'Outdoor', 'Fitness']},
            {'name': 'Acapella Group', 'category': 'Music', 'tags': ['Music', 'Performance', 'Singing']},
            {'name': 'DJ Club', 'category': 'Music', 'tags': ['Music', 'Electronic', 'DJing']},
            {'name': 'Photography Society', 'category': 'Arts', 'tags': ['Photography', 'Arts', 'Visual']},
            {'name': 'Drama Club', 'category': 'Arts', 'tags': ['Theater', 'Performance', 'Acting']},
            {'name': 'eSports Team', 'category': 'Gaming', 'tags': ['Video Games', 'eSports', 'Competition']},
            {'name': 'Board Game Society', 'category': 'Gaming', 'tags': ['Board Games', 'Social', 'Strategy']},
            {'name': 'Coding Club', 'category': 'Technology', 'tags': ['Programming', 'Technology', 'Software']},
            {'name': 'Robotics Team', 'category': 'Technology', 'tags': ['Robotics', 'Engineering', 'AI']},
            {'name': 'Debate Society', 'category': 'Academic', 'tags': ['Debate', 'Public Speaking', 'Academic']},
            {'name': 'Research Symposium', 'category': 'Academic', 'tags': ['Research', 'Academic', 'Science']},
            {'name': 'Entrepreneurship Club', 'category': 'Career', 'tags': ['Entrepreneurship', 'Business', 'Startups']},
            {'name': 'Professional Network', 'category': 'Career', 'tags': ['Networking', 'Career', 'Professional']},
            {'name': 'Study Abroad Alumni', 'category': 'Travel', 'tags': ['Travel', 'Study Abroad', 'International']},
            {'name': 'Adventure Club', 'category': 'Outdoor', 'tags': ['Hiking', 'Camping', 'Outdoor', 'Adventure']}
        ]

        recommendations = []

        # Calculate match score for each club
        for club in clubs:
            score = 0
            matched_interests = []

            for interest in interests:
                # Check if interest matches club category or tags
                if interest['category'] == club['category']:
                    score += interest['level'] * 2

                for tag in club['tags']:
                    if tag.lower() in interest['name'].lower():
                        score += interest['level']
                        matched_interests.append(interest['name'])

            if score > 0:
                recommendations.append({
                    'club_name': club['name'],
                    'club_category': club['category'],
                    'match_score': score,
                    'matched_interests': matched_interests,
                    'reason': f"Matches your interests: {', '.join(matched_interests[:3])}"
                })

        # Sort by score
        recommendations.sort(key=lambda x: x['match_score'], reverse=True)

        # Save recommendations
        with transaction() as conn:
            for rec in recommendations[:10]:
                conn.execute("""
                    INSERT OR REPLACE INTO club_suggestions
                    (user_id, club_name, club_category, match_score, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, rec['club_name'], rec['club_category'],
                      rec['match_score'], rec['reason']))

        return recommendations[:10]

    def get_club_recommendations(self, user_id: str, status: str = 'suggested') -> List[Dict]:
        """Get saved club recommendations for a user."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT suggestion_id, club_name, club_category, match_score,
                       reason, status, suggested_at
                FROM club_suggestions
                WHERE user_id = ? AND status = ?
                ORDER BY match_score DESC
            """, (user_id, status))

            recommendations = []
            for row in cursor.fetchall():
                recommendations.append({
                    'suggestion_id': row[0],
                    'club_name': row[1],
                    'club_category': row[2],
                    'match_score': row[3],
                    'reason': row[4],
                    'status': row[5],
                    'suggested_at': row[6]
                })
            return recommendations
