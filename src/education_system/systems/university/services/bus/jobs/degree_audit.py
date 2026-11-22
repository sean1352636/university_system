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
from education_system.systems.university.services.bus.integration.publishing import _set_kpi, log_and_publish

def run_degree_audit_sweep(*, cohort_year: int) -> dict[str, Any]:
    """Sweep degree audits for ``cohort_year`` and refresh the graduation KPI.

    Public entry point — call from the Course Management GUI's "Run audit"
    button or a scheduled job. Reads ``semester_plans`` starting in that year
    + ``planned_courses``, computes the on-track ratio, writes it into kpi_metrics under
    "Graduation Forecast", and returns the result for display.
    """
    on_track = 0
    total = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='semester_plans'"
            ).fetchone()
            if not tbl:
                return {"cohort_year": cohort_year, "on_track": 0, "total": 0, "rate": None}
            rows = conn.execute(
                "SELECT plan_id, student_id FROM semester_plans "
                "WHERE start_semester LIKE ?",
                (f"%{int(cohort_year)}%",),
            ).fetchall()
            total = len(rows)
            for r in rows:
                if _plan_is_on_track(conn, r[0]):
                    on_track += 1
    except Exception as exc:
        logger.warning("degree audit sweep failed: %s", exc)
        return {"cohort_year": cohort_year, "on_track": 0, "total": 0, "rate": None}

    rate = (on_track / total) if total else None
    if rate is not None:
        _set_kpi(name="Graduation Forecast", category="graduation", value=rate * 100)
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="course_management",
        action="degree_audit_swept",
        cohort_year=cohort_year,
        on_track=on_track,
        total=total,
        rate=rate,
    )
    return {"cohort_year": cohort_year, "on_track": on_track,
            "total": total, "rate": rate}

def _plan_is_on_track(conn: Any, plan_id: int) -> bool:
    try:
        row = conn.execute(
            # A planned course counts once the student is on it or has a mark
            # for it (marks live in module_grades, not student_modules).
            "SELECT COUNT(*) FROM planned_courses pc "
            "JOIN semester_plans sp ON sp.plan_id = pc.plan_id "
            "WHERE pc.plan_id = ? AND NOT EXISTS (SELECT 1 FROM student_modules sm "
            "WHERE sm.student_id = sp.student_id AND sm.module_code = pc.course_id "
            "AND LOWER(sm.status) IN ('enrolled', 'completed', 'complete', 'passed', 'pass', 'awarded')) "
            "AND NOT EXISTS (SELECT 1 FROM module_grades mg "
            "WHERE mg.student_id = sp.student_id AND mg.module_code = pc.course_id)",
            (plan_id,),
        ).fetchone()
        return bool(row and row[0] == 0)
    except Exception:
        return False
