"""The common transition workflow, shared by every phase boundary.

Nursery→primary and sixth_form→university are the same seven steps with
different paperwork, so they run through one state machine here rather
than each system inventing its own transfer flow::

    1. expected           source identifies who is likely to move
    2. applied            destination has an application on file
    3. offered            destination creates a pending admission record
    4. accepted           learner/parent/admissions confirm the destination
    5. handover_approved  source approves the information to release
    6. admitted           destination creates its local learner id
    7. completed          journey updated; source enrolment closed

Each step publishes a durable bus event, so a system that is not running
when a learner progresses picks the work up on its next poll.

Direction of travel
-------------------
Steps only move forward, and a transition may jump ahead — a learner
joining from an external institution mid-year goes straight to
``admitted`` with no application or offer, and a backdated administrative
record can be entered as ``completed`` in one call. Skipped steps are
logged, not rejected. :func:`cancel` and :func:`reject` are reachable from
anywhere before ``completed``. The status update is conditional on the
status that was read, so two concurrent moves cannot both succeed.

The destination is never inferred from a fixed chain.
``progression.next_phase`` supplies a *recommendation* when the caller
does not name one, but any destination is permitted: another school in
the same phase, an apprenticeship, employment, home education, or an
external provider.

Audit trail, decisions and practicalities
-----------------------------------------
Every step, and everything else that happens to a transition, writes a
``learner_transition_event`` row: who acted, when, the effective date,
and for a handover the released and withheld field *keys*. Read it with
:func:`list_transition_events`.

The admissions decision is recorded as ``decision`` / ``decided_by`` /
``decided_at``. It is set to ``accepted`` on the first step that implies
acceptance (accepted, handover_approved or admitted), and to ``rejected``
by :func:`reject`. The receiving institution confirms that the handover
arrived with :func:`acknowledge`. The practical checklist (visit held,
documents received...) is seeded from the boundary's HandoverSpec. Read it
with :func:`get_checklist` and update it with :func:`tick_checklist_item`.

Reading a handover
------------------
Use :func:`get_handover_for`. It filters the payload by the viewer's
system, role and purpose through ``governance.security.sensitive_access``,
and audits the read. :func:`get_handover` returns everything and is kept
for existing internal callers only.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from education_system.platform.cross_system import enrolments, identity_service
from education_system.platform.cross_system import handover as _handover
from education_system.platform.cross_system.enrolment_schema import (
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    TRANSITION_CANCELLED,
    TRANSITION_STATUSES,
    ensure_enrolment_schema,
)
from education_system.platform.cross_system.handover import (
    HandoverAccessError,
    HandoverResult,
    Sensitivity,
)
from education_system.platform.governance.gdpr.consent_service import (
    verify_transition_handover_consent,
)
from education_system.platform.governance.security import sensitive_access
from education_system.platform.identity.auth.db import connect
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

_SOURCE_MODULE = "platform.cross_system.transitions"

# Workflow step -> the event published on entering it.
STEP_EVENTS: dict[str, str] = {
    "expected":          cross_system_bus.EVENT_PROGRESSION_EXPECTED,
    "applied":           cross_system_bus.EVENT_APPLICATION_SUBMITTED,
    "offered":           cross_system_bus.EVENT_PLACE_OFFERED,
    "accepted":          cross_system_bus.EVENT_PLACE_ACCEPTED,
    "handover_approved": cross_system_bus.EVENT_HANDOVER_APPROVED,
    "admitted":          cross_system_bus.EVENT_ENROLMENT_CREATED,
    "completed":         cross_system_bus.EVENT_PROGRESSION_COMPLETED,
    TRANSITION_CANCELLED: cross_system_bus.EVENT_PROGRESSION_CANCELLED,
}

_STEP_INDEX: dict[str, int] = {s: i for i, s in enumerate(TRANSITION_STATUSES)}

# Reaching any of these without an explicit decision means the destination
# said yes: a learner cannot be admitted to a place nobody accepted.
_AUTO_DECISION_STEPS: frozenset[str] = frozenset(
    {"accepted", "handover_approved", "admitted"})

#: How far ahead of the effective date the reminder falls due.
REMINDER_DAYS_BEFORE = 14

# A reminder is useful while the move is still being prepared. Once the
# handover is approved, the destination is actively working on it.
_REMINDER_STATUSES: frozenset[str] = frozenset({"expected", "accepted"})

_TERMINAL: frozenset[str] = frozenset({"completed", TRANSITION_CANCELLED})


class TransitionError(ValueError):
    """An illegal move in the transition workflow."""


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _now_text() -> str:
    """UTC now, in SQLite's ``datetime('now')`` format, so rows stamped here
    sort and compare against rows stamped by SQL defaults."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _actor_text(actor: object) -> str | None:
    if actor is None or actor == "":
        return None
    return str(actor)


def _envelope_actor(actor: object, fallback: object = None) -> int | None:
    """The bus envelope's actor column is an integer user id. A step actor
    may be a name ("parent", "Sixth Form admissions"), which stays in the
    event row and the payload but cannot go in the column."""
    for cand in (actor, fallback):
        if isinstance(cand, bool):
            continue
        if isinstance(cand, int):
            return cand
        if isinstance(cand, str) and cand.strip().isdigit():
            return int(cand.strip())
    return None


def _check_date(value: object, what: str = "effective_date") -> str | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise TransitionError(
            f"{what} must be an ISO date (YYYY-MM-DD), got {value!r}") from exc


def _soft_date(value: object) -> str | None:
    """``start_date`` has always been passed through unchecked. Adopt it as
    the effective date when it parses, and ignore it quietly when not."""
    try:
        return _check_date(value)
    except TransitionError:
        return None


def _platform_system(system: str | None) -> bool:
    return bool(system) and system in identity_service.SYSTEM_SLOTS


def _sender_target(transition: dict) -> str:
    """Who needs to hear about a rejection or acknowledgement: the sender,
    when the sender is a system of this platform."""
    src = transition.get("source_system")
    if _platform_system(src):
        return str(src)
    return str(transition["destination_system"])


def _seed_checklist(source_system: str | None,
                    destination_system: str | None) -> list[dict]:
    return [{"key": item.key, "label": item.label, "owner": item.owner,
             "done": False, "done_by": None, "done_at": None}
            for item in _handover.checklist_for(source_system,
                                                destination_system)]


def _decode_checklist(row: dict) -> list[dict]:
    raw = row.get("checklist_json")
    if raw:
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Transition %s has unreadable checklist_json",
                           row.get("transition_id"))
            decoded = None
        if isinstance(decoded, list):
            return decoded
    if "destination_system" not in row:
        return []
    # Rows opened before checklists existed read as a fresh checklist. The
    # first tick persists it.
    return _seed_checklist(row.get("source_system"),
                           row.get("destination_system"))


