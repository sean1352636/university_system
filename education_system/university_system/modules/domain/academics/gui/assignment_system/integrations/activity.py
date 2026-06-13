"""Activity adapter — read-side queries for the integrations panel.

Each helper returns the most recent N rows that originated from the
assignment subsystem in the table owned by the *other* domain. The
GUI renders these in tabs so a user can see what the silent hooks
have actually produced.
"""

from __future__ import annotations

import logging

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def _query(sql: str, params: tuple = ()) -> list[dict]:
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("activity query failed: %s — %s", sql.split('FROM')[1][:60] if 'FROM' in sql else sql[:60], exc)
        return []


def _table_exists(name: str) -> bool:
    rows = _query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    )
    return bool(rows)


def recent_late_fines(limit: int = 25) -> list[dict]:
    if not _table_exists("payments"):
        return []
    return _query(
        """
        SELECT payment_id, student_id, amount, currency, status, transaction_id,
               payment_date, notes
        FROM payments
        WHERE transaction_id LIKE 'LATE-%'
           OR notes LIKE '[Assignments]%'
        ORDER BY payment_id DESC
        LIMIT ?
        """,
        (limit,),
    )


def recent_dispute_tickets(limit: int = 25) -> list[dict]:
    if not _table_exists("support_tickets"):
        return []
    return _query(
        """
        SELECT ticket_id, user_id, student_id,
               COALESCE(subject, title) AS subject,
               status, priority, created_at
        FROM support_tickets
        WHERE source = 'assignment_dispute'
        ORDER BY ticket_id DESC
        LIMIT ?
        """,
        (limit,),
    )


def recent_integrity_cases(limit: int = 25) -> list[dict]:
    if not _table_exists("legal_cases"):
        return []
    return _query(
        """
        SELECT case_id, case_number, client_id, client_name,
               case_title, priority, status, created_at
        FROM legal_cases
        WHERE case_type = 'academic_integrity'
        ORDER BY case_id DESC
        LIMIT ?
        """,
        (limit,),
    )


def recent_gradebook_syncs(limit: int = 25) -> list[dict]:
    if not _table_exists("student_grades"):
        return []
    return _query(
        """
        SELECT id, student_id, module_code, assessment_name,
               grade, percentage, instructor, grade_date
        FROM student_grades
        WHERE assessment_type = 'assignment'
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )


def recent_calendar_events(limit: int = 25) -> list[dict]:
    if not _table_exists("academic_calendar_events"):
        return []
    return _query(
        """
        SELECT id, name, date, description, last_modified
        FROM academic_calendar_events
        WHERE event_type = 'Assignment Deadline'
        ORDER BY last_modified DESC
        LIMIT ?
        """,
        (limit,),
    )
