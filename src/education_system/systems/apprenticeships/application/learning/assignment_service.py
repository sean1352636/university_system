"""Assignments: set, submit, mark, moderate.

Provider staff set and mark (``assignment.set``) and second-mark a
sample (``assignment.moderate``); the apprentice sees and submits their
own (``assignment.submit``). Employers and the end-point assessor hold
no ``assignment.view``: this is the provider's formative and summative
assessment, separate from EPA and from the employer's view of progress.

The rules that matter — a Refer reopens the work up to its attempt
limit, nobody moderates their own marking, late work is flagged not
refused — are in ``domain/progress/assignments.py``; this module applies
them, scopes every read to the actor, and audits every write.

Every function takes ``actor`` first.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.progress import assignments as rules
from education_system.systems.apprenticeships.domain.progress.assignments import Assignment
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    assignment_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    portfolio_repository,
    programme_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_assignments(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    assignment_type: str | None = None,
    open_only: bool = False,
    overdue_only: bool = False,
    due_within_days: int | None = None,
    with_children: bool = False,
) -> list[Assignment]:
    """Assignments *actor* may see, soonest due first.

    ``open_only`` keeps those still with the apprentice; ``due_within_days``
    those with the apprentice and due by then, overdue ones included. The
    actor's own scope is applied last and wins.
    """
    require(actor, "assignment.view")
    today = date.today()
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "status": _validate_status(status) if status else None,
        "assignment_type": rules.validate_assignment_type(assignment_type)
        if assignment_type else None,
        "open_only": open_only,
    }
    if apprentice_id is not None:
        _require_apprentice(actor, apprentice_id)
    if overdue_only:
        filters["overdue_on"] = today.isoformat()
    if due_within_days is not None:
        filters["open_only"] = True
        filters["due_before"] = (today + timedelta(days=int(due_within_days))).isoformat()
    filters.update(apprentice_filters(actor))
    return repo.list_assignments(with_children=with_children, **filters)


def get_assignment(actor: Actor, assignment_id: int) -> Assignment:
    """One assignment with every attempt and moderation."""
    require(actor, "assignment.view")
    return _load(actor, assignment_id)


def marking_queue(actor: Actor) -> list[Assignment]:
    """Submitted work in scope waiting on a marker."""
    require(actor, "assignment.set")
    filters: dict[str, Any] = {"status": "Submitted"}
    filters.update(apprentice_filters(actor))
    return repo.list_assignments(with_children=True, **filters)


def moderation_queue(actor: Actor) -> list[Assignment]:
    """Marked work in scope, not yet moderated, that *actor* did not mark.

    Their own marking is left out rather than shown and refused: it is
    not theirs to moderate, so it is not in their pile.
    """
    require(actor, "assignment.moderate")
    filters: dict[str, Any] = {"awaiting_moderation": True, "not_marked_by": actor.username}
    filters.update(apprentice_filters(actor))
    return repo.list_assignments(with_children=True, **filters)


def assignment_summary(actor: Actor) -> dict[str, int]:
    """Headline counts in scope, for a KPI row."""
    require(actor, "assignment.view")
    today = date.today()
    items = list_assignments(actor)
    return {
        "with_apprentice": sum(1 for a in items if a.is_with_apprentice),
        "overdue": sum(1 for a in items if a.is_overdue(today)),
        "due_soon": sum(1 for a in items if a.is_due_soon(today)),
        "to_mark": sum(1 for a in items if a.status == "Submitted"),
        "to_moderate": sum(1 for a in items if a.awaiting_moderation),
        "passed": sum(1 for a in items if a.is_passed),
    }


# ═════════════════════════════════════════════════════════════════════
# Setting
# ═════════════════════════════════════════════════════════════════════

def set_assignment(actor: Actor, apprentice_id: int, payload: dict[str, Any]) -> Assignment:
    """Set a piece of work for one apprentice."""
    require(actor, "assignment.set")
    apprentice = _require_apprentice(actor, apprentice_id)

    data = _validate(payload, apprentice=apprentice, existing=None)
    data.update(
        apprentice_id=apprentice_id,
        status="Set",
        attempt=1,
        set_by=actor.username,
    )
    data.setdefault("max_attempts", config.ASSIGNMENT_MAX_ATTEMPTS)
    assignment_id = repo.create(data)
    compliance_repository.record(
        action="create", entity="assignment", entity_id=assignment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['assignment_type']}: {data['title']} for apprentice {apprentice_id}",
    )
    logger.info("Assignment %s set for apprentice %s by %s",
                assignment_id, apprentice_id, actor.username)
    return _reload(assignment_id)


def update_assignment(actor: Actor, assignment_id: int, payload: dict[str, Any]) -> Assignment:
    """Edit an assignment.

    The brief, title, type, KSBs and attempt limit may change only while
    nothing has been handed in — after that, the work was done against
    them. The due date may move for as long as the work is with the
    apprentice.
    """
    require(actor, "assignment.set")
    existing = _load(actor, assignment_id)
    if not existing.is_with_apprentice:
        raise ValidationError(
            f"This assignment is {existing.status.lower()} and can no longer be edited"
        )
    apprentice = apprentice_repository.get(existing.apprentice_id)
    data = _validate(payload, apprentice=apprentice, existing=existing)
    frozen = sorted(k for k in data if k != "due_date")
    if frozen and existing.attempts_used > 0:
        raise ValidationError(
            "Work has already been handed in against this brief, so only the due date "
            "may change. Set a new assignment if the task itself has changed."
        )
    if "max_attempts" in data and data["max_attempts"] < existing.attempts_used:
        raise ValidationError("The attempt limit cannot be below the attempts already used")

    repo.update(assignment_id, data)
    compliance_repository.record(
        action="update", entity="assignment", entity_id=assignment_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )
    return _reload(assignment_id)


def withdraw_assignment(actor: Actor, assignment_id: int, *, reason: str) -> Assignment:
    """Withdraw work set in error or no longer needed. Kept, not deleted."""
    require(actor, "assignment.set")
    existing = _load(actor, assignment_id)
    rules.require_assignment_status(existing.status, "Withdrawn")
    why = (reason or "").strip()
    if not why:
        raise ValidationError("A reason is required to withdraw an assignment")

    repo.update(assignment_id, {"status": "Withdrawn", "feedback": f"Withdrawn: {why}"})
    compliance_repository.record(
        action="withdraw", entity="assignment", entity_id=assignment_id,
        actor=actor.username, actor_role=actor.role, detail=why,
    )
    return _reload(assignment_id)


# ═════════════════════════════════════════════════════════════════════
# Submitting
# ═════════════════════════════════════════════════════════════════════

def submit(
    actor: Actor,
    assignment_id: int,
    *,
    body: str | None = None,
    evidence_id: int | None = None,
) -> Assignment:
    """Hand in an attempt.

    The apprentice submits their own work. An administrator may record a
    submission on an apprentice's behalf (work handed in on paper, say);
    the audit trail names who actually entered it.
    """
    require(actor, "assignment.submit")
    existing = _load(actor, assignment_id)
    if actor.role == config.APPRENTICE and existing.apprentice_id != actor.apprentice_id:
        raise PermissionDenied("You may only submit your own assignments")
    if not existing.is_with_apprentice:
        raise ValidationError(
            f"This assignment is {existing.status.lower()} and is not waiting for a "
            "submission"
        )
    rules.require_assignment_status(existing.status, "Submitted")
    attempt = existing.next_attempt
    if attempt > existing.max_attempts:
        raise ValidationError("Every attempt allowed on this assignment has been used")

    evidence = _validate_evidence(evidence_id, existing.apprentice_id)
    text = rules.validate_submission(body, has_evidence=evidence is not None)
    late = rules.submitted_late(existing.due_date, date.today())

    submission_id = repo.add_submission(
        assignment_id,
        attempt=attempt,
        body=text,
        evidence_id=evidence,
        submitted_by=actor.username,
        is_late=late,
    )
    compliance_repository.record(
        action="create", entity="assignment_submission", entity_id=submission_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Assignment {assignment_id}, attempt {attempt}" + (" (late)" if late else ""),
    )
    logger.info("Assignment %s attempt %s submitted by %s%s",
                assignment_id, attempt, actor.username, " (late)" if late else "")
    return _reload(assignment_id)


# ═════════════════════════════════════════════════════════════════════
# Marking and moderation
# ═════════════════════════════════════════════════════════════════════

def mark(
    actor: Actor,
    assignment_id: int,
    *,
    grade: str,
    feedback: str | None = None,
    resubmit_by: str | None = None,
) -> Assignment:
    """Grade the current attempt.

    A Refer with attempts to spare sends the work back (Referred), and
    *resubmit_by* may set the new deadline. A Refer on the final attempt
    stands. Feedback is required for a Refer: the apprentice cannot put
    right what they were not told about.
    """
    require(actor, "assignment.set")
    existing = _load(actor, assignment_id)
    if existing.status != "Submitted":
        raise ValidationError(
            f"There is no submission waiting to be marked — this assignment is "
            f"{existing.status.lower()}"
        )
    chosen = rules.validate_grade(grade)
    note = _optional_text(feedback)
    if chosen == rules.REFER and not note:
        raise ValidationError("Feedback is required when referring work")

    new_status = rules.status_after_mark(chosen, existing.attempt, existing.max_attempts)
    rules.require_assignment_status(existing.status, new_status)
    due = _validate_date(resubmit_by, "Resubmission date") if new_status == "Referred" else None

    repo.record_mark(
        assignment_id,
        attempt=existing.attempt,
        grade=chosen,
        feedback=note,
        marked_by=actor.username,
        marked_at=_now(),
        status=new_status,
        due_date=due,
    )
    compliance_repository.record(
        action="grade", entity="assignment", entity_id=assignment_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Attempt {existing.attempt}: {chosen} ({new_status})",
    )
    logger.info("Assignment %s attempt %s marked %s by %s",
                assignment_id, existing.attempt, chosen, actor.username)
    return _reload(assignment_id)


def moderate(
    actor: Actor,
    assignment_id: int,
    *,
    outcome: str,
    adjusted_grade: str | None = None,
    notes: str | None = None,
) -> Assignment:
    """Second-mark the current attempt: agree the grade or adjust it.

    The moderator must not be the marker. An adjustment must change the
    grade and say why. If moderation leaves a Refer standing with
    attempts to spare, the work goes back to the apprentice.
    """
    require(actor, "assignment.moderate")
    existing = _load(actor, assignment_id)
    if existing.status not in rules.MODERATABLE:
        raise ValidationError(
            f"Only marked work can be moderated — this assignment is "
            f"{existing.status.lower()}"
        )
    if existing.current_moderation is not None or existing.current_moderated:
        raise ValidationError("This attempt has already been moderated")
    rules.require_different_moderator(actor.username, existing.marked_by)

    chosen = rules.validate_moderation_outcome(outcome)
    note = _optional_text(notes)
    adjusted: str | None = None
    if chosen == "Adjusted":
        adjusted = rules.validate_grade(adjusted_grade)
        if adjusted == existing.grade:
            raise ValidationError(
                "An adjusted grade must differ from the marker's. Record 'Agreed' instead."
            )
        if not note:
            raise ValidationError("Notes are required when adjusting a grade")
    final = adjusted or existing.grade
    new_status = rules.status_after_moderation(final, existing.attempt, existing.max_attempts)
    if new_status != existing.status:
        rules.require_assignment_status(existing.status, new_status)

    moderation_id = repo.add_moderation(
        assignment_id,
        attempt=existing.attempt,
        moderator=actor.username,
        outcome=chosen,
        original_grade=existing.grade,
        adjusted_grade=adjusted,
        notes=note,
        status=new_status,
        grade=final,
    )
    compliance_repository.record(
        action="approve" if chosen == "Agreed" else "grade",
        entity="assignment_moderation", entity_id=moderation_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Assignment {assignment_id} attempt {existing.attempt}: {chosen}"
               + (f" {existing.grade} -> {adjusted}" if adjusted else ""),
    )
    logger.info("Assignment %s moderated %s by %s", assignment_id, chosen, actor.username)
    return _reload(assignment_id)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _load(actor: Actor, assignment_id: int) -> Assignment:
    existing = repo.get(assignment_id, with_children=True)
    if existing is None:
        raise ValidationError(f"No assignment with id {assignment_id}")
    _require_apprentice(actor, existing.apprentice_id)
    return existing


def _reload(assignment_id: int) -> Assignment:
    fresh = repo.get(assignment_id, with_children=True)
    assert fresh is not None
    return fresh


def _validate(
    payload: dict[str, Any], *, apprentice: Apprentice | None, existing: Assignment | None
) -> dict[str, Any]:
    """Normalise an assignment payload; on an edit, only keys present."""
    data: dict[str, Any] = {}
    if existing is None or "title" in payload:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise ValidationError("An assignment needs a title")
        if len(title) > 200:
            raise ValidationError("An assignment title must be 200 characters or fewer")
        data["title"] = title
    if existing is None or "assignment_type" in payload:
        data["assignment_type"] = rules.validate_assignment_type(payload.get("assignment_type"))
    if "brief" in payload:
        brief = str(payload.get("brief") or "").strip()
        if len(brief) > config.ASSIGNMENT_BRIEF_MAX_LENGTH:
            raise ValidationError(
                f"A brief must be {config.ASSIGNMENT_BRIEF_MAX_LENGTH} characters or fewer"
            )
        data["brief"] = brief or None
    if "ksb_codes" in payload:
        data["ksb_codes"] = _validate_ksbs(payload.get("ksb_codes"), apprentice)
    if "due_date" in payload:
        data["due_date"] = _validate_date(payload.get("due_date"), "Due date")
    if "max_attempts" in payload:
        data["max_attempts"] = rules.validate_max_attempts(payload.get("max_attempts"))
    return data


def _validate_ksbs(value: Any, apprentice: Apprentice | None) -> str | None:
    """KSB codes, each one checked against the apprentice's standard.

    An assignment claiming a KSB the standard does not have would never
    line up with the portfolio or the skills matrix.
    """
    codes = rules.parse_ksb_codes(str(value or ""))
    if not codes:
        return None
    if apprentice is not None and apprentice.programme_id:
        known = {k.code for k in programme_repository.list_ksbs(apprentice.programme_id)}
        unknown = [c for c in codes if c not in known]
        if unknown:
            raise ValidationError(
                f"Not on this apprentice's standard: {', '.join(unknown)}"
            )
    return ", ".join(codes)


def _validate_evidence(value: Any, apprentice_id: int) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        evidence_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Evidence is not valid") from exc
    evidence = portfolio_repository.get_evidence(evidence_id, with_mappings=False)
    if evidence is None or evidence.apprentice_id != apprentice_id:
        raise ValidationError("That evidence is not in this apprentice's portfolio")
    return evidence_id


def _validate_status(value: str) -> str:
    cleaned = value.strip()
    found = next((s for s in config.ASSIGNMENT_STATUSES if s.casefold() == cleaned.casefold()),
                 None)
    if found is None:
        raise ValidationError(
            f"Assignment status must be one of: {', '.join(config.ASSIGNMENT_STATUSES)}"
        )
    return found


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _now() -> str:
    """A timestamp in the format SQLite's ``datetime('now')`` writes."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
