"""Progression statistics across all seven systems.

``JourneyService.get_cohort_flow`` (owned by the identity work) walks a
fixed primary → secondary → sixth form → university chain. That leaves out
nursery, FE college and apprenticeships, and it reads a conversion rate
into pairs nobody actually moves between. This module answers the same
questions from what the platform records rather than from an assumed
chain:

* **stage presence** — how many journeys ever reached each system, from the
  per-phase slots *and* the enrolment rows;
* **boundaries** — every (source, destination) pair seen in
  ``learner_transition``, with how many completed, were cancelled or are
  still in flight;
* **recorded moves** — the append-only ``student_journey_transitions``;
* **destination outcomes** — where learners went when they left, including
  destinations outside the platform (employment, an external provider).

Everything is read-only against the shared auth DB.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.paths import SYSTEM_LABELS, SYSTEM_ORDER
from education_system.platform.identity.auth.db import connect

logger = logging.getLogger(__name__)

_CLOSED = ("completed", "cancelled", "rejected")


def _label(system: str | None) -> str:
    if not system:
        return "(entry)"
    return SYSTEM_LABELS.get(system, system.replace("_", " ").title())


def _ensure(db_path: str | None) -> None:
    from education_system.platform.cross_system.enrolment_schema import (
        ensure_enrolment_schema,
    )
    ensure_enrolment_schema(db_path)


def stage_presence(*, year: str | None = None, db_path: str | None = None) -> list[dict]:
    """Journeys that reached each of the seven systems, and how many are there now."""
    from education_system.platform.cross_system.identity_service import SYSTEM_SLOTS
    _ensure(db_path)
    conn = connect(db_path)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(student_journey)")}
        where, params = "", []
        if year:
            where, params = "WHERE substr(j.created_at, 1, 4) = ?", [str(year)]
        out = []
        for system in SYSTEM_ORDER:
            pk, id_col = SYSTEM_SLOTS.get(system, (None, None))
            slot_terms = [f"j.{c} IS NOT NULL" for c in (pk, id_col) if c in cols]
            enrol_term = ("EXISTS (SELECT 1 FROM learner_enrolment e "
                          "WHERE e.journey_id = j.journey_id AND e.system = ?)")
            reached_expr = " OR ".join(slot_terms + [enrol_term])
            reached = conn.execute(
                f"SELECT COUNT(*) FROM student_journey j {where} "
                f"{'AND' if where else 'WHERE'} ({reached_expr})",  # nosec B608
                [*params, system]).fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(DISTINCT journey_id) FROM learner_enrolment "
                "WHERE system = ? AND status = 'active'", (system,)).fetchone()[0]
            out.append({"system": system, "label": _label(system),
                        "reached": reached, "active": active})
        return out
    finally:
        conn.close()


def boundaries(*, year: str | None = None, db_path: str | None = None) -> list[dict]:
    """Every observed (source, destination) pair with its outcome counts."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        where, params = "", []
        if year:
            where, params = "WHERE substr(initiated_at, 1, 4) = ?", [str(year)]
        rows = conn.execute(
            "SELECT source_system, destination_system, status, COUNT(*) AS n "
            f"FROM learner_transition {where} GROUP BY 1, 2, 3",  # nosec B608
            params).fetchall()
    finally:
        conn.close()
    pairs: dict[tuple[str | None, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["source_system"], r["destination_system"])
        entry = pairs.setdefault(key, {
            "source": key[0], "destination": key[1],
            "source_label": _label(key[0]), "destination_label": _label(key[1]),
            "total": 0, "completed": 0, "cancelled": 0, "in_progress": 0,
            "by_status": {},
        })
        entry["total"] += r["n"]
        entry["by_status"][r["status"]] = r["n"]
        if r["status"] == "completed":
            entry["completed"] += r["n"]
        elif r["status"] in ("cancelled", "rejected"):
            entry["cancelled"] += r["n"]
        else:
            entry["in_progress"] += r["n"]
    out = []
    for entry in pairs.values():
        decided = entry["completed"] + entry["cancelled"]
        entry["completion_rate"] = (
            round(100.0 * entry["completed"] / decided, 1) if decided else None)
        out.append(entry)
    out.sort(key=lambda e: -e["total"])
    return out


def recorded_moves(*, year: str | None = None, db_path: str | None = None) -> list[dict]:
    """``student_journey_transitions`` grouped by hop."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        where, params = "", []
        if year:
            where, params = "WHERE substr(occurred_at, 1, 4) = ?", [str(year)]
        rows = conn.execute(
            "SELECT from_system, to_system, COUNT(*) AS n "
            f"FROM student_journey_transitions {where} "  # nosec B608
            "GROUP BY 1, 2 ORDER BY n DESC", params).fetchall()
    finally:
        conn.close()
    return [{"from_system": r["from_system"], "to_system": r["to_system"],
             "from_label": _label(r["from_system"]), "to_label": _label(r["to_system"]),
             "count": r["n"]} for r in rows]


def journey_moves(journey_id: str, *, db_path: str | None = None) -> list[dict]:
    """One learner's recorded moves (``student_journey_transitions``), oldest first."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT from_system, to_system, reason, actor_user_id, occurred_at, notes "
            "FROM student_journey_transitions WHERE journey_id = ? "
            "ORDER BY occurred_at, id", (journey_id,)).fetchall()
    finally:
        conn.close()
    return [{**dict(r), "from_label": _label(r["from_system"]),
             "to_label": _label(r["to_system"])} for r in rows]


