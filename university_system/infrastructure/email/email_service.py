"""Core email processing services."""

from __future__ import annotations

import csv
import json
import queue
import re
import smtplib
import sqlite3
import threading
import time
from datetime import datetime, timedelta

import schedule

from university_system.modules.shared.utils.i18n import get_text as _t, init_i18n
init_i18n()

from university_system.infrastructure.email.config import config
from university_system.infrastructure.email.email_db_utilities import _ensure_db_ready, execute_db_operation
from university_system.modules.shared.utils.logs import handle_exception, log_event
from university_system.infrastructure.email.reports import log_email_metrics
from university_system.infrastructure.email.smtp import send_email_via_smtp
# Import auth access - use function to get current auth instance
try:
    from university_system.infrastructure.shared_context import get_auth as _get_shared_auth
    HAS_SHARED_AUTH = True
except ImportError:
    HAS_SHARED_AUTH = False
    _get_shared_auth = None

# Fallback to email state auth
from university_system.infrastructure.email.state import auth_proxy as _state_auth

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
from university_system.infrastructure.email.templates import (
    ensure_templates_directory,
    list_templates,
    load_template,
    render_template,
    template_management_menu,
)
from university_system.infrastructure.exceptions import (
    EmailError,
    EmailDeliveryError,
    TemplateError,
    AttachmentError,
    ValidationError,
    InvalidInputError,
)

# Import immutable audit logging for compliance
try:
    from university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        mask_sensitive_data,
    )
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
    def mask_sensitive_data(data, fields=None):
        return data

email_queue = queue.Queue()

worker_threads = []
worker_threads_lock = threading.Lock()  # Protect worker_threads list

# Use threading.Event for thread-safe signaling (replaces stop_workers boolean)
stop_workers_event = threading.Event()

scheduled_jobs = {}
scheduled_jobs_lock = threading.Lock()  # Protect scheduled_jobs dict



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
            # Get full user details from database (current_user only has id, username, role)
            user_id = current_auth.current_user.get('id')
            if user_id:
                cursor.execute("SELECT email, first_name, last_name FROM users WHERE id = ?", (user_id,))
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
                    # Fallback if user not found
                    sender_email = config.get('sender_email', "noreply@university.edu")
                    sender_name = config.get('sender_name', "University System")
            else:
                sender_email = config.get('sender_email', "noreply@university.edu")
                sender_name = config.get('sender_name', "University System")
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



def fix_inbox_display_issue():
    """Fix the issue where sent emails don't appear in recipient inboxes"""
    
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
    current_auth = _get_current_auth()
    if current_auth and hasattr(current_auth, 'current_user') and current_auth.current_user:
        log_event('info', f"Using authenticated user as sender: {current_auth.current_user['username']} (ID: {current_auth.current_user['id']})")
        return current_auth.current_user['id']
    
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



@handle_exception
def get_stored_emails(limit=50, offset=0, recipient_filter=None, date_filter=None, sender_filter=None):
    """Simplified get stored emails function

    Args:
        limit: Maximum number of emails to return
        offset: Number of emails to skip
        recipient_filter: Filter by recipient email (partial match)
        date_filter: Filter by date
        sender_filter: Filter by sender email (exact match) - used for non-admin users
    """

    def _get_emails(cursor):
        query = '''
        SELECT id, recipient_email, subject, body, sender_email, sender_name,
               cc_recipients, bcc_recipients, attachment_paths, created_date,
               template_name, template_vars, related_to, student_id
        FROM stored_emails
        '''
        params = []

        # Add filters
        conditions = []
        if recipient_filter:
            conditions.append("recipient_email LIKE ?")
            params.append(f"%{recipient_filter}%")

        if date_filter:
            conditions.append("DATE(created_date) = ?")
            params.append(date_filter)

        if sender_filter:
            conditions.append("sender_email = ?")
            params.append(sender_filter)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        emails = cursor.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) FROM stored_emails"
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions[:-2])
            cursor.execute(count_query, params[:-2])
        else:
            cursor.execute(count_query)
        
        total_count = cursor.fetchone()[0]
        
        return {
            'emails': [
                {
                    'id': email[0], 'recipient_email': email[1], 'subject': email[2],
                    'body': email[3], 'sender_email': email[4], 'sender_name': email[5],
                    'cc_recipients': email[6], 'bcc_recipients': email[7],
                    'attachment_paths': email[8], 'created_date': email[9],
                    'template_name': email[10], 'template_vars': email[11],
                    'related_to': email[12], 'student_id': email[13]
                } for email in emails
            ],
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        }
    
    try:
        return execute_db_operation(_get_emails)
    except sqlite3.Error as e:
        log_event('error', f"Database error retrieving stored emails: {e}")
        return {'emails': [], 'total_count': 0, 'limit': limit, 'offset': offset}



@handle_exception
def delete_stored_email(email_id):
    """Delete a stored email by ID"""
    def _delete_email(cursor):
        cursor.execute('DELETE FROM stored_emails WHERE id = ?', (email_id,))
        deleted_count = cursor.rowcount
        
        if deleted_count > 0:
            log_event('info', f"Deleted stored email ID: {email_id}")
            return True
        else:
            log_event('warning', f"No stored email found with ID: {email_id}")
            return False
    
    try:
        return execute_db_operation(_delete_email)
    except sqlite3.Error as e:
        log_event('error', f"Database error deleting stored email: {e}")
        return False



