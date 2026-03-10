"""Cover management service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import CoverError
import traceback

logger = logging.getLogger(__name__)


class CoverService:
    """CRUD operations for cover arrangements."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_cover(self, absent_staff_id, class_name, date, period=None,
                     cover_staff_id=None, subject_code=None,
                     cover_notes=None):
        """Create a cover arrangement."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO cover_lessons (
                    absent_staff_id, class_name, date, period,
                    cover_staff_id, subject_code, cover_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    absent_staff_id, class_name, date, period,
                    cover_staff_id, subject_code, cover_notes,
                ),
            )
            conn.commit()
            cover_id = cursor.lastrowid
            logger.info(
                "Created cover for %s on %s (id=%s, class=%s)",
                absent_staff_id, date, cover_id, class_name,
            )
            return cover_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CoverError(f"Failed to create cover: {e}") from e
        finally:
            conn.close()

    def get_covers(self, date=None, absent_staff_id=None,
                   cover_staff_id=None, status=None):
        """Retrieve cover arrangements with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM cover_lessons WHERE 1=1"
            params = []
            if date:
                sql += " AND date = ?"
                params.append(date)
            if absent_staff_id:
                sql += " AND absent_staff_id = ?"
                params.append(absent_staff_id)
            if cover_staff_id:
                sql += " AND cover_staff_id = ?"
                params.append(cover_staff_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY date DESC, period"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_cover(self, cover_id, **kwargs):
        """Update a cover arrangement."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "absent_staff_id", "class_name", "date", "period",
                "cover_staff_id", "subject_code", "cover_notes", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [cover_id]
            cursor.execute(
                f"UPDATE cover_lessons SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated cover: %s", cover_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CoverError(f"Failed to update cover: {e}") from e
        finally:
            conn.close()

    def delete_cover(self, cover_id):
        """Delete a cover arrangement."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM cover_lessons WHERE id = ?", (cover_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted cover: %s", cover_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CoverError(f"Failed to delete cover: {e}") from e
        finally:
            conn.close()
