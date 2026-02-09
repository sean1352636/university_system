"""
Smart Notifications Hub Service Layer

Provides unified notification management across all university systems with
customizable preferences, priority levels, channel management, and smart bundling.

Features:
- Multi-channel notifications (academic, social, financial, health, housing, events)
- Priority levels (Low, Medium, High, Urgent)
- Quiet hours with customizable schedules
- Daily digest option
- Smart notification bundling
- Multiple delivery methods (push, email, SMS)
- Comprehensive notification history

Database Schema:
- notifications: Core notification records
- notification_preferences: User preferences and settings
- notification_channels: Channel definitions and user subscriptions
- notification_history: Delivery tracking
- digests: Daily digest compilation
- bundled_notifications: Related notification grouping
"""

import sqlite3
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(Enum):
    """Notification channel categories"""
    ACADEMIC = "academic"
    SOCIAL = "social"
    FINANCIAL = "financial"
    HEALTH = "health"
    HOUSING = "housing"
    EVENTS = "events"
    SYSTEM = "system"


class DeliveryMethod(Enum):
    """Notification delivery methods"""
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"


def map_notification_type_to_channel_priority(notification_type: str) -> Tuple[str, str]:
    """
    Map old notification_type values to new (channel, priority) system.

    This provides backward compatibility for legacy code still using notification_type.

    Args:
        notification_type: Old notification type string

    Returns:
        Tuple of (channel, priority)
    """
    # Mapping of common notification types to channel and priority
    type_mapping = {
        # Academic notifications
        'assignment': ('academic', 'medium'),
        'assignment_due': ('academic', 'high'),
        'grade_posted': ('academic', 'medium'),
        'course_update': ('academic', 'low'),
        'schedule_change': ('academic', 'high'),
        'exam_reminder': ('academic', 'high'),

        # Document notifications
        'document_uploaded': ('system', 'low'),
        'document_verified': ('system', 'low'),
        'document_rejected': ('system', 'medium'),
        'report_email': ('system', 'medium'),

        # General notifications
        'general': ('system', 'medium'),
        'info': ('system', 'low'),
        'warning': ('system', 'medium'),
        'urgent': ('system', 'urgent'),
        'critical': ('system', 'urgent'),

        # Financial
        'payment_due': ('financial', 'high'),
        'payment_received': ('financial', 'low'),
        'invoice': ('financial', 'medium'),

        # Health
        'health_alert': ('health', 'high'),
        'appointment_reminder': ('health', 'medium'),

        # Housing
        'housing_update': ('housing', 'medium'),
        'maintenance_request': ('housing', 'low'),

        # Events
        'event_reminder': ('events', 'low'),
        'event_cancelled': ('events', 'medium'),

        # Social
        'message': ('social', 'low'),
        'friend_request': ('social', 'low'),
    }

    # Default to system/medium if not found
    return type_mapping.get(notification_type.lower(), ('system', 'medium'))


def create_notification_legacy(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = 'general',
    recipient_id: Optional[str] = None,
    recipient_type: Optional[str] = None,
    created_datetime: Optional[str] = None,
    related_document_id: Optional[int] = None,
    **kwargs
) -> int:
    """
    Backward-compatible notification creation using old notification_type parameter.

    This function maps old parameters to the new notification system schema.
    Use this when updating legacy code that uses notification_type.

    Args:
        user_id: Target user ID (or recipient_id if user_id not provided)
        title: Notification title
        message: Notification message
        notification_type: Old-style notification type (converted to channel/priority)
        recipient_id: Legacy recipient ID parameter
        recipient_type: Legacy recipient type parameter (ignored)
        created_datetime: Legacy creation time (ignored, uses CURRENT_TIMESTAMP)
        related_document_id: Related document ID (stored in metadata)
        **kwargs: Additional parameters (stored in metadata if relevant)

    Returns:
        notification_id: Created notification ID
    """
    # Use recipient_id as user_id if user_id is not provided
    if not user_id and recipient_id:
        user_id = recipient_id

    # Map notification_type to channel and priority
    channel, priority = map_notification_type_to_channel_priority(notification_type)

    # Build metadata from legacy fields
    metadata_dict = {}
    if related_document_id:
        metadata_dict['related_document_id'] = related_document_id
    if recipient_type:
        metadata_dict['recipient_type'] = recipient_type
    if notification_type:
        metadata_dict['notification_type'] = notification_type  # Preserve for reference

    # Add any extra kwargs to metadata
    for key, value in kwargs.items():
        if key not in ['user_id', 'title', 'message', 'channel', 'priority']:
            metadata_dict[key] = value

    # Convert metadata to JSON string
    import json
    metadata = json.dumps(metadata_dict) if metadata_dict else None

    # Create notification using the service
    try:
        service = NotificationsService()
        return service.create_notification(
            user_id=user_id,
            channel=channel,
            priority=priority,
            title=title,
            message=message,
            source_system='legacy',
            metadata=metadata
        )
    except Exception as e:
        # Fallback: Direct database insert if service fails
        print(f"Warning: Using direct DB insert due to service error: {e}")
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO notifications (
                    user_id, channel, priority, title, message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, channel, priority, title, message, metadata))
            return cursor.lastrowid


