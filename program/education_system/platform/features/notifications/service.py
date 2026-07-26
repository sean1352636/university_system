"""Cross-system notification service using the shared auth database."""

import sqlite3
from education_system.platform.identity.auth.db import AUTH_DB_FILE


class CrossSystemNotificationService:
    """Send and receive notifications between education system instances."""

    def __init__(self, db_path=None):
        self._db_path = db_path or str(AUTH_DB_FILE)

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def send(self, sender_user_id, sender_system, recipient_user_id,
             recipient_system, title, message=None, priority="normal"):
        """Send a cross-system notification."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO cross_system_notifications
                   (sender_user_id, sender_system, recipient_user_id,
                    recipient_system, title, message, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sender_user_id, sender_system, recipient_user_id,
                 recipient_system, title, message, priority),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cross_system_notifications WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def send_to_role(self, sender_user_id, sender_system,
                     target_system, target_role, title, message=None, priority="normal"):
        """Send a notification to all users with a given role in a target system."""
        conn = self._conn()
        try:
            recipients = conn.execute(
                "SELECT u.id FROM users u "
                "JOIN user_systems us ON u.id = us.user_id "
                "WHERE us.system_key = ? AND us.role = ? AND u.is_active = 1",
                (target_system, target_role),
            ).fetchall()
            count = 0
            for r in recipients:
                conn.execute(
                    """INSERT INTO cross_system_notifications
                       (sender_user_id, sender_system, recipient_user_id,
                        recipient_system, title, message, priority)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sender_user_id, sender_system, r["id"],
                     target_system, title, message, priority),
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def get_unread(self, user_id, system_key=None):
        """Get unread notifications for a user, optionally filtered by system."""
        conn = self._conn()
        try:
            if system_key:
                rows = conn.execute(
                    "SELECT n.*, u.display_name as sender_name FROM cross_system_notifications n "
                    "LEFT JOIN users u ON n.sender_user_id = u.id "
                    "WHERE n.recipient_user_id = ? AND n.recipient_system = ? AND n.is_read = 0 "
                    "ORDER BY n.created_at DESC",
                    (user_id, system_key),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT n.*, u.display_name as sender_name FROM cross_system_notifications n "
                    "LEFT JOIN users u ON n.sender_user_id = u.id "
                    "WHERE n.recipient_user_id = ? AND n.is_read = 0 "
                    "ORDER BY n.created_at DESC",
                    (user_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all(self, user_id, system_key=None, limit=50):
        """Get all notifications for a user."""
        conn = self._conn()
        try:
            if system_key:
                rows = conn.execute(
                    "SELECT n.*, u.display_name as sender_name FROM cross_system_notifications n "
                    "LEFT JOIN users u ON n.sender_user_id = u.id "
                    "WHERE n.recipient_user_id = ? AND n.recipient_system = ? "
                    "ORDER BY n.created_at DESC LIMIT ?",
                    (user_id, system_key, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT n.*, u.display_name as sender_name FROM cross_system_notifications n "
                    "LEFT JOIN users u ON n.sender_user_id = u.id "
                    "WHERE n.recipient_user_id = ? "
                    "ORDER BY n.created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_read(self, notification_id):
        """Mark a notification as read."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE cross_system_notifications SET is_read = 1, read_at = datetime('now') "
                "WHERE id = ?",
                (notification_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_all_read(self, user_id, system_key=None):
        """Mark all notifications as read for a user."""
        conn = self._conn()
        try:
            if system_key:
                conn.execute(
                    "UPDATE cross_system_notifications SET is_read = 1, read_at = datetime('now') "
                    "WHERE recipient_user_id = ? AND recipient_system = ? AND is_read = 0",
                    (user_id, system_key),
                )
            else:
                conn.execute(
                    "UPDATE cross_system_notifications SET is_read = 1, read_at = datetime('now') "
                    "WHERE recipient_user_id = ? AND is_read = 0",
                    (user_id,),
                )
            conn.commit()
        finally:
            conn.close()

    def get_unread_count(self, user_id, system_key=None):
        """Get count of unread notifications."""
        conn = self._conn()
        try:
            if system_key:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cross_system_notifications "
                    "WHERE recipient_user_id = ? AND recipient_system = ? AND is_read = 0",
                    (user_id, system_key),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cross_system_notifications "
                    "WHERE recipient_user_id = ? AND is_read = 0",
                    (user_id,),
                ).fetchone()
            return row["cnt"]
        finally:
            conn.close()
