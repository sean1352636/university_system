"""Helpdesk adapter — file a grade-appeal ticket.

Same shape as the assignment-side dispute path so a single helpdesk
queue can hold appeals from both subsystems. ``source='grade_appeal'``
distinguishes them from the assignment-dispute ticket source.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def file_grade_appeal_ticket(
    *,
    user_id: int | str | None,
    student_id: str,
    module_code: str,
    assessment_name: str,
    current_grade: str | float,
    reason: str,
    priority: str = "medium",
) -> int | None:
    """Open a helpdesk ticket for a grade appeal."""
    subject = f"Grade appeal — {module_code} / {assessment_name}"
    message = (
        f"Student {student_id} is appealing the grade '{current_grade}' "
        f"recorded for assessment '{assessment_name}' in module "
        f"{module_code}.\n\nReason: {reason}"
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='support_tickets'"
            ).fetchone()
            if not row:
                return None
            cur.execute("PRAGMA table_info(support_tickets)")
            cols = {r[1] for r in cur.fetchall()}
            payload = {
                "user_id": user_id,
                "student_id": str(student_id),
                "subject": subject,
                "title": subject,
                "message": message,
                "description": message,
                "category": "Academic Inquiry",
                "priority": priority,
                "impact": "medium",
                "urgency": "medium",
                "status": "open",
                "source": "grade_appeal",
                "department": "Academic Affairs",
                "created_at": now,
                "updated_at": now,
                "last_activity_at": now,
                "created_datetime": now,
                "last_updated_datetime": now,
            }
            usable = {k: v for k, v in payload.items() if k in cols}
            placeholders = ",".join("?" for _ in usable)
            cols_sql = ",".join(usable.keys())
            cur.execute(
                f"INSERT INTO support_tickets ({cols_sql}) VALUES ({placeholders})",
                tuple(usable.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("file_grade_appeal_ticket failed: %s", exc)
        return None
