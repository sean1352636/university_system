"""Student-affairs helpdesk adapter — escalate grade disputes to tickets.

The helpdesk's ``create_ticket_with_details`` is wrapped in CLI
input/print code paths, so we insert into ``support_tickets``
directly using the same column shape.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def escalate_dispute_to_helpdesk(
    *,
    user_id: int | str,
    student_id: str,
    dispute_id: int,
    assignment_title: str,
    reason: str,
    priority: str = "medium",
) -> int | None:
    """Create a helpdesk ticket linked to a grade dispute.

    Returns the new ``ticket_id``, or ``None`` if the helpdesk
    schema isn't initialised in this database.
    """
    subject = f"Grade dispute — {assignment_title} (dispute #{dispute_id})"
    message = (
        f"A grade dispute has been filed for assignment "
        f"'{assignment_title}'. Reason from student: {reason}"
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
                logger.debug("support_tickets table missing; skipping helpdesk escalation")
                return None

            cur.execute("PRAGMA table_info(support_tickets)")
            cols = {r[1] for r in cur.fetchall()}

            payload = {
                "user_id": user_id,
                "subject": subject,
                "description": message,
                "category": "Academic Inquiry",
                "priority": priority,
                "impact": "medium",
                "urgency": "medium",
                "status": "open",
                "source": "assignment_dispute",
                "department": "Academic Affairs",
                "created_at": now,
                "updated_at": now,
                "last_activity_at": now,
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
        logger.warning("escalate_dispute_to_helpdesk failed: %s", exc)
        return None
