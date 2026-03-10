"""Exam management service."""

import logging
from education_system.secondary_school.core.exceptions import ExamError
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.modules.domain.academics.exams.services.exam_notifications import (
    send_exam_notification,
)

logger = logging.getLogger(__name__)

EXAM_TYPES = ("end_of_term", "mock", "gcse", "class_test", "practical", "oral", "coursework")
EXAM_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")


class ExamService:
    """Manage exams and results."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Exam CRUD ──

    def _get_exam_with_subject(self, conn, exam_id: int) -> dict:
        """Fetch exam joined with subject title for notifications."""
        row = conn.execute(
            """SELECT e.*, s.subject_code, s.title as subject_title
               FROM exams e JOIN subjects s ON e.subject_id = s.id
               WHERE e.id = ?""",
            (exam_id,),
        ).fetchone()
        return dict(row) if row else {}

    def create_exam(self, subject_id: int, title: str, exam_type: str = "end_of_term",
                    year_group: str | None = None, date: str | None = None,
                    start_time: str | None = None, duration_minutes: int = 60,
                    room: str | None = None, invigilator: str | None = None,
                    total_marks: int = 100, notes: str | None = None) -> dict:
        if exam_type not in EXAM_TYPES:
            raise ExamError(f"Invalid exam type: {exam_type}")
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO exams (subject_id, title, exam_type, year_group, date,
                   start_time, duration_minutes, room, invigilator, total_marks, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (subject_id, title, exam_type, year_group, date,
                 start_time, duration_minutes, room, invigilator, total_marks, notes),
            )
            conn.commit()
            exam = self._get_exam_with_subject(conn, cursor.lastrowid)
            # Notify enrolled students
            send_exam_notification(self._db_path, exam, "scheduled")
            return exam
        except ExamError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ExamError(f"Failed to create exam: {e}") from e
        finally:
            conn.close()

    def update_exam(self, exam_id: int, **kwargs) -> dict:
        """Update exam details and notify enrolled students."""
        allowed = {
            "title", "exam_type", "year_group", "date", "start_time",
            "duration_minutes", "room", "invigilator", "total_marks", "notes",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            raise ExamError("No valid fields to update.")
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE exams SET {set_clause} WHERE id = ?",
                (*updates.values(), exam_id),
            )
            conn.commit()
            exam = self._get_exam_with_subject(conn, exam_id)
            send_exam_notification(self._db_path, exam, "updated")
            return exam
        except ExamError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ExamError(f"Failed to update exam: {e}") from e
        finally:
            conn.close()

    def list_exams(self, year_group: str | None = None,
                   status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT e.*, s.subject_code, s.title as subject_title
                     FROM exams e JOIN subjects s ON e.subject_id = s.id
                     WHERE 1=1"""
            params: list = []
            if year_group:
                sql += " AND e.year_group = ?"
                params.append(year_group)
            if status:
                sql += " AND e.status = ?"
                params.append(status)
            sql += " ORDER BY e.date DESC, e.start_time"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_exam_status(self, exam_id: int, status: str):
        if status not in EXAM_STATUSES:
            raise ExamError(f"Invalid status: {status}")
        conn = self._conn()
        try:
            conn.execute("UPDATE exams SET status = ? WHERE id = ?", (status, exam_id))
            conn.commit()
            exam = self._get_exam_with_subject(conn, exam_id)
            if status == "cancelled":
                send_exam_notification(self._db_path, exam, "cancelled")
            else:
                send_exam_notification(self._db_path, exam, "updated")
        finally:
            conn.close()

    def delete_exam(self, exam_id: int):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM exam_results WHERE exam_id = ?", (exam_id,))
            conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
            conn.commit()
        finally:
            conn.close()

    # ── Results ──

    def record_result(self, exam_id: int, student_id: int,
                      marks_obtained: float | None = None,
                      grade: str | None = None, absent: bool = False,
                      special_consideration: str | None = None,
                      comment: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM exam_results WHERE exam_id = ? AND student_id = ?",
                (exam_id, student_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE exam_results SET marks_obtained = ?, grade = ?,
                       absent = ?, special_consideration = ?, comment = ?
                       WHERE id = ?""",
                    (marks_obtained, grade, int(absent),
                     special_consideration, comment, existing["id"]),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM exam_results WHERE id = ?",
                                   (existing["id"],)).fetchone()
            else:
                cursor = conn.execute(
                    """INSERT INTO exam_results
                       (exam_id, student_id, marks_obtained, grade, absent,
                        special_consideration, comment)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (exam_id, student_id, marks_obtained, grade, int(absent),
                     special_consideration, comment),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM exam_results WHERE id = ?",
                                   (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ExamError(f"Failed to record result: {e}") from e
        finally:
            conn.close()

    def get_exam_results(self, exam_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT er.*, s.student_id as sid, s.first_name, s.last_name
                   FROM exam_results er
                   JOIN students s ON er.student_id = s.id
                   WHERE er.exam_id = ?
                   ORDER BY s.last_name""",
                (exam_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_exam_results(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT er.*, e.title as exam_title, e.exam_type, e.date,
                          e.total_marks, s.subject_code, s.title as subject_title
                   FROM exam_results er
                   JOIN exams e ON er.exam_id = e.id
                   JOIN subjects s ON e.subject_id = s.id
                   WHERE er.student_id = ?
                   ORDER BY e.date DESC""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
