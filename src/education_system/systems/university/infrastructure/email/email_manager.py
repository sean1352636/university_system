"""Email management functions with logging and queueing.

This module provides email notification helpers for the University System's
communication subsystem. Every helper sends through the university outbox
(``email_service.core.send_email``); the in-memory list is only a record
for :func:`get_queued_emails`.
"""
from __future__ import annotations
import logging
from typing import Any
from datetime import datetime
from collections import deque

# i18n support
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        return key

# Initialize logger
logger = logging.getLogger(__name__)

# In-memory email queue
_email_queue: deque[dict[str, Any]] = deque(maxlen=1000)

try:
    # Reuse the handle_exception decorator from the shared logging utils if available
    from education_system.systems.university.infrastructure.logs import handle_exception as _shared_handle_exception
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


_BODY_LABELS = {
    'ticket_id': 'Ticket', 'ticket_subject': 'Subject', 'reply_by': 'Reply from',
    'sla_breach_type': 'SLA status', 'time_remaining': 'Time remaining',
    'survey_link': 'Survey', 'confirmation_type': 'Confirmation',
}


def _recipient_address(recipient: str | None) -> str | None:
    """An e-mail address for ``recipient`` (an address or a username)."""
    if not recipient:
        return None
    recipient = str(recipient).strip()
    if '@' in recipient:
        return recipient
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection(None, row_factory=False)
        try:
            row = conn.execute("SELECT email FROM users WHERE username = ? "
                               "AND email IS NOT NULL AND TRIM(email) <> ''",
                               (recipient,)).fetchone()
        finally:
            conn.close()
        return row[0] if row else None
    except Exception:
        logger.debug("Could not resolve an address for %s", recipient)
        return None


def _compose_body(email_type: str, subject: str | None, metadata: dict[str, Any]) -> str:
    if metadata.get('body'):
        return str(metadata['body'])
    lines = [subject or email_type.replace('_', ' ').capitalize(), '']
    for key, label in _BODY_LABELS.items():
        if metadata.get(key):
            lines.append(f"{label}: {metadata[key]}")
    for key, value in (metadata.get('details') or {}).items():
        lines.append(f"{str(key).replace('_', ' ').capitalize()}: {value}")
    return "\n".join(lines)


def already_sent(to_ref: str | None) -> bool:
    """True when the outbox already holds a message with reference ``to_ref``
    (the idempotency key of a once-only notice)."""
    if not to_ref:
        return False
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection(None, row_factory=False)
        try:
            return conn.execute("SELECT 1 FROM email_outbox WHERE to_ref = ? LIMIT 1",
                                (str(to_ref),)).fetchone() is not None
        finally:
            conn.close()
    except Exception:   # no outbox table yet
        return False


def _queue_email(
    email_type: str,
    recipient: str | None = None,
    subject: str | None = None,
    **kwargs: Any
) -> str:
    """Send a notification through the university outbox; returns what
    happened ('sent to outbox', 'already sent', 'no address', 'failed').

    Options taken from ``kwargs`` (the rest describe the message):

    * ``to_ref`` — idempotency key: a message whose ``to_ref`` is already in
      the outbox is not sent again;
    * ``kind`` / ``category`` — the outbox kind ('transactional' by default)
      and category (``email_type`` by default);
    * ``in_app_copy`` — False when the caller has already put the notice in
      the person's in-app inbox: the message goes straight to the outbox
      instead of through ``send_email`` (which stores an inbox copy too);
    * ``reply_to`` — the Reply-To address (outbox messages only, i.e. with
      ``in_app_copy=False``).

    The entry is also kept in the in-memory list that
    :func:`get_queued_emails` reports, with the outcome.
    """
    to_ref = kwargs.pop('to_ref', None)
    kind = kwargs.pop('kind', 'transactional')
    category = kwargs.pop('category', None) or email_type
    in_app_copy = kwargs.pop('in_app_copy', True)
    reply_to = kwargs.pop('reply_to', None)
    email_entry = {
        'timestamp': datetime.now().isoformat(),
        'type': email_type,
        'recipient': recipient,
        'subject': subject,
        'status': 'queued',
        'to_ref': to_ref,
        'metadata': kwargs
    }
    address = _recipient_address(recipient)
    subject_line = subject or email_type.replace('_', ' ').capitalize()
    if not address:
        email_entry['status'] = 'no address'
    elif already_sent(to_ref):
        email_entry['status'] = 'already sent'
    else:
        try:
            body = _compose_body(email_type, subject, kwargs)
            if in_app_copy:
                from education_system.systems.university.infrastructure.email.email_service.core import (
                    send_email as _core_send_email,
                )
                ok = _core_send_email(address, subject_line, body, kind=kind,
                                      category=category, to_ref=to_ref)
            else:
                from education_system.systems.university.infrastructure.email import outbox_delivery
                queued = outbox_delivery.enqueue(address, subject_line, body, kind=kind,
                                                 category=category, to_ref=to_ref,
                                                 reply_to=reply_to)
                ok = queued['status'] in ('queued', 'stored')
            email_entry['status'] = 'sent to outbox' if ok else 'failed'
        except Exception as exc:
            email_entry['status'] = 'failed'
            logger.warning("Could not send %s e-mail to %s: %s", email_type, recipient, exc)
    _email_queue.append(email_entry)
    logger.info(f"{email_type} email to {recipient}: {email_entry['status']}")
    return email_entry['status']


