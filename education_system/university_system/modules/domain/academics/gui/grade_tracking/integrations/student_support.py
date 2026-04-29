"""Student support adapter — wellbeing referrals from low grades.

Writes a row into ``wellbeing_referrals`` with concern_type
'academic_performance'. Owned by student_affairs; surfaced to staff
in their support dashboards.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def create_wellbeing_referral(
    *,
    student_id: str,
    referred_by: str | None = None,
    description: str = "",
    urgency: str = "medium",
) -> int | None:
    """Create a wellbeing referral keyed on a low-grade trigger.

    Returns the referral row id, or None if the table is missing.
    """
    if not student_id:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='wellbeing_referrals'"
            ).fetchone()
            if not row:
                return None
            cur.execute(
                """
                INSERT INTO wellbeing_referrals
                    (student_id, referred_by, concern_type, description,
                     urgency, status, created_at, updated_at)
                VALUES (?, ?, 'academic_performance', ?, ?, 'open', ?, ?)
                """,
                (str(student_id), referred_by or "grade_tracking_gui",
                 description, urgency, now, now),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "create_wellbeing_referral failed for %s: %s", student_id, exc,
        )
        return None
