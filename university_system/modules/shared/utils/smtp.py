"""
SMTP utilities for email sending.

Some email helper modules import an ``smtp`` submodule to send
emails through an SMTP server.  In this sandboxed environment there
is no outbound email capability, so these functions log email details
instead of actually sending them.
"""
from __future__ import annotations
from typing import Any, Optional
import logging
from datetime import datetime


# Configure logging for email operations
logger = logging.getLogger(__name__)

# In-memory email queue for testing/debugging
email_queue: list = []


def send_mail(to_address: str, subject: str, body: str, *args: Any, **kwargs: Any) -> None:
    """Send an email via SMTP or log it for debugging.

    Args:
        to_address: Recipient email address
        subject: Email subject
        body: Email body content
        *args: Additional positional arguments
        **kwargs: Additional keyword arguments (from_address, cc, bcc, etc.)
    """
    email_data = {
        'to': to_address,
        'subject': subject,
        'body': body,
        'from': kwargs.get('from_address', 'noreply@university.edu'),
        'cc': kwargs.get('cc', []),
        'bcc': kwargs.get('bcc', []),
        'timestamp': datetime.now().isoformat(),
        'sent': False  # In stub mode, emails are queued not sent
    }

    # Log the email
    logger.info(f"Email queued: To={to_address}, Subject={subject}")

    # Add to queue for debugging/testing
    email_queue.append(email_data)

    return None


def connect_smtp_server(*args: Any, **kwargs: Any) -> Optional[Any]:
    """Connect to the SMTP server.

    Args:
        *args: Server configuration (host, port, etc.)
        **kwargs: Additional connection parameters (use_tls, username, password, etc.)

    Returns:
        None in stub mode, or SMTP connection object in production
    """
    host = kwargs.get('host', 'localhost')
    port = kwargs.get('port', 587)
    use_tls = kwargs.get('use_tls', True)

    logger.info(f"SMTP connection simulated: {host}:{port} (TLS: {use_tls})")

    # In production, would return smtplib.SMTP connection
    # In stub mode, return None to indicate no real connection
    return None


def send_email_via_smtp(*args: Any, **kwargs: Any) -> None:
    """Alias to ``send_mail`` for compatibility.

    Some parts of the codebase expect ``send_email_via_smtp`` to be
    defined on the ``smtp`` module.  This function calls ``send_mail``
    with the provided arguments.
    """
    return send_mail(*args, **kwargs)


__all__ = ['send_mail', 'connect_smtp_server', 'send_email_via_smtp']