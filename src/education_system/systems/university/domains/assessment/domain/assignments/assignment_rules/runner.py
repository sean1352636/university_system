"""The scheduled assignment job (``university_jobs``, every 15 minutes), and
telling students when an assignment becomes visible."""

from __future__ import annotations

import logging

from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import (
    jobs,
)

logger = logging.getLogger(__name__)


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def announce(assignment_id, db_path=None) -> None:
    """E-mail the module's students and put the deadline on the calendar. A
    failure here is logged: the assignment is already open."""
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT title, module_code, due_date, description, created_by "
                           "FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return
    title, module, due, description, created_by = row
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_assignment_notification,
        )
        send_assignment_notification(assignment_id, title, module, due, description or "")
    except Exception:
        logger.warning("Could not e-mail students about assignment %s", assignment_id, exc_info=True)
    try:
        from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules.calendar_sync import (
            sync_assignment_to_calendar,
        )
        sync_assignment_to_calendar(assignment_id=assignment_id, title=title, due_date=due,
                                    module_code=module, created_by=str(created_by))
    except Exception:
        logger.warning("Could not add assignment %s to the calendar", assignment_id, exc_info=True)


def _send_reminder(reminder) -> None:
    from education_system.systems.university.infrastructure.email.email_service.core import (
        send_template_email,
    )
    values = {k: v for k, v in reminder.items() if k != "email"}
    send_template_email("assignment_due_reminder", reminder["email"], values)


def run(db_path=None) -> dict:
    """Open scheduled assignments, then send deadline reminders."""
    conn = _connect(db_path)
    try:
        opened = jobs.open_scheduled(conn)
        conn.commit()
        reminders = jobs.due_reminders(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    for assignment_id in opened:
        announce(assignment_id, db_path)
    sent = 0
    for reminder in reminders:
        try:
            _send_reminder(reminder)
            sent += 1
        except Exception:
            logger.warning("Could not send a deadline reminder", exc_info=True)
    return {"opened": len(opened), "reminders": sent}
