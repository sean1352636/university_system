"""Student management service."""

from datetime import datetime
import logging

from education_system.secondary_school.core.exceptions import StudentError, ValidationError
from education_system.secondary_school.core.defaults import STUDENT_ID_PREFIX
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.infrastructure.validation.validators import (
    validate_email, validate_non_empty,
)

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

    def _key_stage_for_year(self, year_group: str) -> str:
        """Determine key stage from year group."""
        from education_system.secondary_school.infrastructure.database.constants import KS3_YEARS
        return "KS3" if year_group in KS3_YEARS else "KS4"

    def create_student(self, first_name: str, last_name: str,
                       email: str | None = None,
                       date_of_birth: str | None = None, address: str | None = None,
                       year_group: str | None = None, form_group: str | None = None,
                       form_tutor: str | None = None, sen_status: str | None = None,
                       pupil_premium: bool = False,
                       parent_name: str | None = None,
                       parent_email: str | None = None,
                       parent_phone: str | None = None,
                       emergency_contact_name: str | None = None,
                       emergency_contact_phone: str | None = None,
                       user_id: int | None = None) -> dict:
        """Create a new student record."""
        first_name = validate_non_empty(first_name, "First name")
        last_name = validate_non_empty(last_name, "Last name")
        if email:
            email = validate_email(email)
        if parent_email:
            parent_email = validate_email(parent_email)

        year_group = year_group or "7"
        key_stage = self._key_stage_for_year(year_group)
        student_id = self._generate_student_id()

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO students
                   (student_id, user_id, first_name, last_name, email,
                    date_of_birth, address, year_group, form_group, form_tutor,
                    key_stage, sen_status, pupil_premium,
                    parent_name, parent_email, parent_phone,
                    emergency_contact_name, emergency_contact_phone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, user_id, first_name, last_name, email,
                 date_of_birth, address, year_group, form_group, form_tutor,
                 key_stage, sen_status or "none", int(pupil_premium),
                 parent_name, parent_email, parent_phone,
                 emergency_contact_name, emergency_contact_phone),
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
        """Get a student by their student ID (e.g., SEC0001)."""
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
                      key_stage: str | None = None, search: str | None = None,
                      limit: int = 200, offset: int = 0) -> list[dict]:
        """List students with optional filters."""
        sql = "SELECT * FROM students WHERE 1=1"
        params: list = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if year_group:
            sql += " AND year_group = ?"
            params.append(year_group)
        if form_group:
            sql += " AND form_group = ?"
            params.append(form_group)
        if key_stage:
            sql += " AND key_stage = ?"
            params.append(key_stage)
        if search:
            sql += " AND (first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        sql += " ORDER BY year_group, form_group, last_name LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_student(self, student_pk: int, **kwargs) -> dict:
        """Update a student record."""
        allowed = {"first_name", "last_name", "email", "date_of_birth",
                    "address", "year_group", "form_group", "form_tutor", "status",
                    "key_stage", "sen_status", "pupil_premium",
                    "parent_name", "parent_email", "parent_phone",
                    "emergency_contact_name", "emergency_contact_phone", "user_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

        if not updates:
            raise ValidationError("No valid fields to update.")

        if "email" in updates:
            updates["email"] = validate_email(updates["email"])

        # Auto-set key stage if year group changes
        if "year_group" in updates:
            updates["key_stage"] = self._key_stage_for_year(updates["year_group"])

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [student_pk]

        conn = self._conn()
        try:
            conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", params)
            conn.commit()
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
            student = conn.execute(
                "SELECT id, user_id FROM students WHERE id = ?", (student_pk,)
            ).fetchone()
            if not student:
                raise StudentError("Student not found.")

            conn.execute("DELETE FROM behaviour_records WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM attendance_records WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM grades WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM enrollments WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM students WHERE id = ?", (student_pk,))

            user_id = student["user_id"]
            if user_id:
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            logger.info("Student deleted: pk=%d", student_pk)
            return True
        except StudentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentError(f"Failed to delete student: {e}") from e
        finally:
            conn.close()

    def count_students(self, status: str | None = None,
                       year_group: str | None = None) -> int:
        """Count students with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT COUNT(*) as cnt FROM students WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group = ?"
                params.append(year_group)
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
