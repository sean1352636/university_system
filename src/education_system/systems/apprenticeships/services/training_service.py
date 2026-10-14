"""Training delivery: sessions, registers, the training plan, off-the-job hours.

Off-the-job hours are the single number a funding audit turns on, so
this module is deliberately the only way they move. Two paths feed the
same log: an apprentice records what they did and an approver signs it,
or a tutor marks a register and the hours the session was worth land
already approved.

Every function takes ``actor`` first. That is not decoration — reads are
scoped to what the actor may see, writes are refused outright, and the
approval queue an employer opens holds their own apprentices only.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ValidationError,
)
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.domain.training import attendance as attendance_rules
from education_system.systems.apprenticeships.domain.training import learning_plan as plan_rules
from education_system.systems.apprenticeships.domain.training import off_the_job_hours as otj
from education_system.systems.apprenticeships.domain.training import sessions
from education_system.systems.apprenticeships.domain.training.attendance import AttendanceSummary
from education_system.systems.apprenticeships.domain.training.off_the_job_hours import (
    OTJEntry,
    OTJSummary,
)
from education_system.systems.apprenticeships.domain.training.sessions import (
    SessionAttendance,
    TrainingPlanItem,
    TrainingSession,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    training_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    learning_plan_repository,
    programme_repository,
    staff_repository,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

# A register-generated entry still needs an activity type from the
# off-the-job list, and the delivery mode is the closest thing a session
# records.
_ACTIVITY_TYPE_BY_MODE: dict[str, str] = {
    "Classroom": "Teaching of theory",
    "Workshop": "Practical training",
    "Online live": "Teaching of theory",
    "Online self-paced": "Online learning",
    "Workplace": "Practical training",
    "Day release": "Teaching of theory",
    "Block release": "Teaching of theory",
}


# ═════════════════════════════════════════════════════════════════════
# Sessions
# ═════════════════════════════════════════════════════════════════════

def list_sessions(
    actor: Actor,
    *,
    programme_id: int | None = None,
    trainer_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    upcoming_only: bool = False,
) -> list[TrainingSession]:
    """The timetable, filtered as the caller asked.

    Not scoped per actor: a session is a scheduled block of delivery, not
    somebody's personal data. Who attended it is another matter — see
    :func:`get_register`.
    """
    require(actor, "training.view")
    return repo.list_sessions(
        programme_id=programme_id,
        trainer_id=trainer_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        upcoming_only=upcoming_only,
    )


def get_session(actor: Actor, session_id: int) -> TrainingSession:
    require(actor, "training.view")
    session = repo.get_session(session_id)
    if session is None:
        raise ValidationError(f"No training session with id {session_id}")
    return session


def create_session(actor: Actor, payload: dict[str, Any]) -> TrainingSession:
    """Schedule a session.

    Always created as ``Scheduled``: calling a session off is a separate,
    audited move that carries a reason with it.
    """
    require(actor, "training.manage")
    data = _validate_session(payload, existing=None)
    data["status"] = "Scheduled"

    session_id = repo.create_session(data)
    compliance_repository.record(
        action="create", entity="training_session", entity_id=session_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data.get('title')} on {data.get('session_date')}",
    )
    logger.info("Training session %s created by %s", session_id, actor.username)

    created = repo.get_session(session_id)
    assert created is not None
    return created


def update_session(actor: Actor, session_id: int, payload: dict[str, Any]) -> TrainingSession:
    require(actor, "training.manage")
    existing = get_session(actor, session_id)

    data = _validate_session(payload, existing=existing)
    repo.update_session(session_id, data)
    compliance_repository.record(
        action="update", entity="training_session", entity_id=session_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get_session(session_id)
    assert updated is not None
    return updated


def cancel_session(actor: Actor, session_id: int, *, reason: str) -> TrainingSession:
    """Call a session off, keeping the record and the reason.

    Cancelling rather than deleting is what lets a provider account for a
    gap in delivery when the funding body asks why an apprentice's hours
    dipped that month.
    """
    require(actor, "training.manage")
    existing = get_session(actor, session_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to cancel a session")
    if existing.status == "Cancelled":
        raise ValidationError("That session is already cancelled")

    repo.update_session(session_id, {"status": "Cancelled"})
    compliance_repository.record(
        action="update", entity="training_session", entity_id=session_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Cancelled: {reason}",
    )
    logger.info("Training session %s cancelled by %s: %s", session_id, actor.username, reason)

    updated = repo.get_session(session_id)
    assert updated is not None
    return updated


def delete_session(actor: Actor, session_id: int, *, reason: str) -> None:
    """Erase a session and its register.

    For a session scheduled by mistake. One that was scheduled and then
    called off is a cancellation, which keeps the record. The off-the-job
    entries the register generated survive either way — those hours were
    genuinely trained.
    """
    require(actor, "training.manage")
    existing = get_session(actor, session_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to delete a session")

    compliance_repository.record(
        action="delete", entity="training_session", entity_id=session_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.title} ({existing.session_date}): {reason}",
    )
    repo.delete_session(session_id)
    logger.warning(
        "Training session %s (%s) deleted by %s: %s",
        session_id, existing.title, actor.username, reason,
    )


# ═════════════════════════════════════════════════════════════════════
# Registers
# ═════════════════════════════════════════════════════════════════════

def get_register(actor: Actor, session_id: int) -> list[SessionAttendance]:
    """Who was marked what on one session."""
    get_session(actor, session_id)
    marks = repo.list_attendance(session_id)
    # Whoever delivers the session sees the whole room — they have to, to
    # mark it. An apprentice or an employer reading the same register
    # sees only the people they are entitled to see anywhere else.
    if actor.can("training.manage"):
        return marks
    visible = _visible_apprentice_ids(actor)
    if visible is None:
        return marks
    return [mark for mark in marks if mark.apprentice_id in visible]


def mark_attendance(
    actor: Actor,
    session_id: int,
    apprentice_id: int,
    *,
    status: str,
    otj_hours: float | None = None,
    notes: str | None = None,
    absence_reason: str | None = None,
) -> SessionAttendance:
    """Mark one apprentice on a register, and log the hours it earned.

    An absence (Absent or Excused) is stored with its reason; see
    :func:`attendance.validate_absence_reason` for what each mark needs.
    """
    require(actor, "training.manage")
    session = repo.get_session(session_id)
    if session is None:
        raise ValidationError(f"No training session with id {session_id}")
    _require_apprentice(actor, apprentice_id)

    mark = sessions.validate_attendance_status(status)
    reason = attendance_rules.validate_absence_reason(mark, absence_reason)
    if otj_hours is None or mark not in sessions.HOURS_EARNING_STATUSES:
        # An override only applies to a mark that earns hours: an absence
        # earns nothing however the register was typed.
        hours = sessions.hours_for_mark(mark, session.otj_hours)
    else:
        hours = otj.validate_hours(otj_hours)

    attendance_id = repo.upsert_attendance(
        session_id, apprentice_id,
        status=mark, otj_hours=hours, notes=_optional_text(notes), absence_reason=reason,
    )
    _sync_register_hours(actor, session, apprentice_id, mark, hours)
    compliance_repository.record(
        action="update", entity="attendance", entity_id=attendance_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Apprentice {apprentice_id} marked {mark}"
        + (f" — {reason}" if reason else "")
        + f" ({hours}h) on session {session_id}",
    )
    logger.info(
        "Apprentice %s marked %s on session %s by %s",
        apprentice_id, mark, session_id, actor.username,
    )

    record = repo.get_attendance(session_id, apprentice_id)
    assert record is not None
    return record


def attendance_summary(actor: Actor, apprentice_id: int) -> AttendanceSummary:
    require(actor, "training.view")
    _require_apprentice(actor, apprentice_id)
    return repo.attendance_summary(apprentice_id)


def _sync_register_hours(
    actor: Actor,
    session: TrainingSession,
    apprentice_id: int,
    mark: str,
    hours: float,
) -> None:
    """Keep the off-the-job log in step with the register.

    Attending taught delivery *is* off-the-job training, so a Present or
    Late mark writes those hours straight into the log as Approved: the
    tutor marking the register is the same person who would have
    approved the entry, and making an apprentice re-type hours their
    trainer just watched them do is how logs end up under-recorded and
    funding gets clawed back.

    The entry is keyed on the session, so re-marking a register corrects
    the hours it already generated instead of adding a second entry, and
    changing a mark to Absent or Excused takes them away again.
    """
    existing = repo.get_entry_by_session(session.session_id, apprentice_id)
    if mark not in sessions.HOURS_EARNING_STATUSES or hours <= 0:
        if existing is not None:
            repo.delete_entry(existing.entry_id)
        return

    stamp = _now()
    data: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "activity_date": session.session_date,
        "hours": hours,
        "activity_type": _ACTIVITY_TYPE_BY_MODE.get(
            session.delivery_mode, "Teaching of theory"
        ),
        "description": f"Attended: {session.title}",
        "ksb_codes": session.ksb_codes,
        "status": "Approved",
        "session_id": session.session_id,
        "submitted_at": stamp,
        "approved_by": actor.username,
        "approved_at": stamp,
        "decision_note": "Generated from the training register",
    }
    if existing is None:
        repo.create_entry(data)
    else:
        repo.update_entry(existing.entry_id, data)


# ═════════════════════════════════════════════════════════════════════
# Training plan
# ═════════════════════════════════════════════════════════════════════

def list_plan_items(
    actor: Actor, apprentice_id: int, *, status: str | None = None
) -> list[TrainingPlanItem]:
    require(actor, "training.view")
    _require_apprentice(actor, apprentice_id)
    return repo.list_plan_items(apprentice_id, status=status)


def add_plan_item(
    actor: Actor, apprentice_id: int, payload: dict[str, Any]
) -> TrainingPlanItem:
    require(actor, "training.manage")
    _require_apprentice(actor, apprentice_id)

    data = _validate_plan_item(payload, existing=None)
    data["apprentice_id"] = apprentice_id
    _check_objective(data.get("objective_id"), apprentice_id)
    item_id = repo.create_plan_item(data)
    compliance_repository.record(
        action="create", entity="training_plan_item", entity_id=item_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data.get('title')} for apprentice {apprentice_id}",
    )
    logger.info(
        "Training plan item %s added for apprentice %s by %s",
        item_id, apprentice_id, actor.username,
    )

    created = repo.get_plan_item(item_id)
    assert created is not None
    return created


def update_plan_item(
    actor: Actor, item_id: int, payload: dict[str, Any]
) -> TrainingPlanItem:
    require(actor, "training.manage")
    existing = _require_plan_item(actor, item_id)

    data = _validate_plan_item(payload, existing=existing)
    if "objective_id" in data:
        _check_objective(data["objective_id"], existing.apprentice_id)
    repo.update_plan_item(item_id, data)
    compliance_repository.record(
        action="update", entity="training_plan_item", entity_id=item_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
    )

    updated = repo.get_plan_item(item_id)
    assert updated is not None
    return updated


def delete_plan_item(actor: Actor, item_id: int) -> None:
    require(actor, "training.manage")
    existing = _require_plan_item(actor, item_id)

    compliance_repository.record(
        action="delete", entity="training_plan_item", entity_id=item_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.title} from apprentice {existing.apprentice_id}'s plan",
    )
    repo.delete_plan_item(item_id)
    logger.info("Training plan item %s deleted by %s", item_id, actor.username)


# ═════════════════════════════════════════════════════════════════════
# Off-the-job hours
# ═════════════════════════════════════════════════════════════════════

def otj_summary(actor: Actor, apprentice_id: int) -> OTJSummary:
    """Target, progress and pace for one apprentice."""
    require(actor, "otj.view")
    apprentice = _require_apprentice(actor, apprentice_id)
    totals = repo.hour_totals(apprentice_id)
    return otj.build_summary(
        apprentice_id,
        start_iso=apprentice.start_date,
        end_iso=apprentice.planned_end_date,
        weekly_hours=apprentice.weekly_hours,
        approved=totals["approved"],
        pending=totals["pending"],
        draft=totals["draft"],
        entry_count=int(totals["count"]),
    )


def list_otj_entries(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[OTJEntry]:
    """The log *actor* may see, with any extra filters applied.

    An employer passing another organisation's ``apprentice_id`` does not
    widen anything: their own scope is applied last and wins.
    """
    require(actor, "otj.view")
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    }
    filters.update(apprentice_filters(actor))
    return repo.list_entries(**filters)


def log_hours(actor: Actor, payload: dict[str, Any]) -> OTJEntry:
    """Record an off-the-job activity.

    Entries start as ``Draft``: hours only count once an approver has
    signed them, and going straight to approved would let an apprentice
    sign off their own funding evidence.
    """
    require(actor, "otj.log")
    data = _validate_entry(payload, existing=None)
    if actor.role == config.APPRENTICE:
        # An apprentice logs against themselves whatever the form posted.
        if actor.apprentice_id is None:
            raise ValidationError("Your login is not linked to an apprentice record")
        data["apprentice_id"] = actor.apprentice_id
    if data.get("apprentice_id") is None:
        raise ValidationError("An apprentice is required")
    _require_apprentice(actor, data["apprentice_id"])
    data["status"] = "Draft"

    entry_id = repo.create_entry(data)
    compliance_repository.record(
        action="create", entity="otj_entry", entity_id=entry_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{data['hours']}h {data['activity_type']} on {data['activity_date']}",
    )
    logger.info(
        "OTJ entry %s logged for apprentice %s by %s",
        entry_id, data["apprentice_id"], actor.username,
    )

    created = repo.get_entry(entry_id)
    assert created is not None
    return created


def submit_hours(actor: Actor, entry_id: int) -> OTJEntry:
    """Send draft or rejected hours to an approver."""
    entry = _require_entry(actor, entry_id)
    if not actor.is_admin and not (
        actor.role == config.APPRENTICE and entry.apprentice_id == actor.apprentice_id
    ):
        raise PermissionDenied("Only the apprentice whose hours these are may submit them")
    if entry.status not in ("Draft", "Rejected"):
        raise ValidationError(
            f"Only draft or rejected hours can be submitted; these are {entry.status.lower()}"
        )

    repo.set_entry_status(entry_id, "Submitted", submitted_at=_now())
    compliance_repository.record(
        action="update", entity="otj_entry", entity_id=entry_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Submitted {entry.hours}h for approval",
    )
    logger.info("OTJ entry %s submitted by %s", entry_id, actor.username)

    updated = repo.get_entry(entry_id)
    assert updated is not None
    return updated


def approve_hours(actor: Actor, entry_id: int, *, note: str | None = None) -> OTJEntry:
    """Sign hours off so they count towards the target."""
    require(actor, "otj.approve")
    entry = _require_entry(actor, entry_id)
    _require_submitted(entry)

    _approve_entry(actor, entry, _optional_text(note))
    logger.info("OTJ entry %s approved by %s", entry_id, actor.username)

    updated = repo.get_entry(entry_id)
    assert updated is not None
    return updated


def reject_hours(actor: Actor, entry_id: int, *, reason: str) -> OTJEntry:
    """Send hours back to the apprentice.

    A reason is not optional: a rejected entry becomes editable again, so
    the apprentice needs to know what to change before resubmitting.
    """
    require(actor, "otj.approve")
    entry = _require_entry(actor, entry_id)
    _require_submitted(entry)
    if not (reason or "").strip():
        raise ValidationError("A reason is required to reject hours")

    stamp = _now()
    repo.set_entry_status(
        entry_id, "Rejected",
        approved_by=actor.username, approved_at=stamp, decision_note=reason.strip(),
    )
    compliance_repository.record(
        action="reject", entity="otj_entry", entity_id=entry_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Rejected {entry.hours}h on {entry.activity_date}: {reason.strip()}",
        changes=audit.diff(
            entry,
            {"status": "Rejected", "approved_by": actor.username,
             "decision_note": reason.strip()},
            fields=("status", "approved_by", "decision_note"),
        ),
    )
    logger.info("OTJ entry %s rejected by %s: %s", entry_id, actor.username, reason)

    updated = repo.get_entry(entry_id)
    assert updated is not None
    return updated


def bulk_approve(actor: Actor, entry_ids: list[int], *, note: str | None = None) -> int:
    """Approve a queue in one go, returning how many actually moved.

    An entry that is missing or no longer submitted — somebody else got
    to it first — is skipped rather than aborting the batch, because
    losing a whole afternoon's approvals to one stale row is worse than
    approving nineteen of twenty. An entry outside the actor's scope
    still refuses outright: that is a permission failure, not a race.
    """
    require(actor, "otj.approve")
    decision_note = _optional_text(note)
    approved = 0
    for entry_id in entry_ids:
        entry = repo.get_entry(entry_id)
        if entry is None:
            continue
        _require_apprentice(actor, entry.apprentice_id)
        if entry.status != "Submitted":
            continue
        _approve_entry(actor, entry, decision_note)
        approved += 1

    logger.info("%s OTJ entries bulk approved by %s", approved, actor.username)
    return approved


def update_entry(actor: Actor, entry_id: int, payload: dict[str, Any]) -> OTJEntry:
    require(actor, "otj.log")
    existing = _require_entry(actor, entry_id)
    _require_editable(existing)

    data = _validate_entry(payload, existing=existing)
    # Moving an entry to another apprentice is not an edit, it is a
    # different entry.
    data.pop("apprentice_id", None)
    repo.update_entry(entry_id, data)
    updated = repo.get_entry(entry_id)
    assert updated is not None
    compliance_repository.record(
        action="update", entity="otj_entry", entity_id=entry_id,
        actor=actor.username, actor_role=actor.role,
        detail=", ".join(sorted(data)) or "no change",
        changes=audit.diff(existing, updated, fields=sorted(data)),
    )
    return updated


def delete_entry(actor: Actor, entry_id: int) -> None:
    require(actor, "otj.log")
    existing = _require_entry(actor, entry_id)
    _require_editable(existing)

    compliance_repository.record(
        action="delete", entity="otj_entry", entity_id=entry_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Deleted {existing.hours}h on {existing.activity_date}",
    )
    repo.delete_entry(entry_id)
    logger.info("OTJ entry %s deleted by %s", entry_id, actor.username)


def pending_approvals(actor: Actor) -> list[OTJEntry]:
    """The approval queue, holding only what this approver is responsible for."""
    require(actor, "otj.approve")
    filters: dict[str, Any] = {"status": "Submitted"}
    filters.update(apprentice_filters(actor))
    return repo.list_entries(**filters)


def _approve_entry(actor: Actor, entry: OTJEntry, note: str | None) -> None:
    """The approval itself, shared by the single and bulk paths."""
    stamp = _now()
    repo.set_entry_status(
        entry.entry_id, "Approved",
        approved_by=actor.username, approved_at=stamp, decision_note=note,
    )
    compliance_repository.record(
        action="approve", entity="otj_entry", entity_id=entry.entry_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Approved {entry.hours}h on {entry.activity_date}",
        changes=audit.diff(
            entry,
            {"status": "Approved", "approved_by": actor.username, "decision_note": note},
            fields=("status", "approved_by", "decision_note"),
        ),
    )


# ═════════════════════════════════════════════════════════════════════
# Loading and validation
# ═════════════════════════════════════════════════════════════════════

def _check_objective(objective_id: int | None, apprentice_id: int) -> None:
    """An activity can only deliver an objective on its own apprentice's plan."""
    if objective_id is None:
        return
    objective = learning_plan_repository.get_objective(objective_id)
    if objective is None or objective.apprentice_id != apprentice_id:
        raise ValidationError("That objective belongs to a different apprentice's plan")


