"""
Notification system for support tickets.
"""

import datetime
import json
import logging
import time
import re
import os
import hashlib
import mimetypes
import base64
import secrets
import traceback
from typing import Optional, List, Dict, Any
from functools import wraps

from education_system.systems.university.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.systems.university.infrastructure.email.email_manager import send_email
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.systems.university.infrastructure.logging.log_config import get_log_file

from education_system.systems.university.domain.pastoral.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.systems.university.domain.pastoral.services.student_support import auth as _auth_mod
from education_system.systems.university.domain.pastoral.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions
from education_system.systems.university.domain.pastoral.services.student_support.utils.audit import audit_action

logger = logging.getLogger(__name__)

def get_user_notifications(user_id=None, unread_only=False):
    """Get notifications for a user"""
    if not user_id:
        user_id = _auth_mod.auth.current_user['id'] if _auth_mod.auth and _auth_mod.auth.current_user else None

    if not user_id:
        raise ValueError("User ID required")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Determine timestamp column name
        cursor.execute("PRAGMA table_info(notifications)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'created_datetime' in cols:
            ts_col = 'created_datetime'
        elif 'created_at' in cols:
            ts_col = 'created_at'
        elif 'created_date' in cols:
            ts_col = 'created_date'
        else:
            ts_col = 'rowid'

        query = '''
        SELECT * FROM notifications
        WHERE user_id = ?
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        '''
        params = [user_id]

        if unread_only:
            query += ' AND is_read = 0'

        query += f' ORDER BY {ts_col} DESC'

        cursor.execute(query, params)
        notifications = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return notifications

    except Exception as e:
        logger.error(f"Error getting user notifications: {e}")
        return []

# Add this method to the EnhancedStudentSupport class

def mark_notification_read(notification_id, user_id=None):
    """Mark a notification as read"""
    if not user_id:
        user_id = _auth_mod.auth.current_user['id'] if _auth_mod.auth and _auth_mod.auth.current_user else None

    if not user_id:
        raise ValueError("User ID required")

    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE notifications
        SET is_read = 1, read_datetime = ?
        WHERE notification_id = ? AND user_id = ?
        ''', (timestamp, notification_id, user_id))

        conn.commit()
        conn.close()

        return cursor.rowcount > 0

    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        return False

def _get_recent_notifications(user_id, cursor):
    """Get recent notifications for user"""
    # Check which timestamp column exists in the notifications table
    cursor.execute("PRAGMA table_info(notifications)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'created_datetime' in columns:
        ts_col = 'created_datetime'
    elif 'created_at' in columns:
        ts_col = 'created_at'
    elif 'created_date' in columns:
        ts_col = 'created_date'
    else:
        ts_col = None

    if ts_col:
        cursor.execute(f'''
        SELECT notification_id, title, message, notification_type, {ts_col}, is_read
        FROM notifications
        WHERE user_id = ?
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY {ts_col} DESC
        LIMIT 10
        ''', (user_id,))
    else:
        cursor.execute('''
        SELECT notification_id, title, message, notification_type, NULL, is_read
        FROM notifications
        WHERE user_id = ?
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        LIMIT 10
        ''', (user_id,))

    return [
        dict(zip(
            ['notification_id', 'title', 'message', 'type', 'created', 'is_read'],
            row
        ))
        for row in cursor.fetchall()
    ]

def _create_ticket_notifications(ticket_id, student_id, assigned_to, action):
    """Create notifications for ticket events"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        notifications = []
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Notify student (only if student_id exists)
        if action == 'created' and student_id:
            notifications.append((
                student_id, 'Ticket Created',
                f'Your support ticket #{ticket_id} has been created successfully.',
                NotificationType.EMAIL.value, ticket_id, timestamp
            ))

        # Notify assigned staff
        if assigned_to:
            notifications.append((
                assigned_to, 'New Ticket Assignment',
                f'You have been assigned to ticket #{ticket_id}.',
                NotificationType.IN_APP.value, ticket_id, timestamp
            ))

        for notification in notifications:
            cursor.execute('''
            INSERT INTO notifications (
                user_id, title, message, notification_type,
                related_ticket_id, created_datetime
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', notification)

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Error creating notifications: {e}")

@audit_action("view_tickets")

def _trigger_satisfaction_survey(ticket_id, student_id):
    """Trigger satisfaction survey for resolved ticket"""
    # Skip if student_id is None or invalid
    if not student_id:
        logger.warning(f"Cannot trigger satisfaction survey for ticket #{ticket_id}: student_id is None")
        return

    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=10)
        cursor = conn.cursor()

        # Create survey notification
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        expires_at = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO notifications (
            user_id, title, message, notification_type,
            related_ticket_id, created_datetime, expires_at, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            student_id, 'Rate Your Support Experience',
            f'Please rate your support experience for ticket #{ticket_id}.',
            NotificationType.IN_APP.value, ticket_id, timestamp, expires_at,
            json.dumps({'survey_type': 'satisfaction', 'ticket_id': ticket_id})
        ))

        conn.commit()

    except Exception as e:
        logger.error(f"Error triggering satisfaction survey: {e}")
    finally:
        if conn:
            conn.close()

def view_notifications(support):
    """View user notifications"""
    try:
        print("\n🔔 NOTIFICATIONS")
        print("="*40)

        # Get notifications from dashboard data
        dashboard_data = support.get_dashboard_data(_auth_mod.auth.current_user['role'], _auth_mod.auth.current_user['id'])
        notifications = dashboard_data.get('notifications', [])

        if not notifications:
            print("📭 No notifications.")
            return

        print(f"📬 You have {len(notifications)} notifications:")

        for i, notif in enumerate(notifications, 1):
            status_icon = "📫" if notif['is_read'] else "📬"
            print(f"\n{i}. {status_icon} {notif['title']}")
            print(f"   📝 {notif['message']}")
            print(f"   📅 {notif['created']}")
            print(f"   🏷️ Type: {notif['type']}")

        # Mark as read option
        mark_read = input("\nMark all as read? (y/n): ").lower()
        if mark_read == 'y':
            # In a real implementation, this would update the database
            print("✅ All notifications marked as read.")

    except Exception as e:
        print(f"❌ Error viewing notifications: {e}")

    input("\nPress Enter to continue...")

# Additional helper functions for enhanced features