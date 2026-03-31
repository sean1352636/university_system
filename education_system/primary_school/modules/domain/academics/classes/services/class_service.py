"""Class management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ClassError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class ClassService:
    """CRUD operations for classes."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_class(self, class_name, year_group, teacher_staff_id=None,
                     ta_staff_id=None, room=None, capacity=30):
        if not class_name or not class_name.strip():
            raise ClassError("Class name is required")
        if not year_group:
            raise ClassError("Year group is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO classes (
                    class_name, year_group, teacher_staff_id,
                    teaching_assistant_staff_id, room, capacity
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (class_name.strip(), year_group, teacher_staff_id, ta_staff_id,
                 room, capacity),
            )
            conn.commit()
            logger.info("Created class: %s (Year %s)", class_name, year_group)
            return {"class_name": class_name, "year_group": year_group}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClassError(f"Failed to create class: {e}") from e
        finally:
            conn.close()

    def get_class(self, class_name):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM classes WHERE class_name = ?", (class_name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_classes(self, year_group=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM classes WHERE 1=1"
            params = []
            if year_group is not None:
                sql += " AND year_group = ?"
                params.append(year_group)
            sql += " ORDER BY year_group, class_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_class(self, class_name, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"year_group", "teacher_staff_id",
                       "teaching_assistant_staff_id", "room", "capacity"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(class_name)
            cursor.execute(
                f"UPDATE classes SET {set_clause} WHERE class_name = ?", values
            )
            conn.commit()
            logger.info("Updated class: %s", class_name)
            return self.get_class(class_name)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClassError(f"Failed to update class: {e}") from e
        finally:
            conn.close()

    def delete_class(self, class_name):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM classes WHERE class_name = ?", (class_name,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted class: %s", class_name)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClassError(f"Failed to delete class: {e}") from e
        finally:
            conn.close()

    def get_class_pupils(self, class_name):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM pupils WHERE class_name = ?
                   ORDER BY last_name, first_name""",
                (class_name,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
