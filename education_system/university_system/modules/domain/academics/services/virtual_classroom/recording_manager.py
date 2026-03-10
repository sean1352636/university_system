"""
Recording Manager
Handles virtual classroom recordings
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

class RecordingManager:
    """Manager for virtual classroom recording operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def save_recording(
        self,
        session_id: int,
        file_url: str,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        duration: Optional[int] = None,
        file_format: str = 'mp4',
        is_public: bool = False,
        expiry_days: Optional[int] = 90
    ) -> Optional[int]:
        """Save recording metadata"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                expires_at = None
                if expiry_days:
                    expires_at = datetime.now() + timedelta(days=expiry_days)

                cursor.execute("""
                    INSERT INTO virtual_recordings (
                        session_id, file_url, file_name, file_size, duration,
                        format, is_public, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, file_url, file_name, file_size, duration,
                      file_format, 1 if is_public else 0, expires_at))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error saving recording: {e}")
            return None

    def add_transcript(self, recording_id: int, transcript_url: str) -> bool:
        """Add transcript to recording"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_recordings
                    SET has_transcript = 1, transcript_url = ?
                    WHERE recording_id = ?
                """, (transcript_url, recording_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error adding transcript: {e}")
            return False

    def add_captions(self, recording_id: int, captions_url: str) -> bool:
        """Add captions to recording"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_recordings
                    SET has_captions = 1, captions_url = ?
                    WHERE recording_id = ?
                """, (captions_url, recording_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error adding captions: {e}")
            return False

    def increment_view_count(self, recording_id: int) -> bool:
        """Increment view count"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_recordings
                    SET view_count = view_count + 1
                    WHERE recording_id = ?
                """, (recording_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error incrementing view count: {e}")
            return False

    def increment_download_count(self, recording_id: int) -> bool:
        """Increment download count"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_recordings
                    SET download_count = download_count + 1
                    WHERE recording_id = ?
                """, (recording_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error incrementing download count: {e}")
            return False

    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get recording by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT vr.*, vs.session_type, vc.session_name
                    FROM virtual_recordings vr
                    LEFT JOIN virtual_sessions vs ON vr.session_id = vs.session_id
                    LEFT JOIN virtual_classrooms vc ON vs.classroom_id = vc.classroom_id
                    WHERE vr.recording_id = ?
                """, (recording_id,))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting recording: {e}")
            return None

    def get_recordings_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Get all recordings for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_recordings
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                """, (session_id,))

                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting recordings: {e}")
            return []

    def get_recordings_by_classroom(
        self,
        classroom_id: int,
        include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all recordings for a classroom"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT vr.*, vs.start_time, vs.session_type
                    FROM virtual_recordings vr
                    LEFT JOIN virtual_sessions vs ON vr.session_id = vs.session_id
                    WHERE vs.classroom_id = ?
                """

                if not include_expired:
                    query += " AND (vr.expires_at IS NULL OR vr.expires_at > CURRENT_TIMESTAMP)"

                query += " ORDER BY vs.start_time DESC"

                cursor.execute(query, (classroom_id,))
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting classroom recordings: {e}")
            return []

    def list_recordings(self, session_id: Optional[int] = None, is_public: Optional[bool] = None) -> List[Dict[str, Any]]:
        """List all recordings with optional filtering"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_recordings WHERE 1=1"
                params = []

                if session_id is not None:
                    query += " AND session_id = ?"
                    params.append(session_id)

                if is_public is not None:
                    query += " AND is_public = ?"
                    params.append(1 if is_public else 0)

                query += " ORDER BY created_at DESC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error listing recordings: {e}")
            return []

    def delete_recording(self, recording_id: int) -> bool:
        """Delete a recording"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM virtual_recordings
                    WHERE recording_id = ?
                """, (recording_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting recording: {e}")
            return False

    def get_expired_recordings(self) -> List[Dict[str, Any]]:
        """Get all expired recordings"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_recordings
                    WHERE expires_at IS NOT NULL
                    AND expires_at < CURRENT_TIMESTAMP
                    ORDER BY expires_at ASC
                """)

                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting expired recordings: {e}")
            return []

    def get_storage_usage(self, classroom_id: Optional[int] = None) -> Dict[str, Any]:
        """Get storage usage statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if classroom_id:
                    cursor.execute("""
                        SELECT
                            COUNT(*) as total_recordings,
                            COALESCE(SUM(file_size), 0) as total_size,
                            COALESCE(SUM(duration), 0) as total_duration
                        FROM virtual_recordings vr
                        LEFT JOIN virtual_sessions vs ON vr.session_id = vs.session_id
                        WHERE vs.classroom_id = ?
                    """, (classroom_id,))
                else:
                    cursor.execute("""
                        SELECT
                            COUNT(*) as total_recordings,
                            COALESCE(SUM(file_size), 0) as total_size,
                            COALESCE(SUM(duration), 0) as total_duration
                        FROM virtual_recordings
                    """)

                row = cursor.fetchone()
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        except Exception as e:
            print(f"Error getting storage usage: {e}")
            return {}
