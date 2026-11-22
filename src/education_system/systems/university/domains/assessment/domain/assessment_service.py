"""Shared Assessment/Assignment Data Service
This service provides unified access to assessments and assignments for both
the Grade Tracking GUI and Assignment GUI systems.
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH


class AssessmentAssignmentService:
    """Unified service for accessing assessments and assignments"""

    @staticmethod
    def get_all_assessments(module_code: Optional[str] = None) -> List[Dict]:
        """Get all assessments, optionally filtered by module

        Args:
            module_code: Optional module code to filter by

        Returns:
            List of assessment dictionaries
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if module_code:
                cursor.execute("""
                    SELECT * FROM assessments
                    WHERE module_code = ?
                    ORDER BY due_date DESC
                """, (module_code,))
            else:
                cursor.execute("""
                    SELECT * FROM assessments
                    ORDER BY due_date DESC
                """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all_assignments(module_code: Optional[str] = None,
                           student_id: Optional[str] = None) -> List[Dict]:
        """Get all assignments, optionally filtered by module and/or student

        Args:
            module_code: Optional module code to filter by
            student_id: Optional student ID to filter by enrollment

        Returns:
            List of assignment dictionaries
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if student_id and module_code:
                cursor.execute("""
                    SELECT a.* FROM assignments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ? AND a.module_code = ? AND a.is_active = 1
                    ORDER BY a.due_date DESC
                """, (student_id, module_code))
            elif student_id:
                cursor.execute("""
                    SELECT a.* FROM assignments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ? AND a.is_active = 1
                    ORDER BY a.due_date DESC
                """, (student_id,))
            elif module_code:
                cursor.execute("""
                    SELECT * FROM assignments
                    WHERE module_code = ? AND is_active = 1
                    ORDER BY due_date DESC
                """, (module_code,))
            else:
                cursor.execute("""
                    SELECT * FROM assignments
                    WHERE is_active = 1
                    ORDER BY due_date DESC
                """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_assessment_by_id(assessment_id: int) -> Optional[Dict]:
        """Get a single assessment by ID

        Args:
            assessment_id: The assessment ID

        Returns:
            Assessment dictionary or None if not found
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM assessments WHERE assessment_id = ?",
                         (assessment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_assignment_by_id(assignment_id: int) -> Optional[Dict]:
        """Get a single assignment by ID

        Args:
            assignment_id: The assignment ID

        Returns:
            Assignment dictionary or None if not found
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM assignments WHERE id = ?",
                         (assignment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _resolve_author(cursor, created_by):
        """A users.id that actually exists, for the NOT NULL author column.

        Prefers the id supplied by the caller. Falls back to a system
        account, then to the lowest admin — never invents an id, because
        the column is a foreign key.
        """
        if created_by:
            cursor.execute("SELECT 1 FROM users WHERE id = ?", (created_by,))
            if cursor.fetchone():
                return created_by
        for sql in (
            "SELECT id FROM users WHERE COALESCE(service_account, 0) = 1 ORDER BY id LIMIT 1",
            "SELECT id FROM users WHERE username LIKE 'system%' ORDER BY id LIMIT 1",
            "SELECT id FROM users WHERE LOWER(role) = 'admin' ORDER BY id LIMIT 1",
            "SELECT id FROM users ORDER BY id LIMIT 1",
        ):
            cursor.execute(sql)
            row = cursor.fetchone()
            if row:
                return row['id'] if hasattr(row, 'keys') else row[0]
        raise ValueError(
            "assignments.created_by requires a real user and none exists")

    @staticmethod
    def sync_assignment_to_assessment(assignment_id: int) -> Optional[int]:
        """Create an assessment from an assignment if it doesn't exist

        Args:
            assignment_id: The assignment ID to sync

        Returns:
            The assessment_id (new or existing)
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get assignment data. Same Row→dict bridge as
            # sync_assessment_to_assignment so the .get(default) calls
            # below tolerate optional columns.
            cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            assignment = dict(row)

            # Check if assessment already exists for this assignment
            cursor.execute("""
                SELECT assessment_id FROM assessments
                WHERE assessment_name = ? AND module_code = ?
            """, (assignment['title'], assignment['module_code']))

            existing = cursor.fetchone()
            if existing:
                return existing['assessment_id']

            # Create new assessment
            cursor.execute("""
                INSERT INTO assessments
                (assessment_name, assessment_type, module_code, max_points,
                 weight, due_date, description, rubric)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assignment['title'],
                assignment.get('assignment_type', 'Assignment'),
                assignment['module_code'],
                assignment['max_marks'],
                0.0,  # Default weight
                assignment['due_date'],
                assignment.get('description', ''),
                ''  # Empty rubric
            ))

            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def sync_assessment_to_assignment(assessment_id: int, created_by: int) -> Optional[int]:
        """Create an assignment from an assessment if it doesn't exist

        Args:
            assessment_id: The assessment ID to sync
            created_by: User ID creating the assignment

        Returns:
            The assignment id (new or existing)
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get assessment data. fetchone() returns a sqlite3.Row when
            # row_factory is set; Row supports key indexing but not .get(),
            # so wrap in dict() — that also lets the .get(default) calls
            # below survive older schemas missing optional columns.
            cursor.execute("SELECT * FROM assessments WHERE assessment_id = ?",
                         (assessment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            assessment = dict(row)

            # Check if assignment already exists for this assessment
            cursor.execute("""
                SELECT id FROM assignments
                WHERE title = ? AND module_code = ?
            """, (assessment['assessment_name'], assessment['module_code']))

            existing = cursor.fetchone()
            if existing:
                return existing['id']

            # Create new assignment.
            #
            # assignments.created_by is NOT NULL *and* a foreign key to
            # users(id), so an author that is neither real nor omissible
            # has to be resolved. Callers that cannot name one (a
            # background sync, or a GUI whose session has no numeric id)
            # passed 0, the insert died with "FOREIGN KEY constraint
            # failed", and the callers swallowed it — so the mirror
            # silently never happened. Fall back to a system account,
            # which is at least honest about who made the row.
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            created_by = AssessmentAssignmentService._resolve_author(cursor, created_by)
            cursor.execute("""
                INSERT INTO assignments
                (module_code, title, description, due_date, max_marks,
                 created_by, created_at, updated_at, is_active, assignment_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                assessment['module_code'],
                assessment['assessment_name'],
                assessment.get('description') or '',
                # due_date is NOT NULL, and .get(k, default)
                # returns None when the column exists but is
                # empty — which is exactly the case here.
                assessment.get('due_date') or timestamp,
                assessment['max_points'],
                created_by,
                timestamp,
                timestamp,
                assessment.get('assessment_type') or 'individual'
            ))

            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_modules() -> List[Tuple[str, str]]:
        """Get all modules

        Returns:
            List of (module_code, module_name) tuples
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Writes
    #
    # Grade Tracking and the Assignment GUI both create, copy and delete
    # this material, and each had its own SQL for it. Grade Tracking's
    # list merges assessments, assignments and exams, so its operations
    # have to work out which table a row actually lives in — logic the
    # Assignment GUI's copy never had. Rather than duplicate either one,
    # both now call these.
    #
    # A row id prefixed "A" is an assignment; anything else is an
    # assessment. That is the convention the merged list already uses.
    # ------------------------------------------------------------------

    @staticmethod
    def _open():
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def is_assignment_id(raw_id) -> bool:
        """True when a merged-list id refers to the assignments table."""
        return str(raw_id).startswith('A')

    @staticmethod
    def create_assessment(*, name: str, assessment_type: str, module_code: str,
                          max_points: float, weight: float = 0.0,
                          due_date: Optional[str] = None,
                          duration_minutes: Optional[int] = None,
                          status: str = 'Draft', description: str = '',
                          rubric: str = '', mirror_to_assignments: bool = True,
                          created_by: int = 0) -> Optional[int]:
        """Create an assessment, optionally mirroring it to assignments.

        The mirror is what makes a newly created assessment visible in
        the Assignment GUI. Without it the two screens showed different
        sets of work and each had to be told separately.
        """
        conn = AssessmentAssignmentService._open()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO assessments
                (assessment_name, assessment_type, module_code, max_points, weight,
                 due_date, duration_minutes, status, description, rubric, date_created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, assessment_type, module_code, max_points, weight, due_date,
                  duration_minutes, status, description, rubric,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            assessment_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        if mirror_to_assignments and assessment_id:
            try:
                AssessmentAssignmentService.sync_assessment_to_assignment(
                    assessment_id, created_by)
            except Exception:
                # A failed mirror must not lose the assessment that was
                # genuinely created — the sync can be re-run later — but it
                # is logged, because a silently absent mirror looks exactly
                # like a working one from the calling screen.
                logger.exception(
                    "Assessment %s created but could not be mirrored to assignments",
                    assessment_id)
        return assessment_id

    @staticmethod
    def update_assessment(assessment_id, fields: Dict) -> bool:
        """Update an assessment row from a {column: value} mapping."""
        if not fields:
            return False
        conn = AssessmentAssignmentService._open()
        try:
            sets = ", ".join(f"{col} = ?" for col in fields)
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE assessments SET {sets} WHERE assessment_id = ?",
                (*fields.values(), assessment_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def update_assignment(assignment_id, fields: Dict) -> bool:
        """Update an assignment row from a {column: value} mapping."""
        if not fields:
            return False
        conn = AssessmentAssignmentService._open()
        try:
            sets = ", ".join(f"{col} = ?" for col in fields)
            cursor = conn.cursor()
            cursor.execute(f"UPDATE assignments SET {sets} WHERE id = ?",
                           (*fields.values(), assignment_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def delete_item(raw_id) -> bool:
        """Delete an assessment or assignment, with its dependent rows.

        Which table is decided by the id prefix, so a caller working from
        the merged list does not have to know.
        """
        is_assignment = AssessmentAssignmentService.is_assignment_id(raw_id)
        conn = AssessmentAssignmentService._open()
        try:
            cursor = conn.cursor()
            if is_assignment:
                real_id = int(str(raw_id)[1:])
                # Submissions and groups reference the assignment; they go
                # with it, and the FK pragma is relaxed only for that span.
                cursor.execute("PRAGMA foreign_keys = OFF")
                cursor.execute("DELETE FROM assignment_submissions WHERE assignment_id = ?",
                               (real_id,))
                cursor.execute("DELETE FROM group_members WHERE group_id IN "
                               "(SELECT id FROM groups WHERE assignment_id = ?)", (real_id,))
                cursor.execute("DELETE FROM groups WHERE assignment_id = ?", (real_id,))
                cursor.execute("DELETE FROM assignments WHERE id = ?", (real_id,))
                cursor.execute("PRAGMA foreign_keys = ON")
            else:
                cursor.execute("DELETE FROM grades WHERE assessment_id = ?", (raw_id,))
                cursor.execute("DELETE FROM assessments WHERE assessment_id = ?", (raw_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def copy_item(raw_id) -> Optional[str]:
        """Duplicate an assessment or assignment. Returns the new name."""
        is_assignment = AssessmentAssignmentService.is_assignment_id(raw_id)
        conn = AssessmentAssignmentService._open()
        try:
            cursor = conn.cursor()
            if is_assignment:
                real_id = int(str(raw_id)[1:])
                cursor.execute("""
                    SELECT title, assignment_type, module_code, COALESCE(max_marks, 100)
                           AS max_marks, due_date, description, instructions
                    FROM assignments WHERE id = ?""", (real_id,))
                data = cursor.fetchone()
                if not data:
                    return None
                new_name = f"Copy of {data['title']}"
                cursor.execute("PRAGMA foreign_keys = OFF")
                cursor.execute("""
                    INSERT INTO assignments
                    (title, assignment_type, module_code, max_marks, due_date,
                     description, instructions, is_active, created_by,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'system',
                            datetime('now'), datetime('now'))
                """, (new_name, data['assignment_type'], data['module_code'],
                      data['max_marks'], data['due_date'], data['description'],
                      data['instructions']))
                cursor.execute("PRAGMA foreign_keys = ON")
            else:
                cursor.execute("""
                    SELECT assessment_name, assessment_type, module_code, max_points,
                           weight, due_date, description, rubric
                    FROM assessments WHERE assessment_id = ?""", (raw_id,))
                data = cursor.fetchone()
                if not data:
                    return None
                new_name = f"Copy of {data['assessment_name']}"
                cursor.execute("""
                    INSERT INTO assessments
                    (assessment_name, assessment_type, module_code, max_points,
                     weight, due_date, description, rubric, date_created)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (new_name, data['assessment_type'], data['module_code'],
                      data['max_points'], data['weight'], data['due_date'],
                      data['description'], data['rubric']))
            conn.commit()
            return new_name
        finally:
            conn.close()
