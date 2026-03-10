"""Class group service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ClassGroupError
import traceback

logger = logging.getLogger(__name__)


class ClassGroupService:
    """Operations for class groups and pupil assignment."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def get_class_info(self, class_name):
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

    def assign_pupil_to_class(self, pupil_id, class_name):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pupils SET class_name = ?, updated_at = datetime('now') WHERE pupil_id = ?",
                (class_name, pupil_id),
            )
            conn.commit()
            logger.info("Assigned pupil %s to class %s", pupil_id, class_name)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClassGroupError(f"Failed to assign pupil to class: {e}") from e
        finally:
            conn.close()

    def remove_pupil_from_class(self, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pupils SET class_name = NULL, updated_at = datetime('now') WHERE pupil_id = ?",
                (pupil_id,),
            )
            conn.commit()
            logger.info("Removed pupil %s from class", pupil_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ClassGroupError(f"Failed to remove pupil from class: {e}") from e
        finally:
            conn.close()

    def list_classes_with_counts(self):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT c.*, COUNT(p.pupil_id) as pupil_count
                FROM classes c
                LEFT JOIN pupils p ON p.class_name = c.class_name AND p.status = 'Active'
                GROUP BY c.class_name
                ORDER BY c.year_group, c.class_name""",
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
