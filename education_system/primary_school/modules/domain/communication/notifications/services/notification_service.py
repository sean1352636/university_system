"""Notification service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import NotificationError
import traceback

logger = logging.getLogger(__name__)


class NotificationService:
    """CRUD operations for user notifications."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_notification(self, user_id, title, message=None,
                            notification_type="Info", link=None):
        """Create a new notification for a user."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO notifications (
                    user_id, title, message, notification_type,
                    link, is_read, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, datetime('now'))""",
                (user_id, title, message, notification_type, link),
            )
            conn.commit()
            notification_id = cursor.lastrowid
            logger.info("Created notification %s for user %s: %s",
                        notification_id, user_id, title)
            return {"id": notification_id, "user_id": user_id, "title": title}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise NotificationError(f"Failed to create notification: {e}") from e
        finally:
            conn.close()

    def get_notifications(self, user_id, unread_only=False):
        """Get notifications for a user, optionally only unread ones."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM notifications WHERE user_id = ?"
            params = [user_id]
            if unread_only:
                sql += " AND is_read = 0"
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def mark_read(self, notification_id):
        """Mark a single notification as read."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
            conn.commit()
            logger.info("Marked notification %s as read", notification_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise NotificationError(
                f"Failed to mark notification read: {e}") from e
        finally:
            conn.close()

    def mark_all_read(self, user_id):
        """Mark all notifications as read for a user."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn.commit()
            count = cursor.rowcount
            logger.info("Marked %d notifications as read for user %s",
                        count, user_id)
            return count
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise NotificationError(
                f"Failed to mark all notifications read: {e}") from e
        finally:
            conn.close()

    def delete_notification(self, notification_id):
        """Delete a notification."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM notifications WHERE id = ?",
                (notification_id,),
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted notification %s", notification_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise NotificationError(
                f"Failed to delete notification: {e}") from e
        finally:
            conn.close()

    def get_unread_count(self, user_id):
        """Get the count of unread notifications for a user."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()
