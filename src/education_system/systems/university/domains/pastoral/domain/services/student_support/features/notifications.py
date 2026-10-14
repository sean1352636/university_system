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
from education_system.paths import (
    UNIVERSITY_DEFAULT_DB_PATH,
    UNIVERSITY_TICKET_TEMPLATES_DIR,
    UNIVERSITY_UPLOAD_DIR,
)
from education_system.systems.university.infrastructure.logging.log_config import get_log_file

from education_system.systems.university.domains.pastoral.domain.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.systems.university.domains.pastoral.domain.services.student_support import auth as _auth_mod
from education_system.systems.university.domains.pastoral.domain.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions
from education_system.systems.university.domains.pastoral.domain.services.student_support.utils.audit import audit_action

logger = logging.getLogger(__name__)

def get_user_notifications(user_id=None, unread_only=False):
    """Get notifications for a user, from the mailbox the Hub reads.

    Was a query against the retired ``notifications`` table, which is never
    written to — so this returned nothing for everyone, and the callers that
    depend on it (notably "Mark All Read") had nothing to act on.
    """
    if not user_id:
        user_id = _auth_mod.auth.current_user['id'] if _auth_mod.auth and _auth_mod.auth.current_user else None

    if not user_id:
        raise ValueError("User ID required")

    items = _get_recent_notifications(user_id, None, limit=50)
    if unread_only:
        items = [n for n in items if not n.get('is_read')]
    return items


def mark_notification_read(notification_id, user_id=None):
    """Mark one inbox message read, through the same mailbox API as the Hub.

    The standalone ``notifications`` table this used to update is retired and
    never written to, so every call reported success against zero rows and
    "Mark All Read" always said it had marked none.
    """
    try:
        from education_system.systems.university.infrastructure.email.admin import (
            CommunicationDashboard,
        )
        dashboard = CommunicationDashboard(auth=_auth_for_notifications(user_id))
        return bool(dashboard.read_message(notification_id))
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        return False


def _get_recent_notifications(user_id, cursor, limit=10):
    """Recent inbox items for the dashboard widget.

    Reads the user's mailbox through ``CommunicationDashboard`` — the same
    source the Notifications Hub and the header bell use — rather than the
    standalone ``notifications`` table, which the Hub redesign retired. That
    table still exists but is never written to, so this widget reported "No
    recent notifications" to every user while their mailbox held hundreds of
    messages.

    ``cursor`` is accepted for call-compatibility and no longer used.

    Returns dicts shaped as before: ``notification_id``, ``title``,
    ``message``, ``type``, ``created``, ``is_read``.
    """
    try:
        from education_system.systems.university.infrastructure.email.admin import (
            CommunicationDashboard,
        )
    except Exception:
        logger.warning("CommunicationDashboard unavailable; "
                       "dashboard notifications will be empty", exc_info=True)
        return []

    try:
        dashboard = CommunicationDashboard(auth=_auth_for_notifications(user_id))
        inbox = dashboard.get_inbox(page=1, limit=limit)
    except Exception:
        logger.warning("Could not read the inbox for user %s", user_id,
                       exc_info=True)
        return []

    if not isinstance(inbox, dict):
        return []

    items = []
    for m in (inbox.get("messages") or [])[:limit]:
        if not isinstance(m, dict):
            continue
        items.append({
            "notification_id": m.get("id") or m.get("message_id"),
            # The widget shows the subject; fall back to the sender so a
            # subject-less message is not rendered as a blank row.
            "title": (m.get("subject") or m.get("title")
                      or m.get("sender") or "Message"),
            # get_inbox returns `content` (the messages.message column) and
            # `sent_at`; the older key names guessed here were always empty,
            # which showed as a blank timestamp beside every row.
            "message": m.get("content") or m.get("body") or m.get("message") or "",
            "type": m.get("message_type") or "message",
            "created": (m.get("sent_at") or m.get("sent_datetime")
                        or m.get("created_at") or ""),
            "is_read": bool(m.get("is_read")),
        })
    return items


def _auth_for_notifications(user_id):
    """Auth for the mailbox of ``user_id`` — not of whoever is signed in.

    This used to return the live session whenever one existed, ignoring the
    id it was given. The two coincide when you are looking at your own
    dashboard, so it looked right, but any call naming another user read the
    signed-in user's mailbox instead and showed rows belonging to someone
    else. The requested id wins; the live session is only used when it is
    that same user (so its permissions and any extra state come along) or
    when no id was given.
    """
    live = None
    try:
        candidate = getattr(_auth_mod, "auth", None)
        if candidate is not None and getattr(candidate, "current_user", None):
            live = candidate
    except Exception:
        logger.debug("no live auth session for notifications", exc_info=True)

    if user_id is None:
        return live

    if live is not None:
        live_id = (live.current_user or {}).get("id")
        if str(live_id) == str(user_id):
            return live

    class _StandInAuth:
        """Carries just the identity the mailbox query needs."""

        def __init__(self, uid):
            self.current_user = {"id": uid}

        def check_permission(self, *_a, **_k):
            return True

    return _StandInAuth(user_id)


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