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

def publish_health_appointment(appointment_id: int, *, student_id: str,
                                appointment_date: str,
                                appointment_time: str,
                                provider: str | None = None,
                                appointment_type: str | None = None) -> None:
    """Publish a booked health appointment so the calendar checker
    can flag class-time clashes.

    Origin: health appointment_booking schedule_appointment.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="health",
        kind="health_appointment_booked",
        severity="low",
        appointment_id=int(appointment_id),
        student_id=str(student_id),
        appointment_date=str(appointment_date),
        appointment_time=str(appointment_time),
        provider=provider,
        appointment_type=appointment_type,
    )

def _on_health_appointment_booked(**payload: Any) -> None:
    if payload.get("kind") != "health_appointment_booked":
        return
    student_id = payload.get("student_id")
    appt_date = payload.get("appointment_date") or ""
    appt_time = payload.get("appointment_time") or ""
    if not (student_id and appt_date and appt_time):
        return

    # Compute the day-of-week and a 1-hour window around the
    # appointment, then check student timetable / module_schedule.
    try:
        dt = datetime.strptime(
            f"{appt_date[:10]} {appt_time[:5]}", "%Y-%m-%d %H:%M")
    except Exception:
        return
    day_name = dt.strftime("%A")
    window_start = dt.strftime("%H:%M")
    window_end = (dt + timedelta(hours=1)).strftime("%H:%M")

    clash = _has_class_at(student_id, day_name, window_start, window_end)
    if not clash:
        return

    # Notify the student via email + flag the appointment as
    # 'has_conflict' (column added lazily) so the GUI can render a
    # warning badge.
    try:
        with transaction() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(health_appointments)").fetchall()}
            if "has_conflict" not in cols:
                conn.execute(
                    "ALTER TABLE health_appointments "
                    "ADD COLUMN has_conflict INTEGER DEFAULT 0"
                )
            conn.execute(
                "UPDATE health_appointments SET has_conflict = 1 "
                "WHERE id = ?",
                (int(payload.get("appointment_id")),),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("health appt conflict flag failed: %s", exc)

    try:
        from education_system.systems.university.services.bus.email_bus import (
            send_templated,
        )
        send_templated(
            student_id, "hs.incident.logged",
            {
                "incident_id": f"appt_clash:{payload.get('appointment_id')}",
                "severity": "medium",
                "location": (
                    f"{appt_date} {appt_time} — clashes with "
                    f"{clash.get('module_code') or 'class'}"
                ),
            },
            related_to=f"appt:{payload.get('appointment_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("health appt clash email failed: %s", exc)

def _has_class_at(student_id: str, day_of_week: str,
                   start_time: str, end_time: str) -> dict[str, Any] | None:
    """Look for a module_schedule row the student is enrolled in
    that overlaps the window.
    """
    try:
        with get_connection() as conn:
            # student_enrolment is the canonical roster table; fall
            # back to plan_courses if the former isn't present.
            for sql in (
                "SELECT ms.module_code, ms.start_time, ms.end_time "
                "FROM module_schedule ms "
                "JOIN student_enrolment se ON se.module_code = ms.module_code "
                "WHERE se.student_id = ? AND ms.day_of_week = ? "
                "  AND NOT (ms.end_time <= ? OR ms.start_time >= ?) "
                "LIMIT 1",
                "SELECT ms.module_code, ms.start_time, ms.end_time "
                "FROM module_schedule ms "
                "JOIN plan_courses pc ON pc.course_code = ms.module_code "
                "JOIN student_plans sp ON sp.plan_id = pc.plan_id "
                "WHERE sp.student_id = ? AND ms.day_of_week = ? "
                "  AND NOT (ms.end_time <= ? OR ms.start_time >= ?) "
                "LIMIT 1",
            ):
                try:
                    row = conn.execute(
                        sql, (str(student_id), day_of_week,
                              start_time, end_time),
                    ).fetchone()
                    if row:
                        return {"module_code": row[0],
                                "start_time": row[1],
                                "end_time": row[2]}
                except Exception:
                    continue
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return None
