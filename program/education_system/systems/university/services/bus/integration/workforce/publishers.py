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

def publish_leave_decision(staff_id: str, *, action: str,
                           start_date: str | None = None,
                           end_date: str | None = None,
                           leave_type: str | None = None,
                           source: str = "leave") -> None:
    """Feature 2: leave/sabbatical/sickness fan-out."""
    log_and_publish(
        EVENT_STAFF_AVAILABILITY_CHANGED,
        source="staff_hr",
        staff_id=str(staff_id),
        action=action,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
        source_kind=source,
    )

def publish_appraisal_completed(user_id: str, *, cycle_id: int,
                                rating: float) -> None:
    """Feature 7: appraisal → merit-pay proposal."""
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="staff_hr",
        action="appraisal_completed",
        user_id=str(user_id),
        cycle_id=int(cycle_id),
        rating=float(rating),
    )

def publish_cert_expiry(user_id: str, *, training_id: int | None,
                        cert_name: str, expiry_date: str,
                        role_critical: bool = False) -> None:
    """Feature 8: certification expiry alert."""
    try:
        days = (datetime.strptime(expiry_date[:10], "%Y-%m-%d").date()
                - date.today()).days
    except Exception:
        days = None
    log_and_publish(
        EVENT_CERT_CHANGED,
        source="staff_hr",
        user_id=str(user_id),
        training_id=training_id,
        cert_name=cert_name,
        expiry_date=expiry_date,
        days_to_expiry=days,
        role_critical=bool(role_critical),
    )