def _require_apprentice(actor: Actor, apprentice_id: int) -> Apprentice:
    """Load an apprentice, refusing if *actor* may not see them."""
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        raise ValidationError(f"No apprentice with id {apprentice_id}")
    require_apprentice_access(actor, apprentice)
    return apprentice


def _require_entry(actor: Actor, entry_id: int) -> OTJEntry:
    entry = repo.get_entry(entry_id)
    if entry is None:
        raise ValidationError(f"No off-the-job entry with id {entry_id}")
    _require_apprentice(actor, entry.apprentice_id)
    return entry


def _require_plan_item(actor: Actor, item_id: int) -> TrainingPlanItem:
    item = repo.get_plan_item(item_id)
    if item is None:
        raise ValidationError(f"No training plan item with id {item_id}")
    _require_apprentice(actor, item.apprentice_id)
    return item


def _require_submitted(entry: OTJEntry) -> None:
    if entry.status != "Submitted":
        raise ValidationError(
            f"Only submitted hours can be approved or rejected; this entry is "
            f"{entry.status.lower()}"
        )


def _require_editable(entry: OTJEntry) -> None:
    if not entry.is_editable:
        raise ValidationError(
            f"These hours are {entry.status.lower()} and can no longer be changed. "
            "Approved hours are locked because the funding audit counts them — ask "
            "an approver to reject them first if they are wrong."
        )