@handle_exception
def clear_stored_emails(older_than_days=None):
    """Clear stored emails, optionally only those older than specified days"""
    def _clear_emails(cursor):
        if older_than_days:
            cutoff_date = (datetime.now() - timedelta(days=older_than_days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM stored_emails WHERE created_date < ?', (cutoff_date,))
            log_event('info', f"Deleted {cursor.rowcount} stored emails older than {older_than_days} days")
        else:
            cursor.execute('DELETE FROM stored_emails')
            log_event('info', f"Deleted all {cursor.rowcount} stored emails")
        
        return cursor.rowcount
    
    try:
        return execute_db_operation(_clear_emails)
    except sqlite3.Error as e:
        log_event('error', f"Database error clearing stored emails: {e}")
        return 0



@handle_exception
def email_worker():
    """Simplified worker function with better database handling"""
    # No need for global - stop_workers_event is already global and thread-safe

    # Single worker thread with proper serialization
    worker_id = threading.current_thread().ident
    log_event('info', f"Email worker {worker_id} started")

    while not stop_workers_event.is_set():
        try:
            # Get an email task from the queue with a timeout
            task = email_queue.get(timeout=5.0)
            
            # Process the email task with proper delay
            success = False
            
            try:
                if task.get('type') == 'template':
                    success = send_template_email(
                        task['template_name'],
                        task['recipient'],
                        task['template_vars'],
                        task.get('cc'),
                        task.get('bcc'),
                        task.get('attachments')
                    )
                else:
                    success = send_email(
                        task['recipient'],
                        task['subject'],
                        task['body'],
                        task.get('cc'),
                        task.get('bcc'),
                        task.get('attachments')
                    )
                    
            except (smtplib.SMTPException, EmailDeliveryError) as e:
                log_event('error', f"Worker email delivery error: {e}")
                success = False
            except (TemplateError, AttachmentError) as e:
                log_event('error', f"Worker template/attachment error: {e}")
                success = False
            except sqlite3.Error as e:
                log_event('error', f"Worker database error: {e}")
                success = False

            # Handle success/failure
            if success:
                log_event('info', f"Email processed for {task['recipient']}")
            else:
                log_event('error', f"Failed to process email for {task['recipient']}")

            # Mark the task as done
            email_queue.task_done()

            # Longer delay between operations to reduce contention
            time.sleep(config.get('send_delay', 2.0))

        except queue.Empty:
            # No email in queue, continue waiting
            continue
        except (KeyError, TypeError) as e:
            log_event('error', f"Invalid task format in email worker: {e}")
            time.sleep(1.0)
        except RuntimeError as e:
            log_event('error', f"Runtime error in email worker: {e}")
            time.sleep(2.0)
    
    log_event('info', f"Email worker {worker_id} stopped")



@handle_exception
def start_email_workers():
    """Start worker threads for processing the email queue - SINGLE THREAD ONLY"""
    # Only start workers if not in database-only mode
    if config.get('database_only_mode', True):
        log_event('info', "Database-only mode enabled - email workers not started")
        return True

    # Stop any existing workers
    stop_email_workers()

    # Reset event and create new workers - FORCE SINGLE THREAD
    stop_workers_event.clear()  # Thread-safe signal to start workers

    with worker_threads_lock:
        # Create and start ONLY ONE worker thread
        t = threading.Thread(target=email_worker, daemon=True)
        t.start()
        worker_threads.append(t)

        log_event('info', f"Started {len(worker_threads)} email worker thread")

    return True



@handle_exception
def stop_email_workers():
    """Stop all email worker threads"""
    with worker_threads_lock:
        if worker_threads:
            log_event('info', "Stopping email worker threads...")
            stop_workers_event.set()  # Thread-safe signal to stop workers

            # Wait for all threads to complete
            for thread in worker_threads:
                if thread.is_alive():
                    thread.join(timeout=5.0)

            worker_threads.clear()
            log_event('info', "Email workers stopped")
    return True



@handle_exception
def queue_email(recipient, subject, body, cc=None, bcc=None, attachments=None, scheduled_id=None):
    """Queue an email to be sent asynchronously"""
    # In database-only mode, process immediately instead of queuing
    if config.get('database_only_mode', True):
        return send_email(recipient, subject, body, cc, bcc, attachments)
    
    # Ensure worker threads are running
    if not worker_threads:
        start_email_workers()
    
    # Create the email task
    task = {
        'recipient': recipient,
        'subject': subject,
        'body': body,
        'cc': cc,
        'bcc': bcc,
        'attachments': attachments
    }
    
    if scheduled_id:
        task['scheduled_id'] = scheduled_id
    
    # Add to the queue
    email_queue.put(task)
    
    return True



@handle_exception
def queue_template_email(template_name, recipient, template_vars, cc=None, bcc=None, attachments=None, scheduled_id=None):
    """Queue a template email to be sent asynchronously with enhanced logging"""
    # In database-only mode, process immediately instead of queuing
    if config.get('database_only_mode', True):
        log_event('info', f"Processing template email immediately: {template_name} to {recipient}")
        success = send_template_email(template_name, recipient, template_vars, cc, bcc, attachments)
        if scheduled_id and success:
            update_scheduled_email_status(scheduled_id, 'sent')
            log_event('info', f"Scheduled email {scheduled_id} marked as sent")
        elif scheduled_id:
            update_scheduled_email_status(scheduled_id, 'failed')
            log_event('error', f"Scheduled email {scheduled_id} marked as failed")
        return success
    
    # Ensure worker threads are running
    if not worker_threads:
        start_email_workers()
    
    # Create the email task
    task = {
        'type': 'template',
        'template_name': template_name,
        'recipient': recipient,
        'template_vars': template_vars,
        'cc': cc,
        'bcc': bcc,
        'attachments': attachments
    }
    
    if scheduled_id:
        task['scheduled_id'] = scheduled_id
    
    # Add to the queue
    email_queue.put(task)
    log_event('info', f"Template email queued: {template_name} for {recipient}")
    
    return True



@handle_exception
def wait_for_email_queue():
    """Wait for all queued emails to be sent"""
    if config.get('database_only_mode', True):
        log_event('info', "Database-only mode - no queue to wait for")
        return True
        
    queue_size = email_queue.qsize()
    log_event('info', f"Waiting for {queue_size} emails to be sent...")
    email_queue.join()
    log_event('info', "All emails have been sent")
    return True



@handle_exception
def send_bulk(recipients, template_name, template_vars_list=None, rate_limit=None):
    """Send emails to multiple recipients with optional rate limiting"""
    if not recipients:
        log_event('error', "No recipients specified for bulk send")
        return False
    
    if not template_name:
        log_event('error', "No template specified for bulk send")
        return False
    
    # Set rate limit if provided (emails per second) - only applies to SMTP mode
    if rate_limit and not config.get('database_only_mode', True):
        original_delay = config['send_delay']
        config['send_delay'] = 1.0 / rate_limit
    
    success_count = 0
    failure_count = 0
    
    # In database-only mode, process immediately
    if config.get('database_only_mode', True):
        for i, recipient in enumerate(recipients):
            try:
                # Get template variables for this recipient
                vars_dict = template_vars_list[i] if template_vars_list and i < len(template_vars_list) else {}
                
                # Send the email directly
                if send_template_email(template_name, recipient, vars_dict):
                    success_count += 1
                else:
                    failure_count += 1
            except (TemplateError, EmailDeliveryError) as e:
                log_event('error', f"Email error processing for {recipient}: {e}")
                failure_count += 1
            except (KeyError, IndexError) as e:
                log_event('error', f"Template variable error for {recipient}: {e}")
                failure_count += 1
    else:
        # Ensure email workers are running
        if not worker_threads:
            start_email_workers()

        # Send to each recipient
        for i, recipient in enumerate(recipients):
            try:
                # Get template variables for this recipient
                vars_dict = template_vars_list[i] if template_vars_list and i < len(template_vars_list) else {}

                # Queue the email
                queue_template_email(template_name, recipient, vars_dict)
                success_count += 1
            except (TemplateError, ValidationError) as e:
                log_event('error', f"Error queueing email for {recipient}: {e}")
                failure_count += 1
            except (KeyError, IndexError) as e:
                log_event('error', f"Template variable error queueing for {recipient}: {e}")
                failure_count += 1
    
    # Restore original delay if changed
    if rate_limit and not config.get('database_only_mode', True):
        config['send_delay'] = original_delay
    
    log_event('info', f"Bulk send processed: {success_count} successes, {failure_count} failures")
    
    return {
        'total': len(recipients),
        'success': success_count,
        'failure': failure_count
    }



@handle_exception
def schedule_send(datetime_obj, recipients, template_name, template_vars_list=None):
    """Schedule emails to be sent at a specific time"""
    if not recipients:
        log_event('error', "No recipients specified for scheduled send")
        return False
    
    if not template_name:
        log_event('error', "No template specified for scheduled send")
        return False
    
    if not datetime_obj or datetime_obj <= datetime.now():
        log_event('error', "Scheduled datetime must be in the future")
        return False
    
    def _schedule_emails(cursor):
        success_count = 0
        failure_count = 0
        scheduled_ids = []
        
        # Schedule each email
        for i, recipient in enumerate(recipients):
            try:
                # Get template variables for this recipient
                vars_dict = template_vars_list[i] if template_vars_list and i < len(template_vars_list) else {}
                
                # Convert template vars to JSON
                vars_json = json.dumps(vars_dict)
                
                # Insert into scheduled_emails table
                cursor.execute('''
                INSERT INTO scheduled_emails 
                (template_name, recipient_email, template_vars, scheduled_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    template_name,
                    recipient,
                    vars_json,
                    datetime_obj.strftime('%Y-%m-%d %H:%M:%S'),
                    'pending',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                
                scheduled_id = cursor.lastrowid
                scheduled_ids.append(scheduled_id)
                success_count += 1
            except sqlite3.Error as e:
                log_event('error', f"Database error scheduling email for {recipient}: {e}")
                failure_count += 1
            except (json.JSONDecodeError, TypeError) as e:
                log_event('error', f"JSON serialization error for {recipient}: {e}")
                failure_count += 1

        return {
            'total': len(recipients),
            'success': success_count,
            'failure': failure_count,
            'scheduled_ids': scheduled_ids
        }

    try:
        result = execute_db_operation(_schedule_emails)

        # Start the scheduler if needed and not in database-only mode
        if result['success'] > 0 and not config.get('database_only_mode', True):
            ensure_scheduler_running()

        log_event('info', f"Scheduled send: {result['success']} successes, {result['failure']} failures for {datetime_obj}")
        return result

    except sqlite3.Error as e:
        log_event('error', f"Database error scheduling emails: {e}")
        return {
            'total': len(recipients),
            'success': 0,
            'failure': len(recipients),
            'scheduled_ids': []
        }



@handle_exception
def process_scheduled_emails():
    """Process due scheduled emails"""
    def _process_emails(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Find due emails with pending status
        cursor.execute('''
        SELECT id, template_name, recipient_email, template_vars 
        FROM scheduled_emails
        WHERE scheduled_date <= ? AND status = 'pending'
        ''', (current_time,))
        
        scheduled_emails = cursor.fetchall()
        return scheduled_emails
    
    try:
        scheduled_emails = execute_db_operation(_process_emails)
        
        if not scheduled_emails:
            return 0
        
        # Process each due email
        processed_count = 0
        
        for email in scheduled_emails:
            scheduled_id, template_name, recipient, vars_json = email
            
            try:
                # Parse template vars
                template_vars = json.loads(vars_json) if vars_json else {}
                
                # Queue or send the email depending on mode
                if config.get('database_only_mode', True):
                    # Send directly in database mode
                    success = send_template_email(template_name, recipient, template_vars)
                    if success:
                        update_scheduled_email_status(scheduled_id, 'sent')
                    else:
                        update_scheduled_email_status(scheduled_id, 'failed')
                else:
                    # Queue the email
                    queue_template_email(template_name, recipient, template_vars, scheduled_id=scheduled_id)
                    # Update status to 'processing'
                    update_scheduled_email_status(scheduled_id, 'processing')
                
                processed_count += 1
            except (TemplateError, EmailDeliveryError) as e:
                log_event('error', f"Email error processing scheduled email {scheduled_id}: {e}")
                update_scheduled_email_status(scheduled_id, 'failed')
            except sqlite3.Error as e:
                log_event('error', f"Database error processing scheduled email {scheduled_id}: {e}")
                update_scheduled_email_status(scheduled_id, 'failed')

        log_event('info', f"Processed {processed_count} scheduled emails")
        return processed_count

    except sqlite3.Error as e:
        log_event('error', f"Database error processing scheduled emails: {e}")
        return 0



@handle_exception
def ensure_scheduler_running():
    """Ensure the scheduler is running"""
    global scheduled_jobs
    
    # Skip scheduler in database-only mode
    if config.get('database_only_mode', True):
        log_event('info', "Database-only mode - scheduler not needed")
        return True
    
    # Check if scheduler is already running
    if 'process_emails' in scheduled_jobs:
        return True
    
    # Schedule job to run every minute
    scheduled_jobs['process_emails'] = schedule.every(1).minutes.do(process_scheduled_emails)
    
    # Start scheduler in a separate thread if not already running
    scheduler_thread = getattr(ensure_scheduler_running, 'scheduler_thread', None)
    if not scheduler_thread or not scheduler_thread.is_alive():
        ensure_scheduler_running.scheduler_thread = threading.Thread(target=run_scheduler)
        ensure_scheduler_running.scheduler_thread.daemon = True
        ensure_scheduler_running.scheduler_thread.start()
    
    log_event('info', "Email scheduler started")
    return True



def run_scheduler():
    """Run the scheduler in a loop"""
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)  # Check every 10 seconds
        except (RuntimeError, OSError) as e:
            log_event('error', f"Scheduler runtime error: {e}")
            time.sleep(30)  # Longer delay on error



@handle_exception
def update_scheduled_email_status(scheduled_id, status):
    """Update the status of a scheduled email"""
    def _update_status(cursor):
        cursor.execute('''
        UPDATE scheduled_emails
        SET status = ?
        WHERE id = ?
        ''', (status, scheduled_id))
        return True
    
    try:
        return execute_db_operation(_update_status)
    except sqlite3.Error as e:
        log_event('error', f"Database error updating scheduled email status: {e}")
        return False



@handle_exception
def send_registration_confirmation(student_id):
    """Send a registration confirmation email to a student"""
    def _send_confirmation(cursor):
        # Get student information
        cursor.execute('''
        SELECT email_address, title, first_name, middle_name, last_name, course
        FROM students WHERE student_id = ?
        ''', (student_id,))
        
        student = cursor.fetchone()
        
        if not student:
            log_event('error', f"Student not found: {student_id}")
            return False
        
        email_address, title, first_name, middle_name, last_name, course = student
        
        # Get student modules
        cursor.execute('''
        SELECT m.module_type, sm.module_code, m.module_name
        FROM student_modules sm
        JOIN modules m ON sm.module_code = m.module_code
        WHERE sm.student_id = ?
        ORDER BY m.module_type
        ''', (student_id,))
        
        modules = cursor.fetchall()
        
        # Format module list
        modules_list = ""
        for module in modules:
            modules_list += f"- {module[0]}: {module[1]} - {module[2]}\n"
        
        # Prepare template variables
        template_vars = {
            'student_id': student_id,
            'email_address': email_address,
            'title': title,
            'first_name': first_name,
            'middle_name': middle_name or '',
            'last_name': last_name,
            'course': course,
            'modules_list': modules_list
        }
        
        return template_vars, email_address
    
    try:
        result = execute_db_operation(_send_confirmation)
        if result:
            template_vars, email_address = result
            # Queue the email
            return queue_template_email('user_management/registration_confirmation', email_address, template_vars)
        return False
    except sqlite3.Error as e:
        log_event('error', f"Database error sending registration confirmation: {e}")
        return False
    except (TemplateError, EmailError) as e:
        log_event('error', f"Email error sending registration confirmation: {e}")
        return False



@handle_exception
def send_update_confirmation(student_email, updated_fields):
    """Send update confirmation email to student"""
    try:
        # Format updated fields list with field names and new values
        if isinstance(updated_fields, dict):
            updated_fields_str = '\n'.join(
                [f"- {field}: {value}" for field, value in updated_fields.items()]
            )
        else:
            updated_fields_str = '\n'.join([f"- {field}" for field in updated_fields])

        template_vars = {
            'updated_fields': updated_fields_str
        }

        # Send email using template
        return send_template_email('update_confirmation', student_email, template_vars)
    except (TemplateError, EmailDeliveryError) as e:
        log_event('error', f"Email error sending update confirmation: {e}")
        return False
    except (TypeError, AttributeError) as e:
        log_event('error', f"Data error sending update confirmation: {e}")
        return False



@handle_exception
def send_grade_notification(student_id, module_code, module_name, grade):
    """Send a grade notification email to a student"""
    def _send_grade_notification(cursor):
        # Get student information
        cursor.execute('''
        SELECT email_address, title, first_name, middle_name, last_name
        FROM students WHERE student_id = ?
        ''', (student_id,))
        
        student = cursor.fetchone()
        
        if not student:
            log_event('error', f"Student not found: {student_id}")
            return False
        
        email_address, title, first_name, middle_name, last_name = student
        
        # Prepare template variables
        template_vars = {
            'student_id': student_id,
            'email_address': email_address,
            'title': title,
            'first_name': first_name,
            'middle_name': middle_name or '',
            'last_name': last_name,
            'module_code': module_code,
            'module_name': module_name,
            'grade': grade,
            'date_posted': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return template_vars, email_address
    
    try:
        result = execute_db_operation(_send_grade_notification)
        if result:
            template_vars, email_address = result
            # Queue the email
            return queue_template_email('grade_notification', email_address, template_vars)
        return False
    except Exception as e:
        log_event('error', f"Error sending grade notification: {e}")
        return False



@handle_exception
def send_password_reset(student_id, reset_code):
    """Send a password reset email to a student"""
    def _send_password_reset(cursor):
        # Get student information
        cursor.execute('''
        SELECT email_address, title, first_name, middle_name, last_name
        FROM students WHERE student_id = ?
        ''', (student_id,))
        
        student = cursor.fetchone()
        
        if not student:
            log_event('error', f"Student not found: {student_id}")
            return False
        
        email_address, title, first_name, middle_name, last_name = student
        
        # Prepare template variables
        template_vars = {
            'student_id': student_id,
            'email_address': email_address,
            'title': title,
            'first_name': first_name,
            'middle_name': middle_name or '',
            'last_name': last_name,
            'reset_code': reset_code
        }
        
        return template_vars, email_address
    
    try:
        result = execute_db_operation(_send_password_reset)
        if result:
            template_vars, email_address = result
            # Queue the email
            email_sent = queue_template_email('password_reset', email_address, template_vars)

            # Immutable audit log for password reset email (security compliance)
            if IMMUTABLE_AUDIT_AVAILABLE and email_sent:
                safe_log_security_event(
                    action=AuditAction.PASSWORD_RESET,
                    user_id=student_id,
                    resource_type='password_reset_email',
                    details={
                        'recipient_masked': mask_sensitive_data({'email': email_address}, ['email']),
                        'student_id': student_id
                    }
                )

            return email_sent
        return False
    except Exception as e:
        log_event('error', f"Error sending password reset: {e}")
        return False



@handle_exception
def send_assignment_notification(assignment_id, assignment_title, module_code, due_date, description=None):
    """Send assignment notification using the centralized email system"""
    def _send_notifications(cursor):
        # Get students enrolled in the module - use correct email column
        cursor.execute('''
        SELECT s.email_address, s.first_name, s.last_name, s.student_id
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ? AND s.email_address IS NOT NULL AND s.email_address != ''
        ''', (module_code,))

        students = cursor.fetchall()
        success_count = 0

        for email, first_name, last_name, student_id in students:
            # Try template first, fallback to simple email
            template_vars = {
                'student_name': f"{first_name} {last_name}".strip() or "Student",
                'assignment_title': assignment_title,
                'module_code': module_code,
                'due_date': due_date,
                'assignment_description': description or "No description provided"
            }

            # Try template email
            try:
                if send_template_email('assignment_notification', email, template_vars):
                    success_count += 1
                    continue
            except:
                pass

            # Fallback to simple email
            try:
                subject = f"New Assignment: {assignment_title}"
                body = f"""Dear {first_name},

A new assignment has been published for {module_code}.

Assignment: {assignment_title}
Due Date: {due_date}

{description or ''}

Please login to the Assignment System to view details and submit your work.

Best regards,
Academic Administration Team
"""
                if send_email(email, subject, body):
                    success_count += 1
            except Exception as e:
                print(f"Failed to send email to {student_id}: {e}")

        return success_count

    try:
        count = execute_db_operation(_send_notifications)
        log_event('info', f"Assignment notification sent to {count} students")
        return count > 0
    except Exception as e:
        log_event('error', f"Error sending assignment notifications: {e}")
        return False



@handle_exception
def send_grade_notification(student_email, assignment_title, module_code, grade, feedback=None):
    """Send grade notification email"""
    template_vars = {
        'student_name': "Student",  # Could be enhanced to get actual name
        'assignment_title': assignment_title,
        'module_code': module_code,
        'grade': grade,
        'feedback': feedback or "No additional feedback provided"
    }
    
    return send_template_email('assignment_grade_released', student_email, template_vars)



@handle_exception  
def send_extension_notification(student_email, assignment_title, module_code, new_due_date, extension_days):
    """Send extension approval notification"""
    template_vars = {
        'student_name': "Student",
        'assignment_title': assignment_title,
        'module_code': module_code,
        'new_due_date': new_due_date,
        'extension_days': extension_days
    }
    
    return send_template_email('assignment_extension_approved', student_email, template_vars)



@handle_exception
def send_confirmation_email(self, student_id, subject, message):
    """Send a confirmation email to a student using centralized email system"""
    def _send_confirmation_email(cursor):
        # Get student email from student_id
        cursor.execute('''
        SELECT email_address FROM students WHERE student_id = ?
        ''', (student_id,))
            
        result = cursor.fetchone()
            
        if not result:
            log_event('error', f"Could not find email address for student ID {student_id}")
            return False
            
        email_address = result[0]
        return queue_email(email_address, subject, message)
        
    try:
        return execute_db_operation(_send_confirmation_email)
    except Exception as e:
        log_event('error', f"Error sending confirmation email: {e}")
        return False



@handle_exception
def send_batch_email_form():
    """Interactive form for sending batch emails"""
    print("\n" + _t("email_service.batch_sender_title"))
    print("=================")
    
    # Get announcement details
    title = input("Enter announcement title: ")
    
    if not title:
        print(_t("email_service.title_empty"))
        return
    
    print("\n" + _t("email_service.enter_body_hint"))
    body_lines = []
    while True:
        line = input()
        if line == 'END':
            break
        body_lines.append(line)
    
    body = "\n".join(body_lines)
    
    if not body:
        print(_t("email_service.body_empty"))
        return
    
    # Get filter criteria
    print("\n" + _t("email_service.filter_recipients"))
    
    filter_criteria = {}
    
    course = input("Course (CS/DS/leave empty for all): ")
    if course:
        filter_criteria['course'] = course
    
    module = input("Module Code (leave empty for all): ")
    if module:
        filter_criteria['module_code'] = module
    
    year = input("Registration Year (YYYY, leave empty for all): ")
    if year and year.isdigit() and len(year) == 4:
        filter_criteria['registration_year'] = year
    
    # Confirm sending
    if filter_criteria:
        filters = ", ".join(f"{k}: {v}" for k, v in filter_criteria.items())
        confirm = input(f"\n{'Store' if config.get('database_only_mode', True) else 'Send'} announcement to students matching [{filters}]? (y/n): ")
    else:
        confirm = input(f"\n{'Store' if config.get('database_only_mode', True) else 'Send'} announcement to ALL students? (y/n): ")
    
    if confirm.lower() != 'y':
        print(_t("email_service.batch_cancelled"))
        return
    
    # Send the batch email
    success, failed, total = send_batch_announcement(title, body, filter_criteria)
    
    if config.get('database_only_mode', True):
        print("\n" + _t("email_service.emails_stored", total=total))
        print(_t("email_service.success_failed", success=success, failed=failed))
    else:
        print("\n" + _t("email_service.emails_queued", total=total))
        print(_t("email_service.success_failed", success=success, failed=failed))
        
        # Wait for emails to be sent
        if total > 0:
            wait_confirm = input("\nWait for all emails to be sent? (y/n): ")
            if wait_confirm.lower() == 'y':
                wait_for_email_queue()



@handle_exception
def schedule_email_form():
    """Interactive form for scheduling emails"""
    print("\n" + _t("email_service.schedule_title"))
    print("==============")
    
    # Select template
    templates = list_templates()
    
    if not templates:
        print(_t("email_service.no_templates"))
        return
    
    print("\n" + _t("email_service.available_templates") + ":")
    for i, template in enumerate(templates, 1):
        print(f"{i}. {template['name']}")
    
    try:
        template_idx = int(input("\nSelect template (0 to cancel): "))
        if template_idx == 0:
            return
        
        if 1 <= template_idx <= len(templates):
            template_name = templates[template_idx - 1]['name']
        else:
            print(_t("email_service.invalid_template_number"))
            return
    except ValueError:
        print(_t("email_service.invalid_input"))
        return
    
    # Get recipients
    print("\n" + _t("email_service.enter_recipients_hint"))
    recipients = []
    while True:
        line = input()
        if line == 'END':
            break
        if line.strip():
            recipients.append(line.strip())
    
    if not recipients:
        print(_t("email_service.no_recipients"))
        return
    
    # Get scheduled date
    print("\n" + _t("email_service.enter_scheduled_date"))
    try:
        year = int(input("Year (YYYY): "))
        month = int(input("Month (MM): "))
        day = int(input("Day (DD): "))
        hour = int(input("Hour (0-23): "))
        minute = int(input("Minute (0-59): "))
        
        scheduled_date = datetime(year, month, day, hour, minute)
        
        if scheduled_date <= datetime.now():
            print(_t("email_service.date_must_be_future"))
            return
    except ValueError:
        print(_t("email_service.invalid_date"))
        return
    
    # Confirm scheduling
    confirm = input(f"\nSchedule {len(recipients)} emails using template '{template_name}' for {scheduled_date}? (y/n): ")
    
    if confirm.lower() != 'y':
        print(_t("email_service.scheduling_cancelled"))
        return
    
    # Schedule the emails
    result = schedule_send(scheduled_date, recipients, template_name)
    
    print("\n" + _t("email_service.scheduled_count", count=result['success'], date=str(scheduled_date)))
    if result['failure'] > 0:
        print(_t("email_service.failed_schedule", count=result['failure']))

    print(_t("email_service.scheduled_ids", ids=', '.join(map(str, result['scheduled_ids']))))



@handle_exception
def send_ticket_notification(ticket_id, subject, username, admin_list=None):
    """Send an email notification when a new ticket is created"""
    def _send_ticket_notification(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get ticket details including category and priority
        cursor.execute('''
            SELECT category, priority, status
            FROM support_tickets
            WHERE ticket_id = ?
        ''', (ticket_id,))
        ticket_details = cursor.fetchone()

        if not ticket_details:
            log_event('error', f"Could not find ticket {ticket_id}")
            return False

        category, priority, status = ticket_details

        # Get the user's email - check both students and users tables
        user_email = None

        # Try students table first (uses email_address column)
        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (username,))
        result = cursor.fetchone()

        if result and result[0]:
            user_email = result[0]
        else:
            # Fall back to users table (uses email column)
            cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (username, username))
            result = cursor.fetchone()

            if result and result[0]:
                user_email = result[0]

        if not user_email:
            log_event('error', f"Could not find email for user {username}")
            return False

        # Send confirmation to user using template
        user_subject, user_body = render_template('helpdesk_ticket_created_user', {
            'username': username,
            'ticket_id': ticket_id,
            'subject': subject,
            'category': category,
            'priority': priority,
            'status': status or 'Open'
        })
        
        # Queue the email
        success = queue_email(user_email, user_subject, user_body)
        
        if success:
            # Log the notification using safe logging
            safe_log_email(cursor, user_email, user_subject, current_time, 'sent', 
                          related_to=f"Ticket #{ticket_id} Creation")
        
        return success
    
    try:
        result = execute_db_operation(_send_ticket_notification)
        
        # Handle admin notifications separately if needed
        if result and admin_list:
            for admin in admin_list:
                admin_username = admin[0]
                def _notify_admin(cursor):
                    # Check both students and users tables for admin email
                    admin_email = None

                    # Try students table first
                    cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (admin_username,))
                    admin_result = cursor.fetchone()

                    if admin_result and admin_result[0]:
                        admin_email = admin_result[0]
                    else:
                        # Fall back to users table
                        cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (admin_username, admin_username))
                        admin_result = cursor.fetchone()

                        if admin_result and admin_result[0]:
                            admin_email = admin_result[0]

                    if admin_email:
                        # Get full ticket details for admin notification
                        cursor.execute('''
                            SELECT category, priority, status, description, created_at, user_id
                            FROM support_tickets
                            WHERE ticket_id = ?
                        ''', (ticket_id,))
                        ticket_details = cursor.fetchone()

                        if ticket_details:
                            category, priority, status, description, created_at, user_id = ticket_details
                            admin_subject, admin_body = render_template('helpdesk_ticket_created_admin', {
                                'ticket_id': ticket_id,
                                'username': username,
                                'subject': subject,
                                'category': category,
                                'priority': priority,
                                'status': status or 'Open',
                                'description': description or 'No description provided.',
                                'created_at': created_at,
                                'created_by': user_id or username
                            })
                            return queue_email(admin_email, admin_subject, admin_body)
                    return False
                
                execute_db_operation(_notify_admin)
        
        if result:
            log_event('info', f"Ticket notification sent for ticket #{ticket_id}")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending ticket notification: {e}")
        return False



@handle_exception
def send_reply_notification(ticket_id, user_id=None, username=None, responder=None, admin_list=None, status_update=None):
    """Send an email notification when a ticket is replied to or status updated"""
    def _send_reply_notification(cursor):
        # Get the ticket subject
        cursor.execute('SELECT subject FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket_result = cursor.fetchone()
        
        if not ticket_result:
            log_event('error', f"Could not find ticket with ID {ticket_id}")
            return False
        
        ticket_subject = ticket_result[0]
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        success = True
        
        # Notify user if user_id or username is provided
        if username:
            # Check both students and users tables for email
            user_email = None

            # Try students table first
            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (username,))
            user_result = cursor.fetchone()

            if user_result and user_result[0]:
                user_email = user_result[0]
            else:
                # Fall back to users table
                cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (username, username))
                user_result = cursor.fetchone()

                if user_result and user_result[0]:
                    user_email = user_result[0]

            if user_email:
                
                if status_update:
                    user_subject, user_body = render_template('support_ticket_status_changed', {
                        'username': username,
                        'ticket_id': ticket_id,
                        'subject': ticket_subject,
                        'old_status': '',
                        'new_status': status_update.upper()
                    })
                else:
                    user_subject, user_body = render_template('support_ticket_reply', {
                        'username': username,
                        'ticket_id': ticket_id,
                        'subject': ticket_subject,
                        'replied_by': responder
                    })
                
                # Queue the email
                if queue_email(user_email, user_subject, user_body):
                    # Log the notification
                    cursor.execute('''
                    INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        user_email,
                        user_subject,
                        current_time,
                        'sent',
                        f"Ticket #{ticket_id} Update"
                    ))
                else:
                    success = False
        
        return success
    
    try:
        result = execute_db_operation(_send_reply_notification)
        
        # Notify administrators
        if result and admin_list:
            for admin in admin_list:
                admin_username = admin[0]
                if admin_username != responder:  # Don't notify the responder
                    def _notify_admin(cursor):
                        # Check both students and users tables for admin email
                        admin_email = None
                        cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (admin_username,))
                        admin_result = cursor.fetchone()
                        if admin_result and admin_result[0]:
                            admin_email = admin_result[0]
                        else:
                            cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (admin_username, admin_username))
                            admin_result = cursor.fetchone()
                            if admin_result and admin_result[0]:
                                admin_email = admin_result[0]

                        if admin_email:

                            if status_update:
                                admin_subject, admin_body = render_template('support_ticket_status_changed_admin', {
                                    'ticket_id': ticket_id,
                                    'username': username,
                                    'subject': ticket_subject,
                                    'old_status': '',
                                    'new_status': status_update.upper()
                                })
                            else:
                                admin_subject, admin_body = render_template('support_ticket_reply_admin', {
                                    'ticket_id': ticket_id,
                                    'subject': ticket_subject,
                                    'replied_by': responder,
                                    'username': username
                                })
                            
                            return queue_email(admin_email, admin_subject, admin_body)
                        return False
                    
                    execute_db_operation(_notify_admin)
        
        if result:
            log_event('info', f"Reply notification sent for ticket #{ticket_id}")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending reply notification: {e}")
        return False



