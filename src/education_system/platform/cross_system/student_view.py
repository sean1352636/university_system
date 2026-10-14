"""The single student view — one learner's whole history, every system.

Given a canonical ``journey_id`` this returns a read-only, nested snapshot
of everything the platform knows about that person, in ``SYSTEM_ORDER``::

    nursery → primary → secondary → ┬ sixth-form college ┬ → university
                                    ├ FE College         ┤
                                    └ apprenticeships    ┘

The post-16 row is a fork, not a queue, and a learner may appear in more
than one branch of it at once — a degree apprentice holds a university
and an apprenticeships record simultaneously. The view shows every system
the learner has a record in rather than picking a winner.

Since the Learner 360 landed this module is a compatibility face over
:func:`learner_360.build_learner_360`: :func:`build_overview` keeps its
signature and its ``journey_id / found / person / phases / transitions``
keys, and adds the full Learner 360 under ``learner_360``. ``phases`` now
comes from the enrolment history rather than the per-phase slots, so a
learner's second spell in a phase is a second entry instead of being
overwritten — and nursery, primary and sixth-form phases carry attendance.

Everything here is defensive and read-only: a missing database, table or
column degrades to a partial view rather than an error, so the overview is
safe to call from an API handler or a dashboard.
"""

from __future__ import annotations

import logging

from education_system.platform.cross_system import identity_service, learner_360

logger = logging.getLogger(__name__)

# Kept under their old names for callers that reached into this module.
_EXTRACTORS = learner_360.PHASE_EXTRACTORS
_attendance_summary = learner_360._attendance_summary
_connect = learner_360._connect


def build_overview(journey_id: str, *, db_paths: dict | None = None,
                   auth_db: str | None = None) -> dict:
    """Aggregate a learner's whole cross-system history into one dict.

    ``db_paths`` / ``auth_db`` override the canonical registry locations
    (used by tests); production callers pass neither. The caller is
    trusted (no viewer role), exactly as before; screens that know who is
    looking should call :func:`learner_360.build_learner_360` with
    ``viewer_role`` instead.
    """
    view = learner_360.build_learner_360(journey_id, db_paths=db_paths,
                                         auth_db=auth_db)
    if not view.get("found"):
        return {"journey_id": journey_id, "found": False}
    o = view["overview"]
    phases = []
    for rec in view.get("records") or []:
        phase = {"system": rec["system"], "label": rec["label"],
                 "student_id": rec["student_id"],
                 "record": rec.get("record") or {}}
        for key in ("attendance", "results", "enrolment_ids", "statuses"):
            if rec.get(key):
                phase[key] = rec[key]
        phases.append(phase)
    return {
        "journey_id": view["journey_id"],
        "found": True,
        "person": {
            "legal_first_name": o.get("legal_first_name"),
            "legal_last_name": o.get("legal_last_name"),
            "date_of_birth": o.get("date_of_birth"),
            "nhs_number": o.get("nhs_number"),
            "upn": o.get("upn"),
            "full_name": o.get("full_name"),
            "current_system": o.get("current_system"),
            "status": o.get("status"),
        },
        "phases": phases,
        "transitions": view.get("legacy_transitions") or [],
        "learner_360": view,
    }


def build_overview_for_student(system: str, student_id: str, *,
                               db_paths: dict | None = None,
                               auth_db: str | None = None) -> dict:
    """Convenience: resolve the journey from a local id, then aggregate."""
    row = identity_service.find_by_student(system, student_id,
                                           db_path=auth_db)
    if row is None:
        return {"found": False, "system": system, "student_id": student_id}
    return build_overview(row["journey_id"], db_paths=db_paths,
                          auth_db=auth_db)


def format_overview_text(overview: dict) -> str:
    """Render an overview as a compact plain-text summary (CLI / logs)."""
    if not overview.get("found"):
        return f"No journey found ({overview.get('journey_id', '?')})"
    p = overview["person"]
    lines = [
        f"{p.get('full_name', '?')}  (journey {overview['journey_id']})",
        f"  DOB {p.get('date_of_birth') or '—'}   "
        f"UPN {p.get('upn') or '—'}   NHS {p.get('nhs_number') or '—'}",
        f"  Currently: {p.get('current_system') or '—'} "
        f"({p.get('status') or '—'})",
        "  Phases:",
    ]
    for ph in overview["phases"]:
        rec = ph.get("record", {})
        bits = [f"{ph['label']} [{ph['student_id']}]"]
        if rec.get("year_group"):
            bits.append(f"Y{rec['year_group']}")
        if rec.get("course"):
            bits.append(str(rec["course"]))
        if rec.get("status"):
            bits.append(str(rec["status"]))
        att = ph.get("attendance")
        if att:
            bits.append(f"attendance n={att['total']}")
        res = ph.get("results")
        if res:
            bits.append(f"{len(res)} result(s)")
        lines.append("    - " + "  ".join(bits))
    if overview["transitions"]:
        lines.append("  Transitions:")
        for t in overview["transitions"]:
            lines.append(
                f"    {t.get('occurred_at', '?')}  "
                f"{t.get('from_system') or '—'} → {t.get('to_system')}")
    return "\n".join(lines)


__all__ = [
    "build_overview",
    "build_overview_for_student",
    "format_overview_text",
]