def _visible_apprentice_ids(actor: Actor) -> set[int] | None:
    """Ids *actor* may see, or None when they may see everyone.

    ``apprentice_filters`` produces repository arguments, which is what
    most callers want; a register has to be filtered in Python instead,
    because attendance rows are keyed on the session.
    """
    filters = apprentice_filters(actor)
    if not filters:
        return None
    if "apprentice_id" in filters:
        return {int(filters["apprentice_id"])}
    return {
        summary.apprentice.apprentice_id
        for summary in apprentice_repository.list_summaries(**filters)
    }


def _validate_session(
    payload: dict[str, Any], *, existing: TrainingSession | None
) -> dict[str, Any]:
    """Normalise and check a session payload.

    Only keys actually present are validated and returned, so a partial
    edit from a form showing four fields does not blank the other nine.
    """
    data: dict[str, Any] = {}

    if existing is None or "title" in payload:
        data["title"] = _require_text(payload.get("title"), "Session title")
    if existing is None or "session_date" in payload:
        session_date = _validate_date(payload.get("session_date"), "Session date")
        if session_date is None:
            raise ValidationError("Session date is required")
        data["session_date"] = session_date

    if "start_time" in payload:
        data["start_time"] = _validate_time(payload.get("start_time"), "Start time")
    if "end_time" in payload:
        data["end_time"] = _validate_time(payload.get("end_time"), "End time")
    if "delivery_mode" in payload:
        data["delivery_mode"] = sessions.validate_delivery_mode(payload.get("delivery_mode"))
    if "status" in payload:
        data["status"] = sessions.validate_session_status(payload.get("status"))
    for key in ("location", "ksb_codes", "notes"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))

    if "programme_id" in payload:
        data["programme_id"] = _validate_fk(
            payload.get("programme_id"), programme_repository.get, "programme"
        )
    if "trainer_id" in payload:
        data["trainer_id"] = _validate_fk(
            payload.get("trainer_id"), staff_repository.get, "trainer"
        )
    if "capacity" in payload:
        data["capacity"] = _validate_capacity(payload.get("capacity"))
    if "otj_hours" in payload:
        # A session can be worth no off-the-job hours at all — an
        # induction, a social — which ``validate_hours`` rightly refuses
        # for a logged activity.
        value = payload.get("otj_hours")
        data["otj_hours"] = 0.0 if value in (None, "", 0, "0") else otj.validate_hours(value)

    start = data.get("start_time", existing.start_time if existing else None)
    end = data.get("end_time", existing.end_time if existing else None)
    if start and end and end <= start:
        raise ValidationError("End time must be after the start time")

    return data


