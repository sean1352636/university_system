"""Read and act on learner transitions across every system — the transfer monitor.

The per-boundary boards (university applications, post-16 destinations,
apprenticeship applications) each show one institution's side of one kind
of move. Operations needs the other view: every transition on the platform,
where it is stuck and who has to act. This module is that view, shared by
``GET /api/v1/transfers``, the superadmin Transfer Monitor and the
cross-system task list.

It reads ``learner_transition`` directly for the listing (the workflow
module has per-journey and per-destination reads, not a platform-wide
search) and calls :mod:`platform.cross_system.transitions` for every
action, so the state machine stays in one place.

Several workflow functions are being added alongside this module
(``reject``, ``acknowledge``, ``get_checklist``, ``tick_checklist_item``,
``list_transition_events``). They are looked up when called; a missing one
raises :class:`ActionUnavailable` with a message a screen can show, rather
than an ImportError at startup.

``handover_json`` never leaves this module. Rows are returned through
:func:`public`, which replaces it with ``has_handover``.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Collection
from datetime import date, datetime, timedelta
from typing import Any

from education_system.paths import SYSTEM_LABELS
from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.role_manager import (
    PERM_TRANSFER_ACKNOWLEDGE,
    PERM_TRANSFER_APPROVE,
)

logger = logging.getLogger(__name__)

#: Terminal statuses. ``rejected`` is included in case the workflow gains a
#: distinct rejected state rather than recording rejection as a cancellation.
CLOSED_STATUSES: tuple[str, ...] = ("completed", "cancelled", "rejected")

#: Status -> (acting party, next action, permission needed at that party).
AWAITING: dict[str, tuple[str, str, str]] = {
    "expected": ("source", "Record the application", PERM_TRANSFER_APPROVE),
    "applied": ("destination", "Offer a place or reject", PERM_TRANSFER_APPROVE),
    "offered": ("source", "Record the learner's acceptance", PERM_TRANSFER_APPROVE),
    "accepted": ("source", "Approve the handover", PERM_TRANSFER_APPROVE),
    "handover_approved": ("destination", "Acknowledge the handover and admit",
                          PERM_TRANSFER_ACKNOWLEDGE),
    "admitted": ("destination", "Complete the transfer", PERM_TRANSFER_ACKNOWLEDGE),
}

#: Columns a transition may carry a planned start date in, in preference
#: order. None exist in the base schema; the workflow owner may add one.
EFFECTIVE_DATE_KEYS: tuple[str, ...] = (
    "effective_date", "expected_start_date", "start_date")

ACTIONS: tuple[str, ...] = ("approve", "reject", "acknowledge", "complete")


class ActionUnavailable(RuntimeError):
    """The workflow function behind an action is not installed (yet)."""


def label(system: str | None) -> str:
    if not system:
        return "—"
    return SYSTEM_LABELS.get(system, system.replace("_", " ").title())


def call_flexible(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Call *func* with only the keyword arguments it accepts.

    For functions owned by other modules whose exact keywords are still
    settling: passing ``actor_user_id`` to a function that has no such
    parameter should drop it, not fail the whole action.
    """
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return func(*args, **kwargs)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return func(*args, **kwargs)
    return func(*args, **{k: v for k, v in kwargs.items() if k in params})


def _transitions_module():
    from education_system.platform.cross_system import transitions
    return transitions


def workflow_function(name: str) -> Callable | None:
    """``transitions.<name>`` if the workflow provides it, else ``None``."""
    try:
        return getattr(_transitions_module(), name, None)
    except Exception:
        logger.debug("transitions module unavailable", exc_info=True)
        return None


def _ensure(db_path: str | None) -> None:
    from education_system.platform.cross_system.enrolment_schema import (
        ensure_enrolment_schema,
    )
    ensure_enrolment_schema(db_path)


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def effective_date(row: dict) -> str | None:
    for key in EFFECTIVE_DATE_KEYS:
        if row.get(key):
            return str(row[key])[:10]
    return None


def acting_system(row: dict) -> str | None:
    """Which system has to move this transition on next, if any."""
    awaiting = AWAITING.get(row.get("status") or "")
    if not awaiting:
        return None
    return row.get("source_system") if awaiting[0] == "source" \
        else row.get("destination_system")


