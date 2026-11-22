"""Reasonable adjustments and support arrangements.

Provider staff agree and review arrangements (``support.manage``). The
apprentice sees all of their own. An employer holds ``support.view`` too,
but sees only the arrangements the apprentice has agreed to share with
them — never the rest, never the history underneath, and never the
free-text support needs from enrolment, which were written without any
such consent. That narrowing happens here, in the query, so no screen
can forget it.

Every function takes ``actor`` first. Reads are scoped to what the actor
may see, and writes are refused outright.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.learner_support import (
    support_arrangements as rules,
)
from education_system.systems.apprenticeships.domain.learner_support.support_arrangements import (
    SupportArrangement,
    SupportNote,
    SupportRecord,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    support_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    staff_repository,
)
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

_ADJUSTMENT_LIMIT = 500


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def get_record(actor: Actor, apprentice_id: int) -> SupportRecord:
    """One apprentice's support, cut to what *actor* may see."""
    require(actor, "support.view")
    apprentice = _require_apprentice(actor, apprentice_id)
    return SupportRecord(
        apprentice_id=apprentice_id,
        support_needs=None if _is_employer(actor) else apprentice.support_needs,
        arrangements=list_arrangements(actor, apprentice_id=apprentice_id),
    )


def list_arrangements(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    in_force_only: bool = False,
    overdue_only: bool = False,
    due_within_days: int | None = None,
    responsible_staff_id: int | None = None,
) -> list[SupportArrangement]:
    """Arrangements for one apprentice, or across everyone *actor* may see.

    ``overdue_only`` keeps those whose review date has passed;
    ``due_within_days`` those whose review falls within that many days
    (overdue ones included).
    """
    require(actor, "support.view")
    if apprentice_id is not None:
        _require_apprentice(actor, apprentice_id)
        scope: dict[str, Any] = {"apprentice_id": apprentice_id}
    else:
        scope = apprentice_filters(actor)
    today = date.today()
    arrangements = repo.list_arrangements(
        **scope,
        status=rules.validate_status(status) if status else None,
        in_force_only=in_force_only,
        shared_only=_is_employer(actor),
        overdue_as_of=today.isoformat() if overdue_only else None,
        review_due_by=(
            (today + timedelta(days=due_within_days)).isoformat()
            if due_within_days is not None else None
        ),
        responsible_staff_id=responsible_staff_id,
    )
    if _may_read_history(actor) and arrangements:
        notes = repo.list_notes(a.arrangement_id for a in arrangements)
        for arrangement in arrangements:
            arrangement.notes = notes.get(arrangement.arrangement_id, [])
    return arrangements


def due_for_review(actor: Actor, *, within_days: int | None = None) -> list[SupportArrangement]:
    """Arrangements in force whose review is overdue or coming up."""
    days = config.SUPPORT_REVIEW_DUE_SOON_DAYS if within_days is None else within_days
    return list_arrangements(actor, due_within_days=days)


def get_arrangement(actor: Actor, arrangement_id: int) -> SupportArrangement:
    require(actor, "support.view")
    arrangement = _require_arrangement(actor, arrangement_id)
    if _may_read_history(actor):
        arrangement.notes = repo.list_notes([arrangement_id]).get(arrangement_id, [])
    return arrangement


# ═════════════════════════════════════════════════════════════════════
# Writes
# ═════════════════════════════════════════════════════════════════════

def add_arrangement(
    actor: Actor, apprentice_id: int, payload: dict[str, Any]
) -> SupportArrangement:
    """Record a new arrangement.

    A tutor recording one is responsible for it unless they name
    somebody else, so a new arrangement always has an owner to chase.
    """
    require(actor, "support.manage")
    _require_apprentice(actor, apprentice_id)

    data = _validate(payload, existing=None)
    if data.get("responsible_staff_id") is None and actor.staff_id is not None:
        data["responsible_staff_id"] = actor.staff_id
    data.update(apprentice_id=apprentice_id, created_by=actor.username)
    arrangement_id = repo.create_arrangement(data)
    compliance_repository.record(
        action="create", entity="support_arrangement", entity_id=arrangement_id,
        actor=actor.username, actor_role=actor.role,
        # The category only — the adjustment itself may be sensitive.
        detail=f"{data['need_category']} arrangement for apprentice {apprentice_id}"
               + (" (shared with employer)" if data["share_with_employer"] else ""),
    )
    logger.info("Support arrangement %s added for apprentice %s by %s",
                arrangement_id, apprentice_id, actor.username)
    return get_arrangement(actor, arrangement_id)


def update_arrangement(
    actor: Actor, arrangement_id: int, payload: dict[str, Any]
) -> SupportArrangement:
    """Change an arrangement. Only the fields supplied change.

    A change of status or of sharing is written into the history
    automatically — those are the two changes somebody will later ask
    about — and a ``note`` in the payload is added alongside.
    """
    require(actor, "support.manage")
    existing = _require_arrangement(actor, arrangement_id)

    data = _validate(payload, existing=existing)
    lines = _describe_changes(existing, data)
    extra = rules.validate_text(payload.get("note"), "Note")
    if extra:
        lines.append(extra)
    repo.update_arrangement(arrangement_id, data, note=_note(actor, lines))
    compliance_repository.record(
        action="update", entity="support_arrangement", entity_id=arrangement_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(k for k in payload if k != "note")) or "note added",
    )
    return get_arrangement(actor, arrangement_id)


