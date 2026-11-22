"""Complaints: raising them, handling them, and hearing how they were answered.

Every role may raise a complaint (``complaint.raise``); only the
provider's administrators handle them (``complaint.manage``). Handling
means moving a complaint along the route the domain allows, keeping a
running record, and meeting the two deadlines it carries.

A complainant sees their own complaints and nobody else's, and of the
record under each only the entries marked for them — a handler's
working notes ("spoke to the tutor, she disputes this") stay internal.
Whose complaint it is follows the login that raised it, because an
admin or an end-point assessor has no record in this system to hang it
off.

Every function takes ``actor`` first. Reads are scoped to what the actor
may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.quality import complaints as rules
from education_system.systems.apprenticeships.domain.quality.complaints import (
    Complaint,
    ComplaintUpdate,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    complaint_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    employer_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    require,
    require_any,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

_SUBJECT_MAX_LENGTH = 200


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_complaints(
    actor: Actor,
    *,
    status: str | None = None,
    category: str | None = None,
    apprentice_id: int | None = None,
    raised_by: str | None = None,
    handler: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    ack_overdue_only: bool = False,
    due_before: str | None = None,
    today: date | None = None,
) -> list[Complaint]:
    """The complaints *actor* may see, narrowed by any filters given.

    A handler sees every complaint; anyone else only the ones they
    raised, whatever ``raised_by`` they pass. ``overdue_only`` and
    ``ack_overdue_only`` judge lateness against *today* (default: the
    real today), so "what is waiting on me" is one call.
    """
    require_any(actor, "complaint.raise", "complaint.manage")
    if not actor.can("complaint.manage"):
        raised_by = actor.username or _NOBODY
    as_of = (today or date.today()).isoformat()
    return repo.list_complaints(
        status=status or None,
        category=category or None,
        apprentice_id=apprentice_id,
        raised_by=raised_by or None,
        handler=handler or None,
        open_only=open_only,
        overdue_on=as_of if overdue_only else None,
        ack_overdue_on=as_of if ack_overdue_only else None,
        due_before=due_before or None,
    )


def get_complaint(actor: Actor, complaint_id: int) -> Complaint:
    require_any(actor, "complaint.raise", "complaint.manage")
    return _require_visible(actor, complaint_id)


def list_updates(actor: Actor, complaint_id: int) -> list[ComplaintUpdate]:
    """The record under a complaint: all of it for a handler, the shared part otherwise."""
    require_any(actor, "complaint.raise", "complaint.manage")
    _require_visible(actor, complaint_id)
    return repo.list_updates(complaint_id, visible_only=not actor.can("complaint.manage"))


def counts(actor: Actor, *, today: date | None = None) -> dict[str, int]:
    """Headline figures for the complaints screen, within *actor*'s scope."""
    rows = list_complaints(actor, today=today)
    as_of = today or date.today()
    return {
        "total": len(rows),
        "open": sum(1 for c in rows if c.is_open),
        "overdue": sum(1 for c in rows if c.is_overdue(as_of)),
        "awaiting_ack": sum(1 for c in rows if c.status == "Received"),
    }


# ═════════════════════════════════════════════════════════════════════
# Raising
# ═════════════════════════════════════════════════════════════════════

def raise_complaint(actor: Actor, payload: dict[str, Any]) -> Complaint:
    """Record a new complaint from *actor*.

    Who it is about is worked out from the actor where their role pins
    it down: an apprentice's complaint is about their own apprenticeship,
    an employer's comes from their own organisation. Anyone naming an
    apprentice must be able to see that apprentice — otherwise the form
    would be a way to probe who is on the books.

    A handler may give an earlier ``received_at`` when logging a
    complaint that arrived by letter or phone, because the deadlines run
    from receipt, not from data entry.
    """
    require(actor, "complaint.raise")
    category = rules.validate_category(payload.get("category"))
    subject = rules.validate_text(
        payload.get("subject"), "A subject", max_length=_SUBJECT_MAX_LENGTH
    )
    description = rules.validate_text(
        payload.get("description"), "A description", max_length=config.COMPLAINT_MAX_LENGTH
    )

    apprentice_id, employer_id = _about(actor, payload)
    received = _received_on(actor, payload.get("received_at"))
    ack_due, response_due = rules.deadlines(received)

    complaint_id = repo.create(
        {
            "raised_by": actor.username,
            "raised_role": actor.role,
            "apprentice_id": apprentice_id,
            "employer_id": employer_id,
            "category": category,
            "subject": subject,
            "description": description,
            "received_at": received.isoformat(),
            "status": "Received",
            "ack_due_on": ack_due,
            "response_due_on": response_due,
        },
        first_note=(
            f"Complaint received. We will acknowledge it by {ack_due} "
            f"and respond by {response_due}."
        ),
    )
    compliance_repository.record(
        action="create", entity="complaint", entity_id=complaint_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{rules.complaint_reference(complaint_id)} ({category}): {subject}",
    )
    logger.info("Complaint %s raised by %s", complaint_id, actor.username)
    return _reload(complaint_id)


# ═════════════════════════════════════════════════════════════════════
# Handling
# ═════════════════════════════════════════════════════════════════════

def change_status(
    actor: Actor,
    complaint_id: int,
    new_status: str,
    *,
    note: str | None = None,
    outcome: str | None = None,
    escalated_to: str | None = None,
    today: date | None = None,
) -> Complaint:
    """Move a complaint along its route, stamping what each step means.

    The move is written to the complaint's record, visible to the
    complainant — they are entitled to know where their complaint has
    got to, even when the working notes behind it are internal.
    """
    require(actor, "complaint.manage")
    existing = _require_visible(actor, complaint_id)
    target = rules.validate_status(new_status)
    rules.require_transition(existing.status, target)

    outcome_text = rules.validate_text(
        outcome, "The outcome", max_length=config.COMPLAINT_MAX_LENGTH, required=False
    )
    escalated_text = rules.validate_text(
        escalated_to, "Escalated to", max_length=_SUBJECT_MAX_LENGTH, required=False
    )
    rules.require_status_details(
        target,
        outcome=outcome_text or existing.outcome,
        escalated_to=escalated_text or existing.escalated_to,
    )
    comment = rules.validate_text(
        note, "A note", max_length=config.COMPLAINT_MAX_LENGTH, required=False
    )

    stamp = (today or date.today()).isoformat()
    changes: dict[str, Any] = {"status": target}
    if target == "Acknowledged":
        changes["acknowledged_at"] = stamp
        changes["handler"] = existing.handler or actor.username
    if outcome_text:
        changes["outcome"] = outcome_text
    if escalated_text:
        changes["escalated_to"] = escalated_text
    if target == "Closed":
        changes["closed_at"] = stamp

    record = f"Status changed from {existing.status} to {target}."
    if target == "Resolved":
        record += f" Outcome: {changes.get('outcome', existing.outcome)}"
    if target == "Escalated":
        record += f" Escalated to {changes.get('escalated_to', existing.escalated_to)}."
    if comment:
        record += f" {comment}"

    repo.update(
        complaint_id, changes,
        note=record, author=actor.username, author_role=actor.role, visible=True,
    )
    compliance_repository.record(
        action="update", entity="complaint", entity_id=complaint_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.reference}: {existing.status} -> {target}",
    )
    return _reload(complaint_id)


def acknowledge(
    actor: Actor, complaint_id: int, *, note: str | None = None, today: date | None = None
) -> Complaint:
    """The first deadline: tell the complainant it is in hand, and by whom."""
    return change_status(actor, complaint_id, "Acknowledged", note=note, today=today)


def assign_handler(actor: Actor, complaint_id: int, handler: str) -> Complaint:
    require(actor, "complaint.manage")
    existing = _require_visible(actor, complaint_id)
    name = (handler or "").strip()
    if not name:
        raise ValidationError("Name the member of staff handling this complaint")
    repo.update(
        complaint_id, {"handler": name},
        note=f"Handler set to {name}.", author=actor.username, author_role=actor.role,
        visible=False,
    )
    compliance_repository.record(
        action="update", entity="complaint", entity_id=complaint_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.reference}: handler {existing.handler or '-'} -> {name}",
    )
    return _reload(complaint_id)


def add_update(
    actor: Actor, complaint_id: int, note: str, *, visible: bool = False
) -> ComplaintUpdate:
    """Add to a complaint's record.

    A handler chooses whether the complainant sees the entry. A
    complainant's own entries are always visible — it is their side of
    the conversation — and they cannot add to a closed complaint.
    """
    require_any(actor, "complaint.raise", "complaint.manage")
    complaint = _require_visible(actor, complaint_id)
    text = rules.validate_text(note, "A note", max_length=config.COMPLAINT_MAX_LENGTH)
    if not actor.can("complaint.manage"):
        if complaint.status == "Closed":
            raise ValidationError("This complaint is closed")
        visible = True

    update_id = repo.add_update(
        complaint_id, note=text or "", author=actor.username, author_role=actor.role,
        visible=visible,
    )
    compliance_repository.record(
        action="create", entity="complaint_update", entity_id=update_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{complaint.reference}: {'shared' if visible else 'internal'} note",
    )
    created = next((u for u in repo.list_updates(complaint_id) if u.update_id == update_id), None)
    assert created is not None
    return created


def record_satisfaction(actor: Actor, complaint_id: int, satisfied: bool) -> Complaint:
    """Whether the complainant was satisfied with how it was answered.

    Asked once there is an answer to be satisfied with. The complainant
    gives it; a handler may record it on their behalf after a call.
    """
    require_any(actor, "complaint.raise", "complaint.manage")
    complaint = _require_visible(actor, complaint_id)
    if complaint.status not in ("Resolved", "Escalated", "Closed"):
        raise ValidationError("Satisfaction is recorded once the complaint has been answered")
    verdict = "satisfied" if satisfied else "not satisfied"
    repo.update(
        complaint_id, {"satisfied": 1 if satisfied else 0},
        note=f"Complainant is {verdict} with the response.",
        author=actor.username, author_role=actor.role, visible=True,
    )
    compliance_repository.record(
        action="update", entity="complaint", entity_id=complaint_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{complaint.reference}: {verdict}",
    )
    return _reload(complaint_id)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

# No login is blank, so this matches nothing: a raiser with no username
# sees an empty list rather than every complaint without a raiser.
_NOBODY = "\x00"


def is_complainant(actor: Actor, complaint: Complaint) -> bool:
    return bool(actor.username) and complaint.raised_by.casefold() == actor.username.casefold()


def _require_visible(actor: Actor, complaint_id: int) -> Complaint:
    """The complaint, if *actor* handles complaints or raised this one.

    The refusal does not say whether the complaint exists, so reference
    numbers cannot be probed.
    """
    complaint = repo.get(complaint_id)
    if complaint is not None and (actor.can("complaint.manage") or is_complainant(actor, complaint)):
        return complaint
    raise PermissionDenied("You do not have access to this complaint")


def _reload(complaint_id: int) -> Complaint:
    complaint = repo.get(complaint_id)
    assert complaint is not None
    return complaint


def _about(actor: Actor, payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """``(apprentice_id, employer_id)`` the complaint concerns."""
    if actor.role == config.APPRENTICE:
        # About their own apprenticeship, whatever the form posted.
        return actor.apprentice_id, actor.employer_id

    apprentice_id = _optional_id(payload.get("apprentice_id"), "Apprentice")
    apprentice: Apprentice | None = None
    if apprentice_id is not None:
        apprentice = apprentice_repository.get(apprentice_id)
        if apprentice is None:
            raise PermissionDenied("You do not have access to this apprentice's record")
        require_apprentice_access(actor, apprentice)

    if actor.role == config.EMPLOYER:
        return apprentice_id, actor.employer_id

    employer_id = _optional_id(payload.get("employer_id"), "Employer")
    if employer_id is not None:
        if not actor.can("complaint.manage"):
            # Only a handler logging a complaint on someone's behalf may
            # attach an arbitrary employer.
            employer_id = None
        elif employer_repository.get(employer_id) is None:
            raise ValidationError(f"No employer with id {employer_id}")
    if employer_id is None and apprentice is not None:
        employer_id = apprentice.employer_id
    return apprentice_id, employer_id


def _received_on(actor: Actor, value: Any) -> date:
    today = date.today()
    text = str(value or "").strip()
    if not text or not actor.can("complaint.manage"):
        return today
    try:
        received = date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("Date received must be a date in YYYY-MM-DD format") from exc
    if received > today:
        raise ValidationError("Date received cannot be in the future")
    return received


def _optional_id(value: Any, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be a number") from exc
