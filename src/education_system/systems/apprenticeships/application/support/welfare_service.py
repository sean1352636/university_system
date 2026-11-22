"""Welfare concerns, case notes and the risk profile.

The most restricted records in the system. Only provider staff see them
— never the apprentice, the employer or the end-point assessor — and a
tutor only for apprentices on their own caseload. Two checks enforce
that, deliberately redundant: the ``welfare.*`` permissions, which only
admin and staff hold, and a provider-role check of its own, so that a
later, broader grant of ``welfare.view`` in config cannot quietly open
case notes to an outsider.

Audit entries name the category and severity, never the description or
the notes: the audit log is read for who did what, and copying the case
into it would spread the very information this module keeps close.

The risk profile reads warning signs other modules own — attendance,
off-the-job hours, overdue reviews and learning-plan objectives — and
combines them with the open concerns through
:func:`domain.learner_support.welfare.assess_risk`. It is gated on
``welfare.view`` because it shows the concerns.

This module does not feed the platform's safeguarding module
(``platform/governance/safeguarding``); a formal referral is still made
through the designated safeguarding lead.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ApprenticeSummary,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.learner_support import welfare as rules
from education_system.systems.apprenticeships.domain.learner_support.welfare import (
    RiskProfile,
    WelfareConcern,
    WelfareNote,
)
from education_system.systems.apprenticeships.domain.training import attendance as attendance_rules
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    welfare_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    learning_plan_repository,
    review_repository,
    staff_repository,
    training_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

_LEVEL_ORDER = {"High": 0, "Medium": 1, "Low": 2}


# ═════════════════════════════════════════════════════════════════════
# Concerns — reads
# ═════════════════════════════════════════════════════════════════════

def list_concerns(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    open_only: bool = False,
    status: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    assigned_to: int | None = None,
) -> list[WelfareConcern]:
    """Concerns for one apprentice, or across *actor*'s caseload."""
    _require(actor, "welfare.view")
    if apprentice_id is not None:
        _require_apprentice(actor, apprentice_id)
        scope: dict[str, Any] = {"apprentice_id": apprentice_id}
    else:
        scope = apprentice_filters(actor)
    return repo.list_concerns(
        **scope,
        open_only=open_only,
        status=rules.validate_status(status) if status else None,
        severity=rules.validate_severity(severity) if severity else None,
        category=rules.validate_category(category) if category else None,
        assigned_to=assigned_to,
    )


def get_concern(actor: Actor, concern_id: int) -> WelfareConcern:
    """One concern with its full case notes, oldest first."""
    _require(actor, "welfare.view")
    _require_concern(actor, concern_id)
    concern = repo.get_concern(concern_id, with_notes=True)
    assert concern is not None
    return concern


# ═════════════════════════════════════════════════════════════════════
# Concerns — writes
# ═════════════════════════════════════════════════════════════════════

def raise_concern(actor: Actor, apprentice_id: int, payload: dict[str, Any]) -> WelfareConcern:
    """Record a new concern.

    It is assigned to whoever raised it when they are a tutor and no one
    else is named, so a concern is never left without somebody holding it.
    """
    _require(actor, "welfare.manage")
    _require_apprentice(actor, apprentice_id)

    data = {
        "apprentice_id": apprentice_id,
        "category": rules.validate_category(payload.get("category")),
        "severity": rules.validate_severity(payload.get("severity")),
        "description": rules.validate_text(payload.get("description"), "The description"),
        "status": "Open",
        "raised_by": actor.username,
        "assigned_to": _validate_staff(payload.get("assigned_to")) or actor.staff_id,
    }
    concern_id = repo.create_concern(data)
    compliance_repository.record(
        action="create", entity="welfare_concern", entity_id=concern_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['category']} concern ({data['severity']}) for apprentice {apprentice_id}",
    )
    logger.info("Welfare concern %s raised for apprentice %s by %s",
                concern_id, apprentice_id, actor.username)
    return get_concern(actor, concern_id)


