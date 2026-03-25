"""Staff directory service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import StaffError
from education_system.primary_school.core.sql_safety import escape_like
import traceback

logger = logging.getLogger(__name__)


class StaffDirectoryService:
    """Read-only queries against the staff table for directory purposes."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def list_all(self, search=None):
        """List all active staff with optional name/role search."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM staff WHERE status = 'Active'"
            params = []
            if search:
                sql += " AND (first_name LIKE ? OR last_name LIKE ? OR role LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY last_name, first_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_role(self, role):
        """Get staff filtered by role."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM staff
                WHERE role = ? AND status = 'Active'
                ORDER BY last_name, first_name""",
                (role,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_class_teachers(self):
        """Get staff who are assigned as class teachers."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM staff
                WHERE class_teacher_of IS NOT NULL AND status = 'Active'
                ORDER BY class_teacher_of""",
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
