"""Attendance correlation adapter for the at-risk view.

Wraps ``services.attendance.records.get_student_attendance`` so the
risk view can show an attendance column without re-implementing the
SQL.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def fetch_overall_attendance(student_id: str | int) -> dict | None:
    """Return ``{total_sessions, attended, percentage}`` across modules.

    Aggregates per-module records returned by
    ``get_student_attendance`` into one number. Returns None if no
    attendance rows exist.
    """
    try:
        from education_system.university_system.modules.domain.academics.services.attendance.records import (
            get_student_attendance,
        )
    except ImportError as exc:
        logger.debug("attendance service unavailable: %s", exc)
        return None
    try:
        per_module = get_student_attendance(str(student_id)) or {}
    except Exception as exc:
        logger.warning("get_student_attendance failed for %s: %s", student_id, exc)
        return None
    if not per_module:
        return None
    total = sum(v.get("total_sessions", 0) for v in per_module.values())
    attended = sum(v.get("attended", 0) for v in per_module.values())
    pct = (attended / total * 100.0) if total else 0.0
    return {
        "total_sessions": total,
        "attended": attended,
        "percentage": round(pct, 1),
    }
