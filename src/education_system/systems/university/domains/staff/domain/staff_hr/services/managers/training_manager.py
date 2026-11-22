"""
Training Manager

Handles training courses, enrollments, certifications,
and professional development tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import (
    _people as people,
)

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

#: Course fields HR may set.
COURSE_FIELDS = ('name', 'description', 'category', 'provider', 'duration_hours',
                 'passing_score', 'is_mandatory', 'recertification_months', 'is_active')


def _enrollment_owner(conn, enrollment_id: int) -> Optional[str]:
    row = conn.execute('SELECT user_id FROM training_enrollments WHERE enrollment_id = ?',
                       (enrollment_id,)).fetchone()
    return people.key(row[0], conn) if row else None


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
    def create_course(name: str, actor: Any = None, **data) -> int:
        """Create a new training course (with ``actor``: HR only)."""
        if not str(name or '').strip():
            raise ValueError("Course name is required")
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage training courses")
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
            if actor is not None:
                access.audit(conn, actor, 'create_training_course', None, 'training_courses',
                             cursor.lastrowid, {'name': name})
            return cursor.lastrowid

    @staticmethod
    def update_course(course_id: int, actor: Any = None, **data) -> bool:
        """Change a course (with ``actor``: HR only)."""
        changes = {k: v for k, v in data.items() if k in COURSE_FIELDS}
        if 'name' in changes and not str(changes['name'] or '').strip():
            raise ValueError("Course name is required")
        if not changes:
            return False
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage training courses")
            cur = conn.execute('UPDATE training_courses SET ' +
                               ', '.join(validate_identifier(c, "column") + ' = ?' for c in changes) +
                               ', updated_at = ? WHERE course_id = ?',
                               list(changes.values()) + [datetime.now().isoformat(), course_id])
            if actor is not None and cur.rowcount:
                access.audit(conn, actor, 'update_training_course', None, 'training_courses',
                             course_id, {'fields': sorted(changes)})
        log_activity('update', 'training_course', details={'course_id': course_id})
        return bool(cur.rowcount)

    @staticmethod
    def deactivate_course(course_id: int, actor: Any = None) -> bool:
        """Withdraw a course from the catalogue (with ``actor``: HR only)."""
        return TrainingManager.update_course(course_id, actor=actor, is_active=0)

    @staticmethod
    def delete_course(course_id: int, actor: Any = None) -> int:
        """Delete a course and its enrolments (with ``actor``: HR only).
        Returns how many enrolments went with it."""
        with transaction() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage training courses")
            gone = conn.execute('DELETE FROM training_enrollments WHERE course_id = ?',
                                (course_id,)).rowcount
            conn.execute('DELETE FROM training_courses WHERE course_id = ?', (course_id,))
            if actor is not None:
                access.audit(conn, actor, 'delete_training_course', None, 'training_courses',
                             course_id, {'enrollments': gone})
        log_activity('delete', 'training_course', details={'course_id': course_id})
        return gone

    @staticmethod
    def get_all_courses(actor: Any = None, active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Every course with its enrolment count (``active``: only active /
        only inactive; with ``actor``: HR only)."""
        with get_connection() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "manage training courses")
            query = ('SELECT c.*, (SELECT COUNT(*) FROM training_enrollments e '
                     'WHERE e.course_id = c.course_id) AS enrollment_count '
                     'FROM training_courses c')
            if active is not None:
                query += ' WHERE c.is_active = ' + ('1' if active else '0')
            rows = conn.execute(query + ' ORDER BY c.name').fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def enrollment_stats(course_id: int, actor: Any = None) -> Dict[str, int]:
        """Enrolments on a course by status (with ``actor``: HR only)."""
        with get_connection() as conn:
            if actor is not None:
                people.require_hr(actor, conn, "see course enrolments")
            return {r[0]: r[1] for r in conn.execute(
                'SELECT status, COUNT(*) FROM training_enrollments WHERE course_id = ? '
                'GROUP BY status', (course_id,)).fetchall()}

    @staticmethod
    def get_enrollments(user_id: str, status: Optional[str] = None,
                        actor: Any = None) -> List[Dict[str, Any]]:
        """Get training enrollments for a user (with ``actor``: the person,
        their line managers or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this training record")
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
    def enroll(user_id: str, course_id: int, due_date: Optional[str] = None,
               actor: Any = None) -> int:
        """Enroll a user in a training course (with ``actor``: the person,
        their line managers or HR; the course must be active)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_manager(actor, user_id, conn, "enrol this person")
                course = conn.execute('SELECT is_active FROM training_courses WHERE course_id = ?',
                                      (course_id,)).fetchone()
                if not course or not course[0]:
                    raise ValueError("That course is not open for enrolment")
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
            log_activity('create', 'training_enrollment', user_id=user_id,
                         details={'course_id': course_id})
            return cursor.lastrowid

    @staticmethod
    def complete_course(enrollment_id: int, score: float,
                        certificate_path: Optional[str] = None, actor: Any = None) -> bool:
        """Mark a course as completed — or failed, below its passing score
        (with ``actor``: the person, their line managers or HR)."""
        if not 0 <= float(score) <= 100:
            raise ValueError("Score must be between 0 and 100")
        with transaction() as conn:
            if actor is not None:
                owner = _enrollment_owner(conn, enrollment_id)
                if owner is None:
                    return False
                people.require_self_or_manager(actor, owner, conn, "record this training")
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
    def record_result(enrollment_id: int, score: float, actor: Any = None) -> Optional[str]:
        """:meth:`complete_course`, returning the resulting status
        ('completed' or 'failed'; None when there is no such enrolment)."""
        if not TrainingManager.complete_course(enrollment_id, score, actor=actor):
            return None
        with get_connection() as conn:
            row = conn.execute('SELECT status FROM training_enrollments WHERE enrollment_id = ?',
                               (enrollment_id,)).fetchone()
            return row[0] if row else None

    @staticmethod
    def get_certifications(user_id: str, actor: Any = None) -> List[Dict[str, Any]]:
        """Get certifications for a user (with ``actor``: the person, their
        line managers or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "these certifications")
            rows = conn.execute('''
                SELECT * FROM certifications WHERE user_id = ?
                ORDER BY expiry_date
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_certification(user_id: str, name: str, actor: Any = None, **data) -> int:
        """Add a certification for a user (with ``actor``: the person or HR)."""
        if not str(name or '').strip():
            raise ValueError("Certification name is required")
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_hr(actor, user_id, conn, "record certifications")
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
            from education_system.systems.university.services.bus import (
                cert_bus,
            )
            cert_bus._publish(
                "cert.issued",
                cert_id=cert_id, user_id=str(user_id), name=name,
                issuing_body=data.get('issuing_body'),
                expiry_date=data.get('expiry_date'),
            )
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        return cert_id

    @staticmethod
    def get_expiring_certs(days: int = 30) -> List[Dict[str, Any]]:
        """Get certifications expiring within the specified days."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.*, p.department, u.first_name, u.last_name
                FROM certifications c
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                LEFT JOIN users u ON u.username = c.user_id
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

    # ==================== REPORTS ====================

    @staticmethod
    def _mandatory_position(conn) -> tuple:
        """``(current staff usernames, number of mandatory courses, {username:
        mandatory courses done})``. A completion past the course's
        recertification period no longer counts."""
        from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.employee_manager import (
            current_staff,
        )
        staff = [str(s['user_id']) for s in current_staff(conn)]
        courses = conn.execute('''
            SELECT course_id, recertification_months FROM training_courses
            WHERE is_mandatory = 1 AND is_active = 1
        ''').fetchall()
        done: Dict[str, int] = {}
        for course in courses:
            months = course['recertification_months']
            rows = conn.execute('''
                SELECT DISTINCT user_id FROM training_enrollments
                WHERE course_id = ? AND status = 'completed'
                  AND (? IS NULL OR completed_date >= date('now', '-' || ? || ' months'))
            ''', (course['course_id'], months, months)).fetchall()
            for row in rows:
                done[str(row[0])] = done.get(str(row[0]), 0) + 1
        return staff, len(courses), done

    @staticmethod
    def get_completion_report(year: Optional[int] = None) -> Dict[str, Any]:
        """Course and enrolment totals, and where current staff stand on
        mandatory training."""
        wanted = str(year or datetime.now().year)
        with get_connection() as conn:
            programs = conn.execute(
                'SELECT COUNT(*) FROM training_courses WHERE is_active = 1').fetchone()[0]
            statuses = {r[0]: r[1] for r in conn.execute(
                'SELECT status, COUNT(*) FROM training_enrollments GROUP BY status').fetchall()}
            this_year = conn.execute('''
                SELECT COUNT(*) FROM training_enrollments
                WHERE status = 'completed' AND substr(completed_date, 1, 4) = ?
            ''', (wanted,)).fetchone()[0]
            staff, mandatory, done = TrainingManager._mandatory_position(conn)
        total = sum(statuses.values())
        return {
            'total_programs': programs,
            'completed_year': this_year,
            'in_progress': statuses.get('enrolled', 0) + statuses.get('in_progress', 0),
            'completion_rate': statuses.get('completed', 0) * 100.0 / total if total else 0.0,
            'mandatory_required': len(staff) * mandatory,
            'mandatory_completed': sum(done.get(person, 0) for person in staff),
        }

    @staticmethod
    def get_compliance_report() -> Dict[str, Any]:
        """How many current staff have done all their mandatory training."""
        with get_connection() as conn:
            staff, mandatory, done = TrainingManager._mandatory_position(conn)
        compliant = sum(1 for person in staff if done.get(person, 0) >= mandatory)
        return {
            'total_staff': len(staff),
            'compliant': compliant,
            'non_compliant': len(staff) - compliant,
            'compliance_rate': compliant * 100.0 / len(staff) if staff else 0.0,
        }

    @staticmethod
    def get_certification_status(days: int = 30) -> Dict[str, int]:
        """Active certifications by expiry: still valid, expiring within
        ``days``, or expired. No expiry date counts as valid."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT COUNT(*),
                       COALESCE(SUM(expiry_date < date('now')), 0),
                       COALESCE(SUM(expiry_date >= date('now')
                                    AND expiry_date <= date('now', '+' || ? || ' days')), 0)
                FROM certifications WHERE status = 'active'
            ''', (days,)).fetchone()
        total, expired, expiring = row[0], row[1], row[2]
        return {
            'total': total,
            'valid': total - expired - expiring,
            'expiring_soon': expiring,
            'expired': expired,
        }
