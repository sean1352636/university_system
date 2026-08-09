"""
Cover / Substitute Teaching Manager

Provides functionality for:
- Teaching qualification and skill tracking
- Cover request lifecycle management
- Available staff matching
- Volunteer offers and cover assignments
- Cover statistics and reporting
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608


class CoverManager:
    """Manager for substitute/cover teaching arrangements."""

    # ==================== QUALIFICATIONS & SKILLS ====================

    @staticmethod
    def add_qualification(user_id: str, subject_area: str,
                          course_code: str = None,
                          qualification_level: str = 'qualified') -> int:
        """Add a teaching qualification for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO teaching_qualifications (
                    user_id, subject_area, course_code,
                    qualification_level, created_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id, subject_area, course_code,
                qualification_level, datetime.now().isoformat(),
            ))
            qualification_id = cursor.lastrowid
            log_activity('create', 'teaching_qualification', details={
                'qualification_id': qualification_id, 'user_id': user_id,
                'subject_area': subject_area,
            })
            return qualification_id

    @staticmethod
    def get_qualifications(user_id: str) -> List[Dict[str, Any]]:
        """Get teaching qualifications for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM teaching_qualifications
                WHERE user_id = ?
                ORDER BY subject_area
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def remove_qualification(qualification_id: int) -> None:
        """Remove a teaching qualification."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM teaching_qualifications
                WHERE qualification_id = ?
            ''', (qualification_id,))
            log_activity('delete', 'teaching_qualification', details={
                'qualification_id': qualification_id,
            })

    @staticmethod
    def add_skill(user_id: str, skill_name: str,
                  category: str = 'general',
                  proficiency: str = 'intermediate') -> int:
        """Add a skill for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO cover_skills (
                    user_id, skill_name, category,
                    proficiency, created_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id, skill_name, category,
                proficiency, datetime.now().isoformat(),
            ))
            skill_id = cursor.lastrowid
            log_activity('create', 'cover_skill', details={
                'skill_id': skill_id, 'user_id': user_id,
                'skill_name': skill_name,
            })
            return skill_id

    @staticmethod
    def get_skills(user_id: str) -> List[Dict[str, Any]]:
        """Get skills for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM cover_skills
                WHERE user_id = ?
                ORDER BY category, skill_name
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def remove_skill(skill_id: int) -> None:
        """Remove a skill."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM cover_skills WHERE skill_id = ?
            ''', (skill_id,))
            log_activity('delete', 'cover_skill', details={
                'skill_id': skill_id,
            })

    # ==================== COVER REQUEST LIFECYCLE ====================

    @staticmethod
    def create_request(requester_id: str, cover_date: str,
                       start_time: str, end_time: str,
                       request_type: str = 'teaching',
                       course_code: str = None,
                       course_name: str = None,
                       location: str = None,
                       reason: str = None,
                       urgency: str = 'normal',
                       department: str = None) -> int:
        """Create a cover request with status 'open'."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO cover_requests (
                    requester_id, cover_date, start_time, end_time,
                    request_type, course_code, course_name, location,
                    reason, urgency, department, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            ''', (
                requester_id, cover_date, start_time, end_time,
                request_type, course_code, course_name, location,
                reason, urgency, department,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            request_id = cursor.lastrowid
            log_activity('create', 'cover_request', details={
                'request_id': request_id, 'requester_id': requester_id,
                'cover_date': cover_date, 'urgency': urgency,
            })
            return request_id

    @staticmethod
    def get_request(request_id: int) -> Optional[Dict[str, Any]]:
        """Get a single cover request by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM cover_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_requests(user_id: str) -> List[Dict[str, Any]]:
        """Get cover requests created by a user, ordered by date descending."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM cover_requests
                WHERE requester_id = ?
                ORDER BY cover_date DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_open_requests(department: str = None) -> List[Dict[str, Any]]:
        """Get open cover requests, optionally filtered by department.

        Results are ordered by urgency descending then cover_date ascending.
        """
        with get_connection() as conn:
            query = '''
                SELECT * FROM cover_requests
                WHERE status = 'open'
            '''
            params: list = []

            if department:
                query += ' AND department = ?'
                params.append(department)

            query += ' ORDER BY urgency DESC, cover_date'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_request(request_id: int, **data) -> None:
        """Update cover request fields."""
        allowed_fields = {
            'cover_date', 'start_time', 'end_time', 'request_type',
            'course_code', 'course_name', 'location', 'reason',
            'urgency', 'department',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(request_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE cover_requests SET ' + ', '.join(fields)
                + ' WHERE request_id = ?',
                values)
            log_activity('update', 'cover_request', details={
                'request_id': request_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def cancel_request(request_id: int) -> None:
        """Cancel a cover request by setting status to 'cancelled'."""
        with transaction() as conn:
            conn.execute('''
                UPDATE cover_requests
                SET status = 'cancelled', updated_at = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))
            log_activity('update', 'cover_request', details={
                'request_id': request_id, 'action': 'cancelled',
            })

    # ==================== FIND AVAILABLE STAFF ====================

    @staticmethod
    def find_available_staff(request_id: int) -> List[Dict[str, Any]]:
        """Find staff qualified and available for a cover request.

        Matches staff by subject_area or course_code from the
        teaching_qualifications table, then excludes those with
        conflicting cover assignments on the same date/time.
        """
        with get_connection() as conn:
            # Get request details
            request = conn.execute('''
                SELECT * FROM cover_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()

            if not request:
                raise ValueError(f"Cover request {request_id} not found")

            request = dict(request)

            # Find qualified staff
            qualified = conn.execute('''
                SELECT DISTINCT tq.user_id, tq.subject_area, tq.qualification_level
                FROM teaching_qualifications tq
                WHERE (tq.subject_area = ? OR tq.course_code = ?)
                AND tq.user_id != ?
            ''', (
                request['course_name'] or '',
                request['course_code'] or '',
                request['requester_id'],
            )).fetchall()

            # For each, check no existing assignment on that date/time
            available = []
            for q in qualified:
                conflict = conn.execute('''
                    SELECT COUNT(*) as cnt FROM cover_assignments ca
                    JOIN cover_requests cr ON ca.request_id = cr.request_id
                    WHERE ca.assignee_id = ? AND cr.cover_date = ?
                    AND cr.start_time < ? AND cr.end_time > ?
                    AND ca.completed = 0
                ''', (
                    q['user_id'],
                    request['cover_date'],
                    request['end_time'],
                    request['start_time'],
                )).fetchone()

                if conflict['cnt'] == 0:
                    available.append(dict(q))

            return available

    # ==================== OFFER & ASSIGNMENT ====================

    @staticmethod
    def volunteer(request_id: int, volunteer_id: str,
                  message: str = None) -> int:
        """Volunteer for a cover request by creating an offer."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO cover_offers (
                    request_id, volunteer_id, message, created_at
                ) VALUES (?, ?, ?, ?)
            ''', (
                request_id, volunteer_id, message,
                datetime.now().isoformat(),
            ))
            offer_id = cursor.lastrowid
            log_activity('create', 'cover_offer', details={
                'offer_id': offer_id, 'request_id': request_id,
                'volunteer_id': volunteer_id,
            })
            return offer_id

    @staticmethod
    def get_offers(request_id: int) -> List[Dict[str, Any]]:
        """Get volunteer offers for a cover request."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM cover_offers
                WHERE request_id = ?
                ORDER BY created_at
            ''', (request_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def assign_cover(request_id: int, assignee_id: str,
                     assigned_by: str) -> int:
        """Assign cover to a staff member and update request status to 'assigned'."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO cover_assignments (
                    request_id, assignee_id, assigned_by,
                    accepted, completed, created_at
                ) VALUES (?, ?, ?, 0, 0, ?)
            ''', (
                request_id, assignee_id, assigned_by,
                datetime.now().isoformat(),
            ))
            assignment_id = cursor.lastrowid

            conn.execute('''
                UPDATE cover_requests
                SET status = 'assigned', updated_at = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))

            log_activity('create', 'cover_assignment', details={
                'assignment_id': assignment_id, 'request_id': request_id,
                'assignee_id': assignee_id, 'assigned_by': assigned_by,
            })
            return assignment_id

    @staticmethod
    def accept_assignment(assignment_id: int) -> None:
        """Accept a cover assignment."""
        with transaction() as conn:
            conn.execute('''
                UPDATE cover_assignments
                SET accepted = 1, accepted_date = ?
                WHERE assignment_id = ?
            ''', (datetime.now().isoformat(), assignment_id))
            log_activity('update', 'cover_assignment', details={
                'assignment_id': assignment_id, 'action': 'accepted',
            })

    @staticmethod
    def decline_assignment(assignment_id: int) -> None:
        """Decline a cover assignment.

        Deletes the assignment and sets the request status back to 'open'.
        """
        with transaction() as conn:
            # Get the request_id before deleting
            row = conn.execute('''
                SELECT request_id FROM cover_assignments
                WHERE assignment_id = ?
            ''', (assignment_id,)).fetchone()

            if not row:
                raise ValueError(f"Cover assignment {assignment_id} not found")

            request_id = row['request_id']

            conn.execute('''
                DELETE FROM cover_assignments WHERE assignment_id = ?
            ''', (assignment_id,))

            conn.execute('''
                UPDATE cover_requests
                SET status = 'open', updated_at = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))

            log_activity('update', 'cover_assignment', details={
                'assignment_id': assignment_id, 'request_id': request_id,
                'action': 'declined',
            })

    @staticmethod
    def complete_assignment(assignment_id: int, feedback: str = None,
                            rating: int = None) -> None:
        """Complete a cover assignment with optional feedback and rating.

        Sets completed=1, records completed_date, feedback, and rating.
        Updates the associated cover request status to 'completed'.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE cover_assignments
                SET completed = 1, completed_date = ?,
                    feedback = ?, rating = ?
                WHERE assignment_id = ?
            ''', (
                datetime.now().isoformat(), feedback, rating,
                assignment_id,
            ))

            # Get the request_id and update request status
            row = conn.execute('''
                SELECT request_id FROM cover_assignments
                WHERE assignment_id = ?
            ''', (assignment_id,)).fetchone()

            if row:
                conn.execute('''
                    UPDATE cover_requests
                    SET status = 'completed', updated_at = ?
                    WHERE request_id = ?
                ''', (datetime.now().isoformat(), row['request_id']))

            log_activity('update', 'cover_assignment', details={
                'assignment_id': assignment_id, 'action': 'completed',
            })

    # ==================== REPORTING ====================

    @staticmethod
    def get_cover_statistics(department: str = None) -> Dict[str, Any]:
        """Get cover statistics, optionally filtered by department."""
        with get_connection() as conn:
            where_clause = '1=1'
            params: list = []

            if department:
                where_clause += ' AND department = ?'
                params.append(department)

            # Total requests
            row = conn.execute(
                'SELECT COUNT(*) as total_requests'
                ' FROM cover_requests WHERE ' + where_clause,
                params).fetchone()

            stats: Dict[str, Any] = {
                'total_requests': row['total_requests'] or 0,
            }

            # By status
            rows = conn.execute(
                'SELECT status, COUNT(*) as count'
                ' FROM cover_requests WHERE ' + where_clause
                + ' GROUP BY status',
                params).fetchall()
            stats['by_status'] = {r['status']: r['count'] for r in rows}

            # By urgency
            rows = conn.execute(
                'SELECT urgency, COUNT(*) as count'
                ' FROM cover_requests WHERE ' + where_clause
                + ' GROUP BY urgency',
                params).fetchall()
            stats['by_urgency'] = {r['urgency']: r['count'] for r in rows}

            return stats
