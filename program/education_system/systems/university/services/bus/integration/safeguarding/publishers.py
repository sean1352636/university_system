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

_SAFEGUARDING_THRESHOLD = 70

def publish_health_risk_assessment(student_id: str, *, assessment_type: str,
                                    risk_score: int,
                                    risk_factors: list[str] | None = None,
                                    follow_up_date: str | None = None,
                                    assessed_by: str | None = None) -> None:
    """Publish a health risk assessment.

    Origin: ``health.portal.data_privacy.conduct_risk_assessment``.
    Subscribers (this module) raise an incident and an open case
    when the score crosses the safeguarding threshold.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="health",
        kind="health_risk_assessment",
        severity=_severity_for_score(risk_score),
        student_id=str(student_id),
        assessment_type=assessment_type,
        risk_score=int(risk_score),
        risk_factors=risk_factors or [],
        follow_up_date=follow_up_date,
        assessed_by=assessed_by,
    )

def _severity_for_score(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= _SAFEGUARDING_THRESHOLD:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
