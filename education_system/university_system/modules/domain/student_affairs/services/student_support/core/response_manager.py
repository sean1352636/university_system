"""
Ticket response handling for Student Support.
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

from education_system.university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.university_system.infrastructure.email.email_manager import send_email
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.university_system.infrastructure.logging.log_config import get_log_file

from education_system.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.university_system.modules.domain.student_affairs.services.student_support import auth as _auth_mod
from education_system.university_system.modules.domain.student_affairs.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions
from education_system.university_system.modules.domain.student_affairs.services.student_support.utils.audit import audit_action

logger = logging.getLogger(__name__)

def add_ticket_response(ticket_id, response_text, template_id=None, is_internal=False, attachments=None):
    """Add a response to a support ticket with enhanced features."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to respond to a ticket")

    if not response_text:
        raise ValueError("Response text is required")

    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()

        # Check if ticket exists and get details
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()

        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} not found")

        # Check permissions
        _check_response_permission(ticket, _auth_mod.auth.current_user)

        # Process template if provided
        if template_id:
            response_text = _apply_response_template(template_id, ticket_id, response_text, cursor)

        # Add the response
        response_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO ticket_responses (
            ticket_id, responder_id, responder_role, response_text,
            response_datetime, is_internal, template_used
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id, _auth_mod.auth.current_user['id'], _auth_mod.auth.current_user['role'],
            response_text, response_time, is_internal, template_id
        ))

        # Handle attachments
        if attachments:
            _process_attachments(ticket_id, attachments, cursor)

        # Update ticket
        _update_ticket_on_response(ticket_id, ticket, response_time, cursor)

        # Update template usage count
        if template_id:
            cursor.execute('UPDATE response_templates SET usage_count = usage_count + 1 WHERE template_id = ?', (template_id,))

        # Commit main transaction BEFORE calling helper methods
        # This prevents database locks from nested connections
        conn.commit()

        # Store values needed for notifications (ticket data no longer accessible after close)
        student_id = ticket[1]

        # Create notifications (now safe - main transaction is complete)
        if not is_internal:
            _create_response_notifications(ticket_id, student_id, _auth_mod.auth.current_user)

        logger.info(f"Added response to ticket #{ticket_id} by {_auth_mod.auth.current_user['username']}")
        return True

    except Exception as e:
        logger.error(f"Error adding ticket response: {e}")
        raise
    finally:
        if conn:
            conn.close()

def _check_response_permission(ticket, current_user):
    """Check if user can respond to ticket"""
    if current_user['role'] == 'student':
        # Verify it's their own ticket
        conn_main = None
        try:
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (current_user['id'],))
            result = cursor_main.fetchone()
        finally:
            if conn_main:
                conn_main.close()

        if not result or result[0] != ticket[1]:  # ticket[1] is student_id
            raise PermissionError("You can only respond to your own support tickets")

def _apply_response_template(template_id, ticket_id, response_text, cursor):
    """Apply response template with variable substitution"""
    cursor.execute('SELECT content, variables FROM response_templates WHERE template_id = ? AND is_active = 1', (template_id,))
    template_data = cursor.fetchone()

    if not template_data:
        return response_text

    template_content, variables_json = template_data
    variables = json.loads(variables_json or '[]')

    # Replace variables
    replacements = {
        'TICKET_ID': str(ticket_id),
        'USER_NAME': _auth_mod.auth.current_user.get('username', 'User'),
        'CURRENT_DATE': datetime.datetime.now().strftime('%Y-%m-%d'),
        'CURRENT_TIME': datetime.datetime.now().strftime('%H:%M:%S')
    }

    for var in variables:
        if var in replacements:
            template_content = template_content.replace(f'[{var}]', replacements[var])

    # Combine template with additional text
    if response_text and response_text != template_content:
        return f"{template_content}\n\n{response_text}"

    return template_content

def _update_ticket_on_response(ticket_id, ticket, response_time, cursor):
    """Update ticket status and metadata when response is added"""
    new_status = ticket[6]  # Current status
    assigned_to = ticket[9]  # Current assigned_to

    # Auto-update status based on responder role
    if ticket[6] == 'Open' and _auth_mod.auth.current_user['role'] in ('staff', 'admin'):
        new_status = 'In Progress'
        if not assigned_to:
            assigned_to = _auth_mod.auth.current_user['username']

    cursor.execute('''
    UPDATE support_tickets
    SET last_updated_datetime = ?, status = ?, assigned_to = ?
    WHERE ticket_id = ?
    ''', (response_time, new_status, assigned_to, ticket_id))

def _create_response_notifications(ticket_id, student_id, responder):
    """Create notifications for ticket responses"""
    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if responder['role'] in ('staff', 'admin'):
            # Notify student of staff response (only if student_id exists)
            if student_id:
                cursor.execute('''
                INSERT INTO notifications (
                    user_id, title, message, notification_type,
                    related_ticket_id, created_datetime
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, 'Support Response Received',
                    f'Your support ticket #{ticket_id} has received a new response.',
                    NotificationType.EMAIL.value, ticket_id, timestamp
                ))
            else:
                logger.warning(f"Cannot create notification for ticket #{ticket_id}: student_id is NULL")
        else:
            # Notify assigned staff of student response
            # Get assigned staff
            cursor.execute('SELECT assigned_to FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            result = cursor.fetchone()
            if result and result[0]:
                cursor.execute('''
                INSERT INTO notifications (
                    user_id, title, message, notification_type,
                    related_ticket_id, created_datetime
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    result[0], 'Student Response Received',
                    f'Ticket #{ticket_id} has received a new response from the student.',
                    NotificationType.IN_APP.value, ticket_id, timestamp
                ))
            else:
                logger.warning(f"Cannot create notification for ticket #{ticket_id}: no assigned staff")

        conn.commit()

    except Exception as e:
        logger.error(f"Error creating response notifications: {e}")
    finally:
        if conn:
            conn.close()

@audit_action("update_status")

def add_response_enhanced(support, ticket_id):
    """Add response with template support"""
    try:
        # Get response templates
        templates = support.get_response_templates()

        if templates and _auth_mod.auth.current_user['role'] in ('staff', 'admin'):
            print("\n📝 Response Templates:")
            print("0. Write custom response")
            for i, template in enumerate(templates[:10], 1):  # Show first 10
                print(f"{i}. {template['name']}")

            template_choice = input("\nSelect template (0 for custom): ").strip()

            if template_choice.isdigit() and 1 <= int(template_choice) <= len(templates):
                template = templates[int(template_choice) - 1]
                response_text = template['content']
                print(f"\nUsing template: {template['name']}")
                print(f"Template content:\n{response_text}")

                additional = input("\nAdditional text (optional): ").strip()
                if additional:
                    response_text += f"\n\n{additional}"

                template_id = template['template_id']
            else:
                response_text = input("\nEnter your response: ").strip()
                template_id = None
        else:
            response_text = input("\nEnter your response: ").strip()
            template_id = None

        if not response_text:
            print("❌ Response cannot be empty.")
            return

        # Internal note option for staff
        is_internal = False
        if _auth_mod.auth.current_user['role'] in ('staff', 'admin'):
            is_internal = input("Internal note (visible only to staff)? (y/n): ").lower() == 'y'

        # Add response
        support.add_ticket_response(ticket_id, response_text, template_id, is_internal)
        print("✅ Response added successfully!")

    except Exception as e:
        print(f"❌ Error adding response: {e}")
