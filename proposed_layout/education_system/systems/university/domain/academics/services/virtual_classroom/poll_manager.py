"""
Poll Manager
Handles live polling and quizzes during virtual sessions
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

class PollManager:
    """Manager for virtual session polling operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def create_poll(
        self,
        session_id: int,
        question: str,
        created_by: int,
        poll_type: str = 'multiple_choice',
        options: Optional[List[str]] = None,
        correct_answer: Optional[str] = None,
        is_anonymous: bool = True,
        time_limit: Optional[int] = None
    ) -> Optional[int]:
        """Create a new poll"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                valid_types = ['multiple_choice', 'true_false', 'rating', 'open_ended']
                if poll_type not in valid_types:
                    raise ValueError(f"Invalid poll type. Must be one of: {valid_types}")

                options_json = json.dumps(options) if options else None

                cursor.execute("""
                    INSERT INTO virtual_polls (
                        session_id, question, poll_type, options, correct_answer,
                        is_anonymous, time_limit, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, question, poll_type, options_json, correct_answer,
                      1 if is_anonymous else 0, time_limit, created_by))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating poll: {e}")
            return None

    def submit_response(
        self,
        poll_id: int,
        user_id: int,
        answer: str
    ) -> bool:
        """Submit a response to a poll"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if poll is still active
                cursor.execute("""
                    SELECT is_active, correct_answer FROM virtual_polls
                    WHERE poll_id = ?
                """, (poll_id,))

                poll = cursor.fetchone()
                if not poll or not poll[0]:
                    print("Poll is not active")
                    return False

                correct_answer = poll[1]
                is_correct = None

                if correct_answer:
                    is_correct = (answer.lower() == correct_answer.lower())

                # Insert or update response
                cursor.execute("""
                    INSERT INTO poll_responses (poll_id, user_id, answer, is_correct)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(poll_id, user_id) DO UPDATE SET
                        answer = excluded.answer,
                        is_correct = excluded.is_correct,
                        response_time = CURRENT_TIMESTAMP
                """, (poll_id, user_id, answer, is_correct))

                conn.commit()
                return True
        except Exception as e:
            print(f"Error submitting poll response: {e}")
            return False

    def close_poll(self, poll_id: int) -> bool:
        """Close a poll"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_polls
                    SET is_active = 0, closed_at = CURRENT_TIMESTAMP
                    WHERE poll_id = ?
                """, (poll_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error closing poll: {e}")
            return False

    def get_poll(self, poll_id: int) -> Optional[Dict[str, Any]]:
        """Get poll details"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_polls
                    WHERE poll_id = ?
                """, (poll_id,))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    result = dict(zip(columns, row))
                    if result.get('options'):
                        result['options'] = json.loads(result['options'])
                    return result
                return None
        except Exception as e:
            print(f"Error getting poll: {e}")
            return None

    def get_session_polls(
        self,
        session_id: int,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all polls for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_polls WHERE session_id = ?"
                params = [session_id]

                if active_only:
                    query += " AND is_active = 1"

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]

                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    if result.get('options'):
                        result['options'] = json.loads(result['options'])
                    results.append(result)

                return results
        except Exception as e:
            print(f"Error getting session polls: {e}")
            return []

    def get_poll_results(self, poll_id: int) -> Dict[str, Any]:
        """Get poll results"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get poll details
                poll = self.get_poll(poll_id)
                if not poll:
                    return {}

                # Get total responses
                cursor.execute("""
                    SELECT COUNT(*) FROM poll_responses
                    WHERE poll_id = ?
                """, (poll_id,))
                total_responses = cursor.fetchone()[0]

                # Get response distribution
                cursor.execute("""
                    SELECT answer, COUNT(*) as count
                    FROM poll_responses
                    WHERE poll_id = ?
                    GROUP BY answer
                    ORDER BY count DESC
                """, (poll_id,))

                response_distribution = [
                    {'answer': row[0], 'count': row[1]}
                    for row in cursor.fetchall()
                ]

                # If it's a quiz, get accuracy
                accuracy = None
                if poll['correct_answer']:
                    cursor.execute("""
                        SELECT
                            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as accuracy
                        FROM poll_responses
                        WHERE poll_id = ?
                    """, (poll_id,))
                    accuracy_row = cursor.fetchone()
                    if accuracy_row and accuracy_row[0]:
                        accuracy = round(accuracy_row[0], 2)

                return {
                    'poll': poll,
                    'total_responses': total_responses,
                    'response_distribution': response_distribution,
                    'accuracy': accuracy
                }
        except Exception as e:
            print(f"Error getting poll results: {e}")
            return {}

    def get_user_response(self, poll_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a user's response to a poll"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM poll_responses
                    WHERE poll_id = ? AND user_id = ?
                """, (poll_id, user_id))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting user response: {e}")
            return None

    def delete_poll(self, poll_id: int) -> bool:
        """Delete a poll"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM virtual_polls
                    WHERE poll_id = ?
                """, (poll_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting poll: {e}")
            return False
