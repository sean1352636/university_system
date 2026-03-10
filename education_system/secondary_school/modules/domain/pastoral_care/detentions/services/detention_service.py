"""Detention management service."""

import logging
from education_system.secondary_school.core.exceptions import DetentionError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

DETENTION_TYPES = ("lunchtime", "after_school", "saturday", "internal_exclusion")


class DetentionService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_detention(self, student_id, reason, date, detention_type="lunchtime",
                         start_time=None, end_time=None, room=None, supervisor=None,
                         behaviour_record_id=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO detentions
                   (student_id, behaviour_record_id, detention_type, date, start_time,
                    end_time, room, supervisor, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, behaviour_record_id, detention_type, date, start_time,
                 end_time, room, supervisor, reason))
            conn.commit()
            return dict(conn.execute("SELECT * FROM detentions WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise DetentionError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_detentions(self, status=None, student_id=None):
        conn = self._conn()
        try:
            sql = """SELECT d.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM detentions d
                     JOIN students s ON d.student_id = s.id WHERE 1=1"""
            params = []
            if status:
                sql += " AND d.status = ?"
                params.append(status)
            if student_id:
                sql += " AND d.student_id = ?"
                params.append(student_id)
            sql += " ORDER BY d.date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def mark_attended(self, detention_id, attended=True):
        conn = self._conn()
        try:
            conn.execute("UPDATE detentions SET attended = ?, status = 'completed' WHERE id = ?",
                         (int(attended), detention_id))
            conn.commit()
        finally:
            conn.close()

    def mark_missed(self, detention_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE detentions SET attended = 0, status = 'missed' WHERE id = ?",
                         (detention_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_detention(self, detention_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM detentions WHERE id = ?", (detention_id,))
            conn.commit()
        finally:
            conn.close()
