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
from education_system.systems.university.services.bus.integration.publishing import log_and_publish

def publish_waitlist_promoted(student_id: str, *, course_code: str,
                              plan_id: int | None = None,
                              fee_amount: float | None = None) -> None:
    """Feature 9: waitlist atomic enrol+bill (publish step)."""
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="course_management",
        action="waitlist_promoted",
        student_id=str(student_id),
        course_code=course_code,
        plan_id=plan_id,
        fee_amount=fee_amount,
    )

def publish_enrolment_withdrew(student_id: str, course_code: str,
                               *, reason: str | None = None) -> None:
    """Course Management calls this when a student drops a module."""
    log_and_publish(
        EVENT_ENROLMENT_CHANGED,
        source="course_management",
        action="withdrew",
        student_id=str(student_id),
        course_code=course_code,
        reason=reason,
    )

def publish_enrolment_added(student_id: str, course_code: str,
                            *, source: str = "course_management") -> None:
    """Origin: enrolment writers (student_registration, course
    catalog, grade_tracking module_manager). Publishes through the
    canonical EVENT_ENROLMENT_CHANGED so consumers (study matching
    auto-suggest, exam roster, finance) can react.
    """
    log_and_publish(
        EVENT_ENROLMENT_CHANGED,
        source=source,
        action="enrolled",
        student_id=str(student_id),
        course_code=course_code,
    )
