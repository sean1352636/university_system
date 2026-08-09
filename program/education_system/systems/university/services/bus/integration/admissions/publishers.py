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
from education_system.systems.university.services.bus.integration.persistence.student_lookup import resolve_student_id
from education_system.systems.university.services.bus.integration.publishing import _current_year, log_and_publish

def publish_clearing_accepted(application_id: int, *, course_code: str,
                              ucas_id: str | None = None,
                              applicant_name: str | None = None,
                              academic_year: str | None = None) -> None:
    """Feature 1: clearing acceptance fan-out.

    Triggered by ClearingAdjustmentService.update_application_status('accepted').
    """
    student_ref = (
        resolve_student_id(ucas_id=ucas_id, application_id=application_id)
        or f"clearing:{application_id}"
    )
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="clearing_adjustment",
        action="clearing_accepted",
        application_id=int(application_id),
        student_ref=student_ref,
        ucas_id=ucas_id,
        applicant_name=applicant_name,
        course_code=course_code,
        academic_year=academic_year or _current_year(),
    )

def publish_adjustment_approved(request_id: int, *, student_id: str,
                                from_course: str, to_course: str) -> None:
    """Feature 3: adjustment approved fan-out."""
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="clearing_adjustment",
        action="adjustment_approved",
        request_id=int(request_id),
        student_id=str(student_id),
        from_course=from_course,
        to_course=to_course,
    )

def publish_apl_approved(claim_id: int, *, student_id: str,
                         credits_awarded: int,
                         claim_type: str | None = None,
                         decision: str = "approved",
                         target_course: str | None = None) -> None:
    """APL/RPL claim decision fan-out.

    Triggered by ``PriorLearningService.review_claim`` when the
    decision is ``approved`` or ``partial``. Logged on
    ``EVENT_COURSE_CHANGED`` so HESA Export, External QA, and degree
    audit subscribers can pick it up without the APL module having to
    know who's listening.
    """
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="prior_learning_recognition",
        action="apl_approved",
        claim_id=int(claim_id),
        student_id=str(student_id),
        credits_awarded=int(credits_awarded or 0),
        claim_type=claim_type,
        decision=decision,
        target_course=target_course,
    )

def publish_admissions_decision(application_id: int, *,
                                decision: str,
                                applicant_id: str | None = None,
                                course: str | None = None,
                                application_fee: float | None = None,
                                fee_paid: bool = False) -> None:
    """Publish an admissions decision (pre-clearing track).

    Origin: ``admissions_crm_core.ApplicationManager.make_decision``.
    Subscriber updates yield-rate KPI (offers vs accepts) and, on
    a positive decision with unpaid fee, raises the application
    fee charge.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="admissions",
        action="admissions_decision",
        application_id=int(application_id),
        decision=decision,
        applicant_id=str(applicant_id) if applicant_id else None,
        course=course,
        application_fee=float(application_fee) if application_fee is not None else None,
        fee_paid=bool(fee_paid),
    )
