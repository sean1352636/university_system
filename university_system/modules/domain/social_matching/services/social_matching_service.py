"""
Social Matching Service - Interest-based social connection platform.

Features:
- Interest-based matching with compatibility scoring
- Study abroad buddy finder
- Intramural sports team formation
- Club recommendation engine
- Social activity suggestions
- Personality-based matching
- Privacy controls
"""

import json
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.core.sql_safety import validate_identifier

# Interest categories
INTEREST_CATEGORIES = [
    'Sports', 'Music', 'Arts', 'Gaming', 'Outdoor',
    'Technology', 'Academic', 'Career', 'Travel', 'Other'
]

# Personality types
PERSONALITY_TYPES = [
    'Introvert', 'Extrovert', 'Ambivert'
]

# Group size preferences
GROUP_SIZE_PREFERENCES = [
    'One-on-One', 'Small Group (3-5)', 'Medium Group (6-10)', 'Large Group (10+)'
]

# Activity levels
ACTIVITY_LEVELS = [
    'Low', 'Moderate', 'High', 'Very High'
]

class SocialMatchingService:
    """Service for managing interest-based social matching and connections."""

    def __init__(self):
        """Initialize the social matching service."""
        from university_system.modules.domain.social_matching.database.db_init import (
            initialize_social_matching_tables
        )
        initialize_social_matching_tables()

    # ========== Interest Management ==========

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

    # ========== Personality Profile ==========

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

    # ========== Privacy Settings ==========

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

    # ========== Interest Matching ==========

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

    # ========== Buddy Requests ==========

    def send_buddy_request(self, sender_id: str, receiver_id: str,
                          request_type: str, destination: str = "",
                          message: str = "") -> int:
        """
        Send a buddy request to another user.

        Args:
            sender_id: User sending request
            receiver_id: User receiving request
            request_type: Type (study_abroad, general, sports, etc.)
            destination: Study abroad destination (if applicable)
            message: Personal message

        Returns:
            Request ID
        """
        # Check receiver's privacy settings
        privacy = self.get_privacy_settings(receiver_id)
        if not privacy['allow_messages']:
            raise PermissionError("User does not accept buddy requests")

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO buddy_requests
                (sender_id, receiver_id, request_type, destination, message)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, request_type, destination, message))

            request_id = cursor.lastrowid

        log_activity('create', 'buddy_request', user_id=sender_id,
                    details={'receiver': receiver_id, 'type': request_type})
        return request_id

    def get_buddy_requests(self, user_id: str, status: str = 'pending',
                          direction: str = 'received') -> List[Dict]:
        """
        Get buddy requests for a user.

        Args:
            user_id: User identifier
            status: Request status (pending, accepted, declined)
            direction: 'received' or 'sent'

        Returns:
            List of buddy requests
        """
        with get_connection() as conn:
            if direction == 'received':
                field = 'receiver_id'
            else:
                field = 'sender_id'

            safe_field = validate_identifier(field, "column")
            cursor = conn.execute(
                "SELECT request_id, sender_id, receiver_id, request_type,"
                "       destination, message, status, sent_at, responded_at"
                " FROM buddy_requests"
                " WHERE " + safe_field + " = ? AND status = ?"
                " ORDER BY sent_at DESC",
                (user_id, status))

            requests = []
            for row in cursor.fetchall():
                requests.append({
                    'request_id': row[0],
                    'sender_id': row[1],
                    'receiver_id': row[2],
                    'type': row[3],
                    'destination': row[4],
                    'message': row[5],
                    'status': row[6],
                    'sent_at': row[7],
                    'responded_at': row[8]
                })
            return requests

    def respond_to_buddy_request(self, request_id: int, user_id: str,
                                 accept: bool) -> bool:
        """Respond to a buddy request (accept or decline)."""
        status = 'accepted' if accept else 'declined'

        with transaction() as conn:
            cursor = conn.execute("""
                UPDATE buddy_requests
                SET status = ?, responded_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND receiver_id = ?
            """, (status, request_id, user_id))

            if cursor.rowcount > 0:
                log_activity('update', 'buddy_request', user_id=user_id,
                           details={'request_id': request_id, 'response': status})
                return True
        return False

    # ========== Study Abroad Buddy Finder ==========

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

    # ========== Team Formation ==========

    def create_team(self, creator_id: str, team_name: str, sport_type: str,
                   team_size: int, skill_level: str, description: str = "") -> int:
        """
        Create a new intramural sports team.

        Args:
            creator_id: Team creator
            team_name: Team name
            sport_type: Type of sport
            team_size: Target team size
            skill_level: Skill level (Beginner, Intermediate, Advanced)
            description: Team description

        Returns:
            Team ID
        """
        with transaction() as conn:
            # Create team
            cursor = conn.execute("""
                INSERT INTO team_formations
                (team_name, sport_type, creator_id, team_size, skill_level, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (team_name, sport_type, creator_id, team_size, skill_level, description))

            team_id = cursor.lastrowid

            # Add creator as first member
            conn.execute("""
                INSERT INTO team_members (team_id, user_id, role)
                VALUES (?, ?, 'captain')
            """, (team_id, creator_id))

        log_activity('create', 'team_formation', user_id=creator_id,
                    details={'team_name': team_name, 'sport': sport_type})
        return team_id

    def join_team(self, team_id: int, user_id: str) -> bool:
        """Join an existing team."""
        with transaction() as conn:
            # Check team capacity
            cursor = conn.execute("""
                SELECT current_members, team_size
                FROM team_formations
                WHERE team_id = ? AND status = 'recruiting'
            """, (team_id,))

            row = cursor.fetchone()
            if not row:
                return False

            current, max_size = row
            if current >= max_size:
                return False

            # Add member
            try:
                conn.execute("""
                    INSERT INTO team_members (team_id, user_id)
                    VALUES (?, ?)
                """, (team_id, user_id))

                # Update member count
                conn.execute("""
                    UPDATE team_formations
                    SET current_members = current_members + 1
                    WHERE team_id = ?
                """, (team_id,))

                log_activity('create', 'team_member', user_id=user_id,
                           details={'team_id': team_id})
                return True
            except sqlite3.IntegrityError:
                return False

    def get_available_teams(self, sport_type: str = "", skill_level: str = "") -> List[Dict]:
        """Get available teams looking for members."""
        with get_connection() as conn:
            query = """
                SELECT team_id, team_name, sport_type, creator_id,
                       team_size, current_members, skill_level, description, created_at
                FROM team_formations
                WHERE status = 'recruiting'
                AND current_members < team_size
            """
            params = []

            if sport_type:
                query += " AND sport_type = ?"
                params.append(sport_type)

            if skill_level:
                query += " AND skill_level = ?"
                params.append(skill_level)

            query += " ORDER BY created_at DESC"

            cursor = conn.execute(query, params)

            teams = []
            for row in cursor.fetchall():
                teams.append({
                    'team_id': row[0],
                    'team_name': row[1],
                    'sport_type': row[2],
                    'creator_id': row[3],
                    'team_size': row[4],
                    'current_members': row[5],
                    'skill_level': row[6],
                    'description': row[7],
                    'created_at': row[8]
                })
            return teams

    def get_team_members(self, team_id: int) -> List[Dict]:
        """Get members of a team."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT user_id, role, joined_at
                FROM team_members
                WHERE team_id = ?
                ORDER BY joined_at
            """, (team_id,))

            members = []
            for row in cursor.fetchall():
                members.append({
                    'user_id': row[0],
                    'role': row[1],
                    'joined_at': row[2]
                })
            return members

    # ========== Club Recommendations ==========

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

    # ========== Social Activities ==========

    def create_social_activity(self, creator_id: str, activity_name: str,
                              activity_type: str, description: str, location: str,
                              activity_date: str, activity_time: str,
                              max_participants: int, interests_matched: List[str]) -> int:
        """
        Create a new social activity.

        Args:
            creator_id: Activity creator
            activity_name: Name of activity
            activity_type: Type of activity
            description: Activity description
            location: Location
            activity_date: Date (YYYY-MM-DD)
            activity_time: Time (HH:MM)
            max_participants: Maximum participants
            interests_matched: Related interests

        Returns:
            Activity ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO social_activities
                (activity_name, activity_type, description, location,
                 activity_date, activity_time, max_participants,
                 interests_matched, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (activity_name, activity_type, description, location,
                  activity_date, activity_time, max_participants,
                  json.dumps(interests_matched), creator_id))

            activity_id = cursor.lastrowid

            # Creator automatically joins
            conn.execute("""
                INSERT INTO activity_participants
                (activity_id, user_id, rsvp_status)
                VALUES (?, ?, 'going')
            """, (activity_id, creator_id))

            conn.execute("""
                UPDATE social_activities
                SET current_participants = 1
                WHERE activity_id = ?
            """, (activity_id,))

        log_activity('create', 'social_activity', user_id=creator_id,
                    details={'activity_name': activity_name})
        return activity_id

    def get_suggested_activities(self, user_id: str, days_ahead: int = 30) -> List[Dict]:
        """
        Get suggested activities based on user interests.

        Args:
            user_id: User identifier
            days_ahead: Number of days to look ahead

        Returns:
            List of suggested activities
        """
        interests = self.get_user_interests(user_id)
        if not interests:
            return []

        interest_names = [i['name'].lower() for i in interests]

        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT activity_id, activity_name, activity_type, description,
                       location, activity_date, activity_time, max_participants,
                       current_participants, interests_matched, created_by
                FROM social_activities
                WHERE activity_date >= date('now')
                AND activity_date <= ?
                AND current_participants < max_participants
                ORDER BY activity_date, activity_time
            """, (end_date,))

            activities = []
            for row in cursor.fetchall():
                activity_interests = json.loads(row[9]) if row[9] else []

                # Calculate match score
                match_score = sum(1 for ai in activity_interests
                                if any(ai.lower() in int_name for int_name in interest_names))

                if match_score > 0:
                    activities.append({
                        'activity_id': row[0],
                        'activity_name': row[1],
                        'activity_type': row[2],
                        'description': row[3],
                        'location': row[4],
                        'activity_date': row[5],
                        'activity_time': row[6],
                        'max_participants': row[7],
                        'current_participants': row[8],
                        'interests_matched': activity_interests,
                        'created_by': row[10],
                        'match_score': match_score
                    })

            activities.sort(key=lambda x: x['match_score'], reverse=True)
            return activities

    def join_activity(self, activity_id: int, user_id: str, rsvp_status: str = 'going') -> bool:
        """
        Join a social activity.

        Args:
            activity_id: Activity ID
            user_id: User identifier
            rsvp_status: RSVP status (interested, going, maybe)

        Returns:
            True if successful
        """
        with transaction() as conn:
            # Check capacity
            cursor = conn.execute("""
                SELECT current_participants, max_participants
                FROM social_activities
                WHERE activity_id = ?
            """, (activity_id,))

            row = cursor.fetchone()
            if not row:
                return False

            current, max_part = row
            if current >= max_part and rsvp_status == 'going':
                return False

            # Add participant
            try:
                conn.execute("""
                    INSERT INTO activity_participants
                    (activity_id, user_id, rsvp_status)
                    VALUES (?, ?, ?)
                """, (activity_id, user_id, rsvp_status))

                if rsvp_status == 'going':
                    conn.execute("""
                        UPDATE social_activities
                        SET current_participants = current_participants + 1
                        WHERE activity_id = ?
                    """, (activity_id,))

                log_activity('create', 'activity_participant', user_id=user_id,
                           details={'activity_id': activity_id, 'status': rsvp_status})
                return True
            except sqlite3.IntegrityError:
                return False

    def get_my_activities(self, user_id: str) -> List[Dict]:
        """Get activities a user has joined."""
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT a.activity_id, a.activity_name, a.activity_type, a.description,
                       a.location, a.activity_date, a.activity_time,
                       a.current_participants, a.max_participants,
                       ap.rsvp_status, ap.joined_at
                FROM social_activities a
                JOIN activity_participants ap ON a.activity_id = ap.activity_id
                WHERE ap.user_id = ?
                AND a.activity_date >= date('now')
                ORDER BY a.activity_date, a.activity_time
            """, (user_id,))

            activities = []
            for row in cursor.fetchall():
                activities.append({
                    'activity_id': row[0],
                    'activity_name': row[1],
                    'activity_type': row[2],
                    'description': row[3],
                    'location': row[4],
                    'activity_date': row[5],
                    'activity_time': row[6],
                    'current_participants': row[7],
                    'max_participants': row[8],
                    'my_rsvp': row[9],
                    'joined_at': row[10]
                })
            return activities

    # ========== Statistics and Analytics ==========

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
