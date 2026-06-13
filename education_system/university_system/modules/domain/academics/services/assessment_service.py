"""Shared Assessment/Assignment Data Service
This service provides unified access to assessments and assignments for both
the Grade Tracking GUI and Assignment GUI systems.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
from typing import List, Dict, Optional, Tuple
from datetime import datetime

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH


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

            # Create new assignment
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO assignments
                (module_code, title, description, due_date, max_marks,
                 created_by, created_at, updated_at, is_active, assignment_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                assessment['module_code'],
                assessment['assessment_name'],
                assessment.get('description', ''),
                assessment.get('due_date', timestamp),
                assessment['max_points'],
                created_by,
                timestamp,
                timestamp,
                assessment.get('assessment_type', 'individual')
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