def _validate_plan_item(
    payload: dict[str, Any], *, existing: TrainingPlanItem | None
) -> dict[str, Any]:
    """Normalise and check a training plan item payload."""
    data: dict[str, Any] = {}

    if existing is None or "title" in payload:
        data["title"] = _require_text(payload.get("title"), "Item title")
    for key in ("description", "ksb_codes"):
        if key in payload:
            data[key] = _optional_text(payload.get(key))
    if "status" in payload:
        data["status"] = plan_rules.validate_plan_item_status(
            payload.get("status"), current=existing.status if existing else None
        )
    if "objective_id" in payload:
        data["objective_id"] = _validate_fk(
            payload.get("objective_id"), learning_plan_repository.get_objective, "objective"
        )
    if "delivery_mode" in payload:
        data["delivery_mode"] = sessions.validate_delivery_mode(payload.get("delivery_mode"))
    if "planned_start" in payload:
        data["planned_start"] = _validate_date(payload.get("planned_start"), "Planned start")
    if "planned_end" in payload:
        data["planned_end"] = _validate_date(payload.get("planned_end"), "Planned end")
    if "planned_hours" in payload:
        data["planned_hours"] = _validate_planned_hours(payload.get("planned_hours"))

    start = data.get("planned_start", existing.planned_start if existing else None)
    end = data.get("planned_end", existing.planned_end if existing else None)
    if start and end and end < start:
        raise ValidationError("Planned end date cannot be before the planned start date")

    return data


