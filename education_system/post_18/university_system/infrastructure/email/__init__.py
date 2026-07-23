"""High-level convenience exports for the email infrastructure package."""

from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.email_service import (
    queue_email,
    queue_template_email,
    send_email as _real_send_email,
    send_template_email,
)
from education_system.post_18.university_system.infrastructure.email import email_service as _email_service_module


def send_email(*args, **kwargs):
    """Compatibility wrapper around ``email_service.core.send_email``.

    Historically two parallel ``send_email`` implementations existed:
    one in ``email_service.core`` (the real one — recipient kwarg
    ``recipient_email``) and a no-op queue stub in ``email_manager``
    (kwarg ``recipient``). Callers split roughly 50/50 between the two
    spellings. This wrapper accepts either so both populations keep
    working after the package facade was fixed to expose only the real
    implementation."""
    if "recipient" in kwargs and "recipient_email" not in kwargs:
        kwargs["recipient_email"] = kwargs.pop("recipient")
    return _real_send_email(*args, **kwargs)
from education_system.post_18.university_system.infrastructure.email.admin import (
    initialize_communication_system,
    set_auth,
)
# Export new dependency injection classes for cleaner architecture
from education_system.post_18.university_system.infrastructure.email.smtp import (
    SMTPClient,
    SMTPConfig,
    EmailService,
)


def _insert_inbox_message_with_legacy_support(cursor, sender_id, recipient_id, subject, body, attachments, current_time):
    """Insert inbox messages while tolerating legacy schemas."""
    cursor.execute('PRAGMA table_info(messages)')
    message_columns = {row[1] for row in cursor.fetchall()}

    insert_columns = ['sender_id', 'recipient_id', 'subject']
    insert_values = [sender_id, recipient_id, subject]

    if 'message' in message_columns:
        insert_columns.append('message')
        insert_values.append(body)
    if 'content' in message_columns:
        insert_columns.append('content')
        insert_values.append(body)

    if 'attachment_path' in message_columns:
        insert_columns.append('attachment_path')
        insert_values.append(attachments)

    if 'is_read' in message_columns and 'is_read' not in insert_columns:
        insert_columns.append('is_read')
        insert_values.append(0)

    if 'sent_at' in message_columns:
        insert_columns.append('sent_at')
        insert_values.append(current_time)

    if 'assignment_id' in message_columns:
        insert_columns.append('assignment_id')
        insert_values.append(None)

    if 'reply_to' in message_columns:
        insert_columns.append('reply_to')
        insert_values.append(None)

    placeholders = ', '.join('?' for _ in insert_columns)
    column_list = ', '.join(insert_columns)
    cursor.execute(f'INSERT INTO messages ({column_list}) VALUES ({placeholders})', insert_values)


