"""Cross-system safeguarding alerts — a flag follows the learner.

A safeguarding concern raised in one system is recorded against the
canonical ``journey_id`` in the shared ``safeguarding_alerts`` table (in
``auth.db``), so *every* system can see it: a flag on a secondary-school
pupil is visible the moment they progress into sixth form. A
``safeguarding.flag.raised`` event is also published on the durable bus so
live systems are actively notified (drained in real time by the
:mod:`bus_drainer`), not just on next launch.

The event goes only to the systems that hold an open enrolment for the
learner. It used to be broadcast to every system, which meant a nursery
was told about a concern raised at a university about someone it last
taught fifteen years ago. The shared table still makes the flag readable
wherever the learner turns up later.

Layers:

* :func:`raise_flag` / :func:`raise_flag_for_local_concern` — producers.
* :func:`get_alerts` — any system reads a learner's flags.
* :func:`redeem_safeguarding_reference` — a designated safeguarding lead
  resolves the ``safeguarding_reference`` a transition handover carries.
* :func:`register_consumer` — subscribes an idempotent handler that
  ensures an alert raised elsewhere is present locally (a hook point for
  per-system reactions; the shared table already makes it visible).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Mapping
from typing import Any

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

_initialised: set[str] = set()

_SOURCE_MODULE = "shared.safeguarding.alert_service"


class SafeguardingAccessError(PermissionError):
    """The caller may not redeem this safeguarding reference."""


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


def holding_systems(journey_id: str, *, exclude: str | None = None,
                    db_path: str | None = None) -> list[str]:
    """Platform systems that currently hold the learner.

    These are the systems with an *open* enrolment (applicant through
    active), so a destination preparing to receive the learner is included.
    A journey with no enrolment rows at all predates the enrolment model,
    and falls back to its populated journey slots. Never raises: an empty
    list means nobody else to notify.
    """
    try:
        from education_system.platform.cross_system import (
            enrolments,
            identity_service,
        )
        platform_systems = set(identity_service.SYSTEM_SLOTS)
        rows = enrolments.list_enrolments(journey_id, db_path=db_path)
        held: list[str] = []
        if rows:
            open_rows = enrolments.open_enrolments(journey_id,
                                                   db_path=db_path)
            for e in open_rows:
                system = e.get("system")
                if system in platform_systems and system not in held:
                    held.append(system)
        else:
            journey = identity_service.get(journey_id, db_path=db_path) or {}
            for system, (_pk, id_col) in identity_service.SYSTEM_SLOTS.items():
                if journey.get(id_col):
                    held.append(system)
    except Exception:
        logger.exception("Could not work out which systems hold journey %s",
                         journey_id)
        return []
    return [s for s in held if s != exclude]


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
    """Record a safeguarding flag against ``journey_id`` and notify the
    systems that hold the learner.

    Returns the new ``alert_id``. The flag is immediately visible to every
    system via :func:`get_alerts`. One bus event is addressed to each
    system with an open enrolment, other than the one raising it.
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
    targets = holding_systems(journey_id, exclude=source_system,
                              db_path=db_path)
    # Payload carries the alert fields minus the keys that are explicit
    # publish_cross_system params (journey_id / source_system).
    payload: dict[str, Any] = {k: v for k, v in row.items()
                               if k not in ("journey_id", "source_system")}
    for target in targets:
        try:
            cross_system_bus.publish_cross_system(
                cross_system_bus.EVENT_SAFEGUARDING_FLAG_RAISED,
                source_system=source_system,
                source_module=_SOURCE_MODULE,
                journey_id=journey_id, target_system=target,
                idempotency_key=f"safeguarding.flag.raised:{alert_id}:{target}",
                db_path=db_path, **payload)
        except Exception:
            logger.exception("Safeguarding flag %s recorded but not "
                             "published to %s", alert_id, target)
    logger.info("Safeguarding flag %s raised for journey %s by %s (%s); "
                "notified %s", alert_id, journey_id, source_system, severity,
                ", ".join(targets) or "no other system")
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
        from education_system.platform.cross_system import person
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


# ── Redeeming a handover's safeguarding reference ─────────────────────────

def _principal(dsl_user: Any) -> tuple[str, str, str | None, Any]:
    """(actor_id, role, system, raw id) from a user mapping or object."""
    def get(key: str) -> Any:
        if isinstance(dsl_user, Mapping):
            return dsl_user.get(key)
        return getattr(dsl_user, key, None)

    uid = get("user_id")
    if uid is None:
        uid = get("id")
    role = get("role")
    if not role:
        roles = get("roles") or ()
        role = next(iter(roles), "") if not isinstance(roles, str) else roles
    system = get("system") or get("system_key")
    actor_id = str(uid if uid is not None else get("username") or "unknown")
    return actor_id, str(role or "").strip().lower(), system, uid


def _audit(action: str, *, reference: str, actor: Any, details: dict,
           severity: str = "info", db_path: str | None) -> None:
    # The helper lives with the transfer workflow, which owns the rule for
    # finding the audit DB beside the auth DB in use. It is imported lazily
    # so importing governance never loads the cross-system layer.
    from education_system.platform.cross_system.transitions import (
        audit_cross_system,
    )
    audit_cross_system(action, target_type="safeguarding_reference",
                       target_id=reference, actor=actor, details=details,
                       severity=severity, db_path=db_path)


