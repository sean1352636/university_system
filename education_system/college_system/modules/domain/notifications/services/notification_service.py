"""Notification management service."""

from datetime import datetime, timedelta

from education_system.college_system.core.exceptions import NotificationError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing user notifications."""

    VALID_TYPES = {"info", "success", "warning", "alert"}

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def send(self, user_id: int, title: str, message: str | None = None,
             type: str = "info") -> dict:
        """Send a notification to a user."""
        if not title or not title.strip():
            raise NotificationError("Notification title is required.")
        if type not in self.VALID_TYPES:
            raise NotificationError(f"Invalid type: {type}. Must be one of: {', '.join(self.VALID_TYPES)}")

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO notifications (user_id, title, message, type)
                   VALUES (?, ?, ?, ?)""",
                (user_id, title.strip(), message, type),
            )
            conn.commit()
            logger.debug("Notification sent: user_id=%d type=%s title='%s'", user_id, type, title.strip())

            row = conn.execute(
                "SELECT * FROM notifications WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except NotificationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise NotificationError(f"Failed to send notification: {e}") from e
        finally:
            conn.close()

    def send_bulk(self, user_ids: list[int], title: str,
                  message: str | None = None, type: str = "info") -> int:
        """Send the same notification to multiple users. Returns count sent."""
        if not title or not title.strip():
            raise NotificationError("Notification title is required.")
        if type not in self.VALID_TYPES:
            raise NotificationError(f"Invalid type: {type}.")

        conn = self._conn()
        try:
            for uid in user_ids:
                conn.execute(
                    """INSERT INTO notifications (user_id, title, message, type)
                       VALUES (?, ?, ?, ?)""",
                    (uid, title.strip(), message, type),
                )
            conn.commit()
            logger.info("Bulk notification sent to %d users: '%s'", len(user_ids), title.strip())
            return len(user_ids)
        except Exception as e:
            conn.rollback()
            raise NotificationError(f"Bulk send failed: {e}") from e
        finally:
            conn.close()

    def get_notifications(self, user_id: int, unread_only: bool = False,
                          limit: int = 50) -> list[dict]:
        """Get notifications for a user."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM notifications WHERE user_id = ?"
            params: list = [user_id]

            if unread_only:
                sql += " AND is_read = 0"

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count_unread(self, user_id: int) -> int:
        """Count unread notifications for a user."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def mark_read(self, notification_id: int, user_id: int) -> bool:
        """Mark a single notification as read."""
        conn = self._conn()
        try:
            result = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                (notification_id, user_id),
            )
            conn.commit()
            if result.rowcount == 0:
                raise NotificationError("Notification not found.")
            return True
        except NotificationError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications for a user as read. Returns count updated."""
        conn = self._conn()
        try:
            result = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn.commit()
            return result.rowcount
        finally:
            conn.close()

    def delete_old(self, days: int = 30) -> int:
        """Delete notifications older than the specified number of days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM notifications WHERE created_at < ?", (cutoff,)
            )
            conn.commit()
            logger.info("Old notifications deleted: %d removed (older than %d days)", result.rowcount, days)
            return result.rowcount
        finally:
            conn.close()