def record_review(
    actor: Actor,
    arrangement_id: int,
    *,
    outcome: str,
    next_review_date: str | None,
    status: str | None = None,
) -> SupportArrangement:
    """The arrangement has been reviewed: say how it went and when it is next due.

    Ending an arrangement at review needs no next date; keeping it in
    force does, or it would drop off every overdue list for good.
    """
    require(actor, "support.manage")
    existing = _require_arrangement(actor, arrangement_id)
    text = rules.validate_text(outcome, "What the review found", required=True)

    new_status = rules.validate_status(status) if status else existing.status
    review = rules.validate_review_date(
        next_review_date, status=new_status, today=date.today(), current=None,
    )
    lines = [f"Reviewed: {text}"]
    if new_status != existing.status:
        lines.append(f"Status {existing.status} -> {new_status}")
    if review:
        lines.append(f"Next review {review}")
    repo.update_arrangement(
        arrangement_id, {"status": new_status, "review_date": review},
        note=_note(actor, lines),
    )
    compliance_repository.record(
        action="update", entity="support_arrangement", entity_id=arrangement_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Reviewed; {existing.status} -> {new_status}; next review {review or '—'}",
    )
    return get_arrangement(actor, arrangement_id)


def add_note(actor: Actor, arrangement_id: int, body: str) -> SupportNote:
    require(actor, "support.manage")
    _require_arrangement(actor, arrangement_id)
    text = rules.validate_text(body, "A note", required=True)
    assert text is not None
    note_id = repo.add_note(
        arrangement_id, author=actor.username, author_role=actor.role, body=text,
    )
    compliance_repository.record(
        action="create", entity="support_note", entity_id=note_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Note on support arrangement {arrangement_id}",
    )
    notes = repo.list_notes([arrangement_id]).get(arrangement_id, [])
    return next(n for n in notes if n.note_id == note_id)


def delete_arrangement(actor: Actor, arrangement_id: int, *, reason: str) -> None:
    """Remove an arrangement recorded by mistake.

    One that was real but no longer applies should be Ended instead,
    which keeps it and its history.
    """
    require(actor, "support.manage")
    existing = _require_arrangement(actor, arrangement_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete an arrangement")
    compliance_repository.record(
        action="delete", entity="support_arrangement", entity_id=arrangement_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.need_category} arrangement for apprentice "
               f"{existing.apprentice_id}: {reason}",
    )
    repo.delete_arrangement(arrangement_id)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _is_employer(actor: Actor) -> bool:
    return actor.role == config.EMPLOYER


def _may_read_history(actor: Actor) -> bool:
    """Provider staff and the apprentice themselves — never the employer."""
    return actor.is_provider or actor.role == config.APPRENTICE


def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_arrangement(actor: Actor, arrangement_id: int) -> SupportArrangement:
    arrangement = repo.get_arrangement(arrangement_id)
    if arrangement is None:
        raise ValidationError(f"No support arrangement with id {arrangement_id}")
    _require_apprentice(actor, arrangement.apprentice_id)
    # Worded like the apprentice refusal: an employer must not be able to
    # tell an unshared arrangement from one that does not exist.
    if _is_employer(actor) and not rules.visible_to_employer(arrangement):
        raise PermissionDenied("You do not have access to this support arrangement")
    return arrangement


def _validate(
    payload: dict[str, Any], *, existing: SupportArrangement | None
) -> dict[str, Any]:
    """Normalise and check an arrangement payload.

    Only keys actually present are validated and returned, so a partial
    edit does not blank the rest. The review date is judged against the
    status the arrangement will have after the edit.
    """
    data: dict[str, Any] = {}
    if existing is None or "need_category" in payload:
        data["need_category"] = rules.validate_category(payload.get("need_category"))
    if existing is None or "adjustment" in payload:
        data["adjustment"] = rules.validate_text(
            payload.get("adjustment"), "The adjustment", required=True, limit=_ADJUSTMENT_LIMIT,
        )
    if "arrangements" in payload:
        data["arrangements"] = rules.validate_text(payload.get("arrangements"), "Arrangements")
    if existing is None or "status" in payload:
        data["status"] = rules.validate_status(payload.get("status"))
    if existing is None or "share_with_employer" in payload:
        data["share_with_employer"] = _flag(payload.get("share_with_employer"))
    if "responsible_staff_id" in payload:
        data["responsible_staff_id"] = _validate_staff(payload.get("responsible_staff_id"))

    status = data.get("status") or (existing.status if existing else "Active")
    if existing is None or "review_date" in payload or "status" in payload:
        data["review_date"] = rules.validate_review_date(
            payload.get("review_date") if "review_date" in payload
            else getattr(existing, "review_date", None),
            status=status,
            today=date.today(),
            current=getattr(existing, "review_date", None),
        )
    return data


def _describe_changes(existing: SupportArrangement, data: dict[str, Any]) -> list[str]:
    lines = []
    if "status" in data and data["status"] != existing.status:
        lines.append(f"Status {existing.status} -> {data['status']}")
    if "share_with_employer" in data and data["share_with_employer"] != existing.share_with_employer:
        lines.append(
            "Now shared with the employer" if data["share_with_employer"]
            else "No longer shared with the employer"
        )
    if "review_date" in data and data["review_date"] != existing.review_date:
        lines.append(f"Review date {existing.review_date or '—'} -> {data['review_date'] or '—'}")
    return lines


def _note(actor: Actor, lines: list[str]) -> dict[str, str] | None:
    if not lines:
        return None
    return {"author": actor.username, "author_role": actor.role, "body": "; ".join(lines)}


def _validate_staff(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        staff_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Responsible staff must be a staff id") from exc
    if staff_repository.get(staff_id) is None:
        raise ValidationError(f"No member of staff with id {staff_id}")
    return staff_id


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)
