"""
Teaching Load Manager

Provides functionality for:
- Course assignment tracking with weighted load calculations
- Release time management for administrative and research duties
- Departmental teaching load standards and policies
- Overload detection and semester-by-semester analysis
- Department-wide load distribution and balance suggestions
- Bulk import of course assignments from external sources
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608


class TeachingLoadManager:
    """Manager for teaching load tracking, standards, and analysis."""

    # ==================== COURSE ASSIGNMENTS ====================

    @staticmethod
    def add_course_assignment(user_id: str, course_code: str,
                              course_name: str, section: str,
                              academic_year: str, semester: str,
                              credit_hours: float = 3.0,
                              contact_hours_pw: float = 3.0,
                              lecture_hours_pw: float = None,
                              lab_hours_pw: float = None,
                              tutorial_hours_pw: float = None,
                              enrolled_students: int = 0,
                              max_enrollment: int = 30,
                              department: str = None,
                              is_new_prep: bool = False,
                              is_team_taught: bool = False,
                              team_share_pct: int = 100,
                              source: str = 'manual',
                              notes: str = None,
                              created_by: str = None) -> int:
        """Add a new course assignment to a user's teaching load.

        Automatically calculates weighted_hours based on credit_hours,
        class size factor (from department standards), and team teaching
        share percentage.

        The class_size_factor is determined by looking up the department's
        teaching load standard: if enrolled_students >= large_class_threshold
        the large_class_factor is used; otherwise 1.0.

        weighted_hours = credit_hours * class_size_factor * (team_share_pct / 100)

        Args:
            user_id: The ID of the instructor being assigned.
            course_code: The course code (e.g. 'CS101').
            course_name: The full name of the course.
            section: The section identifier (e.g. '001').
            academic_year: The academic year (e.g. '2025-2026').
            semester: The semester (e.g. 'Fall', 'Spring', 'Summer').
            credit_hours: Number of credit hours for the course.
            contact_hours_pw: Total contact hours per week.
            lecture_hours_pw: Lecture hours per week (optional).
            lab_hours_pw: Lab hours per week (optional).
            tutorial_hours_pw: Tutorial hours per week (optional).
            enrolled_students: Current enrollment count.
            max_enrollment: Maximum enrollment capacity.
            department: Department offering the course (optional).
            is_new_prep: Whether this is a new preparation for the instructor.
            is_team_taught: Whether the course is team-taught.
            team_share_pct: Percentage of the course this instructor teaches.
            source: Source of the assignment data (default 'manual').
            notes: Additional notes (optional).
            created_by: User ID of the person creating the assignment.

        Returns:
            The assignment_id of the newly created course assignment.
        """
        # Look up class size factor from standards
        class_size_factor = 1.0
        with get_connection() as conn:
            standard = None
            if department:
                standard = conn.execute('''
                    SELECT large_class_threshold, large_class_factor
                    FROM teaching_load_standards
                    WHERE department = ?
                    ORDER BY is_default DESC
                    LIMIT 1
                ''', (department,)).fetchone()
            if not standard:
                standard = conn.execute('''
                    SELECT large_class_threshold, large_class_factor
                    FROM teaching_load_standards
                    WHERE is_default = 1
                    LIMIT 1
                ''').fetchone()
            if standard:
                std = dict(standard)
                threshold = std.get('large_class_threshold', 50)
                if enrolled_students >= threshold:
                    class_size_factor = std.get('large_class_factor', 1.25)

        weighted_hours = credit_hours * class_size_factor * (team_share_pct / 100)
        now = datetime.now().isoformat()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO teaching_load_courses (
                    user_id, course_code, course_name, section,
                    academic_year, semester, credit_hours, contact_hours_pw,
                    lecture_hours_pw, lab_hours_pw, tutorial_hours_pw,
                    enrolled_students, max_enrollment, class_size_factor,
                    weighted_hours, department, is_new_prep, is_team_taught,
                    team_share_pct, status, source, notes, created_by,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'active', ?, ?, ?, ?, ?
                )
            ''', (
                user_id, course_code, course_name, section,
                academic_year, semester, credit_hours, contact_hours_pw,
                lecture_hours_pw, lab_hours_pw, tutorial_hours_pw,
                enrolled_students, max_enrollment, class_size_factor,
                weighted_hours, department, int(is_new_prep),
                int(is_team_taught), team_share_pct, source, notes,
                created_by, now, now,
            ))
            assignment_id = cursor.lastrowid
            log_activity('create', 'teaching_load_course', details={
                'assignment_id': assignment_id, 'user_id': user_id,
                'course_code': course_code, 'section': section,
                'academic_year': academic_year, 'semester': semester,
                'weighted_hours': weighted_hours,
            })
            return assignment_id

    @staticmethod
    def get_course_assignment(assignment_id: int) -> Optional[Dict[str, Any]]:
        """Get a single course assignment by ID.

        Args:
            assignment_id: The primary key of the course assignment.

        Returns:
            A dict of the course assignment row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM teaching_load_courses
                WHERE assignment_id = ?
            ''', (assignment_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_course_assignments(user_id: str,
                                    academic_year: str = None,
                                    semester: str = None) -> List[Dict[str, Any]]:
        """Get all course assignments for a user with optional filters.

        Args:
            user_id: The instructor's user ID.
            academic_year: Filter by academic year (optional).
            semester: Filter by semester (optional).

        Returns:
            A list of course assignment dicts ordered by course_code.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM teaching_load_courses WHERE user_id = ?'
            params: list = [user_id]

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)

            if semester:
                query += ' AND semester = ?'
                params.append(semester)

            query += ' ORDER BY course_code'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_course_assignment(assignment_id: int, **data) -> None:
        """Update allowed fields on a course assignment.

        After updating, recalculates weighted_hours based on the current
        credit_hours, class_size_factor, and team_share_pct.

        Allowed fields: course_name, section, credit_hours, contact_hours_pw,
        lecture_hours_pw, lab_hours_pw, tutorial_hours_pw, enrolled_students,
        max_enrollment, department, is_new_prep, is_team_taught,
        team_share_pct, status, notes.

        Args:
            assignment_id: The course assignment to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'course_name', 'section', 'credit_hours', 'contact_hours_pw',
            'lecture_hours_pw', 'lab_hours_pw', 'tutorial_hours_pw',
            'enrolled_students', 'max_enrollment', 'department',
            'is_new_prep', 'is_team_taught', 'team_share_pct',
            'status', 'notes',
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
        values.append(assignment_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE teaching_load_courses SET '
                + ', '.join(fields) + ' WHERE assignment_id = ?',
                values)
            log_activity('update', 'teaching_load_course', details={
                'assignment_id': assignment_id,
                'updated_fields': list(data.keys()),
            })

        # Recalculate weighted_hours after update
        TeachingLoadManager._recalculate_weighted_hours(assignment_id)

    @staticmethod
    def delete_course_assignment(assignment_id: int) -> None:
        """Delete a course assignment.

        Args:
            assignment_id: The course assignment to delete.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM teaching_load_courses
                WHERE assignment_id = ?
            ''', (assignment_id,))
            log_activity('delete', 'teaching_load_course', details={
                'assignment_id': assignment_id,
            })

    @staticmethod
    def update_enrollment(assignment_id: int,
                          enrolled_students: int) -> None:
        """Update enrollment count and recalculate class size factor and weighted hours.

        When enrollment changes, the class_size_factor may change if the
        student count crosses the large_class_threshold defined in the
        department's teaching load standard.

        Args:
            assignment_id: The course assignment to update.
            enrolled_students: The new enrollment count.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE teaching_load_courses
                SET enrolled_students = ?, updated_at = ?
                WHERE assignment_id = ?
            ''', (enrolled_students, datetime.now().isoformat(),
                  assignment_id))
            log_activity('update', 'teaching_load_course', details={
                'assignment_id': assignment_id,
                'action': 'update_enrollment',
                'enrolled_students': enrolled_students,
            })

        # Recalculate class_size_factor and weighted_hours
        TeachingLoadManager._recalculate_weighted_hours(assignment_id)

    @staticmethod
    def _recalculate_weighted_hours(assignment_id: int) -> None:
        """Recalculate class_size_factor and weighted_hours for a course assignment.

        Looks up the department standard to determine the large class
        threshold and factor, then computes:
            class_size_factor = large_class_factor if enrolled >= threshold else 1.0
            weighted_hours = credit_hours * class_size_factor * (team_share_pct / 100)

        Args:
            assignment_id: The course assignment to recalculate.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM teaching_load_courses
                WHERE assignment_id = ?
            ''', (assignment_id,)).fetchone()

        if not row:
            return

        course = dict(row)
        department = course.get('department')
        enrolled_students = course.get('enrolled_students', 0)
        credit_hours = course.get('credit_hours', 3.0)
        team_share_pct = course.get('team_share_pct', 100)

        # Look up class size factor from standards
        class_size_factor = 1.0
        with get_connection() as conn:
            standard = None
            if department:
                standard = conn.execute('''
                    SELECT large_class_threshold, large_class_factor
                    FROM teaching_load_standards
                    WHERE department = ?
                    ORDER BY is_default DESC
                    LIMIT 1
                ''', (department,)).fetchone()
            if not standard:
                standard = conn.execute('''
                    SELECT large_class_threshold, large_class_factor
                    FROM teaching_load_standards
                    WHERE is_default = 1
                    LIMIT 1
                ''').fetchone()
            if standard:
                std = dict(standard)
                threshold = std.get('large_class_threshold', 50)
                if enrolled_students >= threshold:
                    class_size_factor = std.get('large_class_factor', 1.25)

        weighted_hours = credit_hours * class_size_factor * (team_share_pct / 100)

        with transaction() as conn:
            conn.execute('''
                UPDATE teaching_load_courses
                SET class_size_factor = ?, weighted_hours = ?, updated_at = ?
                WHERE assignment_id = ?
            ''', (class_size_factor, weighted_hours,
                  datetime.now().isoformat(), assignment_id))

    # ==================== RELEASE TIME ====================

    @staticmethod
    def add_release_time(user_id: str, academic_year: str, semester: str,
                         release_type: str, title: str,
                         hours_per_week: float,
                         credit_equivalent: float = 0,
                         start_date: str = None,
                         end_date: str = None,
                         funding_source: str = None,
                         notes: str = None) -> int:
        """Add a release time entry for a user.

        Release time reduces a faculty member's teaching obligation for
        administrative duties, research, or other responsibilities.

        Args:
            user_id: The instructor's user ID.
            academic_year: The academic year (e.g. '2025-2026').
            semester: The semester (e.g. 'Fall', 'Spring').
            release_type: Type of release (e.g. 'research', 'admin', 'service').
            title: Short description of the release (e.g. 'Department Chair').
            hours_per_week: Hours per week of release time.
            credit_equivalent: Credit-hour equivalent of the release (default 0).
            start_date: Start date of the release period (optional, ISO format).
            end_date: End date of the release period (optional, ISO format).
            funding_source: Source funding the release (optional).
            notes: Additional notes (optional).

        Returns:
            The release_id of the newly created release time record.
        """
        now = datetime.now().isoformat()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO teaching_load_release_time (
                    user_id, academic_year, semester, release_type, title,
                    hours_per_week, credit_equivalent, start_date, end_date,
                    funding_source, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            ''', (
                user_id, academic_year, semester, release_type, title,
                hours_per_week, credit_equivalent, start_date, end_date,
                funding_source, notes, now, now,
            ))
            release_id = cursor.lastrowid
            log_activity('create', 'teaching_load_release', details={
                'release_id': release_id, 'user_id': user_id,
                'release_type': release_type, 'title': title,
                'credit_equivalent': credit_equivalent,
            })
            return release_id

    @staticmethod
    def get_release_time(user_id: str = None,
                         academic_year: str = None,
                         semester: str = None) -> List[Dict[str, Any]]:
        """Get release time records with optional filters.

        Args:
            user_id: Filter by user ID (optional).
            academic_year: Filter by academic year (optional).
            semester: Filter by semester (optional).

        Returns:
            A list of release time dicts ordered by academic_year and semester.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM teaching_load_release_time WHERE 1=1'
            params: list = []

            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)

            if semester:
                query += ' AND semester = ?'
                params.append(semester)

            query += ' ORDER BY academic_year DESC, semester'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_release_time(release_id: int, **data) -> None:
        """Update allowed fields on a release time record.

        Allowed fields: title, hours_per_week, credit_equivalent,
        start_date, end_date, funding_source, status, approved_by, notes.

        Args:
            release_id: The release time record to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'title', 'hours_per_week', 'credit_equivalent',
            'start_date', 'end_date', 'funding_source',
            'status', 'approved_by', 'notes',
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
        values.append(release_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE teaching_load_release_time SET '
                + ', '.join(fields) + ' WHERE release_id = ?',
                values)
            log_activity('update', 'teaching_load_release', details={
                'release_id': release_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def delete_release_time(release_id: int) -> None:
        """Delete a release time record.

        Args:
            release_id: The release time record to delete.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM teaching_load_release_time
                WHERE release_id = ?
            ''', (release_id,))
            log_activity('delete', 'teaching_load_release', details={
                'release_id': release_id,
            })

    # ==================== STANDARDS ====================

    @staticmethod
    def create_standard(department: str, role: str,
                        standard_credits: int = 12,
                        standard_courses: int = 4,
                        max_credits: int = 15,
                        max_new_preps: int = 2,
                        large_class_threshold: int = 50,
                        large_class_factor: float = 1.25,
                        overload_rate: float = 0,
                        is_default: bool = False) -> int:
        """Create a teaching load standard for a department and role.

        Standards define the expected teaching load, overload thresholds,
        and large class adjustments for a given department/role combination.

        Args:
            department: Department name the standard applies to.
            role: Faculty role the standard applies to (e.g. 'professor',
                  'lecturer', 'adjunct').
            standard_credits: Normal credit-hour load per semester (default 12).
            standard_courses: Normal number of courses per semester (default 4).
            max_credits: Maximum credits before overload (default 15).
            max_new_preps: Maximum new preparations allowed (default 2).
            large_class_threshold: Student count that triggers large class
                                   factor (default 50).
            large_class_factor: Multiplier for large class weighted hours
                                (default 1.25).
            overload_rate: Compensation rate per overload credit (default 0).
            is_default: Whether this is the fallback standard (default False).

        Returns:
            The standard_id of the newly created standard.
        """
        now = datetime.now().isoformat()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO teaching_load_standards (
                    department, role, standard_credits, standard_courses,
                    max_credits, max_new_preps, large_class_threshold,
                    large_class_factor, overload_rate, is_default,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                department, role, standard_credits, standard_courses,
                max_credits, max_new_preps, large_class_threshold,
                large_class_factor, overload_rate, int(is_default),
                now, now,
            ))
            standard_id = cursor.lastrowid
            log_activity('create', 'teaching_load_standard', details={
                'standard_id': standard_id, 'department': department,
                'role': role, 'standard_credits': standard_credits,
            })
            return standard_id

    @staticmethod
    def get_standards(department: str = None,
                      role: str = None) -> List[Dict[str, Any]]:
        """Get teaching load standards with optional filters.

        Args:
            department: Filter by department (optional).
            role: Filter by role (optional).

        Returns:
            A list of standard dicts ordered by department and role.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM teaching_load_standards WHERE 1=1'
            params: list = []

            if department:
                query += ' AND department = ?'
                params.append(department)

            if role:
                query += ' AND role = ?'
                params.append(role)

            query += ' ORDER BY department, role'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_standard(standard_id: int) -> Optional[Dict[str, Any]]:
        """Get a single teaching load standard by ID.

        Args:
            standard_id: The primary key of the standard.

        Returns:
            A dict of the standard row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM teaching_load_standards
                WHERE standard_id = ?
            ''', (standard_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_standard(standard_id: int, **data) -> None:
        """Update allowed fields on a teaching load standard.

        Allowed fields: standard_credits, standard_courses, max_credits,
        max_new_preps, large_class_threshold, large_class_factor,
        overload_rate.

        Args:
            standard_id: The standard to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'standard_credits', 'standard_courses', 'max_credits',
            'max_new_preps', 'large_class_threshold', 'large_class_factor',
            'overload_rate',
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
        values.append(standard_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE teaching_load_standards SET '
                + ', '.join(fields) + ' WHERE standard_id = ?',
                values)
            log_activity('update', 'teaching_load_standard', details={
                'standard_id': standard_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def delete_standard(standard_id: int) -> None:
        """Delete a teaching load standard.

        Args:
            standard_id: The standard to delete.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM teaching_load_standards
                WHERE standard_id = ?
            ''', (standard_id,))
            log_activity('delete', 'teaching_load_standard', details={
                'standard_id': standard_id,
            })

    # ==================== ANALYSIS ====================

    @staticmethod
    def _find_standard_for_user(conn, user_id: str,
                                department: str = None) -> Optional[Dict[str, Any]]:
        """Find the best matching teaching load standard for a user.

        Resolution order:
        1. Match by department and role (from user's course assignments).
        2. Match by role only.
        3. Fall back to the default standard.

        Args:
            conn: An active database connection.
            user_id: The user to find a standard for.
            department: Department to use for matching (optional).

        Returns:
            A dict of the matching standard, or None if no standard exists.
        """
        # Try to determine the user's department from their courses if not given
        if not department:
            dept_row = conn.execute('''
                SELECT department FROM teaching_load_courses
                WHERE user_id = ? AND department IS NOT NULL
                LIMIT 1
            ''', (user_id,)).fetchone()
            if dept_row:
                department = dict(dept_row).get('department')

        # Try department + role match
        if department:
            row = conn.execute('''
                SELECT * FROM teaching_load_standards
                WHERE department = ?
                ORDER BY is_default ASC
                LIMIT 1
            ''', (department,)).fetchone()
            if row:
                return dict(row)

        # Try role-only match (any non-default standard)
        row = conn.execute('''
            SELECT * FROM teaching_load_standards
            WHERE is_default = 0
            ORDER BY department
            LIMIT 1
        ''').fetchone()
        if row:
            return dict(row)

        # Fall back to default
        row = conn.execute('''
            SELECT * FROM teaching_load_standards
            WHERE is_default = 1
            LIMIT 1
        ''').fetchone()
        if row:
            return dict(row)

        return None

    @staticmethod
    def get_user_load_summary(user_id: str, academic_year: str,
                              semester: str) -> Dict[str, Any]:
        """Get a comprehensive teaching load summary for a user in a semester.

        Computes totals across all active course assignments and approved
        release time, then compares against the applicable teaching load
        standard to determine overload status.

        Args:
            user_id: The instructor's user ID.
            academic_year: The academic year.
            semester: The semester.

        Returns:
            A dict containing:
                - total_courses: Number of active course assignments.
                - total_credits: Sum of credit_hours across assignments.
                - total_contact_hours: Sum of contact_hours_pw.
                - total_weighted_hours: Sum of weighted_hours.
                - total_students: Sum of enrolled_students.
                - release_credits: Sum of credit_equivalent from approved
                  release time entries.
                - net_load: total_credits - release_credits.
                - standard_credits: The standard credit load (or None).
                - max_credits: The maximum before overload (or None).
                - is_overloaded: Whether net_load exceeds max_credits.
                - overload_credits: Credits above max_credits (0 if not
                  overloaded).
                - courses: List of course assignment dicts.
        """
        with get_connection() as conn:
            # Get active course assignments
            courses_rows = conn.execute('''
                SELECT * FROM teaching_load_courses
                WHERE user_id = ? AND academic_year = ? AND semester = ?
                  AND (status = 'active' OR status IS NULL)
                ORDER BY course_code
            ''', (user_id, academic_year, semester)).fetchall()
            courses = [dict(row) for row in courses_rows]

            total_courses = len(courses)
            total_credits = sum(c.get('credit_hours', 0) for c in courses)
            total_contact_hours = sum(
                c.get('contact_hours_pw', 0) for c in courses)
            total_weighted_hours = sum(
                c.get('weighted_hours', 0) for c in courses)
            total_students = sum(
                c.get('enrolled_students', 0) for c in courses)

            # Get approved release time
            release_rows = conn.execute('''
                SELECT * FROM teaching_load_release_time
                WHERE user_id = ? AND academic_year = ? AND semester = ?
                  AND status = 'approved'
            ''', (user_id, academic_year, semester)).fetchall()
            release_credits = sum(
                dict(r).get('credit_equivalent', 0) for r in release_rows)

            net_load = total_credits - release_credits

            # Find applicable standard
            standard = TeachingLoadManager._find_standard_for_user(
                conn, user_id)

            standard_credits = None
            max_credits = None
            is_overloaded = False
            overload_credits = 0

            if standard:
                standard_credits = standard.get('standard_credits', 12)
                max_credits = standard.get('max_credits', 15)
                is_overloaded = net_load > max_credits
                overload_credits = max(0, net_load - max_credits)

            return {
                'user_id': user_id,
                'academic_year': academic_year,
                'semester': semester,
                'total_courses': total_courses,
                'total_credits': total_credits,
                'total_contact_hours': total_contact_hours,
                'total_weighted_hours': total_weighted_hours,
                'total_students': total_students,
                'release_credits': release_credits,
                'net_load': net_load,
                'standard_credits': standard_credits,
                'max_credits': max_credits,
                'is_overloaded': is_overloaded,
                'overload_credits': overload_credits,
                'courses': courses,
            }

    @staticmethod
    def detect_overload(user_id: str, academic_year: str,
                        semester: str) -> Dict[str, Any]:
        """Detect whether a user is overloaded for a given semester.

        Args:
            user_id: The instructor's user ID.
            academic_year: The academic year.
            semester: The semester.

        Returns:
            A dict containing:
                - is_overloaded: Boolean indicating overload status.
                - overload_credits: Number of credits above the maximum.
                - standard: The standard dict used for comparison, or None.
        """
        with get_connection() as conn:
            # Calculate total credits from active courses
            row = conn.execute('''
                SELECT COALESCE(SUM(credit_hours), 0) as total_credits
                FROM teaching_load_courses
                WHERE user_id = ? AND academic_year = ? AND semester = ?
                  AND (status = 'active' OR status IS NULL)
            ''', (user_id, academic_year, semester)).fetchone()
            total_credits = dict(row).get('total_credits', 0)

            # Calculate release credits
            rel_row = conn.execute('''
                SELECT COALESCE(SUM(credit_equivalent), 0) as release_credits
                FROM teaching_load_release_time
                WHERE user_id = ? AND academic_year = ? AND semester = ?
                  AND status = 'approved'
            ''', (user_id, academic_year, semester)).fetchone()
            release_credits = dict(rel_row).get('release_credits', 0)

            net_load = total_credits - release_credits

            standard = TeachingLoadManager._find_standard_for_user(
                conn, user_id)

            is_overloaded = False
            overload_credits = 0

            if standard:
                max_credits = standard.get('max_credits', 15)
                is_overloaded = net_load > max_credits
                overload_credits = max(0, net_load - max_credits)

            return {
                'is_overloaded': is_overloaded,
                'overload_credits': overload_credits,
                'standard': standard,
            }

    @staticmethod
    def get_semester_comparison(user_id: str) -> List[Dict[str, Any]]:
        """Get all historical load snapshots for a user across semesters.

        Useful for comparing teaching load trends over time.

        Args:
            user_id: The instructor's user ID.

        Returns:
            A list of history record dicts ordered by academic_year
            descending, then semester.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM teaching_load_history
                WHERE user_id = ?
                ORDER BY academic_year DESC, semester
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def snapshot_semester(user_id: str, academic_year: str,
                          semester: str) -> int:
        """Take a snapshot of the user's load and save to history.

        Calculates the full load summary and inserts or replaces the
        record in teaching_load_history (UNIQUE on user_id, academic_year,
        semester).

        Args:
            user_id: The instructor's user ID.
            academic_year: The academic year.
            semester: The semester.

        Returns:
            The history_id of the inserted or replaced history record.
        """
        summary = TeachingLoadManager.get_user_load_summary(
            user_id, academic_year, semester)

        now = datetime.now().isoformat()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO teaching_load_history (
                    user_id, academic_year, semester, total_courses,
                    total_credits, total_contact_hours, total_weighted_hours,
                    total_students, release_hours, net_load_credits,
                    is_overloaded, overload_credits, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, academic_year, semester,
                summary['total_courses'],
                summary['total_credits'],
                summary['total_contact_hours'],
                summary['total_weighted_hours'],
                summary['total_students'],
                summary['release_credits'],
                summary['net_load'],
                int(summary['is_overloaded']),
                summary['overload_credits'],
                now,
            ))
            history_id = cursor.lastrowid
            log_activity('create', 'teaching_load_history', details={
                'history_id': history_id, 'user_id': user_id,
                'academic_year': academic_year, 'semester': semester,
                'net_load': summary['net_load'],
                'is_overloaded': summary['is_overloaded'],
            })
            return history_id

    # ==================== DEPARTMENT ====================

    @staticmethod
    def get_department_loads(department: str, academic_year: str,
                            semester: str) -> List[Dict[str, Any]]:
        """Get per-user teaching load summaries for an entire department.

        Args:
            department: The department to query.
            academic_year: The academic year.
            semester: The semester.

        Returns:
            A list of dicts, one per user, containing:
                - user_id
                - total_courses
                - total_credits
                - net_load
                - is_overloaded
        """
        with get_connection() as conn:
            # Get distinct users in the department for this term
            user_rows = conn.execute('''
                SELECT DISTINCT user_id
                FROM teaching_load_courses
                WHERE department = ? AND academic_year = ? AND semester = ?
                  AND (status = 'active' OR status IS NULL)
                ORDER BY user_id
            ''', (department, academic_year, semester)).fetchall()

        results = []
        for user_row in user_rows:
            uid = dict(user_row)['user_id']
            summary = TeachingLoadManager.get_user_load_summary(
                uid, academic_year, semester)
            results.append({
                'user_id': uid,
                'total_courses': summary['total_courses'],
                'total_credits': summary['total_credits'],
                'net_load': summary['net_load'],
                'is_overloaded': summary['is_overloaded'],
            })

        return results

    @staticmethod
    def get_load_balance_suggestions(department: str, academic_year: str,
                                     semester: str) -> List[Dict[str, Any]]:
        """Identify overloaded and underloaded staff and suggest transfers.

        Compares each instructor's net load against the department standard.
        Staff above max_credits are considered overloaded; staff below
        standard_credits are considered underloaded. For each overloaded
        instructor, a suggestion is generated pairing them with an
        underloaded instructor who has capacity.

        Args:
            department: The department to analyse.
            academic_year: The academic year.
            semester: The semester.

        Returns:
            A list of suggestion dicts, each containing:
                - from_user_id: The overloaded instructor.
                - to_user_id: The underloaded instructor.
                - overload_credits: How many credits the overloaded
                  instructor is above the maximum.
                - available_capacity: How many credits the underloaded
                  instructor can absorb.
                - suggested_transfer: The minimum of overload_credits and
                  available_capacity.
                - reason: A human-readable explanation.
        """
        loads = TeachingLoadManager.get_department_loads(
            department, academic_year, semester)

        # Look up the department standard
        with get_connection() as conn:
            std_row = conn.execute('''
                SELECT * FROM teaching_load_standards
                WHERE department = ?
                ORDER BY is_default ASC
                LIMIT 1
            ''', (department,)).fetchone()
            if not std_row:
                std_row = conn.execute('''
                    SELECT * FROM teaching_load_standards
                    WHERE is_default = 1
                    LIMIT 1
                ''').fetchone()

        if not std_row:
            return []

        standard = dict(std_row)
        standard_credits = standard.get('standard_credits', 12)
        max_credits = standard.get('max_credits', 15)

        overloaded = []
        underloaded = []

        for load in loads:
            net = load['net_load']
            if net > max_credits:
                overloaded.append({
                    'user_id': load['user_id'],
                    'overload_credits': net - max_credits,
                    'net_load': net,
                })
            elif net < standard_credits:
                underloaded.append({
                    'user_id': load['user_id'],
                    'available_capacity': standard_credits - net,
                    'net_load': net,
                })

        suggestions = []
        underloaded_idx = 0

        for over in overloaded:
            remaining_overload = over['overload_credits']
            while remaining_overload > 0 and underloaded_idx < len(underloaded):
                under = underloaded[underloaded_idx]
                if under['available_capacity'] <= 0:
                    underloaded_idx += 1
                    continue

                transfer = min(remaining_overload, under['available_capacity'])
                suggestions.append({
                    'from_user_id': over['user_id'],
                    'to_user_id': under['user_id'],
                    'overload_credits': over['overload_credits'],
                    'available_capacity': under['available_capacity'],
                    'suggested_transfer': transfer,
                    'reason': (
                        f"Transfer {transfer} credit(s) from "
                        f"{over['user_id']} (net load {over['net_load']}, "
                        f"overloaded by {over['overload_credits']}) to "
                        f"{under['user_id']} (net load {under['net_load']}, "
                        f"capacity for {under['available_capacity']} more)"
                    ),
                })
                remaining_overload -= transfer
                under['available_capacity'] -= transfer
                if under['available_capacity'] <= 0:
                    underloaded_idx += 1

        log_activity('query', 'teaching_load_balance', details={
            'department': department, 'academic_year': academic_year,
            'semester': semester, 'suggestions_count': len(suggestions),
        })

        return suggestions

    # ==================== IMPORT ====================

    @staticmethod
    def import_course_assignments(assignments: List[Dict[str, Any]],
                                  created_by: str = None) -> Dict[str, Any]:
        """Bulk import course assignments from a list of dictionaries.

        Each dictionary in the list should contain the same fields accepted
        by add_course_assignment. Missing optional fields use their defaults.

        Args:
            assignments: A list of dicts, each representing a course
                         assignment. Required keys: user_id, course_code,
                         course_name, section, academic_year, semester.
            created_by: User ID of the person performing the import.

        Returns:
            A dict containing:
                - imported: Number of successfully imported assignments.
                - errors: A list of error dicts with 'index' and 'error'
                  keys for any failed imports.
        """
        imported = 0
        errors = []

        for idx, assignment in enumerate(assignments):
            try:
                # Validate required fields
                required = [
                    'user_id', 'course_code', 'course_name',
                    'section', 'academic_year', 'semester',
                ]
                missing = [f for f in required if f not in assignment]
                if missing:
                    raise ValueError(
                        f"Missing required fields: {', '.join(missing)}")

                TeachingLoadManager.add_course_assignment(
                    user_id=assignment['user_id'],
                    course_code=assignment['course_code'],
                    course_name=assignment['course_name'],
                    section=assignment['section'],
                    academic_year=assignment['academic_year'],
                    semester=assignment['semester'],
                    credit_hours=assignment.get('credit_hours', 3.0),
                    contact_hours_pw=assignment.get('contact_hours_pw', 3.0),
                    lecture_hours_pw=assignment.get('lecture_hours_pw'),
                    lab_hours_pw=assignment.get('lab_hours_pw'),
                    tutorial_hours_pw=assignment.get('tutorial_hours_pw'),
                    enrolled_students=assignment.get('enrolled_students', 0),
                    max_enrollment=assignment.get('max_enrollment', 30),
                    department=assignment.get('department'),
                    is_new_prep=assignment.get('is_new_prep', False),
                    is_team_taught=assignment.get('is_team_taught', False),
                    team_share_pct=assignment.get('team_share_pct', 100),
                    source=assignment.get('source', 'import'),
                    notes=assignment.get('notes'),
                    created_by=created_by,
                )
                imported += 1
            except Exception as exc:
                errors.append({
                    'index': idx,
                    'error': str(exc),
                })

        log_activity('import', 'teaching_load_courses', details={
            'total': len(assignments), 'imported': imported,
            'errors_count': len(errors), 'created_by': created_by,
        })

        return {
            'imported': imported,
            'errors': errors,
        }
