"""Grade management service with UCAS tariff point calculation."""

from datetime import datetime

from education_system.college_system.core.exceptions import GradeError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.database.constants import GRADE_SCALE
from education_system.college_system.infrastructure.validation.validators import validate_grade_score

import logging

logger = logging.getLogger(__name__)


class GradeService:
    """Service for managing grades, UCAS points, and transcripts."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    @staticmethod
    def score_to_letter(score: float) -> str:
        """Convert a numeric score (0-100) to a letter grade."""
        for letter, (low, high, _) in GRADE_SCALE.items():
            if low <= score <= high:
                return letter
        return "U"

    @staticmethod
    def letter_to_ucas_points(letter: str) -> int:
        """Convert a letter grade to UCAS tariff points."""
        for grade_letter, (_, _, points) in GRADE_SCALE.items():
            if grade_letter == letter:
                return points
        return 0

    def record_grade(self, student_pk: int, course_pk: int, score: float,
                     term: str | None = None, grade_type: str = "actual",
                     recorded_by: str | None = None) -> dict:
        """Record or update a grade for a student in a course."""
        score = validate_grade_score(score)
        letter = self.score_to_letter(score)

        conn = self._conn()
        try:
            # Verify enrollment exists
            enrollment = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ?",
                (student_pk, course_pk),
            ).fetchone()
            if not enrollment:
                raise GradeError("Student is not enrolled in this course.")

            # Check if grade already exists for this grade_type
            existing = conn.execute(
                "SELECT * FROM grades WHERE student_id = ? AND course_id = ? AND grade_type = ?",
                (student_pk, course_pk, grade_type),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE grades SET score = ?, letter_grade = ?, term = ?,
                       recorded_by = ?, updated_at = datetime('now')
                       WHERE student_id = ? AND course_id = ? AND grade_type = ?""",
                    (score, letter, term, recorded_by, student_pk, course_pk, grade_type),
                )
            else:
                conn.execute(
                    """INSERT INTO grades (student_id, course_id, score, letter_grade,
                       term, grade_type, recorded_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (student_pk, course_pk, score, letter, term, grade_type, recorded_by),
                )

            conn.commit()
            logger.info("Grade recorded: student=%d course=%d score=%.1f grade=%s", student_pk, course_pk, score, letter)

            # Notify student of grade
            try:
                student_row = conn.execute(
                    "SELECT user_id FROM students WHERE id = ?", (student_pk,)
                ).fetchone()
                course_row = conn.execute(
                    "SELECT course_code FROM courses WHERE id = ?", (course_pk,)
                ).fetchone()
                if student_row and student_row["user_id"] and course_row:
                    from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
                    nsvc = NotificationService(self._db_path)
                    nsvc.send(
                        student_row["user_id"],
                        f"Grade posted for {course_row['course_code']}",
                        f"Your grade for {course_row['course_code']} has been recorded: {letter} ({score}).",
                        type="info",
                    )
            except Exception:
                pass  # Don't break grade recording if notification fails

            return self.get_grade(student_pk, course_pk)
        except GradeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GradeError(f"Failed to record grade: {e}") from e
        finally:
            conn.close()

    def record_predicted_grade(self, student_pk: int, course_pk: int,
                               predicted_grade: str, term: str | None = None,
                               recorded_by: str | None = None) -> dict:
        """Record a predicted grade for a student in a course."""
        conn = self._conn()
        try:
            # Verify enrollment exists
            enrollment = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ?",
                (student_pk, course_pk),
            ).fetchone()
            if not enrollment:
                raise GradeError("Student is not enrolled in this course.")

            grade_type = "predicted"

            # Check if predicted grade already exists
            existing = conn.execute(
                "SELECT * FROM grades WHERE student_id = ? AND course_id = ? AND grade_type = ?",
                (student_pk, course_pk, grade_type),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE grades SET predicted_grade = ?, letter_grade = ?, term = ?,
                       recorded_by = ?, updated_at = datetime('now')
                       WHERE student_id = ? AND course_id = ? AND grade_type = ?""",
                    (predicted_grade, predicted_grade, term, recorded_by,
                     student_pk, course_pk, grade_type),
                )
            else:
                conn.execute(
                    """INSERT INTO grades (student_id, course_id, predicted_grade,
                       letter_grade, term, grade_type, recorded_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (student_pk, course_pk, predicted_grade, predicted_grade,
                     term, grade_type, recorded_by),
                )

            conn.commit()
            logger.info("Predicted grade recorded: student=%d course=%d grade=%s", student_pk, course_pk, predicted_grade)
            return {
                "student_id": student_pk,
                "course_id": course_pk,
                "predicted_grade": predicted_grade,
                "grade_type": grade_type,
                "term": term,
            }
        except GradeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GradeError(f"Failed to record predicted grade: {e}") from e
        finally:
            conn.close()

    def get_grade(self, student_pk: int, course_pk: int) -> dict | None:
        """Get a grade for a specific student and course."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT g.*, c.course_code, c.title, c.credits, c.qualification_type,
                          s.student_id as sid, s.first_name, s.last_name
                   FROM grades g
                   JOIN courses c ON g.course_id = c.id
                   JOIN students s ON g.student_id = s.id
                   WHERE g.student_id = ? AND g.course_id = ? AND g.grade_type = 'actual'""",
                (student_pk, course_pk),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_student_grades(self, student_pk: int) -> list[dict]:
        """Get all actual grades for a student."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT g.*, c.course_code, c.title, c.credits, c.qualification_type
                   FROM grades g JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ? AND g.grade_type = 'actual'
                   ORDER BY g.term, c.course_code""",
                (student_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_predicted_grades(self, student_pk: int) -> list[dict]:
        """Get all predicted grades for a student."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT g.*, c.course_code, c.title, c.qualification_type
                   FROM grades g JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ? AND g.grade_type = 'predicted'
                   ORDER BY c.course_code""",
                (student_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def calculate_ucas_points(self, student_pk: int) -> int:
        """Calculate total UCAS tariff points for a student."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT g.letter_grade
                   FROM grades g JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ? AND g.letter_grade IS NOT NULL
                   AND g.grade_type = 'actual'""",
                (student_pk,),
            ).fetchall()

            if not rows:
                return 0

            total_points = 0
            for row in rows:
                total_points += self.letter_to_ucas_points(row["letter_grade"])

            return total_points
        finally:
            conn.close()

    def get_transcript(self, student_pk: int) -> dict:
        """Get a full transcript for a student."""
        conn = self._conn()
        try:
            student = conn.execute(
                "SELECT * FROM students WHERE id = ?", (student_pk,)
            ).fetchone()
            if not student:
                raise GradeError("Student not found.")

            grades = self.get_student_grades(student_pk)
            ucas_points = self.calculate_ucas_points(student_pk)

            total_subjects = len([g for g in grades if g["letter_grade"] != "U"])

            return {
                "student": dict(student),
                "grades": grades,
                "ucas_points": ucas_points,
                "total_subjects": total_subjects,
                "total_courses": len(grades),
            }
        finally:
            conn.close()

    def get_course_grades(self, course_pk: int) -> list[dict]:
        """Get all grades for a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT g.*, s.student_id as sid, s.first_name, s.last_name
                   FROM grades g JOIN students s ON g.student_id = s.id
                   WHERE g.course_id = ? AND g.grade_type = 'actual'
                   ORDER BY s.last_name, s.first_name""",
                (course_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_class_statistics(self, course_pk: int) -> dict:
        """Get grade statistics for a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT score FROM grades WHERE course_id = ? AND score IS NOT NULL AND grade_type = 'actual'",
                (course_pk,),
            ).fetchall()

            if not rows:
                return {"count": 0, "average": 0, "min": 0, "max": 0, "median": 0}

            scores = sorted(r["score"] for r in rows)
            n = len(scores)
            median = scores[n // 2] if n % 2 == 1 else (scores[n // 2 - 1] + scores[n // 2]) / 2

            return {
                "count": n,
                "average": round(sum(scores) / n, 2),
                "min": scores[0],
                "max": scores[-1],
                "median": round(median, 2),
            }
        finally:
            conn.close()
