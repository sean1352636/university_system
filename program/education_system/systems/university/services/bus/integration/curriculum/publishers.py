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
from education_system.systems.university.services.bus.integration.publishing import _current_year, log_and_publish

def publish_timetable_locked(user_ids: list[str], *, academic_year: str | None = None,
                             semester: str | None = None) -> None:
    """Feature 4: lock-down fan-out."""
    log_and_publish(
        EVENT_MODULE_SCHEDULE_CHANGED,
        source="module_scheduling",
        action="timetable_locked",
        user_ids=[str(u) for u in user_ids],
        academic_year=academic_year or _current_year(),
        semester=semester,
    )

def publish_demand_forecast(course_code: str, *, predicted_enrollment: int,
                            academic_year: str | None = None) -> None:
    """Feature 6: KPI → clearing vacancy planner."""
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="kpi_dashboard",
        action="demand_forecast",
        course_code=course_code,
        predicted_enrollment=int(predicted_enrollment),
        academic_year=academic_year or _current_year(),
    )
