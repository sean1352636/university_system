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

def publish_exam_event(exam_id: int, *, action: str,
                       module_code: str | None = None,
                       exam_title: str | None = None,
                       start_time: str | None = None,
                       duration_minutes: int | None = None,
                       pass_mark: float | None = None,
                       student_id: str | None = None,
                       score: float | None = None,
                       total_marks: float | None = None,
                       percentage: float | None = None,
                       passed: bool | None = None) -> None:
    """Publish an exam lifecycle event.

    ``action`` is one of: ``"published"``, ``"unpublished"``,
    ``"graded"``, ``"pending_grade"``. Origin: ExamPortalService.
    """
    log_and_publish(
        EVENT_EXAM_CHANGED,
        source="exam_management",
        exam_id=int(exam_id),
        action=action,
        module_code=module_code,
        exam_title=exam_title,
        start_time=start_time,
        duration_minutes=duration_minutes,
        pass_mark=pass_mark,
        student_id=student_id,
        score=score,
        total_marks=total_marks,
        percentage=percentage,
        passed=passed,
    )
