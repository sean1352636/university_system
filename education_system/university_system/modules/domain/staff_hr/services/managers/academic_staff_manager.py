"""
Academic Staff Manager

Handles teaching portfolios, research profiles, student supervisions,
external examiners, and peer observations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.sql_safety import validate_identifier

try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class AcademicStaffManager:
    """Manager for academic staff features."""

    # ==================== TEACHING PORTFOLIOS ====================

    @staticmethod
    def get_teaching_portfolio(user_id: str) -> Optional[Dict[str, Any]]:
        """Get teaching portfolio for a user."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM teaching_portfolios WHERE user_id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_teaching_portfolio(user_id: str, **data) -> bool:
        """Update or create teaching portfolio."""
        with transaction() as conn:
            existing = conn.execute('''
                SELECT portfolio_id FROM teaching_portfolios WHERE user_id = ?
            ''', (user_id,)).fetchone()

            if existing:
                fields = ', '.join(validate_identifier(k, "column") + ' = ?' for k in data.keys())
                values = list(data.values()) + [datetime.now().isoformat(), user_id]
                conn.execute(
                    'UPDATE teaching_portfolios SET ' + fields + ', last_updated = ? WHERE user_id = ?',
                    values)
            else:
                safe_cols = [validate_identifier(k, "column") for k in data.keys()]
                cols = ', '.join(['user_id'] + safe_cols)
                placeholders = ', '.join(['?'] * (len(data) + 1))
                values = [user_id] + list(data.values())
                conn.execute(
                    'INSERT INTO teaching_portfolios (' + cols + ') VALUES (' + placeholders + ')',
                    values)
            return True

    # ==================== RESEARCH PROFILES ====================

    @staticmethod
    def get_research_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Get research profile for a user."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM research_profiles WHERE user_id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_research_profile(user_id: str, **data) -> bool:
        """Update or create research profile."""
        with transaction() as conn:
            existing = conn.execute('''
                SELECT profile_id FROM research_profiles WHERE user_id = ?
            ''', (user_id,)).fetchone()

            if existing:
                fields = ', '.join(validate_identifier(k, "column") + ' = ?' for k in data.keys())
                values = list(data.values()) + [datetime.now().isoformat(), user_id]
                conn.execute(
                    'UPDATE research_profiles SET ' + fields + ', last_updated = ? WHERE user_id = ?',
                    values)
            else:
                safe_cols = [validate_identifier(k, "column") for k in data.keys()]
                cols = ', '.join(['user_id'] + safe_cols)
                placeholders = ', '.join(['?'] * (len(data) + 1))
                values = [user_id] + list(data.values())
                conn.execute(
                    'INSERT INTO research_profiles (' + cols + ') VALUES (' + placeholders + ')',
                    values)
            return True

    # ==================== STUDENT SUPERVISIONS ====================

    @staticmethod
    def get_supervisions(supervisor_id: str,
                         status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get student supervisions for a supervisor."""
        with get_connection() as conn:
            query = 'SELECT * FROM student_supervisions WHERE supervisor_id = ?'
            params = [supervisor_id]
            if status:
                query += ' AND status = ?'
                params.append(status)
            query += ' ORDER BY start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_supervision(supervisor_id: str, student_id: str,
                        program_type: str, **data) -> int:
        """Add a new student supervision."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO student_supervisions (
                    supervisor_id, student_id, student_name, program_type,
                    thesis_title, start_date, expected_end_date,
                    supervision_role, progress_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (supervisor_id, student_id, data.get('student_name'),
                  program_type, data.get('thesis_title'), data.get('start_date'),
                  data.get('expected_end_date'),
                  data.get('supervision_role', 'primary'),
                  data.get('progress_notes')))
            return cursor.lastrowid

    @staticmethod
    def update_supervision(supervision_id: int, **data) -> bool:
        """Update a supervision record."""
        if not data:
            return False
        with transaction() as conn:
            fields = ', '.join(validate_identifier(k, "column") + ' = ?' for k in data.keys())
            values = list(data.values()) + [datetime.now().isoformat(), supervision_id]
            conn.execute(
                'UPDATE student_supervisions SET ' + fields + ', updated_at = ? WHERE supervision_id = ?',
                values)
            return True

    # ==================== EXTERNAL EXAMINERS ====================

    @staticmethod
    def get_external_examiners(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get external examiners."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM external_examiners WHERE status = 'active'
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM external_examiners ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_external_examiner(name: str, **data) -> int:
        """Add a new external examiner."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO external_examiners (
                    name, institution, email, phone, expertise_area,
                    department, appointment_start, appointment_end,
                    contact_person_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('institution'), data.get('email'),
                  data.get('phone'), data.get('expertise_area'),
                  data.get('department'), data.get('appointment_start'),
                  data.get('appointment_end'), data.get('contact_person_id'),
                  data.get('notes')))
            return cursor.lastrowid

    @staticmethod
    def get_examiner_assignments(examiner_id: int) -> List[Dict[str, Any]]:
        """Get assignments for an external examiner."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM examiner_assignments
                WHERE examiner_id = ? ORDER BY academic_year DESC
            ''', (examiner_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== PEER OBSERVATIONS ====================

    @staticmethod
    def get_peer_observations(user_id: str,
                              role: str = 'both') -> List[Dict[str, Any]]:
        """Get peer observations where user is observer or observee."""
        with get_connection() as conn:
            if role == 'observer':
                rows = conn.execute('''
                    SELECT * FROM peer_observations WHERE observer_id = ?
                    ORDER BY observation_date DESC
                ''', (user_id,)).fetchall()
            elif role == 'observee':
                rows = conn.execute('''
                    SELECT * FROM peer_observations WHERE observee_id = ?
                    ORDER BY observation_date DESC
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM peer_observations
                    WHERE observer_id = ? OR observee_id = ?
                    ORDER BY observation_date DESC
                ''', (user_id, user_id)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_observation(observer_id: str, observee_id: str,
                           observation_date: str, **data) -> int:
        """Create a new peer observation record."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO peer_observations (
                    observer_id, observer_name, observee_id, observee_name,
                    course_code, course_name, observation_date,
                    observation_type, class_size, duration_minutes,
                    strengths, areas_for_development, action_points,
                    overall_rating, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (observer_id, data.get('observer_name'), observee_id,
                  data.get('observee_name'), data.get('course_code'),
                  data.get('course_name'), observation_date,
                  data.get('observation_type', 'peer'),
                  data.get('class_size'), data.get('duration_minutes'),
                  data.get('strengths'), data.get('areas_for_development'),
                  data.get('action_points'), data.get('overall_rating'),
                  data.get('status', 'draft')))
            return cursor.lastrowid

    @staticmethod
    def submit_observation(observation_id: int) -> bool:
        """Submit a peer observation for acknowledgement."""
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_observations
                SET status = 'submitted' WHERE observation_id = ?
            ''', (observation_id,))
            return True

    @staticmethod
    def acknowledge_observation(observation_id: int) -> bool:
        """Acknowledge a peer observation."""
        with transaction() as conn:
            conn.execute('''
                UPDATE peer_observations
                SET status = 'acknowledged', acknowledged_date = ?
                WHERE observation_id = ?
            ''', (datetime.now().isoformat(), observation_id))
            return True
