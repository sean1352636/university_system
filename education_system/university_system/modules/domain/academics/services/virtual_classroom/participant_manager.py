"""
Participant Manager
Handles session participants and attendance tracking
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from education_system.university_system.core.paths import DEFAULT_DB_PATH

class ParticipantManager:
    """Manager for session participant operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def add_participant(
        self,
        session_id: int,
        user_id: int,
        user_type: str = 'student',
        device_type: str = 'desktop'
    ) -> Optional[int]:
        """Add a participant to a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO session_participants (
                        session_id, user_id, user_type, device_type, join_time
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (session_id, user_id, user_type, device_type))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error adding participant: {e}")
            return None

    def record_leave(self, participant_id: int) -> bool:
        """Record when a participant leaves"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE session_participants
                    SET leave_time = CURRENT_TIMESTAMP,
                        duration = CAST((julianday(CURRENT_TIMESTAMP) - julianday(join_time)) * 86400 AS INTEGER)
                    WHERE participant_id = ? AND leave_time IS NULL
                """, (participant_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error recording leave: {e}")
            return False

    def update_attendance_status(self, participant_id: int, status: str) -> bool:
        """Update participant attendance status"""
        valid_statuses = ['present', 'absent', 'late', 'left_early']
        if status not in valid_statuses:
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE session_participants
                    SET attendance_status = ?
                    WHERE participant_id = ?
                """, (status, participant_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating attendance: {e}")
            return False

    def raise_hand(self, participant_id: int) -> bool:
        """Increment hand raise count"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE session_participants
                    SET raised_hand_count = raised_hand_count + 1
                    WHERE participant_id = ?
                """, (participant_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error raising hand: {e}")
            return False

    def toggle_mute(self, participant_id: int, is_muted: bool) -> bool:
        """Toggle mute status"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE session_participants
                    SET is_muted = ?
                    WHERE participant_id = ?
                """, (1 if is_muted else 0, participant_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error toggling mute: {e}")
            return False

    def toggle_video(self, participant_id: int, is_video_on: bool) -> bool:
        """Toggle video status"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE session_participants
                    SET is_video_on = ?
                    WHERE participant_id = ?
                """, (1 if is_video_on else 0, participant_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error toggling video: {e}")
            return False

    def get_session_participants(
        self,
        session_id: int,
        user_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all participants for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM session_participants WHERE session_id = ?"
                params = [session_id]

                if user_type:
                    query += " AND user_type = ?"
                    params.append(user_type)

                query += " ORDER BY join_time ASC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting participants: {e}")
            return []

    def get_participant_by_user(
        self,
        session_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get participant record for a specific user in a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM session_participants
                    WHERE session_id = ? AND user_id = ?
                """, (session_id, user_id))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting participant: {e}")
            return None

    def get_attendance_summary(self, session_id: int) -> Dict[str, int]:
        """Get attendance summary for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        attendance_status,
                        COUNT(*) as count
                    FROM session_participants
                    WHERE session_id = ?
                    GROUP BY attendance_status
                """, (session_id,))

                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            print(f"Error getting attendance summary: {e}")
            return {}

    def get_user_attendance_history(
        self,
        user_id: int,
        classroom_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get attendance history for a user"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT sp.*, vs.session_type, vs.start_time, vc.session_name
                    FROM session_participants sp
                    JOIN virtual_sessions vs ON sp.session_id = vs.session_id
                    JOIN virtual_classrooms vc ON vs.classroom_id = vc.classroom_id
                    WHERE sp.user_id = ?
                """
                params = [user_id]

                if classroom_id:
                    query += " AND vc.classroom_id = ?"
                    params.append(classroom_id)

                query += " ORDER BY vs.start_time DESC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting attendance history: {e}")
            return []
