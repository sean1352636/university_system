"""Correspondence: compose, send, log and template.

The provider's message log — with the five parties round an apprentice,
"who was told what, and when" is asked far more often here than in a
school. A missed review, a funding query, a gateway delay: each one
turns into a question about correspondence, and this is where the
answer lives.

Scoping is the reason this is a service and not a repository call.
``Actor`` comes first on every function, as everywhere else in this
system, and the log is filtered by what that actor may see:

* **admin** — everything
* **staff** — their own caseload, and the employers who supervise it
* **employer** — only messages about their own apprentices
* **apprentice** — only their own
* **end-point assessor** — nothing; the EPAO is independent and the
  provider's correspondence is not theirs to read

Delivery is best-effort over the platform's shared SMTP service, exactly
as in the FE College equivalent: the log is always written, and a refused
delivery is marked ``Failed`` rather than lost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    ValidationError,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    email_repository as repo,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    require,
)

logger = logging.getLogger(__name__)

#: Outbound messages go out in the training provider's name.
PROVIDER_NAME = "Apprenticeships"


@dataclass
class SendResult:
    """What happened when a message was sent.

    ``delivered`` is about SMTP; ``status`` is about the log. They differ
    exactly when delivery was attempted and refused — the case the
    screens need to report plainly rather than swallow.
    """

    message: dict[str, Any]
    delivered: bool = False
    detail: str = ""

    @property
    def message_id(self) -> str:
        return str(self.message.get("message_id") or "")

    @property
    def status(self) -> str:
        return str(self.message.get("status") or "")

    @property
    def recipient(self) -> str:
        to_name = self.message.get("to_name") or ""
        to_address = self.message.get("to_address") or ""
        if to_name and to_address:
            return f"{to_name} <{to_address}>"
        return to_name or to_address or "—"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═════════════════════════════════════════════════════════════════════
# Scoping
# ═════════════════════════════════════════════════════════════════════

def _visible_apprentice_ids(actor: Actor) -> list[int] | None:
    """The apprentice ids this actor's view of the log is confined to.

    ``None`` means unrestricted. An empty list means "nobody", which the
    repository turns into no rows — deliberately not into every row,
    which is the failure mode this shape exists to prevent.
    """
    if actor.is_admin:
        return None
    # Reuse the cohort scoping that already governs every other read, so
    # correspondence can never be visible for an apprentice whose record
    # is not.
    from education_system.systems.apprenticeships.services import apprentice_service
    summaries = apprentice_service.list_apprentices(actor)
    return [s.apprentice.apprentice_id for s in summaries]


def _require_visible(actor: Actor, message: dict[str, Any]) -> None:
    """Refuse a message outside the actor's scope."""
    if actor.is_admin:
        return
    allowed = _visible_apprentice_ids(actor)
    if allowed is None:
        return
    linked = message.get("apprentice_id")
    if linked is None:
        # Not about a particular apprentice — provider business, so only
        # provider staff see it.
        if not actor.is_provider:
            raise PermissionDenied(
                "That message is not about one of your apprentices")
        return
    if int(linked) not in allowed:
        raise PermissionDenied(
            "That message is about an apprentice you do not have access to")


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def search(actor: Actor, **filters: Any) -> list[dict[str, Any]]:
    """The message log this actor may see, newest first."""
    require(actor, "email.view")
    scope = _visible_apprentice_ids(actor)
    if scope is not None and "apprentice_ids" not in filters:
        filters["apprentice_ids"] = scope
    return repo.search(**filters)


def get(actor: Actor, message_id: str) -> dict[str, Any]:
    """One message in full."""
    require(actor, "email.view")
    message = repo.get(message_id)
    if message is None:
        raise ValidationError(f"No message with reference {message_id}")
    _require_visible(actor, message)
    return message


def drafts(actor: Actor) -> list[dict[str, Any]]:
    return search(actor, status="Draft")


def inbox(actor: Actor) -> list[dict[str, Any]]:
    return search(actor, direction="Incoming")


def for_apprentice(actor: Actor, apprentice_id: int) -> list[dict[str, Any]]:
    """Everything logged about one apprentice."""
    require(actor, "email.view")
    existing = apprentice_repository.get(apprentice_id)
    if existing is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    _require_visible(actor, {"apprentice_id": apprentice_id})
    return repo.search(apprentice_id=apprentice_id)