def public(row: dict | None) -> dict | None:
    """A transition safe to hand to a screen or an API client."""
    if row is None:
        return None
    out = {k: v for k, v in row.items()
           if k not in ("handover_json", "_db_path", "choices_json")}
    out["has_handover"] = bool(row.get("handover_json"))
    awaiting = AWAITING.get(row.get("status") or "")
    out["awaiting_party"] = awaiting[0] if awaiting else None
    out["awaiting_action"] = awaiting[1] if awaiting else None
    out["acting_system"] = acting_system(row)
    out["effective_date"] = effective_date(row)
    out["source_label"] = label(row.get("source_system"))
    out["destination_label"] = label(row.get("destination_system"))
    return out


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def search_transitions(
    *,
    status: str | None = None,
    source_system: str | None = None,
    destination_system: str | None = None,
    journey_id: str | None = None,
    systems: Collection[str] | None = None,
    open_only: bool = False,
    since: str | None = None,
    limit: int = 200,
    db_path: str | None = None,
) -> list[dict]:
    """Platform-wide transition search, newest first, as :func:`public` rows.

    ``systems`` scopes the result to transitions with either end in one of
    those systems — how a non-superadmin's view is restricted.
    """
    if limit < 1 or limit > 2000:
        raise ValueError("limit must be between 1 and 2000")
    _ensure(db_path)
    sql = ["SELECT * FROM learner_transition WHERE 1 = 1"]
    args: list[Any] = []
    for column, value in (("status", status), ("source_system", source_system),
                          ("destination_system", destination_system),
                          ("journey_id", journey_id)):
        if value:
            sql.append(f"AND {column} = ?")
            args.append(value)
    if open_only:
        sql.append(f"AND status NOT IN ({', '.join('?' * len(CLOSED_STATUSES))})")
        args.extend(CLOSED_STATUSES)
    if since:
        sql.append("AND datetime(initiated_at) >= datetime(?)")
        args.append(since)
    if systems is not None:
        scoped = sorted({s for s in systems if s})
        if not scoped:
            return []
        marks = ", ".join("?" * len(scoped))
        sql.append(f"AND (source_system IN ({marks}) OR destination_system IN ({marks}))")
        args.extend(scoped)
        args.extend(scoped)
    sql.append("ORDER BY initiated_at DESC, rowid DESC LIMIT ?")
    args.append(limit)
    conn = connect(db_path)
    try:
        rows = conn.execute(" ".join(sql), args).fetchall()  # nosec B608 - literals only
    finally:
        conn.close()
    return [public(dict(r)) for r in rows]


def get_transition(transition_id: str, *, db_path: str | None = None) -> dict | None:
    row = _transitions_module().get_transition(transition_id, db_path=db_path)
    return public(row)


def transition_events(transition_id: str, *, db_path: str | None = None) -> tuple[list[dict], str]:
    """The step history of one transition, and where it came from.

    Prefers the workflow's own ``list_transition_events``; falls back to
    the bus outbox, where every workflow step is published with the
    transition id in its payload.
    """
    fn = workflow_function("list_transition_events")
    if fn is not None:
        try:
            return list(call_flexible(fn, transition_id, db_path=db_path)), "workflow"
        except Exception:
            logger.warning("list_transition_events failed for %s; using the bus",
                           transition_id, exc_info=True)
    from education_system.platform.integrations.external import cross_system_bus
    events = cross_system_bus.list_events(
        transition_id=transition_id, limit=500, db_path=db_path)
    events.reverse()  # oldest first reads as a history
    return events, "bus"


def transition_checklist(transition_id: str, *, db_path: str | None = None) -> list[dict] | None:
    """The transition's checklist, or ``None`` if the workflow has none yet."""
    fn = workflow_function("get_checklist")
    if fn is None:
        return None
    result = call_flexible(fn, transition_id, db_path=db_path)
    if isinstance(result, dict):
        items = result.get("items")
        return list(items) if isinstance(items, list) else [result]
    return list(result or [])


def checklist_item_done(item: dict) -> bool:
    for key in ("done", "completed", "ticked", "is_done"):
        if key in item:
            return bool(item[key])
    return bool(item.get("completed_at") or item.get("ticked_at"))


def transition_detail(transition_id: str, *, db_path: str | None = None) -> dict | None:
    """Everything the monitor shows for one transition."""
    row = get_transition(transition_id, db_path=db_path)
    if row is None:
        return None
    events, events_source = transition_events(transition_id, db_path=db_path)
    try:
        checklist = transition_checklist(transition_id, db_path=db_path)
    except Exception:
        logger.warning("Checklist unavailable for %s", transition_id, exc_info=True)
        checklist = None
    return {
        "transition": row,
        "events": events,
        "events_source": events_source,
        "checklist": checklist,
        "checklist_available": checklist is not None,
    }


