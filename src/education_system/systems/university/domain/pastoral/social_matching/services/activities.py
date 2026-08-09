"""Social activities mixin for the Social Matching Service."""

import json
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity


class ActivityMixin:
    """Methods for social activity management."""

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
