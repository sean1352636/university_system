"""Core email sending engine and sender resolution."""

from __future__ import annotations

import re
import smtplib
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from education_system.university_system.core.i18n import get_text as _t, init_i18n
init_i18n()

from education_system.university_system.infrastructure.email.config import config
from education_system.university_system.infrastructure.email.email_db_utilities import _ensure_db_ready, execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event
from education_system.university_system.infrastructure.email.reports import log_email_metrics
from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp
# Import auth access - use function to get current auth instance
try:
    from education_system.university_system.infrastructure.shared_context import get_auth as _get_shared_auth
    HAS_SHARED_AUTH = True
except ImportError:
    HAS_SHARED_AUTH = False
    _get_shared_auth = None

# Fallback to email state auth
from education_system.university_system.infrastructure.email.state import auth_proxy as _state_auth

from education_system.university_system.infrastructure.email.templates import (
    render_template,
)
from education_system.university_system.infrastructure.exceptions import (
    EmailError,
    EmailDeliveryError,
    TemplateError,
    AttachmentError,
    InvalidInputError,
)

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        mask_sensitive_data,
    )
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
    def mask_sensitive_data(data, fields=None):
        return data


def _get_current_auth():
    """Get the current auth instance with proper fallback"""
    if HAS_SHARED_AUTH:
        try:
            auth = _get_shared_auth()
            if hasattr(auth, 'current_user') and auth.current_user:
                return auth
        except (AttributeError, RuntimeError) as e:
            log_event('debug', f"Auth retrieval fallback triggered: {e}")
    # Fallback to state auth
    return _state_auth if _state_auth else None

# For backward compatibility, expose as 'auth' variable
# But it should be called via _get_current_auth() in critical paths
auth = _state_auth


@handle_exception
def safe_log_email(cursor, recipient, subject, sent_date, status, related_to=None, student_id=None,
                  sender_email=None, sender_name=None, cc_recipients=None, bcc_recipients=None,
                  attachment_info=None, template_name=None, template_vars=None):
    """Safely log email to email_log table with fallback for missing columns"""
    try:
        # Try to insert with all columns
        cursor.execute('''
        INSERT INTO email_log
        (recipient, subject, sent_date, status, related_to, student_id, sender_email,
         sender_name, cc_recipients, bcc_recipients, attachment_info, template_name, template_vars)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            recipient, subject, sent_date, status, related_to, student_id,
            sender_email, sender_name, cc_recipients, bcc_recipients,
            attachment_info, template_name, template_vars
        ))
        return True
    except sqlite3.OperationalError as e:
        # Schema mismatch - columns may not exist, try fallback
        log_event('warning', f"Could not log with extended columns (schema mismatch): {e}")
        try:
            # Fallback to basic columns
            cursor.execute('''
            INSERT INTO email_log
            (recipient, subject, sent_date, status, related_to, student_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipient, subject, sent_date, status, related_to, student_id))
            return True
        except sqlite3.Error as e2:
            log_event('error', f"Database error logging email: {e2}")
            return False

@handle_exception
def send_email(recipient_email, subject, body, cc=None, bcc=None, attachments=None):
    """
    Store email in DB or send via SMTP based on mode with enhanced logging.

    Args:
        recipient_email: Email address of recipient
        subject: Email subject
        body: Email body
        cc: CC recipients (optional)
        bcc: BCC recipients (optional)
        attachments: Email attachments (optional)

    Returns:
        bool: True if email was processed successfully, False otherwise

    Raises:
        InvalidInputError: If required parameters are missing or invalid
        EmailDeliveryError: If email delivery fails
    """
    _ensure_db_ready()

    # Validate required parameters
    if not recipient_email or not isinstance(recipient_email, str):
        raise InvalidInputError(
            "Recipient email address is required",
            code="EMAIL_MISSING_RECIPIENT",
            details={'recipient': recipient_email}
        )

    if not subject or not isinstance(subject, str):
        raise InvalidInputError(
            "Email subject is required",
            code="EMAIL_MISSING_SUBJECT"
        )

    if body is None:  # Allow empty string but not None
        raise InvalidInputError(
            "Email body is required",
            code="EMAIL_MISSING_BODY"
        )

    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, recipient_email):
        raise InvalidInputError(
            f"Invalid email format: {recipient_email}",
            code="EMAIL_INVALID_FORMAT",
            details={'email': recipient_email}
        )

    # Log the email attempt
    if auth and auth.current_user:
        log_event('info', f"Initiating email to {recipient_email}: {subject[:50]}...")

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cc_str = ", ".join(cc) if isinstance(cc, list) else cc if cc else None
    bcc_str = ", ".join(bcc) if isinstance(bcc, list) else bcc if bcc else None
    attachment_str = ", ".join(attachments) if attachments else None

    if config.get('database_only_mode', True):
        result = send_email_db_only(
            recipient_email, subject, body, cc_str, bcc_str, attachment_str, current_time
        )
    else:
        result = send_email_via_smtp(
            recipient_email, subject, body, cc_str, bcc_str, attachment_str, current_time
        )

    # Enhanced logging of result
    if result:
        log_event('info', f"Email processed successfully to {recipient_email}")
        # Log metrics
        log_email_metrics('sent')
    else:
        log_event('error', f"Failed to process email to {recipient_email}")
        log_email_metrics('failed')

    return result