def update_concern(actor: Actor, concern_id: int, payload: dict[str, Any]) -> WelfareConcern:
    """Change a concern's category, severity, description or assignee.

    Every change is written into the case notes as well as made, so the
    notes read as a complete account: "severity Medium -> High" belongs
    in the history, not only in the current row. Status has its own
    function, because each status carries its own obligations.
    """
    _require(actor, "welfare.manage")
    existing = _require_concern(actor, concern_id)
    if "status" in payload:
        raise ValidationError("Change a concern's status with change_status, not an edit")

    data: dict[str, Any] = {}
    lines: list[str] = []
    if "category" in payload:
        data["category"] = rules.validate_category(payload.get("category"))
        if data["category"] != existing.category:
            lines.append(f"Category {existing.category} -> {data['category']}")
    if "severity" in payload:
        data["severity"] = rules.validate_severity(payload.get("severity"))
        if data["severity"] != existing.severity:
            lines.append(f"Severity {existing.severity} -> {data['severity']}")
    if "description" in payload:
        data["description"] = rules.validate_text(payload.get("description"), "The description")
        if data["description"] != existing.description:
            lines.append("Description revised")
    if "assigned_to" in payload:
        data["assigned_to"] = _validate_staff(payload.get("assigned_to"))
        if data["assigned_to"] != existing.assigned_to:
            member = staff_repository.get(data["assigned_to"]) if data["assigned_to"] else None
            lines.append(f"Assigned to {member.full_name if member else 'nobody'}")
    extra = rules.validate_text(payload.get("note"), "The note", required=False)
    if extra:
        lines.append(extra)

    repo.update_concern(concern_id, data, note=_note(actor, lines))
    compliance_repository.record(
        action="update", entity="welfare_concern", entity_id=concern_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(k for k in data)) or "note added",
    )
    return get_concern(actor, concern_id)


def change_status(
    actor: Actor,
    concern_id: int,
    status: str,
    *,
    note: str | None = None,
    escalated_to: str | None = None,
    outcome: str | None = None,
) -> WelfareConcern:
    """Move a concern on: to Monitoring, Escalated, Closed, or back to Open.

    Escalating records who to and when; closing records the outcome and
    when. Reopening a closed concern clears both close fields, keeping
    the old outcome in the case note that records the reopening.
    """
    _require(actor, "welfare.manage")
    existing = _require_concern(actor, concern_id)
    new = rules.validate_status(status)
    target = rules.validate_text(escalated_to, "Escalated to", required=False)
    result = rules.validate_text(outcome, "The outcome", required=False)
    rules.check_transition(existing.status, new, escalated_to=target, outcome=result)

    now = _now()
    data: dict[str, Any] = {"status": new}
    lines = [f"Status {existing.status} -> {new}"]
    if new == rules.ESCALATED:
        data.update(escalated_to=target, escalated_at=now)
        lines.append(f"escalated to {target}")
    if new == rules.CLOSED:
        data.update(closed_at=now, outcome=result)
        lines.append(f"outcome: {result}")
    elif existing.status == rules.CLOSED:
        data.update(closed_at=None, outcome=None)
        if existing.outcome:
            lines.append(f"reopened; previous outcome was: {existing.outcome}")
    extra = rules.validate_text(note, "The note", required=False)
    if extra:
        lines.append(extra)

    repo.update_concern(concern_id, data, note=_note(actor, lines))
    compliance_repository.record(
        action="update", entity="welfare_concern", entity_id=concern_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{existing.status} -> {new}",
    )
    logger.info("Welfare concern %s moved %s -> %s by %s",
                concern_id, existing.status, new, actor.username)
    return get_concern(actor, concern_id)


def add_note(actor: Actor, concern_id: int, note: str) -> WelfareNote:
    """Add a case note. Notes cannot be edited or deleted: they are the record."""
    _require(actor, "welfare.manage")
    _require_concern(actor, concern_id)
    text = rules.validate_text(note, "A case note")
    assert text is not None
    note_id = repo.add_note(concern_id, author=actor.username, author_role=actor.role, note=text)
    compliance_repository.record(
        action="create", entity="welfare_note", entity_id=note_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Case note on welfare concern {concern_id}",
    )
    return next(n for n in repo.list_notes(concern_id) if n.note_id == note_id)


# ═════════════════════════════════════════════════════════════════════
# Risk
# ═════════════════════════════════════════════════════════════════════

