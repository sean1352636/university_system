"""What the hourly assignment job does: open scheduled assignments and work
out who is owed a deadline reminder. Sending happens after the commit, so each
returns what to send."""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import (
    submitting,
    visibility,
)


def open_scheduled(conn, now=None) -> list[int]:
    return visibility.publish_due(conn, now)


def _when_left(due: datetime, now: datetime) -> str:
    hours = max((due - now).total_seconds() / 3600, 0)
    if hours < 24:
        return f"in {max(int(hours), 1)} hour(s)"
    return f"in {round(hours / 24)} day(s)"


def due_reminders(conn, now=None) -> list[dict]:
    """Students owed a reminder: enrolled, not yet submitted, within the
    assignment's reminder period. Each is recorded so they get only one."""
    now = now or datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    assignments = conn.execute(
        "SELECT a.id, a.title, a.module_code, a.due_date, a.reminder_days, m.module_name "
        "FROM assignments a LEFT JOIN modules m ON m.module_code = a.module_code "
        "WHERE a.is_active = 1 AND COALESCE(a.reminder_days, 0) > 0 AND a.due_date > ? "
        "AND COALESCE(a.assignment_type, '') <> 'quiz'", (stamp,)).fetchall()
    out: list[dict] = []
    # Recorded after the loop: the mitigating-circumstances lookup in
    # effective_due opens its own connection and would wait on an open write.
    sent: list[tuple] = []
    for aid, title, module, due_text, days, module_name in assignments:
        due = visibility.parse_when(due_text)
        if not due or due - now > timedelta(days=int(days)):
            continue
        students = conn.execute(
            "SELECT DISTINCT st.student_id, st.first_name, st.last_name, st.email_address "
            "FROM student_modules sm JOIN students st ON st.student_id = sm.student_id "
            "WHERE sm.module_code = ? AND COALESCE(st.email_address, '') <> '' "
            "AND NOT EXISTS (SELECT 1 FROM assignment_reminders_sent r "
            "WHERE r.assignment_id = ? AND r.student_id = st.student_id) "
            "AND NOT EXISTS (SELECT 1 FROM assignment_submissions s WHERE s.assignment_id = ? "
            "AND s.student_id = st.student_id AND COALESCE(s.status, '') <> 'withdrawn')",
            (module, aid, aid)).fetchall()
        for sid, first, last, email in students:
            # Someone with an extension is reminded nearer their own deadline.
            own_due = submitting.effective_due(conn, aid, sid, due_text) or due
            if own_due - now > timedelta(days=int(days)):
                continue
            sent.append((aid, sid, stamp))
            out.append({"email": email, "student_name": f"{first or ''} {last or ''}".strip(),
                        "assignment_title": title, "module_code": module,
                        "module_name": module_name or "",
                        "due_date": own_due.strftime("%Y-%m-%d %H:%M"),
                        "days_until_due": _when_left(own_due, now)})
    conn.executemany("INSERT OR IGNORE INTO assignment_reminders_sent (assignment_id, "
                     "student_id, sent_at) VALUES (?, ?, ?)", sent)
    return out
