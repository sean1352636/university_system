"""Assignment management service."""

import logging
from education_system.primary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class AssignmentService:
    """Assignment management."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_assignment(self, title, description=None, subject_id=None, teacher_id=None,
                         class_name=None, year_group=None, due_date=None, max_marks=100):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO assignments (title, description, subject_id, teacher_id, class_name, year_group, due_date, max_marks)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description, subject_id, teacher_id, class_name, year_group, due_date, max_marks))
            conn.commit()
            row = conn.execute("SELECT * FROM assignments WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_assignments(self, subject_id=None, class_name=None, year_group=None, status=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM assignments WHERE 1=1"
            params = []
            if subject_id: sql += " AND subject_id = ?"; params.append(subject_id)
            if class_name: sql += " AND class_name = ?"; params.append(class_name)
            if year_group: sql += " AND year_group = ?"; params.append(year_group)
            if status: sql += " AND status = ?"; params.append(status)
            sql += " ORDER BY due_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_assignment(self, assignment_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_assignment(self, assignment_id, **kwargs):
        conn = self._conn()
        try:
            allowed = {"title", "description", "subject_id", "teacher_id", "class_name", "year_group", "due_date", "max_marks", "status"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates: return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE assignments SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                         list(updates.values()) + [assignment_id])
            conn.commit()
            return self.get_assignment(assignment_id)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_assignment(self, assignment_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def submit_assignment(self, assignment_id, pupil_id, marks=None, feedback=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO assignment_submissions (assignment_id, pupil_id, marks, feedback) VALUES (?, ?, ?, ?)",
                (assignment_id, pupil_id, marks, feedback))
            conn.commit()
            row = conn.execute("SELECT * FROM assignment_submissions WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_submissions(self, assignment_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM assignment_submissions WHERE assignment_id = ? ORDER BY submitted_at DESC",
                (assignment_id,)).fetchall()]
        finally:
            conn.close()

    def grade_submission(self, submission_id, marks, feedback=None):
        conn = self._conn()
        try:
            conn.execute("UPDATE assignment_submissions SET marks = ?, feedback = ?, status = 'graded' WHERE id = ?",
                         (marks, feedback, submission_id))
            conn.commit()
            row = conn.execute("SELECT * FROM assignment_submissions WHERE id = ?", (submission_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