def _patched_send_email_db_only(recipient_email, subject, body, cc, bcc, attachments, current_time):
    """Patched version that supports legacy message schemas when storing emails."""
    _email_service_module._ensure_db_ready()

    def _store_email(cursor):
        sender_email = _email_service_module.config.get('sender_email', "noreply@university.edu")
        sender_name = _email_service_module.config.get('sender_name', "University System")

        # If there's a logged-in user, use their details from the university DB
        current_auth = _email_service_module._get_current_auth()
        if current_auth and hasattr(current_auth, 'current_user') and current_auth.current_user:
            username = current_auth.current_user.get('username')
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
                        sender_name = username

        cursor.execute('PRAGMA table_info(stored_emails)')
        stored_email_columns = {row[1] for row in cursor.fetchall()}
        stored_email_values = {
            'recipient_email': recipient_email,
            'subject': subject,
            'body': body,
            'sender_email': sender_email,
            'sender_name': sender_name,
            'cc_recipients': cc,
            'bcc_recipients': bcc,
            'attachment_paths': attachments,
            'created_date': current_time,
            'sent_date': current_time,
            'status': 'sent',
            'cc': cc,
            'bcc': bcc,
        }
        insertable_columns = [name for name in stored_email_values if name in stored_email_columns]
        if insertable_columns:
            placeholders = ', '.join('?' for _ in insertable_columns)
            column_list = ', '.join(insertable_columns)
            cursor.execute(
                f'INSERT INTO stored_emails ({column_list}) VALUES ({placeholders})',
                [stored_email_values[name] for name in insertable_columns],
            )
        else:
            cursor.execute(
                'INSERT INTO stored_emails (recipient_email, subject, body) VALUES (?, ?, ?)',
                (recipient_email, subject, body),
            )

        cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
        user_row = cursor.fetchone()

        if user_row:
            recipient_id = user_row[0]

            sender_id = None
            try:
                sender_id = _email_service_module.get_appropriate_sender_id(cursor, sender_email, sender_name, current_time)
            except Exception as exc:  # pragma: no cover - fallback logging only
                _email_service_module.log_event('warning', f"get_appropriate_sender_id failed, falling back: {exc}")

            if not sender_id:
                try:
                    system_username = _email_service_module.generate_system_username(sender_name, sender_email)
                    cursor.execute("SELECT id FROM users WHERE username = ? AND role = 'admin'", (system_username,))
                    row = cursor.fetchone()
                    if row:
                        sender_id = row[0]
                    else:
                        parts = sender_name.split(' ', 1)
                        first = parts[0] if parts else sender_name
                        last = parts[1] if len(parts) > 1 else ''
                        cursor.execute('''
                            INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (system_username, first, last, sender_email, 'admin', current_time, current_time))
                        sender_id = cursor.lastrowid
                except Exception as exc:  # pragma: no cover - fallback logging only
                    _email_service_module.log_event('warning', f"System sender fallback failed: {exc}")

            if not sender_id:
                sender_id = recipient_id

            _insert_inbox_message_with_legacy_support(cursor, sender_id, recipient_id, subject, body, attachments, current_time)
        else:
            _email_service_module.log_event('info', f"Email stored for {recipient_email}, but no matching user account found.")

        try:
            cursor.execute('''
                INSERT INTO email_log
                    (recipient, subject, sent_date, status, sender_email, sender_name,
                     cc_recipients, bcc_recipients, attachment_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (recipient_email, subject, current_time, 'stored', sender_email, sender_name,
                  cc, bcc, attachments))
        except Exception as exc:
            _email_service_module.log_event('warning', f"Extended email_log insert failed, falling back: {exc}")
            try:
                cursor.execute('''
                    INSERT INTO email_log (recipient, subject, sent_date, status, sender_email)
                    VALUES (?, ?, ?, ?, ?)
                ''', (recipient_email, subject, current_time, 'stored', sender_email))
            except Exception as fallback_exc:
                _email_service_module.log_event(
                    'error',
                    f"Fallback email_log insert also failed; email not recorded: "
                    f"{fallback_exc}")

        try:
            cursor.connection.commit()
        except Exception as exc:  # pragma: no cover - non-critical warning
            _email_service_module.log_event('warning', f"Explicit commit failed (connection may auto-commit on close): {exc}")

        return True

    try:
        return _email_service_module.execute_db_operation(_store_email)
    except Exception as exc:
        _email_service_module.log_event('error', f"Error storing email: {exc}")
        return False


_email_service_module.send_email_db_only = _patched_send_email_db_only
send_email_db_only = _patched_send_email_db_only


def send_email_notification(recipient_email: str, subject: str, message: str, **kwargs):
    """Backwards-compatible helper that forwards to ``send_email``."""
    return send_email(recipient_email, subject, message, **kwargs)


__all__ = [
    'send_email',
    'queue_email',
    'send_template_email',
    'queue_template_email',
    'send_email_notification',
    'initialize_communication_system',
    'set_auth',
    # Dependency injection classes
    'SMTPClient',
    'SMTPConfig',
    'EmailService',
    # Email fallback/degradation
    'EmailServiceWithFallback',
    'EmailServiceUnavailable',
    'Email',
    'SendResult',
    'SendStatus',
    'CircuitBreaker',
    'FallbackQueue',
    'calculate_retry_time',
]

# Email fallback and graceful degradation
try:
    from education_system.post_18.university_system.infrastructure.email.email_fallback import (
        EmailServiceWithFallback,
        EmailServiceUnavailable,
        Email,
        SendResult,
        SendStatus,
        CircuitBreaker,
        FallbackQueue,
        calculate_retry_time,
    )
except ImportError as e:
    # Log but don't fail if email_fallback has import issues
    import logging
    logging.getLogger(__name__).warning(f"Could not import email_fallback: {e}")

# Import the legacy compatibility facade so callers can access the broader
# email subsystem (templates, admin helpers, etc.) directly from this
# package, matching historical behaviour.
#
# IMPORTANT: only export names from email_manager that aren't already
# bound at this point. Several names (notably ``send_email``) exist in
# both modules — the implementations in email_manager are no-op queue
# stubs that just append to an in-process Python list, while the ones
# already imported from email_service.core actually persist to the
# inbox / SMTP. Letting the loop overwrite them silently broke every
# caller that expected `from infrastructure.email import send_email` to
# deliver mail. (Was the cause of the council emails never showing up.)
from education_system.post_18.university_system.infrastructure.email import email_manager as _email_manager  # noqa: E402  (import after __all__ setup)

_already_bound = set(globals())
for _name in getattr(_email_manager, "__all__", []):
    if _name in _already_bound:
        continue  # don't clobber the real implementation
    globals()[_name] = getattr(_email_manager, _name)
    if _name not in __all__:
        __all__.append(_name)

del _name, _email_manager, _already_bound

# Additionally expose selected helper functions directly from the email_service
# module.  Certain parts of the application import these helpers from the
# ``university_system.infrastructure.email`` package.  Only assign names
# that exist on the underlying module; missing attributes are ignored.
for _helper in [
    'send_confirmation_email',
    'send_appointment_confirmation',
    'send_book_checkout_confirmation',
    'send_book_return_reminder',
    'send_overdue_notification',
    'send_health_notification',
    'send_internship_notification',
    'send_application_confirmation',
    'send_alumni_welcome_email',
    'send_mentorship_notification',
    'send_event_invitation',
    'send_donation_receipt',
    'send_permit_confirmation',
    'send_permit_update_confirmation',
    'send_sla_alert',
    'send_satisfaction_survey',
    'send_bulk_satisfaction_surveys',
    'send_grade_notification',
    'send_password_reset',
    'send_assignment_notification',
    'send_extension_notification',
    'send_reply_notification',
    'send_ticket_notification',
    'send_update_confirmation',
    'send_registration_confirmation',
    'send_bulk',
    'schedule_send',
    'process_scheduled_emails',
    'ensure_scheduler_running',
    'run_scheduler',
    'update_scheduled_email_status',
]:
    try:
        globals()[_helper] = getattr(_email_service_module, _helper)
        if _helper not in __all__:
            __all__.append(_helper)
    except AttributeError:
        # Skip missing helpers silently
        pass

del _helper
