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
from education_system.systems.university.services.bus.integration.publishing import _set_kpi
from education_system.systems.university.services.bus.integration.workforce.publishers import publish_cert_expiry
from education_system.systems.university.services.bus.integration.workforce.subscribers import _is_role_critical

def sweep_expiring_certifications(*, within_days: int = 30) -> int:
    """Scan certifications for upcoming expiries and publish events.

    Public entry point — call from a daily cron or HR dashboard
    refresh. Returns the number of expiring certs found.
    """
    found = 0
    try:
        from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.training_manager import (
            TrainingManager,
        )
        rows = TrainingManager.get_expiring_certs(days=within_days)
    except Exception as exc:
        logger.debug("training_manager.get_expiring_certs unavailable: %s", exc)
        rows = []

    critical_count = 0
    for r in rows:
        found += 1
        critical = _is_role_critical(r.get("user_id"))
        if critical:
            critical_count += 1
        publish_cert_expiry(
            user_id=r.get("user_id"),
            training_id=r.get("certification_id") or r.get("course_id"),
            cert_name=r.get("name") or r.get("course_name") or "certification",
            expiry_date=r.get("expiry_date") or r.get("expires_on") or "",
            role_critical=critical,
        )
    # KPI risk gauge: ratio of critical expiring certs to total expiring.
    if found:
        ratio = (critical_count / found) * 100
        _set_kpi(name="Compliance Risk", category="risk", value=ratio)
    return found
