"""Grade management service."""

from datetime import datetime
import logging
from education_system.secondary_school.core.sql_safety import validate_identifier  # nosec B608

from education_system.secondary_school.core.exceptions import GradeError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

ASSESSMENT_TYPES = ("classwork", "homework", "test", "mock_exam", "coursework", "end_of_term")


class GradeService:
    """Service for managing student grades."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_grade(self, student_id: int, subject_id: int,
                  assessment_type: str = "classwork", assessment_name: str | None = None,
                  score: float | None = None, grade: str | None = None,
                  term: str | None = None, academic_year: str | None = None,
                  teacher_comment: str | None = None) -> dict:
        """Record a grade for a student."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO grades
                   (student_id, subject_id, assessment_type, assessment_name,
                    score, grade, term, academic_year, teacher_comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, subject_id, assessment_type, assessment_name,
                 score, grade, term, academic_year, teacher_comment),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM grades WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise GradeError(f"Failed to add grade: {e}") from e
        finally:
            conn.close()

    def get_student_grades(self, student_id: int, subject_id: int | None = None,
                           term: str | None = None) -> list[dict]:
        sql = """SELECT g.*, s.subject_code, s.title
                 FROM grades g JOIN subjects s ON g.subject_id = s.id
                 WHERE g.student_id = ?"""
        params: list = [student_id]

        if subject_id:
            sql += " AND g.subject_id = ?"
            params.append(subject_id)
        if term:
            sql += " AND g.term = ?"
            params.append(term)

        sql += " ORDER BY g.graded_at DESC"

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_subject_grades(self, subject_id: int, assessment_name: str | None = None) -> list[dict]:
        sql = """SELECT g.*, st.student_id as sid, st.first_name, st.last_name
                 FROM grades g JOIN students st ON g.student_id = st.id
                 WHERE g.subject_id = ?"""
        params: list = [subject_id]
        if assessment_name:
            sql += " AND g.assessment_name = ?"
            params.append(assessment_name)
        sql += " ORDER BY st.last_name"

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_grade(self, grade_id: int, **kwargs) -> dict:
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("score", "grade", "assessment_type", "assessment_name",
                    "term", "academic_year", "teacher_comment"):
            val = kwargs.get(col)
            if val is not None:
                set_parts.append(f"{validate_identifier(col)} = ?")
                params.append(val)
        if not set_parts:
            raise GradeError("No valid fields to update.")
        params.append(grade_id)
        set_clause = ", ".join(set_parts)

        conn = self._conn()
        try:
            conn.execute(f"UPDATE grades SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            row = conn.execute("SELECT * FROM grades WHERE id = ?", (grade_id,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_grade(self, grade_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_student_average(self, student_id: int, subject_id: int | None = None) -> float | None:
        """Calculate average score for a student, optionally per subject."""
        sql = "SELECT AVG(score) as avg_score FROM grades WHERE student_id = ? AND score IS NOT NULL"
        params: list = [student_id]
        if subject_id:
            sql += " AND subject_id = ?"
            params.append(subject_id)

        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["avg_score"] if row and row["avg_score"] is not None else None
        finally:
            conn.close()