def overdue_transitions(*, stale_days: int = 14, today: date | None = None,
                        systems: Collection[str] | None = None,
                        db_path: str | None = None) -> list[dict]:
    """Open transitions past their effective date or idle for *stale_days*.

    A transition with a start date that has passed and is not complete is
    overdue whatever its activity; one with no date is only overdue once
    nothing has happened to it for ``stale_days``.
    """
    today = today or date.today()
    cutoff = datetime.combine(today - timedelta(days=stale_days), datetime.min.time())
    out = []
    for row in search_transitions(open_only=True, systems=systems, limit=2000,
                                  db_path=db_path):
        due = row.get("effective_date")
        if due and due < today.isoformat():
            out.append({**row, "overdue_reason": f"effective date {due} has passed"})
            continue
        stamp = row.get("updated_at") or row.get("initiated_at")
        try:
            last = datetime.fromisoformat(str(stamp).replace("Z", ""))
        except (TypeError, ValueError):
            continue
        if last < cutoff:
            out.append({**row, "overdue_reason":
                        f"no activity since {str(stamp)[:10]}"})
    return out


def transition_counts(*, db_path: str | None = None) -> dict:
    """Counts by status and by (source, destination) boundary."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        by_status = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM learner_transition GROUP BY status")}
        by_boundary = [dict(r) for r in conn.execute(
            "SELECT source_system, destination_system, status, COUNT(*) AS n "
            "FROM learner_transition GROUP BY 1, 2, 3 ORDER BY n DESC")]
    finally:
        conn.close()
    return {"by_status": by_status, "by_boundary": by_boundary,
            "open": sum(n for s, n in by_status.items() if s not in CLOSED_STATUSES)}


# ---------------------------------------------------------------------------
# Learners
# ---------------------------------------------------------------------------

def search_learners(query: str, *, limit: int = 50,
                    db_path: str | None = None) -> list[dict]:
    """Journeys matching a name, a journey id prefix, or any local id."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    from education_system.platform.cross_system.identity_service import SYSTEM_SLOTS
    _ensure(db_path)
    conn = connect(db_path)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(student_journey)")}
        id_cols = [c for _pk, c in SYSTEM_SLOTS.values() if c in cols]
        like = f"%{query}%"
        clauses = ["journey_id LIKE ?",
                   "(legal_first_name || ' ' || legal_last_name) LIKE ?"]
        args: list[Any] = [f"{query}%", like]
        for col in id_cols:
            clauses.append(f"{col} = ?")
            args.append(query)
        args.append(limit)
        # Merged journeys are tombstones pointing at their survivor; listing
        # them would offer the same learner twice.
        rows = conn.execute(
            "SELECT journey_id, legal_first_name, legal_last_name, date_of_birth, "
            "current_system, status FROM student_journey "
            f"WHERE ({' OR '.join(clauses)}) "  # nosec B608 - column names from SYSTEM_SLOTS
            "AND COALESCE(status, '') != 'merged' "
            "ORDER BY legal_last_name, legal_first_name LIMIT ?", args).fetchall()
    finally:
        conn.close()
    return [{
        "journey_id": r["journey_id"],
        "name": f"{r['legal_first_name']} {r['legal_last_name']}".strip(),
        "date_of_birth": r["date_of_birth"],
        "current_system": r["current_system"],
        "status": r["status"],
    } for r in rows]


def resolve_journey(journey_id: str, *, db_path: str | None = None) -> str | None:
    """The surviving journey id (follows merges), or ``None`` if unknown."""
    from education_system.platform.cross_system import identity_service
    resolver = getattr(identity_service, "resolve_journey_id", None)
    if resolver is None:
        return journey_id if identity_service.get(journey_id, db_path=db_path) else None
    return resolver(journey_id, db_path=db_path)


