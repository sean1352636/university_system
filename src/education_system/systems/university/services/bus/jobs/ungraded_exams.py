"""Focused components extracted from the legacy integration bus."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED,
    EVENT_CERT_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
    publish,
    subscribe,
)

logger = logging.getLogger(__name__)

def sweep_ungraded_exams(*, reminder_after_days: int = 7,
                         hold_after_days: int = 14) -> dict[str, int]:
    """Daily sweep over ``exam_portal_attempts``.

    - Attempts submitted >= reminder_after_days ago and still not
      graded → email the instructor.
    - Attempts submitted >= hold_after_days ago and still not graded
      → place a finance hold against the student so transcripts
      can't release.
    Returns ``{"reminded": N, "held": M}``.
    """
    reminded = 0
    held = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_attempts'"
            ).fetchone()
            if not tbl:
                return {"reminded": 0, "held": 0}

            stale = conn.execute(
                "SELECT a.id, a.student_id, a.submitted_at, "
                "       e.id as exam_id, e.title, e.created_by, e.module_code "
                "FROM exam_portal_attempts a "
                "JOIN exam_portal_exams e ON e.id = a.exam_id "
                "WHERE a.graded_at IS NULL "
                "  AND a.submitted_at IS NOT NULL "
                "  AND julianday('now') - julianday(a.submitted_at) >= ?",
                (int(reminder_after_days),),
            ).fetchall()
    except Exception as exc:
        logger.warning("sweep_ungraded_exams query failed: %s", exc)
        return {"reminded": 0, "held": 0}

    # Group by instructor for one email per instructor per sweep.
    by_instructor: dict[str, list[dict[str, Any]]] = {}
    for r in stale:
        d = dict(r)
        by_instructor.setdefault(str(d.get("created_by") or "admin"), []).append(d)

    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        for instructor_id, attempts in by_instructor.items():
            oldest = min(a.get("submitted_at") or "" for a in attempts)
            send_templated(
                instructor_id, "exam.pending_grade",
                {
                    "exam_title": attempts[0].get("title") or "exam",
                    "count": len(attempts),
                    "oldest_submitted": oldest,
                },
                related_to=f"exam:{attempts[0].get('exam_id')}",
                force=True,
            )
            reminded += len(attempts)
    except Exception as exc:
        logger.debug("ungraded sweep email failed: %s", exc)

    # Holds for older still-ungraded attempts.
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            place_hold,
        )
        for r in stale:
            d = dict(r)
            sub = d.get("submitted_at") or ""
            try:
                age_days = (datetime.now() - datetime.strptime(
                    sub[:19], "%Y-%m-%d %H:%M:%S")).days
            except Exception:
                age_days = 0
            if age_days >= hold_after_days and d.get("student_id"):
                place_hold(
                    d["student_id"],
                    reason=f"Exam '{d.get('title')}' awaiting grading",
                    source="exam_management",
                    reference_id=f"attempt:{d.get('id')}",
                )
                held += 1
    except Exception as exc:
        logger.debug("ungraded sweep hold failed: %s", exc)

    return {"reminded": reminded, "held": held}
