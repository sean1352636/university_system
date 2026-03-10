"""Assignment management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import AssignmentError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import (
    validate_non_empty, validate_date,
)

import logging

logger = logging.getLogger(__name__)


class AssignmentService:
    """Service for managing assignments and submissions."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_assignment(self, course_id: int, title: str, description: str | None = None,
                          due_date: str = "", max_score: float = 100,
                          allow_late: bool = False,
                          created_by: int | None = None) -> dict:
        """Create a new assignment for a course."""
        title = validate_non_empty(title, "Title")
        due_date = validate_date(due_date)

        conn = self._conn()
        try:
            course = conn.execute(
                "SELECT id FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            if not course:
                raise AssignmentError("Course not found.")

            conn.execute(
                """INSERT INTO assignments
                   (course_id, title, description, due_date, max_score, allow_late, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (course_id, title, description, due_date, max_score,
                 1 if allow_late else 0, created_by),
            )
            conn.commit()
            logger.info("Assignment created: course=%d title='%s'", course_id, title)

            row = conn.execute(
                "SELECT * FROM assignments WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except AssignmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AssignmentError(f"Failed to create assignment: {e}") from e
        finally:
            conn.close()

    def update_assignment(self, assignment_id: int, **updates) -> dict:
        """Update an assignment."""
        allowed = {"title", "description", "due_date", "max_score", "allow_late"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise AssignmentError("No valid fields to update.")

        if "title" in updates:
            updates["title"] = validate_non_empty(updates["title"], "Title")
        if "due_date" in updates:
            updates["due_date"] = validate_date(updates["due_date"])
        if "allow_late" in updates:
            updates["allow_late"] = 1 if updates["allow_late"] else 0

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not existing:
                raise AssignmentError("Assignment not found.")

            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE assignments SET {set_parts} WHERE id = ?",
                (*updates.values(), assignment_id),
            )
            conn.commit()

            row = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            return dict(row)
        except AssignmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AssignmentError(f"Failed to update assignment: {e}") from e
        finally:
            conn.close()

    def delete_assignment(self, assignment_id: int) -> bool:
        """Delete an assignment and its submissions."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not existing:
                raise AssignmentError("Assignment not found.")

            conn.execute("DELETE FROM submissions WHERE assignment_id = ?", (assignment_id,))
            conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
            conn.commit()
            logger.info("Assignment deleted: id=%d", assignment_id)
            return True
        except AssignmentError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_assignment(self, assignment_id: int) -> dict | None:
        """Get a single assignment by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT a.*, c.course_code, c.title as course_title
                   FROM assignments a
                   JOIN courses c ON a.course_id = c.id
                   WHERE a.id = ?""",
                (assignment_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_assignments(self, course_id: int | None = None) -> list[dict]:
        """List assignments, optionally filtered by course."""
        conn = self._conn()
        try:
            sql = """SELECT a.*, c.course_code, c.title as course_title
                     FROM assignments a
                     JOIN courses c ON a.course_id = c.id"""
            params: list = []
            if course_id is not None:
                sql += " WHERE a.course_id = ?"
                params.append(course_id)
            sql += " ORDER BY a.due_date DESC"

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def submit(self, assignment_id: int, student_pk: int,
               content: str | None = None) -> dict:
        """Submit an assignment. Validates enrollment and detects late submissions."""
        conn = self._conn()
        try:
            assignment = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not assignment:
                raise AssignmentError("Assignment not found.")

            # Verify student is enrolled in the course
            enrollment = conn.execute(
                """SELECT * FROM enrollments
                   WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
                (student_pk, assignment["course_id"]),
            ).fetchone()
            if not enrollment:
                raise AssignmentError("Student is not enrolled in this course.")

            # Detect late submission
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            due = assignment["due_date"]
            is_late = 1 if now[:10] > due[:10] else 0

            if is_late and not assignment["allow_late"]:
                raise AssignmentError("Late submissions are not allowed for this assignment.")

            conn.execute(
                """INSERT INTO submissions
                   (assignment_id, student_id, content, submitted_at, is_late)
                   VALUES (?, ?, ?, ?, ?)""",
                (assignment_id, student_pk, content, now, is_late),
            )
            conn.commit()
            logger.info("Submission received: assignment=%d student=%d late=%s", assignment_id, student_pk, bool(is_late))

            row = conn.execute(
                "SELECT * FROM submissions WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except AssignmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AssignmentError(f"Submission failed: {e}") from e
        finally:
            conn.close()

    def grade_submission(self, submission_id: int, score: float,
                         feedback: str | None = None,
                         graded_by: int | None = None) -> dict:
        """Grade a submission."""
        conn = self._conn()
        try:
            sub = conn.execute(
                "SELECT * FROM submissions WHERE id = ?", (submission_id,)
            ).fetchone()
            if not sub:
                raise AssignmentError("Submission not found.")

            assignment = conn.execute(
                "SELECT max_score FROM assignments WHERE id = ?",
                (sub["assignment_id"],),
            ).fetchone()
            if score < 0 or score > assignment["max_score"]:
                raise AssignmentError(
                    f"Score must be between 0 and {assignment['max_score']}."
                )

            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """UPDATE submissions
                   SET score = ?, feedback = ?, graded_by = ?, graded_at = ?
                   WHERE id = ?""",
                (score, feedback, graded_by, now, submission_id),
            )
            conn.commit()
            logger.info("Submission graded: id=%d score=%.1f", submission_id, score)

            row = conn.execute(
                "SELECT * FROM submissions WHERE id = ?", (submission_id,)
            ).fetchone()
            return dict(row)
        except AssignmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AssignmentError(f"Grading failed: {e}") from e
        finally:
            conn.close()

    def get_student_submissions(self, student_pk: int) -> list[dict]:
        """Get all submissions for a student."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.*, a.title as assignment_title, a.due_date,
                          a.max_score, c.course_code
                   FROM submissions s
                   JOIN assignments a ON s.assignment_id = a.id
                   JOIN courses c ON a.course_id = c.id
                   WHERE s.student_id = ?
                   ORDER BY s.submitted_at DESC""",
                (student_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_assignment_submissions(self, assignment_id: int) -> list[dict]:
        """Get all submissions for an assignment."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.*, st.student_id as sid, st.first_name, st.last_name
                   FROM submissions s
                   JOIN students st ON s.student_id = st.id
                   WHERE s.assignment_id = ?
                   ORDER BY s.submitted_at""",
                (assignment_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