def learner_systems(journey_id: str, *, db_path: str | None = None) -> set[str] | None:
    """Systems that hold this learner, or ``None`` if the journey is unknown.

    The union of the legacy per-phase slots and the enrolment rows, because
    a journey registered before enrolments existed has only slots, and a
    non-phase destination (an apprenticeship at an external provider) has
    only an enrolment.
    """
    from education_system.platform.cross_system import enrolments, identity_service
    journey = identity_service.get(journey_id, db_path=db_path)
    if journey is None:
        return None
    systems = {s for s, (_pk, col) in identity_service.SYSTEM_SLOTS.items()
               if journey.get(col) or journey.get(_pk)}
    if journey.get("current_system"):
        systems.add(journey["current_system"])
    try:
        systems |= {r["system"] for r in enrolments.list_enrolments(
            journey_id, db_path=db_path)}
    except Exception:
        logger.debug("Enrolments unavailable for %s", journey_id, exc_info=True)
    return systems


def learner_360_record(journey_id: str, *, viewer_role: str | None = None,
                       viewer_system: str | None = None,
                       db_path: str | None = None) -> dict | None:
    """``learner_360.build_learner_360``, or ``None`` if not installed.

    Passes the auth DB as ``auth_db`` — that function's name for it. A
    ``db_path`` keyword would be silently dropped and the view built from
    the default (live) auth database. ``viewer_role=None`` is the trusted
    platform tier; pass the viewer's role to get their tier instead.
    """
    try:
        from education_system.platform.cross_system import learner_360
    except ImportError:
        return None
    build = getattr(learner_360, "build_learner_360", None)
    if build is None:
        return None
    return build(journey_id, viewer_role=viewer_role, viewer_system=viewer_system,
                 auth_db=db_path)


def duplicate_candidates(*, limit: int = 100,
                         db_path: str | None = None) -> list[dict] | None:
    """Possible duplicate journeys as dicts, or ``None`` if not installed.

    Each has ``journey_id`` (suggested survivor), ``duplicate_id``,
    ``score`` and ``reasons``, plus the two journey rows.
    """
    try:
        from education_system.platform.cross_system import identity_service
    except ImportError:
        return None
    finder = getattr(identity_service, "find_duplicate_candidates", None)
    if finder is None:
        return None
    out = []
    for cand in call_flexible(finder, limit=limit, db_path=db_path) or []:
        if hasattr(cand, "as_dict"):
            out.append(cand.as_dict())
        elif isinstance(cand, dict):
            out.append(dict(cand))
        else:
            import dataclasses
            out.append(dataclasses.asdict(cand))
    return out


def event_display(event: dict) -> dict:
    """One step-history row, whether from the workflow trail or the bus.

    The workflow's ``learner_transition_event`` rows carry ``step``/``at``/
    ``actor``; bus envelopes carry ``event_name``/``created_at`` and the two
    systems. Screens show both through this one shape.
    """
    if "step" in event:
        return {"when": str(event.get("at") or "")[:16],
                "what": event["step"],
                "detail": " → ".join(s for s in (event.get("from_status"),
                                                 event["step"]) if s),
                "who": event.get("actor") or "",
                "effective_date": event.get("effective_date")}
    return {"when": str(event.get("created_at") or "")[:16],
            "what": event.get("event_name") or "",
            "detail": f"{label(event.get('source_system'))} → "
                      f"{label(event.get('target_system'))}",
            "who": event.get("delivery_status") or "",
            "effective_date": (event.get("payload") or {}).get("start_date")}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def action_system(action: str, transition: dict) -> str | None:
    """The system whose staff may take *action* on *transition*.

    Approval releases the source's information, so it belongs to the
    source. Rejection, acknowledgement and completion are the receiving
    institution's decisions.
    """
    if action == "approve":
        return transition.get("source_system")
    return transition.get("destination_system")


def action_permission(action: str) -> str:
    return PERM_TRANSFER_APPROVE if action in ("approve", "reject") \
        else PERM_TRANSFER_ACKNOWLEDGE


def _adapter_handover(transition: dict, consent: Any):
    """Build the handover through the source system's adapter."""
    from education_system.platform.cross_system import enrolments, handover
    from education_system.platform.cross_system.adapters import registry

    source = transition.get("source_system")
    destination = transition["destination_system"]
    adapter = registry.get(source) if source else None
    if adapter is None or not adapter.capabilities().get("export_handover"):
        raise ActionUnavailable(
            f"No handover payload was supplied and the {label(source)} adapter "
            "cannot export one here. Approve from the source system's board, "
            "or supply the approved payload.")
    local_id = None
    if transition.get("source_enrolment_id"):
        src = enrolments.get_enrolment(transition["source_enrolment_id"],
                                       db_path=transition.get("_db_path"))
        local_id = (src or {}).get("local_student_id")
    if not local_id:
        raise ActionUnavailable(
            "The source enrolment has no local student id to export from.")
    exported = adapter.export_handover(local_id, consent,
                                       destination_system=destination)
    return handover.build_handover(
        source, destination, exported.record, consent=consent,
        safeguarding_reference=exported.safeguarding_reference)


