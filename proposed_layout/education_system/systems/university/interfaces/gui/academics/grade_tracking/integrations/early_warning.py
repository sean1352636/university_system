"""Early warning adapter — auto-flag at-risk students.

Inserts an ``early_warning_indicators`` row when a risk score
crosses the configured threshold. Uses the same table that
``services/early_warning/early_warning_core.IndicatorManager``
manages, so its dashboards and follow-up workflows pick the row up.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def flag_at_risk_student(
    *,
    student_id: str,
    risk_score: int,
    risk_level: str,
    factors_summary: str = "",
) -> int | None:
    """Insert (or refresh) an early-warning indicator for a student.

    Idempotent on the (student_id, indicator_type='grade_risk',
    is_resolved=0) tuple — re-running just updates the severity and
    notes instead of stacking duplicates.
    Returns the indicator_id.
    """
    if not student_id:
        return None
    severity = risk_level.lower() if isinstance(risk_level, str) else "medium"
    notes = f"Risk score: {risk_score}. Factors: {factors_summary}".strip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='early_warning_indicators'"
            ).fetchone()
            if not row:
                return None
            existing = cur.execute(
                """
                SELECT indicator_id FROM early_warning_indicators
                WHERE student_id = ? AND indicator_type = 'grade_risk'
                  AND is_resolved = 0
                ORDER BY indicator_id DESC LIMIT 1
                """,
                (str(student_id),),
            ).fetchone()
            if existing:
                cur.execute(
                    """
                    UPDATE early_warning_indicators
                       SET indicator_value = ?, severity = ?, notes = ?,
                           detected_at = ?
                     WHERE indicator_id = ?
                    """,
                    (str(risk_score), severity, notes, now, existing[0]),
                )
                conn.commit()
                return existing[0]
            cur.execute(
                """
                INSERT INTO early_warning_indicators
                    (student_id, indicator_type, indicator_value, severity,
                     detected_at, is_resolved, notes)
                VALUES (?, 'grade_risk', ?, ?, ?, 0, ?)
                """,
                (str(student_id), str(risk_score), severity, now, notes),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "flag_at_risk_student failed for %s: %s", student_id, exc,
        )
        return None
