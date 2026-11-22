"""Dental clinic e-mail, through the university e-mail service (outbox).

The domain no longer reaches into the GUI package to send mail."""

import logging

logger = logging.getLogger(__name__)


def send_dental_email(recipient, subject, body) -> bool:
    if not recipient:
        logger.info("Dental e-mail %r not sent: no recipient", subject)
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        return bool(send_email(recipient, subject, body))
    except Exception as exc:
        logger.warning("Dental e-mail %r to %s failed: %s", subject, recipient, exc)
        return False
