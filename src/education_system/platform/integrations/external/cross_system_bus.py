"""Durable cross-system event bus.

The existing in-process ``_event_bus`` (under
``university_system/.../academics/gui/_event_bus.py``) is fast-path only
and cannot carry events between subsystem processes. This module is the
durable bridge: producers write a row to ``cross_system_event_outbox`` in the
shared auth database, and each subsystem runs a poller that reads new
events targeted at it (or broadcast events) and dispatches them to
in-process subscribers.

Idempotency is guaranteed by the
``(event_id, consumer_system, consumer_handler)`` PK on
``cross_system_event_consumed`` — re-delivery is silently dropped.

A failed handler records ``status='failed'`` with the error and an
``attempts`` counter. ``poll_and_dispatch`` will retry events whose
last status is ``'failed'`` up to ``max_attempts``.

Step 1 of the cross-system integration plan — the durable transport.
Producers / consumers are wired in subsequent steps.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import uuid
from collections.abc import Callable, Collection
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any

from education_system.platform.identity.auth.db import connect
from education_system.platform.kernel.core.correlation import (
    get_correlation_id,
    new_correlation_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event-name catalogue (v1 minimum viable set)
# ---------------------------------------------------------------------------
# Events follow the dotted ``domain.action.tense`` convention used by the
# existing in-process bus. Adding a new event here is a one-liner; consumers
# subscribe via ``subscribe(event_name, handler)``.

EVENT_JOURNEY_REGISTERED        = "journey.registered"
EVENT_JOURNEY_TRANSITIONED      = "journey.transitioned"
EVENT_STUDENT_PROGRESSION_OFFERED   = "student.progression.offered"
EVENT_STUDENT_PROGRESSION_ACCEPTED  = "student.progression.accepted"
EVENT_STUDENT_PROGRESSION_COMPLETED = "student.progression.completed"
EVENT_STUDENT_WITHDRAWN         = "student.withdrawn"
EVENT_QUALIFICATION_AWARDED     = "qualification.awarded"
EVENT_SAFEGUARDING_FLAG_RAISED  = "safeguarding.flag.raised"
EVENT_GDPR_REDACTION_REQUESTED  = "gdpr.redaction.requested"
EVENT_PARENT_LINKAGE_CHANGED    = "parent.linkage.changed"

# ── Degree apprenticeship concurrent-enrolment workflow ──
EVENT_DEGREE_APPRENTICESHIP_LINKED = "degree_apprenticeship.linked"
EVENT_UNIVERSITY_REGISTRATION_CHANGED = "university.registration.changed"
EVENT_UNIVERSITY_CREDITS_UPDATED = "university.credits.updated"
EVENT_UNIVERSITY_DEGREE_AWARDED = "university.degree.awarded"
EVENT_APPRENTICESHIP_GATEWAY_REQUESTED = "apprenticeship.gateway.requested"
EVENT_APPRENTICESHIP_COMPLETED = "apprenticeship.completed"
EVENT_DEGREE_APPRENTICESHIP_RECONCILIATION_REQUIRED = (
    "degree_apprenticeship.reconciliation_required"
)

# ── Enrolment-based transition workflow ──
# The seven steps of the common progression workflow, published by
# ``platform.cross_system.transitions`` as a transition advances. Every
# phase boundary uses the same vocabulary, so a consumer that handles
# ``place.offered`` handles it for nursery→primary and sixth_form→
# university alike.
EVENT_PROGRESSION_EXPECTED      = "progression.expected"
EVENT_APPLICATION_SUBMITTED     = "application.submitted"
EVENT_PLACE_OFFERED             = "place.offered"
EVENT_PLACE_ACCEPTED            = "place.accepted"
EVENT_HANDOVER_APPROVED         = "handover.approved"
EVENT_ENROLMENT_CREATED         = "enrolment.created"
EVENT_PROGRESSION_COMPLETED     = "progression.completed"
EVENT_PROGRESSION_CANCELLED     = "progression.cancelled"

# ── Linked-platform lifecycle ──
# Events the linked-education plan names that had no equivalent above.
# Where a plan name maps onto an event that already existed, it is listed
# in PLAN_EVENT_ALIASES rather than given a second name for the same thing.
EVENT_LEARNER_UPDATED           = "learner.updated"
EVENT_JOURNEY_MERGED            = "journey.merged"
EVENT_ENROLMENT_ENDED           = "enrolment.ended"
EVENT_PROGRESSION_REJECTED      = "progression.rejected"
EVENT_HANDOVER_ACKNOWLEDGED     = "handover.acknowledged"
EVENT_TRANSITION_REMINDER       = "transition.reminder"
EVENT_PROGRAMME_COMPLETED       = "programme.completed"
EVENT_LEARNER_GRADUATED         = "learner.graduated"
EVENT_APPRENTICESHIP_STARTED    = "apprenticeship.started"
EVENT_DESTINATION_RECORDED      = "destination.recorded"

# The plan's CamelCase vocabulary, mapped onto the dotted names actually
# published. Documentation and the event monitor use it; producers and
# consumers use the dotted names.
PLAN_EVENT_ALIASES: dict[str, str] = {
    "LearnerCreated": EVENT_JOURNEY_REGISTERED,
    "LearnerUpdated": EVENT_LEARNER_UPDATED,
    "EnrolmentCreated": EVENT_ENROLMENT_CREATED,
    "EnrolmentEnded": EVENT_ENROLMENT_ENDED,
    "ProgressionStarted": EVENT_PROGRESSION_EXPECTED,
    "ProgressionAccepted": EVENT_PLACE_ACCEPTED,
    "ProgressionRejected": EVENT_PROGRESSION_REJECTED,
    "TransferRequested": EVENT_APPLICATION_SUBMITTED,
    "TransferApproved": EVENT_HANDOVER_APPROVED,
    "TransferCompleted": EVENT_PROGRESSION_COMPLETED,
    "QualificationAchieved": EVENT_QUALIFICATION_AWARDED,
    "ProgrammeCompleted": EVENT_PROGRAMME_COMPLETED,
    "LearnerWithdrawn": EVENT_STUDENT_WITHDRAWN,
    "LearnerGraduated": EVENT_LEARNER_GRADUATED,
    "ApprenticeshipStarted": EVENT_APPRENTICESHIP_STARTED,
    "ApprenticeshipCompleted": EVENT_APPRENTICESHIP_COMPLETED,
    "UniversityAdmissionAccepted": EVENT_PLACE_ACCEPTED,
}

# Compatibility bridge. Three workflow steps duplicate events that existing
# consumers already subscribe to — notably ``ProgressionIntake``, which
# listens for ``student.progression.completed``. ``transitions`` publishes
# the legacy twin alongside the new name so nothing that works today stops
# working. Remove an entry once every consumer of the legacy name has moved
# to the workflow vocabulary.
LEGACY_EVENT_TWINS: dict[str, str] = {
    EVENT_PLACE_OFFERED:         EVENT_STUDENT_PROGRESSION_OFFERED,
    EVENT_PLACE_ACCEPTED:        EVENT_STUDENT_PROGRESSION_ACCEPTED,
    EVENT_PROGRESSION_COMPLETED: EVENT_STUDENT_PROGRESSION_COMPLETED,
}

# All known event names. Producers may publish unknown names too, but the
# core set above is what consumers should expect.
KNOWN_EVENTS: frozenset[str] = frozenset({
    EVENT_LEARNER_UPDATED,
    EVENT_JOURNEY_MERGED,
    EVENT_ENROLMENT_ENDED,
    EVENT_PROGRESSION_REJECTED,
    EVENT_HANDOVER_ACKNOWLEDGED,
    EVENT_TRANSITION_REMINDER,
    EVENT_PROGRAMME_COMPLETED,
    EVENT_LEARNER_GRADUATED,
    EVENT_APPRENTICESHIP_STARTED,
    EVENT_DESTINATION_RECORDED,
    EVENT_JOURNEY_REGISTERED,
    EVENT_JOURNEY_TRANSITIONED,
    EVENT_STUDENT_PROGRESSION_OFFERED,
    EVENT_STUDENT_PROGRESSION_ACCEPTED,
    EVENT_STUDENT_PROGRESSION_COMPLETED,
    EVENT_STUDENT_WITHDRAWN,
    EVENT_QUALIFICATION_AWARDED,
    EVENT_SAFEGUARDING_FLAG_RAISED,
    EVENT_GDPR_REDACTION_REQUESTED,
    EVENT_PARENT_LINKAGE_CHANGED,
    EVENT_DEGREE_APPRENTICESHIP_LINKED,
    EVENT_UNIVERSITY_REGISTRATION_CHANGED,
    EVENT_UNIVERSITY_CREDITS_UPDATED,
    EVENT_UNIVERSITY_DEGREE_AWARDED,
    EVENT_APPRENTICESHIP_GATEWAY_REQUESTED,
    EVENT_APPRENTICESHIP_COMPLETED,
    EVENT_DEGREE_APPRENTICESHIP_RECONCILIATION_REQUIRED,
    EVENT_PROGRESSION_EXPECTED,
    EVENT_APPLICATION_SUBMITTED,
    EVENT_PLACE_OFFERED,
    EVENT_PLACE_ACCEPTED,
    EVENT_HANDOVER_APPROVED,
    EVENT_ENROLMENT_CREATED,
    EVENT_PROGRESSION_COMPLETED,
    EVENT_PROGRESSION_CANCELLED,
})

# ── Published before they were catalogued ──
# Both names were already on the bus — the university's student lifecycle
# publishes ``enrolment.changed`` and the secondary post-16 board publishes
# ``post16.application.status_changed`` — but neither was in KNOWN_EVENTS,
# so the webhook forwarder and the event monitor could not see them.
EVENT_ENROLMENT_CHANGED                  = "enrolment.changed"
EVENT_POST16_APPLICATION_STATUS_CHANGED  = "post16.application.status_changed"

KNOWN_EVENTS = KNOWN_EVENTS | frozenset({
    EVENT_ENROLMENT_CHANGED,
    EVENT_POST16_APPLICATION_STATUS_CHANGED,
})


# ---------------------------------------------------------------------------
# In-process subscriber registry
# ---------------------------------------------------------------------------

_HandlerSig = Callable[[dict], None]
_AlertSig = Callable[[dict[str, Any]], None]
_subscribers: dict[str, list[tuple[str, _HandlerSig]]] = {}
_delivery_alert_handlers: list[_AlertSig] = []
_lock = threading.RLock()

# The auth DB the current dispatch is reading from. Handlers receive only
# the envelope, so a shared consumer that writes back (a notification, a
# webhook delivery row) would otherwise always hit the default database —
# which, in a test that drives the bus against a temp DB, is the live one.
_dispatch_db_path: ContextVar[str | None] = ContextVar(
    "cross_system_bus_dispatch_db_path", default=None)


def current_dispatch_db_path() -> str | None:
    """The ``db_path`` of the dispatch currently running this handler.

    ``None`` means the default auth database. Only meaningful inside a
    handler called by :func:`poll_and_dispatch`.
    """
    return _dispatch_db_path.get()


def subscribe(event_name: str, handler: _HandlerSig,
              *, handler_name: str | None = None) -> Callable[[], None]:
    """Register an in-process handler for ``event_name``.

    The poller calls registered handlers when it sees a matching event in
    the durable outbox. ``handler_name`` defaults to the dotted
    ``module.qualname`` of the callable and is used as the identity in
    ``cross_system_event_consumed`` so the same handler isn't run twice
    for the same event.

    Returns an unsubscribe callable.
    """
    name = handler_name or _default_handler_name(handler)
    with _lock:
        _subscribers.setdefault(event_name, []).append((name, handler))

    def _unsubscribe() -> None:
        with _lock:
            lst = _subscribers.get(event_name, [])
            _subscribers[event_name] = [(n, h) for (n, h) in lst if h is not handler]
    return _unsubscribe


def subscribe_delivery_alerts(handler: _AlertSig) -> Callable[[], None]:
    """Register an operations adapter for newly exhausted deliveries."""
    with _lock:
        _delivery_alert_handlers.append(handler)

    def _unsubscribe() -> None:
        with _lock:
            if handler in _delivery_alert_handlers:
                _delivery_alert_handlers.remove(handler)

    return _unsubscribe


def _alert_dead_letter(details: dict[str, Any]) -> None:
    logger.critical(
        "Cross-system delivery exhausted event_id=%s consumer=%s handler=%s "
        "attempts=%s",
        details["event_id"],
        details["consumer_system"],
        details["consumer_handler"],
        details["attempts"],
    )
    with _lock:
        handlers = tuple(_delivery_alert_handlers)
    for handler in handlers:
        try:
            handler(details)
        except Exception:
            logger.exception("Delivery-alert adapter failed")


def _default_handler_name(handler: _HandlerSig) -> str:
    mod = getattr(handler, "__module__", "?")
    qn = getattr(handler, "__qualname__", getattr(handler, "__name__", "?"))
    return f"{mod}.{qn}"


def clear_subscribers_for_test() -> None:
    """Test-only helper to reset the registry between tests."""
    with _lock:
        _subscribers.clear()


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def publish_cross_system(
    event_name: str,
    *,
    source_system: str,
    source_module: str,
    journey_id: str | None = None,
    target_system: str | None = None,
    actor_user_id: int | None = None,
    event_version: int = 1,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    available_at: str | None = None,
    db_path: str | None = None,
    **payload: Any,
) -> str:
    """Append a row to the durable outbox; return the new ``event_id``.

    ``target_system`` of ``None`` means broadcast — every consumer system
    will pick it up. Pass an explicit ``"university"`` / ``"sixth_form"`` /
    etc. to address a single recipient.

    Payload values must be JSON-serialisable. ``journey_id`` is the
    canonical identity key for student-scoped events.
    """
    if not event_name:
        raise ValueError("event_name is required")
    if event_version < 1:
        raise ValueError("event_version must be at least 1")
    event_id = str(uuid.uuid4())
    correlation = correlation_id or get_correlation_id() or new_correlation_id()
    idempotency = idempotency_key or event_id
    available = available_at or datetime.now(UTC).isoformat()
    payload_blob = json.dumps(payload, default=str)
    conn = connect(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO cross_system_event_outbox
                (event_id, event_name, event_version, correlation_id,
                 causation_id, idempotency_key, journey_id, source_system,
                 source_module, target_system, payload_json, actor_user_id,
                 available_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id, event_name, event_version, correlation,
                causation_id, idempotency, journey_id, source_system,
                source_module, target_system, payload_blob, actor_user_id,
                available,
            ),
        )
        if cursor.rowcount == 0:
            existing = conn.execute(
                "SELECT event_id FROM cross_system_event_outbox "
                "WHERE idempotency_key = ?",
                (idempotency,),
            ).fetchone()
            assert existing is not None
            event_id = str(existing["event_id"])
        conn.commit()
    finally:
        conn.close()
    logger.info(
        "cross_system_bus publish event=%s id=%s source=%s/%s target=%s journey=%s",
        event_name, event_id, source_system, source_module,
        target_system or "*", journey_id,
    )
    return event_id


# ---------------------------------------------------------------------------
# Poll & dispatch
# ---------------------------------------------------------------------------

def poll_and_dispatch(
    consumer_system: str,
    *,
    batch_size: int = 50,
    max_attempts: int = 5,
    db_path: str | None = None,
    any_target: bool = False,
    handler_names: Collection[str] | None = None,
) -> int:
    """Process up to ``batch_size`` outstanding events for ``consumer_system``.

    Selects events whose ``target_system`` is ``consumer_system`` or NULL
    (broadcast) and that have at least one registered subscriber, where:

      - no row exists in ``cross_system_event_consumed`` for any registered
        handler (= never tried), **or**
      - the previous attempt for that handler ended ``'failed'`` and
        ``attempts < max_attempts``.

    ``any_target=True`` drops the target filter, and ``handler_names``
    restricts dispatch to the named handlers. Together they let a
    platform-level drainer run the shared consumers (notifications,
    webhooks) over events addressed to a system that is not running —
    without also running that system's intake handlers in the wrong
    process.

    Returns the number of (event, handler) pairs dispatched, including
    failures.
    """
    if not consumer_system:
        raise ValueError("consumer_system is required")
    if not _subscribers:
        return 0
    allowed = frozenset(handler_names) if handler_names is not None else None

    dispatched = 0
    conn = connect(db_path)
    try:
        # We pull a wider batch than ``batch_size`` because some events may
        # have all their handlers already acked — they'd still count toward
        # the LIMIT otherwise. ``batch_size * 4`` is a conservative cap.
        target_clause = (
            "1 = 1" if any_target
            else "(target_system IS NULL OR target_system = ?)")
        params: list[Any] = [] if any_target else [consumer_system]
        params.append(max(batch_size * 4, batch_size))
        rows = conn.execute(
            f"""SELECT event_id, event_name, event_version, correlation_id,
                      causation_id, idempotency_key, journey_id, source_system,
                      source_module, target_system, payload_json,
                      actor_user_id, available_at, created_at
                 FROM cross_system_event_outbox
                WHERE {target_clause}
                  AND datetime(available_at) <= datetime('now')
                ORDER BY created_at, event_id
                LIMIT ?""",  # nosec B608 - clause is one of two literals
            params,
        ).fetchall()

        per_event_handled = 0
        for row in rows:
            if per_event_handled >= batch_size:
                break

            handlers = list(_subscribers.get(row["event_name"], []))
            if allowed is not None:
                handlers = [(n, h) for (n, h) in handlers if n in allowed]
            if not handlers:
                continue

            for handler_name, handler in handlers:
                ack_row = conn.execute(
                    """SELECT status, attempts, next_attempt_at
                         FROM cross_system_event_consumed
                        WHERE event_id = ? AND consumer_system = ?
                          AND consumer_handler = ?""",
                    (row["event_id"], consumer_system, handler_name),
                ).fetchone()

                if ack_row is not None:
                    if ack_row["status"] in {"ok", "skipped", "abandoned"}:
                        continue
                    if ack_row["status"] == "dead_letter":
                        continue
                    if ack_row["attempts"] >= max_attempts:
                        continue
                    if (
                        "next_attempt_at" in ack_row.keys()
                        and ack_row["next_attempt_at"]
                        and datetime.fromisoformat(
                            str(ack_row["next_attempt_at"]).replace("Z", "+00:00")
                        ) > datetime.now(UTC)
                    ):
                        continue

                envelope = _row_to_envelope(row)
                status, error = "ok", None
                token = _dispatch_db_path.set(db_path)
                try:
                    handler(envelope)
                except Exception as exc:
                    status = "failed"
                    error = repr(exc)
                    logger.exception(
                        "cross_system_bus handler %s failed for event %s id=%s",
                        handler_name, row["event_name"], row["event_id"],
                    )
                finally:
                    _dispatch_db_path.reset(token)

                attempts = (ack_row["attempts"] + 1) if ack_row else 1
                if status == "failed" and attempts >= max_attempts:
                    status = "dead_letter"
                next_attempt_at = None
                if status == "failed":
                    delay = min(300.0, 2 ** max(0, attempts - 1))
                    delay += random.uniform(0, max(0.1, delay * 0.25))
                    next_attempt_at = (
                        datetime.now(UTC) + timedelta(seconds=delay)
                    ).isoformat()
                conn.execute(
                    """INSERT INTO cross_system_event_consumed
                        (event_id, consumer_system, consumer_handler,
                         status, error_message, attempts, next_attempt_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (event_id, consumer_system, consumer_handler)
                        DO UPDATE SET status        = excluded.status,
                                      error_message = excluded.error_message,
                                      attempts      = excluded.attempts,
                                      next_attempt_at = excluded.next_attempt_at,
                                      consumed_at   = datetime('now')""",
                    (row["event_id"], consumer_system, handler_name,
                     status, error, attempts, next_attempt_at),
                )
                conn.commit()
                if status == "dead_letter":
                    _alert_dead_letter(
                        {
                            "event_id": row["event_id"],
                            "event_name": row["event_name"],
                            "consumer_system": consumer_system,
                            "consumer_handler": handler_name,
                            "attempts": attempts,
                            "error": error,
                            "correlation_id": row["correlation_id"],
                            "journey_id": row["journey_id"],
                            # Alert adapters write (an in-app notice), and
                            # must write to the database the event came from.
                            "db_path": db_path,
                        }
                    )
                dispatched += 1
                per_event_handled += 1
                if per_event_handled >= batch_size:
                    break
    finally:
        conn.close()
    return dispatched


def _row_to_envelope(row) -> dict:
    """Convert an outbox row into the dict passed to subscriber handlers."""
    try:
        payload = json.loads(row["payload_json"])
    except Exception:
        payload = {}
    return {
        "event_id":      row["event_id"],
        "event_name":    row["event_name"],
        "event_version": row["event_version"],
        "correlation_id": row["correlation_id"],
        "causation_id": row["causation_id"],
        "idempotency_key": row["idempotency_key"],
        "journey_id":    row["journey_id"],
        "source_system": row["source_system"],
        "source_module": row["source_module"],
        "target_system": row["target_system"],
        "actor_user_id": row["actor_user_id"],
        "created_at":    row["created_at"],
        "available_at":  row["available_at"],
        "payload":       payload,
    }


def events_for_journeys(
    journey_ids,
    *,
    event_name: str | None = None,
    db_path: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """``{journey_id: [envelope, ...]}`` — what was published about a learner.

    The outbox is append-only and every row keeps its payload, which makes
    it the record of what one system actually *sent* another rather than
    what the receiver chose to store. A handover dashboard needs exactly
    that: the university's admissions tables hold the applicant, but only
    the event says which handover fields crossed and which were withheld
    for want of consent.

    Newest first within each journey. Batched because the caller is a
    board showing a whole cohort, and one connection per learner is what
    makes such a screen feel broken.
    """
    ids = [str(j) for j in journey_ids if j]
    if not ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    conn = connect(db_path)
    try:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            placeholders = ",".join("?" * len(chunk))
            params: list[Any] = list(chunk)
            name_clause = ""
            if event_name:
                name_clause = " AND event_name = ?"
                params.append(event_name)
            rows = conn.execute(
                f"""SELECT * FROM cross_system_event_outbox
                     WHERE journey_id IN ({placeholders}){name_clause}
                     ORDER BY created_at DESC, rowid DESC""",  # nosec B608
                params,
            ).fetchall()
            for row in rows:
                out.setdefault(str(row["journey_id"]), []).append(
                    _row_to_envelope(row))
    finally:
        conn.close()
    return out


def latest_event_for_journey(
    journey_id: str,
    *,
    event_name: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    """The most recent envelope published about one journey, or ``None``."""
    found = events_for_journeys([journey_id], event_name=event_name,
                                db_path=db_path).get(str(journey_id)) or []
    return found[0] if found else None


def list_failed_deliveries(
    *,
    consumer_system: str | None = None,
    exhausted_only: bool = False,
    max_attempts: int = 5,
    limit: int = 100,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return operator-visible failed/dead-letter deliveries.

    A failed receipt at or above ``max_attempts`` is a dead letter. Rows remain
    immutable in the outbox; retry/abandon changes only the consumer receipt.
    """
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    conditions = ["c.status IN ('failed', 'dead_letter')"]
    params: list[Any] = []
    if consumer_system:
        conditions.append("c.consumer_system = ?")
        params.append(consumer_system)
    if exhausted_only:
        # A receipt the dispatcher already marked dead_letter is exhausted
        # whatever max_attempts that dispatcher ran with; comparing attempts
        # alone hid dead letters from a poller configured with fewer tries.
        conditions.append("(c.status = 'dead_letter' OR c.attempts >= ?)")
        params.append(max_attempts)
    params.append(limit)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"""SELECT c.event_id, c.consumer_system, c.consumer_handler,
                       c.status, c.error_message, c.attempts, c.consumed_at,
                       o.event_name, o.journey_id, o.source_system,
                       o.source_module, o.target_system, o.payload_json,
                       o.actor_user_id, o.created_at
                  FROM cross_system_event_consumed c
                  JOIN cross_system_event_outbox o
                    ON o.event_id = c.event_id
                 WHERE {' AND '.join(conditions)}
                 ORDER BY c.consumed_at DESC
                 LIMIT ?""",
            params,
        ).fetchall()
        return [
            {
                **dict(row),
                "dead_letter": (row["status"] == "dead_letter"
                                or row["attempts"] >= max_attempts),
                "payload": _decode_payload(row["payload_json"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def retry_failed_delivery(
    event_id: str,
    consumer_system: str,
    consumer_handler: str,
    *,
    db_path: str | None = None,
) -> bool:
    """Requeue one failed delivery while preserving its attempt history."""
    conn = connect(db_path)
    try:
        cursor = conn.execute(
            """UPDATE cross_system_event_consumed
                  SET status = 'failed', attempts = 0,
                      error_message = 'Manually queued for retry',
                      next_attempt_at = NULL,
                      consumed_at = datetime('now')
                WHERE event_id = ? AND consumer_system = ?
                  AND consumer_handler = ?
                  AND status IN ('failed', 'dead_letter', 'abandoned')""",
            (event_id, consumer_system, consumer_handler),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def abandon_failed_delivery(
    event_id: str,
    consumer_system: str,
    consumer_handler: str,
    *,
    reason: str,
    db_path: str | None = None,
) -> bool:
    """Mark a failed delivery as deliberately abandoned by an operator."""
    if not reason.strip():
        raise ValueError("An abandonment reason is required")
    conn = connect(db_path)
    try:
        cursor = conn.execute(
            """UPDATE cross_system_event_consumed
                  SET status = 'abandoned', error_message = ?,
                      consumed_at = datetime('now')
                WHERE event_id = ? AND consumer_system = ?
                  AND consumer_handler = ?
                  AND status IN ('failed', 'dead_letter')""",
            (
                f"Abandoned by operator: {reason.strip()}",
                event_id,
                consumer_system,
                consumer_handler,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _decode_payload(payload_json: str) -> dict[str, Any]:
    try:
        value = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {"value": value}


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

#: Delivery states :func:`list_events` reports, most urgent first. An event
#: has one receipt per (consumer system, handler), so its state is rolled up:
#: one dead letter makes the whole event a dead letter, because that is the
#: receipt an operator has to act on.
DELIVERY_STATUSES: tuple[str, ...] = (
    "dead_letter", "failed", "scheduled", "pending", "delivered", "abandoned",
)

_DELIVERY_STATUS_SQL = """
    CASE
      WHEN EXISTS (SELECT 1 FROM cross_system_event_consumed c
                    WHERE c.event_id = o.event_id
                      AND (c.status = 'dead_letter'
                           OR (c.status = 'failed' AND c.attempts >= :max_attempts)))
        THEN 'dead_letter'
      WHEN EXISTS (SELECT 1 FROM cross_system_event_consumed c
                    WHERE c.event_id = o.event_id AND c.status = 'failed')
        THEN 'failed'
      WHEN datetime(o.available_at) > datetime('now') THEN 'scheduled'
      WHEN EXISTS (SELECT 1 FROM cross_system_event_consumed c
                    WHERE c.event_id = o.event_id AND c.status IN ('ok', 'skipped'))
        THEN 'delivered'
      WHEN EXISTS (SELECT 1 FROM cross_system_event_consumed c
                    WHERE c.event_id = o.event_id AND c.status = 'abandoned')
        THEN 'abandoned'
      ELSE 'pending'
    END"""


def list_events(
    *,
    event_name: str | None = None,
    journey_id: str | None = None,
    source_system: str | None = None,
    target_system: str | None = None,
    since: str | None = None,
    status: str | None = None,
    limit: int = 200,
    transition_id: str | None = None,
    systems: Collection[str] | None = None,
    include_payload: bool = True,
    max_attempts: int = 5,
    db_path: str | None = None,
) -> list[dict]:
    """Newest-first outbox rows with a rolled-up delivery status.

    The read side for the event monitor and ``GET /api/v1/events``.
    ``event_name`` also accepts the plan's CamelCase vocabulary
    (``TransferApproved``), since that is what the monitor shows.
    ``status`` is one of :data:`DELIVERY_STATUSES`. ``systems`` restricts
    the result to events that name one of those systems as source or
    target — how a non-superadmin's view is scoped. ``transition_id``
    matches the id every workflow event carries in its payload.

    Each row is an envelope (see :func:`_row_to_envelope`) plus
    ``delivery_status`` and ``receipts`` (how many handler receipts exist).
    """
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if status is not None and status not in DELIVERY_STATUSES:
        raise ValueError(
            f"status must be one of {', '.join(DELIVERY_STATUSES)}")
    if event_name:
        event_name = PLAN_EVENT_ALIASES.get(event_name, event_name)

    conditions: list[str] = []
    params: dict[str, Any] = {"max_attempts": max_attempts, "limit": limit}
    for column, value in (("event_name", event_name),
                          ("journey_id", journey_id),
                          ("source_system", source_system),
                          ("target_system", target_system)):
        if value:
            conditions.append(f"o.{column} = :{column}")
            params[column] = value
    if since:
        conditions.append("datetime(o.created_at) >= datetime(:since)")
        params["since"] = since
    if transition_id:
        conditions.append(
            "json_extract(o.payload_json, '$.transition_id') = :transition_id")
        params["transition_id"] = transition_id
    if systems is not None:
        scoped = sorted({s for s in systems if s})
        if not scoped:
            return []
        names = []
        for i, system in enumerate(scoped):
            params[f"sys{i}"] = system
            names.append(f":sys{i}")
        joined = ", ".join(names)
        conditions.append(
            f"(o.source_system IN ({joined}) OR o.target_system IN ({joined}))")
    where = " AND ".join(conditions) or "1 = 1"
    status_clause = "WHERE delivery_status = :status" if status else ""
    if status:
        params["status"] = status

    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"""SELECT * FROM (
                    SELECT o.*,
                           {_DELIVERY_STATUS_SQL} AS delivery_status,
                           (SELECT COUNT(*) FROM cross_system_event_consumed c
                             WHERE c.event_id = o.event_id) AS receipts
                      FROM cross_system_event_outbox o
                     WHERE {where}
                ) {status_clause}
                ORDER BY created_at DESC, event_id DESC
                LIMIT :limit""",  # nosec B608 - clauses are built from literals
            params,
        ).fetchall()
    finally:
        conn.close()

    out = []
    for row in rows:
        envelope = _row_to_envelope(row)
        envelope["delivery_status"] = row["delivery_status"]
        envelope["receipts"] = row["receipts"]
        if not include_payload:
            envelope.pop("payload", None)
        out.append(envelope)
    return out


def delivery_backlog(
    consumer_system: str,
    *,
    max_attempts: int = 5,
    db_path: str | None = None,
) -> dict[str, int]:
    """Receipt counts for one consumer system — the intake health figure.

    ``undelivered`` counts events addressed to the system (or broadcast)
    with no receipt at all from it. That is an upper bound on its backlog:
    an event nobody in that system subscribes to also has no receipt.
    """
    conn = connect(db_path)
    try:
        counts = {
            r["status"]: r["n"] for r in conn.execute(
                """SELECT CASE WHEN status = 'failed' AND attempts >= ?
                               THEN 'dead_letter' ELSE status END AS status,
                          COUNT(*) AS n
                     FROM cross_system_event_consumed
                    WHERE consumer_system = ?
                    GROUP BY 1""",
                (max_attempts, consumer_system)).fetchall()
        }
        undelivered = conn.execute(
            """SELECT COUNT(*) FROM cross_system_event_outbox o
                WHERE (o.target_system IS NULL OR o.target_system = ?)
                  AND datetime(o.available_at) <= datetime('now')
                  AND NOT EXISTS (
                      SELECT 1 FROM cross_system_event_consumed c
                       WHERE c.event_id = o.event_id
                         AND c.consumer_system = ?)""",
            (consumer_system, consumer_system)).fetchone()[0]
    finally:
        conn.close()
    return {
        "delivered": counts.get("ok", 0) + counts.get("skipped", 0),
        "failed": counts.get("failed", 0),
        "dead_letter": counts.get("dead_letter", 0),
        "abandoned": counts.get("abandoned", 0),
        "undelivered": undelivered,
    }


__all__ = [
    "EVENT_JOURNEY_REGISTERED",
    "EVENT_JOURNEY_TRANSITIONED",
    "EVENT_STUDENT_PROGRESSION_OFFERED",
    "EVENT_STUDENT_PROGRESSION_ACCEPTED",
    "EVENT_STUDENT_PROGRESSION_COMPLETED",
    "EVENT_STUDENT_WITHDRAWN",
    "EVENT_QUALIFICATION_AWARDED",
    "EVENT_SAFEGUARDING_FLAG_RAISED",
    "EVENT_GDPR_REDACTION_REQUESTED",
    "EVENT_PARENT_LINKAGE_CHANGED",
    "EVENT_PROGRESSION_EXPECTED",
    "EVENT_APPLICATION_SUBMITTED",
    "EVENT_PLACE_OFFERED",
    "EVENT_PLACE_ACCEPTED",
    "EVENT_HANDOVER_APPROVED",
    "EVENT_ENROLMENT_CREATED",
    "EVENT_PROGRESSION_COMPLETED",
    "EVENT_PROGRESSION_CANCELLED",
    "EVENT_LEARNER_UPDATED",
    "EVENT_JOURNEY_MERGED",
    "EVENT_ENROLMENT_ENDED",
    "EVENT_PROGRESSION_REJECTED",
    "EVENT_HANDOVER_ACKNOWLEDGED",
    "EVENT_TRANSITION_REMINDER",
    "EVENT_PROGRAMME_COMPLETED",
    "EVENT_LEARNER_GRADUATED",
    "EVENT_APPRENTICESHIP_STARTED",
    "EVENT_DESTINATION_RECORDED",
    "EVENT_ENROLMENT_CHANGED",
    "EVENT_POST16_APPLICATION_STATUS_CHANGED",
    "PLAN_EVENT_ALIASES",
    "LEGACY_EVENT_TWINS",
    "KNOWN_EVENTS",
    "DELIVERY_STATUSES",
    "subscribe",
    "subscribe_delivery_alerts",
    "current_dispatch_db_path",
    "publish_cross_system",
    "poll_and_dispatch",
    "events_for_journeys",
    "latest_event_for_journey",
    "list_events",
    "delivery_backlog",
    "list_failed_deliveries",
    "retry_failed_delivery",
    "abandon_failed_delivery",
    "clear_subscribers_for_test",
]