def display_chat_rooms_menu(*args, **kwargs) -> None:
    """Display a menu for managing chat rooms.

    Prints a simple text-based menu for chat room management.
    """
    print("\n" + "=" * 60)
    print(_t("email.chat_rooms.menu_title", default="===== CHAT ROOMS =====").center(60))
    print("=" * 60)
    print(f"\n1. {_t('email.chat_rooms.view_all', default='View All')}")
    print(f"2. {_t('email.chat_rooms.create_new', default='Create New')}")
    print(f"3. {_t('email.chat_rooms.archive', default='Archive')}")
    print(f"4. {_t('email.chat_rooms.view_statistics', default='View Statistics')}")
    print(f"5. {_t('email.chat_rooms.manage_members', default='Manage Members')}")
    print(f"0. {_t('email.common.return_to_main', default='Return To Main')}")
    print("\n" + "=" * 60)
    logger.debug("Displayed chat rooms menu")


def send_ticket_notification(
    ticket_id: str | None = None,
    recipient: str | None = None,
    ticket_subject: str | None = None,
    *args,
    **kwargs
) -> str:
    """Send a notification email for a new helpdesk ticket.

    Args:
        ticket_id: ID of the ticket
        recipient: Email recipient (support staff)
        ticket_subject: Subject of the ticket
    """
    subject = f"New Helpdesk Ticket #{ticket_id}: {ticket_subject or 'No Subject'}"
    return _queue_email(
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
) -> str:
    """Generic email sending helper.

    Args:
        recipient: Email recipient
        subject: Email subject
        body: Email body content
    """
    return _queue_email(
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
) -> str:
    """Send a confirmation email.

    Args:
        recipient: Email recipient
        confirmation_type: Type of confirmation (e.g., 'appointment', 'membership')
        details: Additional confirmation details
    """
    if details is None:
        details = {}

    subject = f"Confirmation: {confirmation_type or 'Action'}"
    return _queue_email(
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
) -> str:
    """Send a notification when a support agent replies to a ticket.

    Args:
        ticket_id: ID of the ticket
        recipient: Email recipient (ticket creator)
        reply_by: Name/ID of the person who replied
    """
    subject = f"New Reply to Ticket #{ticket_id}"
    return _queue_email(
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
) -> str:
    """Send an SLA alert notification.

    Args:
        ticket_id: ID of the ticket
        recipient: Email recipient (support staff)
        sla_breach_type: Type of SLA breach ('warning', 'breach')
        time_remaining: Time remaining before/since breach
    """
    subject = f"SLA {sla_breach_type or 'Alert'} for Ticket #{ticket_id}"
    return _queue_email(
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
) -> str:
    """Send a customer satisfaction survey email.

    Args:
        ticket_id: ID of the resolved ticket
        recipient: Email recipient
        survey_link: Link to the survey
    """
    subject = f"Please Rate Your Support Experience - Ticket #{ticket_id}"
    return _queue_email(
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