"""My Attendance: one student's own registers, read through the same rules the
attendance office uses.

Figures come from :mod:`application.attendance.registers` (sessions defined
by the timetable, so a session with no register is shown as such rather than
silently dropped) and self-certifications from
:mod:`application.attendance.engagement`. For a sponsored (Student route)
student the page also shows the run of missed contact points against the
UKVI reporting limit, because that is the number the university reports on.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.attendance import engagement, registers
from education_system.systems.university.application.self_service.identity import (
    SelfServiceError,
    table_columns,
)

OUTCOMES = ("present", "late", "excused", "absent", "no_register")


def _rate(present: int, late: int, absent: int):
    counted = present + late + absent
    return round((present + late) / counted * 100, 1) if counted else None


def by_module(sessions: list[dict]) -> list[dict]:
    """Per-module counts and attendance rate, in module-code order."""
    rows: dict[str, dict] = {}
    for s in sessions:
        code = s.get("module_code") or ""
        row = rows.setdefault(code, {"module_code": code, **{k: 0 for k in OUTCOMES}})
        outcome = s.get("outcome")
        if outcome in OUTCOMES:
            row[outcome] += 1
    for row in rows.values():
        row["expected"] = sum(row[k] for k in OUTCOMES)
        row["attendance_pct"] = _rate(row["present"], row["late"], row["absent"])
    return [rows[k] for k in sorted(rows)]


def _sponsored(conn, student_id) -> bool:
    if not table_columns(conn, "visa_records"):
        return False
    return str(student_id) in {str(s) for s in engagement.sponsored_students(conn)}


def ukvi_position(conn, student_id, sessions: list[dict]) -> dict | None:
    """Missed-contact-point run against the reporting limit, for a sponsored
    student only (``None`` otherwise)."""
    if not _sponsored(conn, student_id):
        return None
    limit = registers.setting(conn, "ukvi_missed_contact_points", 10)
    missed = registers.consecutive_missed(sessions)
    return {"limit": limit, "consecutive_missed": missed,
            "last_engaged": registers.last_engaged(sessions),
            "at_risk": missed >= max(1, limit - 2)}


def my_attendance(conn, student_id, start: date | None = None, end: date | None = None) -> dict:
    """Everything the My Attendance page shows, for *student_id* only."""
    if not student_id:
        raise SelfServiceError("No student record is linked to this account.")
    if start is None or end is None:
        start, end = registers.default_window(conn)
    sessions = registers.student_sessions(conn, student_id, start, end)
    summary = registers.student_summary(conn, student_id, start, end)
    return {
        "student_id": str(student_id),
        "window": (start.isoformat(), end.isoformat()),
        "summary": summary,
        "modules": by_module(sessions),
        "sessions": sessions,
        "self_certifications": engagement.self_certifications(conn, student_id),
        "ukvi": ukvi_position(conn, student_id, sessions),
    }


def certify_own_absence(conn, student_id, start: date, end: date, reason: str) -> int:
    """Self-certify a short illness for *student_id* (the engagement rules
    apply: maximum length, yearly allowance, never over an exam). The caller
    commits."""
    if not student_id:
        raise SelfServiceError("No student record is linked to this account.")
    if not (reason or "").strip():
        raise SelfServiceError("Please give a reason for the absence.")
    return engagement.self_certify(conn, student_id, start, end, reason.strip())
