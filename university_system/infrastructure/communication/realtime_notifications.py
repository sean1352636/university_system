"""
Real-time Notifications for the University System.

Provides WebSocket-based real-time notifications for important events
like grade postings, messages, and system alerts.

Note: This module provides the infrastructure for real-time notifications.
For the Flask web interface, you'll need to install flask-socketio.
For the CLI/GUI interfaces, this provides a notification queue system.
"""

from __future__ import annotations

import json
import logging
import queue
from university_system.infrastructure.database.db import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from university_system.core.sql_safety import validate_table_name

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Types of notifications."""
    GRADE_POSTED = 'grade_posted'
    MESSAGE_RECEIVED = 'message_received'
    ENROLLMENT_CONFIRMED = 'enrollment_confirmed'
    PAYMENT_RECEIVED = 'payment_received'
    DEADLINE_REMINDER = 'deadline_reminder'
    SYSTEM_ALERT = 'system_alert'
    ANNOUNCEMENT = 'announcement'
    COURSE_UPDATE = 'course_update'
    SCHEDULE_CHANGE = 'schedule_change'

class NotificationPriority(Enum):
    """Priority levels for notifications."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class Notification:
    """A single notification."""
    id: Optional[int] = None
    type: NotificationType = NotificationType.SYSTEM_ALERT
    recipient_id: Optional[int] = None  # User ID
    title: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    read_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type.value,
            'recipient_id': self.recipient_id,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_read': self.read_at is not None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        return cls(
            id=data.get('id'),
            type=NotificationType(data['type']) if isinstance(data.get('type'), str) else data.get('type', NotificationType.SYSTEM_ALERT),
            recipient_id=data.get('recipient_id'),
            title=data.get('title', ''),
            message=data.get('message', ''),
            data=data.get('data', {}),
            priority=NotificationPriority(data['priority']) if isinstance(data.get('priority'), int) else data.get('priority', NotificationPriority.NORMAL),
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at', datetime.now()),
            read_at=datetime.fromisoformat(data['read_at']) if data.get('read_at') else None,
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
        )