def send_email_db_only(recipient_email, subject, body, cc, bcc, attachments, current_time):
    _ensure_db_ready()
    """Store email in DB and ALWAYS create an inbox message for a valid user.
       Robust against sender resolution failures and ensures commit.
    """
    def _store_email(cursor):
        # Use logged-in user's email/name if available, otherwise use config defaults
        current_auth = _get_current_auth()
        if current_auth and hasattr(current_auth, 'current_user') and current_auth.current_user:
            # Look up user by username in the university DB (the id may come
            # from the shared auth DB and not match the local users table).
            username = current_auth.current_user.get('username')
            user_data = None
            if username:
                cursor.execute(
                    "SELECT email, first_name, last_name FROM users WHERE username = ?",
                    (username,),
                )
                user_data = cursor.fetchone()
            if user_data:
                sender_email = user_data[0]
                first_name = (user_data[1] or '').strip()
                last_name = (user_data[2] or '').strip()
                if first_name or last_name:
                    sender_name = f"{first_name} {last_name}".strip()
                else:
                    sender_name = current_auth.current_user.get('username', 'University System')
            else:
                # User not in university DB — use config defaults
                sender_email = config.get('sender_email', "noreply@university.edu")
                sender_name = current_auth.current_user.get(
                    'display_name',
                    config.get('sender_name', "University System"),
                )
        else:
            sender_email = config.get('sender_email', "noreply@university.edu")
            sender_name  = config.get('sender_name',  "University System")

        # 1) Store in stored_emails (admin/storage view)
        cursor.execute('''
            INSERT INTO stored_emails
                (recipient_email, subject, body, sender_email, sender_name,
                 cc_recipients, bcc_recipients, attachment_paths, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (recipient_email, subject, body, sender_email, sender_name,
              cc, bcc, attachments, current_time))

        # 2) If recipient is a real user, create an inbox message
        cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
        user_row = cursor.fetchone()

        if user_row:
            recipient_id = user_row[0]

            # Resolve a sender_id with strong fallbacks
            sender_id = None
            try:
                sender_id = get_appropriate_sender_id(cursor, sender_email, sender_name, current_time)
            except (sqlite3.Error, ValueError, KeyError) as e:
                log_event('warning', f"get_appropriate_sender_id failed, falling back: {e}")

            if not sender_id:
                # Fallback: create/find a system user explicitly
                try:
                    system_username = generate_system_username(sender_name, sender_email)
                    cursor.execute("SELECT id FROM users WHERE username = ? AND role = 'admin'", (system_username,))
                    su = cursor.fetchone()
                    if su:
                        sender_id = su[0]
                    else:
                        parts = sender_name.split(' ', 1)
                        first = parts[0] if parts else sender_name
                        last  = parts[1] if len(parts) > 1 else ''
                        cursor.execute('''
                            INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (system_username, first, last, sender_email, 'admin', current_time, current_time))
                        sender_id = cursor.lastrowid
                except sqlite3.Error as e:
                    log_event('warning', f"System sender fallback failed (database error): {e}")

            if not sender_id:
                # Absolute last resort: still create the message so it shows up.
                sender_id = recipient_id

            # Create the inbox message (what the UI reads)
            cursor.execute('''
                INSERT INTO messages
                    (sender_id, recipient_id, subject, message, content, attachment_path, is_read, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            ''', (sender_id, recipient_id, subject, body, body, attachments, current_time))
        else:
            log_event('info', f"Email stored for {recipient_email}, but no matching user account found.")

        # 3) Log the email event (extended columns if present)
        try:
            cursor.execute('''
                INSERT INTO email_log
                    (recipient, subject, sent_date, status, sender_email, sender_name,
                     cc_recipients, bcc_recipients, attachment_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (recipient_email, subject, current_time, 'stored', sender_email, sender_name,
                  cc, bcc, attachments))
        except sqlite3.OperationalError as e:
            # Fallback to minimal log if extended columns aren't available (schema mismatch)
            log_event('warning', f"Extended email_log insert failed (schema mismatch), falling back: {e}")
            cursor.execute('''
                INSERT INTO email_log (recipient, subject, sent_date, status, sender_email)
                VALUES (?, ?, ?, ?, ?)
            ''', (recipient_email, subject, current_time, 'stored', sender_email))

        # Make sure everything is persisted
        try:
            cursor.connection.commit()
        except sqlite3.Error as e:
            log_event('warning', f"Explicit commit failed (connection may auto-commit on close): {e}")

        return True

    try:
        return execute_db_operation(_store_email)
    except sqlite3.Error as e:
        log_event('error', f"Database error storing email: {e}")
        return False
    except EmailError as e:
        log_event('error', f"Email error storing email: {e}")
        return False

def generate_system_username(sender_name, sender_email):
    """Generate a descriptive username for system users"""

    # Clean sender name for username (remove spaces, special chars)
    clean_name = re.sub(r'[^\w]', '', sender_name.lower())

    # If sender_name is generic, use email local part
    generic_names = ['system', 'university', 'noreply', 'admin']
    if clean_name in generic_names or len(clean_name) < 3:
        email_local = sender_email.split('@')[0]
        clean_name = re.sub(r'[^\w]', '', email_local.lower())

    # Ensure it's not too long
    if len(clean_name) > 20:
        clean_name = clean_name[:20]

    return f"system_{clean_name}"

@handle_exception
def send_email_as_user(recipient_email, subject, body, sender_user_id=None, cc=None, bcc=None, attachments=None):
    """Send an email with a specific user as the sender"""

    # If sender_user_id is provided, temporarily set that as the context
    original_user = None
    if sender_user_id and auth:
        # Store original user
        original_user = auth.current_user

        # Get the sender user info
        def _get_sender_info(cursor):
            cursor.execute("SELECT id, username, email, first_name, last_name FROM users WHERE id = ?", (sender_user_id,))
            return cursor.fetchone()

        try:
            sender_info = execute_db_operation(_get_sender_info)
            if sender_info:
                # Temporarily set as current user for context
                auth.current_user = {
                    'id': sender_info[0],
                    'username': sender_info[1],
                    'email': sender_info[2],
                    'first_name': sender_info[3],
                    'last_name': sender_info[4]
                }
        except (sqlite3.Error, AttributeError, IndexError) as e:
            log_event('warning', f"Could not set sender context: {e}")

    # Send the email (will use the sender context we just set)
    result = send_email(recipient_email, subject, body, cc, bcc, attachments)

    # Restore original user context
    if original_user and auth:
        auth.current_user = original_user

    return result

@handle_exception
def send_email_as_system(recipient_email, subject, body, system_name="University System", cc=None, bcc=None, attachments=None):
    """Send an email as a named system entity"""

    # Temporarily override config for this send
    original_sender_name = config.get('sender_name')
    config['sender_name'] = system_name

    result = send_email(recipient_email, subject, body, cc, bcc, attachments)

    # Restore original config
    config['sender_name'] = original_sender_name

    return result

def get_appropriate_sender_id(cursor, sender_email, sender_name, current_time):
    """
    Get the appropriate sender ID based on context:
    1. If there's a logged-in user, use their ID (for user-initiated emails)
    2. If sender_email matches a real user, use that user's ID
    3. Otherwise, create/use a system user with the appropriate name
    """

    # Method 1: If we have an authenticated user sending the email, use their ID
    # IMPORTANT: The current_user['id'] may come from the shared auth database
    # (auth.db), not the university's own users table.  We must look up the
    # user in the university DB by username to get the correct local ID.
    current_auth = _get_current_auth()
    if current_auth and hasattr(current_auth, 'current_user') and current_auth.current_user:
        username = current_auth.current_user.get('username')
        if username:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            local_row = cursor.fetchone()
            if local_row:
                log_event('info', f"Using authenticated user as sender: {username} (local ID: {local_row[0]})")
                return local_row[0]
            # User exists in shared auth but not in university DB — create a
            # local profile so the FK constraint is satisfied.
            email = current_auth.current_user.get('email', f"{username}@university.local")
            display = current_auth.current_user.get('display_name', username)
            parts = display.split(' ', 1)
            first = parts[0] if parts else display
            last = parts[1] if len(parts) > 1 else ''
            role = current_auth.current_user.get('role', 'admin')
            try:
                cursor.execute('''
                    INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, first, last, email, role, current_time, current_time))
                new_id = cursor.lastrowid
                log_event('info', f"Created local user profile for shared-auth user: {username} (ID: {new_id})")
                return new_id
            except sqlite3.Error as e:
                log_event('warning', f"Failed to create local profile for {username}: {e}")

    # Method 2: Look for a real user with the sender email
    cursor.execute("SELECT id, username FROM users WHERE email = ?", (sender_email,))
    real_user = cursor.fetchone()

    if real_user:
        log_event('info', f"Found real user for sender email {sender_email}: {real_user[1]} (ID: {real_user[0]})")
        return real_user[0]

    # Method 3: Create or get a system user with appropriate naming
    # Use sender_name to create a more descriptive system user
    system_username = generate_system_username(sender_name, sender_email)

    cursor.execute("SELECT id FROM users WHERE username = ? AND role = 'admin'", (system_username,))
    system_user = cursor.fetchone()

    if system_user:
        return system_user[0]
    else:
        # Create a new system user with descriptive name
        # Parse sender_name for first/last name
        name_parts = sender_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else sender_name
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        cursor.execute('''
        INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (system_username, first_name, last_name, sender_email, 'admin', current_time, current_time))

        new_user_id = cursor.lastrowid
        log_event('info', f"Created system user: {system_username} (ID: {new_user_id}) for {sender_name}")
        return new_user_id

@handle_exception
def send_template_email(template_name, recipient_email, template_vars, cc=None, bcc=None, attachments=None):
    """
    Send an email using a template with enhanced logging.

    Args:
        template_name: Name of the email template to use
        recipient_email: Email address of recipient
        template_vars: Dictionary of variables to render in template
        cc: CC recipients (optional)
        bcc: BCC recipients (optional)
        attachments: Email attachments (optional)

    Returns:
        bool: True if email was sent successfully, False otherwise

    Raises:
        InvalidInputError: If template_name or recipient_email is missing
        TemplateError: If template rendering fails
        EmailDeliveryError: If email delivery fails
    """
    # Validate inputs
    if not template_name:
        raise InvalidInputError(
            "Template name is required",
            code="EMAIL_MISSING_TEMPLATE_NAME"
        )

    if not recipient_email:
        raise InvalidInputError(
            "Recipient email is required",
            code="EMAIL_MISSING_RECIPIENT"
        )

    # Log template email attempt
    if auth and auth.current_user:
        log_event('info', f"Sending template email '{template_name}' to {recipient_email}")

    subject, body = render_template(template_name, template_vars)

    if subject is None or body is None:
        log_event('error', f"Failed to render template: {template_name}")
        raise TemplateError(
            f"Failed to render email template: {template_name}",
            code="TEMPLATE_RENDER_FAILED",
            details={'template_name': template_name, 'recipient': recipient_email}
        )

    # Log successful template rendering
    log_event('info', f"Template '{template_name}' rendered successfully")

    result = send_email(recipient_email, subject, body, cc, bcc, attachments)

    if result:
        log_event('info', f"Template email '{template_name}' sent successfully to {recipient_email}")
    else:
        log_event('error', f"Failed to send template email '{template_name}' to {recipient_email}")

    return result
