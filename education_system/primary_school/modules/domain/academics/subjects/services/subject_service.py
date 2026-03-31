"""Subject management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import SubjectError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class SubjectService:
    """CRUD operations for subjects."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_subject(self, subject_code, title, description=None, is_core=1,
                       key_stage=None, coordinator_staff_id=None):
        if not subject_code or not subject_code.strip():
            raise SubjectError("Subject code is required")
        if not title or not title.strip():
            raise SubjectError("Title is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO subjects (
                    subject_code, title, description, is_core, key_stage,
                    coordinator_staff_id
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (subject_code.strip(), title.strip(), description, is_core,
                 key_stage, coordinator_staff_id),
            )
            conn.commit()
            logger.info("Created subject: %s (%s)", title, subject_code)
            return {"subject_code": subject_code, "title": title}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SubjectError(f"Failed to create subject: {e}") from e
        finally:
            conn.close()

    def get_subject(self, subject_code):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM subjects WHERE subject_code = ?", (subject_code,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_subjects(self, key_stage=None, is_core=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM subjects WHERE 1=1"
            params = []
            if key_stage is not None:
                sql += " AND key_stage = ?"
                params.append(key_stage)
            if is_core is not None:
                sql += " AND is_core = ?"
                params.append(is_core)
            sql += " ORDER BY title"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_subject(self, subject_code, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"title", "description", "is_core", "key_stage",
                       "coordinator_staff_id"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(subject_code)
            cursor.execute(
                f"UPDATE subjects SET {set_clause} WHERE subject_code = ?", values
            )
            conn.commit()
            logger.info("Updated subject: %s", subject_code)
            return self.get_subject(subject_code)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SubjectError(f"Failed to update subject: {e}") from e
        finally:
            conn.close()

    def delete_subject(self, subject_code):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM subjects WHERE subject_code = ?", (subject_code,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted subject: %s", subject_code)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SubjectError(f"Failed to delete subject: {e}") from e
        finally:
            conn.close()
