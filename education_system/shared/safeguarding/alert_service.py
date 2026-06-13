"""Cross-system safeguarding alerts — a flag follows the learner.

A safeguarding concern raised in one system is recorded against the
canonical ``journey_id`` in the shared ``safeguarding_alerts`` table (in
``auth.db``), so *every* system can see it: a flag on a secondary-school
pupil is visible the moment they progress into sixth form. A
``safeguarding.flag.raised`` event is also published on the durable bus so
live systems are actively notified (drained in real time by the
:mod:`bus_drainer`), not just on next launch.

Two layers:

* :func:`raise_flag` / :func:`raise_flag_for_local_concern` — producers.
* :func:`get_alerts` — any system reads a learner's flags.
* :func:`register_consumer` — subscribes an idempotent handler that
  ensures an alert raised elsewhere is present locally (a hook point for
  per-system reactions; the shared table already makes it visible).
"""

from __future__ import annotations

import logging
import uuid

from education_system.shared.auth.db import connect
from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.integrations import cross_system_bus

logger = logging.getLogger(__name__)

_initialised: set[str] = set()


def _ensure(db_path: str | None) -> None:
    key = db_path or "<default>"
    if key in _initialised:
        return
    try:
        initialise_auth_db(db_path)
    except Exception:
        logger.debug("alert_service: auth schema init skipped", exc_info=True)
    _initialised.add(key)


def _insert_alert(row: dict, db_path: str | None) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO safeguarding_alerts
                 (alert_id, journey_id, source_system, source_ref, category,
                  severity, summary, raised_by, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["alert_id"], row["journey_id"], row["source_system"],
             row.get("source_ref"), row.get("category"),
             row.get("severity", "medium"), row.get("summary"),
             row.get("raised_by"), row.get("status", "open")))
        conn.commit()
    finally:
        conn.close()


def raise_flag(
    journey_id: str,
    *,
    source_system: str,
    category: str | None = None,
    severity: str = "medium",
    summary: str | None = None,
    source_ref: str | None = None,
    raised_by: str | None = None,
    db_path: str | None = None,
) -> str:
    """Record a safeguarding flag against ``journey_id`` and broadcast it.

    Returns the new ``alert_id``. The flag is immediately visible to every
    system via :func:`get_alerts`; the bus event notifies live systems.
    """
    _ensure(db_path)
    alert_id = str(uuid.uuid4())
    row = {
        "alert_id": alert_id, "journey_id": journey_id,
        "source_system": source_system, "source_ref": source_ref,
        "category": category, "severity": severity, "summary": summary,
        "raised_by": raised_by, "status": "open",
    }
    _insert_alert(row, db_path)
    try:
        # Payload carries the alert fields minus the keys that are explicit
        # publish_cross_system params (journey_id / source_system).
        payload = {k: v for k, v in row.items()
                   if k not in ("journey_id", "source_system")}
        cross_system_bus.publish_cross_system(
            cross_system_bus.EVENT_SAFEGUARDING_FLAG_RAISED,
            source_system=source_system,
            source_module="shared.safeguarding.alert_service",
            journey_id=journey_id, target_system=None,  # broadcast
            db_path=db_path, **payload)
    except Exception:
        logger.exception("Safeguarding flag %s recorded but not published",
                         alert_id)
    logger.info("Safeguarding flag %s raised for journey %s by %s (%s)",
                alert_id, journey_id, source_system, severity)
    return alert_id


def raise_flag_for_local_concern(
    system: str,
    local_student_id: str,
    *,
    category: str | None = None,
    severity: str = "medium",
    summary: str | None = None,
    source_ref: str | None = None,
    raised_by: str | None = None,
    db_path: str | None = None,
) -> str | None:
    """Resolve a local pupil/student id to its journey, then raise a flag.

    Returns the ``alert_id``, or ``None`` if the pupil isn't linked to a
    canonical journey yet (best-effort; never raises).
    """
    try:
        from education_system.shared.cross_system import person
        p = person.get_by_student(system, local_student_id, db_path=db_path)
        if p is None:
            logger.debug("No journey for %s/%s — safeguarding flag not "
                         "shared cross-system", system, local_student_id)
            return None
        return raise_flag(
            p.journey_id, source_system=system, category=category,
            severity=severity, summary=summary,
            source_ref=source_ref or local_student_id,
            raised_by=raised_by, db_path=db_path)
    except Exception:
        logger.exception("Cross-system safeguarding publish failed for "
                         "%s/%s (local concern still stands)",
                         system, local_student_id)
        return None


def get_alerts(journey_id: str, *, status: str | None = None,
               db_path: str | None = None) -> list[dict]:
    """Return all safeguarding alerts for a learner, newest first."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        sql = "SELECT * FROM safeguarding_alerts WHERE journey_id = ?"
        args: list = [journey_id]
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY created_at DESC, alert_id"
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


# ── Consumer ───────────────────────────────────────────────────────────────

def _handle_flag_raised(envelope: dict) -> None:
    """Idempotently ensure an alert raised elsewhere is recorded here.

    Because all systems share ``auth.db`` the row already exists; this is a
    hook point for per-system reactions and a safety net if a producer
    published without inserting.
    """
    payload = envelope.get("payload") or {}
    alert_id = payload.get("alert_id")
    journey_id = envelope.get("journey_id") or payload.get("journey_id")
    if not (alert_id and journey_id):
        return
    payload.setdefault("journey_id", journey_id)
    payload.setdefault("source_system", envelope.get("source_system", "?"))
    _insert_alert(payload, None)


_registered = False


def register_consumer() -> None:
    """Idempotently subscribe the safeguarding handler to the bus."""
    global _registered
    if _registered:
        return
    cross_system_bus.subscribe(
        cross_system_bus.EVENT_SAFEGUARDING_FLAG_RAISED,
        _handle_flag_raised,
        handler_name="shared.safeguarding.alert_service")
    _registered = True


__all__ = [
    "raise_flag",
    "raise_flag_for_local_concern",
    "get_alerts",
    "register_consumer",
]
