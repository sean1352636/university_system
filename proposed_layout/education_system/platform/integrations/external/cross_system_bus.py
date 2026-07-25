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
import threading
import uuid
from collections.abc import Callable
from typing import Any

from education_system.platform.identity.auth.db import connect

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

# All known event names. Producers may publish unknown names too, but the
# core set above is what consumers should expect.
KNOWN_EVENTS: frozenset[str] = frozenset({
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
})


# ---------------------------------------------------------------------------
# In-process subscriber registry
# ---------------------------------------------------------------------------

_HandlerSig = Callable[[dict], None]
_subscribers: dict[str, list[tuple[str, _HandlerSig]]] = {}
_lock = threading.RLock()


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
    event_id = str(uuid.uuid4())
    payload_blob = json.dumps(payload, default=str)
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO cross_system_event_outbox
                (event_id, event_name, journey_id, source_system,
                 source_module, target_system, payload_json, actor_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, event_name, journey_id, source_system,
             source_module, target_system, payload_blob, actor_user_id),
        )
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
) -> int:
    """Process up to ``batch_size`` outstanding events for ``consumer_system``.

    Selects events whose ``target_system`` is ``consumer_system`` or NULL
    (broadcast) and that have at least one registered subscriber, where:

      - no row exists in ``cross_system_event_consumed`` for any registered
        handler (= never tried), **or**
      - the previous attempt for that handler ended ``'failed'`` and
        ``attempts < max_attempts``.

    Returns the number of (event, handler) pairs dispatched, including
    failures.
    """
    if not consumer_system:
        raise ValueError("consumer_system is required")
    if not _subscribers:
        return 0

    dispatched = 0
    conn = connect(db_path)
    try:
        # We pull a wider batch than ``batch_size`` because some events may
        # have all their handlers already acked — they'd still count toward
        # the LIMIT otherwise. ``batch_size * 4`` is a conservative cap.
        rows = conn.execute(
            """SELECT event_id, event_name, journey_id, source_system,
                      source_module, target_system, payload_json,
                      actor_user_id, created_at
                 FROM cross_system_event_outbox
                WHERE target_system IS NULL OR target_system = ?
                ORDER BY created_at, event_id
                LIMIT ?""",
            (consumer_system, max(batch_size * 4, batch_size)),
        ).fetchall()

        per_event_handled = 0
        for row in rows:
            if per_event_handled >= batch_size:
                break

            handlers = list(_subscribers.get(row["event_name"], []))
            if not handlers:
                continue

            for handler_name, handler in handlers:
                ack_row = conn.execute(
                    """SELECT status, attempts FROM cross_system_event_consumed
                        WHERE event_id = ? AND consumer_system = ?
                          AND consumer_handler = ?""",
                    (row["event_id"], consumer_system, handler_name),
                ).fetchone()

                if ack_row is not None:
                    if ack_row["status"] == "ok" or ack_row["status"] == "skipped":
                        continue
                    if ack_row["attempts"] >= max_attempts:
                        continue

                envelope = _row_to_envelope(row)
                status, error = "ok", None
                try:
                    handler(envelope)
                except Exception as exc:
                    status = "failed"
                    error = repr(exc)
                    logger.exception(
                        "cross_system_bus handler %s failed for event %s id=%s",
                        handler_name, row["event_name"], row["event_id"],
                    )

                attempts = (ack_row["attempts"] + 1) if ack_row else 1
                conn.execute(
                    """INSERT INTO cross_system_event_consumed
                        (event_id, consumer_system, consumer_handler,
                         status, error_message, attempts)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT (event_id, consumer_system, consumer_handler)
                        DO UPDATE SET status        = excluded.status,
                                      error_message = excluded.error_message,
                                      attempts      = excluded.attempts,
                                      consumed_at   = datetime('now')""",
                    (row["event_id"], consumer_system, handler_name,
                     status, error, attempts),
                )
                conn.commit()
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
        "journey_id":    row["journey_id"],
        "source_system": row["source_system"],
        "source_module": row["source_module"],
        "target_system": row["target_system"],
        "actor_user_id": row["actor_user_id"],
        "created_at":    row["created_at"],
        "payload":       payload,
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
    "KNOWN_EVENTS",
    "subscribe",
    "publish_cross_system",
    "poll_and_dispatch",
    "clear_subscribers_for_test",
]
