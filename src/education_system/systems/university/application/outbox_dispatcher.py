"""Delivers the university event outbox (``university_event_outbox``).

Services write events in the same transaction as the decision
(``infrastructure/events.transactional_publisher``); this dispatcher acts on
them afterwards, so an outage downstream never undoes a decision.

For each due event (not delivered, not dead-lettered, ``available_at``
reached) it runs the event's handler and then feeds the institutional
connectors (``connector_feeds``):

* ``student.provisioning.requested`` - finishes provisioning
  (``StudentLifecycleService.provision``); left for a few minutes first,
  because the screen that created the student usually does it straight
  away.
* ``student.purge.requested`` - opens a right-to-erasure request in the
  dual-control queue (``application/students/erasure``), where a second
  person approves it after re-entering their password and someone then
  carries it out. Nothing is deleted here.
* every other known event - only the connector feeds.

A failure is retried with a growing delay (1, 2, 4 ... minutes, capped at
an hour); after :data:`MAX_ATTEMPTS` the event is dead-lettered with its
last error, and :func:`requeue` gives it another go. Unknown event names
are dead-lettered straight away so they are seen.

The same pass drains the student lifecycle actions
(``lifecycle_handlers.drain``). :func:`start_worker` runs both every minute
in a daemon thread.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from education_system.systems.university.application import connector_feeds, lifecycle_handlers
from education_system.systems.university.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 8
#: Each provisioning retry sends the activation e-mail again, so give up sooner.
MAX_PROVISIONING_ATTEMPTS = 3
PROVISIONING_SETTLE = timedelta(minutes=5)
INTERVAL = 60
_WORKER: threading.Thread | None = None
_LOCK = threading.Lock()
_PASS_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(UTC)


def _provision(event: Mapping[str, Any]) -> None:
    from education_system.systems.university.application.students.lifecycle import (
        StudentLifecycleService,
    )

    from education_system.systems.university.infrastructure.auth import UserAuth

    result = StudentLifecycleService().provision(str(event["aggregate_id"]), auth=UserAuth())
    if getattr(result, "provisioning_error", None):
        raise RuntimeError(f"provisioning incomplete: {result.provisioning_error}")


def _open_erasure_request(event: Mapping[str, Any]) -> None:
    from education_system.systems.university.application.students import erasure

    p = event["payload"]
    reason = str(p.get("reason") or "")
    if p.get("approved_by"):
        reason += f" (approval named on the API request: {p['approved_by']})"
    with transaction() as conn:
        open_already = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='student_erasure_requests'").fetchone() and conn.execute(
            "SELECT 1 FROM student_erasure_requests WHERE student_id = ? "
            "AND status IN ('requested', 'approved')", (str(p["student_id"]),)).fetchone()
        if open_already:
            return
        erasure.request(conn, str(p["student_id"]), str(p.get("case_reference") or ""),
                        reason, str(p.get("actor_id") or "api"))


def _feeds_only(event: Mapping[str, Any]) -> None:
    """The event's work is the connector feeds, run after every handler."""


HANDLERS: dict[str, Callable[[Mapping[str, Any]], None]] = {
    "student.provisioning.requested": _provision,
    "student.purge.requested": _open_erasure_request,
    "safeguarding.case.raised": _feeds_only,  # the DSL is told when the case is saved
    **{name: _feeds_only for name in connector_feeds.FEEDS},
}


def _due(limit: int) -> list[dict[str, Any]]:
    now = _now()
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM university_event_outbox WHERE delivered_at IS NULL "
            "AND dead_lettered_at IS NULL AND available_at <= ? "
            "ORDER BY available_at LIMIT ?", (now.isoformat(), limit),
        ).fetchall()
    due = []
    for row in rows:
        event = dict(row)
        if (event["event_name"] == "student.provisioning.requested" and not event["attempts"]
                and _parse(event["available_at"]) > now - PROVISIONING_SETTLE):
            continue
        event["payload"] = json.loads(event["payload_json"] or "{}")
        due.append(event)
    return due


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _delivered(event_id: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE university_event_outbox SET delivered_at = ?, last_error = NULL, "
            "attempts = attempts + 1 WHERE event_id = ? AND delivered_at IS NULL",
            (_now().isoformat(), event_id),
        )


def _limit(event: Mapping[str, Any]) -> int:
    if event["event_name"] == "student.provisioning.requested":
        return MAX_PROVISIONING_ATTEMPTS
    return MAX_ATTEMPTS


def _failed(event: Mapping[str, Any], error: str, *, final: bool = False) -> None:
    attempts = int(event.get("attempts") or 0) + 1
    now = _now()
    dead = final or attempts >= _limit(event)
    retry_at = now + timedelta(minutes=min(60, 2 ** (attempts - 1)))
    with transaction() as conn:
        conn.execute(
            "UPDATE university_event_outbox SET attempts = ?, last_error = ?, "
            "available_at = ?, dead_lettered_at = ? WHERE event_id = ?",
            (attempts, error[:500], retry_at.isoformat(),
             now.isoformat() if dead else None, event["event_id"]),
        )


