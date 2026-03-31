"""Subject management service."""

from datetime import datetime
import logging
from education_system.secondary_school.core.sql_safety import validate_identifier, escape_like  # nosec B608

from education_system.secondary_school.core.exceptions import SubjectError, ValidationError
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.infrastructure.validation.validators import validate_non_empty

logger = logging.getLogger(__name__)


class SubjectService:
    """Service for managing subjects (courses)."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_subject(self, subject_code: str, title: str,
                       description: str | None = None, department: str | None = None,
                       key_stage: str = "KS3", is_core: bool = False,
                       capacity: int = 30, teacher: str | None = None,
                       room: str | None = None) -> dict:
        """Create a new subject."""
        subject_code = validate_non_empty(subject_code, "Subject code").upper()
        title = validate_non_empty(title, "Title")

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO subjects
                   (subject_code, title, description, department, key_stage,
                    is_core, capacity, teacher, room)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (subject_code, title, description, department, key_stage,
                 int(is_core), capacity, teacher, room),
            )
            conn.commit()
            logger.info("Subject created: %s - %s", subject_code, title)
            return self.get_subject_by_code(subject_code)
        except Exception as e:
            conn.rollback()
            raise SubjectError(f"Failed to create subject: {e}") from e
        finally:
            conn.close()

    def get_subject(self, subject_pk: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_subject_by_code(self, subject_code: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM subjects WHERE subject_code = ?", (subject_code,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_subjects(self, status: str | None = None, key_stage: str | None = None,
                      department: str | None = None, search: str | None = None,
                      limit: int = 100, offset: int = 0) -> list[dict]:
        sql = "SELECT * FROM subjects WHERE 1=1"
        params: list = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if key_stage:
            sql += " AND key_stage = ?"
            params.append(key_stage)
        if department:
            sql += " AND department = ?"
            params.append(department)
        if search:
            sql += " AND (subject_code LIKE ? OR title LIKE ?)"
            escaped = escape_like(search)
            term = f"%{escaped}%"
            params.extend([term, term])

        sql += " ORDER BY department, subject_code LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_subject(self, subject_pk: int, **kwargs) -> dict:
        allowed = {"subject_code", "title", "description", "department", "key_stage",
                    "is_core", "capacity", "teacher", "room", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")

        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [subject_pk]

        conn = self._conn()
        try:
            conn.execute(f"UPDATE subjects SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            result = self.get_subject(subject_pk)
            if not result:
                raise SubjectError("Subject not found.")
            return result
        finally:
            conn.close()

    def delete_subject(self, subject_pk: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM enrollments WHERE subject_id = ?", (subject_pk,))
            conn.execute("DELETE FROM grades WHERE subject_id = ?", (subject_pk,))
            conn.execute("DELETE FROM attendance_records WHERE subject_id = ?", (subject_pk,))
            conn.execute("DELETE FROM timetable_slots WHERE subject_id = ?", (subject_pk,))
            conn.execute("DELETE FROM subjects WHERE id = ?", (subject_pk,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise SubjectError(f"Failed to delete subject: {e}") from e
        finally:
            conn.close()