def _validate_entry(
    payload: dict[str, Any], *, existing: OTJEntry | None
) -> dict[str, Any]:
    """Normalise and check an off-the-job entry payload.

    ``session_id``, ``status`` and the approval stamps are deliberately
    not read from the payload. They mark an entry as generated by a
    register and signed off by a named approver, so a form able to set
    them could conjure approved hours out of nothing.
    """
    data: dict[str, Any] = {}

    if "apprentice_id" in payload:
        data["apprentice_id"] = _validate_fk(
            payload.get("apprentice_id"), apprentice_repository.get, "apprentice"
        )
    if existing is None or "activity_date" in payload:
        data["activity_date"] = _validate_activity_date(payload.get("activity_date"))
    if existing is None or "hours" in payload:
        data["hours"] = otj.validate_hours(payload.get("hours"))
    if existing is None or "activity_type" in payload:
        data["activity_type"] = otj.validate_activity_type(payload.get("activity_type"))
    if existing is None or "description" in payload:
        data["description"] = _require_text(
            payload.get("description"), "Description", max_length=2000
        )
    if "ksb_codes" in payload:
        data["ksb_codes"] = _optional_text(payload.get("ksb_codes"))

    return data


def _validate_activity_date(value: Any) -> str:
    """The day the training happened.

    Refused if it is in the future: hours logged before they are trained
    would let an apprentice reach the gateway target on activity that has
    not taken place.
    """
    activity_date = _validate_date(value, "Activity date")
    if activity_date is None:
        raise ValidationError("Activity date is required")
    if activity_date > date.today().isoformat():
        raise ValidationError("Hours cannot be logged for a date in the future")
    return activity_date


