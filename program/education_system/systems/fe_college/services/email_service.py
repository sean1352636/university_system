"""Email centre use cases — compose, send, log and template.

The college's outbound correspondence in one place: the GUI's Email
screen and the CLI's email commands both call only this, so a fee
reminder sent from a terminal is logged identically to one sent from a
window.

Two layers, deliberately separate:

**The log** is authoritative and always written. ``compose`` and ``send``
record what the college said and when, and that record stands whether or
not a mail server was reachable.

**Delivery** is best-effort on top. :func:`send` hands the message to the
platform's shared :mod:`~education_system.platform.integrations.email`
service if it is configured, and marks the row ``Failed`` if that
refuses — so a delivery problem is visible in the log rather than looking
like the message was never written. A college with no SMTP configured
still gets a complete, useful correspondence record, which is what the
demo and most installs actually run on.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.systems.fe_college.config import COLLEGE_NAME
from education_system.systems.fe_college.domain.communications.messages import (
    Message,
    Outbox,
    now_stamp,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    message_repository as repo,
)

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """What happened when a message was sent.

    ``delivered`` is about SMTP, ``message.status`` about the log. They
    differ exactly when delivery was attempted and refused, which is the
    case the screens need to report clearly rather than silently.
    """

    message: Message
    delivered: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.message.status != "Failed"


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def get(message_id: str) -> Message | None:
    return repo.get(message_id)


def search(**filters) -> list[Message]:
    """Filtered log, newest first. See ``message_repository.search``."""
    return repo.search(**filters)


def drafts() -> list[Message]:
    return repo.search(status="Draft")


def inbox() -> list[Message]:
    return repo.search(direction="Incoming")


def for_learner(student_id: str) -> list[Message]:
    """Everything the college has sent or received about one learner."""
    return repo.search(student_id=student_id)


def outbox() -> Outbox:
    return repo.outbox()


def recipients() -> list[dict]:
    return repo.recipients()


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def compose(
    *,
    subject: str,
    body: str = "",
    to_name: str = "",
    to_address: str = "",
    category: str = "General",
    priority: str = "Normal",
    channel: str = "Email",
    student_id: str = "",
    staff_id: str = "",
    from_name: str = "",
    from_address: str = "",
    tags: str = "",
    send_now: bool = False,
) -> SendResult:
    """Write a new outgoing message, optionally sending it straight away.

    Saved as a Draft by default. Composing and sending are separate acts
    because a fee reminder or a safeguarding note is usually drafted,
    read back, and only then sent.
    """
    message = Message(
        message_id=None,
        subject=subject,
        body=body,
        direction="Outgoing",
        channel=channel,
        category=category,
        priority=priority,
        status="Draft",
        from_name=from_name or COLLEGE_NAME,
        from_address=from_address,
        to_name=to_name,
        to_address=to_address,
        student_id=student_id,
        staff_id=staff_id,
        tags=tags,
    )
    repo.create(message)
    logger.info("Composed message %s to %s", message.message_id,
                message.to_address or "-")
    if send_now:
        return send(message.message_id or "")
    return SendResult(message=message, detail="Saved as a draft.")


def log_incoming(
    *,
    subject: str,
    body: str = "",
    from_name: str = "",
    from_address: str = "",
    category: str = "General",
    student_id: str = "",
    staff_id: str = "",
) -> Message:
    """Record something that came *in* — an enquiry, an employer reply.

    Logged as ``Received`` with a timestamp, because an inbound message
    has by definition already arrived; there is no draft state for it.
    """
    message = Message(
        message_id=None,
        subject=subject,
        body=body,
        direction="Incoming",
        channel="Email",
        category=category,
        status="Received",
        from_name=from_name,
        from_address=from_address,
        student_id=student_id,
        staff_id=staff_id,
        sent_at=now_stamp(),
    )
    repo.create(message)
    logger.info("Logged incoming message %s from %s", message.message_id,
                from_address or from_name or "-")
    return message


def update_draft(message_id: str, **changes) -> Message:
    """Edit a draft. Only drafts are editable — a sent message is a record."""
    message = repo.get(message_id)
    if message is None:
        raise ValidationError(f"No message with reference {message_id}")
    if not message.is_draft:
        raise ValidationError(
            f"{message_id} has already been sent; a sent message is a record "
            f"of what went out and cannot be rewritten")
    for field, value in changes.items():
        if value is not None and hasattr(message, field):
            setattr(message, field, value)
    repo.update(message)
    return message


def send(message_id: str) -> SendResult:
    """Send a draft: attempt delivery, then stamp the log accordingly."""
    message = repo.get(message_id)
    if message is None:
        raise ValidationError(f"No message with reference {message_id}")
    if message.direction != "Outgoing":
        raise ValidationError("Only an outgoing message can be sent")
    if message.is_sent:
        raise ValidationError(f"{message_id} has already been sent")

    configured = _delivery_configured()
    delivered, detail = _deliver(message, configured=configured)

    # Failed means "we tried to deliver and were refused". Nothing is tried
    # when no SMTP is configured, or when the message is an SMS or a letter
    # that this system records rather than sends — in both cases the log is
    # the record, and Failed would report an error the college has not had.
    attempted = configured and message.channel == "Email"
    message.status = "Failed" if attempted and not delivered else "Sent"
    message.sent_at = now_stamp()
    repo.update(message)

    logger.info("Message %s marked %s (delivery: %s)", message_id,
                message.status, detail or "not attempted")
    return SendResult(message=message, delivered=delivered, detail=detail)


def delete(message_id: str) -> bool:
    """Remove a draft. Sent correspondence is never deleted."""
    message = repo.get(message_id)
    if message is None:
        return False
    if message.is_sent:
        raise ValidationError(
            "Sent correspondence cannot be deleted — it is the record of what "
            "the college communicated")
    return repo.delete(message_id)


# ═════════════════════════════════════════════════════════════════════
# Delivery — best-effort, over the platform's shared SMTP service
# ═════════════════════════════════════════════════════════════════════

def _delivery_configured() -> bool:
    """Whether an SMTP server is configured for real delivery.

    When nothing is configured the college still logs everything and the
    message is marked Sent — that is the intended behaviour for a demo or
    an install that posts letters, not a silent failure.
    """
    try:
        from education_system.platform.integrations.email import load_email_config
        config = load_email_config() or {}
        return bool(config.get("smtp_host") or config.get("host"))
    except Exception:
        logger.debug("Email config unavailable", exc_info=True)
        return False


def _deliver(message: Message, *, configured: bool) -> tuple[bool, str]:
    """Hand the message to the shared email service. Never raises."""
    if message.channel != "Email":
        return (False, f"{message.channel} is recorded, not delivered from here")
    if not configured:
        return (False, "")
    try:
        from education_system.platform.integrations.email import EmailService
        EmailService().send_email(
            message.to_address, message.subject, message.body or "")
        return (True, "delivered")
    except Exception as exc:
        logger.warning("Delivery failed for %s: %s", message.message_id, exc)
        return (False, str(exc))


__all__ = [
    "SendResult",
    "get",
    "search",
    "drafts",
    "inbox",
    "for_learner",
    "outbox",
    "recipients",
    "compose",
    "log_incoming",
    "update_draft",
    "send",
    "delete",
]
