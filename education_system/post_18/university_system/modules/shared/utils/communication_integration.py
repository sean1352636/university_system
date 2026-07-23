"""Communication Integration Utility

This module provides unified wrappers for all communication methods,
integrating standalone systems with central infrastructure.

Use this module to send emails, SMS, and notifications across the university system.
All communications are logged to the central database for audit and compliance.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level imports from infrastructure services.
# These are imported at module level so that they can be patched in tests.
# If the infrastructure packages are unavailable (e.g. during isolated unit
# testing) we fall back to None; the wrapper functions below handle the
# ImportError case gracefully.
# ---------------------------------------------------------------------------

try:
    from education_system.post_18.university_system.infrastructure.email.email_service import (
        send_email,
        send_template_email,
        send_email_as_system,
        queue_email,
    )
    from education_system.post_18.university_system.infrastructure.email.email_service import (
        send_bulk,
    )
except ImportError:
    send_email = None  # type: ignore[assignment]
    send_template_email = None  # type: ignore[assignment]
    send_email_as_system = None  # type: ignore[assignment]
    queue_email = None  # type: ignore[assignment]
    send_bulk = None  # type: ignore[assignment]

try:
    from education_system.post_18.university_system.infrastructure.communication.sms_service import (
        send_sms,
    )
except ImportError:
    send_sms = None  # type: ignore[assignment]

try:
    from education_system.post_18.university_system.infrastructure.communication.sms_service import (
        send_bulk_sms,
    )
except ImportError:
    send_bulk_sms = None  # type: ignore[assignment]

try:
    from education_system.post_18.university_system.infrastructure.email.template_utils import (
        render_template,
    )
except ImportError:
    render_template = None  # type: ignore[assignment]


# ============================================================================
# EMAIL INTEGRATION
# ============================================================================

def send_email_unified(
    recipient: str,
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    attachments: Optional[List[str]] = None,
    template_name: Optional[str] = None,
    template_vars: Optional[Dict[str, Any]] = None,
    sender_type: str = 'system',
    **kwargs
) -> bool:
    """
    Send email via central infrastructure.

    This function integrates all email sending into the central email service,
    replacing standalone SMTP implementations across the codebase.

    Args:
        recipient: Email address
        subject: Email subject
        body: Email body (plain text or HTML)
        cc: CC recipients
        bcc: BCC recipients
        attachments: List of attachment file paths
        template_name: Email template name (if using templates)
        template_vars: Variables for template rendering
        sender_type: 'system', 'user', or 'custom'
        **kwargs: Additional parameters

    Returns:
        bool: True if email sent/queued successfully

    Examples:
        # Simple email
        send_email_unified(
            'student@example.com',
            'Welcome',
            'Welcome to the university!'
        )

        # Template email
        send_email_unified(
            'student@example.com',
            'Grade Notification',
            '',
            template_name='academics/grade_notification',
            template_vars={'grade': 'A', 'module': 'CS101'}
        )
    """
    try:
        # Use template if provided
        if template_name and template_vars:
            return send_template_email(
                template_name,
                recipient,
                template_vars,
                cc=cc,
                bcc=bcc,
                attachments=attachments
            )

        # Send via appropriate method based on sender_type
        if sender_type == 'system':
            return send_email_as_system(
                recipient,
                subject,
                body,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                **kwargs
            )
        else:
            return send_email(
                recipient,
                subject,
                body,
                cc=cc,
                bcc=bcc,
                attachments=attachments
            )

    except Exception as e:
        logger.error(f"Error sending email via central infrastructure: {e}")
        # Fallback: log to console
        print(f"[EMAIL FALLBACK] To: {recipient}")
        print(f"[EMAIL FALLBACK] Subject: {subject}")
        print(f"[EMAIL FALLBACK] Body: {body[:100]}...")
        return False


def send_bulk_email_unified(
    recipients: List[str],
    template_name: str,
    template_vars_list: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Dict[str, int]:
    """
    Send bulk emails via central infrastructure.

    Args:
        recipients: List of email addresses
        template_name: Email template name
        template_vars_list: List of template variables (one per recipient)
        **kwargs: Additional parameters

    Returns:
        dict: {'sent': count, 'failed': count}
    """
    try:
        result = send_bulk(recipients, template_name, template_vars_list, **kwargs)
        return {'sent': len(recipients), 'failed': 0}  # send_bulk doesn't return counts

    except Exception as e:
        logger.error(f"Error sending bulk email: {e}")
        return {'sent': 0, 'failed': len(recipients)}


def queue_email_unified(
    recipient: str,
    subject: str,
    body: str,
    **kwargs
) -> bool:
    """
    Queue email for asynchronous sending.

    Args:
        recipient: Email address
        subject: Email subject
        body: Email body
        **kwargs: Additional parameters

    Returns:
        bool: True if queued successfully
    """
    try:
        queue_email(recipient, subject, body, **kwargs)
        return True

    except Exception as e:
        logger.error(f"Error queueing email: {e}")
        return False


# ============================================================================
# SMS INTEGRATION
# ============================================================================

def send_sms_unified(
    phone_number: str,
    message: str,
    student_id: Optional[str] = None,
    related_to: Optional[str] = None,
    provider: str = 'mock'
) -> bool:
    """
    Send SMS via central infrastructure.

    This function integrates all SMS sending (except MFA) into the central
    SMS service, replacing standalone Twilio/AWS SNS implementations.

    Args:
        phone_number: Recipient phone number (E.164 format recommended)
        message: SMS message content (max 1600 chars)
        student_id: Student ID for logging
        related_to: What this SMS relates to (e.g., 'calendar_reminder')
        provider: 'twilio', 'aws_sns', or 'mock' (default: mock for safety)

    Returns:
        bool: True if SMS sent successfully

    Examples:
        # Simple SMS
        send_sms_unified(
            '+447123456789',
            'Your appointment is tomorrow at 2pm'
        )

        # With logging
        send_sms_unified(
            '+447123456789',
            'Class cancelled',
            student_id='STU001',
            related_to='calendar_notification'
        )
    """
    try:
        return send_sms(
            phone_number,
            message,
            student_id=student_id,
            related_to=related_to
        )

    except Exception as e:
        logger.error(f"Error sending SMS via central infrastructure: {e}")
        # Fallback: log to console
        print(f"[SMS FALLBACK] To: {phone_number}")
        print(f"[SMS FALLBACK] Message: {message}")
        return False


def send_bulk_sms_unified(
    recipients: List[str],
    message: str,
    student_ids: Optional[List[str]] = None,
    related_to: Optional[str] = None
) -> Dict[str, int]:
    """
    Send bulk SMS via central infrastructure.

    Args:
        recipients: List of phone numbers
        message: SMS message
        student_ids: List of student IDs (optional)
        related_to: What this relates to

    Returns:
        dict: {'sent': count, 'failed': count}
    """
    try:
        return send_bulk_sms(recipients, message, student_ids=student_ids, related_to=related_to)

    except Exception as e:
        logger.error(f"Error sending bulk SMS: {e}")
        return {'sent': 0, 'failed': len(recipients)}


# ============================================================================
# DOMAIN-SPECIFIC HELPERS
# ============================================================================

def send_library_notification(
    user_id: str,
    notification_type: str,
    book_title: str,
    due_date: Optional[str] = None,
    days_overdue: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    via: str = 'email'
) -> bool:
    """
    Send library notification (due date, overdue, reservation, etc.).

    Args:
        user_id: User/Student ID
        notification_type: 'due_soon', 'overdue', 'reservation_ready', 'checkout'
        book_title: Book title
        due_date: Due date (for relevant types)
        days_overdue: Days overdue (for overdue type)
        email: Email address (if not using user_id lookup)
        phone: Phone number (for SMS)
        via: 'email' or 'sms'

    Returns:
        bool: True if notification sent successfully
    """
    try:

        # Build message based on type
        if notification_type == 'due_soon':
            subject, body = render_template('library_due_soon', {
                'book_title': book_title,
                'due_date': due_date
            })
            sms_msg = f"Library: '{book_title}' due {due_date}"

        elif notification_type == 'overdue':
            subject, body = render_template('library_overdue', {
                'book_title': book_title,
                'days_overdue': str(days_overdue)
            })
            sms_msg = f"Library: '{book_title}' overdue {days_overdue} days"

        elif notification_type == 'reservation_ready':
            subject, body = render_template('library_reservation_ready', {
                'book_title': book_title
            })
            sms_msg = f"Library: '{book_title}' ready for pickup"

        elif notification_type == 'checkout':
            subject, body = render_template('library_checkout', {
                'book_title': book_title,
                'due_date': due_date
            })
            sms_msg = f"Library: Checked out '{book_title}', due {due_date}"

        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return False

        # Send notification
        if via == 'email' and email:
            return send_email_unified(email, subject, body, sender_type='system')

        elif via == 'sms' and phone:
            return send_sms_unified(phone, sms_msg, student_id=user_id, related_to='library')

        else:
            logger.warning(f"No contact method provided for {via}")
            return False

    except Exception as e:
        logger.error(f"Error sending library notification: {e}")
        return False


def send_calendar_reminder(
    user_id: str,
    event_name: str,
    event_date: str,
    event_time: str,
    location: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    via: str = 'email'
) -> bool:
    """
    Send academic calendar event reminder.

    Args:
        user_id: User/Student ID
        event_name: Event name
        event_date: Event date
        event_time: Event time
        location: Event location
        email: Email address
        phone: Phone number
        via: 'email' or 'sms'

    Returns:
        bool: True if reminder sent successfully
    """
    try:

        location_line = f"Location: {location}\n" if location else ""

        subject, body = render_template('calendar_reminder', {
            'event_name': event_name,
            'event_date': event_date,
            'event_time': event_time,
            'location_line': location_line
        })

        sms_msg = f"Reminder: {event_name} on {event_date} at {event_time}"
        if location:
            sms_msg += f" ({location})"

        # Send notification
        if via == 'email' and email:
            return send_email_unified(email, subject, body, sender_type='system')

        elif via == 'sms' and phone:
            return send_sms_unified(phone, sms_msg, student_id=user_id, related_to='calendar')

        else:
            logger.warning(f"No contact method provided for {via}")
            return False

    except Exception as e:
        logger.error(f"Error sending calendar reminder: {e}")
        return False


def send_restaurant_notification(
    customer_id: str,
    notification_type: str,
    order_id: Optional[str] = None,
    reservation_id: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send restaurant/dining notification.

    Args:
        customer_id: Customer ID
        notification_type: 'order_confirmation', 'reservation_confirmation', 'loyalty_update'
        order_id: Order ID (for order confirmations)
        reservation_id: Reservation ID
        email: Email address
        phone: Phone number
        details: Additional details dict

    Returns:
        bool: True if notification sent successfully
    """
    try:

        details = details or {}

        if notification_type == 'order_confirmation':
            total_line = f"Total: £{details['total']:.2f}\n" if 'total' in details else ""
            items_line = f"Items: {details['items']}\n" if 'items' in details else ""

            subject, body = render_template('restaurant_order_confirmation', {
                'order_id': order_id,
                'total_line': total_line,
                'items_line': items_line
            })

        elif notification_type == 'reservation_confirmation':
            date_line = f"Date: {details['date']}\n" if 'date' in details else ""
            time_line = f"Time: {details['time']}\n" if 'time' in details else ""
            guests_line = f"Guests: {details['guests']}\n" if 'guests' in details else ""

            subject, body = render_template('restaurant_reservation_confirmation', {
                'reservation_id': reservation_id,
                'date_line': date_line,
                'time_line': time_line,
                'guests_line': guests_line
            })

        elif notification_type == 'loyalty_update':
            points_line = f"Current Points: {details['points']}\n" if 'points' in details else ""

            subject, body = render_template('restaurant_loyalty_update', {
                'points_line': points_line
            })

        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return False

        # Send via email
        if email:
            return send_email_unified(email, subject, body, sender_type='system')

        logger.warning("No email provided for restaurant notification")
        return False

    except Exception as e:
        logger.error(f"Error sending restaurant notification: {e}")
        return False


