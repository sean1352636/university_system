"""Cover management service."""

import logging
from education_system.secondary_school.core.exceptions import CoverError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

COVER_STATUSES = ("pending", "assigned", "completed", "cancelled")


class CoverService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_cover(self, absent_teacher, date, period, cover_teacher=None,
                     subject_id=None, year_group=None, room=None, work_set=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO cover_lessons (absent_teacher, cover_teacher, subject_id,
                   year_group, date, period, room, work_set, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (absent_teacher, cover_teacher, subject_id, year_group, date, period,
                 room, work_set, notes))
            conn.commit()
            status = "assigned" if cover_teacher else "pending"
            conn.execute("UPDATE cover_lessons SET status = ? WHERE id = ?", (status, cursor.lastrowid))
            conn.commit()
            row = conn.execute("SELECT * FROM cover_lessons WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise CoverError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_covers(self, date=None, status=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM cover_lessons WHERE 1=1"
            params = []
            if date:
                sql += " AND date = ?"
                params.append(date)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY date DESC, period"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def assign_cover(self, cover_id, cover_teacher):
        conn = self._conn()
        try:
            conn.execute("UPDATE cover_lessons SET cover_teacher = ?, status = 'assigned' WHERE id = ?",
                         (cover_teacher, cover_id))
            conn.commit()
        finally:
            conn.close()

    def complete_cover(self, cover_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE cover_lessons SET status = 'completed' WHERE id = ?", (cover_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_cover(self, cover_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM cover_lessons WHERE id = ?", (cover_id,))
            conn.commit()
        finally:
            conn.close()
