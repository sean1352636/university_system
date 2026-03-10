"""Pastoral care service."""

import logging
from education_system.secondary_school.core.exceptions import PastoralError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

NOTE_TYPES = ("general", "welfare", "academic", "behaviour", "attendance", "family", "medical")


class PastoralService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Pastoral Notes ---

    def add_note(self, student_id, content, note_type="general",
                 recorded_by=None, is_confidential=False, follow_up_date=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO pastoral_notes
                   (student_id, note_type, content, recorded_by, is_confidential, follow_up_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, note_type, content, recorded_by,
                 int(is_confidential), follow_up_date))
            conn.commit()
            row = conn.execute("SELECT * FROM pastoral_notes WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise PastoralError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_notes(self, student_id=None, note_type=None):
        conn = self._conn()
        try:
            sql = """SELECT pn.*, s.first_name, s.last_name, s.year_group, s.form_group
                     FROM pastoral_notes pn
                     JOIN students s ON pn.student_id = s.id
                     WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND pn.student_id = ?"
                params.append(student_id)
            if note_type:
                sql += " AND pn.note_type = ?"
                params.append(note_type)
            sql += " ORDER BY pn.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def mark_follow_up_done(self, note_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE pastoral_notes SET follow_up_done = 1 WHERE id = ?", (note_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_note(self, note_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM pastoral_notes WHERE id = ?", (note_id,))
            conn.commit()
        finally:
            conn.close()

    # --- House Points ---

    def award_house_points(self, student_id, house, points=1, reason=None, awarded_by=None):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO house_points (student_id, house, points, reason, awarded_by) VALUES (?, ?, ?, ?, ?)",
                (student_id, house, points, reason, awarded_by))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise PastoralError(f"Failed: {e}") from e
        finally:
            conn.close()

    def house_points_summary(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT house, SUM(points) as total FROM house_points GROUP BY house ORDER BY total DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def student_house_points(self, student_id):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT hp.*, s.first_name, s.last_name
                   FROM house_points hp JOIN students s ON hp.student_id = s.id
                   WHERE hp.student_id = ? ORDER BY hp.created_at DESC""",
                (student_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