class NotificationHandler(ABC):
    """Abstract base class for notification handlers."""

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send a notification."""
        pass

class DatabaseNotificationHandler(NotificationHandler):
    """Stores notifications in the database for later retrieval."""

    # Use dedicated table to avoid conflicts with existing notifications table
    TABLE_NAME = 'realtime_notifications'

    def __init__(self, db_path: Optional[str] = None):
        validate_table_name(self.TABLE_NAME)
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        """Initialize notifications table."""
        with get_connection(self.db_path) as conn:
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    recipient_id INTEGER,
                    title TEXT NOT NULL,
                    message TEXT,
                    data TEXT,
                    priority INTEGER DEFAULT 2,
                    created_at TEXT NOT NULL,
                    read_at TEXT,
                    expires_at TEXT
                )
            ''')
            conn.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_realtime_notif_recipient
                ON {self.TABLE_NAME}(recipient_id, read_at, created_at DESC)
            ''')
            conn.commit()

    def send(self, notification: Notification) -> bool:
        try:
            with get_connection(self.db_path) as conn:
                cursor = conn.execute(f'''
                    INSERT INTO {self.TABLE_NAME}
                    (type, recipient_id, title, message, data, priority, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    notification.type.value,
                    notification.recipient_id,
                    notification.title,
                    notification.message,
                    json.dumps(notification.data),
                    notification.priority.value,
                    notification.created_at.isoformat(),
                    notification.expires_at.isoformat() if notification.expires_at else None,
                ))
                conn.commit()
                notification.id = cursor.lastrowid
            return True
        except Exception as e:
            logger.error(f"Failed to store notification: {e}")
            return False

class InMemoryNotificationHandler(NotificationHandler):
    """In-memory notification queue for real-time delivery."""

    def __init__(self, max_queue_size: int = 10000):
        self._queues: Dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self.max_queue_size = max_queue_size

    def send(self, notification: Notification) -> bool:
        if notification.recipient_id is None:
            return False

        with self._lock:
            if notification.recipient_id not in self._queues:
                self._queues[notification.recipient_id] = queue.Queue(maxsize=self.max_queue_size)

            try:
                self._queues[notification.recipient_id].put_nowait(notification)
                return True
            except queue.Full:
                logger.warning(f"Notification queue full for user {notification.recipient_id}")
                return False

    def get_notifications(self, user_id: int, timeout: float = 0.0) -> List[Notification]:
        """Get pending notifications for a user."""
        with self._lock:
            if user_id not in self._queues:
                return []

        notifications = []
        user_queue = self._queues.get(user_id)

        if user_queue:
            try:
                while True:
                    notification = user_queue.get_nowait()
                    notifications.append(notification)
            except queue.Empty:
                pass

        return notifications

    def wait_for_notification(self, user_id: int, timeout: float = 30.0) -> Optional[Notification]:
        """Wait for a notification with timeout."""
        with self._lock:
            if user_id not in self._queues:
                self._queues[user_id] = queue.Queue(maxsize=self.max_queue_size)

        try:
            return self._queues[user_id].get(timeout=timeout)
        except queue.Empty:
            return None

class NotificationService:
    """
    Main notification service for sending and managing notifications.

    Example:
        >>> service = NotificationService()
        >>>
        >>> # Send a grade notification
        >>> service.notify_grade_posted(
        ...     student_id=123,
        ...     course_id='CS101',
        ...     grade='A'
        ... )
        >>>
        >>> # Get unread notifications
        >>> notifications = service.get_unread(user_id=123)
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        enable_realtime: bool = True,
    ):
        """
        Initialize notification service.

        Args:
            db_path: Database path
            enable_realtime: Enable real-time notification queue
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_handler = DatabaseNotificationHandler(db_path)
        self.realtime_handler = InMemoryNotificationHandler() if enable_realtime else None

        self._subscribers: Dict[int, Set[Callable[[Notification], None]]] = {}
        self._global_subscribers: Set[Callable[[Notification], None]] = set()
        self._lock = threading.Lock()

        logger.info("NotificationService initialized")

    def send(self, notification: Notification) -> bool:
        """
        Send a notification.

        Args:
            notification: The notification to send

        Returns:
            True if sent successfully
        """
        # Store in database
        stored = self.db_handler.send(notification)

        # Add to real-time queue if enabled
        if self.realtime_handler and notification.recipient_id:
            self.realtime_handler.send(notification)

        # Notify subscribers
        self._notify_subscribers(notification)

        logger.debug(f"Notification sent: {notification.type.value} to user {notification.recipient_id}")
        return stored

    def _notify_subscribers(self, notification: Notification) -> None:
        """Notify registered subscribers."""
        with self._lock:
            # Global subscribers
            for callback in self._global_subscribers:
                try:
                    callback(notification)
                except Exception as e:
                    logger.error(f"Subscriber callback error: {e}")

            # User-specific subscribers
            if notification.recipient_id in self._subscribers:
                for callback in self._subscribers[notification.recipient_id]:
                    try:
                        callback(notification)
                    except Exception as e:
                        logger.error(f"User subscriber callback error: {e}")

    def subscribe(
        self,
        callback: Callable[[Notification], None],
        user_id: Optional[int] = None,
    ) -> None:
        """
        Subscribe to notifications.

        Args:
            callback: Function to call when notification is sent
            user_id: Only receive notifications for this user (None for all)
        """
        with self._lock:
            if user_id is None:
                self._global_subscribers.add(callback)
            else:
                if user_id not in self._subscribers:
                    self._subscribers[user_id] = set()
                self._subscribers[user_id].add(callback)

    def unsubscribe(
        self,
        callback: Callable[[Notification], None],
        user_id: Optional[int] = None,
    ) -> None:
        """Unsubscribe from notifications."""
        with self._lock:
            if user_id is None:
                self._global_subscribers.discard(callback)
            elif user_id in self._subscribers:
                self._subscribers[user_id].discard(callback)

    # Convenience methods for common notification types

    def notify_grade_posted(
        self,
        student_id: int,
        course_id: str,
        grade: str,
        course_name: Optional[str] = None,
    ) -> bool:
        """Send notification when a grade is posted."""
        course_display = course_name or course_id
        return self.send(Notification(
            type=NotificationType.GRADE_POSTED,
            recipient_id=student_id,
            title="Grade Posted",
            message=f"Your grade for {course_display} has been posted: {grade}",
            data={
                'course_id': course_id,
                'course_name': course_name,
                'grade': grade,
                'timestamp': datetime.now().isoformat(),
            },
            priority=NotificationPriority.HIGH,
        ))

    def notify_message_received(
        self,
        recipient_id: int,
        sender_name: str,
        subject: str,
        message_id: Optional[int] = None,
    ) -> bool:
        """Send notification when a message is received."""
        return self.send(Notification(
            type=NotificationType.MESSAGE_RECEIVED,
            recipient_id=recipient_id,
            title="New Message",
            message=f"New message from {sender_name}: {subject}",
            data={
                'sender_name': sender_name,
                'subject': subject,
                'message_id': message_id,
            },
            priority=NotificationPriority.NORMAL,
        ))

    def notify_enrollment_confirmed(
        self,
        student_id: int,
        course_id: str,
        course_name: Optional[str] = None,
    ) -> bool:
        """Send notification when enrollment is confirmed."""
        course_display = course_name or course_id
        return self.send(Notification(
            type=NotificationType.ENROLLMENT_CONFIRMED,
            recipient_id=student_id,
            title="Enrollment Confirmed",
            message=f"You have been enrolled in {course_display}",
            data={
                'course_id': course_id,
                'course_name': course_name,
            },
            priority=NotificationPriority.NORMAL,
        ))

    def notify_deadline_reminder(
        self,
        recipient_id: int,
        title: str,
        deadline: datetime,
        item_type: str = 'assignment',
    ) -> bool:
        """Send deadline reminder notification."""
        time_remaining = deadline - datetime.now()
        if time_remaining.days > 0:
            time_str = f"{time_remaining.days} days"
        elif time_remaining.seconds > 3600:
            time_str = f"{time_remaining.seconds // 3600} hours"
        else:
            time_str = f"{time_remaining.seconds // 60} minutes"

        return self.send(Notification(
            type=NotificationType.DEADLINE_REMINDER,
            recipient_id=recipient_id,
            title=f"Deadline Reminder: {title}",
            message=f"{item_type.title()} '{title}' is due in {time_str}",
            data={
                'deadline': deadline.isoformat(),
                'item_type': item_type,
                'item_title': title,
            },
            priority=NotificationPriority.HIGH if time_remaining.days == 0 else NotificationPriority.NORMAL,
            expires_at=deadline,
        ))

    def notify_system_alert(
        self,
        title: str,
        message: str,
        recipient_id: Optional[int] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> bool:
        """Send system alert notification."""
        return self.send(Notification(
            type=NotificationType.SYSTEM_ALERT,
            recipient_id=recipient_id,
            title=title,
            message=message,
            priority=priority,
        ))

    def broadcast_announcement(
        self,
        title: str,
        message: str,
        user_ids: Optional[List[int]] = None,
    ) -> int:
        """
        Broadcast announcement to multiple users.

        Args:
            title: Announcement title
            message: Announcement message
            user_ids: List of user IDs (None for all users)

        Returns:
            Number of notifications sent
        """
        if user_ids is None:
            # Get all active users
            with get_connection(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id FROM users WHERE id IN (SELECT user_id FROM user_accounts WHERE is_active = 1)"
                )
                user_ids = [row[0] for row in cursor.fetchall()]

        sent = 0
        for user_id in user_ids:
            if self.send(Notification(
                type=NotificationType.ANNOUNCEMENT,
                recipient_id=user_id,
                title=title,
                message=message,
                priority=NotificationPriority.NORMAL,
            )):
                sent += 1

        logger.info(f"Broadcast sent to {sent}/{len(user_ids)} users")
        return sent

    # Retrieval methods

    def get_unread(
        self,
        user_id: int,
        limit: int = 50,
        notification_type: Optional[NotificationType] = None,
    ) -> List[Notification]:
        """Get unread notifications for a user."""
        table = self.db_handler.TABLE_NAME
        with get_connection(self.db_path) as conn:
            query = f'''
                SELECT id, type, recipient_id, title, message, data, priority,
                       created_at, read_at, expires_at
                FROM {table}
                WHERE recipient_id = ? AND read_at IS NULL
            '''
            params = [user_id]

            if notification_type:
                query += " AND type = ?"
                params.append(notification_type.value)

            query += " ORDER BY priority DESC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)

            notifications = []
            for row in cursor.fetchall():
                notifications.append(Notification(
                    id=row[0],
                    type=NotificationType(row[1]),
                    recipient_id=row[2],
                    title=row[3],
                    message=row[4],
                    data=json.loads(row[5]) if row[5] else {},
                    priority=NotificationPriority(row[6]),
                    created_at=datetime.fromisoformat(row[7]),
                    read_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    expires_at=datetime.fromisoformat(row[9]) if row[9] else None,
                ))

            return notifications

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications."""
        table = self.db_handler.TABLE_NAME
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(f'''
                SELECT COUNT(*) FROM {table}
                WHERE recipient_id = ? AND read_at IS NULL
            ''', (user_id,))
            return cursor.fetchone()[0]

    def mark_as_read(self, notification_id: int) -> bool:
        """Mark a notification as read."""
        table = self.db_handler.TABLE_NAME
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(f'''
                UPDATE {table} SET read_at = ? WHERE id = ?
            ''', (datetime.now().isoformat(), notification_id))
            conn.commit()
            return cursor.rowcount > 0

    def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user."""
        table = self.db_handler.TABLE_NAME
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(f'''
                UPDATE {table} SET read_at = ?
                WHERE recipient_id = ? AND read_at IS NULL
            ''', (datetime.now().isoformat(), user_id))
            conn.commit()
            return cursor.rowcount

    def cleanup_old_notifications(self, days: int = 30) -> int:
        """Remove old read notifications."""
        table = self.db_handler.TABLE_NAME
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(f'''
                DELETE FROM {table}
                WHERE read_at IS NOT NULL AND read_at < ?
            ''', (cutoff,))
            conn.commit()

            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old notifications")
            return deleted

    def wait_for_notification(
        self,
        user_id: int,
        timeout: float = 30.0,
    ) -> Optional[Notification]:
        """
        Wait for a real-time notification (blocking).

        Args:
            user_id: User ID to wait for
            timeout: Timeout in seconds

        Returns:
            Notification if received, None on timeout
        """
        if self.realtime_handler:
            return self.realtime_handler.wait_for_notification(user_id, timeout)
        return None

# Global service instance
_notification_service: Optional[NotificationService] = None
_service_lock = threading.Lock()

def get_notification_service() -> NotificationService:
    """Get or create the global notification service."""
    global _notification_service

    if _notification_service is None:
        with _service_lock:
            if _notification_service is None:
                _notification_service = NotificationService()

    return _notification_service

# Convenience functions

def notify_grade_posted(student_id: int, course_id: str, grade: str, course_name: Optional[str] = None) -> bool:
    """Send grade posted notification."""
    return get_notification_service().notify_grade_posted(student_id, course_id, grade, course_name)

def notify_message_received(recipient_id: int, sender_name: str, subject: str, message_id: Optional[int] = None) -> bool:
    """Send message received notification."""
    return get_notification_service().notify_message_received(recipient_id, sender_name, subject, message_id)

__all__ = [
    'NotificationService',
    'Notification',
    'NotificationType',
    'NotificationPriority',
    'NotificationHandler',
    'DatabaseNotificationHandler',
    'InMemoryNotificationHandler',
    'get_notification_service',
    'notify_grade_posted',
    'notify_message_received',
]
