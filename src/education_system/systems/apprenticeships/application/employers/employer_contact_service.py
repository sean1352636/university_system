"""Keeping in touch with employers: contacts, the contact log, commitments.

Provider staff hold ``employer.contact``: they keep an employer's
contacts current, log every conversation, and track what the employer
has committed to. A tutor sees only the employers of apprentices on
their own caseload — the employers they actually deal with — while an
admin sees them all. Reading commitments follows ``employer.view``, so
an employer can be shown their own; changing them is the provider's job.

Contacts are ``employer_managers`` rows with a contact role. Linking a
contact to a portal login, or making them the signatory, grants access
and stays with ``employer.manage`` in :mod:`employer_service`.

Every function takes ``actor`` first. Every write is audited with the
before and after values in its detail.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.employers import contacts as rules
from education_system.systems.apprenticeships.domain.employers.contacts import (
    ContactLogEntry,
    EmployerCommitment,
)
from education_system.systems.apprenticeships.domain.employers.models import (
    Employer,
    EmployerManager,
    EmployerSummary,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    employer_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.application.employers import employer_service
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    may_view_apprentice,
    require,
)

logger = logging.getLogger(__name__)

# Contact fields a member of staff may set. Login linking, the signatory
# flag and deactivation grant or revoke access, so need employer.manage.
_STAFF_CONTACT_FIELDS = ("full_name", "job_title", "email", "phone", "contact_role")


# ═════════════════════════════════════════════════════════════════════
# Scope
# ═════════════════════════════════════════════════════════════════════

def visible_employer_ids(actor: Actor) -> set[int] | None:
    """The employers *actor* works with; None means every employer.

    Staff: the employers of apprentices on their caseload. A tutor with
    no staff record has no caseload, so sees nobody — not everybody.
    """
    if actor.role == config.ADMIN:
        return None
    if actor.role == config.STAFF:
        return repo.employer_ids_for_tutor(actor.staff_id) if actor.staff_id else set()
    if actor.role == config.EMPLOYER:
        return {actor.employer_id} if actor.employer_id else set()
    return set()


def _require_employer(actor: Actor, employer_id: int) -> Employer:
    scope = visible_employer_ids(actor)
    if scope is not None and employer_id not in scope:
        raise PermissionDenied("You do not have access to this employer's records")
    employer = repo.get(employer_id)
    if employer is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return employer


def _check_apprentice(actor: Actor, employer_id: int, apprentice_id: Any) -> int | None:
    """An optional apprentice, who must work for this employer and be in scope."""
    if apprentice_id in (None, "", 0, "0"):
        return None
    try:
        key = int(apprentice_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Apprentice is not valid") from exc
    apprentice = apprentice_repository.get(key)
    if apprentice is None or apprentice.employer_id != employer_id:
        raise ValidationError("That apprentice does not work for this employer")
    if not may_view_apprentice(actor, apprentice):
        raise PermissionDenied("You do not have access to this apprentice's record")
    return key


def _check_contact(employer_id: int, contact_id: Any) -> int | None:
    if contact_id in (None, "", 0, "0"):
        return None
    try:
        key = int(contact_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Contact is not valid") from exc
    contact = repo.get_manager(key)
    if contact is None or contact.employer_id != employer_id:
        raise ValidationError("That contact belongs to a different employer")
    return key


# ═════════════════════════════════════════════════════════════════════
# Employers and their contacts
# ═════════════════════════════════════════════════════════════════════

def list_employers(actor: Actor, *, search: str | None = None) -> list[EmployerSummary]:
    """The employers *actor* keeps in touch with."""
    require(actor, "employer.contact")
    scope = visible_employer_ids(actor)
    summaries = repo.list_summaries(search=search)
    if scope is None:
        return summaries
    return [s for s in summaries if s.employer.employer_id in scope]


def get_employer(actor: Actor, employer_id: int) -> EmployerSummary:
    require(actor, "employer.contact")
    _require_employer(actor, employer_id)
    summary = repo.get_summary(employer_id)
    assert summary is not None
    return summary


def list_contacts(
    actor: Actor, employer_id: int, *, active_only: bool = False
) -> list[EmployerManager]:
    """The employer's contacts and what each does."""
    require(actor, "employer.contact")
    _require_employer(actor, employer_id)
    return repo.list_managers(employer_id, active_only=active_only)