# ============================================================================
# MIGRATION HELPERS
# ============================================================================

def migrate_standalone_email(
    old_function_name: str,
    recipient: str,
    subject: str,
    body: str,
    **kwargs
) -> bool:
    """
    Helper function to migrate from standalone email functions.

    Usage in old code:
        # OLD: send_email_smtp(recipient, subject, body)
        # NEW: migrate_standalone_email('send_email_smtp', recipient, subject, body)

    Args:
        old_function_name: Name of old function (for logging)
        recipient: Email address
        subject: Email subject
        body: Email body
        **kwargs: Additional parameters

    Returns:
        bool: True if migrated successfully
    """
    logger.info(f"Migrating {old_function_name} to central email service")
    return send_email_unified(recipient, subject, body, **kwargs)


def migrate_standalone_sms(
    old_function_name: str,
    phone_number: str,
    message: str,
    **kwargs
) -> bool:
    """
    Helper function to migrate from standalone SMS functions.

    Usage in old code:
        # OLD: send_sms_twilio(phone, message)
        # NEW: migrate_standalone_sms('send_sms_twilio', phone, message)

    Args:
        old_function_name: Name of old function (for logging)
        phone_number: Phone number
        message: SMS message
        **kwargs: Additional parameters

    Returns:
        bool: True if migrated successfully
    """
    logger.info(f"Migrating {old_function_name} to central SMS service")
    return send_sms_unified(phone_number, message, **kwargs)