def dispatch(event: Mapping[str, Any]) -> None:
    """Run one event's handler and connector feeds (raises on failure)."""
    handler = HANDLERS[event["event_name"]]
    handler(event)
    connector_feeds.feed(event["event_id"], event["event_name"], event["payload"])


def drain(limit: int = 50) -> dict[str, int]:
    """Deliver due events. Returns counts of delivered / retrying / dead."""
    counts = {"delivered": 0, "retrying": 0, "dead_lettered": 0}
    for event in _due(limit):
        if event["event_name"] not in HANDLERS:
            _failed(event, f"No handler for {event['event_name']}", final=True)
            counts["dead_lettered"] += 1
            continue
        try:
            dispatch(event)
        except Exception as exc:
            logger.warning("Outbox event %s (%s) failed: %s",
                           event["event_id"], event["event_name"], exc)
            _failed(event, str(exc))
            dead = int(event.get("attempts") or 0) + 1 >= _limit(event)
            counts["dead_lettered" if dead else "retrying"] += 1
            continue
        _delivered(event["event_id"])
        counts["delivered"] += 1
    return counts


def run_once() -> dict[str, Any]:
    """One pass over the outbox and the lifecycle actions."""
    if not _PASS_LOCK.acquire(blocking=False):
        return {"skipped": "a pass is already running"}
    try:
        return {"outbox": drain(), "lifecycle_actions": lifecycle_handlers.drain()}
    finally:
        _PASS_LOCK.release()


# ── for the admin screens ───────────────────────────────────────────────


def summary() -> dict[str, int]:
    with transaction() as conn:
        row = conn.execute(
            "SELECT SUM(delivered_at IS NOT NULL), "
            "SUM(delivered_at IS NULL AND dead_lettered_at IS NULL), "
            "SUM(dead_lettered_at IS NOT NULL) FROM university_event_outbox").fetchone()
        actions = dict(conn.execute(
            "SELECT status, COUNT(*) FROM student_lifecycle_actions GROUP BY status"
        ).fetchall()) if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='student_lifecycle_actions'").fetchone() else {}
    return {"delivered": int(row[0] or 0), "waiting": int(row[1] or 0),
            "dead_lettered": int(row[2] or 0),
            "actions_pending": int(actions.get("pending", 0)),
            "actions_failed": int(actions.get("failed", 0)),
            "actions_completed": int(actions.get("completed", 0))}


def events(state: str = "waiting", limit: int = 200) -> list[dict[str, Any]]:
    """``waiting``, ``dead`` or ``delivered`` events, newest first (no payloads:
    some carry names and e-mail addresses)."""
    where = {"waiting": "delivered_at IS NULL AND dead_lettered_at IS NULL",
             "dead": "dead_lettered_at IS NOT NULL",
             "delivered": "delivered_at IS NOT NULL"}[state]
    with transaction() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT event_id, event_name, aggregate_id, attempts, available_at, "  # nosec B608
            f"delivered_at, dead_lettered_at, last_error FROM university_event_outbox "
            f"WHERE {where} ORDER BY available_at DESC LIMIT ?", (limit,))]


def lifecycle_actions(limit: int = 200) -> list[dict[str, Any]]:
    with transaction() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT action_id, student_id, target_system, action, status, attempts, "
            "last_error, created_at FROM student_lifecycle_actions "
            "WHERE status IN ('pending', 'failed') ORDER BY action_id DESC LIMIT ?",
            (limit,))]


def requeue(event_id: str) -> bool:
    """Give a dead-lettered event another run of attempts, now."""
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE university_event_outbox SET dead_lettered_at = NULL, attempts = 0, "
            "available_at = ? WHERE event_id = ? AND dead_lettered_at IS NOT NULL",
            (_now().isoformat(), event_id))
        return cur.rowcount == 1


# ── worker ──────────────────────────────────────────────────────────────


def _loop(interval: int) -> None:
    while True:
        try:
            result = run_once()
            if any(result.get("outbox", {}).values()) or any(
                    result.get("lifecycle_actions", {}).values()):
                logger.info("University outbox pass: %s", result)
        except Exception:
            logger.exception("University outbox pass failed")
        time.sleep(interval)


def start_worker(interval: int = INTERVAL) -> bool:
    """Start the dispatcher once per process; False if already running."""
    global _WORKER
    with _LOCK:
        if _WORKER and _WORKER.is_alive():
            return False
        _WORKER = threading.Thread(target=_loop, args=(interval,), daemon=True,
                                   name="university-outbox")
        _WORKER.start()
        return True


__all__ = [
    "HANDLERS", "MAX_ATTEMPTS", "dispatch", "drain", "events", "lifecycle_actions",
    "requeue", "run_once", "start_worker", "summary",
]