@handle_exception
def send_appointment_confirmation(student_id, appointment_id, appointment_date, appointment_time, provider, appointment_type):
    """Send an email confirmation for a scheduled health appointment"""
    def _send_appointment_confirmation(cursor):
        # Get the student's email address
        cursor.execute('SELECT email_address, first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()
        
        if not result:
            log_event('error', "Could not find student email address")
            return False
        
        email_address, first_name, last_name = result
        
        subject, body = render_template('health_appointment_confirmation', {
            'first_name': first_name,
            'last_name': last_name,
            'appointment_id': appointment_id,
            'appointment_type': appointment_type,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'provider': provider
        })
        
        # Queue the email
        success = queue_email(email_address, subject, body)
        
        # Log the email in the database
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Health Appointment (ID: {appointment_id})",
            student_id
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_appointment_confirmation)
        
        if result:
            log_event('info', f"Appointment confirmation email sent for appointment {appointment_id}")
        else:
            log_event('error', "Failed to send appointment confirmation email")
            
        return result
        
    except Exception as e:
        log_event('error', f"Error sending appointment confirmation email: {e}")
        return False



@handle_exception
def send_health_notification(student_id, advisory_title, advisory_description, severity):
    """Send a health advisory notification to a student"""
    def _send_health_notification(cursor):
        # Get the student's email address
        cursor.execute('SELECT email_address, first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()
        
        if not result:
            log_event('error', f"Could not find student with ID {student_id}")
            return False
        
        email_address, first_name, last_name = result
        
        subject, body = render_template('health_advisory', {
            'first_name': first_name,
            'last_name': last_name,
            'advisory_title': advisory_title,
            'severity': severity,
            'advisory_description': advisory_description
        })
        
        # Queue the email
        success = queue_email(email_address, subject, body)
        
        # Log the email in the database
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Health Advisory ({severity})",
            student_id
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_health_notification)
        
        if result:
            log_event('info', f"Health notification email sent to student {student_id}")
        else:
            log_event('error', "Failed to send health notification email")
            
        return result
        
    except Exception as e:
        log_event('error', f"Error sending health notification email: {e}")
        return False



