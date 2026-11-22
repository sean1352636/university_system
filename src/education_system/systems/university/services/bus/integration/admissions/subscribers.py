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
from education_system.systems.university.services.bus.integration.finance.subscribers import _lookup_program_fee
from education_system.systems.university.services.bus.integration.publishing import _bump_kpi, _set_kpi

def _on_clearing_accepted(**payload: Any) -> None:
    if payload.get("action") != "clearing_accepted":
        return
    course_code = payload.get("course_code")
    student_ref = payload.get("student_ref") or ""
    year = payload.get("academic_year")

    # Module Scheduling: drop one seat from any matching module_schedule row.
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'"
            ).fetchone()
            if tbl:
                conn.execute(
                    "UPDATE module_schedule "
                    "SET enrolled = COALESCE(enrolled, 0) + 1 "
                    "WHERE module_code = ?",
                    (course_code,),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("clearing→scheduling capacity update failed: %s", exc)

    # Finance: raise the program fee charge if we have a real student_id.
    if student_ref and not student_ref.startswith("clearing:"):
        try:
            from education_system.systems.university.services.bus.finance_bus import (
                raise_charge,
            )
            fee = _lookup_program_fee(course_code, year)
            if fee and fee > 0:
                raise_charge(
                    student_ref, fee,
                    source="clearing",
                    description=f"Tuition: {course_code} {year}",
                    reference_id=f"clearing:{payload.get('application_id')}",
                )
        except Exception as exc:
            logger.debug("clearing→finance charge failed: %s", exc)

    # KPI: bump enrolment counter for the year.
    _bump_kpi(category="enrollment", increment=1)

def _on_adjustment_approved(**payload: Any) -> None:
    if payload.get("action") != "adjustment_approved":
        return
    student_id = payload.get("student_id")
    from_course = payload.get("from_course")
    to_course = payload.get("to_course")
    request_id = payload.get("request_id")
    if not (student_id and from_course and to_course):
        return

    # Course Management: swap the entry in the student's semester plans.
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='planned_courses'"
            ).fetchone()
            if tbl:
                conn.execute(
                    "UPDATE OR IGNORE planned_courses SET course_id = ? "
                    "WHERE plan_id IN (SELECT plan_id FROM semester_plans WHERE student_id = ?) "
                    "AND course_id = ?",
                    (to_course, str(student_id), from_course),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("adjustment→plan swap failed: %s", exc)

    # Finance: credit the dropped course, debit the new one (idempotent on request_id).
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        old_fee = _lookup_program_fee(from_course, None) or 0.0
        new_fee = _lookup_program_fee(to_course, None) or 0.0
        if old_fee:
            raise_charge(
                student_id, -float(old_fee),
                source="adjustment",
                description=f"Credit: {from_course} (adjustment)",
                reference_id=f"adjustment:{request_id}:credit",
            )
        if new_fee:
            raise_charge(
                student_id, float(new_fee),
                source="adjustment",
                description=f"Debit: {to_course} (adjustment)",
                reference_id=f"adjustment:{request_id}:debit",
            )
    except Exception as exc:
        logger.debug("adjustment→finance failed: %s", exc)

def _on_apl_approved(**payload: Any) -> None:
    if payload.get("action") != "apl_approved":
        return
    student_id = payload.get("student_id")
    credits = payload.get("credits_awarded")
    if not student_id:
        return
    logger.info(
        "APL approved: student=%s credits=%s claim=%s type=%s",
        student_id, credits, payload.get("claim_id"),
        payload.get("claim_type"),
    )

_DEFAULT_APPLICATION_FEE = 25.0

def _on_admissions_decision(**payload: Any) -> None:
    if payload.get("action") != "admissions_decision":
        return
    decision = (payload.get("decision") or "").lower()

    # Yield-rate metric: ratio of accepts to total decisions.
    _bump_yield_rate(decision)

    # Fee charge on accept when not already paid.
    if decision in ("accepted", "offer", "approved"):
        applicant_id = payload.get("applicant_id")
        if applicant_id and not payload.get("fee_paid"):
            fee = payload.get("application_fee") or _DEFAULT_APPLICATION_FEE
            try:
                from education_system.systems.university.services.bus.finance_bus import (
                    raise_charge,
                )
                raise_charge(
                    applicant_id, float(fee),
                    source="admissions",
                    description="Application fee",
                    reference_id=f"admission_app:{payload.get('application_id')}",
                )
            except Exception as exc:
                logger.debug("admissions→fee charge failed: %s", exc)

def _bump_yield_rate(decision: str) -> None:
    """Update the running Yield Rate (%) KPI: accepted / decisions_made."""
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='admission_applications'"
            ).fetchone()
            if not tbl:
                return
            total = conn.execute(
                "SELECT COUNT(*) FROM admission_applications "
                "WHERE decision IS NOT NULL AND decision != ''"
            ).fetchone()[0] or 0
            accepted = conn.execute(
                "SELECT COUNT(*) FROM admission_applications "
                "WHERE LOWER(decision) IN ('accepted', 'offer', 'approved')"
            ).fetchone()[0] or 0
    except Exception:
        return
    if total <= 0:
        return
    rate = (accepted / total) * 100
    _set_kpi(name="Yield Rate", category="admissions", value=rate)
