"""Queued sending, now backed by the university outbox.

The old in-memory queue lost every unsent message when the program closed
and retried nothing. The outbox (``application/mail/outbox``, delivered
by ``infrastructure/email/outbox_delivery``) is durable and retries with
back-off, so "queue" now means "put it in the outbox". The public names
are kept so existing callers keep working.
"""

from __future__ import annotations

import queue
import threading

from education_system.systems.university.infrastructure.logs import handle_exception, log_event

# Kept for importers; nothing is held in memory any more.
email_queue = queue.Queue()
worker_threads: list[threading.Thread] = []
worker_threads_lock = threading.Lock()
stop_workers_event = threading.Event()


def _delivery():
    from education_system.systems.university.infrastructure.email import outbox_delivery
    return outbox_delivery


@handle_exception
def email_worker():
    """Run one outbox delivery pass."""
    return _delivery().deliver_due()


@handle_exception
def start_email_workers():
    """Start the outbox delivery worker (once per process)."""
    _delivery().start_worker()
    return True


@handle_exception
def stop_email_workers():
    """The outbox worker is a daemon that stops with the program; queued
    messages stay in the outbox, so there is nothing to drain."""
    return True


@handle_exception
def queue_email(recipient, subject, body, cc=None, bcc=None, attachments=None, scheduled_id=None):
    """Put an e-mail in the outbox (delivered in the background)."""
    from education_system.systems.university.infrastructure.email.email_service.core import send_email
    success = send_email(recipient, subject, body, cc, bcc, attachments)
    if scheduled_id:
        _mark_scheduled(scheduled_id, success)
    return success


@handle_exception
def queue_template_email(template_name, recipient, template_vars, cc=None, bcc=None,
                         attachments=None, scheduled_id=None):
    """Render a template and put the e-mail in the outbox."""
    from education_system.systems.university.infrastructure.email.email_service.core import (
        send_template_email,
    )
    success = send_template_email(template_name, recipient, template_vars, cc, bcc, attachments)
    if scheduled_id:
        _mark_scheduled(scheduled_id, success)
    return success


def _mark_scheduled(scheduled_id, success) -> None:
    from education_system.systems.university.infrastructure.email.email_service.scheduling import (
        update_scheduled_email_status,
    )
    update_scheduled_email_status(scheduled_id, 'sent' if success else 'failed')
    log_event('info' if success else 'error',
              f"Scheduled email {scheduled_id} marked as {'sent' if success else 'failed'}")


@handle_exception
def wait_for_email_queue():
    """Run a delivery pass now instead of waiting for the worker."""
    result = _delivery().deliver_due()
    log_event('info', f"Outbox delivery pass: {result}")
    return True