@handle_exception
def send_internship_notification(student_id, internship_id, status, feedback=None):
    """Send a notification about an internship application status update"""
    def _send_internship_notification(cursor):
        # Get student and internship information
        cursor.execute('''
        SELECT s.email_address, s.first_name, s.last_name, i.title, i.company
        FROM students s
        JOIN internships i ON i.internship_id = ?
        WHERE s.student_id = ?
        ''', (internship_id, student_id))
        
        result = cursor.fetchone()
        
        if not result:
            log_event('error', "Could not find student or internship details")
            return False
        
        email_address, first_name, last_name, internship_title, company = result
        
        # Construct appropriate message based on status
        if status == 'approved':
            template_name="internships/internship_application_approved"
        elif status == 'rejected':
            template_name="internships/internship_application_rejected"
        else:
            template_name="internships/internship_application_status_update"

        subject, message = render_template(template_name, {
            "first_name": first_name,
            "last_name": last_name,
            "internship_title": internship_title,
            "company": company,
            "status": status
        })

        # Add feedback if provided
        if feedback and message:
            message += f"\n\nFeedback: {feedback}"
        
        # Queue the email
        success = queue_email(email_address, subject, message)
        
        # Log the email in the database
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Internship Update ({status})",
            student_id
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_internship_notification)
        
        if result:
            log_event('info', f"Internship notification email sent to student {student_id}")
        else:
            log_event('error', "Failed to send internship notification email")
            
        return result
        
    except Exception as e:
        log_event('error', f"Error sending internship notification: {e}")
        return False