def redeem_safeguarding_reference(reference: str, *, dsl_user: Any,
                                  purpose: str,
                                  db_path: str | None = None
                                  ) -> dict[str, Any]:
    """Resolve the ``safeguarding_reference`` carried by a handover.

    A handover never carries safeguarding detail. It carries this opaque
    reference, and until now nothing could turn the reference back into
    anything. This resolves it, for a designated safeguarding lead only, to:
    the transition(s) whose approved handover carried it, the learner's
    journey, and that learner's safeguarding alerts (the reference may also
    be an ``alert_id`` or an alert's ``source_ref``).

    ``dsl_user`` is a mapping or object with ``id``/``user_id``, ``role``
    and optionally ``system``. The role must pass the ``safeguarding``
    policy in ``sensitive_access`` for ``purpose`` (``dsl``,
    ``safeguarding`` or ``superadmin``, or an approved break-glass grant).
    A DSL whose ``system`` is given must be a party to the transition or
    hold the learner, unless they are ``superadmin``.

    Every attempt is audited as ``SAFEGUARDING_VIEW``. A redemption from a
    different system than the one that issued the reference is also audited
    as ``CROSS_SYSTEM_ACCESS``. Raises :class:`SafeguardingAccessError` when
    refused, and ``ValueError`` if the reference is empty or matches more
    than one learner.
    """
    ref = (reference or "").strip()
    if not ref:
        raise ValueError("A safeguarding reference is required")
    actor_id, role, system, raw_id = _principal(dsl_user)
    _ensure(db_path)
    from education_system.platform.cross_system.enrolment_schema import (
        ensure_enrolment_schema,
    )
    from education_system.platform.governance.security import (
        sensitive_access,
    )
    ensure_enrolment_schema(db_path)

    conn = connect(db_path)
    try:
        try:
            transitions = [dict(r) for r in conn.execute(
                """SELECT transition_id, journey_id, source_system,
                          destination_system, status, handover_approved_at
                     FROM learner_transition
                    WHERE handover_json IS NOT NULL
                      AND json_valid(handover_json)
                      AND json_extract(handover_json,
                                       '$.safeguarding_reference') = ?
                    ORDER BY initiated_at""", (ref,)).fetchall()]
        except sqlite3.OperationalError:
            # A SQLite without JSON1 cannot search the payloads, so fall
            # back to reading them.
            import json as _json
            transitions = []
            for r in conn.execute(
                    "SELECT transition_id, journey_id, source_system, "
                    "destination_system, status, handover_approved_at, "
                    "handover_json FROM learner_transition "
                    "WHERE handover_json IS NOT NULL").fetchall():
                try:
                    body = _json.loads(r["handover_json"])
                except (TypeError, ValueError):
                    continue
                if isinstance(body, dict) and str(
                        body.get("safeguarding_reference")) == ref:
                    row = dict(r)
                    row.pop("handover_json", None)
                    transitions.append(row)
        direct_alerts = [dict(r) for r in conn.execute(
            "SELECT * FROM safeguarding_alerts WHERE alert_id = ? "
            "OR source_ref = ?", (ref, ref)).fetchall()]
    finally:
        conn.close()

    journeys = ({t["journey_id"] for t in transitions}
                | {a["journey_id"] for a in direct_alerts})
    base = {"purpose": purpose, "dsl_role": role, "dsl_system": system,
            "transition_ids": [t["transition_id"] for t in transitions]}
    if len(journeys) > 1:
        _audit("SAFEGUARDING_VIEW", reference=ref, actor=raw_id,
               severity="warning", db_path=db_path,
               details={**base, "decision": "refused",
                        "reason": "reference matches more than one learner"})
        raise ValueError(
            "This safeguarding reference matches more than one learner; "
            "resolve it DSL-to-DSL with the issuing setting")
    journey_id = next(iter(journeys), None)

    issuers = ({t["source_system"] for t in transitions if t["source_system"]}
               | {a["source_system"] for a in direct_alerts})
    parties = issuers | {t["destination_system"] for t in transitions}

    decision = sensitive_access.authorize_sensitive_fields(
        actor_id=actor_id, actor_role=role or "unknown",
        domain="safeguarding", subject_id=journey_id,
        fields={"safeguarding_reference"}, purpose=purpose or "",
        db_path=db_path)
    refusal: str | None = None if decision.allowed else decision.reason
    if (refusal is None and system and role != "superadmin" and journey_id
            and system not in parties
            and system not in holding_systems(journey_id, db_path=db_path)):
        refusal = (f"{system} is not a party to this handover and does not "
                   f"hold the learner")
    if refusal is not None:
        _audit("SAFEGUARDING_VIEW", reference=ref, actor=raw_id,
               severity="warning", db_path=db_path,
               details={**base, "journey_id": journey_id,
                        "decision": "denied", "reason": refusal})
        raise SafeguardingAccessError(
            f"Safeguarding reference not redeemed: {refusal}")

    alerts = get_alerts(journey_id, db_path=db_path) if journey_id else []
    result = {
        "reference": ref,
        "resolved": journey_id is not None,
        "journey_id": journey_id,
        "transitions": transitions,
        "alerts": alerts,
        "issued_by": sorted(issuers),
        "redeemed_by": actor_id,
        "purpose": purpose,
    }
    details = {**base, "journey_id": journey_id, "decision": "allowed",
               "alert_ids": [a["alert_id"] for a in alerts],
               "grant_id": decision.grant_id}
    _audit("SAFEGUARDING_VIEW", reference=ref, actor=raw_id,
           db_path=db_path, details=details)
    if system and issuers and system not in issuers:
        _audit("CROSS_SYSTEM_ACCESS", reference=ref, actor=raw_id,
               db_path=db_path, details=details)
    logger.info("Safeguarding reference %s redeemed by %s (%s) for %s",
                ref, actor_id, role, purpose)
    return result


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
        handler_name=_SOURCE_MODULE)
    _registered = True


__all__ = [
    "SafeguardingAccessError",
    "raise_flag",
    "raise_flag_for_local_concern",
    "get_alerts",
    "holding_systems",
    "redeem_safeguarding_reference",
    "register_consumer",
]
