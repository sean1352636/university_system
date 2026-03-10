"""Staff directory service."""

import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class StaffDirectoryService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_entry(self, first_name, last_name, title="Mr", role="Teacher",
                  department=None, email=None, phone_ext=None, room=None,
                  subjects=None, responsibilities=None, staff_id=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO staff_directory
                   (staff_id, first_name, last_name, title, role, department,
                    email, phone_ext, room, subjects, responsibilities)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_id, first_name, last_name, title, role, department,
                 email, phone_ext, room, subjects, responsibilities))
            conn.commit()
            return dict(conn.execute("SELECT * FROM staff_directory WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def list_staff(self, department=None, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM staff_directory WHERE 1=1"
            params = []
            if department:
                sql += " AND department = ?"
                params.append(department)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY last_name, first_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_departments(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT department FROM staff_directory WHERE department IS NOT NULL ORDER BY department"
            ).fetchall()
            return [r["department"] for r in rows]
        finally:
            conn.close()

    def delete_entry(self, entry_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM staff_directory WHERE id = ?", (entry_id,))
            conn.commit()
        finally:
            conn.close()
