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

_COHORT_RISK_THRESHOLD = 65.0

def sweep_cohort_attendance_risk(*, threshold_pct: float = _COHORT_RISK_THRESHOLD,
                                  weeks: int = 3) -> dict[str, int]:
    """Scan recent attendance per module; raise risk for cohorts below threshold.

    Reads ``attendance_records`` over the last ``weeks`` weeks,
    computes the cohort attendance % per module_code, and routes
    each below-threshold module through
    ``attendance_bus.flag_module_attendance_risk`` (which writes
    into the canonical ``risks`` table via risk_bus).

    Returns ``{"checked": N, "raised": M}``. Idempotent — risk_bus
    keys on ``reference_id='module:<code>'`` so a second sweep on
    the same window won't double-raise.
    """
    checked = 0
    raised = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='attendance_records'"
            ).fetchone()
            if not tbl:
                return {"checked": 0, "raised": 0}
            rows = conn.execute(
                "SELECT module_code, "
                "       SUM(CASE WHEN LOWER(status) IN ('present','late','excused') "
                "                THEN 1 ELSE 0 END) AS attended, "
                "       COUNT(*) AS total "
                "FROM attendance_records "
                "WHERE julianday('now') - julianday(date) <= ? "
                "GROUP BY module_code",
                (int(weeks * 7),),
            ).fetchall()
    except Exception as exc:
        logger.warning("sweep_cohort_attendance_risk query failed: %s", exc)
        return {"checked": 0, "raised": 0}

    try:
        from education_system.systems.university.services.bus.attendance_bus import (
            flag_module_attendance_risk,
        )
    except Exception:
        return {"checked": 0, "raised": 0}

    for r in rows:
        d = dict(r)
        if not d["total"]:
            continue
        checked += 1
        pct = float(d["attended"] or 0) / float(d["total"]) * 100.0
        if pct < threshold_pct:
            try:
                rid = flag_module_attendance_risk(
                    d["module_code"],
                    cohort_pct=pct, weeks_observed=weeks,
                )
                if rid:
                    raised += 1
            except Exception as exc:
                logger.debug("flag_module_attendance_risk failed for %s: %s",
                             d["module_code"], exc)

    return {"checked": checked, "raised": raised}
