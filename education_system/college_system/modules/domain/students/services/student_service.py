"""Student management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import StudentError, ValidationError
from education_system.college_system.core.defaults import STUDENT_ID_PREFIX
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import (
    validate_email, validate_non_empty, validate_student_id,
)

import logging

logger = logging.getLogger(__name__)


class StudentService:
    """Service for managing student records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _generate_student_id(self) -> str:
        """Generate the next sequential student ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT student_id FROM students ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                num = int(row["student_id"].replace(STUDENT_ID_PREFIX, "")) + 1
            else:
                num = 1
            return f"{STUDENT_ID_PREFIX}{num:04d}"
        finally:
            conn.close()

    def create_student(self, first_name: str, last_name: str,
                       email: str | None = None, phone: str | None = None,
                       date_of_birth: str | None = None, address: str | None = None,
                       year_group: str | None = None, form_group: str | None = None,
                       form_tutor: str | None = None, user_id: int | None = None) -> dict:
        """Create a new student record."""
        first_name = validate_non_empty(first_name, "First name")
        last_name = validate_non_empty(last_name, "Last name")
        if email:
            email = validate_email(email)

        student_id = self._generate_student_id()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO students
                   (student_id, user_id, first_name, last_name, email, phone,
                    date_of_birth, address, year_group, form_group, form_tutor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, user_id, first_name, last_name, email, phone,
                 date_of_birth, address, year_group or "12", form_group, form_tutor),
            )
            conn.commit()
            logger.info("Student created: %s (%s %s)", student_id, first_name, last_name)
            return self.get_student_by_student_id(student_id)
        except Exception as e:
            conn.rollback()
            raise StudentError(f"Failed to create student: {e}") from e
        finally:
            conn.close()

    def get_student(self, student_pk: int) -> dict | None:
        """Get a student by primary key."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM students WHERE id = ?", (student_pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_student_by_student_id(self, student_id: str) -> dict | None:
        """Get a student by their student ID (e.g., STU0001)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_students(self, status: str | None = None,
                      year_group: str | None = None, form_group: str | None = None,
                      search: str | None = None, limit: int = 100,
                      offset: int = 0) -> list[dict]:
        """List students with optional filters."""
        sql = "SELECT * FROM students WHERE 1=1"
        params = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if year_group:
            sql += " AND year_group = ?"
            params.append(year_group)
        if form_group:
            sql += " AND form_group = ?"
            params.append(form_group)
        if search:
            sql += " AND (first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        sql += " ORDER BY student_id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_student(self, student_pk: int, **kwargs) -> dict:
        """Update a student record."""
        allowed = {"first_name", "last_name", "email", "phone", "date_of_birth",
                    "address", "year_group", "form_group", "form_tutor", "status",
                    "user_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

        if not updates:
            raise ValidationError("No valid fields to update.")

        if "email" in updates:
            updates["email"] = validate_email(updates["email"])

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [student_pk]

        conn = self._conn()
        try:
            conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Student updated: pk=%d", student_pk)
            result = self.get_student(student_pk)
            if not result:
                raise StudentError("Student not found.")
            return result
        finally:
            conn.close()

    def delete_student(self, student_pk: int) -> bool:
        """Permanently delete a student and all related data."""
        conn = self._conn()
        try:
            # Check student exists and get user_id for cleanup
            student = conn.execute(
                "SELECT id, user_id FROM students WHERE id = ?", (student_pk,)
            ).fetchone()
            if not student:
                raise StudentError("Student not found.")

            # Delete related records
            conn.execute("DELETE FROM submissions WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM attendance_records WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM grades WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM waitlist WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM enrollments WHERE student_id = ?", (student_pk,))

            # Delete the student record
            conn.execute("DELETE FROM students WHERE id = ?", (student_pk,))

            # Delete linked user account and its data
            user_id = student["user_id"]
            if user_id:
                conn.execute("UPDATE messages SET sender_deleted = 1 WHERE sender_id = ?", (user_id,))
                conn.execute("UPDATE messages SET recipient_deleted = 1 WHERE recipient_id = ?", (user_id,))
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            logger.info("Student deleted: pk=%d (user_id=%s)", student_pk, student["user_id"])
            return True
        except StudentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            logger.error("Student deletion failed: pk=%d: %s", student_pk, e)
            raise StudentError(f"Failed to delete student: {e}") from e
        finally:
            conn.close()

    def get_student_profile(self, student_pk: int) -> dict | None:
        """Get a comprehensive student profile with enrollment info."""
        student = self.get_student(student_pk)
        if not student:
            return None

        conn = self._conn()
        try:
            enrollments = conn.execute(
                """SELECT e.*, c.course_code, c.title
                   FROM enrollments e JOIN courses c ON e.course_id = c.id
                   WHERE e.student_id = ? AND e.status = 'enrolled'""",
                (student_pk,),
            ).fetchall()

            grades = conn.execute(
                """SELECT g.*, c.course_code, c.title, c.credits
                   FROM grades g JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ?""",
                (student_pk,),
            ).fetchall()

            student["enrollments"] = [dict(e) for e in enrollments]
            student["grades"] = [dict(g) for g in grades]
            return student
        finally:
            conn.close()

    def count_students(self, status: str | None = None) -> int:
        """Count total students, optionally filtered by status."""
        conn = self._conn()
        try:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM students WHERE status = ?", (status,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()
            return row["cnt"]
        finally:
            conn.close()