@handle_exception
def send_application_confirmation(student_id, internship_id):
    """Send a confirmation email when a student applies for an internship"""
    def _send_application_confirmation(cursor):
        # Get student and internship information
        cursor.execute('''
        SELECT s.email_address, s.first_name, s.last_name, i.title, i.company, i.deadline_date
        FROM students s
        JOIN internships i ON i.internship_id = ?
        WHERE s.student_id = ?
        ''', (internship_id, student_id))
        
        result = cursor.fetchone()
        
        if not result:
            log_event('error', "Could not find student or internship details")
            return False
        
        email_address, first_name, last_name, internship_title, company, deadline = result
        
        # Construct message using template
        subject, message = render_template('internship_application_confirmed', {
            'first_name': first_name,
            'last_name': last_name,
            'internship_title': internship_title,
            'company': company,
            'deadline': deadline
        })
        
        # Queue the email
        success = queue_email(email_address, subject, message)
        
        # Log the email in the database
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Internship Application",
            student_id
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_application_confirmation)
        
        if result:
            log_event('info', f"Internship application confirmation email sent to student {student_id}")
        else:
            log_event('error', "Failed to send internship application confirmation email")
            
        return result
        
    except Exception as e:
        log_event('error', f"Error sending application confirmation: {e}")
        return False



@handle_exception
def send_alumni_welcome_email(alumni_id, email_address, full_name):
    """Send a welcome email to a newly registered alumni"""
    subject, message = render_template("alumni_welcome", {
        "full_name": full_name
    })

    # Queue the email
    success = queue_email(email_address, subject, message)
    
    # Log the email in the database
    def _log_alumni_email(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Alumni Welcome (ID: {alumni_id})"
        ))
        return True
    
    try:
        execute_db_operation(_log_alumni_email)
        
        if success:
            log_event('info', f"Alumni welcome email sent to {email_address}")
        else:
            log_event('error', f"Failed to send alumni welcome email to {email_address}")
        
        return success
        
    except Exception as e:
        log_event('error', f"Error sending alumni welcome email: {e}")
        return False



def send_mentorship_notification(mentor_email, mentee_email, mentor_name, mentee_name, focus_area, start_date, end_date=None):
    end_text = f" until {end_date}" if end_date else ""
    subject, body = render_template("mentorship_notification", {
        "mentor_name": mentor_name,
        "mentee_name": mentee_name,
        "focus_area": focus_area,
        "start_date": start_date,
        "end_text": end_text
    })

    send_email(mentor_email, subject, body)
    send_email(mentee_email, subject, body)



@handle_exception
def send_event_invitation(alumni_id, event_id=None, email_address=None, event_name=None, event_date=None, event_location=None):
    """Send an invitation to an alumni event"""
    def _send_event_invitation(cursor):
        # If only alumni_id and event_id are provided, fetch the other details from database
        if email_address is None or event_name is None or event_date is None or event_location is None:
            # Get alumni email
            if email_address is None:
                cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (alumni_id,))
                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find email for alumni ID {alumni_id}")
                    return False
                email_address = result[0]
            
            # Get event details
            if event_name is None or event_date is None or event_location is None:
                cursor.execute('''
                SELECT event_name, event_date, location 
                FROM alumni_events 
                WHERE event_id = ?
                ''', (event_id,))
                
                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find event details for event ID {event_id}")
                    return False
                
                event_name, event_date, event_location = result

        subject, message = render_template("alumni_event_invitation", {
            "event_name": event_name,
            "event_date": event_date,
            "event_location": event_location
        })

        # Queue the email
        success = queue_email(email_address, subject, message)
        
        # Log the email
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Event Invitation: {event_name}"
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_event_invitation)
        
        if result:
            log_event('info', f"Event invitation sent to {email_address} for event: {event_name}")
        else:
            log_event('error', f"Failed to send event invitation to {email_address}")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending event invitation: {e}")
        return False



@handle_exception
def send_donation_receipt(alumni_id, donation_id=None, email_address=None, amount=None, donation_date=None, purpose=None):
    """Send a receipt for an alumni donation"""
    def _send_donation_receipt(cursor):
        # If only alumni_id and donation_id are provided, fetch the other details from database
        if email_address is None or amount is None or donation_date is None:
            # Get alumni email
            if email_address is None:
                cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (alumni_id,))
                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find email for alumni ID {alumni_id}")
                    return False
                email_address = result[0]
            
            # Get donation details
            if amount is None or donation_date is None:
                cursor.execute('''
                SELECT amount, donation_date, purpose 
                FROM alumni_donations 
                WHERE donation_id = ?
                ''', (donation_id,))
                
                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find donation details for donation ID {donation_id}")
                    return False
                
                amount, donation_date, purpose = result

        purpose_text = f"\nDonation Purpose: {purpose}" if purpose else ""

        subject, message = render_template("donation_receipt", {
            "amount": f"{amount:.2f}",
            "donation_date": donation_date,
            "purpose_text": purpose_text
        })

        # Queue the email
        success = queue_email(email_address, subject, message)
        
        # Log the email
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email_address, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Donation Receipt: £{amount:.2f}"
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_donation_receipt)
        
        if result:
            log_event('info', f"Donation receipt sent to {email_address} for amount: £{amount:.2f}")
        else:
            log_event('error', f"Failed to send donation receipt to {email_address}")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending donation receipt: {e}")
        return False



@handle_exception
def send_permit_confirmation(permit_id, email, zone, permit_type, start_date, end_date):
    """Send a parking permit confirmation email"""
    subject, body = render_template('parking_permit_confirmation', {
        'permit_id': permit_id,
        'zone': zone,
        'zone_description': '',
        'permit_type': permit_type,
        'start_date': start_date,
        'end_date': end_date,
        'vehicle_info': '',
        'status': 'Active',
        'student_name': 'Permit Holder'
    })
    
    # Queue the email
    success = queue_email(email, subject, body)
    
    # Log the email
    def _log_permit_email(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Parking Permit Confirmation (ID: {permit_id})"
        ))
        return True
    
    try:
        execute_db_operation(_log_permit_email)
        
        if success:
            log_event('info', f"Permit confirmation email sent to {email}")
        else:
            log_event('error', f"Failed to send permit confirmation email to {email}")
        
        return success
        
    except Exception as e:
        log_event('error', f"Error sending permit confirmation: {e}")
        return False



@handle_exception
def send_permit_update_confirmation(permit_id, email, updated_fields):
    """Send a parking permit update confirmation email"""
    # Format the updated fields
    field_updates = "\n".join([f"- {field}: {value}" for field, value in updated_fields.items()])

    subject, body = render_template('parking_permit_updated', {
        'permit_id': permit_id,
        'updates': field_updates
    })
    
    # Queue the email
    success = queue_email(email, subject, body)
    
    # Log the email
    def _log_permit_update_email(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Parking Permit Update (ID: {permit_id})"
        ))
        return True
    
    try:
        execute_db_operation(_log_permit_update_email)
        
        if success:
            log_event('info', f"Permit update confirmation email sent to {email}")
        else:
            log_event('error', f"Failed to send permit update confirmation email to {email}")
        
        return success
        
    except Exception as e:
        log_event('error', f"Error sending permit update confirmation: {e}")
        return False



@handle_exception
def send_book_checkout_confirmation(user_id, book_id, book_title, due_date):
    """Send an email confirmation for a book checkout"""
    def _send_checkout_confirmation(cursor):
        # Get user email - first check students
        cursor.execute('''
        SELECT email_address, title, first_name, last_name
        FROM students WHERE student_id = ?
        ''', (user_id,))

        user_info = cursor.fetchone()

        if not user_info:
            # Check in users table by id
            cursor.execute('''
            SELECT email, '', username, role
            FROM users WHERE id = ?
            ''', (user_id,))
            user_info = cursor.fetchone()

        if not user_info:
            # Check in users table by username (for staff like "admin")
            cursor.execute('''
            SELECT email, '', first_name, last_name
            FROM users WHERE username = ?
            ''', (user_id,))
            user_info = cursor.fetchone()

        if not user_info:
            log_event('error', f"User {user_id} not found")
            return False

        email, title, first_name, last_name = user_info
        
        subject, body = render_template('library_book_checkout_confirmation', {
            'title': title or '',
            'first_name': first_name,
            'last_name': last_name,
            'book_title': book_title,
            'book_id': book_id,
            'due_date': due_date
        })
        
        # Queue the email
        success = queue_email(email, subject, body)
        
        # Log the email
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Book Checkout: {book_title}"
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_checkout_confirmation)
        
        if result:
            log_event('info', f"Checkout confirmation email sent for book {book_id}")
        else:
            log_event('error', f"Failed to send checkout confirmation email")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending book checkout confirmation: {e}")
        return False



@handle_exception
def send_book_return_reminder(user_id, book_id, book_title, due_date):
    """Send a reminder email for an upcoming book return date"""
    def _send_return_reminder(cursor):
        # Get user email - first check students
        cursor.execute('''
        SELECT email_address, title, first_name, last_name
        FROM students WHERE student_id = ?
        ''', (user_id,))

        user_info = cursor.fetchone()

        if not user_info:
            # Check in users table by id
            cursor.execute('''
            SELECT email, '', username, role
            FROM users WHERE id = ?
            ''', (user_id,))
            user_info = cursor.fetchone()

        if not user_info:
            # Check in users table by username (for staff like "admin")
            cursor.execute('''
            SELECT email, '', first_name, last_name
            FROM users WHERE username = ?
            ''', (user_id,))
            user_info = cursor.fetchone()

        if not user_info:
            log_event('error', f"User {user_id} not found")
            return False

        email, title, first_name, last_name = user_info
        
        subject, body = render_template('library_return_reminder', {
            'title': title or '',
            'first_name': first_name,
            'last_name': last_name,
            'book_title': book_title,
            'book_id': book_id,
            'due_date': due_date
        })
        
        # Queue the email
        success = queue_email(email, subject, body)
        
        # Log the email
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Book Return Reminder: {book_title}"
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_return_reminder)
        
        if result:
            log_event('info', f"Return reminder email sent for book {book_id}")
        else:
            log_event('error', f"Failed to send return reminder email")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending book return reminder: {e}")
        return False