def cohort_flow_all_systems(*, year: str | None = None,
                            db_path: str | None = None) -> dict:
    """The all-systems replacement for ``get_cohort_flow``'s funnel."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM student_journey"
                             + (" WHERE substr(created_at, 1, 4) = ?" if year else ""),
                             [str(year)] if year else []).fetchone()[0]
        years = sorted({r[0] for r in conn.execute(
            "SELECT DISTINCT substr(created_at, 1, 4) FROM student_journey "
            "WHERE created_at IS NOT NULL") if r[0]}, reverse=True)
        current = [dict(r) for r in conn.execute(
            "SELECT current_system AS system, COUNT(*) AS count FROM student_journey "
            "GROUP BY current_system ORDER BY count DESC")]
    finally:
        conn.close()
    for row in current:
        row["label"] = _label(row["system"])
    return {
        "year": str(year) if year else None,
        "available_years": years,
        "total_journeys": total,
        "systems": list(SYSTEM_ORDER),
        "stage_presence": stage_presence(year=year, db_path=db_path),
        "boundaries": boundaries(year=year, db_path=db_path),
        "recorded_moves": recorded_moves(year=year, db_path=db_path),
        "current_distribution": current,
    }


def destination_outcomes(*, db_path: str | None = None) -> dict:
    """Where learners went. Prefers ``cross_system.destinations.outcome_summary``.

    The fallback counts completed transitions by destination — which covers
    moves to non-platform destinations, since the workflow records those
    too — and the ``destination.recorded`` events published so far.
    """
    try:
        from education_system.platform.cross_system import destinations
        summary_fn = getattr(destinations, "outcome_summary", None)
    except Exception:
        summary_fn = None
    if summary_fn is not None:
        from education_system.platform.features.analytics.transfer_monitor import (
            call_flexible,
        )
        try:
            return {"source": "destinations",
                    "summary": call_flexible(summary_fn, db_path=db_path)}
        except Exception:
            logger.warning("destinations.outcome_summary failed; using transitions",
                           exc_info=True)

    _ensure(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT source_system, destination_system, COUNT(*) AS n "
            "FROM learner_transition WHERE status = 'completed' "
            "GROUP BY 1, 2 ORDER BY n DESC").fetchall()
        recorded = conn.execute(
            "SELECT COUNT(*) FROM cross_system_event_outbox "
            "WHERE event_name = 'destination.recorded'").fetchone()[0]
    finally:
        conn.close()
    platform = set(SYSTEM_ORDER)
    return {
        "source": "transitions",
        "by_destination": [{
            "source": r["source_system"], "destination": r["destination_system"],
            "source_label": _label(r["source_system"]),
            "destination_label": _label(r["destination_system"]),
            "within_platform": r["destination_system"] in platform,
            "count": r["n"],
        } for r in rows],
        "recorded_destination_events": recorded,
    }


def progression_statistics(*, year: str | None = None,
                           db_path: str | None = None) -> dict:
    """One call for a report: flow, boundaries and outcomes."""
    flow = cohort_flow_all_systems(year=year, db_path=db_path)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **flow,
        "destination_outcomes": destination_outcomes(db_path=db_path),
    }


__all__ = [
    "boundaries",
    "cohort_flow_all_systems",
    "destination_outcomes",
    "journey_moves",
    "progression_statistics",
    "recorded_moves",
    "stage_presence",
]
