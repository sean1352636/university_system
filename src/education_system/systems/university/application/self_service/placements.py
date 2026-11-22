"""My Placement: the signed-in student's own placement record and hours log.

The Placement Hours tracker is the placement office's tool and lists every
student on placement. A student sees their own enrolment (employer,
supervisor, dates), the hours logged against it and how many are signed off
against the required total. Logging and signing off hours stays with the
placement office and supervisor, so this is read-only.

Functions take an open connection and only read.
"""

from __future__ import annotations

from education_system.systems.university.application.self_service.identity import table_columns
from education_system.systems.university.domains.progression.domain.placements.placement_service import (
    REQUIRED_HOURS,
)

PROFILE_FIELDS = ("cohort", "employer", "supervisor", "start_date", "end_date")


def my_placement(conn, student_id) -> dict:
    """``{"profile", "hours", "total", "signed_off", "required", "remaining"}``
    for *student_id*; ``profile`` is ``None`` when they are not on placement."""
    sid = str(student_id)
    profile = None
    if table_columns(conn, "placement_profiles"):
        row = conn.execute(
            "SELECT cohort, employer, supervisor, start_date, end_date "
            "FROM placement_profiles WHERE student_id = ?", (sid,)).fetchone()
        profile = dict(zip(PROFILE_FIELDS, row)) if row else None
    hours = []
    if table_columns(conn, "placement_hours_log"):
        cur = conn.execute(
            "SELECT log_date, hours, activity, supervisor_signoff, notes "
            "FROM placement_hours_log WHERE student_id = ? ORDER BY log_date DESC", (sid,))
        hours = [dict(zip(("log_date", "hours", "activity", "signed_off", "notes"), r))
                 for r in cur.fetchall()]
    total = round(sum(float(h["hours"] or 0) for h in hours), 2)
    signed = round(sum(float(h["hours"] or 0) for h in hours if h["signed_off"]), 2)
    return {"profile": profile, "hours": hours, "total": total, "signed_off": signed,
            "required": REQUIRED_HOURS, "remaining": max(0.0, round(REQUIRED_HOURS - signed, 2))}
