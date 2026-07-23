"""
Virtual Session Manager
Handles scheduling and management of virtual sessions
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger("virtual_classroom.emails")


def _send_virtual_classroom_email(template_name: str, recipient_email: str,
                                  vars_: Dict[str, Any]) -> bool:
    """Render ``virtual_classroom/<template_name>`` and dispatch best-effort.

    Skips silently when *recipient_email* is empty."""
    if not recipient_email:
        return False
    try:
        from education_system.post_18.university_system.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.post_18.university_system.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    subject, body = render_template(f"virtual_classroom/{template_name}", vars_)
    if not subject or not body:
        return False
    try:
        send_email(recipient_email=recipient_email, subject=subject, body=body)
        return True
    except Exception:
        logger.exception("send_email failed virtual_classroom/%s recipient=%s",
                         template_name, recipient_email)
        return False


class SessionManager:
    """Manager for virtual session operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def create_session(
        self,
        classroom_id: int,
        start_time: datetime,
        session_type: str = 'lecture',
        duration_minutes: int = 60,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """
        Create a new virtual session

        Args:
            classroom_id: ID of the virtual classroom
            start_time: When the session starts
            session_type: Type of session (lecture, lab, office_hours, review)
            duration_minutes: Expected duration in minutes
            notes: Optional notes about the session

        Returns:
            session_id if successful, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Calculate end time
                end_time = start_time + timedelta(minutes=duration_minutes)

                # Validate session type
                valid_types = ['lecture', 'lab', 'office_hours', 'review', 'exam']
                if session_type not in valid_types:
                    raise ValueError(f"Invalid session type. Must be one of: {valid_types}")

                cursor.execute("""
                    INSERT INTO virtual_sessions (
                        classroom_id, session_type, start_time, end_time, notes, status
                    ) VALUES (?, ?, ?, ?, ?, 'scheduled')
                """, (classroom_id, session_type, start_time, end_time, notes))

                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            print(f"Error creating session: {e}")
            return None

    def start_session(self, session_id: int) -> bool:
        """Start a virtual session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_sessions
                    SET status = 'in_progress',
                        actual_start_time = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND status = 'scheduled'
                """, (session_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error starting session: {e}")
            return False

    def end_session(
        self,
        session_id: int,
        recording_url: Optional[str] = None,
        recording_size: Optional[int] = None,
        recording_duration: Optional[int] = None
    ) -> bool:
        """End a virtual session and optionally save recording info"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_sessions
                    SET status = 'completed',
                        actual_end_time = CURRENT_TIMESTAMP,
                        recording_url = ?,
                        recording_size = ?,
                        recording_duration = ?
                    WHERE session_id = ? AND status = 'in_progress'
                """, (recording_url, recording_size, recording_duration, session_id))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error ending session: {e}")
            return False

    def cancel_session(self, session_id: int) -> bool:
        """Cancel a scheduled session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_sessions
                    SET status = 'cancelled'
                    WHERE session_id = ? AND status = 'scheduled'
                """, (session_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error cancelling session: {e}")
            return False

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session details by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT vs.*, vc.session_name, vc.platform, vc.meeting_link
                    FROM virtual_sessions vs
                    JOIN virtual_classrooms vc ON vs.classroom_id = vc.classroom_id
                    WHERE vs.session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(cursor, row)
                return None

        except Exception as e:
            print(f"Error getting session: {e}")
            return None

    def get_sessions_by_classroom(
        self,
        classroom_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get sessions for a classroom"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_sessions WHERE classroom_id = ?"
                params = [classroom_id]

                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY start_time DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting sessions by classroom: {e}")
            return []

    def get_upcoming_sessions(
        self,
        classroom_id: Optional[int] = None,
        days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """Get upcoming scheduled sessions"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                future_date = datetime.now() + timedelta(days=days_ahead)

                query = """
                    SELECT vs.*, vc.session_name, vc.platform, vc.meeting_link
                    FROM virtual_sessions vs
                    JOIN virtual_classrooms vc ON vs.classroom_id = vc.classroom_id
                    WHERE vs.status = 'scheduled'
                    AND vs.start_time BETWEEN CURRENT_TIMESTAMP AND ?
                """
                params = [future_date]

                if classroom_id:
                    query += " AND vs.classroom_id = ?"
                    params.append(classroom_id)

                query += " ORDER BY vs.start_time ASC"

                cursor.execute(query, params)
                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting upcoming sessions: {e}")
            return []

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get currently active sessions"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT vs.*, vc.session_name, vc.platform, vc.meeting_link
                    FROM virtual_sessions vs
                    JOIN virtual_classrooms vc ON vs.classroom_id = vc.classroom_id
                    WHERE vs.status = 'in_progress'
                    ORDER BY vs.actual_start_time DESC
                """)

                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting active sessions: {e}")
            return []

    def update_session(
        self,
        session_id: int,
        **kwargs
    ) -> bool:
        """
        Update session details

        Supported kwargs:
            session_type, start_time, end_time, notes, status
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                allowed_fields = ['session_type', 'start_time', 'end_time', 'notes', 'status']

                updates = []
                values = []

                for key, value in kwargs.items():
                    if key in allowed_fields:
                        updates.append(f"{validate_identifier(key, 'column')} = ?")
                        values.append(value)

                if not updates:
                    return False

                values.append(session_id)
                query = f"UPDATE virtual_sessions SET {', '.join(updates)} WHERE session_id = ?"

                cursor.execute(query, values)
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating session: {e}")
            return False

    def list_sessions(self, classroom_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all sessions with optional filtering"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_sessions WHERE 1=1"
                params = []

                if classroom_id is not None:
                    query += " AND classroom_id = ?"
                    params.append(classroom_id)

                if status is not None:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY start_time DESC"

                cursor.execute(query, params)
                return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []

    def get_session_statistics(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed statistics for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Participant stats
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_participants,
                        SUM(CASE WHEN attendance_status = 'present' THEN 1 ELSE 0 END) as attended,
                        AVG(duration) as avg_duration,
                        SUM(chat_message_count) as total_chat_messages,
                        SUM(raised_hand_count) as total_hand_raises
                    FROM session_participants
                    WHERE session_id = ?
                """, (session_id,))

                participant_stats = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

                # Poll stats
                cursor.execute("""
                    SELECT COUNT(*) as total_polls
                    FROM virtual_polls
                    WHERE session_id = ?
                """, (session_id,))

                poll_count = cursor.fetchone()[0]

                # Breakout room stats
                cursor.execute("""
                    SELECT COUNT(*) as total_breakout_rooms
                    FROM breakout_rooms
                    WHERE session_id = ?
                """, (session_id,))

                breakout_count = cursor.fetchone()[0]

                return {
                    **participant_stats,
                    'total_polls': poll_count,
                    'total_breakout_rooms': breakout_count
                }

        except Exception as e:
            print(f"Error getting session statistics: {e}")
            return None

    def _row_to_dict(self, cursor, row) -> Dict[str, Any]:
        """Convert database row to dictionary"""
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

    # ------------------------------------------------------------------ #
    #  Email notifications
    # ------------------------------------------------------------------ #
    def send_session_invites(self, session_id: int,
                             recipients: List[Dict[str, str]],
                             classroom_name: str = "",
                             host_name: str = "(host)",
                             join_url: str = "",
                             meeting_id: str = "",
                             dial_in: str = "(not provided)",
                             session_notes: str = "") -> int:
        """Send a session invitation to each ``{'name','email'}`` in *recipients*.
        Returns the number of emails accepted by the dispatch layer."""
        session = self.get_session(session_id)
        if not session:
            return 0
        start = session.get('start_time') or ''
        end   = session.get('end_time') or ''
        try:
            start_dt = datetime.fromisoformat(str(start))
            end_dt   = datetime.fromisoformat(str(end))
            date_s   = start_dt.strftime('%Y-%m-%d')
            start_s  = start_dt.strftime('%H:%M')
            end_s    = end_dt.strftime('%H:%M')
            duration = max(0, int((end_dt - start_dt).total_seconds() // 60))
        except Exception:
            date_s, start_s, end_s, duration = start, '', '', '?'
        sent = 0
        for r in recipients or []:
            ok = _send_virtual_classroom_email('session_invite', r.get('email', ''), {
                'participant_name': r.get('name') or 'Participant',
                'session_id':       session_id,
                'classroom_name':   classroom_name or f"Classroom #{session.get('classroom_id', '?')}",
                'session_type':     session.get('session_type', 'lecture'),
                'session_title':    session.get('session_type', 'Virtual session').title(),
                'session_date':     date_s,
                'start_time':       start_s,
                'end_time':         end_s,
                'duration_minutes': duration,
                'host_name':        host_name,
                'join_url':         join_url or '(see classroom page)',
                'meeting_id':       meeting_id or str(session_id),
                'dial_in':          dial_in,
                'session_notes':    session_notes or session.get('notes') or '(no notes)',
            })
            sent += 1 if ok else 0
        return sent

    def send_recording_ready(self, session_id: int,
                             recipients: List[Dict[str, str]],
                             classroom_name: str = "",
                             host_name: str = "(host)",
                             transcript_url: str = "(not available)",
                             captions_url: str = "(not available)",
                             expires_on: str = "(see retention policy)") -> int:
        """Email each recipient that the recording for *session_id* is ready.
        Requires the session to already have a ``recording_url``."""
        session = self.get_session(session_id)
        if not session or not session.get('recording_url'):
            return 0
        try:
            start_dt = datetime.fromisoformat(str(session.get('start_time') or ''))
            date_s   = start_dt.strftime('%Y-%m-%d')
        except Exception:
            date_s = str(session.get('start_time') or '')
        size = session.get('recording_size') or 0
        if isinstance(size, (int, float)) and size:
            size_s = f"{size / (1024*1024):.1f} MB"
        else:
            size_s = '(unknown)'
        duration = session.get('recording_duration')
        duration_s = f"{duration} min" if duration else '(unknown)'
        sent = 0
        for r in recipients or []:
            ok = _send_virtual_classroom_email('recording_ready', r.get('email', ''), {
                'participant_name':   r.get('name') or 'Participant',
                'session_id':         session_id,
                'classroom_name':     classroom_name or f"Classroom #{session.get('classroom_id', '?')}",
                'session_type':       session.get('session_type', 'lecture'),
                'session_title':      session.get('session_type', 'Virtual session').title(),
                'session_date':       date_s,
                'host_name':          host_name,
                'recording_duration': duration_s,
                'recording_size':     size_s,
                'recording_url':      session.get('recording_url'),
                'transcript_url':     transcript_url,
                'captions_url':       captions_url,
                'expires_on':         expires_on,
            })
            sent += 1 if ok else 0
        return sent

    @staticmethod
    def flag_low_attendance(recipient_email: str, participant_name: str,
                            classroom_name: str, module_code: str,
                            window_start: str, window_end: str,
                            sessions_held: int, sessions_attended: int,
                            threshold: int = 75,
                            recent_misses: str = "(see classroom log)") -> bool:
        """Email a participant when their attendance dips below *threshold*%."""
        rate = round((sessions_attended / sessions_held) * 100) if sessions_held else 0
        return _send_virtual_classroom_email('attendance_flag', recipient_email, {
            'participant_name':  participant_name or 'Participant',
            'classroom_name':    classroom_name,
            'module_code':       module_code,
            'window_start':      window_start,
            'window_end':        window_end,
            'sessions_held':     sessions_held,
            'sessions_attended': sessions_attended,
            'attendance_rate':   rate,
            'threshold':         threshold,
            'recent_misses':     recent_misses,
        })
