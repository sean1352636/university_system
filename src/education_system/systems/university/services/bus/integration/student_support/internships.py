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

def publish_internship_placement(placement_id: int, *, student_id: str,
                                  internship_id: int,
                                  company: str | None = None,
                                  supervisor_email: str | None = None,
                                  start_date: str | None = None,
                                  end_date: str | None = None) -> None:
    """Publish a confirmed internship placement.

    Origin: ``internship_management.review_application`` after the
    placement INSERT.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="careers",
        action="internship_placed",
        placement_id=int(placement_id),
        student_id=str(student_id),
        internship_id=int(internship_id),
        company=company,
        supervisor_email=supervisor_email,
        start_date=start_date,
        end_date=end_date,
    )

def _on_internship_placed(**payload: Any) -> None:
    if payload.get("action") != "internship_placed":
        return

    # Bump Internship Placements KPI.
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_value FROM kpi_metrics "
                "WHERE kpi_name = 'Internship Placements' LIMIT 1"
            ).fetchone()
            current = float(row[0] or 0) if row else 0.0
    except Exception:
        current = 0.0
    _set_kpi(name="Internship Placements", category="careers",
             value=current + 1)

    # Email the employer supervisor — direct address (not a user_id).
    supervisor_email = payload.get("supervisor_email")
    if not supervisor_email:
        return
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        # email_bus resolves recipients by user_id; we use the email
        # as the user_id and force send so prefs lookup doesn't 404.
        send_templated(
            supervisor_email, "careers.engagement.started",
            {
                "kind": "internship",
                "role": payload.get("company") or "internship",
                "hours_required": "see contract",
            },
            related_to=f"placement:{payload.get('placement_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("internship→employer email failed: %s", exc)