def risk_profile(actor: Actor, apprentice_id: int) -> RiskProfile:
    """How worried to be about one apprentice, and why."""
    _require(actor, "welfare.view")
    _require_apprentice(actor, apprentice_id)
    summary = apprentice_repository.get_summary(apprentice_id)
    assert summary is not None
    today = date.today()
    overdue_reviews = len(
        review_repository.list_reviews(apprentice_id=apprentice_id, overdue_only=True)
    )
    return _profile(
        summary,
        attendance=training_repository.attendance_summary(apprentice_id),
        overdue_reviews=overdue_reviews,
        overdue_objectives=_overdue_objectives(apprentice_id, today),
        open_concerns=repo.list_concerns(apprentice_id=apprentice_id, open_only=True),
        today=today,
    )


def at_risk(actor: Actor, *, include_low: bool = False) -> list[RiskProfile]:
    """The active apprentices on *actor*'s caseload worth worrying about.

    Highest risk first. Reads each warning sign once for the whole
    cohort where the owning repository allows it — attendance, reviews
    and concerns are one query apiece — and the learning plan per
    apprentice, which has no cohort query.
    """
    _require(actor, "welfare.view")
    scope = apprentice_filters(actor)
    cohort = apprentice_repository.list_summaries(**scope, active_only=True)
    if not cohort:
        return []
    ids = [s.apprentice.apprentice_id for s in cohort]
    today = date.today()

    marks = training_repository.attendance_by_apprentice(ids)
    overdue_reviews = Counter(
        r.apprentice_id for r in review_repository.list_reviews(**scope, overdue_only=True)
    )
    concerns: dict[int, list[WelfareConcern]] = defaultdict(list)
    for concern in repo.list_concerns(**scope, open_only=True):
        concerns[concern.apprentice_id].append(concern)

    profiles = []
    for summary in cohort:
        aid = summary.apprentice.apprentice_id
        profile = _profile(
            summary,
            attendance=attendance_rules.summarise(aid, marks.get(aid, [])),
            overdue_reviews=overdue_reviews.get(aid, 0),
            overdue_objectives=_overdue_objectives(aid, today),
            open_concerns=concerns.get(aid, []),
            today=today,
        )
        if include_low or profile.is_at_risk:
            profiles.append(profile)
    profiles.sort(key=lambda p: (_LEVEL_ORDER[p.level], -p.score, p.apprentice_name))
    return profiles


def _profile(
    summary: ApprenticeSummary,
    *,
    attendance: attendance_rules.AttendanceSummary,
    overdue_reviews: int,
    overdue_objectives: int,
    open_concerns: list[WelfareConcern],
    today: date,
) -> RiskProfile:
    behind = summary.is_behind_on(today)
    return rules.assess_risk(
        summary.apprentice.apprentice_id,
        apprentice_name=summary.full_name,
        tutor_name=summary.tutor_name,
        attendance_concern=attendance.concern_reason if attendance.is_concern else None,
        otj_behind=behind,
        otj_detail=(
            f"{summary.otj_percent:.0f}% of hours logged, "
            f"{summary.progress_percent_on(today):.0f}% of the programme elapsed"
            if behind else ""
        ),
        overdue_reviews=overdue_reviews,
        overdue_objectives=overdue_objectives,
        open_concerns=open_concerns,
    )


def _overdue_objectives(apprentice_id: int, today: date) -> int:
    return sum(
        1 for o in learning_plan_repository.list_objectives(apprentice_id) if o.is_overdue(today)
    )


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _require(actor: Actor, permission: str) -> None:
    """The permission, and provider staff whatever the permission table says."""
    require(actor, permission)
    if not actor.is_provider:
        raise PermissionDenied("Welfare records are for provider staff only")


def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_concern(actor: Actor, concern_id: int) -> WelfareConcern:
    concern = repo.get_concern(concern_id)
    if concern is None:
        raise ValidationError(f"No welfare concern with id {concern_id}")
    _require_apprentice(actor, concern.apprentice_id)
    return concern


def _validate_staff(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        staff_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Assigned to must be a staff id") from exc
    if staff_repository.get(staff_id) is None:
        raise ValidationError(f"No member of staff with id {staff_id}")
    return staff_id


def _note(actor: Actor, lines: list[str]) -> dict[str, str] | None:
    if not lines:
        return None
    return {"author": actor.username, "author_role": actor.role, "note": "; ".join(lines)}


def _now() -> str:
    """A UTC timestamp in the shape ``datetime('now')`` gives ``raised_at``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
