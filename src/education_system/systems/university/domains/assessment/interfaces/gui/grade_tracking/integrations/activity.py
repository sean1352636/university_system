"""Activity adapter for the grade-tracking integrations panel.

Same shape as the assignment-side ``activity.py``: each helper
returns the most recent N rows the grade GUI's hooks have produced
in the *other* domain's table.
"""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def _query(sql: str, params: tuple = ()) -> list[dict]:
    try:
        conn = sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("activity query failed: %s", exc)
        return []


def _table_exists(name: str) -> bool:
    return bool(_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ))


def recent_early_warning_indicators(limit: int = 25) -> list[dict]:
    if not _table_exists("early_warning_indicators"):
        return []
    return _query(
        """
        SELECT indicator_id, student_id, indicator_value, severity,
               detected_at, is_resolved, notes
        FROM early_warning_indicators
        WHERE indicator_type = 'grade_risk'
        ORDER BY indicator_id DESC LIMIT ?
        """,
        (limit,),
    )


def recent_wellbeing_referrals(limit: int = 25) -> list[dict]:
    if not _table_exists("wellbeing_referrals"):
        return []
    return _query(
        """
        SELECT id, student_id, referred_by, urgency, status, created_at
        FROM wellbeing_referrals
        WHERE concern_type = 'academic_performance'
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    )


def recent_grade_appeal_tickets(limit: int = 25, actor=None) -> list[dict]:
    """The newest tickets raised by the ``grade_appeal`` channel that the signed-in
    ``actor`` may see (through the support-tickets port; summaries only)."""
    from education_system.systems.university.services.bus import support_tickets_bus
    return support_tickets_bus.recent_tickets(actor, channel="grade_appeal", limit=limit)


def recent_assessment_calendar_events(limit: int = 25) -> list[dict]:
    if not _table_exists("academic_calendar_events"):
        return []
    return _query(
        """
        SELECT id, name, date, description, last_modified
        FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar')
        WHERE event_type = 'Assessment'
        ORDER BY last_modified DESC LIMIT ?
        """,
        (limit,),
    )


def recent_aid_gpa_reviews(limit: int = 25) -> list[dict]:
    if not _table_exists("financial_aid"):
        return []
    return _query(
        """
        SELECT aid_id, student_id, aid_type, amount, status, updated_at, notes
        FROM financial_aid
        WHERE notes LIKE '%[gpa-check%'
        ORDER BY aid_id DESC LIMIT ?
        """,
        (limit,),
    )


def recent_grade_legal_cases(limit: int = 25) -> list[dict]:
    if not _table_exists("legal_cases"):
        return []
    return _query(
        """
        SELECT case_id, case_number, client_id, case_title, status, created_at
        FROM legal_cases
        WHERE case_type = 'grade_audit'
        ORDER BY case_id DESC LIMIT ?
        """,
        (limit,),
    )
