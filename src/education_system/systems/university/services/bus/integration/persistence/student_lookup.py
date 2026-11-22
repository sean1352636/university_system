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

def resolve_student_id(*, ucas_id: str | None = None,
                       application_id: int | None = None) -> str | None:
    """Resolve a clearing applicant to a real student_id, if one exists.

    Falls through gracefully when the link tables aren't present —
    callers (e.g. clearing acceptance) treat None as "create-on-demand
    elsewhere" rather than a hard error.
    """
    try:
        with get_connection() as conn:
            if ucas_id:
                # Students carry no UCAS id: the clearing application holds it,
                # and its e-mail address finds the student record.
                row = conn.execute(
                    "SELECT s.student_id FROM clearing_applications c "
                    "JOIN students s ON LOWER(s.email_address) = LOWER(c.email) "
                    "WHERE c.ucas_id = ? AND TRIM(COALESCE(c.email, '')) <> '' LIMIT 1",
                    (str(ucas_id),),
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
            if application_id is not None:
                row = conn.execute(
                    "SELECT ucas_id, applicant_name FROM clearing_applications "
                    "WHERE id = ?",
                    (int(application_id),),
                ).fetchone()
                if row:
                    return f"clearing:{application_id}"  # opaque ref
    except Exception as exc:
        logger.debug("resolve_student_id failed: %s", exc)
    return None
