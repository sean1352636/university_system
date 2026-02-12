"""Teaching Assistant Management Service.

Provides functionality for assigning, managing, and tracking Teaching Assistants
across modules, including role management, permission controls, and workload tracking.
"""

from __future__ import annotations

import logging
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

# Valid role types for teaching assistants
VALID_ROLE_TYPES = ('ta', 'lead_ta', 'grader')

# Valid permission types that can be granted to TAs
VALID_PERMISSION_TYPES = (
    'grade_assignments',
    'take_attendance',
    'upload_materials',
    'manage_discussions',
    'view_student_info',
)

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row object to a plain dictionary.

    Args:
        row: A sqlite3.Row instance returned from a query.

    Returns:
        A dictionary mapping column names to their values.
    """
    return dict(row)

class TAService:
    """Service class for managing Teaching Assistants.

    Handles TA assignment, removal, updates, permission management,
    and workload tracking. All mutation operations are logged via
    the centralized activity logger.
    """

    def __init__(self) -> None:
        """Initialize TAService and ensure database tables exist."""
        self._init_db()

    def _init_db(self) -> None:
        """Create the teaching_assistants and ta_permissions tables if they do not exist."""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS teaching_assistants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        instructor_id TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        role_type TEXT DEFAULT 'ta',
                        hours_per_week REAL DEFAULT 10,
                        status TEXT DEFAULT 'active',
                        start_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        end_date TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(student_id, module_code)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ta_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ta_id INTEGER NOT NULL,
                        permission_type TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        granted_by TEXT NOT NULL,
                        granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (ta_id) REFERENCES teaching_assistants(id),
                        UNIQUE(ta_id, permission_type, module_code)
                    )
                ''')
            logger.info("TA management tables initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize TA management tables: {e}")
            raise

    # ------------------------------------------------------------------
    # TA Assignment CRUD
    # ------------------------------------------------------------------

    def assign_ta(
        self,
        student_id: str,
        instructor_id: str,
        module_code: str,
        role_type: str = 'ta',
        hours_per_week: float = 10,
    ) -> int:
        """Assign a student as a Teaching Assistant for a module.

        Args:
            student_id: The student's unique identifier.
            instructor_id: The supervising instructor's identifier.
            module_code: The module/course code.
            role_type: One of 'ta', 'lead_ta', or 'grader'.
            hours_per_week: Weekly hours commitment.

        Returns:
            The ID of the newly created TA assignment.

        Raises:
            ValueError: If role_type is not valid.
            sqlite3.IntegrityError: If the student is already a TA for this module.
        """
        if role_type not in VALID_ROLE_TYPES:
            raise ValueError(
                f"Invalid role_type '{role_type}'. Must be one of {VALID_ROLE_TYPES}"
            )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO teaching_assistants
                    (student_id, instructor_id, module_code, role_type,
                     hours_per_week, status, start_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
                ''',
                (student_id, instructor_id, module_code, role_type,
                 hours_per_week, now, now, now),
            )
            ta_id = cursor.lastrowid

        log_activity(
            'create', 'teaching_assistant',
            details={
                'ta_id': ta_id,
                'student_id': student_id,
                'instructor_id': instructor_id,
                'module_code': module_code,
                'role_type': role_type,
                'hours_per_week': hours_per_week,
            },
        )
        logger.info(
            f"Assigned TA: student={student_id}, module={module_code}, "
            f"role={role_type}, id={ta_id}"
        )
        return ta_id

    def remove_ta(self, ta_id: int) -> bool:
        """Remove (deactivate) a TA assignment by setting its status to 'inactive'.

        Args:
            ta_id: The TA assignment ID to deactivate.

        Returns:
            True if the assignment was found and deactivated, False otherwise.
        """
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                UPDATE teaching_assistants
                SET status = 'inactive', end_date = ?, updated_at = ?
                WHERE id = ? AND status = 'active'
                ''',
                (now, now, ta_id),
            )
            rows_affected = cursor.rowcount

        if rows_affected > 0:
            log_activity(
                'delete', 'teaching_assistant',
                details={'ta_id': ta_id},
            )
            logger.info(f"Removed TA assignment: id={ta_id}")
            return True

        logger.warning(f"TA assignment not found or already inactive: id={ta_id}")
        return False

    def update_ta(self, ta_id: int, **kwargs: Any) -> bool:
        """Update fields on an existing TA assignment.

        Supported keyword arguments: role_type, hours_per_week, status,
        instructor_id, end_date.

        Args:
            ta_id: The TA assignment ID to update.
            **kwargs: Field-value pairs to update.

        Returns:
            True if the record was updated, False if not found or no valid fields.

        Raises:
            ValueError: If role_type is provided but invalid.
        """
        allowed_fields = {
            'role_type', 'hours_per_week', 'status', 'instructor_id', 'end_date',
        }
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_fields:
            logger.warning(f"No valid fields provided for TA update: id={ta_id}")
            return False

        if 'role_type' in update_fields and update_fields['role_type'] not in VALID_ROLE_TYPES:
            raise ValueError(
                f"Invalid role_type '{update_fields['role_type']}'. "
                f"Must be one of {VALID_ROLE_TYPES}"
            )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        update_fields['updated_at'] = now

        set_clause = ', '.join(f'{field} = ?' for field in update_fields)
        values = list(update_fields.values()) + [ta_id]

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE teaching_assistants SET {set_clause} WHERE id = ?',
                values,
            )
            rows_affected = cursor.rowcount

        if rows_affected > 0:
            log_activity(
                'update', 'teaching_assistant',
                details={'ta_id': ta_id, 'updated_fields': update_fields},
            )
            logger.info(f"Updated TA assignment: id={ta_id}, fields={list(update_fields.keys())}")
            return True

        logger.warning(f"TA assignment not found for update: id={ta_id}")
        return False

    def get_ta(self, ta_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single TA assignment by ID.

        Args:
            ta_id: The TA assignment ID.

        Returns:
            A dictionary of the TA record, or None if not found.
        """
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM teaching_assistants WHERE id = ?',
                (ta_id,),
            )
            row = cursor.fetchone()

        if row:
            return _row_to_dict(row)
        return None

    # ------------------------------------------------------------------
    # Permission Management
    # ------------------------------------------------------------------

    def set_ta_permissions(
        self,
        ta_id: int,
        permission_types: List[str],
        module_code: str,
        granted_by: str,
    ) -> bool:
        """Set (replace) the permissions for a TA on a specific module.

        Existing permissions for this TA and module are removed, then the
        new set of permissions is inserted.

        Args:
            ta_id: The TA assignment ID.
            permission_types: List of permission type strings to grant.
            module_code: The module code the permissions apply to.
            granted_by: Identifier of the user granting permissions.

        Returns:
            True if permissions were set successfully.

        Raises:
            ValueError: If any permission_type is invalid.
        """
        invalid = [p for p in permission_types if p not in VALID_PERMISSION_TYPES]
        if invalid:
            raise ValueError(
                f"Invalid permission types: {invalid}. "
                f"Valid types are {VALID_PERMISSION_TYPES}"
            )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as conn:
            cursor = conn.cursor()

            # Remove existing permissions for this TA on this module
            cursor.execute(
                'DELETE FROM ta_permissions WHERE ta_id = ? AND module_code = ?',
                (ta_id, module_code),
            )

            # Insert new permissions
            for perm_type in permission_types:
                cursor.execute(
                    '''
                    INSERT INTO ta_permissions
                        (ta_id, permission_type, module_code, granted_by, granted_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (ta_id, perm_type, module_code, granted_by, now),
                )

        log_activity(
            'update', 'ta_permissions',
            details={
                'ta_id': ta_id,
                'module_code': module_code,
                'permissions': permission_types,
                'granted_by': granted_by,
            },
        )
        logger.info(
            f"Set TA permissions: ta_id={ta_id}, module={module_code}, "
            f"permissions={permission_types}"
        )
        return True

    def check_ta_permission(
        self,
        student_id: str,
        module_code: str,
        permission_type: str,
    ) -> bool:
        """Check whether a student has a specific TA permission for a module.

        Only active TA assignments are considered.

        Args:
            student_id: The student's unique identifier.
            module_code: The module code to check.
            permission_type: The permission type to verify.

        Returns:
            True if the student holds the specified permission, False otherwise.
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT 1
                FROM ta_permissions tp
                JOIN teaching_assistants ta ON tp.ta_id = ta.id
                WHERE ta.student_id = ?
                  AND tp.module_code = ?
                  AND tp.permission_type = ?
                  AND ta.status = 'active'
                LIMIT 1
                ''',
                (student_id, module_code, permission_type),
            )
            result = cursor.fetchone()

        return result is not None

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_tas_for_module(self, module_code: str) -> List[Dict[str, Any]]:
        """Get all active TAs assigned to a specific module.

        Args:
            module_code: The module code to query.

        Returns:
            A list of TA assignment dictionaries.
        """
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM teaching_assistants
                WHERE module_code = ? AND status = 'active'
                ORDER BY role_type, student_id
                ''',
                (module_code,),
            )
            rows = cursor.fetchall()

        return [_row_to_dict(row) for row in rows]

    def get_ta_assignments_for_student(self, student_id: str) -> List[Dict[str, Any]]:
        """Get all TA assignments (active and inactive) for a student.

        Args:
            student_id: The student's unique identifier.

        Returns:
            A list of TA assignment dictionaries.
        """
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM teaching_assistants
                WHERE student_id = ?
                ORDER BY status, start_date DESC
                ''',
                (student_id,),
            )
            rows = cursor.fetchall()

        return [_row_to_dict(row) for row in rows]

    def get_ta_workload(self, student_id: str) -> Dict[str, Any]:
        """Get the total workload summary for a student across all active TA assignments.

        Args:
            student_id: The student's unique identifier.

        Returns:
            A dictionary containing:
                - total_hours: Total hours per week across all assignments.
                - assignment_count: Number of active assignments.
                - assignments: List of active assignment dictionaries.
        """
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM teaching_assistants
                WHERE student_id = ? AND status = 'active'
                ORDER BY module_code
                ''',
                (student_id,),
            )
            rows = cursor.fetchall()

        assignments = [_row_to_dict(row) for row in rows]
        total_hours = sum(a.get('hours_per_week', 0) for a in assignments)

        return {
            'total_hours': total_hours,
            'assignment_count': len(assignments),
            'assignments': assignments,
        }

    def get_all_tas(self, status: str = 'active') -> List[Dict[str, Any]]:
        """Get all TA assignments filtered by status.

        Args:
            status: The status to filter by (e.g. 'active', 'inactive').
                Defaults to 'active'.

        Returns:
            A list of TA assignment dictionaries.
        """
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM teaching_assistants
                WHERE status = ?
                ORDER BY module_code, student_id
                ''',
                (status,),
            )
            rows = cursor.fetchall()

        return [_row_to_dict(row) for row in rows]
