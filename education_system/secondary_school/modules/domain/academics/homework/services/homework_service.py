"""Homework service."""

import logging
from education_system.secondary_school.core.exceptions import HomeworkError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

SUBMISSION_STATUSES = ("pending", "submitted", "late", "marked", "missing")


class HomeworkService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_homework(self, subject_id, title, due_date, year_group=None,
                        description=None, set_by=None, max_marks=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO homework (subject_id, year_group, title, description, set_by, due_date, max_marks)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (subject_id, year_group, title, description, set_by, due_date, max_marks))
            conn.commit()
            row = conn.execute("SELECT * FROM homework WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_homework(self, subject_id=None, year_group=None, status=None):
        conn = self._conn()
        try:
            sql = """SELECT h.*, s.subject_code, s.title as subject_title
                     FROM homework h JOIN subjects s ON h.subject_id = s.id WHERE 1=1"""
            params = []
            if subject_id:
                sql += " AND h.subject_id = ?"
                params.append(subject_id)
            if year_group:
                sql += " AND h.year_group = ?"
                params.append(year_group)
            if status:
                sql += " AND h.status = ?"
                params.append(status)
            sql += " ORDER BY h.due_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_homework(self, hw_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM homework_submissions WHERE homework_id = ?", (hw_id,))
            conn.execute("DELETE FROM homework WHERE id = ?", (hw_id,))
            conn.commit()
        finally:
            conn.close()

    def submit(self, homework_id, student_id):
        conn = self._conn()
        try:
            from datetime import datetime
            existing = conn.execute("SELECT id FROM homework_submissions WHERE homework_id = ? AND student_id = ?",
                                    (homework_id, student_id)).fetchone()
            if existing:
                conn.execute("UPDATE homework_submissions SET status = 'submitted', submitted_at = datetime('now') WHERE id = ?",
                             (existing["id"],))
            else:
                conn.execute("INSERT INTO homework_submissions (homework_id, student_id, submitted_at, status) VALUES (?, ?, datetime('now'), 'submitted')",
                             (homework_id, student_id))
            conn.commit()
        finally:
            conn.close()

    def mark_submission(self, homework_id, student_id, marks=None, feedback=None):
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM homework_submissions WHERE homework_id = ? AND student_id = ?",
                                    (homework_id, student_id)).fetchone()
            if existing:
                conn.execute("UPDATE homework_submissions SET marks = ?, feedback = ?, status = 'marked' WHERE id = ?",
                             (marks, feedback, existing["id"]))
            else:
                conn.execute("INSERT INTO homework_submissions (homework_id, student_id, marks, feedback, status) VALUES (?, ?, ?, ?, 'marked')",
                             (homework_id, student_id, marks, feedback))
            conn.commit()
        finally:
            conn.close()

    def get_submissions(self, homework_id):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT hs.*, s.student_id as sid, s.first_name, s.last_name
                   FROM homework_submissions hs JOIN students s ON hs.student_id = s.id
                   WHERE hs.homework_id = ? ORDER BY s.last_name""",
                (homework_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
