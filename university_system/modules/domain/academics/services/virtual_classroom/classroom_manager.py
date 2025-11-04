"""
Virtual Classroom Manager
Handles creation and management of virtual classrooms
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH


class VirtualClassroomManager:
    """Manager for virtual classroom operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def create_classroom(
        self,
        session_name: str,
        instructor_id: int,
        platform: str,
        course_id: Optional[int] = None,
        meeting_link: Optional[str] = None,
        meeting_id: Optional[str] = None,
        passcode: Optional[str] = None,
        max_participants: int = 100,
        features: Optional[Dict[str, bool]] = None
    ) -> Optional[int]:
        """
        Create a new virtual classroom

        Args:
            session_name: Name of the classroom/session
            instructor_id: ID of the instructor
            platform: Platform name (zoom, teams, meet, webrtc)
            course_id: Optional course ID
            meeting_link: Meeting URL
            meeting_id: Platform-specific meeting ID
            passcode: Meeting passcode/password
            max_participants: Maximum number of participants
            features: Dictionary of enabled features

        Returns:
            classroom_id if successful, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Validate platform
                valid_platforms = ['zoom', 'teams', 'meet', 'webrtc']
                if platform.lower() not in valid_platforms:
                    raise ValueError(f"Invalid platform. Must be one of: {valid_platforms}")

                # Default features
                if features is None:
                    features = {
                        'whiteboard': True,
                        'breakout_rooms': True,
                        'recording': True,
                        'polling': True,
                        'chat': True,
                        'screen_sharing': True
                    }

                features_json = json.dumps(features)

                cursor.execute("""
                    INSERT INTO virtual_classrooms (
                        session_name, course_id, instructor_id, platform,
                        meeting_link, meeting_id, passcode, max_participants, features
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_name, course_id, instructor_id, platform.lower(),
                      meeting_link, meeting_id, passcode, max_participants, features_json))

                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            print(f"Error creating virtual classroom: {e}")
            return None

    def get_classroom(self, classroom_id: int) -> Optional[Dict[str, Any]]:
        """Get classroom details by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_classrooms
                    WHERE classroom_id = ?
                """, (classroom_id,))

                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(cursor, row)
                return None

        except Exception as e:
            print(f"Error getting classroom: {e}")
            return None

    def get_classrooms_by_instructor(self, instructor_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all classrooms for an instructor"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_classrooms WHERE instructor_id = ?"
                params = [instructor_id]

                if active_only:
                    query += " AND is_active = 1"

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting classrooms by instructor: {e}")
            return []

    def get_classrooms_by_course(self, course_id: int) -> List[Dict[str, Any]]:
        """Get all classrooms for a course"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_classrooms
                    WHERE course_id = ? AND is_active = 1
                    ORDER BY created_at DESC
                """, (course_id,))

                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting classrooms by course: {e}")
            return []

    def update_classroom(
        self,
        classroom_id: int,
        **kwargs
    ) -> bool:
        """
        Update classroom details

        Supported kwargs:
            session_name, meeting_link, meeting_id, passcode,
            max_participants, features, is_active
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Build update query
                allowed_fields = [
                    'session_name', 'meeting_link', 'meeting_id', 'passcode',
                    'max_participants', 'features', 'is_active'
                ]

                updates = []
                values = []

                for key, value in kwargs.items():
                    if key in allowed_fields:
                        if key == 'features' and isinstance(value, dict):
                            value = json.dumps(value)
                        updates.append(f"{key} = ?")
                        values.append(value)

                if not updates:
                    return False

                values.append(classroom_id)
                query = f"UPDATE virtual_classrooms SET {', '.join(updates)} WHERE classroom_id = ?"

                cursor.execute(query, values)
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating classroom: {e}")
            return False

    def deactivate_classroom(self, classroom_id: int) -> bool:
        """Deactivate a virtual classroom"""
        return self.update_classroom(classroom_id, is_active=0)

    def delete_classroom(self, classroom_id: int) -> bool:
        """Delete a virtual classroom (cascade deletes sessions)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM virtual_classrooms
                    WHERE classroom_id = ?
                """, (classroom_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting classroom: {e}")
            return False

    def list_classrooms(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get all classrooms with optional filtering"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_classrooms"
                if active_only:
                    query += " WHERE is_active = 1"
                query += " ORDER BY created_at DESC"

                cursor.execute(query)
                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error listing classrooms: {e}")
            return []

    def get_classroom_stats(self, classroom_id: int) -> Optional[Dict[str, Any]]:
        """Get statistics for a classroom"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get total sessions
                cursor.execute("""
                    SELECT COUNT(*) as total_sessions,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                           SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled_sessions
                    FROM virtual_sessions
                    WHERE classroom_id = ?
                """, (classroom_id,))

                session_stats = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

                # Get total participants
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as unique_participants,
                           AVG(duration) as avg_duration
                    FROM session_participants sp
                    JOIN virtual_sessions vs ON sp.session_id = vs.session_id
                    WHERE vs.classroom_id = ?
                """, (classroom_id,))

                participant_stats = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

                # Get recordings count
                cursor.execute("""
                    SELECT COUNT(*) as total_recordings,
                           SUM(file_size) as total_storage
                    FROM virtual_recordings vr
                    JOIN virtual_sessions vs ON vr.session_id = vs.session_id
                    WHERE vs.classroom_id = ?
                """, (classroom_id,))

                recording_stats = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

                return {
                    **session_stats,
                    **participant_stats,
                    **recording_stats
                }

        except Exception as e:
            print(f"Error getting classroom stats: {e}")
            return None

    def _row_to_dict(self, cursor, row) -> Dict[str, Any]:
        """Convert database row to dictionary"""
        columns = [description[0] for description in cursor.description]
        result = dict(zip(columns, row))

        # Parse JSON fields
        if 'features' in result and result['features']:
            try:
                result['features'] = json.loads(result['features'])
            except:
                result['features'] = {}

        return result
