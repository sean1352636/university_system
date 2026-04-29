"""Academic-calendar adapter — mirror assignment due dates as events.

Mirrors the lecture-sync pattern in
``services/course_management/calendar_lecture_sync.py``: one
``academic_calendar_events`` row per assignment, deterministic id
``ASGN-{assignment_id}``, ``event_type='Assignment Deadline'``.
Idempotent — re-running upserts.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

EVENT_TYPE = "Assignment Deadline"


def _event_id(assignment_id: int) -> str:
    return f"ASGN-{int(assignment_id)}"


def sync_assignment_to_calendar(
    *,
    assignment_id: int,
    title: str,
    due_date: str,
    module_code: str | None = None,
    created_by: str | None = None,
) -> bool:
    """Upsert an academic-calendar event for the assignment's due date.

    ``due_date`` may be a full ``YYYY-MM-DD HH:MM:SS`` string or just
    ``YYYY-MM-DD`` — we store both ``date`` and ``date_start`` /
    ``date_end`` to the same value so the calendar treats it as a
    point event.
    """
    if not assignment_id or not due_date:
        return False

    date_only = (due_date or "").split(" ")[0]
    name = f"{title} ({module_code})" if module_code else title
    description = (
        f"Submission deadline for assignment '{title}'"
        + (f" in module {module_code}" if module_code else "")
        + "."
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_id = _event_id(assignment_id)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='academic_calendar_events'"
            ).fetchone()
            if not row:
                return False

            existing = cur.execute(
                "SELECT id FROM academic_calendar_events WHERE id = ?",
                (event_id,),
            ).fetchone()

            # Schema CHECK requires either (date) OR (date_start, date_end);
            # we always store deadlines as point-in-time `date` events.
            if existing:
                cur.execute(
                    """
                    UPDATE academic_calendar_events
                       SET name = ?, date = ?, date_start = NULL, date_end = NULL,
                           description = ?, event_type = ?, last_modified = ?
                     WHERE id = ?
                    """,
                    (name, date_only, description, EVENT_TYPE, now, event_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO academic_calendar_events
                        (id, name, date, date_start, date_end, description,
                         event_type, date_added, last_modified, created_by)
                    VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
                    """,
                    (event_id, name, date_only, description, EVENT_TYPE,
                     now, now, created_by),
                )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "sync_assignment_to_calendar failed for %s: %s",
            assignment_id, exc,
        )
        return False


def remove_assignment_from_calendar(assignment_id: int) -> bool:
    """Delete the ASGN-* calendar row for an assignment (e.g. on archive)."""
    if not assignment_id:
        return False
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            conn.execute(
                "DELETE FROM academic_calendar_events WHERE id = ?",
                (_event_id(assignment_id),),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "remove_assignment_from_calendar failed for %s: %s",
            assignment_id, exc,
        )
        return False