def _validate_planned_hours(value: Any) -> float:
    """Hours a planned block of learning is expected to take.

    Not ``off_the_job_hours.validate_hours``: that caps at 24 because it
    guards one logged activity, whereas a plan item covers a block of
    delivery that can run to several days.
    """
    if value in (None, ""):
        return 0.0
    try:
        hours = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Planned hours must be a number") from exc
    if hours < 0:
        raise ValidationError("Planned hours cannot be negative")
    return round(hours, 2)


def _validate_capacity(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        capacity = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Capacity must be a whole number") from exc
    if capacity <= 0:
        raise ValidationError("Capacity must be greater than zero")
    return capacity


def _require_text(value: Any, label: str, *, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label} is required")
    if len(text) > max_length:
        raise ValidationError(f"{label} must be {max_length} characters or fewer")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _validate_date(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc


def _validate_time(value: Any, label: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise ValidationError(f"{label} must be a time in HH:MM format") from exc


def _validate_fk(value: Any, lookup: Any, label: str) -> int | None:
    """Check a foreign key points at something that exists."""
    if value in (None, "", 0, "0"):
        return None
    try:
        key = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label.capitalize()} is not valid") from exc
    if lookup(key) is None:
        raise ValidationError(f"No {label} with id {key}")
    return key


def _now() -> str:
    """A timestamp in the format SQLite's ``datetime('now')`` writes.

    The stamps this module sets sit in the same rows as repository-set
    columns, so they have to sort against them.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
