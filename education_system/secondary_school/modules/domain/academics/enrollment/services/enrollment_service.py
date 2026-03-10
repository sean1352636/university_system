"""Enrollment management service."""

from datetime import datetime
import logging

from education_system.secondary_school.core.exceptions import EnrollmentError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class EnrollmentService:
    """Service for managing student-subject enrollments."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def enroll_student(self, student_id: int, subject_id: int) -> dict:
        """Enroll a student in a subject."""
        conn = self._conn()
        try:
            # Check for existing enrollment
            existing = conn.execute(
                "SELECT id, status FROM enrollments WHERE student_id = ? AND subject_id = ?",
                (student_id, subject_id),
            ).fetchone()
            if existing and existing["status"] == "enrolled":
                raise EnrollmentError("Student is already enrolled in this subject.")

            # Check capacity
            subject = conn.execute(
                "SELECT capacity FROM subjects WHERE id = ?", (subject_id,)
            ).fetchone()
            if not subject:
                raise EnrollmentError("Subject not found.")

            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM enrollments WHERE subject_id = ? AND status = 'enrolled'",
                (subject_id,),
            ).fetchone()["cnt"]

            if count >= subject["capacity"]:
                raise EnrollmentError("Subject is at full capacity.")

            if existing:
                conn.execute(
                    "UPDATE enrollments SET status = 'enrolled', enrolled_at = datetime('now'), dropped_at = NULL WHERE id = ?",
                    (existing["id"],),
                )
            else:
                conn.execute(
                    "INSERT INTO enrollments (student_id, subject_id) VALUES (?, ?)",
                    (student_id, subject_id),
                )
            conn.commit()

            row = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND subject_id = ?",
                (student_id, subject_id),
            ).fetchone()
            return dict(row)
        except EnrollmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EnrollmentError(f"Enrollment failed: {e}") from e
        finally:
            conn.close()

    def drop_enrollment(self, student_id: int, subject_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE enrollments SET status = 'dropped', dropped_at = datetime('now')
                   WHERE student_id = ? AND subject_id = ? AND status = 'enrolled'""",
                (student_id, subject_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_student_enrollments(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT e.*, s.subject_code, s.title, s.teacher, s.room
                   FROM enrollments e JOIN subjects s ON e.subject_id = s.id
                   WHERE e.student_id = ? AND e.status = 'enrolled'""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_subject_students(self, subject_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT e.*, st.student_id as sid, st.first_name, st.last_name,
                          st.year_group, st.form_group
                   FROM enrollments e JOIN students st ON e.student_id = st.id
                   WHERE e.subject_id = ? AND e.status = 'enrolled'
                   ORDER BY st.last_name""",
                (subject_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