@handle_exception
def send_overdue_notification(user_id, book_id, book_title, due_date, days_overdue):
    """Send a notification for an overdue book"""
    def _send_overdue_notification(cursor):
        # Get user email - first check students
        cursor.execute('''
        SELECT email_address, title, first_name, last_name
        FROM students WHERE student_id = ?
        ''', (user_id,))

        user_info = cursor.fetchone()

        if not user_info:
            # Check in users table by id
            cursor.execute('''
            SELECT email, '', username, role
            FROM users WHERE id = ?
            ''', (user_id,))
            user_info = cursor.fetchone()

        if not user_info:
            # Check in users table by username (for staff like "admin")
            cursor.execute('''
            SELECT email, '', first_name, last_name
            FROM users WHERE username = ?
            ''', (user_id,))
            user_info = cursor.fetchone()

        if not user_info:
            log_event('error', f"User {user_id} not found")
            return False

        email, title, first_name, last_name = user_info
        
        subject, body = render_template('library_overdue_notice', {
            'title': title or '',
            'first_name': first_name,
            'last_name': last_name,
            'book_title': book_title,
            'book_id': book_id,
            'days_overdue': days_overdue,
            'due_date': due_date
        })
        
        # Queue the email
        success = queue_email(email, subject, body)
        
        # Log the email
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email, 
            subject, 
            current_time,
            'sent' if success else 'failed',
            f"Overdue Notice: {book_title} ({days_overdue} days)"
        ))
        
        return success
    
    try:
        result = execute_db_operation(_send_overdue_notification)
        
        if result:
            log_event('info', f"Overdue notification email sent for book {book_id}")
        else:
            log_event('error', f"Failed to send overdue notification email")
        
        return result
        
    except Exception as e:
        log_event('error', f"Error sending overdue notification: {e}")
        return False



@handle_exception
def display_stored_emails_menu(auth=None):
    """Interactive menu to view stored emails

    Args:
        auth: Authentication object. If provided and user is not admin,
              only shows emails sent by the current user.
    """
    # Determine sender filter based on user role
    sender_filter = None
    is_admin = False
    if auth and auth.current_user:
        user_role = auth.current_user.get('role', '')
        is_admin = user_role == 'admin'
        if user_role in ('student', 'staff', 'instructor'):
            sender_filter = auth.current_user.get('email', '')

    while True:
        print("\n" + _t("email_service.stored_emails_title") + ":")
        print("=========================")
        if sender_filter:
            print(_t("email_service.showing_sent_only"))
        print("1. " + _t("email_service.view_recent"))
        print("2. " + _t("email_service.search_stored"))
        print("3. " + _t("email_service.view_email_details"))
        print("4. " + _t("email_service.delete_stored"))
        if is_admin:
            print("5. " + _t("email_service.clear_old"))
            print("6. " + _t("email_service.clear_all"))
            print("7. " + _t("email_service.export_csv"))
            print("8. " + _t("email_service.back_to_menu"))
        else:
            print("5. " + _t("email_service.export_csv"))
            print("6. " + _t("email_service.back_to_menu"))

        max_choice = 8 if is_admin else 6
        choice = input(f"Choose an option (1-{max_choice}): ")

        if choice == '1':
            # View recent emails
            emails_data = get_stored_emails(limit=20, sender_filter=sender_filter)
            
            if emails_data['emails']:
                print("\n" + _t("email_service.recent_stored", count=emails_data['total_count']) + ":")
                print("=" * 100)
                print(f"{'ID':<5}{_t('email_service.recipient'):<30}{_t('email_service.subject'):<35}{'Date':<20}{_t('email_service.template')}")
                print("-" * 100)

                for email in emails_data['emails']:
                    subject = email['subject'][:32] + "..." if len(email['subject']) > 32 else email['subject']
                    template = email['template_name'] or "Direct"

                    print(f"{email['id']:<5}{email['recipient_email']:<30}{subject:<35}{email['created_date']:<20}{template}")
            else:
                print(_t("email_service.no_stored_found"))
            
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            # Search emails
            search_term = input(_t("email_service.enter_recipient_search") + ": ")
            emails_data = get_stored_emails(limit=50, recipient_filter=search_term, sender_filter=sender_filter)

            if emails_data['emails']:
                print("\n" + _t("email_service.found_emails", count=len(emails_data['emails']), search=search_term) + ":")
                print("=" * 100)
                print(f"{'ID':<5}{_t('email_service.recipient'):<30}{_t('email_service.subject'):<35}{'Date':<20}{_t('email_service.template')}")
                print("-" * 100)

                for email in emails_data['emails']:
                    subject = email['subject'][:32] + "..." if len(email['subject']) > 32 else email['subject']
                    template = email['template_name'] or "Direct"

                    print(f"{email['id']:<5}{email['recipient_email']:<30}{subject:<35}{email['created_date']:<20}{template}")
            else:
                print(_t("email_service.not_found_for", search=search_term))
            
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            # View email details
            try:
                email_id = int(input("Enter email ID to view details: "))

                def _get_email_details(cursor):
                    query = '''
                    SELECT id, recipient_email, subject, body, sender_email, sender_name,
                           cc_recipients, bcc_recipients, attachment_paths, created_date,
                           template_name, template_vars, related_to, student_id
                    FROM stored_emails WHERE id = ?
                    '''
                    params = [email_id]
                    # For non-admin users, also verify they sent the email
                    if sender_filter:
                        query += ' AND sender_email = ?'
                        params.append(sender_filter)

                    cursor.execute(query, params)

                    result = cursor.fetchone()
                    if result:
                        return {
                            'id': result[0], 'recipient_email': result[1], 'subject': result[2],
                            'body': result[3], 'sender_email': result[4], 'sender_name': result[5],
                            'cc_recipients': result[6], 'bcc_recipients': result[7],
                            'attachment_paths': result[8], 'created_date': result[9],
                            'template_name': result[10], 'template_vars': result[11],
                            'related_to': result[12], 'student_id': result[13]
                        }
                    return None

                email = execute_db_operation(_get_email_details)

                if email:
                    print("\n" + _t("email_service.email_details", id=email['id']) + ":")
                    print("=" * 80)
                    print(f"{_t('email_service.from')}: {email['sender_name']} <{email['sender_email']}>")
                    print(f"{_t('email_service.to')}: {email['recipient_email']}")
                    if email['cc_recipients']:
                        print(f"{_t('email_service.cc')}: {email['cc_recipients']}")
                    if email['bcc_recipients']:
                        print(f"{_t('email_service.bcc')}: {email['bcc_recipients']}")
                    print(f"{_t('email_service.subject')}: {email['subject']}")
                    print(f"Date: {email['created_date']}")
                    if email['template_name']:
                        print(f"{_t('email_service.template')}: {email['template_name']}")
                    if email['attachment_paths']:
                        print(f"{_t('email_service.attachments')}: {email['attachment_paths']}")
                    print("-" * 80)
                    print(_t("email_service.body") + ":")
                    print(email['body'])
                    print("=" * 80)
                else:
                    print(_t("email_service.not_found_id", id=email_id))

            except ValueError:
                print(_t("email_service.invalid_email_id"))
            
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            # Delete email
            try:
                email_id = int(input("Enter email ID to delete: "))

                # For non-admin users, verify they own this email before deleting
                if sender_filter:
                    def _check_ownership(cursor):
                        cursor.execute(
                            'SELECT id FROM stored_emails WHERE id = ? AND sender_email = ?',
                            (email_id, sender_filter)
                        )
                        return cursor.fetchone() is not None

                    owns_email = execute_db_operation(_check_ownership)
                    if not owns_email:
                        print(_t("email_service.not_found_or_no_permission"))
                        input("\nPress Enter to continue...")
                        continue

                confirm = input(_t("email_service.confirm_delete", id=email_id) + " (y/n): ")

                if confirm.lower() == 'y':
                    if delete_stored_email(email_id):
                        print(_t("email_service.deleted_success"))
                    else:
                        print(_t("email_service.failed_delete"))
                else:
                    print(_t("email_service.deletion_cancelled"))

            except ValueError:
                print(_t("email_service.invalid_email_id"))

            input("\nPress Enter to continue...")

        elif choice == '5':
            if is_admin:
                # Clear old emails (admin only)
                try:
                    days = int(input("Delete emails older than how many days? "))
                    confirm = input(f"Delete all emails older than {days} days? (y/n): ")

                    if confirm.lower() == 'y':
                        deleted_count = clear_stored_emails(older_than_days=days)
                        print(_t("email_service.deleted_old", count=deleted_count))
                    else:
                        print(_t("email_service.operation_cancelled"))

                except ValueError:
                    print(_t("email_service.invalid_days"))

                input("\nPress Enter to continue...")
            else:
                # Export to CSV (non-admin option 5)
                try:
                    filename = input("Enter CSV filename (default: my_emails.csv): ") or "my_emails.csv"
                    emails_data = get_stored_emails(limit=10000, sender_filter=sender_filter)

                    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['id', 'recipient_email', 'subject', 'sender_email', 'sender_name',
                                    'cc_recipients', 'bcc_recipients', 'created_date', 'template_name', 'body']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                        writer.writeheader()
                        for email in emails_data['emails']:
                            writer.writerow({
                                'id': email['id'],
                                'recipient_email': email['recipient_email'],
                                'subject': email['subject'],
                                'sender_email': email['sender_email'],
                                'sender_name': email['sender_name'],
                                'cc_recipients': email['cc_recipients'],
                                'bcc_recipients': email['bcc_recipients'],
                                'created_date': email['created_date'],
                                'template_name': email['template_name'],
                                'body': email['body']
                            })

                    print(_t("email_service.exported_count", count=len(emails_data['emails']), filename=filename))

                except Exception as e:
                    print(_t("email_service.export_error", error=str(e)))

                input("\nPress Enter to continue...")

        elif choice == '6':
            if is_admin:
                # Clear all emails (admin only)
                confirm = input("Are you sure you want to delete ALL stored emails? (y/n): ")

                if confirm.lower() == 'y':
                    confirm2 = input("This action cannot be undone. Type 'DELETE ALL' to confirm: ")

                    if confirm2 == 'DELETE ALL':
                        deleted_count = clear_stored_emails()
                        print(_t("email_service.deleted_all", count=deleted_count))
                    else:
                        print(_t("email_service.operation_cancelled"))
                else:
                    print(_t("email_service.operation_cancelled"))

                input("\nPress Enter to continue...")
            else:
                # Back (non-admin option 6)
                break

        elif choice == '7' and is_admin:
            # Export to CSV (admin only)
            try:
                filename = input("Enter CSV filename (default: stored_emails.csv): ") or "stored_emails.csv"
                emails_data = get_stored_emails(limit=10000)  # Get all emails

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['id', 'recipient_email', 'subject', 'sender_email', 'sender_name',
                                'cc_recipients', 'bcc_recipients', 'created_date', 'template_name', 'body']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for email in emails_data['emails']:
                        writer.writerow({
                            'id': email['id'],
                            'recipient_email': email['recipient_email'],
                            'subject': email['subject'],
                            'sender_email': email['sender_email'],
                            'sender_name': email['sender_name'],
                            'cc_recipients': email['cc_recipients'],
                            'bcc_recipients': email['bcc_recipients'],
                            'created_date': email['created_date'],
                            'template_name': email['template_name'],
                            'body': email['body']
                        })

                print(_t("email_service.exported_count", count=len(emails_data['emails']), filename=filename))

            except Exception as e:
                print(_t("email_service.export_error", error=str(e)))

            input("\nPress Enter to continue...")

        elif choice == '8' and is_admin:
            break

        else:
            print(_t("email_service.invalid_choice"))



