"""Email maintenance, fixes, and diagnostic utilities."""

from __future__ import annotations

import re
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.email.config import config
from education_system.post_18.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.post_18.university_system.core.logs import handle_exception, log_event
from education_system.post_18.university_system.infrastructure.email.templates import render_template


def fix_inbox_display_issue():
    """Fix the issue where sent emails don't appear in recipient inboxes"""
    from education_system.post_18.university_system.infrastructure.email.email_service.core import get_appropriate_sender_id

    def _fix_missing_inbox_messages(cursor):
        # Find stored emails that don't have corresponding inbox messages
        cursor.execute('''
        SELECT se.id, se.recipient_email, se.subject, se.body,
               se.sender_email, se.sender_name, se.created_date,
               se.attachment_paths
        FROM stored_emails se
        LEFT JOIN users u ON se.recipient_email = u.email
        LEFT JOIN messages m ON (m.recipient_id = u.id AND m.subject = se.subject AND m.sent_at = se.created_date)
        WHERE u.id IS NOT NULL AND m.id IS NULL
        ORDER BY se.created_date DESC
        ''')

        missing_messages = cursor.fetchall()
        fixed_count = 0

        print(_t("email_service.found_missing", count=len(missing_messages)))

        for email_data in missing_messages:
            se_id, recipient_email, subject, body, sender_email, sender_name, created_date, attachments = email_data

            try:
                # Get recipient ID
                cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                recipient_result = cursor.fetchone()

                if recipient_result:
                    recipient_id = recipient_result[0]

                    # Get appropriate sender ID
                    sender_id = get_appropriate_sender_id(cursor, sender_email, sender_name, created_date)

                    # Create the inbox message
                    cursor.execute('''
                    INSERT INTO messages (
                        sender_id, recipient_id, subject, message, content,
                        attachment_path, is_read, sent_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    ''', (sender_id, recipient_id, subject, body, body, attachments, created_date))

                    fixed_count += 1
                    print(_t("email_service.added_to_inbox", subject=subject[:50], recipient=recipient_email))

            except sqlite3.Error as e:
                print(_t("email_service.failed_fix_message", recipient=recipient_email, error=str(e)))

        return fixed_count

    try:
        count = execute_db_operation(_fix_missing_inbox_messages)
        print("\n" + _t("email_service.fixed_inbox_messages", count=count))
        return count
    except sqlite3.Error as e:
        print(_t("email_service.db_error_fixing", error=str(e)))
        return 0

def fix_existing_email_senders():
    """Fix existing emails that show 'system' as sender when they should show actual users"""

    def _fix_senders(cursor):
        # Find messages from generic 'system' users that could be attributed to real users
        cursor.execute('''
        SELECT m.id, m.subject, m.sent_at, m.sender_id, u.username as current_sender,
               se.sender_name, se.sender_email
        FROM messages m
        LEFT JOIN users u ON m.sender_id = u.id
        LEFT JOIN stored_emails se ON (
            se.subject = m.subject AND
            se.created_date = m.sent_at
        )
        WHERE u.username IN ('system', 'system_system', 'system_university')
        AND se.sender_name IS NOT NULL
        AND se.sender_name NOT IN ('System', 'University System', 'system')
        ORDER BY m.sent_at DESC
        LIMIT 100
        ''')

        messages_to_fix = cursor.fetchall()
        fixed_count = 0

        print(_t("email_service.found_messages_fix", count=len(messages_to_fix)))

        for msg_data in messages_to_fix:
            msg_id, subject, sent_at, current_sender_id, current_sender, sender_name, sender_email = msg_data

            # Look for a real user with this email
            cursor.execute("SELECT id, username FROM users WHERE email = ? AND role != 'admin'", (sender_email,))
            real_user = cursor.fetchone()

            if real_user and real_user[0] != current_sender_id:
                try:
                    # Update message to use real user as sender
                    cursor.execute("UPDATE messages SET sender_id = ? WHERE id = ?", (real_user[0], msg_id))
                    print(_t("email_service.fixed_message", id=msg_id, subject=subject[:50], new_sender=real_user[1], old_sender=current_sender))
                    fixed_count += 1
                except Exception as e:
                    print(_t("email_service.failed_fix", id=msg_id, error=str(e)))

        return fixed_count

    try:
        count = execute_db_operation(_fix_senders)
        print("\n" + _t("email_service.fixed_sender_count", count=count))
        return count
    except Exception as e:
        print(_t("email_service.error_fixing_senders", error=str(e)))
        return 0

def test_sender_attribution(auth_instance=None):
    """Test that emails show proper sender names

    Args:
        auth_instance: Optional authentication instance to use. If not provided, uses module-level auth.
    """
    from education_system.post_18.university_system.infrastructure.email.email_service.core import (
        auth, send_email_as_user, send_email_as_system,
    )

    # Use provided auth instance or fall back to module-level
    _auth = auth_instance if auth_instance else auth

    if not _auth:
        print(_t("email_service.auth_not_init"))
        return False

    if not hasattr(_auth, 'current_user') or not _auth.current_user:
        print(_t("email_service.not_logged_in"))
        return False

    current_user = _auth.current_user
    print(_t("email_service.testing_attribution", username=current_user['username'], email=current_user.get('email', 'no email')))

    # Test 1: Send email as current user
    print("\n1. " + _t("email_service.test_as_user"))
    test_email = current_user.get('email', 'test@example.com')

    result1 = send_email_as_user(
        test_email,
        f"Test Sender Attribution - From {current_user['username']}",
        f"This email should show as coming from {current_user['username']}, not 'system'.",
        current_user['id']
    )

    # Test 2: Send email as named system
    print("2. " + _t("email_service.test_as_system"))
    result2 = send_email_as_system(
        test_email,
        "Test System Email - Library Services",
        "This email should show as coming from 'Library Services', not generic 'system'.",
        "Library Services"
    )

    if result1 and result2:
        print(_t("email_service.test_emails_sent"))

        # Check recent messages
        from education_system.post_18.university_system.infrastructure.email.admin import CommunicationDashboard
        dashboard = CommunicationDashboard(auth=_auth)
        inbox = dashboard.get_inbox(limit=5)

        print("\n" + _t("email_service.recent_inbox_messages") + ":")
        for i, msg in enumerate(inbox.get('messages', [])[:5], 1):
            print(f"  {i}. {_t('email_service.from')}: '{msg['sender']}' - {_t('email_service.subject')}: '{msg['subject'][:50]}...'")

        return True
    else:
        print(_t("email_service.failed_test_emails"))
        return False
