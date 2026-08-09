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

_LOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS integration_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name    TEXT NOT NULL,
    source_module TEXT NOT NULL,
    payload_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_LOG_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_integration_log_event "
    "ON integration_log(event_name, created_at DESC)"
)

def _ensure_log_table() -> None:
    try:
        with get_connection() as conn:
            conn.executescript(_LOG_SCHEMA_SQL)
            conn.execute(_LOG_INDEX_SQL)
            conn.commit()
    except Exception as exc:
        logger.debug("integration_log table init failed: %s", exc)

def recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent integration events. Used by the KPI activity widget."""
    _ensure_log_table()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT log_id, event_name, source_module, payload_json, created_at "
                "FROM integration_log ORDER BY log_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["payload"] = json.loads(d.pop("payload_json"))
                except Exception:
                    d["payload"] = {}
                out.append(d)
            return out
    except Exception as exc:
        logger.warning("recent_events failed: %s", exc)
        return []