@handle_exception
def send_sla_alert(ticket_id, alert_type='overdue'):
    """Send SLA alert notifications for tickets"""
    def _send_sla_alert(cursor):
        # Get ticket and assignment information
        cursor.execute('''
        SELECT t.ticket_id, t.subject, t.priority, t.due_date, t.created_at,
               u1.username as submitter, u1.email as submitter_email,
               u2.username as assignee, u2.email as assignee_email,
               t.department
        FROM support_tickets t
        JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE t.ticket_id = ?
        ''', (ticket_id,))
        
        ticket_info = cursor.fetchone()
        
        if not ticket_info:
            log_event('error', f"Ticket {ticket_id} not found for SLA alert")
            return False
        
        ticket_id, subject, priority, due_date, created_at, submitter, submitter_email, assignee, assignee_email, department = ticket_info
        
        # Determine alert message based on type using templates
        template_vars = {
            'ticket_id': ticket_id,
            'subject': subject,
            'priority': priority.upper(),
            'due_date': due_date,
            'submitter': submitter,
            'submitter_email': submitter_email,
            'assignee': assignee or 'Unassigned',
            'department': department or 'None',
            'created_at': created_at
        }

        if alert_type == 'overdue':
            alert_subject, alert_body = render_template('sla_alert_overdue', template_vars)
        elif alert_type == 'escalation':
            alert_subject, alert_body = render_template('sla_alert_escalation', template_vars)
        else:
            alert_subject, alert_body = render_template('sla_alert_general', template_vars)
        
        # Send alerts to relevant parties
        recipients = []
        
        # Add assignee if available
        if assignee_email:
            recipients.append(assignee_email)
        
        # Add managers and admins
        cursor.execute('''
        SELECT DISTINCT u.email
        FROM users u
        LEFT JOIN departments d ON u.id = d.manager_id
        WHERE (u.role = 'admin' AND u.is_active = 1)
           OR (d.name = ? AND u.is_active = 1)
        ''', (department,))
        
        admin_emails = [row[0] for row in cursor.fetchall() if row[0]]
        recipients.extend(admin_emails)
        
        # Remove duplicates
        recipients = list(set(recipients))
        
        # Send alerts
        success_count = 0
        for recipient_email in recipients:
            if queue_email(recipient_email, alert_subject, alert_body):
                success_count += 1
        
        # Log the alert
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            f"SLA Alert ({len(recipients)} recipients)",
            alert_subject,
            current_time,
            'sent' if success_count > 0 else 'failed',
            f"SLA Alert for Ticket #{ticket_id}"
        ))
        
        return success_count > 0
    
    try:
        result = execute_db_operation(_send_sla_alert)
        if result:
            log_event('info', f"SLA alert sent for ticket #{ticket_id}")
        return result
    except Exception as e:
        log_event('error', f"Error sending SLA alert for ticket {ticket_id}: {e}")
        return False



@handle_exception
def send_satisfaction_survey(ticket_id, custom_message=None):
    """Send customer satisfaction survey for resolved tickets"""
    def _send_satisfaction_survey(cursor):
        # Get ticket and customer information
        # Use COALESCE to handle both old schema (title) and new schema (subject)
        cursor.execute('''
        SELECT t.ticket_id, COALESCE(t.subject, t.title) as subject,
               COALESCE(t.resolved_at, t.closed_at) as resolved_at, t.status,
               u.username, u.email, u.first_name, u.last_name
        FROM support_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.ticket_id = ?
        ''', (ticket_id,))

        ticket_info = cursor.fetchone()

        if not ticket_info:
            log_event('error', f"Ticket {ticket_id} not found for satisfaction survey")
            return False

        # Use different variable names to avoid shadowing the outer ticket_id
        tk_id, subject, resolved_at, status, username, email, first_name, last_name = ticket_info
        
        # Only send surveys for resolved/closed tickets
        if status not in ['resolved', 'closed']:
            log_event('warning', f"Cannot send satisfaction survey for ticket {ticket_id} - status is {status}")
            return False
        
        # Create survey
        customer_name = f"{first_name} {last_name}".strip() if first_name or last_name else username

        if custom_message:
            survey_subject = f"How did we do? Feedback requested for Ticket #{ticket_id}"
            survey_body = custom_message
        else:
            survey_subject, survey_body = render_template('satisfaction_survey', {
                'customer_name': customer_name,
                'ticket_id': ticket_id,
                'subject': subject,
                'resolved_at': resolved_at
            })
        
        # Send the survey
        success = queue_email(email, survey_subject, survey_body)
        
        if success:
            # Log the survey send
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                email,
                survey_subject,
                current_time,
                'sent',
                f"Satisfaction Survey for Ticket #{ticket_id}",
                None
            ))
            
            # Mark that survey was sent (you could add a field to track this)
            # For now, we'll just log it
            log_event('info', f"Satisfaction survey sent for ticket #{ticket_id} to {email}")
        
        return success
    
    try:
        result = execute_db_operation(_send_satisfaction_survey)
        if result:
            log_event('info', f"Satisfaction survey sent for ticket #{ticket_id}")
        return result
    except Exception as e:
        log_event('error', f"Error sending satisfaction survey for ticket {ticket_id}: {e}")
        return False



@handle_exception
def send_bulk_satisfaction_surveys(days_old=1):
    """Send satisfaction surveys for tickets resolved in the last N days"""
    def _send_bulk_surveys(cursor):
        # Find recently resolved tickets that don't have surveys sent yet
        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        SELECT t.ticket_id
        FROM support_tickets t
        WHERE t.status IN ('resolved', 'closed')
          AND t.resolved_at >= ?
          AND t.ticket_id NOT IN (
              SELECT DISTINCT CAST(SUBSTR(related_to, 
                  INSTR(related_to, '#') + 1, 
                  INSTR(related_to || ' ', ' ') - INSTR(related_to, '#') - 1
              ) AS INTEGER)
              FROM email_log 
              WHERE related_to LIKE 'Satisfaction Survey for Ticket #%'
          )
        ''', (cutoff_date,))
        
        ticket_ids = [row[0] for row in cursor.fetchall()]
        
        success_count = 0
        for ticket_id in ticket_ids:
            if send_satisfaction_survey(ticket_id):
                success_count += 1
        
        return success_count, len(ticket_ids)
    
    try:
        result = execute_db_operation(_send_bulk_surveys)
        if result:
            success_count, total_count = result
            log_event('info', f"Bulk satisfaction surveys: {success_count}/{total_count} sent successfully")
        return result
    except Exception as e:
        log_event('error', f"Error sending bulk satisfaction surveys: {e}")
        return 0, 0



def fix_existing_email_senders():
    """Fix existing emails that show 'system' as sender when they should show actual users"""
    
    def _fix_senders(cursor):
        # Find messages from generic 'system' users that could be attributed to real users
        cursor.execute('''
        SELECT m.id, m.subject, m.sent_at, m.sender_id, u.username as current_sender,
               se.sender_name, se.sender_email
        FROM messages m
        JOIN users u ON m.sender_id = u.id
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
        dashboard = CommunicationDashboard(auth=_auth)
        inbox = dashboard.get_inbox(limit=5)

        print("\n" + _t("email_service.recent_inbox_messages") + ":")
        for i, msg in enumerate(inbox.get('messages', [])[:5], 1):
            print(f"  {i}. {_t('email_service.from')}: '{msg['sender']}' - {_t('email_service.subject')}: '{msg['subject'][:50]}...'")

        return True
    else:
        print(_t("email_service.failed_test_emails"))
        return False


# ============================================================================
# Schedule Change Notifications for Module Scheduling System
# ============================================================================

def send_schedule_change_notification(schedule_id: int, old_data: dict, new_data: dict) -> bool:
    """
    Send notifications for schedule changes to affected students and staff.

    Args:
        schedule_id: The schedule entry ID
        old_data: Dictionary with old schedule data (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
        new_data: Dictionary with new schedule data

    Returns:
        True if notifications were sent successfully
    """
    try:
        from university_system.infrastructure.database.db import get_connection
        from university_system.modules.shared.utils.activity_logger import log_activity

        module_code = old_data.get('module_code')
        if not module_code:
            return False

        # Get module information
        module_info = _get_module_info(module_code)
        if not module_info:
            return False

        # Determine what changed
        changes = []
        datetime_changed = False
        instructor_changed = False
        room_changed = False

        if (old_data.get('day_of_week') != new_data.get('day_of_week') or
            old_data.get('start_time') != new_data.get('start_time') or
            old_data.get('end_time') != new_data.get('end_time')):
            datetime_changed = True
            changes.append('date/time')

        if old_data.get('instructor_id') != new_data.get('instructor_id'):
            instructor_changed = True
            changes.append('instructor')

        if old_data.get('room_id') != new_data.get('room_id'):
            room_changed = True
            changes.append('room')

        if not changes:
            return True  # No notification needed

        # Get recipients
        students = _get_enrolled_students(module_code)
        staff = _get_module_staff(module_code)

        # Send appropriate notifications
        success = True

        if datetime_changed:
            success = success and _notify_datetime_change(
                students + staff, module_info, old_data, new_data
            )

        if instructor_changed:
            success = success and _notify_instructor_change(
                students, module_info, old_data, new_data
            )

            # Notify new instructor
            new_instructor_id = new_data.get('instructor_id')
            if new_instructor_id:
                success = success and _notify_new_instructor_assignment(
                    new_instructor_id, module_info, new_data
                )

        if room_changed:
            success = success and _notify_room_change(
                students + staff, module_info, old_data, new_data
            )

        # Log the notification activity
        log_activity(
            'notify',
            'schedule_change',
            details={
                'schedule_id': schedule_id,
                'module_code': module_code,
                'changes': ', '.join(changes),
                'recipients': len(students) + len(staff)
            }
        )

        return success

    except (smtplib.SMTPException, EmailDeliveryError) as e:
        log_event('error', f"Email delivery error sending schedule change notifications: {e}")
        return False
    except sqlite3.Error as e:
        log_event('error', f"Database error sending schedule change notifications: {e}")
        return False


