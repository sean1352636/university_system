"""Form Groups / Tutor Groups service."""

import logging
from education_system.secondary_school.core.exceptions import FormGroupError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

YEAR_GROUPS = ("7", "8", "9", "10", "11")


class FormGroupService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_group(self, name, year_group, form_tutor=None, room=None,
                     max_students=30, registration_time="08:40"):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO form_groups
                   (name, year_group, form_tutor, room, max_students, registration_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, year_group, form_tutor, room, max_students, registration_time))
            conn.commit()
            return dict(conn.execute("SELECT * FROM form_groups WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise FormGroupError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_groups(self, year_group=None, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM form_groups WHERE 1=1"
            params = []
            if year_group:
                sql += " AND year_group = ?"
                params.append(year_group)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY year_group, name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_group(self, group_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM form_group_students WHERE form_group_id = ?", (group_id,))
            conn.execute("DELETE FROM form_groups WHERE id = ?", (group_id,))
            conn.commit()
        finally:
            conn.close()

    def add_student(self, group_id, student_id):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO form_group_students (form_group_id, student_id) VALUES (?, ?)",
                (group_id, student_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise FormGroupError(f"Failed: {e}") from e
        finally:
            conn.close()

    def remove_student(self, form_group_student_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM form_group_students WHERE id = ?", (form_group_student_id,))
            conn.commit()
        finally:
            conn.close()

    def list_students(self, group_id):
        conn = self._conn()
        try:
            sql = """SELECT fgs.id as fgs_id, s.first_name, s.last_name, s.student_id as stu_code,
                            s.year_group
                     FROM form_group_students fgs
                     JOIN students s ON fgs.student_id = s.id
                     WHERE fgs.form_group_id = ? AND fgs.status = 'active'
                     ORDER BY s.last_name"""
            return [dict(r) for r in conn.execute(sql, (group_id,)).fetchall()]
        finally:
            conn.close()

    def student_count(self, group_id):
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM form_group_students WHERE form_group_id = ? AND status = 'active'",
                (group_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
