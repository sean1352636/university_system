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
from education_system.systems.university.services.bus.integration.safeguarding.publishers import _SAFEGUARDING_THRESHOLD

def _on_health_risk_assessment(**payload: Any) -> None:
    if payload.get("kind") != "health_risk_assessment":
        return
    score = int(payload.get("risk_score") or 0)
    if score < _SAFEGUARDING_THRESHOLD:
        return  # below threshold — no auto-escalation
    student_id = payload.get("student_id")
    if not student_id:
        return

    # 1. Open a safeguarding case via cases_bus (idempotent on
    # subject_id+kind so repeat assessments don't pile up cases).
    try:
        from education_system.systems.university.services.bus.cases_bus import (
            open_case,
        )
        open_case(
            kind="safeguarding",
            subject_id=str(student_id),
            severity=payload.get("severity") or "high",
            description=(
                f"Health risk assessment: {payload.get('assessment_type')} "
                f"score {score}"
            ),
            opened_by=payload.get("assessed_by") or "health_portal",
        )
    except Exception as exc:
        logger.debug("cases_bus open_case failed: %s", exc)

    # 2. Email the designated safeguarding lead.
    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        dsl = _designated_safeguarding_lead() or _admin_user_id() or "admin"
        send_templated(
            dsl, "hs.incident.logged",
            {
                "incident_id": f"health:{student_id}:{score}",
                "severity": payload.get("severity") or "high",
                "location": "health portal",
            },
            related_to=f"safeguarding:{student_id}",
            force=True,
        )
    except Exception as exc:
        logger.debug("safeguarding email failed: %s", exc)

def _designated_safeguarding_lead() -> str | None:
    """Look up the DSL user_id. Falls back to None if not configured.

    The convention here is a row in ``users`` with
    ``role='safeguarding_lead'``; if that role doesn't exist, callers
    fall through to the admin recipient.
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users "
                "WHERE LOWER(role) IN ('safeguarding_lead', 'dsl', 'designated_lead') "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None

def _on_case_opened_for_tutor_group(**payload: Any) -> None:
    """Append a pastoral agenda item to the next tutor-group meeting
    when an attendance_concern case is opened.

    cases_bus publishes via EVENT_CASE_OPENED. We filter on
    ``kind='attendance_concern'`` so other case kinds don't crowd
    the tutor's calendar.
    """
    if (payload.get("kind") or "").lower() != "attendance_concern":
        return
    student_id = payload.get("subject_id")
    case_id = payload.get("case_id") or payload.get("record_id")
    if not student_id:
        return

    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='tutor_group_members'"
            ).fetchone()
            if not tbl:
                return
            grp = conn.execute(
                "SELECT m.group_id FROM tutor_group_members m "
                "WHERE m.student_id = ? AND m.is_active = 1 "
                "ORDER BY m.membership_id DESC LIMIT 1",
                (str(student_id),),
            ).fetchone()
            if not grp:
                return
            group_id = grp[0]
            meeting = conn.execute(
                "SELECT meeting_id, agenda FROM tutor_group_meetings "
                "WHERE group_id = ? AND status = 'scheduled' "
                "  AND scheduled_at >= datetime('now') "
                "ORDER BY scheduled_at ASC LIMIT 1",
                (group_id,),
            ).fetchone()
    except Exception as exc:
        logger.debug("tutor_group lookup failed: %s", exc)
        return

    note = (
        f"Attendance concern: student {student_id} "
        f"(case #{case_id}) — review intervention plan."
    )
    try:
        with transaction() as conn:
            if meeting and meeting[0]:
                # Append to the next scheduled meeting's agenda.
                existing = (meeting[1] or "").rstrip()
                new_agenda = f"{existing}\n• {note}".lstrip()
                conn.execute(
                    "UPDATE tutor_group_meetings SET agenda = ? "
                    "WHERE meeting_id = ?",
                    (new_agenda, meeting[0]),
                )
            else:
                # No upcoming meeting — drop a placeholder so the
                # tutor sees the flag on the dashboard.
                conn.execute(
                    "INSERT INTO tutor_group_meetings "
                    "(group_id, scheduled_at, duration_minutes, agenda, status) "
                    "VALUES (?, ?, 30, ?, 'pending')",
                    (group_id,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     f"• {note}"),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("tutor_group agenda update failed: %s", exc)
