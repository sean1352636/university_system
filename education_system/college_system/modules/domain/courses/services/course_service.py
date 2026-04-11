"""Course management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import CourseError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import (
    validate_course_code, validate_non_empty, validate_positive_int,
)

from education_system.college_system.core.sql_safety import validate_identifier, escape_like  # nosec B608
import logging

logger = logging.getLogger(__name__)


class CourseService:
    """Service for managing courses and prerequisites."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_course(self, course_code: str, title: str,
                      guided_learning_hours: int = 3,
                      capacity: int = 30, description: str | None = None,
                      subject_area: str | None = None, teacher: str | None = None,
                      term: str | None = None, schedule: str | None = None,
                      qualification_type: str | None = None) -> dict:
        """Create a new course."""
        course_code = validate_course_code(course_code)
        title = validate_non_empty(title, "Title")
        guided_learning_hours = validate_positive_int(guided_learning_hours, "Guided Learning Hours")
        capacity = validate_positive_int(capacity, "Capacity")

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO courses
                   (course_code, title, description, credits, capacity, department,
                    instructor, semester, schedule, qualification_type, subject_area,
                    teacher, term)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (course_code, title, description, guided_learning_hours, capacity,
                 subject_area, teacher, term, schedule,
                 qualification_type or "A-Level", subject_area, teacher, term),
            )
            conn.commit()
            logger.info("Course created: %s (%s)", course_code, title)
            return self.get_course_by_code(course_code)
        except Exception as e:
            conn.rollback()
            if "UNIQUE" in str(e):
                raise CourseError(f"Course code '{course_code}' already exists.") from e
            raise CourseError(f"Failed to create course: {e}") from e
        finally:
            conn.close()

    def get_course(self, course_pk: int) -> dict | None:
        """Get a course by primary key."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_course_by_code(self, course_code: str) -> dict | None:
        """Get a course by its course code."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM courses WHERE course_code = ?", (course_code.upper(),)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_courses(self, subject_area: str | None = None, term: str | None = None,
                     qualification_type: str | None = None,
                     status: str | None = None, search: str | None = None,
                     limit: int = 100, offset: int = 0) -> list[dict]:
        """List courses with optional filters."""
        sql = "SELECT * FROM courses WHERE 1=1"
        params = []

        if subject_area:
            sql += " AND subject_area = ?"
            params.append(subject_area)
        if term:
            sql += " AND term = ?"
            params.append(term)
        if qualification_type:
            sql += " AND qualification_type = ?"
            params.append(qualification_type)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if search:
            sql += " AND (course_code LIKE ? OR title LIKE ?)"
            escaped = escape_like(search)
            term = f"%{escaped}%"
            params.extend([term, term])

        sql += " ORDER BY course_code LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_course(self, course_pk: int, **kwargs) -> dict:
        """Update a course record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("title", "description", "credits", "capacity", "subject_area",
                    "teacher", "term", "schedule", "status", "qualification_type"):
            val = kwargs.get(col)
            if val is not None:
                set_parts.append(f"{validate_identifier(col)} = ?")
                params.append(val)

        if not set_parts:
            raise ValidationError("No valid fields to update.")

        set_parts.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(course_pk)
        set_clause = ", ".join(set_parts)

        conn = self._conn()
        try:
            conn.execute(f"UPDATE courses SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Course updated: pk=%d", course_pk)
            result = self.get_course(course_pk)
            if not result:
                raise CourseError("Course not found.")
            return result
        finally:
            conn.close()

    def delete_course(self, course_pk: int) -> bool:
        """Permanently delete a course and all related data."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM courses WHERE id = ?", (course_pk,)
            ).fetchone()
            if not existing:
                raise CourseError("Course not found.")

            # Delete related records
            # Submissions for assignments belonging to this course
            conn.execute(
                "DELETE FROM submissions WHERE assignment_id IN "
                "(SELECT id FROM assignments WHERE course_id = ?)",
                (course_pk,),
            )
            conn.execute("DELETE FROM assignments WHERE course_id = ?", (course_pk,))
            conn.execute("DELETE FROM attendance_records WHERE session_id IN "
                         "(SELECT id FROM attendance_sessions WHERE course_id = ?)",
                         (course_pk,))
            conn.execute("DELETE FROM attendance_sessions WHERE course_id = ?", (course_pk,))
            conn.execute("DELETE FROM timetable_slots WHERE course_id = ?", (course_pk,))
            conn.execute("DELETE FROM grades WHERE course_id = ?", (course_pk,))
            conn.execute("DELETE FROM waitlist WHERE course_id = ?", (course_pk,))
            conn.execute("DELETE FROM enrollments WHERE course_id = ?", (course_pk,))
            conn.execute("DELETE FROM prerequisites WHERE course_id = ? OR prerequisite_id = ?",
                         (course_pk, course_pk))

            # Delete the course
            conn.execute("DELETE FROM courses WHERE id = ?", (course_pk,))
            conn.commit()
            logger.info("Course deleted: pk=%d (cascaded related records)", course_pk)
            return True
        except CourseError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise CourseError(f"Failed to delete course: {e}") from e
        finally:
            conn.close()

    def get_enrollment_count(self, course_pk: int) -> int:
        """Get the number of currently enrolled students."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM enrollments WHERE course_id = ? AND status = 'enrolled'",
                (course_pk,),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def get_roster(self, course_pk: int) -> list[dict]:
        """Get the list of students enrolled in a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.*, e.enrolled_at
                   FROM students s JOIN enrollments e ON s.id = e.student_id
                   WHERE e.course_id = ? AND e.status = 'enrolled'
                   ORDER BY s.last_name, s.first_name""",
                (course_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- Prerequisites ---

    def add_prerequisite(self, course_pk: int, prerequisite_pk: int):
        """Add a prerequisite to a course (with circular dependency check)."""
        if course_pk == prerequisite_pk:
            raise CourseError("A course cannot be its own prerequisite.")

        if self._has_circular_dependency(prerequisite_pk, course_pk):
            raise CourseError("Circular prerequisite dependency detected.")

        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO prerequisites (course_id, prerequisite_id) VALUES (?, ?)",
                (course_pk, prerequisite_pk),
            )
            conn.commit()
            logger.info("Prerequisite added: course=%d requires=%d", course_pk, prerequisite_pk)
        finally:
            conn.close()

    def remove_prerequisite(self, course_pk: int, prerequisite_pk: int):
        """Remove a prerequisite from a course."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM prerequisites WHERE course_id = ? AND prerequisite_id = ?",
                (course_pk, prerequisite_pk),
            )
            conn.commit()
        finally:
            conn.close()

    def get_prerequisites(self, course_pk: int) -> list[dict]:
        """Get all prerequisites for a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT c.* FROM courses c
                   JOIN prerequisites p ON c.id = p.prerequisite_id
                   WHERE p.course_id = ?""",
                (course_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _has_circular_dependency(self, course_pk: int, target_pk: int,
                                 visited: set | None = None) -> bool:
        """Check if adding target_pk as a prerequisite would create a cycle."""
        if visited is None:
            visited = set()

        if course_pk in visited:
            return False
        visited.add(course_pk)

        conn = self._conn()
        try:
            prereqs = conn.execute(
                "SELECT prerequisite_id FROM prerequisites WHERE course_id = ?",
                (course_pk,),
            ).fetchall()

            for row in prereqs:
                if row["prerequisite_id"] == target_pk:
                    return True
                if self._has_circular_dependency(row["prerequisite_id"], target_pk, visited):
                    return True
            return False
        finally:
            conn.close()

    def count_courses(self, status: str | None = None) -> int:
        """Count total courses, optionally filtered by status."""
        conn = self._conn()
        try:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM courses WHERE status = ?", (status,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()
            return row["cnt"]
        finally:
            conn.close()
