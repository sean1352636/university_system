"""Attendance adapter — wraps services/attendance for assignment-screen use.

Two helpers:
  * ``fetch_module_attendance`` returns the student's attendance summary
    for the assignment's module (percentage, attended, total).
  * ``fetch_attendance_warning`` derives a one-line warning to surface
    next to a submission/grade entry when the student is at risk
    (default threshold 75%).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

LOW_ATTENDANCE_THRESHOLD = 75.0


def fetch_module_attendance(student_id: str | int, module_code: str) -> dict | None:
    """Return ``{total_sessions, attended, percentage}`` for the module.

    Returns ``None`` if attendance tracking has no data for that pair.
    Delegates to ``services.attendance.records.get_student_attendance``
    so any future schema changes there flow through automatically.
    """
    try:
        from education_system.university_system.modules.domain.academics.services.attendance.records import (
            get_student_attendance,
        )
    except ImportError as exc:
        logger.debug("attendance service unavailable: %s", exc)
        return None

    try:
        stats = get_student_attendance(str(student_id), module_code) or {}
    except Exception as exc:
        logger.warning(
            "get_student_attendance failed for %s/%s: %s",
            student_id, module_code, exc,
        )
        return None

    record = stats.get(module_code)
    if not record:
        return None
    return {
        "total_sessions": record.get("total_sessions", 0),
        "attended": record.get("attended", 0),
        "percentage": float(record.get("percentage") or 0.0),
    }


def fetch_attendance_warning(
    student_id: str | int,
    module_code: str,
    *,
    threshold: float = LOW_ATTENDANCE_THRESHOLD,
) -> str | None:
    """Return a short warning string when attendance is below ``threshold``.

    Returns ``None`` when attendance is healthy or unknown — callers can
    use truthiness to decide whether to render the badge.
    """
    summary = fetch_module_attendance(student_id, module_code)
    if not summary:
        return None
    pct = summary["percentage"]
    if pct >= threshold:
        return None
    return (
        f"Attendance for {module_code}: "
        f"{summary['attended']}/{summary['total_sessions']} "
        f"sessions ({pct:.0f}%) — below {threshold:.0f}% threshold."
    )