def hydrate(row: dict) -> dict:
    """Decode the JSON columns a caller reads as structured data.

    ``choices`` is stored as JSON text but every reader — the admissions
    applicant list, the college dashboards — wants the list. Decoding here
    means no caller has to know which of the two it is holding. A row that
    never carried choices reads as ``[]`` rather than absent, so
    ``row["choices"][0]`` is never the thing that raises. ``checklist`` is
    decoded the same way.
    """
    raw = row.get("choices_json")
    if raw:
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Transition %s has unreadable choices_json",
                           row.get("transition_id"))
            decoded = []
        row["choices"] = decoded if isinstance(decoded, list) else []
    else:
        row.setdefault("choices", [])
    row["checklist"] = _decode_checklist(row)
    return row


def _row(r: sqlite3.Row | None) -> dict | None:
    return hydrate(dict(r)) if r is not None else None


def _insert_event(conn: sqlite3.Connection, transition_id: str, step: str, *,
                  from_status: str | None = None, actor: object = None,
                  effective_date: str | None = None, note: str | None = None,
                  released: Iterable[str] | None = None,
                  withheld: Iterable[str] | None = None) -> None:
    """Append one audit-trail row on the caller's connection, so it commits
    or rolls back with the change it describes."""
    conn.execute(
        """INSERT INTO learner_transition_event
             (transition_id, step, from_status, actor, at, effective_date,
              note, released_fields, withheld_fields)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (transition_id, step, from_status, _actor_text(actor), _now_text(),
         effective_date, note,
         json.dumps(sorted(released)) if released is not None else None,
         json.dumps(sorted(withheld)) if withheld is not None else None))


def _publish(event: str, transition: dict, *, actor: object = None,
             target: str | None = None, **payload: Any) -> None:
    """Publish a workflow event, plus its legacy twin where one exists.

    Best-effort: a bus failure must not roll back a transition that has
    already been recorded in the database.
    """
    # NB: no "source_system" key — the envelope already carries that as a
    # column, and duplicating it here collides with the explicit keyword
    # below. Payload callers read it from the envelope.
    body = {
        "transition_id": transition["transition_id"],
        "source_enrolment_id": transition.get("source_enrolment_id"),
        "destination_system": transition["destination_system"],
        "destination_enrolment_id": transition.get(
            "destination_enrolment_id"),
        "status": transition["status"],
        "effective_date": transition.get("effective_date"),
        **payload,
    }
    if actor is not None:
        body.setdefault("actor", _actor_text(actor))
    names = [event]
    twin = cross_system_bus.LEGACY_EVENT_TWINS.get(event)
    if twin:
        names.append(twin)
    for name in names:
        try:
            cross_system_bus.publish_cross_system(
                name,
                source_system=transition.get("source_system") or "platform",
                source_module=_SOURCE_MODULE,
                journey_id=transition["journey_id"],
                target_system=target or transition["destination_system"],
                actor_user_id=_envelope_actor(
                    actor, transition.get("actor_user_id")),
                db_path=transition.get("_db_path"),
                **body)
        except Exception:
            logger.exception(
                "Failed to publish %s for transition %s (state already "
                "saved)", name, transition["transition_id"])


def _audit_db_path(db_path: str | None) -> str | None:
    """The audit DB beside the auth DB actually in use.

    In production that is PLATFORM_AUDIT_DB_FILE, because both live in
    PLATFORM_DB_FILES_DIR. Asking the connection rather than trusting
    ``db_path`` means a test that points the auth DB somewhere temporary
    (by argument or by patching) cannot write into the live audit DB.
    """
    conn = connect(db_path)
    try:
        rows = conn.execute("PRAGMA database_list").fetchall()
    finally:
        conn.close()
    main = next((r["file"] for r in rows if r["name"] == "main"), "")
    if not main:
        return None   # in-memory: nowhere durable to put an audit row
    return str(Path(main).with_name("audit.db"))


def audit_cross_system(action: str, *, target_type: str,
                       target_id: str | None, actor: object = None,
                       details: dict[str, Any] | None = None,
                       severity: str = "info",
                       db_path: str | None = None) -> None:
    """Write one central audit entry for data crossing a boundary.

    ``action`` names an ``AuditAction`` member (``"CROSS_BOUNDARY_HANDOVER"``,
    ``"CROSS_SYSTEM_TRANSFER"``, ``"CROSS_SYSTEM_ACCESS"``,
    ``"SAFEGUARDING_VIEW"``). It is imported lazily because the audit
    package pulls in the fail-closed alerting machinery.

    Best-effort. The primary transfer trail is ``learner_transition_event``,
    written in the same transaction as the change. This is the platform
    audit copy, and losing it must not undo a move that has already happened.
    """
    try:
        from education_system.platform.governance.audit.logger import (
            AuditAction,
            AuditLogger,
        )
        path = _audit_db_path(db_path)
        if path is None:
            logger.debug("No durable audit DB beside %s; %s not audited",
                         db_path, action)
            return
        uid = _envelope_actor(actor)
        AuditLogger("platform", db_path=path).log(
            AuditAction[action], user_id=uid,
            username=None if uid is not None else _actor_text(actor),
            target_type=target_type, target_id=target_id,
            details=details or {}, severity=severity)
    except Exception:
        logger.exception("Could not write %s audit entry for %s %s", action,
                         target_type, target_id)


def _audit_transition(action: str, transition: dict, *, actor: object,
                      details: dict[str, Any], severity: str = "info",
                      db_path: str | None) -> None:
    audit_cross_system(
        action, target_type="learner_transition",
        target_id=transition.get("transition_id"), actor=actor,
        details={"journey_id": transition.get("journey_id"),
                 "source_system": transition.get("source_system"),
                 "destination_system": transition.get("destination_system"),
                 **details},
        severity=severity, db_path=db_path)


def _require_live(current: dict | None, transition_id: str,
                  to_status: str) -> dict:
    """Refuse a move out of a terminal state *before* any side effect.

    complete() and cancel() touch enrolments before the status update.
    Checking only in _advance let cancel() on a completed transition close
    the learner's live destination enrolment and then raise.
    """
    if current is None:
        raise TransitionError(f"No transition {transition_id}")
    if current["status"] in _TERMINAL:
        raise TransitionError(
            f"Transition {transition_id} is already {current['status']} and "
            f"cannot move to {to_status}")
    return current


def _advance(transition_id: str, to_status: str, *,
             db_path: str | None = None, actor: object = None,
             effective_date: str | None = None, note: str | None = None,
             released: Iterable[str] | None = None,
             withheld: Iterable[str] | None = None,
             event_step: str | None = None,
             stamps: tuple[str, ...] = (),
             **fields: Any) -> dict:
    """Move a transition forward to ``to_status`` and patch ``fields``.

    ``stamps`` names columns set to "now". The status change and its
    ``learner_transition_event`` row commit together.
    """
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, to_status)
    now = current["status"]

    if to_status != TRANSITION_CANCELLED:
        if to_status not in _STEP_INDEX:
            raise TransitionError(f"Unknown workflow step {to_status!r}")
        here, there = _STEP_INDEX[now], _STEP_INDEX[to_status]
        if there <= here:
            raise TransitionError(
                f"Transition {transition_id} is at {now!r}; the workflow "
                f"only moves forward, so it cannot go to {to_status!r}")
        if there > here + 1:
            logger.info(
                "Transition %s jumping %s -> %s, skipping %s", transition_id,
                now, to_status,
                ", ".join(TRANSITION_STATUSES[here + 1:there]))

    effective = _check_date(effective_date)
    if effective:
        fields["effective_date"] = effective
    if (to_status in _AUTO_DECISION_STEPS and not current.get("decision")
            and "decision" not in fields):
        fields["decision"] = DECISION_ACCEPTED
        fields["decided_by"] = _actor_text(actor)
        stamps = (*stamps, "decided_at")

    stamp = _now_text()
    sets = [f"{k} = ?" for k in fields]
    args: list[Any] = list(fields.values())
    for column in stamps:
        sets.append(f"{column} = ?")
        args.append(stamp)
    sets.append("status = ?")
    args.append(to_status)
    sets.append("updated_at = datetime('now')")
    if to_status == "completed":
        sets.append("completed_at = datetime('now')")
    args.extend([transition_id, now])

    conn = connect(db_path)
    try:
        # Conditional on the status just read: of two concurrent moves from
        # the same step, exactly one lands and the other is told so.
        cur = conn.execute(
            f"UPDATE learner_transition SET {', '.join(sets)} "  # nosec B608
            "WHERE transition_id = ? AND status = ?", args)
        if cur.rowcount != 1:
            raise TransitionError(
                f"Transition {transition_id} changed while moving "
                f"{now!r} -> {to_status!r}; re-read it and retry")
        _insert_event(conn, transition_id, event_step or to_status,
                      from_status=now, actor=actor,
                      effective_date=effective or current.get(
                          "effective_date"),
                      note=note, released=released, withheld=withheld)
        conn.commit()
    finally:
        conn.close()

    out = get_transition(transition_id, db_path=db_path)
    assert out is not None
    out["_db_path"] = db_path
    logger.info("Transition %s: %s -> %s (%s -> %s)", transition_id, now,
                to_status, out.get("source_system") or "?",
                out["destination_system"])
    return out


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_transition(transition_id: str, *,
                   db_path: str | None = None) -> dict | None:
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        return _row(conn.execute(
            "SELECT * FROM learner_transition WHERE transition_id = ?",
            (transition_id,)).fetchone())
    finally:
        conn.close()


def list_transitions(journey_id: str, *, db_path: str | None = None
                     ) -> list[dict]:
    """Every transition attempted for a journey, oldest first — including
    the ones that were cancelled, because "applied and was rejected" is
    part of the history."""
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        return [hydrate(dict(r)) for r in conn.execute(
            "SELECT * FROM learner_transition WHERE journey_id = ? "
            "ORDER BY initiated_at, rowid", (journey_id,)).fetchall()]
    finally:
        conn.close()


def pending_transitions(destination_system: str, *,
                        status: str | None = None,
                        db_path: str | None = None) -> list[dict]:
    """Transitions heading into one system that have not completed.

    This is the destination's work queue — the admissions view of "who is
    coming and how far along are they".
    """
    ensure_enrolment_schema(db_path)
    sql = ["SELECT * FROM learner_transition WHERE destination_system = ?"]
    args: list = [destination_system]
    if status:
        sql.append("AND status = ?")
        args.append(status)
    else:
        sql.append("AND status NOT IN ('completed', ?)")
        args.append(TRANSITION_CANCELLED)
    sql.append("ORDER BY initiated_at")
    conn = connect(db_path)
    try:
        return [hydrate(dict(r))
                for r in conn.execute(" ".join(sql), args).fetchall()]
    finally:
        conn.close()


def list_transition_events(transition_id: str, *,
                           db_path: str | None = None) -> list[dict]:
    """The transfer audit trail for one transition, oldest first.

    ``released_fields`` / ``withheld_fields`` are decoded to lists (empty
    where the step released nothing). They hold field keys only.
    """
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM learner_transition_event WHERE transition_id = ? "
            "ORDER BY event_id", (transition_id,)).fetchall()]
    finally:
        conn.close()
    for row in rows:
        for col in ("released_fields", "withheld_fields"):
            raw = row.get(col)
            try:
                row[col] = json.loads(raw) if raw else []
            except (TypeError, ValueError):
                row[col] = []
    return rows


# ---------------------------------------------------------------------------
# Step 1 — expected progression
# ---------------------------------------------------------------------------

def start_transition(
    *,
    journey_id: str,
    destination_system: str | None = None,
    source_system: str | None = None,
    source_enrolment_id: str | None = None,
    reason: str | None = None,
    actor_user_id: int | None = None,
    status: str = "expected",
    effective_date: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Open a transition. Step 1 of the workflow.

    ``destination_system`` defaults to the *recommended* next phase after
    ``source_system``, but any destination is accepted — including ones
    that are not phases at all (``apprenticeship``, ``employment``,
    ``home_education``, ``external``).

    ``effective_date`` is when the move is due to take effect. With one set
    on an ``expected`` transition, a reminder is queued ahead of it (see
    :func:`schedule_transition_reminder`).
    """
    if not journey_id:
        raise TransitionError("journey_id is required")
    ensure_enrolment_schema(db_path)

    if source_enrolment_id and not source_system:
        src = enrolments.get_enrolment(source_enrolment_id, db_path=db_path)
        if src is not None:
            source_system = src["system"]

    # Import locally: progression imports identity_service, and keeping this
    # out of the module header avoids a load-order dependency.
    from education_system.platform.cross_system.progression import (
        next_phase,
        normalise_system,
    )

    # Fold legacy spellings onto their real system key before anything is
    # stored. A journey recorded against ``apprenticeship`` (the old label,
    # from before the system joined the registry) has to reach the same
    # adapter and the same slot as one recorded against ``apprenticeships``,
    # or the two spellings become two parallel histories for one learner.
    source_system = normalise_system(source_system)
    destination_system = normalise_system(destination_system)

    if not destination_system:
        destination_system = next_phase(source_system or "")
        if not destination_system:
            raise TransitionError(
                f"No destination given and no phase follows "
                f"{source_system!r} — name the destination explicitly")
        logger.debug("Transition destination defaulted to recommended "
                     "next phase %s", destination_system)

    if status not in _STEP_INDEX:
        raise TransitionError(f"Unknown workflow step {status!r}")
    effective = _check_date(effective_date)

    transition_id = str(uuid.uuid4())
    checklist = _seed_checklist(source_system, destination_system)
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO learner_transition
                 (transition_id, journey_id, source_enrolment_id,
                  source_system, destination_system, status, reason,
                  actor_user_id, effective_date, checklist_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (transition_id, journey_id, source_enrolment_id, source_system,
             destination_system, status, reason, actor_user_id, effective,
             json.dumps(checklist)))
        _insert_event(conn, transition_id, status, actor=actor_user_id,
                      effective_date=effective, note=reason)
        conn.commit()
    finally:
        conn.close()

    out = get_transition(transition_id, db_path=db_path)
    assert out is not None
    out["_db_path"] = db_path
    logger.info("Opened transition %s for journey %s (%s -> %s) at %s",
                transition_id, journey_id, source_system or "?",
                destination_system, status)
    _publish(STEP_EVENTS[status], out, actor=actor_user_id, reason=reason)
    _maybe_schedule_reminder(out, db_path=db_path)
    return out


# ---------------------------------------------------------------------------
# Step 2 — application submitted
# ---------------------------------------------------------------------------

def record_application(transition_id: str, *,
                       application_reference: str | None = None,
                       actor_user_id: int | str | None = None,
                       effective_date: str | None = None,
                       db_path: str | None = None, **payload: Any) -> dict:
    """Step 2: an application exists at the destination.

    The reference and the ranked choice list are *stored* on the row, not
    only published. They used to go to the bus alone, which left the
    learner's own transition record — the thing the university's applicant
    list reads — with no course and no UCAS id, and no way to get either
    back once the event had been consumed.
    """
    stored: dict[str, Any] = {}
    if application_reference is not None:
        stored["application_reference"] = str(application_reference)
    choices = payload.get("choices")
    if choices:
        stored["choices_json"] = json.dumps(choices, default=str)
    out = _advance(transition_id, "applied", db_path=db_path,
                   actor=actor_user_id, effective_date=effective_date,
                   **stored)
    _publish(STEP_EVENTS["applied"], out, actor=actor_user_id,
             application_reference=application_reference, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 3 — place offered
# ---------------------------------------------------------------------------

def offer_place(
    transition_id: str,
    *,
    destination_enrolment_id: str | None = None,
    local_student_id: str | None = None,
    institution_id: str | None = None,
    year_group: str | None = None,
    conditions: str | None = None,
    actor_user_id: int | str | None = None,
    effective_date: str | None = None,
    db_path: str | None = None,
    **payload: Any,
) -> dict:
    """Step 3: the destination holds a pending admission record.

    Creates the destination's ``applicant`` enrolment when one was not
    supplied, and marks it ``offered``. This is where a learner first
    exists in the destination system — as an applicant, never as an
    enrolled learner.
    """
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, "offered")

    if destination_enrolment_id is None:
        destination_enrolment_id = current.get("destination_enrolment_id")
    if destination_enrolment_id is None:
        created = enrolments.create_enrolment(
            journey_id=current["journey_id"],
            system=current["destination_system"],
            local_student_id=local_student_id,
            institution_id=institution_id,
            year_group=year_group,
            status="offered",
            notes=f"created by transition {transition_id}",
            db_path=db_path)
        destination_enrolment_id = created["enrolment_id"]
    else:
        enrolments.set_status(destination_enrolment_id, "offered",
                              db_path=db_path)

    out = _advance(transition_id, "offered", db_path=db_path,
                   actor=actor_user_id, effective_date=effective_date,
                   note=conditions,
                   destination_enrolment_id=destination_enrolment_id)
    _publish(STEP_EVENTS["offered"], out, actor=actor_user_id,
             conditions=conditions, local_student_id=local_student_id,
             institution_id=institution_id, year_group=year_group, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 4 — offer accepted
# ---------------------------------------------------------------------------

def accept_place(transition_id: str, *, accepted_by: str | None = None,
                 actor_user_id: int | str | None = None,
                 effective_date: str | None = None,
                 db_path: str | None = None, **payload: Any) -> dict:
    """Step 4: the learner, parent or admissions team confirms.

    Records the admissions decision as ``accepted``. The actor is
    ``actor_user_id`` when given, otherwise ``accepted_by``.
    """
    actor = actor_user_id if actor_user_id is not None else accepted_by
    out = _advance(transition_id, "accepted", db_path=db_path, actor=actor,
                   effective_date=effective_date)
    if out.get("destination_enrolment_id"):
        enrolments.set_status(out["destination_enrolment_id"], "accepted",
                              db_path=db_path)
    _publish(STEP_EVENTS["accepted"], out, actor=actor,
             accepted_by=accepted_by, **payload)
    _maybe_schedule_reminder(out, db_path=db_path)
    return out


# ---------------------------------------------------------------------------
# Step 5 — handover prepared and approved
# ---------------------------------------------------------------------------

def approve_handover(
    transition_id: str,
    handover: HandoverResult | dict,
    *,
    consent_reference: str | None = None,
    actor_user_id: int | str | None = None,
    effective_date: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Step 5: the source approves the information to release.

    Accepts either a :class:`~.handover.HandoverResult` (the normal path,
    built by the source adapter) or a plain payload dict. The approved
    payload is stored on the transition, so what was released is
    auditable after the fact.

    Consent: when ``consent_reference`` points at a ``consent_records``
    row (``consent_records:<id>``, see
    ``consent_service.transition_handover_reference``), it is checked. If
    the row is not a granted ``transition_handover`` consent, every
    sensitive field is withheld before anything is stored. A reference in
    any other format is the sending system's own consent id. It is stored
    as before, and cannot be verified here.

    The payload itself is *not* put on the bus — the event carries the
    field names and a pointer to the transition, and the destination
    reads the payload back through :func:`get_handover_for`. Bus rows are
    long-lived and broadly readable; a learner's SEND and medical detail
    should not be sitting in them.
    """
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, "handover_approved")
    if isinstance(handover, HandoverResult):
        payload = dict(handover.payload)
        summary: dict[str, Any] = {
            "included": list(handover.included),
            "withheld_no_consent": list(handover.withheld_no_consent),
            "withheld_restricted": list(handover.withheld_restricted),
            "missing_required": list(handover.missing_required),
        }
    else:
        payload = dict(handover)
        summary = {"included": sorted(payload)}

    note: str | None = None
    consent_ok = verify_transition_handover_consent(consent_reference,
                                                    db_path=db_path)
    if consent_ok is False:
        payload, stripped = _handover.withhold_sensitive(
            current.get("source_system"), current["destination_system"],
            payload)
        summary["withheld_no_consent"] = sorted(
            set(summary.get("withheld_no_consent", [])) | set(stripped))
        summary["included"] = sorted(payload)
        note = (f"consent reference {consent_reference} is not a granted "
                f"transition_handover consent; sensitive fields withheld")
        logger.warning("Transition %s: %s", transition_id, note)
    elif consent_ok:
        note = f"consent {consent_reference} verified"

    released = sorted(payload)
    withheld = sorted(set(summary.get("withheld_no_consent", []))
                      | set(summary.get("withheld_restricted", [])))
    out = _advance(
        transition_id, "handover_approved", db_path=db_path,
        actor=actor_user_id, effective_date=effective_date, note=note,
        released=released, withheld=withheld,
        handover_json=json.dumps(payload, default=str),
        consent_reference=consent_reference,
        handover_approved_at=_now_text())
    _audit_transition(
        "CROSS_BOUNDARY_HANDOVER", out, actor=actor_user_id,
        details={"released_fields": released, "withheld_fields": withheld,
                 "consent_reference": consent_reference,
                 "consent_verified": consent_ok},
        db_path=db_path)
    _publish(STEP_EVENTS["handover_approved"], out, actor=actor_user_id,
             consent_reference=consent_reference, **summary)
    return out


def _decode_handover(row: dict | None) -> dict | None:
    if row is None or not row.get("handover_json"):
        return None
    try:
        loaded = json.loads(row["handover_json"])
    except (TypeError, ValueError):
        logger.exception("Transition %s has unreadable handover_json",
                         row.get("transition_id"))
        return None
    return loaded if isinstance(loaded, dict) else None


def get_handover(transition_id: str, *,
                 db_path: str | None = None) -> dict | None:
    """The whole approved handover payload, or ``None`` if not yet approved.

    Ungated and unaudited. Kept so existing internal callers keep working.
    Anything showing a handover to a person should use
    :func:`get_handover_for` instead.
    """
    return _decode_handover(get_transition(transition_id, db_path=db_path))


def get_handover_for(transition_id: str, *, viewer_role: str,
                     viewer_system: str, purpose: str | None = None,
                     viewer_id: int | str | None = None,
                     db_path: str | None = None) -> dict | None:
    """The approved handover as one viewer is entitled to see it.

    The rules:

    * ``viewer_system`` must be the source or the destination of the
      transition (or the viewer a ``superadmin``); otherwise
      :class:`~.handover.HandoverAccessError` is raised.
    * Routine fields are visible to either party.
    * Sensitive fields need a role the ``handover`` policy in
      ``sensitive_access.FIELD_POLICIES`` permits *and* a recognised
      ``purpose`` (e.g. ``transition_planning``). An approved break-glass
      grant also opens them.
    * The restricted ``safeguarding_reference`` is visible only to the
      designated-lead roles (``dsl`` / ``safeguarding`` / ``superadmin``)
      with a purpose. Anyone else sees that it was withheld, not what it
      says.

    Every decision goes to ``sensitive_access_audit``, and the read as a
    whole to the central audit log as ``CROSS_SYSTEM_ACCESS``.

    Returns ``None`` if there is no approved handover. Otherwise returns
    ``{"payload": {...visible...}, "released": [...], "withheld": [...],
    ...}``.
    """
    row = get_transition(transition_id, db_path=db_path)
    payload = _decode_handover(row)
    if row is None or payload is None:
        return None

    from education_system.platform.cross_system.progression import (
        normalise_system,
    )
    role = (viewer_role or "").strip().lower()
    system = normalise_system((viewer_system or "").strip().lower()) or ""
    src, dst = row.get("source_system"), row["destination_system"]
    actor_id = (str(viewer_id) if viewer_id is not None
                else f"{system or '?'}:{role or '?'}")
    base = {"viewer_system": system, "viewer_role": role,
            "purpose": purpose}

    if system not in {src, dst} and role != "superadmin":
        _audit_transition(
            "CROSS_SYSTEM_ACCESS", row, actor=viewer_id, severity="warning",
            details={**base, "decision": "denied",
                     "reason": "viewer system is not a party to the "
                               "transition"},
            db_path=db_path)
        raise HandoverAccessError(
            f"{system or 'an unnamed system'} is neither the source nor the "
            f"destination of transition {transition_id}")

    groups = _handover.classify_payload(src, dst, payload)
    visible = {k: payload[k] for k in groups[Sensitivity.ROUTINE]}
    withheld: list[str] = []
    guarded = groups[Sensitivity.SENSITIVE] + groups[Sensitivity.RESTRICTED]
    if guarded:
        permitted, refused = sensitive_access.partition_fields(
            "handover", role, guarded)
        # Asked separately so a role entitled to some fields gets those,
        # rather than a single all-or-nothing denial. The refused half is
        # still asked, because an approved break-glass grant may open it.
        for subset in (permitted, refused):
            if not subset:
                continue
            decision = sensitive_access.authorize_sensitive_fields(
                actor_id=actor_id, actor_role=role or "unknown",
                domain="handover", subject_id=row["journey_id"],
                fields=subset, purpose=purpose or "", db_path=db_path)
            if decision.allowed:
                visible.update({k: payload[k] for k in subset})
            else:
                withheld.extend(subset)

    result = {
        "transition_id": transition_id,
        "journey_id": row["journey_id"],
        "source_system": src,
        "destination_system": dst,
        "boundary": f"{src or '?'}->{dst}",
        "payload": visible,
        "released": sorted(visible),
        "withheld": sorted(withheld),
        "acknowledged_at": row.get("acknowledged_at"),
        **base,
    }
    _audit_transition(
        "CROSS_SYSTEM_ACCESS", row, actor=viewer_id,
        details={**base, "decision": "allowed",
                 "released_fields": result["released"],
                 "withheld_fields": result["withheld"]},
        db_path=db_path)
    return result


# ---------------------------------------------------------------------------
# Receiving institution acknowledges the handover
# ---------------------------------------------------------------------------

def acknowledge(transition_id: str, *, actor_user_id: int | str | None,
                note: str | None = None,
                db_path: str | None = None) -> dict:
    """The receiving institution confirms the handover arrived.

    Stamps ``acknowledged_by`` / ``acknowledged_at``, ticks the
    ``documents_received`` checklist item where the boundary has one, and
    tells the sender (``handover.acknowledged``). Does not change the
    workflow status. Idempotent: a second acknowledgement returns the row
    unchanged and publishes nothing.

    ``note`` goes to the audit trail only, never the bus. It is staff free
    text and may describe the handover it refers to.
    """
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute(
            "SELECT * FROM learner_transition WHERE transition_id = ?",
            (transition_id,)).fetchone()
        if r is None:
            raise TransitionError(f"No transition {transition_id}")
        row = hydrate(dict(r))
        if row["status"] == TRANSITION_CANCELLED:
            raise TransitionError(
                f"Transition {transition_id} is cancelled; there is no "
                f"handover to acknowledge")
        if not row.get("handover_json"):
            raise TransitionError(
                f"Transition {transition_id} has no approved handover yet")
        if row.get("acknowledged_at"):
            return row

        stamp = _now_text()
        checklist = row["checklist"]
        for item in checklist:
            if item.get("key") == "documents_received" and not item.get(
                    "done"):
                item.update(done=True, done_by=_actor_text(actor_user_id),
                            done_at=stamp)
        conn.execute(
            """UPDATE learner_transition
                  SET acknowledged_by = ?, acknowledged_at = ?,
                      checklist_json = ?, updated_at = datetime('now')
                WHERE transition_id = ?""",
            (_actor_text(actor_user_id), stamp, json.dumps(checklist),
             transition_id))
        _insert_event(conn, transition_id, "acknowledged",
                      from_status=row["status"], actor=actor_user_id,
                      effective_date=row.get("effective_date"), note=note)
        conn.commit()
    finally:
        conn.close()

    out = get_transition(transition_id, db_path=db_path)
    assert out is not None
    out["_db_path"] = db_path
    _publish(cross_system_bus.EVENT_HANDOVER_ACKNOWLEDGED, out,
             actor=actor_user_id, target=_sender_target(out),
             acknowledged_by=out.get("acknowledged_by"),
             acknowledged_at=out.get("acknowledged_at"))
    return out


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

def get_checklist(transition_id: str, *,
                  db_path: str | None = None) -> list[dict]:
    """The transition's practical checklist.

    Items are ``{key, label, owner, done, done_by, done_at}``. A transition
    opened before checklists existed reads as its boundary's default list.
    """
    row = get_transition(transition_id, db_path=db_path)
    if row is None:
        raise TransitionError(f"No transition {transition_id}")
    checklist: list[dict] = row["checklist"]
    return checklist


def tick_checklist_item(transition_id: str, key: str, *,
                        actor_user_id: int | str | None, done: bool = True,
                        note: str | None = None,
                        db_path: str | None = None) -> list[dict]:
    """Mark one checklist item done (or, with ``done=False``, not done).

    Returns the whole updated checklist. Ticking an item that is already in
    the requested state changes nothing and writes no event. Allowed after
    completion (documents do arrive late), but not on a cancelled
    transition.
    """
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        # IMMEDIATE takes the write lock before the read, so two people
        # ticking different items cannot each overwrite the other's tick.
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute(
            "SELECT * FROM learner_transition WHERE transition_id = ?",
            (transition_id,)).fetchone()
        if r is None:
            raise TransitionError(f"No transition {transition_id}")
        row = hydrate(dict(r))
        if row["status"] == TRANSITION_CANCELLED:
            raise TransitionError(
                f"Transition {transition_id} is cancelled")
        checklist: list[dict] = row["checklist"]
        item = next((i for i in checklist if i.get("key") == key), None)
        if item is None:
            raise TransitionError(
                f"No checklist item {key!r} on transition {transition_id}; "
                f"expected one of "
                f"{', '.join(str(i.get('key')) for i in checklist)}")
        if bool(item.get("done")) == bool(done):
            return checklist
        item["done"] = bool(done)
        item["done_by"] = _actor_text(actor_user_id) if done else None
        item["done_at"] = _now_text() if done else None
        conn.execute(
            "UPDATE learner_transition SET checklist_json = ?, "
            "updated_at = datetime('now') WHERE transition_id = ?",
            (json.dumps(checklist), transition_id))
        _insert_event(conn, transition_id, "checklist",
                      from_status=row["status"], actor=actor_user_id,
                      effective_date=row.get("effective_date"),
                      note=note or f"{key} {'done' if done else 'reopened'}")
        conn.commit()
    finally:
        conn.close()
    return checklist


def add_note(transition_id: str, note: str, *, step: str = "note",
             actor_user_id: int | str | None = None,
             db_path: str | None = None) -> None:
    """Append a note to the transition's step log, without changing it.

    For what happens at the far end after the move - e.g. the SEND service's
    EHCP decisions on a school's request (``send_referrals``). Allowed after
    completion; refused on a cancelled transition. *note* is shown to both
    ends, so it must hold no more than both may see.
    """
    text = (note or "").strip()
    if not text:
        raise TransitionError("A note needs some text")
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT status, effective_date FROM learner_transition "
                         "WHERE transition_id = ?", (transition_id,)).fetchone()
        if r is None:
            raise TransitionError(f"No transition {transition_id}")
        if r["status"] == TRANSITION_CANCELLED:
            raise TransitionError(f"Transition {transition_id} is cancelled")
        _insert_event(conn, transition_id, step, from_status=r["status"],
                      actor=actor_user_id, effective_date=r["effective_date"],
                      note=text[:1000])
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Effective date and reminders
# ---------------------------------------------------------------------------

def set_effective_date(transition_id: str, effective_date: str, *,
                       actor_user_id: int | str | None = None,
                       note: str | None = None,
                       db_path: str | None = None) -> dict:
    """Set or move the date the transition takes effect, without a step.

    Queues a reminder for the new date where the status calls for one. A
    reminder already queued for the old date is not withdrawn: the payload
    carries the date it was for, so the consumer can see that it is stale.
    """
    effective = _check_date(effective_date)
    if effective is None:
        raise TransitionError("effective_date is required")
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, "a new effective date")
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE learner_transition SET effective_date = ?, "
            "updated_at = datetime('now') WHERE transition_id = ?",
            (effective, transition_id))
        _insert_event(conn, transition_id, "effective_date",
                      from_status=current["status"], actor=actor_user_id,
                      effective_date=effective,
                      note=note or (f"moved from {current['effective_date']}"
                                    if current.get("effective_date")
                                    else None))
        conn.commit()
    finally:
        conn.close()
    out = get_transition(transition_id, db_path=db_path)
    assert out is not None
    out["_db_path"] = db_path
    _maybe_schedule_reminder(out, db_path=db_path)
    return out


def schedule_transition_reminder(transition_id: str, *,
                                 days_before: int = REMINDER_DAYS_BEFORE,
                                 db_path: str | None = None) -> str | None:
    """Queue ``transition.reminder`` to fall due before the effective date.

    Only for a transition that is ``expected`` or ``accepted`` and has an
    effective date still to come. The event is published now with a
    delayed ``available_at`` (08:00 UTC, ``days_before`` days ahead of the
    date), so the bus holds it until then. If that moment has already
    passed, it is available at once.

    Idempotent per (transition, effective date, days_before), so calling it
    on every save queues one reminder. Returns the bus event id, or ``None``
    when no reminder applies. The consumer should re-read the transition on
    delivery: it may have moved on, been cancelled, or been rescheduled
    (compare ``effective_date``).
    """
    row = get_transition(transition_id, db_path=db_path)
    if row is None:
        raise TransitionError(f"No transition {transition_id}")
    return _schedule_reminder(row, days_before=days_before, db_path=db_path)


def _schedule_reminder(row: dict, *, days_before: int,
                       db_path: str | None) -> str | None:
    if days_before < 0:
        raise TransitionError("days_before cannot be negative")
    if row["status"] not in _REMINDER_STATUSES:
        return None
    effective = _soft_date(row.get("effective_date"))
    if effective is None:
        return None
    due_on = date.fromisoformat(effective)
    now = datetime.now(UTC)
    if due_on < now.date():
        return None
    due = datetime.combine(due_on - timedelta(days=days_before), time(8, 0),
                           tzinfo=UTC)
    dst = row["destination_system"]
    target = dst if _platform_system(dst) else _sender_target(row)
    return cross_system_bus.publish_cross_system(
        cross_system_bus.EVENT_TRANSITION_REMINDER,
        source_system=row.get("source_system") or "platform",
        source_module=_SOURCE_MODULE,
        journey_id=row["journey_id"],
        target_system=target,
        available_at=due.isoformat() if due > now else None,
        idempotency_key=(f"transition.reminder:{row['transition_id']}:"
                         f"{effective}:{days_before}"),
        db_path=db_path,
        transition_id=row["transition_id"],
        destination_system=dst,
        status=row["status"],
        effective_date=effective,
        days_before=days_before)


def _maybe_schedule_reminder(row: dict, *, db_path: str | None) -> None:
    try:
        _schedule_reminder(row, days_before=REMINDER_DAYS_BEFORE,
                           db_path=db_path)
    except Exception:
        logger.exception("Could not queue a reminder for transition %s",
                         row.get("transition_id"))


# ---------------------------------------------------------------------------
# Step 6 — destination admits
# ---------------------------------------------------------------------------

def admit(
    transition_id: str,
    *,
    local_student_id: str,
    year_group: str | None = None,
    start_date: str | None = None,
    institution_id: str | None = None,
    actor_user_id: int | str | None = None,
    effective_date: str | None = None,
    db_path: str | None = None,
    **payload: Any,
) -> dict:
    """Step 6: the destination has created its local learner id.

    The destination enrolment is created if the workflow jumped straight
    here (a learner arriving from an external institution has no offer
    record), and stamped with the local id. ``start_date`` doubles as the
    effective date when none is given.
    """
    if not local_student_id:
        raise TransitionError("local_student_id is required to admit")
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, "admitted")

    dest_id = current.get("destination_enrolment_id")
    if dest_id:
        enrolments.update_enrolment(
            dest_id, db_path=db_path, local_student_id=local_student_id,
            **{k: v for k, v in (("year_group", year_group),
                                 ("institution_id", institution_id))
               if v is not None})
    else:
        created = enrolments.create_enrolment(
            journey_id=current["journey_id"],
            system=current["destination_system"],
            local_student_id=local_student_id,
            institution_id=institution_id, year_group=year_group,
            start_date=start_date, status="accepted",
            notes=f"created by transition {transition_id}", db_path=db_path)
        dest_id = created["enrolment_id"]

    out = _advance(transition_id, "admitted", db_path=db_path,
                   actor=actor_user_id,
                   effective_date=effective_date or _soft_date(start_date),
                   destination_enrolment_id=dest_id)
    _publish(STEP_EVENTS["admitted"], out, actor=actor_user_id,
             local_student_id=local_student_id, year_group=year_group,
             start_date=start_date, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 7 — complete, and close the source
# ---------------------------------------------------------------------------

def complete(
    transition_id: str,
    *,
    start_date: str | None = None,
    close_source: bool = True,
    source_exit_reason: str | None = None,
    source_status: str = "transferred",
    actor_user_id: int | str | None = None,
    effective_date: str | None = None,
    destination_detail: str | None = None,
    db_path: str | None = None,
    **payload: Any,
) -> dict:
    """Step 7: activate the destination enrolment and close the source.

    Also updates the canonical journey — linking the destination system's
    slot and appending a ``student_journey_transitions`` row — so the
    legacy slot readers stay correct while enrolments are authoritative.

    ``close_source=False`` leaves the source enrolment open, which is what
    a genuinely concurrent enrolment (school plus a college course) needs.

    A transition to a non-phase destination (employment, training, gap year,
    NEET) has no destination enrolment. Completing one records the
    learner's *leaving* destination in ``destinations``, with
    ``destination_detail`` as the employer or provider. See also
    :func:`complete_non_phase`. The move is written to the central audit
    log as ``CROSS_SYSTEM_TRANSFER``.
    """
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, "completed")

    dest_id = current.get("destination_enrolment_id")
    local_id = None
    if dest_id:
        dest = enrolments.activate(dest_id, start_date=start_date,
                                   db_path=db_path)
        local_id = dest.get("local_student_id")

    source_closed = False
    if close_source and current.get("source_enrolment_id"):
        enrolments.close_enrolment(
            current["source_enrolment_id"],
            reason=source_exit_reason or
            f"progressed to {current['destination_system']}",
            status=source_status, end_date=start_date, db_path=db_path)
        source_closed = True

    _sync_journey(current, local_id, db_path=db_path)

    out = _advance(transition_id, "completed", db_path=db_path,
                   actor=actor_user_id,
                   effective_date=effective_date or _soft_date(start_date))
    _audit_transition(
        "CROSS_SYSTEM_TRANSFER", out, actor=actor_user_id,
        details={"source_enrolment_id": out.get("source_enrolment_id"),
                 "destination_enrolment_id": dest_id,
                 "local_student_id": local_id,
                 "source_closed": source_closed,
                 "source_status": source_status if source_closed else None,
                 "effective_date": out.get("effective_date")},
        db_path=db_path)
    _record_leaving_destination(out, detail=destination_detail,
                                actor=actor_user_id, db_path=db_path)
    _publish(STEP_EVENTS["completed"], out, actor=actor_user_id,
             local_student_id=local_id, target_student_id=local_id,
             start_date=start_date, **payload)
    return out


def complete_non_phase(
    transition_id: str,
    *,
    detail: str | None = None,
    actor_user_id: int | str | None = None,
    effective_date: str | None = None,
    close_source: bool = True,
    source_status: str = "completed",
    source_exit_reason: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Complete a transition to employment, training, a gap year and so on.

    These used to open at ``expected`` and stay there, because nothing
    admits a learner into "employment". This walks straight to
    ``completed`` (the workflow allows the jump), closes the source
    enrolment as ``completed`` by default (pass ``withdrawn`` for a learner
    who left before finishing), and records the leaving destination.
    ``detail`` is the employer or provider.
    """
    from education_system.platform.cross_system.progression import (
        is_non_phase_destination,
    )
    current = get_transition(transition_id, db_path=db_path)
    if current is None:
        raise TransitionError(f"No transition {transition_id}")
    dest = current["destination_system"]
    if not is_non_phase_destination(dest):
        raise TransitionError(
            f"Transition {transition_id} goes to {dest!r}, a system of this "
            f"platform — admit the learner there and use complete()")
    return complete(
        transition_id, start_date=effective_date, close_source=close_source,
        source_exit_reason=source_exit_reason or
        f"left for {dest.replace('_', ' ')}",
        source_status=source_status, actor_user_id=actor_user_id,
        effective_date=effective_date, destination_detail=detail,
        db_path=db_path)


def _record_leaving_destination(transition: dict, *, detail: str | None,
                                actor: object, db_path: str | None) -> None:
    """Mirror a completed non-phase transition into ``learner_destination``.

    Best-effort: the move has happened, whatever the analytics table says.
    """
    from education_system.platform.cross_system.progression import (
        is_non_phase_destination,
    )
    dest = transition["destination_system"]
    if not is_non_phase_destination(dest):
        return
    from education_system.platform.cross_system import destinations
    kind = destinations.destination_kind_for_system(dest)
    if kind is None:
        # external / home_education are real outcomes, but not destination
        # measure categories. Guessing "unknown" would under-report them.
        return
    try:
        destinations.record_destination(
            transition["journey_id"], destination=kind, checkpoint="leaving",
            source_system=transition.get("source_system") or "platform",
            detail=detail, recorded_by=_actor_text(actor),
            recorded_on=transition.get("effective_date"),
            notes=transition.get("reason"),
            transition_id=transition["transition_id"], db_path=db_path)
    except Exception:
        logger.exception("Transition %s completed but its leaving destination "
                         "was not recorded", transition["transition_id"])


def _sync_journey(transition: dict, local_student_id: str | None, *,
                  db_path: str | None) -> None:
    """Keep ``student_journey`` in step with a completed transition.

    Best-effort. The destination may be somewhere with no slot at all
    (an apprenticeship, an external provider); the transition audit row
    is still written so the journey shows where the learner went.
    """
    journey_id = transition["journey_id"]
    dest = transition["destination_system"]
    try:
        if dest in identity_service.SYSTEM_SLOTS and local_student_id:
            identity_service.link_system(
                journey_id, dest, student_id=local_student_id,
                set_current=True, db_path=db_path)
        identity_service.record_transition(
            journey_id, from_system=transition.get("source_system"),
            to_system=dest, actor_user_id=transition.get("actor_user_id"),
            reason=transition.get("reason") or
            f"{transition.get('source_system') or '?'} → {dest} transition",
            db_path=db_path)
    except Exception:
        logger.exception(
            "Journey sync failed for transition %s (enrolments are still "
            "correct)", transition["transition_id"])


# ---------------------------------------------------------------------------
# Cancellation and rejection
# ---------------------------------------------------------------------------

def _terminate(transition_id: str, *, reason: str, actor: object,
               cancel_destination_enrolment: bool, event: str,
               event_step: str, rejected: bool, db_path: str | None,
               payload: dict[str, Any]) -> dict:
    current = _require_live(get_transition(transition_id, db_path=db_path),
                            transition_id, TRANSITION_CANCELLED)

    if cancel_destination_enrolment and current.get(
            "destination_enrolment_id"):
        try:
            enrolments.close_enrolment(
                current["destination_enrolment_id"], reason=reason,
                status="cancelled", db_path=db_path)
        except Exception:
            logger.exception(
                "Could not cancel destination enrolment for transition %s",
                transition_id)

    fields: dict[str, Any] = {"cancelled_reason": reason}
    stamps: tuple[str, ...] = ()
    if rejected:
        fields.update(decision=DECISION_REJECTED,
                      decided_by=_actor_text(actor), decision_reason=reason)
        stamps = ("decided_at",)
    out = _advance(transition_id, TRANSITION_CANCELLED, db_path=db_path,
                   actor=actor, note=reason, event_step=event_step,
                   stamps=stamps, **fields)
    _publish(event, out, actor=actor,
             target=_sender_target(out) if rejected else None,
             reason=reason, **payload)
    return out


def cancel(transition_id: str, *, reason: str,
           cancel_destination_enrolment: bool = True,
           actor_user_id: int | str | None = None,
           db_path: str | None = None, **payload: Any) -> dict:
    """Abandon a transition at any point before it completes.

    The row is kept — a place applied for and not taken is part of the
    journey. The destination's applicant/offer enrolment is closed as
    ``cancelled`` unless the caller wants to keep it open (a deferred
    entry that will be picked up next cycle).

    For an admissions *decision* not to take the learner, use
    :func:`reject`, which records the decision and tells the sender.
    """
    actor = (actor_user_id if actor_user_id is not None
             else payload.get("cancelled_by"))
    return _terminate(
        transition_id, reason=reason, actor=actor,
        cancel_destination_enrolment=cancel_destination_enrolment,
        event=STEP_EVENTS[TRANSITION_CANCELLED],
        event_step=TRANSITION_CANCELLED, rejected=False, db_path=db_path,
        payload=payload)


def reject(transition_id: str, *, reason: str,
           actor_user_id: int | str | None,
           cancel_destination_enrolment: bool = True,
           db_path: str | None = None, **payload: Any) -> dict:
    """The destination decides not to take the learner.

    Ends the transition as ``cancelled`` (so every "is it still live?"
    check treats it as over), with ``decision = 'rejected'``,
    ``decided_by``, ``decided_at`` and ``decision_reason`` recorded. It
    publishes ``progression.rejected``, addressed to the sending system,
    and deliberately *not* ``progression.cancelled`` as well, so a consumer
    subscribed to both does not notify twice. Reachable from any step
    before completion, including after acceptance (conditions not met on
    results day).
    """
    if not reason or not reason.strip():
        raise TransitionError("A rejection needs a reason")
    return _terminate(
        transition_id, reason=reason.strip(), actor=actor_user_id,
        cancel_destination_enrolment=cancel_destination_enrolment,
        event=cross_system_bus.EVENT_PROGRESSION_REJECTED,
        event_step="rejected", rejected=True, db_path=db_path,
        payload=payload)


__all__ = [
    "TransitionError",
    "add_note",
    "STEP_EVENTS",
    "REMINDER_DAYS_BEFORE",
    "hydrate",
    "get_transition",
    "list_transitions",
    "pending_transitions",
    "list_transition_events",
    "start_transition",
    "record_application",
    "offer_place",
    "accept_place",
    "approve_handover",
    "get_handover",
    "get_handover_for",
    "acknowledge",
    "get_checklist",
    "tick_checklist_item",
    "set_effective_date",
    "schedule_transition_reminder",
    "admit",
    "complete",
    "complete_non_phase",
    "cancel",
    "reject",
    "audit_cross_system",
]