def _get_module_info(module_code: str) -> dict | None:
    """Get module information from database"""
    try:
        from university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT module_code, module_name, credits
                FROM modules
                WHERE module_code = ?
            ''', (module_code,))
            row = cursor.fetchone()

            if row:
                return {
                    'module_code': row[0],
                    'module_name': row[1] if row[1] else row[0],
                    'credits': row[2] if row[2] else 'N/A'
                }
    except sqlite3.Error as e:
        log_event('error', f"Database error getting module info: {e}")
    return None


def _get_room_location(room_id: int | None) -> str:
    """Get room location string"""
    if not room_id:
        return "TBA"

    try:
        from university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT building, room_number
                FROM rooms
                WHERE id = ?
            ''', (room_id,))
            row = cursor.fetchone()

            if row and row[0] and row[1]:
                return f"{row[0]}-{row[1]}"
    except sqlite3.Error as e:
        log_event('error', f"Database error getting room location: {e}")

    return "TBA"


def _get_instructor_info(instructor_id: int | None) -> dict:
    """Get instructor information"""
    if not instructor_id:
        return {'name': 'TBA', 'email': ''}

    try:
        from university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT first_name, last_name, email
                FROM instructors
                WHERE id = ?
            ''', (instructor_id,))
            row = cursor.fetchone()

            if row:
                return {
                    'name': f"{row[0]} {row[1]}",
                    'email': row[2] if row[2] else ''
                }
    except sqlite3.Error as e:
        log_event('error', f"Database error getting instructor info: {e}")

    return {'name': 'TBA', 'email': ''}


def _get_enrolled_students(module_code: str) -> list:
    """Get list of students enrolled in a module"""
    students = []
    try:
        from university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                INNER JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ? AND sm.status = 'Enrolled'
            ''', (module_code,))

            for row in cursor.fetchall():
                if row[3]:  # Has email
                    students.append({
                        'student_id': row[0],
                        'name': f"{row[1]} {row[2]}",
                        'email': row[3]
                    })
    except sqlite3.Error as e:
        log_event('error', f"Database error getting enrolled students: {e}")

    return students


def _get_module_staff(module_code: str) -> list:
    """Get staff associated with a module (via schedules)"""
    staff = []
    try:
        from university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT i.id, i.first_name, i.last_name, i.email
                FROM instructors i
                INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                WHERE ms.module_code = ?
            ''', (module_code,))

            for row in cursor.fetchall():
                if row[3]:  # Has email
                    staff.append({
                        'instructor_id': row[0],
                        'name': f"{row[1]} {row[2]}",
                        'email': row[3]
                    })
    except sqlite3.Error as e:
        log_event('error', f"Database error getting module staff: {e}")

    return staff


def _notify_datetime_change(recipients: list, module_info: dict, old_data: dict, new_data: dict) -> bool:
    """Send date/time change notifications"""
    old_room = _get_room_location(old_data.get('room_id'))

    for recipient in recipients:
        try:
            variables = {
                'recipient_name': recipient['name'],
                'module_code': module_info['module_code'],
                'module_name': module_info['module_name'],
                'old_day': old_data.get('day_of_week', 'TBA'),
                'old_start_time': old_data.get('start_time', 'TBA'),
                'old_end_time': old_data.get('end_time', 'TBA'),
                'new_day': new_data.get('day_of_week', 'TBA'),
                'new_start_time': new_data.get('start_time', 'TBA'),
                'new_end_time': new_data.get('end_time', 'TBA'),
                'room_location': old_room,
                'session_type': old_data.get('session_type', 'Session'),
                'instructor_name': _get_instructor_info(old_data.get('instructor_id'))['name'],
                'coordinator_email': 'coordinator@university.edu',
                'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
            }

            # Load and render template
            template = load_template('academics/schedule_change_datetime')
            if template:
                subject = template.get('subject', 'Schedule Change Notification')
                body = template.get('body', 'A schedule change has occurred.')

                # Replace variables
                for key, value in variables.items():
                    subject = subject.replace(f'${key}', str(value))
                    body = body.replace(f'${key}', str(value))
            else:
                subject = f"Schedule Change - {module_info['module_code']}: Date/Time Updated"
                body = f"Dear {recipient['name']},\n\nThe schedule for {module_info['module_code']} has changed.\n\nOld: {old_data.get('day_of_week')} at {old_data.get('start_time')}\nNew: {new_data.get('day_of_week')} at {new_data.get('start_time')}"

            send_email(recipient['email'], subject, body)

        except (smtplib.SMTPException, EmailDeliveryError) as e:
            log_event('error', f"Email error sending datetime change to {recipient['email']}: {e}")
            return False
        except (TemplateError, KeyError) as e:
            log_event('error', f"Template error sending datetime change to {recipient['email']}: {e}")
            return False

    return True


def _notify_instructor_change(recipients: list, module_info: dict, old_data: dict, new_data: dict) -> bool:
    """Send instructor change notifications"""
    old_instructor = _get_instructor_info(old_data.get('instructor_id'))
    new_instructor = _get_instructor_info(new_data.get('instructor_id'))
    room_location = _get_room_location(new_data.get('room_id'))

    for recipient in recipients:
        try:
            variables = {
                'recipient_name': recipient['name'],
                'module_code': module_info['module_code'],
                'module_name': module_info['module_name'],
                'day_of_week': new_data.get('day_of_week', 'TBA'),
                'start_time': new_data.get('start_time', 'TBA'),
                'end_time': new_data.get('end_time', 'TBA'),
                'room_location': room_location,
                'session_type': new_data.get('session_type', 'Session'),
                'old_instructor_name': old_instructor['name'],
                'new_instructor_name': new_instructor['name'],
                'new_instructor_email': new_instructor['email'] or 'TBA',
                'coordinator_email': 'coordinator@university.edu',
                'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
            }

            template = load_template('academics/schedule_change_instructor')
            if template:
                subject = template.get('subject', 'Schedule Change Notification')
                body = template.get('body', 'An instructor change has occurred.')

                for key, value in variables.items():
                    subject = subject.replace(f'${key}', str(value))
                    body = body.replace(f'${key}', str(value))
            else:
                subject = f"Schedule Change - {module_info['module_code']}: Instructor Updated"
                body = f"Dear {recipient['name']},\n\nThe instructor for {module_info['module_code']} has changed.\n\nOld: {old_instructor['name']}\nNew: {new_instructor['name']}"

            send_email(recipient['email'], subject, body)

        except Exception as e:
            log_event('error', f"Error sending instructor change email to {recipient['email']}: {e}")
            return False

    return True


def _notify_room_change(recipients: list, module_info: dict, old_data: dict, new_data: dict) -> bool:
    """Send room change notifications"""
    old_room = _get_room_location(old_data.get('room_id'))
    new_room = _get_room_location(new_data.get('room_id'))
    instructor_info = _get_instructor_info(new_data.get('instructor_id'))

    for recipient in recipients:
        try:
            variables = {
                'recipient_name': recipient['name'],
                'module_code': module_info['module_code'],
                'module_name': module_info['module_name'],
                'day_of_week': new_data.get('day_of_week', 'TBA'),
                'start_time': new_data.get('start_time', 'TBA'),
                'end_time': new_data.get('end_time', 'TBA'),
                'session_type': new_data.get('session_type', 'Session'),
                'instructor_name': instructor_info['name'],
                'old_room_location': old_room,
                'new_room_location': new_room,
                'coordinator_email': 'coordinator@university.edu',
                'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
            }

            template = load_template('academics/schedule_change_room')
            if template:
                subject = template.get('subject', 'Schedule Change Notification')
                body = template.get('body', 'A room change has occurred.')

                for key, value in variables.items():
                    subject = subject.replace(f'${key}', str(value))
                    body = body.replace(f'${key}', str(value))
            else:
                subject = f"Schedule Change - {module_info['module_code']}: Room Updated"
                body = f"Dear {recipient['name']},\n\nThe room for {module_info['module_code']} has changed.\n\nOld: {old_room}\nNew: {new_room}"

            send_email(recipient['email'], subject, body)

        except Exception as e:
            log_event('error', f"Error sending room change email to {recipient['email']}: {e}")
            return False

    return True


def _notify_new_instructor_assignment(instructor_id: int, module_info: dict, schedule_data: dict) -> bool:
    """Notify a newly assigned instructor"""
    instructor_info = _get_instructor_info(instructor_id)
    if not instructor_info['email']:
        return True  # No email to send to

    room_location = _get_room_location(schedule_data.get('room_id'))

    # Get student count
    student_count = 0
    try:
        from university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM enrollments
                WHERE module_code = ? AND status = 'enrolled'
            ''', (module_info['module_code'],))
            row = cursor.fetchone()
            if row:
                student_count = row[0]
    except Exception:
        pass

    try:
        variables = {
            'instructor_name': instructor_info['name'],
            'module_code': module_info['module_code'],
            'module_name': module_info['module_name'],
            'session_type': schedule_data.get('session_type', 'Session'),
            'day_of_week': schedule_data.get('day_of_week', 'TBA'),
            'start_time': schedule_data.get('start_time', 'TBA'),
            'end_time': schedule_data.get('end_time', 'TBA'),
            'room_location': room_location,
            'student_count': str(student_count),
            'hod_email': 'hod@university.edu',
            'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
        }

        template = load_template('academics/instructor_assignment_notification')
        if template:
            subject = template.get('subject', 'New Module Assignment')
            body = template.get('body', 'You have been assigned to teach a module.')

            for key, value in variables.items():
                subject = subject.replace(f'${key}', str(value))
                body = body.replace(f'${key}', str(value))
        else:
            subject = f"New Module Assignment - {module_info['module_code']}"
            body = f"Dear {instructor_info['name']},\n\nYou have been assigned to teach {module_info['module_code']} on {schedule_data.get('day_of_week')} at {schedule_data.get('start_time')}."

        send_email(instructor_info['email'], subject, body)
        return True

    except Exception as e:
        log_event('error', f"Error sending instructor assignment email: {e}")
        return False