def add_contact(actor: Actor, employer_id: int, payload: dict[str, Any]) -> EmployerManager:
    """Add a named contact with their role.

    With ``employer.manage`` this is :func:`employer_service.add_manager`
    and may link a login; otherwise login and signatory fields are
    ignored.
    """
    require(actor, "employer.contact")
    employer = _require_employer(actor, employer_id)
    if actor.can("employer.manage"):
        return employer_service.add_manager(actor, employer_id, payload)

    data = employer_service.validate_contact_payload(
        {k: v for k, v in payload.items() if k in _STAFF_CONTACT_FIELDS}, existing=None
    )
    data["employer_id"] = employer_id
    manager_id = repo.create_manager(data)
    compliance_repository.record(
        action="create", entity="employer_manager", entity_id=manager_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['full_name']} ({data.get('contact_role') or 'no role'}) "
               f"added to {employer.name}",
    )
    created = repo.get_manager(manager_id)
    assert created is not None
    return created


def update_contact(actor: Actor, manager_id: int, payload: dict[str, Any]) -> EmployerManager:
    """Edit a contact's details and role."""
    require(actor, "employer.contact")
    existing = repo.get_manager(manager_id)
    if existing is None:
        raise ValidationError(f"No contact with id {manager_id}")
    _require_employer(actor, existing.employer_id)
    if actor.can("employer.manage"):
        return employer_service.update_manager(actor, manager_id, payload)

    data = employer_service.validate_contact_payload(
        {k: v for k, v in payload.items() if k in _STAFF_CONTACT_FIELDS}, existing=existing
    )
    repo.update_manager(manager_id, data)
    compliance_repository.record(
        action="update", entity="employer_manager", entity_id=manager_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.full_name}: " + _changes(existing, data),
    )
    updated = repo.get_manager(manager_id)
    assert updated is not None
    return updated


# ═════════════════════════════════════════════════════════════════════
# The contact log
# ═════════════════════════════════════════════════════════════════════

def list_contact_log(
    actor: Actor,
    employer_id: int | None = None,
    *,
    apprentice_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
) -> list[ContactLogEntry]:
    """Conversations, newest first — one employer's, or all in scope."""
    require(actor, "employer.contact")
    if employer_id is not None:
        _require_employer(actor, employer_id)
    return repo.list_contact_log(
        employer_id=employer_id,
        employer_ids=visible_employer_ids(actor),
        apprentice_id=apprentice_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


def follow_ups(
    actor: Actor,
    *,
    employer_id: int | None = None,
    apprentice_id: int | None = None,
    due_from: str | None = None,
    due_by: str | None = None,
    overdue_only: bool = False,
) -> list[ContactLogEntry]:
    """Open follow-ups in scope, filterable by due date — for task lists."""
    require(actor, "employer.contact")
    if employer_id is not None:
        _require_employer(actor, employer_id)
    entries = repo.list_contact_log(
        employer_id=employer_id,
        employer_ids=visible_employer_ids(actor),
        apprentice_id=apprentice_id,
        open_follow_ups=True,
        follow_up_from=due_from,
        follow_up_to=due_by,
        follow_up_overdue_on=date.today().isoformat() if overdue_only else None,
    )
    return sorted(entries, key=lambda e: (e.follow_up_date or "", e.log_id))


def log_contact(actor: Actor, employer_id: int, payload: dict[str, Any]) -> ContactLogEntry:
    """Record a conversation with an employer."""
    require(actor, "employer.contact")
    employer = _require_employer(actor, employer_id)

    contacted_on = _validate_date(payload.get("contacted_on"), "Contact date") \
        or date.today().isoformat()
    if contacted_on > date.today().isoformat():
        raise ValidationError("A contact cannot be logged in the future")
    follow_up = _validate_date(payload.get("follow_up_date"), "Follow-up date")
    if follow_up and follow_up < contacted_on:
        raise ValidationError("The follow-up date cannot be before the contact")

    data = {
        "employer_id": employer_id,
        "contact_id": _check_contact(employer_id, payload.get("contact_id")),
        "apprentice_id": _check_apprentice(actor, employer_id, payload.get("apprentice_id")),
        "contacted_on": contacted_on,
        "channel": rules.validate_channel(payload.get("channel")),
        "summary": rules.validate_text(
            payload.get("summary"), "A summary", limit=config.CONTACT_SUMMARY_MAX_LENGTH
        ),
        "follow_up_date": follow_up,
        "logged_by": actor.username,
        "logged_by_role": actor.role,
    }
    log_id = repo.create_contact_log(data)
    compliance_repository.record(
        action="create", entity="employer_contact_log", entity_id=log_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['channel']} with {employer.name} on {contacted_on}"
               + (f", follow up by {follow_up}" if follow_up else ""),
    )
    logger.info("Contact %s logged with employer %s by %s", log_id, employer_id, actor.username)
    created = repo.get_contact_log(log_id)
    assert created is not None
    return created


