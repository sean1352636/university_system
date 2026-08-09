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

def _admin_user_id() -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users WHERE LOWER(role) = 'admin' "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None

def send_finance_report(report_title: str, summary: str,
                        *, recipient_user_id: str | None = None,
                        related_to: str | None = None) -> str | None:
    """Route a finance report through email_bus so it lands in
    ``email_log`` and fires ``EVENT_EMAIL_SENT`` for audit.

    Returns the message_id on success.
    """
    target = recipient_user_id or _admin_user_id() or "admin"
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        return send_templated(
            target, "finance.report.sent",
            {
                "report_title": report_title,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "summary": summary[:1500],
            },
            related_to=related_to or "finance_report",
            force=True,
        )
    except Exception as exc:
        logger.warning("send_finance_report failed: %s", exc)
        return None
