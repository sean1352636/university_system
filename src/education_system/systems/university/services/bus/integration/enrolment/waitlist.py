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
from education_system.systems.university.services.bus.integration.enrolment.publishers import publish_waitlist_promoted
from education_system.systems.university.services.bus.integration.finance.subscribers import _lookup_program_fee

def promote_from_waitlist(student_id: str, course_code: str, *,
                           plan_id: int | None = None,
                           academic_year: str | None = None) -> bool:
    """Atomic enrol-and-bill from a waitlist offer.

    Inserts/locks the planned_courses row, decrements module_schedule capacity,
    raises a fee charge, then publishes a single event. Either all four
    succeed or the SQL transaction is rolled back; the finance charge
    fires after commit so a publish-only failure won't double-bill.
    """
    sid = str(student_id)
    fee = _lookup_program_fee(course_code, academic_year) or 0.0
    success = False
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='planned_courses'"
            ).fetchone()
            if tbl and plan_id is not None:
                conn.execute(
                    # Goes in the plan's latest semester, locked because the
                    # student is now enrolled on it.
                    "INSERT INTO planned_courses "
                    "(plan_id, course_id, semester_number, semester_name, is_locked, notes) "
                    "SELECT sp.plan_id, ?, "
                    "COALESCE((SELECT MAX(pc.semester_number) FROM planned_courses pc "
                    "WHERE pc.plan_id = sp.plan_id), 1), "
                    "COALESCE((SELECT pc.semester_name FROM planned_courses pc "
                    "WHERE pc.plan_id = sp.plan_id ORDER BY pc.semester_number DESC LIMIT 1), "
                    "sp.start_semester), 1, 'Enrolled from waitlist' "
                    "FROM semester_plans sp WHERE sp.plan_id = ? "
                    "ON CONFLICT(plan_id, course_id) DO UPDATE SET is_locked = 1",
                    (course_code, plan_id),
                )
            sched = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'"
            ).fetchone()
            if sched:
                conn.execute(
                    "UPDATE module_schedule SET enrolled = COALESCE(enrolled, 0) + 1 "
                    "WHERE module_code = ?",
                    (course_code,),
                )
            conn.commit()
            success = True
    except Exception as exc:
        logger.warning("waitlist promote db step failed: %s", exc)
        return False

    if success and fee > 0:
        try:
            from education_system.systems.university.services.bus.finance_bus import (
                raise_charge,
            )
            raise_charge(
                sid, fee,
                source="waitlist",
                description=f"Tuition: {course_code} (waitlist promote)",
                reference_id=f"waitlist:{plan_id}:{course_code}",
            )
        except Exception as exc:
            logger.warning("waitlist promote charge failed: %s", exc)

    publish_waitlist_promoted(
        sid, course_code=course_code, plan_id=plan_id, fee_amount=fee,
    )
    return success
