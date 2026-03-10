"""Notification centre service."""

import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, user_id, title, message):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                (user_id, title, message))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def list_notifications(self, user_id, unread_only=False):
        conn = self._conn()
        try:
            sql = "SELECT * FROM notifications WHERE user_id = ?"
            params = [user_id]
            if unread_only:
                sql += " AND is_read = 0"
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def mark_read(self, notification_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
        finally:
            conn.close()

    def mark_all_read(self, user_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_notification(self, notification_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
            conn.commit()
        finally:
            conn.close()

    def unread_count(self, user_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
                               (user_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
