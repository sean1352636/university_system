"""
In-App Notification Service

Extends the existing real-time notification system with additional features:
- Notification center with read/unread tracking
- Rich notifications with actions
- Notification preferences
- Bulk operations
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.infrastructure.communication.realtime_notifications import (
    NotificationService as BaseNotificationService,
    Notification,
    NotificationType,
    NotificationPriority,
    get_notification_service as get_base_notification_service
)

logger = logging.getLogger(__name__)


class InAppNotificationService:
    """Enhanced in-app notification service"""

    def __init__(self):
        """Initialize in-app notification service"""
        self.base_service = get_base_notification_service()
        self._ensure_extended_tables()

    def _heal_notification_actions_schema(self, conn) -> None:
        """Repair the notification_actions FK on older DBs.

        Pre-fix deployments shipped ``FOREIGN KEY (notification_id)
        REFERENCES notifications(id)`` — but the notifications PK is
        ``notification_id``, not ``id``. Any DELETE on the
        notifications table then fails with "foreign key mismatch".

        We detect the broken FK with PRAGMA foreign_key_list and, if
        present, rebuild the table with the correct FK target,
        carrying the existing rows over.
        """
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='notification_actions'"
            ).fetchone()
            if not row:
                return
            fks = list(conn.execute("PRAGMA foreign_key_list(notification_actions)"))
            # row layout: (id, seq, table, from, to, on_update, on_delete, match)
            broken = any(
                r[2] == "notifications" and r[4] != "notification_id"
                for r in fks
            )
            if not broken:
                return
            logger.warning(
                "Repairing notification_actions FK (was REFERENCES "
                "notifications(id), should be notifications(notification_id))"
            )
            # The 12-step ALTER TABLE recipe — must run with FK
            # enforcement off so the rename doesn't trigger the
            # broken constraint. We're already inside a transaction,
            # so commit it first, do the unwrapped fix, then let the
            # caller continue.
            conn.commit()
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN")
            try:
                conn.execute("ALTER TABLE notification_actions RENAME TO _notification_actions_old")
                conn.execute('''
                    CREATE TABLE notification_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        notification_id INTEGER NOT NULL,
                        action_text TEXT NOT NULL,
                        action_url TEXT NOT NULL,
                        action_type TEXT DEFAULT 'link',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (notification_id)
                            REFERENCES notifications(notification_id)
                            ON DELETE CASCADE
                    )
                ''')
                conn.execute('''
                    INSERT INTO notification_actions
                        (id, notification_id, action_text, action_url,
                         action_type, created_at)
                    SELECT id, notification_id, action_text, action_url,
                           action_type, created_at
                    FROM _notification_actions_old
                ''')
                conn.execute("DROP TABLE _notification_actions_old")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
        except Exception as exc:
            logger.warning("notification_actions schema heal failed: %s", exc)

    def _ensure_extended_tables(self):
        """Create extended notification tables"""
        try:
            with transaction() as conn:
                # Notification actions table (e.g., "View Grade", "Reply")
                # FK targets notifications(notification_id) — that's the
                # actual PK of the notifications table. Earlier deployments
                # shipped this FK pointing at a non-existent `id` column,
                # which caused SQLite to refuse DELETE FROM notifications
                # with "foreign key mismatch". The migration block in
                # _heal_notification_actions_schema repairs older DBs.
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS notification_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        notification_id INTEGER NOT NULL,
                        action_text TEXT NOT NULL,
                        action_url TEXT NOT NULL,
                        action_type TEXT DEFAULT 'link',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (notification_id)
                            REFERENCES notifications(notification_id)
                            ON DELETE CASCADE
                    )
                ''')
                self._heal_notification_actions_schema(conn)

                # Notification preferences table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS notification_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL UNIQUE,
                        email_enabled INTEGER DEFAULT 1,
                        sms_enabled INTEGER DEFAULT 0,
                        push_enabled INTEGER DEFAULT 1,
                        in_app_enabled INTEGER DEFAULT 1,
                        digest_frequency TEXT DEFAULT 'instant',
                        quiet_hours_start TEXT,
                        quiet_hours_end TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                ''')

                # Type-specific preferences
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS notification_type_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        notification_type TEXT NOT NULL,
                        email_enabled INTEGER DEFAULT 1,
                        sms_enabled INTEGER DEFAULT 0,
                        push_enabled INTEGER DEFAULT 1,
                        in_app_enabled INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP,
                        UNIQUE(user_id, notification_type)
                    )
                ''')

                logger.info("Extended notification tables ensured")
        except Exception as e:
            logger.error(f"Error creating extended notification tables: {e}")

    def create_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM_ALERT,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        expires_in_days: Optional[int] = None
    ) -> Optional[int]:
        """
        Create an in-app notification

        Args:
            user_id: Target user ID
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            data: Additional data
            actions: List of actions [{'text': 'View', 'url': '/grades'}]
            expires_in_days: Expiration in days (None = no expiration)

        Returns:
            Notification ID or None on failure
        """
        # Create base notification
        notification = Notification(
            type=notification_type,
            recipient_id=int(user_id) if user_id.isdigit() else 0,  # Convert user_id to int
            title=title,
            message=message,
            data=data or {},
            priority=priority,
            expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None
        )

        # Send via base service
        success = self.base_service.send(notification)

        if not success:
            return None

        # Get the notification ID from the database
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT id FROM notifications
                    WHERE recipient_id = ?
                      AND title = ?
                      AND message = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (notification.recipient_id, title, message))

                row = cursor.fetchone()
                notification_id = row[0] if row else None

        except Exception as e:
            logger.error(f"Error getting notification ID: {e}")
            return None

        # Add actions if provided
        if actions:
            self._add_actions(notification_id, actions)

        logger.info(f"Created in-app notification {notification_id} for user {user_id}")
        return notification_id

    def _add_actions(self, notification_id: int, actions: List[Dict[str, str]]):
        """Add actions to notification"""
        try:
            with transaction() as conn:
                for action in actions:
                    conn.execute('''
                        INSERT INTO notification_actions (
                            notification_id, action_text, action_url, action_type
                        ) VALUES (?, ?, ?, ?)
                    ''', (
                        notification_id,
                        action.get('text', 'View'),
                        action.get('url', '#'),
                        action.get('type', 'link')
                    ))
        except Exception as e:
            logger.error(f"Error adding notification actions: {e}")

    def get_unread_notifications(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get unread notifications for user"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT id, type, title, message, data, priority,
                           created_at, expires_at
                    FROM notifications
                    WHERE recipient_id = ?
                      AND read_at IS NULL
                      AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY priority DESC, created_at DESC
                    LIMIT ?
                ''', (user_id, datetime.now(), limit))

                notifications = []
                for row in cursor.fetchall():
                    notification_id = row[0]
                    notification = {
                        'id': notification_id,
                        'type': row[1],
                        'title': row[2],
                        'message': row[3],
                        'data': row[4],
                        'priority': row[5],
                        'created_at': row[6],
                        'expires_at': row[7],
                        'actions': self._get_actions(notification_id)
                    }
                    notifications.append(notification)

                return notifications

        except Exception as e:
            logger.error(f"Error fetching unread notifications: {e}")
            return []

    def _get_actions(self, notification_id: int) -> List[Dict[str, str]]:
        """Get actions for notification"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT action_text, action_url, action_type
                    FROM notification_actions
                    WHERE notification_id = ?
                ''', (notification_id,))

                return [
                    {
                        'text': row[0],
                        'url': row[1],
                        'type': row[2]
                    }
                    for row in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Error fetching notification actions: {e}")
            return []

    def mark_as_read(self, notification_id: int, user_id: str) -> bool:
        """Mark notification as read"""
        return self.base_service.mark_as_read(notification_id)

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for user"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    UPDATE notifications
                    SET read_at = ?
                    WHERE recipient_id = ? AND read_at IS NULL
                ''', (datetime.now(), user_id))

                count = cursor.rowcount
                logger.info(f"Marked {count} notifications as read for user {user_id}")
                return count

        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0

    def delete_notification(self, notification_id: int, user_id: str) -> bool:
        """Delete notification"""
        try:
            with transaction() as conn:
                # Delete actions first (foreign key)
                conn.execute('''
                    DELETE FROM notification_actions
                    WHERE notification_id = ?
                ''', (notification_id,))

                # Delete notification
                conn.execute('''
                    DELETE FROM notifications
                    WHERE id = ? AND recipient_id = ?
                ''', (notification_id, user_id))

                logger.info(f"Deleted notification {notification_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False

    def get_notification_count(self, user_id: str, unread_only: bool = True) -> int:
        """Get notification count for user"""
        try:
            with get_connection() as conn:
                query = '''
                    SELECT COUNT(*)
                    FROM notifications
                    WHERE recipient_id = ?
                      AND (expires_at IS NULL OR expires_at > ?)
                '''
                params = [user_id, datetime.now()]

                if unread_only:
                    query += ' AND read_at IS NULL'

                cursor = conn.execute(query, params)
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Error getting notification count: {e}")
            return 0

    def set_user_preferences(
        self,
        user_id: str,
        email_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None,
        push_enabled: Optional[bool] = None,
        in_app_enabled: Optional[bool] = None,
        digest_frequency: Optional[str] = None,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None
    ) -> bool:
        """Set user notification preferences"""
        try:
            with transaction() as conn:
                # Check if preferences exist
                cursor = conn.execute('''
                    SELECT id FROM notification_preferences WHERE user_id = ?
                ''', (user_id,))

                exists = cursor.fetchone() is not None

                if exists:
                    # Update existing preferences
                    updates = []
                    params = []

                    if email_enabled is not None:
                        updates.append("email_enabled = ?")
                        params.append(1 if email_enabled else 0)
                    if sms_enabled is not None:
                        updates.append("sms_enabled = ?")
                        params.append(1 if sms_enabled else 0)
                    if push_enabled is not None:
                        updates.append("push_enabled = ?")
                        params.append(1 if push_enabled else 0)
                    if in_app_enabled is not None:
                        updates.append("in_app_enabled = ?")
                        params.append(1 if in_app_enabled else 0)
                    if digest_frequency is not None:
                        updates.append("digest_frequency = ?")
                        params.append(digest_frequency)
                    if quiet_hours_start is not None:
                        updates.append("quiet_hours_start = ?")
                        params.append(quiet_hours_start)
                    if quiet_hours_end is not None:
                        updates.append("quiet_hours_end = ?")
                        params.append(quiet_hours_end)

                    if updates:
                        updates.append("updated_at = ?")
                        params.append(datetime.utcnow())
                        params.append(user_id)

                        conn.execute(f'''
                            UPDATE notification_preferences
                            SET {", ".join(updates)}
                            WHERE user_id = ?
                        ''', params)

                else:
                    # Insert new preferences
                    conn.execute('''
                        INSERT INTO notification_preferences (
                            user_id, email_enabled, sms_enabled, push_enabled,
                            in_app_enabled, digest_frequency,
                            quiet_hours_start, quiet_hours_end
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        1 if email_enabled is None or email_enabled else 0,
                        1 if sms_enabled else 0,
                        1 if push_enabled is None or push_enabled else 0,
                        1 if in_app_enabled is None or in_app_enabled else 0,
                        digest_frequency or 'instant',
                        quiet_hours_start,
                        quiet_hours_end
                    ))

                logger.info(f"Updated notification preferences for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error setting notification preferences: {e}")
            return False

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user notification preferences"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT email_enabled, sms_enabled, push_enabled,
                           in_app_enabled, digest_frequency,
                           quiet_hours_start, quiet_hours_end
                    FROM notification_preferences
                    WHERE user_id = ?
                ''', (user_id,))

                row = cursor.fetchone()

                if row:
                    return {
                        'email_enabled': bool(row[0]),
                        'sms_enabled': bool(row[1]),
                        'push_enabled': bool(row[2]),
                        'in_app_enabled': bool(row[3]),
                        'digest_frequency': row[4],
                        'quiet_hours_start': row[5],
                        'quiet_hours_end': row[6]
                    }

                # Return defaults if not found
                return {
                    'email_enabled': True,
                    'sms_enabled': False,
                    'push_enabled': True,
                    'in_app_enabled': True,
                    'digest_frequency': 'instant',
                    'quiet_hours_start': None,
                    'quiet_hours_end': None
                }

        except Exception as e:
            logger.error(f"Error getting notification preferences: {e}")
            return {}

    def cleanup_expired_notifications(self, days_old: int = 30) -> int:
        """Delete old read notifications"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)

            with transaction() as conn:
                # Delete old notifications
                cursor = conn.execute('''
                    DELETE FROM notifications
                    WHERE read_at IS NOT NULL
                      AND read_at < ?
                ''', (cutoff_date,))

                count = cursor.rowcount

                # Clean up orphaned actions
                conn.execute('''
                    DELETE FROM notification_actions
                    WHERE notification_id NOT IN (SELECT id FROM notifications)
                ''')

                logger.info(f"Cleaned up {count} old notifications")
                return count

        except Exception as e:
            logger.error(f"Error cleaning up notifications: {e}")
            return 0


# Singleton instance
_in_app_notification_service: Optional[InAppNotificationService] = None


def get_in_app_notification_service() -> InAppNotificationService:
    """Get or create in-app notification service singleton"""
    global _in_app_notification_service
    if _in_app_notification_service is None:
        _in_app_notification_service = InAppNotificationService()
    return _in_app_notification_service
