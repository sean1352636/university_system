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

def publish_event_attendance(event_id: int, *, user_id: str,
                             event_name: str | None = None,
                             event_category: str | None = None) -> None:
    """Publish an event check-in. Origin: ``EventsService.check_in_to_event``."""
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="events",
        action="event_check_in",
        event_id=int(event_id),
        user_id=str(user_id),
        event_name=event_name,
        event_category=event_category,
    )

def _on_event_check_in(**payload: Any) -> None:
    if payload.get("action") != "event_check_in":
        return
    # Bump the Student Engagement KPI by 1. _set_kpi handles the
    # "create on first sight" path so a fresh deploy doesn't need a
    # seed migration.
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_value FROM kpi_metrics "
                "WHERE kpi_name = 'Student Engagement' LIMIT 1"
            ).fetchone()
            current = float(row[0] or 0) if row else 0.0
    except Exception:
        current = 0.0
    _set_kpi(name="Student Engagement", category="engagement",
             value=current + 1)
