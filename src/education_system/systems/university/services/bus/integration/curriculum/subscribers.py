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

def _on_timetable_locked(**payload: Any) -> None:
    if payload.get("action") != "timetable_locked":
        return
    user_ids = payload.get("user_ids") or []
    if not user_ids:
        return

    try:
        with transaction() as conn:
            for uid in user_ids:
                hours = _sum_weekly_block_hours(conn, str(uid))
                if hours is None:
                    continue
                # Stamp into payroll_periods if the column exists.
                try:
                    conn.execute(
                        "UPDATE payroll_periods SET contracted_hours = ? "
                        "WHERE status = 'open' AND ? IN ("
                        "  SELECT user_id FROM faculty_schedule_blocks "
                        "  WHERE user_id = ?)",
                        (float(hours), str(uid), str(uid)),
                    )
                except Exception as exc:
                    logger.debug("payroll_periods stamp skipped: %s", exc)
            conn.commit()
    except Exception as exc:
        logger.debug("timetable_locked payroll stamp failed: %s", exc)

    # KPI: write/refresh staff_utilisation summary.
    avg = _avg_utilisation(user_ids)
    if avg is not None:
        _set_kpi(name="Staff Utilisation", category="staff", value=avg)

def _sum_weekly_block_hours(conn: Any, user_id: str) -> float | None:
    try:
        rows = conn.execute(
            "SELECT start_time, end_time FROM faculty_schedule_blocks "
            "WHERE user_id = ? AND COALESCE(is_locked, 0) = 1",
            (user_id,),
        ).fetchall()
    except Exception:
        return None
    total = 0.0
    for r in rows:
        try:
            s = datetime.strptime(r[0][:5], "%H:%M")
            e = datetime.strptime(r[1][:5], "%H:%M")
            total += (e - s).total_seconds() / 3600.0
        except Exception:
            continue
    return total

def _avg_utilisation(user_ids: list[str]) -> float | None:
    if not user_ids:
        return None
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT user_id, COALESCE(SUM(end_time - start_time), 0) "
                "FROM faculty_schedule_blocks WHERE user_id IN (%s) "
                "GROUP BY user_id"
                % ",".join("?" * len(user_ids)),
                tuple(user_ids),
            ).fetchall()
        if not rows:
            return None
        return float(sum(r[1] or 0 for r in rows) / len(rows))
    except Exception:
        return None

def _on_demand_forecast(**payload: Any) -> None:
    if payload.get("action") != "demand_forecast":
        return
    course_code = payload.get("course_code")
    predicted = payload.get("predicted_enrollment")
    year = payload.get("academic_year")
    if not course_code or predicted is None:
        return
    try:
        with transaction() as conn:
            # Add the column lazily if missing.
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(clearing_vacancies)").fetchall()}
            if "suggested_places" not in cols:
                conn.execute(
                    "ALTER TABLE clearing_vacancies ADD COLUMN suggested_places INTEGER"
                )
            conn.execute(
                "UPDATE clearing_vacancies SET suggested_places = ? "
                "WHERE course_code = ? AND (academic_year = ? OR ? IS NULL)",
                (int(predicted), course_code, year, year),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("demand_forecast→vacancy update failed: %s", exc)

_current_term: dict[str, Any] = {"start": None, "end": None, "name": None}

def _on_term_changed(**payload: Any) -> None:
    if payload.get("start_date"):
        _current_term["start"] = str(payload["start_date"])[:10]
    if payload.get("end_date"):
        _current_term["end"] = str(payload["end_date"])[:10]
    if payload.get("term") or payload.get("name"):
        _current_term["name"] = str(payload.get("term") or payload.get("name"))