def complete_follow_up(actor: Actor, log_id: int) -> ContactLogEntry:
    """Mark a logged conversation's follow-up as done."""
    require(actor, "employer.contact")
    entry = repo.get_contact_log(log_id)
    if entry is None:
        raise ValidationError(f"No contact log entry with id {log_id}")
    _require_employer(actor, entry.employer_id)
    if not entry.follow_up_open:
        raise ValidationError("There is no open follow-up on this entry")

    repo.update_contact_log(log_id, {
        "follow_up_done_at": date.today().isoformat(),
        "follow_up_done_by": actor.username,
    })
    compliance_repository.record(
        action="update", entity="employer_contact_log", entity_id=log_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Follow-up due {entry.follow_up_date}: open -> done",
    )
    updated = repo.get_contact_log(log_id)
    assert updated is not None
    return updated


# ═════════════════════════════════════════════════════════════════════
# Commitments
# ═════════════════════════════════════════════════════════════════════

def list_commitments(
    actor: Actor,
    employer_id: int | None = None,
    *,
    apprentice_id: int | None = None,
    outstanding_only: bool = False,
    overdue_only: bool = False,
    due_from: str | None = None,
    due_to: str | None = None,
) -> list[EmployerCommitment]:
    """Commitments in scope, outstanding first and soonest due first."""
    require(actor, "employer.view")
    if employer_id is not None:
        _require_employer(actor, employer_id)
    return repo.list_commitments(
        employer_id=employer_id,
        employer_ids=visible_employer_ids(actor),
        apprentice_id=apprentice_id,
        outstanding_only=outstanding_only,
        overdue_on=date.today().isoformat() if overdue_only else None,
        due_from=due_from,
        due_to=due_to,
    )


def get_commitment(actor: Actor, commitment_id: int) -> EmployerCommitment:
    require(actor, "employer.view")
    return _require_commitment(actor, commitment_id)


def add_commitment(
    actor: Actor, employer_id: int, payload: dict[str, Any]
) -> EmployerCommitment:
    """Record something the employer has undertaken to do."""
    require(actor, "employer.contact")
    employer = _require_employer(actor, employer_id)

    data = _validate_commitment(actor, employer_id, payload, existing=None)
    data.update(employer_id=employer_id, status="Open", escalation_level=0,
                created_by=actor.username)
    commitment_id = repo.create_commitment(data)
    compliance_repository.record(
        action="create", entity="employer_commitment", entity_id=commitment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['category']}: {data['commitment']} ({employer.name}"
               + (f", due {data['due_date']}" if data.get("due_date") else "") + ")",
    )
    created = repo.get_commitment(commitment_id)
    assert created is not None
    return created


def update_commitment(
    actor: Actor, commitment_id: int, payload: dict[str, Any]
) -> EmployerCommitment:
    """Edit an outstanding commitment. Status moves through escalate / close."""
    require(actor, "employer.contact")
    existing = _require_commitment(actor, commitment_id)
    if not existing.is_outstanding:
        raise ValidationError(f"This commitment is {existing.status} and can no longer change")

    data = _validate_commitment(actor, existing.employer_id, payload, existing=existing)
    repo.update_commitment(commitment_id, data)
    compliance_repository.record(
        action="update", entity="employer_commitment", entity_id=commitment_id,
        actor=actor.username, actor_role=actor.role,
        detail=_changes(existing, data),
    )
    updated = repo.get_commitment(commitment_id)
    assert updated is not None
    return updated