def perform_action(
    action: str,
    transition_id: str,
    *,
    actor_user_id: int | None = None,
    actor: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
    handover: dict | None = None,
    consent: Any = None,
    consent_reference: str | None = None,
    start_date: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Run one workflow action and return the transition as :func:`public`.

    Raises ``transitions.TransitionError`` for an illegal move and
    :class:`ActionUnavailable` when the workflow does not provide the step.
    """
    if action not in ACTIONS:
        raise ValueError(f"Unknown action {action!r}; expected one of {ACTIONS}")
    transitions = _transitions_module()
    # Workflow steps take **payload and publish it, so anything passed here
    # ends up on the bus. Unset values are dropped rather than published as
    # nulls, and db_path is only passed where it is a real parameter.
    common = {k: v for k, v in {"actor_user_id": actor_user_id,
                                "actor": actor}.items() if v is not None}
    common["db_path"] = db_path

    if action == "approve":
        custom = workflow_function("approve")
        if custom is not None and handover is None:
            result = call_flexible(custom, transition_id, consent=consent,
                                   consent_reference=consent_reference, **common)
        else:
            payload: Any = handover
            if payload is None:
                current = transitions.get_transition(transition_id, db_path=db_path)
                if current is None:
                    raise transitions.TransitionError(f"No transition {transition_id}")
                current["_db_path"] = db_path
                payload = _adapter_handover(current, consent)
            result = transitions.approve_handover(
                transition_id, payload, consent_reference=consent_reference,
                db_path=db_path)
    elif action == "complete":
        result = transitions.complete(transition_id, start_date=start_date,
                                      db_path=db_path)
    else:
        fn = workflow_function(action)
        if fn is None:
            raise ActionUnavailable(
                f"The transfer workflow has no '{action}' step yet.")
        if action == "reject":
            # reject() publishes its **payload; only the decision itself is
            # passed, never the operator's name or free-text notes.
            result = fn(transition_id, reason=reason, actor_user_id=actor_user_id,
                        db_path=db_path)
        else:
            # acknowledge() keeps its note on the audit trail, not the bus.
            extra = {"note": notes} if notes else {}
            result = call_flexible(fn, transition_id, actor_user_id=actor_user_id,
                                   db_path=db_path, **extra)
    if isinstance(result, dict) and result.get("transition_id"):
        return public(result) or {}
    return get_transition(transition_id, db_path=db_path) or {}


def tick_checklist(transition_id: str, item: str, *, done: bool = True,
                   actor_user_id: int | None = None, actor: str | None = None,
                   db_path: str | None = None) -> Any:
    fn = workflow_function("tick_checklist_item")
    if fn is None:
        raise ActionUnavailable("The transfer workflow has no checklist yet.")
    return call_flexible(fn, transition_id, item, done=done,
                         actor_user_id=actor_user_id, actor=actor, db_path=db_path)


def start_transfer(*, journey_id: str, destination_system: str | None = None,
                   source_system: str | None = None,
                   source_enrolment_id: str | None = None,
                   reason: str | None = None, status: str = "expected",
                   actor_user_id: int | None = None,
                   db_path: str | None = None) -> dict:
    """Open a transition (``transitions.start_transition``) as a public row."""
    row = _transitions_module().start_transition(
        journey_id=journey_id, destination_system=destination_system,
        source_system=source_system, source_enrolment_id=source_enrolment_id,
        reason=reason, actor_user_id=actor_user_id, status=status,
        db_path=db_path)
    return public(row) or {}


__all__ = [
    "ACTIONS",
    "AWAITING",
    "ActionUnavailable",
    "CLOSED_STATUSES",
    "action_permission",
    "action_system",
    "call_flexible",
    "checklist_item_done",
    "duplicate_candidates",
    "event_display",
    "get_transition",
    "learner_360_record",
    "resolve_journey",
    "learner_systems",
    "overdue_transitions",
    "perform_action",
    "public",
    "search_learners",
    "search_transitions",
    "start_transfer",
    "tick_checklist",
    "transition_checklist",
    "transition_counts",
    "transition_detail",
    "transition_events",
    "workflow_function",
]
