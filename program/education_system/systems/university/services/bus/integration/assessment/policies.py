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
from education_system.systems.university.services.bus.integration.curriculum.subscribers import _current_term

def can_student_start_exam(student_id: str) -> tuple[bool, str | None]:
    """Return ``(allowed, reason)`` for an exam-start gate.

    Wraps ``finance_bus.has_active_hold``. Callers (exam_service) can
    plug this in without learning the holds schema.
    """
    if not student_id:
        return True, None
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            has_active_hold, list_active_holds,
        )
        if not has_active_hold(student_id):
            return True, None
        holds = list_active_holds(student_id) or []
        reason = (holds[0].get("reason") if holds else None) or "active finance hold"
        return False, reason
    except Exception as exc:
        logger.debug("hold check failed for %s: %s — allowing", student_id, exc)
        return True, None

def is_exam_within_term(start_time: str | None, end_time: str | None) -> bool:
    """Return True if the exam window falls inside the cached term.

    Returns True (permissive) when no term has been broadcast yet —
    the integration check shouldn't block an admin who never set a
    term in the first place.
    """
    if not _current_term["start"] or not _current_term["end"]:
        return True
    if not start_time or not end_time:
        return True
    try:
        s = str(start_time)[:10]
        e = str(end_time)[:10]
        return _current_term["start"] <= s and e <= _current_term["end"]
    except Exception:
        return True