def escalate_commitment(actor: Actor, commitment_id: int, *, reason: str) -> EmployerCommitment:
    """Raise an outstanding commitment one escalation level, saying why."""
    require(actor, "employer.contact")
    existing = _require_commitment(actor, commitment_id)
    why = rules.validate_text(reason, "A reason for escalating", limit=1000)
    level = rules.next_escalation_level(existing)

    note = f"{date.today().isoformat()} escalated to level {level} by {actor.username}: {why}"
    repo.update_commitment(commitment_id, {
        "status": "Escalated",
        "escalation_level": level,
        "escalated_at": date.today().isoformat(),
        "escalated_by": actor.username,
        "escalation_reason": why,
        "notes": f"{existing.notes}\n{note}" if existing.notes else note,
    })
    compliance_repository.record(
        action="update", entity="employer_commitment", entity_id=commitment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Escalation {existing.escalation_level} -> {level} "
               f"({config.COMMITMENT_ESCALATION_LEVELS[level]}); status "
               f"{existing.status} -> Escalated: {why}",
    )
    logger.info("Commitment %s escalated to %s by %s", commitment_id, level, actor.username)
    updated = repo.get_commitment(commitment_id)
    assert updated is not None
    return updated


def close_commitment(
    actor: Actor, commitment_id: int, *, status: str, note: str | None = None
) -> EmployerCommitment:
    """Mark a commitment Met or Withdrawn."""
    require(actor, "employer.contact")
    existing = _require_commitment(actor, commitment_id)
    target = rules.validate_closure(existing, status)
    if target == "Withdrawn" and not (note or "").strip():
        raise ValidationError("Say why the commitment is being withdrawn")

    patch: dict[str, Any] = {"status": target, "closed_at": date.today().isoformat()}
    text = (note or "").strip()
    if text:
        line = f"{date.today().isoformat()} {target.lower()} by {actor.username}: {text}"
        patch["notes"] = f"{existing.notes}\n{line}" if existing.notes else line
    repo.update_commitment(commitment_id, patch)
    compliance_repository.record(
        action="update", entity="employer_commitment", entity_id=commitment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Status {existing.status} -> {target}" + (f": {text}" if text else ""),
    )
    updated = repo.get_commitment(commitment_id)
    assert updated is not None
    return updated


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require_commitment(actor: Actor, commitment_id: int) -> EmployerCommitment:
    commitment = repo.get_commitment(commitment_id)
    if commitment is None:
        raise ValidationError(f"No commitment with id {commitment_id}")
    _require_employer(actor, commitment.employer_id)
    return commitment


def _validate_commitment(
    actor: Actor, employer_id: int, payload: dict[str, Any],
    *, existing: EmployerCommitment | None,
) -> dict[str, Any]:
    """Only keys present are validated and returned, so a partial edit keeps the rest."""
    data: dict[str, Any] = {}
    if existing is None or "commitment" in payload:
        data["commitment"] = rules.validate_text(
            payload.get("commitment"), "The commitment", limit=500
        )
    if existing is None or "category" in payload:
        data["category"] = rules.validate_category(payload.get("category"))
    if "due_date" in payload:
        data["due_date"] = _validate_date(payload.get("due_date"), "Due date")
    if "apprentice_id" in payload:
        data["apprentice_id"] = _check_apprentice(actor, employer_id, payload.get("apprentice_id"))
    if "notes" in payload:
        data["notes"] = str(payload.get("notes") or "").strip() or None
    return data


def _changes(existing: Any, data: dict[str, Any]) -> str:
    """``field: before -> after`` for each value that actually changed."""
    parts = [
        f"{key}: {getattr(existing, key, None) or '—'} -> {value or '—'}"
        for key, value in sorted(data.items())
        if getattr(existing, key, None) != value
    ]
    return "; ".join(parts) or "no change"


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc
