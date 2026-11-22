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
from education_system.systems.university.services.bus.integration.finance.reporting import _admin_user_id
from education_system.systems.university.services.bus.integration.publishing import log_and_publish

def publish_complaint_filed(complaint_id: str | int, *,
                            user_id: str | None,
                            email: str | None = None,
                            category: str | None = None,
                            priority: str | None = None,
                            subject: str | None = None) -> None:
    """Publish a complaint submission.

    Origin: ``complaints_portal.insert_complaint``. Only urgent /
    high-priority complaints auto-escalate; lower priorities save
    silently.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="complaints",
        kind="complaint_filed",
        severity=_severity_for_priority(priority),
        complaint_id=str(complaint_id),
        user_id=str(user_id) if user_id else None,
        email=email,
        category=category,
        priority=priority,
        subject=subject,
    )

def _severity_for_priority(priority: str | None) -> str:
    p = (priority or "").lower()
    if p in ("urgent", "critical", "p0"):
        return "critical"
    if p in ("high", "p1"):
        return "high"
    if p in ("medium", "p2"):
        return "medium"
    return "low"

def _on_complaint_filed(**payload: Any) -> None:
    if payload.get("kind") != "complaint_filed":
        return
    priority = (payload.get("priority") or "").lower()
    if priority not in ("urgent", "critical", "p0", "high", "p1"):
        return  # auto-escalation only for genuine fires

    user_id = payload.get("user_id") or "unknown"

    # Open a case so disciplinary / pastoral pipelines see it.
    try:
        from education_system.systems.university.services.bus.cases_bus import (
            open_case,
        )
        open_case(
            kind="complaint",
            subject_id=str(user_id),
            severity=payload.get("severity") or "high",
            description=(
                f"Urgent complaint #{payload.get('complaint_id')} — "
                f"{payload.get('category') or 'uncategorised'}: "
                f"{payload.get('subject') or ''}"
            ),
            opened_by="complaints_portal",
        )
    except Exception as exc:
        logger.debug("complaint→cases_bus failed: %s", exc)

    # Email the Dean of Students (or fallback admin).
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        recipient = _dean_of_students_user_id() or _admin_user_id() or "admin"
        send_templated(
            recipient, "case.opened",
            {
                "case_id": payload.get("complaint_id"),
                "kind": "complaint",
                "severity": payload.get("severity") or "high",
            },
            related_to=f"complaint:{payload.get('complaint_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("complaint→dean email failed: %s", exc)

def _dean_of_students_user_id() -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM users "
                "WHERE LOWER(role) IN ('dean', 'dean_of_students', "
                "                      'student_affairs_dean') "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None
