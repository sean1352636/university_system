"""Announcement service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import AnnouncementError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class AnnouncementService:
    """CRUD operations for school announcements."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_announcement(self, title, content, audience="All",
                            priority="Normal", publish_date=None,
                            expiry_date=None, created_by=None):
        """Create a new announcement."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO announcements (
                    title, content, audience, priority,
                    publish_date, expiry_date, created_by,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Active', datetime('now'))""",
                (title, content, audience, priority,
                 publish_date, expiry_date, created_by),
            )
            conn.commit()
            ann_id = cursor.lastrowid
            logger.info("Created announcement %s: %s", ann_id, title)
            return {"id": ann_id, "title": title, "audience": audience}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AnnouncementError(
                f"Failed to create announcement: {e}") from e
        finally:
            conn.close()

    def get_announcement(self, ann_id):
        """Get a single announcement by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM announcements WHERE id = ?", (ann_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_announcements(self, audience=None, status="Active"):
        """List announcements with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM announcements WHERE 1=1"
            params = []
            if audience:
                sql += " AND audience = ?"
                params.append(audience)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_announcement(self, ann_id, **kwargs):
        """Update an announcement."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "title", "content", "audience", "priority",
                "publish_date", "expiry_date", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(ann_id)
            cursor.execute(
                f"UPDATE announcements SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated announcement %s", ann_id)
            return self.get_announcement(ann_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AnnouncementError(
                f"Failed to update announcement: {e}") from e
        finally:
            conn.close()

    def delete_announcement(self, ann_id):
        """Delete an announcement."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM announcements WHERE id = ?", (ann_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted announcement %s", ann_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AnnouncementError(
                f"Failed to delete announcement: {e}") from e
        finally:
            conn.close()
