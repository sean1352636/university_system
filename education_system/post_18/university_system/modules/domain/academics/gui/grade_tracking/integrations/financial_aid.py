"""Financial-aid adapter — flag GPA changes affecting awards.

Updates ``financial_aid.notes`` for the latest active aid record so
finance reviewers can see the current GPA at a glance, and tags the
record as ``status='gpa_review'`` when GPA drops below the
configured threshold (default 2.0). Uses the legacy ``financial_aid``
table directly because ``FinancialAidManager`` operates on
``aid_packages`` / ``aid_components`` and isn't a clean fit for a
GPA-driven side-effect.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

DEFAULT_GPA_THRESHOLD = 2.0


def notify_aid_of_gpa(
    *,
    student_id: str,
    gpa: float,
    threshold: float = DEFAULT_GPA_THRESHOLD,
) -> bool:
    """Tag the student's aid row(s) when GPA drops below threshold.

    Returns True when at least one row was updated. Silently no-ops
    when the table doesn't exist or the student has no aid.
    """
    if not student_id or gpa is None:
        return False
    note_line = (
        f"[gpa-check {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"GPA {gpa:.2f}"
        + (
            f" — below {threshold:.2f} threshold; review eligibility."
            if gpa < threshold else " — meets threshold."
        )
    )
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='financial_aid'"
            ).fetchone()
            if not row:
                return False
            target_status = "gpa_review" if gpa < threshold else None
            if target_status:
                cur.execute(
                    """
                    UPDATE financial_aid
                       SET status = ?,
                           notes = COALESCE(notes || char(10), '') || ?,
                           updated_at = ?
                     WHERE student_id = ? AND status NOT IN ('rejected','closed')
                    """,
                    (target_status, note_line, datetime.now().isoformat(),
                     str(student_id)),
                )
            else:
                cur.execute(
                    """
                    UPDATE financial_aid
                       SET notes = COALESCE(notes || char(10), '') || ?,
                           updated_at = ?
                     WHERE student_id = ? AND status NOT IN ('rejected','closed')
                    """,
                    (note_line, datetime.now().isoformat(), str(student_id)),
                )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("notify_aid_of_gpa failed for %s: %s", student_id, exc)
        return False
