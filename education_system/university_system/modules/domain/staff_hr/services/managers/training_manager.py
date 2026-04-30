"""
Training Manager

Handles training courses, enrollments, certifications,
and professional development tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction

try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class TrainingManager:
    """Manager for training and certification tracking."""

    @staticmethod
    def get_courses(category: Optional[str] = None,
                    mandatory_only: bool = False) -> List[Dict[str, Any]]:
        """Get training courses with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM training_courses WHERE is_active = 1'
            params = []
            if category:
                query += ' AND category = ?'
                params.append(category)
            if mandatory_only:
                query += ' AND is_mandatory = 1'
            query += ' ORDER BY category, name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_course(course_id: int) -> Optional[Dict[str, Any]]:
        """Get a course by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM training_courses WHERE course_id = ?
            ''', (course_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_course(name: str, **data) -> int:
        """Create a new training course."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO training_courses (
                    name, description, category, provider,
                    duration_hours, passing_score, is_mandatory,
                    recertification_months, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('description'), data.get('category'),
                  data.get('provider'), data.get('duration_hours'),
                  data.get('passing_score', 70), data.get('is_mandatory', 0),
                  data.get('recertification_months'), data.get('is_active', 1)))
            return cursor.lastrowid

    @staticmethod
    def get_enrollments(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get training enrollments for a user."""
        with get_connection() as conn:
            query = '''
                SELECT e.*, c.name as course_name, c.category,
                       c.duration_hours, c.is_mandatory
                FROM training_enrollments e
                JOIN training_courses c ON e.course_id = c.course_id
                WHERE e.user_id = ?
            '''
            params = [user_id]
            if status:
                query += ' AND e.status = ?'
                params.append(status)
            query += ' ORDER BY e.enrolled_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def enroll(user_id: str, course_id: int, due_date: Optional[str] = None) -> int:
        """Enroll a user in a training course."""
        with transaction() as conn:
            existing = conn.execute('''
                SELECT enrollment_id FROM training_enrollments
                WHERE user_id = ? AND course_id = ?
                  AND status NOT IN ('completed', 'failed')
            ''', (user_id, course_id)).fetchone()
            if existing:
                raise ValueError("User is already enrolled in this course")
            cursor = conn.execute('''
                INSERT INTO training_enrollments (user_id, course_id, due_date)
                VALUES (?, ?, ?)
            ''', (user_id, course_id, due_date))
            return cursor.lastrowid

    @staticmethod
    def complete_course(enrollment_id: int, score: float,
                        certificate_path: Optional[str] = None) -> bool:
        """Mark a course as completed."""
        with transaction() as conn:
            enrollment = conn.execute('''
                SELECT c.passing_score FROM training_enrollments e
                JOIN training_courses c ON e.course_id = c.course_id
                WHERE e.enrollment_id = ?
            ''', (enrollment_id,)).fetchone()
            if not enrollment:
                return False
            status = 'completed' if score >= (enrollment[0] or 70) else 'failed'
            conn.execute('''
                UPDATE training_enrollments
                SET status = ?, completed_date = ?, score = ?, certificate_path = ?
                WHERE enrollment_id = ?
            ''', (status, datetime.now().isoformat() if status == 'completed' else None,
                  score, certificate_path, enrollment_id))
            return True

    @staticmethod
    def get_certifications(user_id: str) -> List[Dict[str, Any]]:
        """Get certifications for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM certifications WHERE user_id = ?
                ORDER BY expiry_date
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_certification(user_id: str, name: str, **data) -> int:
        """Add a certification for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO certifications (
                    user_id, name, issuing_body, credential_id,
                    issue_date, expiry_date, document_path, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, data.get('issuing_body'), data.get('credential_id'),
                  data.get('issue_date'), data.get('expiry_date'),
                  data.get('document_path'), data.get('status', 'active'),
                  data.get('notes')))
            cert_id = cursor.lastrowid

        # Cross-domain: publish through cert_bus so the chatbot,
        # expiring-certs dashboard, and email subscribers see the
        # new certification (and so cases_bus.apply_sanction's
        # cert-revoke path has a known counterpart event).
        try:
            from education_system.university_system.modules.services import (
                cert_bus,
            )
            cert_bus._publish(
                "cert.issued",
                cert_id=cert_id, user_id=str(user_id), name=name,
                issuing_body=data.get('issuing_body'),
                expiry_date=data.get('expiry_date'),
            )
        except Exception:
            pass

        return cert_id

    @staticmethod
    def get_expiring_certs(days: int = 30) -> List[Dict[str, Any]]:
        """Get certifications expiring within the specified days."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.*, p.department, u.first_name, u.last_name
                FROM certifications c
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.expiry_date <= date('now', '+' || ? || ' days')
                  AND c.expiry_date >= date('now') AND c.status = 'active'
                ORDER BY c.expiry_date
            ''', (days,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_mandatory_incomplete(user_id: str) -> List[Dict[str, Any]]:
        """Get incomplete mandatory training for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.* FROM training_courses c
                WHERE c.is_mandatory = 1 AND c.is_active = 1
                  AND c.course_id NOT IN (
                      SELECT course_id FROM training_enrollments
                      WHERE user_id = ? AND status = 'completed'
                  )
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]