class NotificationsService:
    """Service for managing the Smart Notifications Hub"""

    def __init__(self):
        """Initialize notifications service and create database schema"""
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create all required database tables"""
        with transaction() as conn:
            # Temporarily disable foreign key constraints during migration
            conn.execute('PRAGMA foreign_keys = OFF')

            # Check if old notifications table exists and migrate it
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
            if cursor.fetchone():
                # Check if table has old or hybrid schema
                cursor = conn.execute("PRAGMA table_info(notifications)")
                columns = {row[1] for row in cursor.fetchall()}

                # Detect schema type
                has_channel = 'channel' in columns
                has_priority = 'priority' in columns
                has_notification_type = 'notification_type' in columns

                # Pure old schema: has notification_type but not channel/priority
                is_pure_old = has_notification_type and not (has_channel and has_priority)

                # Hybrid/corrupt schema: has notification_type along with channel/priority
                # OR has extra columns beyond the core new schema
                is_hybrid = has_notification_type and has_channel and has_priority

                # Check for extra columns that shouldn't be in new schema
                unwanted_cols = {'assignment_id', 'recipient_type', 'recipient_id', 'sent', 'created_date'}
                has_unwanted = bool(unwanted_cols & columns)

                if is_pure_old or is_hybrid or has_unwanted:
                    # Need to migrate - check if backup already exists
                    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications_old'")
                    backup_exists = cursor.fetchone() is not None

                    if backup_exists:
                        # Backup already exists, just drop the current table
                        print(f"Dropping notifications table (backup exists, schema={'hybrid' if is_hybrid else 'old'})...")
                        conn.execute('DROP TABLE notifications')
                        print("Old notifications table dropped")
                    else:
                        # No backup yet, rename current table
                        print("Backing up old notifications table...")
                        conn.execute('ALTER TABLE notifications RENAME TO notifications_old')
                        print("Old notifications table backed up as notifications_old")

            # Check notification_preferences for wrong foreign key
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_preferences'")
            if cursor.fetchone():
                cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='notification_preferences'")
                schema = cursor.fetchone()[0]
                if 'users (id)' in schema or 'user_id INTEGER' in schema:
                    # Old schema with wrong foreign key or INTEGER user_id
                    print("Migrating notification_preferences table...")
                    conn.execute('DROP TABLE IF EXISTS notification_preferences')
                    print("Recreating notification_preferences with correct schema")

            # Check notification_channels for wrong foreign key
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_channels'")
            if cursor.fetchone():
                cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='notification_channels'")
                schema = cursor.fetchone()[0]
                if 'users(user_id)' in schema:
                    # Old schema with wrong foreign key
                    print("Migrating notification_channels table...")
                    conn.execute('DROP TABLE IF EXISTS notification_channels')
                    print("Recreating notification_channels with correct schema")

            # Check notification_history for wrong foreign key
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='digests'")
            if cursor.fetchone():
                cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='digests'")
                result = cursor.fetchone()
                if result:
                    schema = result[0]
                    if 'users(user_id)' in schema:
                        print("Migrating digests table...")
                        conn.execute('DROP TABLE IF EXISTS digests')
                        print("Recreating digests with correct schema")

            # Check bundled_notifications for wrong foreign key
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bundled_notifications'")
            if cursor.fetchone():
                cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bundled_notifications'")
                result = cursor.fetchone()
                if result:
                    schema = result[0]
                    if 'users(user_id)' in schema:
                        print("Migrating bundled_notifications table...")
                        conn.execute('DROP TABLE IF EXISTS bundled_notifications')
                        print("Recreating bundled_notifications with correct schema")

            # Core notifications table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source_system TEXT,
                    source_id TEXT,
                    is_read INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    read_at TEXT,
                    expires_at TEXT,
                    metadata TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(username)
                )
            ''')

            # User notification preferences
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    quiet_hours_start TEXT,
                    quiet_hours_end TEXT,
                    daily_digest_enabled INTEGER DEFAULT 0,
                    daily_digest_time TEXT DEFAULT '08:00',
                    bundle_notifications INTEGER DEFAULT 1,
                    bundle_time_window INTEGER DEFAULT 300,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(username)
                )
            ''')

            # Migrate existing notification_preferences table if needed
            # Check if table exists and add missing columns
            cursor = conn.execute("PRAGMA table_info(notification_preferences)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            required_columns = {
                'quiet_hours_start': 'TEXT',
                'quiet_hours_end': 'TEXT',
                'daily_digest_enabled': 'INTEGER DEFAULT 0',
                'daily_digest_time': "TEXT DEFAULT '08:00'",
                'bundle_notifications': 'INTEGER DEFAULT 1',
                'bundle_time_window': 'INTEGER DEFAULT 300',
                'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
            }

            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    try:
                        conn.execute(f'ALTER TABLE notification_preferences ADD COLUMN {col_name} {col_type}')
                    except Exception:
                        pass  # Column might already exist or other constraint

            # Channel-specific user settings
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notification_channels (
                    channel_setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    min_priority TEXT DEFAULT 'low',
                    push_enabled INTEGER DEFAULT 1,
                    email_enabled INTEGER DEFAULT 1,
                    sms_enabled INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, channel),
                    FOREIGN KEY (user_id) REFERENCES users(username)
                )
            ''')

            # Notification delivery history
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notification_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER NOT NULL,
                    delivery_method TEXT NOT NULL,
                    delivered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    error_message TEXT,
                    FOREIGN KEY (notification_id) REFERENCES notifications(notification_id)
                )
            ''')

            # Daily digest compilation
            conn.execute('''
                CREATE TABLE IF NOT EXISTS digests (
                    digest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    digest_date DATE NOT NULL,
                    sent_at TEXT,
                    notification_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, digest_date),
                    FOREIGN KEY (user_id) REFERENCES users(username)
                )
            ''')

            # Bundled notifications (related notifications grouped together)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bundled_notifications (
                    bundle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    bundle_title TEXT NOT NULL,
                    notification_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(username)
                )
            ''')

            # Link notifications to bundles
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notification_bundle_items (
                    bundle_id INTEGER NOT NULL,
                    notification_id INTEGER NOT NULL,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (bundle_id, notification_id),
                    FOREIGN KEY (bundle_id) REFERENCES bundled_notifications(bundle_id),
                    FOREIGN KEY (notification_id) REFERENCES notifications(notification_id)
                )
            ''')

            # Create indexes for performance
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
                ON notifications(user_id, is_read, created_at DESC)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_notifications_channel
                ON notifications(user_id, channel, created_at DESC)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_notifications_priority
                ON notifications(priority, created_at DESC)
            ''')

            # Re-enable foreign key constraints
            conn.execute('PRAGMA foreign_keys = ON')

    # ==================== Notification Management ====================

    def create_notification(
        self,
        user_id: str,
        channel: str,
        priority: str,
        title: str,
        message: str,
        source_system: Optional[str] = None,
        source_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[str] = None
    ) -> int:
        """
        Create a new notification

        Args:
            user_id: Target user ID
            channel: Notification channel
            priority: Priority level
            title: Notification title
            message: Notification message
            source_system: Originating system
            source_id: Source record ID
            expires_at: Expiration timestamp
            metadata: Additional JSON metadata

        Returns:
            notification_id: Created notification ID
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO notifications (
                    user_id, channel, priority, title, message,
                    source_system, source_id, expires_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, channel, priority, title, message,
                source_system, source_id, expires_at, metadata
            ))

            notification_id = cursor.lastrowid

            # Check if we should bundle this notification
            if self._should_bundle_notification(user_id, channel):
                self._add_to_bundle(notification_id, user_id, channel, title)

            # Check if we should deliver immediately
            if not self._is_quiet_hours(user_id) and not self._is_digest_only(user_id):
                self._deliver_notification(notification_id, user_id, channel, priority)

            log_activity(
                'create', 'notification',
                notification_id=notification_id,
                details={
                    'user_id': user_id,
                    'channel': channel,
                    'priority': priority,
                    'title': title
                }
            )

            return notification_id

    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        channel: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get user notifications with filtering

        Args:
            user_id: User ID
            unread_only: Only show unread notifications
            channel: Filter by channel
            priority: Filter by priority
            limit: Maximum results
            offset: Result offset

        Returns:
            List of notification dictionaries
        """
        query = 'SELECT * FROM notifications WHERE user_id = ? AND is_archived = 0'
        params = [user_id]

        if unread_only:
            query += ' AND is_read = 0'

        if channel:
            query += ' AND channel = ?'
            params.append(channel)

        if priority:
            query += ' AND priority = ?'
            params.append(priority)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        with get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]

            notifications = []
            for row in cursor.fetchall():
                notification = dict(zip(columns, row))
                notifications.append(notification)

            return notifications

    def mark_as_read(self, notification_id: int, user_id: str) -> bool:
        """
        Mark a notification as read

        Args:
            notification_id: Notification ID
            user_id: User ID (for authorization)

        Returns:
            Success status
        """
        with transaction() as conn:
            cursor = conn.execute('''
                UPDATE notifications
                SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE notification_id = ? AND user_id = ?
            ''', (notification_id, user_id))

            if cursor.rowcount > 0:
                log_activity(
                    'update', 'notification',
                    notification_id=notification_id,
                    details={'action': 'mark_as_read'}
                )
                return True

            return False

    def mark_all_as_read(self, user_id: str, channel: Optional[str] = None) -> int:
        """
        Mark all notifications as read

        Args:
            user_id: User ID
            channel: Optional channel filter

        Returns:
            Number of notifications marked as read
        """
        query = 'UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND is_read = 0'
        params = [user_id]

        if channel:
            query += ' AND channel = ?'
            params.append(channel)

        with transaction() as conn:
            cursor = conn.execute(query, params)
            count = cursor.rowcount

            if count > 0:
                log_activity(
                    'update', 'notification',
                    details={
                        'user_id': user_id,
                        'action': 'mark_all_as_read',
                        'channel': channel,
                        'count': count
                    }
                )

            return count

    def archive_notification(self, notification_id: int, user_id: str) -> bool:
        """Archive a notification"""
        with transaction() as conn:
            cursor = conn.execute('''
                UPDATE notifications
                SET is_archived = 1
                WHERE notification_id = ? AND user_id = ?
            ''', (notification_id, user_id))

            return cursor.rowcount > 0

    def delete_old_notifications(self, user_id: str, days: int = 30) -> int:
        """Delete notifications older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with transaction() as conn:
            cursor = conn.execute('''
                DELETE FROM notifications
                WHERE user_id = ? AND created_at < ? AND is_read = 1
            ''', (user_id, cutoff_date))

            count = cursor.rowcount

            if count > 0:
                log_activity(
                    'delete', 'notification',
                    details={
                        'user_id': user_id,
                        'count': count,
                        'older_than_days': days
                    }
                )

            return count

    def get_unread_count(self, user_id: str, channel: Optional[str] = None) -> int:
        """Get count of unread notifications"""
        query = 'SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0 AND is_archived = 0'
        params = [user_id]

        if channel:
            query += ' AND channel = ?'
            params.append(channel)

        with get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]

    # ==================== Preferences Management ====================

    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user notification preferences"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM notification_preferences WHERE user_id = ?
                ''', (user_id,))

                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                else:
                    # Create default preferences
                    return self._create_default_preferences(user_id)
        except Exception:
            # If query fails, return defaults without database storage
            return self._create_default_preferences(user_id)

    def _create_default_preferences(self, user_id: str) -> Dict[str, Any]:
        """Create default preferences for new user"""
        try:
            with transaction() as conn:
                # Temporarily disable foreign key constraints for this insert
                conn.execute('PRAGMA foreign_keys = OFF')

                conn.execute('''
                    INSERT INTO notification_preferences (
                        user_id, quiet_hours_start, quiet_hours_end,
                        daily_digest_enabled, daily_digest_time,
                        bundle_notifications, bundle_time_window
                    ) VALUES (?, '22:00', '08:00', 0, '08:00', 1, 300)
                ''', (user_id,))

                # Create default channel settings
                for channel in NotificationChannel:
                    conn.execute('''
                        INSERT OR IGNORE INTO notification_channels (
                            user_id, channel, enabled, min_priority,
                            push_enabled, email_enabled, sms_enabled
                        ) VALUES (?, ?, 1, 'low', 1, 1, 0)
                    ''', (user_id, channel.value))

                # Re-enable foreign key constraints
                conn.execute('PRAGMA foreign_keys = ON')
        except Exception as e:
            # If insertion fails, return default values without database storage
            return {
                'user_id': user_id,
                'quiet_hours_start': '22:00',
                'quiet_hours_end': '08:00',
                'daily_digest_enabled': 0,
                'daily_digest_time': '08:00',
                'bundle_notifications': 1,
                'bundle_time_window': 300
            }

        return self.get_preferences(user_id)

    def update_preferences(
        self,
        user_id: str,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
        daily_digest_enabled: Optional[bool] = None,
        daily_digest_time: Optional[str] = None,
        bundle_notifications: Optional[bool] = None,
        bundle_time_window: Optional[int] = None
    ) -> bool:
        """Update user notification preferences"""
        updates = []
        params = []

        if quiet_hours_start is not None:
            updates.append('quiet_hours_start = ?')
            params.append(quiet_hours_start)

        if quiet_hours_end is not None:
            updates.append('quiet_hours_end = ?')
            params.append(quiet_hours_end)

        if daily_digest_enabled is not None:
            updates.append('daily_digest_enabled = ?')
            params.append(1 if daily_digest_enabled else 0)

        if daily_digest_time is not None:
            updates.append('daily_digest_time = ?')
            params.append(daily_digest_time)

        if bundle_notifications is not None:
            updates.append('bundle_notifications = ?')
            params.append(1 if bundle_notifications else 0)

        if bundle_time_window is not None:
            updates.append('bundle_time_window = ?')
            params.append(bundle_time_window)

        if not updates:
            return False

        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(user_id)

        query = f'UPDATE notification_preferences SET {", ".join(updates)} WHERE user_id = ?'

        with transaction() as conn:
            cursor = conn.execute(query, params)

            if cursor.rowcount > 0:
                log_activity(
                    'update', 'notification_preferences',
                    details={'user_id': user_id, 'updates': dict(zip(updates, params[:-1]))}
                )
                return True

            return False

    def get_channel_settings(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all channel settings for user"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM notification_channels WHERE user_id = ?
                ''', (user_id,))

                columns = [desc[0] for desc in cursor.description]
                settings = []

                for row in cursor.fetchall():
                    settings.append(dict(zip(columns, row)))

                return settings
        except Exception:
            # Return empty list if query fails
            return []

    def update_channel_settings(
        self,
        user_id: str,
        channel: str,
        enabled: Optional[bool] = None,
        min_priority: Optional[str] = None,
        push_enabled: Optional[bool] = None,
        email_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None
    ) -> bool:
        """Update settings for a specific channel"""
        updates = []
        params = []

        if enabled is not None:
            updates.append('enabled = ?')
            params.append(1 if enabled else 0)

        if min_priority is not None:
            updates.append('min_priority = ?')
            params.append(min_priority)

        if push_enabled is not None:
            updates.append('push_enabled = ?')
            params.append(1 if push_enabled else 0)

        if email_enabled is not None:
            updates.append('email_enabled = ?')
            params.append(1 if email_enabled else 0)

        if sms_enabled is not None:
            updates.append('sms_enabled = ?')
            params.append(1 if sms_enabled else 0)

        if not updates:
            return False

        params.extend([user_id, channel])
        query = f'UPDATE notification_channels SET {", ".join(updates)} WHERE user_id = ? AND channel = ?'

        with transaction() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0

    # ==================== Smart Features ====================

    def _is_quiet_hours(self, user_id: str) -> bool:
        """Check if current time is within user's quiet hours"""
        prefs = self.get_preferences(user_id)

        if not prefs.get('quiet_hours_start') or not prefs.get('quiet_hours_end'):
            return False

        now = datetime.now().time()
        start = datetime.strptime(prefs['quiet_hours_start'], '%H:%M').time()
        end = datetime.strptime(prefs['quiet_hours_end'], '%H:%M').time()

        if start < end:
            return start <= now <= end
        else:  # Quiet hours span midnight
            return now >= start or now <= end

    def _is_digest_only(self, user_id: str) -> bool:
        """Check if user has daily digest enabled"""
        prefs = self.get_preferences(user_id)
        return bool(prefs.get('daily_digest_enabled', 0))

    def _should_bundle_notification(self, user_id: str, channel: str) -> bool:
        """Check if notifications should be bundled for this user/channel"""
        prefs = self.get_preferences(user_id)
        return bool(prefs.get('bundle_notifications', 0))

    def _add_to_bundle(
        self,
        notification_id: int,
        user_id: str,
        channel: str,
        title: str
    ) -> None:
        """Add notification to an existing or new bundle"""
        with transaction() as conn:
            # Check for recent bundle
            cursor = conn.execute('''
                SELECT bundle_id FROM bundled_notifications
                WHERE user_id = ? AND channel = ?
                AND datetime(created_at) > datetime('now', '-5 minutes')
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id, channel))

            row = cursor.fetchone()

            if row:
                bundle_id = row[0]
                # Update existing bundle
                conn.execute('''
                    UPDATE bundled_notifications
                    SET notification_count = notification_count + 1
                    WHERE bundle_id = ?
                ''', (bundle_id,))
            else:
                # Create new bundle
                cursor = conn.execute('''
                    INSERT INTO bundled_notifications (
                        user_id, channel, bundle_title, notification_count,
                        expires_at
                    ) VALUES (?, ?, ?, 1, datetime('now', '+7 days'))
                ''', (user_id, channel, f"{channel.title()} notifications"))
                bundle_id = cursor.lastrowid

            # Link notification to bundle
            conn.execute('''
                INSERT INTO notification_bundle_items (bundle_id, notification_id)
                VALUES (?, ?)
            ''', (bundle_id, notification_id))

    def _deliver_notification(
        self,
        notification_id: int,
        user_id: str,
        channel: str,
        priority: str
    ) -> None:
        """Deliver notification through appropriate channels"""
        # Get channel settings
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT push_enabled, email_enabled, sms_enabled, min_priority
                FROM notification_channels
                WHERE user_id = ? AND channel = ? AND enabled = 1
            ''', (user_id, channel))

            row = cursor.fetchone()
            if not row:
                return

            push_enabled, email_enabled, sms_enabled, min_priority = row

            # Check if priority meets minimum
            priority_levels = ['low', 'medium', 'high', 'urgent']
            if priority_levels.index(priority) < priority_levels.index(min_priority):
                return

            # Log delivery attempts
            with transaction() as conn_trans:
                if push_enabled:
                    conn_trans.execute('''
                        INSERT INTO notification_history (
                            notification_id, delivery_method, status
                        ) VALUES (?, 'push', 'sent')
                    ''', (notification_id,))

                if email_enabled:
                    conn_trans.execute('''
                        INSERT INTO notification_history (
                            notification_id, delivery_method, status
                        ) VALUES (?, 'email', 'queued')
                    ''', (notification_id,))

                if sms_enabled and priority in ['high', 'urgent']:
                    conn_trans.execute('''
                        INSERT INTO notification_history (
                            notification_id, delivery_method, status
                        ) VALUES (?, 'sms', 'queued')
                    ''', (notification_id,))

    def generate_daily_digest(self, user_id: str) -> Optional[int]:
        """Generate daily digest for user"""
        today = datetime.now().date()

        # Get unread notifications from last 24 hours
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM notifications
                WHERE user_id = ? AND is_read = 0
                AND date(created_at) = ?
            ''', (user_id, today))

            count = cursor.fetchone()[0]

            if count == 0:
                return None

        # Create digest record
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO digests (user_id, digest_date, notification_count, sent_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, today, count))

            digest_id = cursor.lastrowid

            log_activity(
                'create', 'digest',
                digest_id=digest_id,
                details={'user_id': user_id, 'count': count}
            )

            return digest_id

    # ==================== Statistics & Analytics ====================

    def get_notification_stats(self, user_id: str) -> Dict[str, Any]:
        """Get notification statistics for user"""
        with get_connection() as conn:
            # Total counts
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread,
                    SUM(CASE WHEN priority = 'urgent' THEN 1 ELSE 0 END) as urgent
                FROM notifications
                WHERE user_id = ? AND is_archived = 0
            ''', (user_id,))

            total, unread, urgent = cursor.fetchone()

            # By channel
            cursor = conn.execute('''
                SELECT channel, COUNT(*) as count
                FROM notifications
                WHERE user_id = ? AND is_archived = 0
                GROUP BY channel
            ''', (user_id,))

            by_channel = {row[0]: row[1] for row in cursor.fetchall()}

            # Recent activity
            cursor = conn.execute('''
                SELECT COUNT(*) FROM notifications
                WHERE user_id = ? AND date(created_at) = date('now')
            ''', (user_id,))

            today = cursor.fetchone()[0]

            return {
                'total': total or 0,
                'unread': unread or 0,
                'urgent': urgent or 0,
                'today': today or 0,
                'by_channel': by_channel
            }