def counts(actor: Actor) -> dict[str, int]:
    """Header totals, scoped like the log itself."""
    require(actor, "email.view")
    return repo.counts(_visible_apprentice_ids(actor))


def recipients(actor: Actor) -> list[dict[str, Any]]:
    """Everyone this actor may write to.

    An employer or an apprentice gets a directory confined to their own
    people; provider staff get the full one.
    """
    require(actor, "email.send")
    directory = repo.recipients()
    scope = _visible_apprentice_ids(actor)
    if scope is None:
        return directory
    allowed = set(scope)
    return [
        entry for entry in directory
        if entry["apprentice_id"] is None or entry["apprentice_id"] in allowed
    ]


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def _validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Check the vocabulary and the things that make a message a message."""
    def one_of(value: Any, allowed: tuple[str, ...], label: str, default: str) -> str:
        text = ("" if value is None else str(value)).strip() or default
        if text not in allowed:
            raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
        return text

    out = dict(payload)
    out["direction"] = one_of(payload.get("direction"),
                              config.MESSAGE_DIRECTIONS, "Direction", "Outgoing")
    out["channel"] = one_of(payload.get("channel"),
                            config.MESSAGE_CHANNELS, "Channel", "Email")
    out["category"] = one_of(payload.get("category"),
                             config.MESSAGE_CATEGORIES, "Category", "General")
    out["priority"] = one_of(payload.get("priority"),
                             config.MESSAGE_PRIORITIES, "Priority", "Normal")
    out["status"] = one_of(payload.get("status"),
                           config.MESSAGE_STATUSES, "Status", "Draft")

    subject = (payload.get("subject") or "").strip()
    if not subject:
        raise ValidationError("A message needs a subject")
    out["subject"] = subject

    to_address = (payload.get("to_address") or "").strip()
    if to_address and "@" not in to_address:
        raise ValidationError(f"'{to_address}' is not a valid email address")
    if out["direction"] == "Outgoing" and out["channel"] == "Email" \
            and not to_address:
        raise ValidationError("An outgoing email needs a To address")
    return out


def compose(
    actor: Actor,
    *,
    subject: str,
    body: str = "",
    to_name: str = "",
    to_address: str = "",
    category: str = "General",
    priority: str = "Normal",
    channel: str = "Email",
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tags: str = "",
    send_now: bool = False,
) -> SendResult:
    """Write a new outgoing message, optionally sending it straight away.

    Saved as a draft by default: a funding query or a safeguarding note
    is normally drafted, read back, and only then sent.
    """
    require(actor, "email.send")
    if apprentice_id is not None:
        _require_visible(actor, {"apprentice_id": apprentice_id})

    payload = _validate({
        "direction": "Outgoing",
        "channel": channel,
        "category": category,
        "priority": priority,
        "status": "Draft",
        "subject": subject,
        "body": body,
        # Sent in the provider's name, not the individual's — an employer
        # replying to a review chase should reach the provider, not one
        # tutor's inbox. Who actually sent it is kept in ``sent_by``.
        "from_name": PROVIDER_NAME,
        "to_name": to_name,
        "to_address": to_address,
        "apprentice_id": apprentice_id,
        "employer_id": employer_id,
        "sent_by": actor.username,
        "tags": tags,
    })
    message_id = repo.create(payload)
    logger.info("%s composed message %s to %s",
                actor.username, message_id, to_address or "-")
    if send_now:
        return send(actor, message_id)
    message = repo.get(message_id) or payload
    return SendResult(message=message, detail="Saved as a draft.")


def log_incoming(
    actor: Actor,
    *,
    subject: str,
    body: str = "",
    from_name: str = "",
    from_address: str = "",
    category: str = "General",
    apprentice_id: int | None = None,
    employer_id: int | None = None,
) -> dict[str, Any]:
    """Record something that came *in* — an employer reply, an EPAO query.

    Logged as ``Received`` with a timestamp: an inbound message has by
    definition already arrived, so it has no draft state.
    """
    require(actor, "email.send")
    if apprentice_id is not None:
        _require_visible(actor, {"apprentice_id": apprentice_id})
    if not (from_address or from_name):
        raise ValidationError("An incoming message needs a sender")

    payload = _validate({
        "direction": "Incoming",
        "channel": "Email",
        "category": category,
        "status": "Received",
        "subject": subject,
        "body": body,
        "from_name": from_name,
        "from_address": from_address,
        "apprentice_id": apprentice_id,
        "employer_id": employer_id,
        "sent_by": actor.username,
        "sent_at": _now(),
    })
    message_id = repo.create(payload)
    logger.info("%s logged incoming message %s from %s",
                actor.username, message_id, from_address or from_name)
    message = repo.get(message_id)
    assert message is not None
    return message


def update_draft(actor: Actor, message_id: str, **changes: Any) -> dict[str, Any]:
    """Edit a draft. A sent message is a record and cannot be rewritten."""
    require(actor, "email.send")
    message = get(actor, message_id)
    if message["status"] != "Draft":
        raise ValidationError(
            f"{message_id} has already been sent; a sent message is the record "
            f"of what went out and cannot be rewritten")
    merged = {**message, **{k: v for k, v in changes.items() if v is not None}}
    repo.update(message_id, _validate(merged))
    updated = repo.get(message_id)
    assert updated is not None
    return updated


def send(actor: Actor, message_id: str) -> SendResult:
    """Send a draft: attempt delivery, then stamp the log accordingly."""
    require(actor, "email.send")
    message = get(actor, message_id)
    if message["direction"] != "Outgoing":
        raise ValidationError("Only an outgoing message can be sent")
    if message["status"] in ("Sent", "Received"):
        raise ValidationError(f"{message_id} has already been sent")

    configured = _delivery_configured()
    delivered, detail = _deliver(message, configured=configured)

    # Failed means "we tried and were refused". Nothing is tried when no
    # SMTP is configured, or for an SMS or letter this system records
    # rather than sends — marking those Failed would report an error the
    # provider has not had.
    attempted = configured and message["channel"] == "Email"
    status = "Failed" if attempted and not delivered else "Sent"
    repo.update(message_id, {"status": status, "sent_at": _now(),
                             "sent_by": actor.username})

    compliance_repository.record(
        action="update", entity="message", entity_id=message_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{status} to {message.get('to_address') or '-'}: "
               f"{message.get('subject')}",
    )
    logger.info("Message %s marked %s by %s (delivery: %s)",
                message_id, status, actor.username, detail or "not attempted")
    refreshed = repo.get(message_id)
    assert refreshed is not None
    return SendResult(message=refreshed, delivered=delivered, detail=detail)


def delete(actor: Actor, message_id: str) -> bool:
    """Discard a draft. Sent correspondence is never deleted."""
    require(actor, "email.send")
    message = get(actor, message_id)
    if message["status"] in ("Sent", "Received"):
        raise ValidationError(
            "Sent correspondence cannot be deleted — it is the record of what "
            "the provider communicated, and funding audits ask for it")
    return repo.delete(message_id)


# ═════════════════════════════════════════════════════════════════════
# Delivery — best-effort, over the platform's shared SMTP service
# ═════════════════════════════════════════════════════════════════════

def _delivery_configured() -> bool:
    """Whether an SMTP server is configured for real delivery."""
    try:
        from education_system.platform.integrations.email import load_email_config
        settings = load_email_config() or {}
        return bool(settings.get("smtp_host") or settings.get("host"))
    except Exception:
        logger.debug("Email config unavailable", exc_info=True)
        return False


def _deliver(message: dict[str, Any], *, configured: bool) -> tuple[bool, str]:
    """Hand the message to the shared email service. Never raises."""
    if message.get("channel") != "Email":
        return (False, f"{message.get('channel')} is recorded, not delivered here")
    if not configured:
        return (False, "")
    try:
        from education_system.platform.integrations.email import EmailService
        EmailService().send_email(
            message.get("to_address") or "",
            message.get("subject") or "",
            message.get("body") or "")
        return (True, "delivered")
    except Exception as exc:
        logger.warning("Delivery failed for %s: %s",
                       message.get("message_id"), exc)
        return (False, str(exc))


__all__ = [
    "SendResult",
    "search",
    "get",
    "drafts",
    "inbox",
    "for_apprentice",
    "counts",
    "recipients",
    "compose",
    "log_incoming",
    "update_draft",
    "send",
    "delete",
]
