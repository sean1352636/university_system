"""The cross-system task list: what is waiting on this person, across systems.

Each board shows its own queue; nothing showed a superadmin (or a sixth-form
admissions officer who also covers FE) the whole of what was waiting on
them. This module assembles one list from four sources:

``transition``   a transfer at a step the user's system must act on
``checklist``    an outstanding checklist item on an open transfer
``overdue``      a transfer past its start date or idle too long
``duplicate``    a possible duplicate learner record (identity.merge only)
``dead_letter``  an event the bus gave up delivering (events.view only)

Filtering is by the cross-system permissions in ``role_manager``: a
transition task appears only if the user holds the permission its next
step needs, in the system that has to take it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from education_system.platform.identity.auth.role_manager import (
    PERM_EVENTS_VIEW,
    PERM_IDENTITY_MERGE,
    PERM_TRANSFER_VIEW,
    has_cross_system_permission,
    is_superadmin_systems,
    permitted_systems,
)

logger = logging.getLogger(__name__)

_PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


def _task(kind: str, title: str, *, priority: str = "normal", system: str | None = None,
          detail: str = "", action: str | None = None, **refs: Any) -> dict:
    return {"kind": kind, "title": title, "priority": priority, "system": system,
            "detail": detail, "action": action, **refs}


def list_tasks(user_systems: Iterable[Mapping] | None = None, *,
               db_path: str | None = None, stale_days: int = 14,
               limit: int = 500) -> list[dict]:
    """Tasks for a user (``user_systems`` = their ``[{system_key, role}]``).

    ``None`` means "every task" — used by the superadmin console, which
    already knows its user is a superadmin.
    """
    from education_system.platform.features.analytics import transfer_monitor as tm

    systems = list(user_systems) if user_systems is not None else None
    everything = systems is None or is_superadmin_systems(systems)

    def allowed(permission: str, system: str | None) -> bool:
        if everything:
            return True
        return bool(system) and has_cross_system_permission(systems, permission, system)

    tasks: list[dict] = []
    scope = None if everything else permitted_systems(systems, PERM_TRANSFER_VIEW)

    try:
        open_rows = tm.search_transitions(open_only=True, systems=scope, limit=2000,
                                          db_path=db_path)
    except Exception:
        logger.warning("Transition tasks unavailable", exc_info=True)
        open_rows = []

    for row in open_rows:
        awaiting = tm.AWAITING.get(row.get("status") or "")
        acting = row.get("acting_system")
        if awaiting and allowed(awaiting[2], acting):
            tasks.append(_task(
                "transition", f"{awaiting[1]}: {row['source_label']} to "
                f"{row['destination_label']}",
                system=acting, detail=f"Status {row['status']}",
                action="transfers", transition_id=row["transition_id"],
                journey_id=row["journey_id"]))
        try:
            checklist = tm.transition_checklist(row["transition_id"], db_path=db_path)
        except Exception:
            checklist = None
        for item in checklist or []:
            if tm.checklist_item_done(item):
                continue
            # ``owner`` is a party (source / destination / both), not a system.
            owner = item.get("owner") or "destination"
            owners = {"source": [row.get("source_system")],
                      "destination": [row["destination_system"]],
                      "both": [row.get("source_system"), row["destination_system"]],
                      }.get(owner, [row["destination_system"]])
            owner_system = next((s for s in owners if s and allowed(PERM_TRANSFER_VIEW, s)),
                                None)
            if owner_system is None:
                continue
            name = item.get("label") or item.get("key") or "checklist item"
            tasks.append(_task(
                "checklist", f"Outstanding: {name}", system=owner_system,
                detail=f"{row['source_label']} to {row['destination_label']}",
                action="transfers", transition_id=row["transition_id"],
                item=item.get("key")))

    try:
        for row in tm.overdue_transitions(stale_days=stale_days, systems=scope,
                                          db_path=db_path):
            tasks.append(_task(
                "overdue", f"Overdue transfer: {row['source_label']} to "
                f"{row['destination_label']}", priority="high",
                system=row.get("acting_system"), detail=row["overdue_reason"],
                action="transfers", transition_id=row["transition_id"],
                journey_id=row["journey_id"]))
    except Exception:
        logger.warning("Overdue transitions unavailable", exc_info=True)

    if everything or has_cross_system_permission(systems, PERM_IDENTITY_MERGE):
        try:
            candidates = tm.duplicate_candidates(db_path=db_path) or []
        except Exception:
            logger.warning("Duplicate candidates unavailable", exc_info=True)
            candidates = []
        for cand in candidates:
            reasons = "; ".join(cand.get("reasons") or [])
            tasks.append(_task(
                "duplicate", f"Possible duplicate learner (score {cand.get('score')})",
                detail=reasons, action="identity",
                journey_ids=[cand.get("journey_id"), cand.get("duplicate_id")]))

    if everything or has_cross_system_permission(systems, PERM_EVENTS_VIEW):
        try:
            from education_system.platform.integrations.external import cross_system_bus
            dead = cross_system_bus.list_failed_deliveries(
                exhausted_only=True, limit=200, db_path=db_path)
        except Exception:
            logger.warning("Dead letters unavailable", exc_info=True)
            dead = []
        for d in dead:
            if not everything and d.get("consumer_system") not in \
                    permitted_systems(systems, PERM_EVENTS_VIEW):
                continue
            tasks.append(_task(
                "dead_letter", f"Undelivered event: {d['event_name']}",
                priority="high", system=d.get("consumer_system"),
                detail=f"{d['consumer_handler']} after {d['attempts']} attempt(s)",
                action="events", event_id=d["event_id"],
                consumer_handler=d["consumer_handler"]))

    tasks.sort(key=lambda t: (_PRIORITY_ORDER.get(t["priority"], 3), t["kind"]))
    return tasks[:limit]


__all__ = ["list_tasks"]
