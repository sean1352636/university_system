"""Email management functions with logging and queueing.

This module provides email notification functionality with proper logging
and in-memory queueing for the University System's communication subsystem.
"""
from __future__ import annotations
import logging
from typing import Any
from datetime import datetime
from collections import deque

# i18n support
try:
    from university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        return key

# Initialize logger
logger = logging.getLogger(__name__)

# In-memory email queue
_email_queue: deque[dict[str, Any]] = deque(maxlen=1000)

try:
    # Reuse the handle_exception decorator from the shared logging utils if available
    from university_system.core.logs import handle_exception as _shared_handle_exception
except Exception:
    # Fallback: define a no-op decorator
    def _shared_handle_exception(func):  # type: ignore[no-redef]
        """Fallback decorator that returns the function unchanged."""
        return func


def handle_exception(func):  # type: ignore[override]
    """Proxy for the shared handle_exception decorator.

    When decorating functions in this module, simply use this wrapper.  If
    the shared decorator is unavailable, this becomes a no-op decorator.
    """
    return _shared_handle_exception(func)


def _queue_email(
    email_type: str,
    recipient: str | None = None,
    subject: str | None = None,
    **kwargs: Any
) -> None:
    """Queue an email for sending.

    Args:
        email_type: Type of email notification
        recipient: Email recipient
        subject: Email subject
        **kwargs: Additional email parameters
    """
    email_entry = {
        'timestamp': datetime.now().isoformat(),
        'type': email_type,
        'recipient': recipient,
        'subject': subject,
        'status': 'queued',
        'metadata': kwargs
    }

    _email_queue.append(email_entry)
    logger.info(f"Queued {email_type} email to {recipient}: {subject}")


def display_chat_rooms_menu(*args, **kwargs) -> None:
    """Display a menu for managing chat rooms.

    Prints a simple text-based menu for chat room management.
    """
    print("\n" + "=" * 60)
    print(_t("email.chat_rooms.menu_title").center(60))
    print("=" * 60)
    print(f"\n1. {_t('email.chat_rooms.view_all')}")
    print(f"2. {_t('email.chat_rooms.create_new')}")
    print(f"3. {_t('email.chat_rooms.archive')}")
    print(f"4. {_t('email.chat_rooms.view_statistics')}")
    print(f"5. {_t('email.chat_rooms.manage_members')}")
    print(f"0. {_t('email.common.return_to_main')}")
    print("\n" + "=" * 60)
    logger.debug("Displayed chat rooms menu")


def send_ticket_notification(
    ticket_id: str | None = None,
    recipient: str | None = None,
    ticket_subject: str | None = None,
    *args,
    **kwargs
) -> None:
    """Send a notification email for a new helpdesk ticket.

    Args:
        ticket_id: ID of the ticket
        recipient: Email recipient (support staff)
        ticket_subject: Subject of the ticket
    """
    subject = f"New Helpdesk Ticket #{ticket_id}: {ticket_subject or 'No Subject'}"
    _queue_email(
        email_type='ticket_notification',
        recipient=recipient,
        subject=subject,
        ticket_id=ticket_id,
        ticket_subject=ticket_subject,
        **kwargs
    )


def send_email(
    recipient: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    *args,
    **kwargs
) -> None:
    """Generic email sending helper.

    Args:
        recipient: Email recipient
        subject: Email subject
        body: Email body content
    """
    _queue_email(
        email_type='generic',
        recipient=recipient,
        subject=subject,
        body=body,
        **kwargs
    )


def send_confirmation_email(
    recipient: str | None = None,
    confirmation_type: str | None = None,
    details: dict[str, Any] | None = None,
    *args,
    **kwargs
) -> None:
    """Send a confirmation email.

    Args:
        recipient: Email recipient
        confirmation_type: Type of confirmation (e.g., 'appointment', 'membership')
        details: Additional confirmation details
    """
    if details is None:
        details = {}

    subject = f"Confirmation: {confirmation_type or 'Action'}"
    _queue_email(
        email_type='confirmation',
        recipient=recipient,
        subject=subject,
        confirmation_type=confirmation_type,
        details=details,
        **kwargs
    )


def send_reply_notification(
    ticket_id: str | None = None,
    recipient: str | None = None,
    reply_by: str | None = None,
    *args,
    **kwargs
) -> None:
    """Send a notification when a support agent replies to a ticket.

    Args:
        ticket_id: ID of the ticket
        recipient: Email recipient (ticket creator)
        reply_by: Name/ID of the person who replied
    """
    subject = f"New Reply to Ticket #{ticket_id}"
    _queue_email(
        email_type='reply_notification',
        recipient=recipient,
        subject=subject,
        ticket_id=ticket_id,
        reply_by=reply_by,
        **kwargs
    )


def send_sla_alert(
    ticket_id: str | None = None,
    recipient: str | None = None,
    sla_breach_type: str | None = None,
    time_remaining: str | None = None,
    *args,
    **kwargs
) -> None:
    """Send an SLA alert notification.

    Args:
        ticket_id: ID of the ticket
        recipient: Email recipient (support staff)
        sla_breach_type: Type of SLA breach ('warning', 'breach')
        time_remaining: Time remaining before/since breach
    """
    subject = f"SLA {sla_breach_type or 'Alert'} for Ticket #{ticket_id}"
    _queue_email(
        email_type='sla_alert',
        recipient=recipient,
        subject=subject,
        ticket_id=ticket_id,
        sla_breach_type=sla_breach_type,
        time_remaining=time_remaining,
        **kwargs
    )


def send_satisfaction_survey(
    ticket_id: str | None = None,
    recipient: str | None = None,
    survey_link: str | None = None,
    *args,
    **kwargs
) -> None:
    """Send a customer satisfaction survey email.

    Args:
        ticket_id: ID of the resolved ticket
        recipient: Email recipient
        survey_link: Link to the survey
    """
    subject = f"Please Rate Your Support Experience - Ticket #{ticket_id}"
    _queue_email(
        email_type='satisfaction_survey',
        recipient=recipient,
        subject=subject,
        ticket_id=ticket_id,
        survey_link=survey_link,
        **kwargs
    )


def get_queued_emails(limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve queued emails from the in-memory queue.

    Args:
        limit: Maximum number of emails to retrieve

    Returns:
        List of queued email dictionaries
    """
    emails = list(_email_queue)[-limit:]
    logger.debug(f"Retrieved {len(emails)} queued emails")
    return emails


def clear_email_queue() -> int:
    """Clear all emails from the queue.

    Returns:
        Number of emails cleared
    """
    count = len(_email_queue)
    _email_queue.clear()
    logger.info(f"Cleared {count} emails from queue")
    return count


# Export names that tests may inspect
__all__ = [
    'handle_exception',
    'display_chat_rooms_menu',
    'send_ticket_notification',
    'send_email',
    'send_confirmation_email',
    'send_reply_notification',
    'send_sla_alert',
    'send_satisfaction_survey',
    'get_queued_emails',
    'clear_email_queue',
]