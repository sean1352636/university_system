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
from education_system.systems.university.services.bus.integration.persistence.event_log import _ensure_log_table

def log_and_publish(event: str, *, source: str, **payload: Any) -> None:
    """Record the event in ``integration_log`` then fan out via the bus.

    Best-effort logging — a logging failure must never silence the
    publish.
    """
    try:
        _ensure_log_table()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO integration_log (event_name, source_module, payload_json) "
                "VALUES (?, ?, ?)",
                (event, source, json.dumps(payload, default=str)),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("integration_log write failed (%s): %s", event, exc)
    publish(event, **payload)

def _set_kpi(*, name: str, category: str, value: float) -> None:
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_metrics'"
            ).fetchone()
            if not tbl:
                return
            row = conn.execute(
                "SELECT kpi_id FROM kpi_metrics WHERE kpi_name = ? LIMIT 1", (name,),
            ).fetchone()
            today = date.today().isoformat()
            if row:
                conn.execute(
                    "UPDATE kpi_metrics SET current_value = ?, measurement_date = ? "
                    "WHERE kpi_id = ?",
                    (float(value), today, row[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO kpi_metrics (kpi_name, kpi_category, current_value, "
                    "  target_value, measurement_date, period, trend) "
                    "VALUES (?, ?, ?, ?, ?, 'monthly', 'flat')",
                    (name, category, float(value), float(value), today),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("_set_kpi(%s) failed: %s", name, exc)

def _bump_kpi(*, category: str, increment: float) -> None:
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_metrics'"
            ).fetchone()
            if not tbl:
                return
            row = conn.execute(
                "SELECT kpi_id, current_value FROM kpi_metrics "
                "WHERE kpi_category = ? ORDER BY kpi_id LIMIT 1",
                (category,),
            ).fetchone()
            if not row:
                return
            new_val = float(row[1] or 0) + float(increment)
            conn.execute(
                "UPDATE kpi_metrics SET current_value = ?, measurement_date = ? "
                "WHERE kpi_id = ?",
                (new_val, date.today().isoformat(), row[0]),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("_bump_kpi(%s) failed: %s", category, exc)

def _current_year() -> str:
    today = date.today()
    # Sept onwards belongs to the next academic year (e.g. 2025/26).
    if today.month >= 9:
        return f"{today.year}/{str(today.year + 1)[-2:]}"
    return f"{today.year - 1}/{str(today.year)[-2:]}"
