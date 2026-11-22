"""Academic-calendar adapter — surface assessment dates as events.

Same pattern as ``domain/assignments/assignment_rules/calendar_sync.py``.
Deterministic id ``ASSMT-{assessment_id}``, ``event_type='Assessment'``,
honours the schema's CHECK constraint by storing a point-in-time
``date`` rather than a span.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

EVENT_TYPE = "Assessment"


def _event_id(assessment_id: int) -> str:
    return f"ASSMT-{int(assessment_id)}"


def sync_assessment_to_calendar(
    *,
    assessment_id: int,
    name: str,
    due_date: str,
    module_code: str | None = None,
    created_by: str | None = None,
) -> bool:
    """Upsert an academic-calendar event for an assessment due date."""
    if not assessment_id or not due_date:
        return False
    date_only = (due_date or "").split(" ")[0]
    label = f"{name} ({module_code})" if module_code else name
    description = (
        f"Assessment '{name}' due"
        + (f" in module {module_code}" if module_code else "")
        + "."
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_id = _event_id(assessment_id)
    try:
        conn = sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='academic_calendar_events'"
            ).fetchone()
            if not row:
                return False
            existing = cur.execute(
                "SELECT id FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?",
                (event_id,),
            ).fetchone()
            if existing:
                cur.execute(
                    """
                    UPDATE unified_events SET title = ?, event_date = ?, start_datetime = NULL, end_datetime = NULL,
                           description = ?, event_type = ?, updated_at = ? WHERE source_type = 'academic_calendar' AND (source_event_id = ?)""",
                    (label, date_only, description, EVENT_TYPE, now, event_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO unified_events (
                    source_event_id, title, event_date, start_datetime, end_datetime, description, event_type, created_at, updated_at, created_by, source_type
                ) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, 'academic_calendar')
                    """,
                    (event_id, label, date_only, description, EVENT_TYPE,
                     now, now, created_by),
                )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "sync_assessment_to_calendar failed for %s: %s",
            assessment_id, exc,
        )
        return False


def remove_assessment_from_calendar(assessment_id: int) -> bool:
    if not assessment_id:
        return False
    try:
        conn = sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            conn.execute(
                "DELETE FROM unified_events WHERE source_type = 'academic_calendar' AND (source_event_id = ?)",
                (_event_id(assessment_id),),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "remove_assessment_from_calendar failed for %s: %s",
            assessment_id, exc,
        )
        return False
