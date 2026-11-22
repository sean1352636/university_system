"""Study companion reminders: what is due today, sent once a day.

A reminder lists the student's flashcards due for review, today's and missed
plan tasks, exams in the next week and assignment deadlines in the next
three days. It goes to the Hub inbox (``messages``) and, when the student has
asked for it, by email. ``study_companion_reminders`` records each send, so
opening the companion ten times still sends one reminder a day.

There is no background scheduler for the university yet, so reminders go out
when a student opens the companion (their own) and when staff press
*Send reminders* (everyone's). Students turn them off — or on for email — in
the companion's settings (``study_companion_settings``).

Functions take an open connection and do not commit; emails are returned as
``(address, subject, body)`` for the caller to send once committed.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    study_context as ctx,
)

DEFAULT_SETTINGS = {"reminders_enabled": 1, "email_reminders": 0, "share_with_tutor": 1,
                    "daily_card_limit": 20}
EXAM_WINDOW_DAYS = 7
DEADLINE_WINDOW_DAYS = 3


def _today(today=None) -> date:
    if today is None:
        return date.today()
    return today if isinstance(today, date) else date.fromisoformat(str(today)[:10])


# ── settings ────────────────────────────────────────────────────────────


def settings(conn, student_id) -> dict:
    row = conn.execute("SELECT reminders_enabled, email_reminders, share_with_tutor, "
                       "daily_card_limit FROM study_companion_settings WHERE student_id = ?",
                       (str(student_id),)).fetchone()
    if not row:
        return dict(DEFAULT_SETTINGS)
    return dict(zip(DEFAULT_SETTINGS, tuple(row)))


def save_settings(conn, student_id, **values) -> dict:
    current = settings(conn, student_id)
    for key in DEFAULT_SETTINGS:
        if key in values and values[key] is not None:
            current[key] = int(values[key]) if key == "daily_card_limit" else int(bool(values[key]))
    if not 1 <= current["daily_card_limit"] <= 500:
        raise ValueError("Daily card limit is between 1 and 500")
    conn.execute(
        "INSERT INTO study_companion_settings (student_id, reminders_enabled, email_reminders, "
        "share_with_tutor, daily_card_limit, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(student_id) DO UPDATE SET reminders_enabled = excluded.reminders_enabled, "
        "email_reminders = excluded.email_reminders, share_with_tutor = excluded.share_with_tutor, "
        "daily_card_limit = excluded.daily_card_limit, updated_at = excluded.updated_at",
        (str(student_id), current["reminders_enabled"], current["email_reminders"],
         current["share_with_tutor"], current["daily_card_limit"]))
    return current


# ── what is due ─────────────────────────────────────────────────────────


def due_card_count(conn, student_id, today=None) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM flashcards WHERE student_id = ? AND COALESCE(suspended, 0) = 0 "
        "AND (next_review IS NULL OR next_review <= ?)",
        (str(student_id), _today(today).isoformat())).fetchone()
    return int(row[0] or 0)


def _tasks(conn, student_id, where, params) -> list[dict]:
    cur = conn.execute(
        "SELECT t.task_id, t.plan_id, t.task_title, t.scheduled_date, t.duration_minutes, "
        "t.priority, t.module_code, p.plan_name FROM study_plan_tasks t "
        "JOIN study_plans p ON p.plan_id = t.plan_id WHERE p.student_id = ? "
        "AND COALESCE(p.status, 'Active') = 'Active' AND COALESCE(t.status, 'pending') = 'pending' "
        "AND " + where + " ORDER BY t.scheduled_date, t.task_id", (str(student_id), *params))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def today_summary(conn, student_id, today=None) -> dict:
    """Everything the companion would remind the student about today."""
    day = _today(today)
    iso = day.isoformat()
    return {
        "date": iso,
        "due_cards": due_card_count(conn, student_id, day),
        "tasks_today": _tasks(conn, student_id, "t.scheduled_date = ?", (iso,)),
        "overdue_tasks": _tasks(conn, student_id, "t.scheduled_date < ?", (iso,)),
        "exams_soon": ctx.upcoming_exams(conn, student_id, day,
                                         day + timedelta(days=EXAM_WINDOW_DAYS)),
        "deadlines_soon": ctx.upcoming_deadlines(conn, student_id, day,
                                                 day + timedelta(days=DEADLINE_WINDOW_DAYS)),
    }


def message_for(summary) -> tuple[str, str] | None:
    """``(subject, body)`` for a summary, or ``None`` when nothing is due."""
    lines = []
    if summary["due_cards"]:
        lines.append(f"• {summary['due_cards']} flashcard(s) due for review")
    for t in summary["tasks_today"]:
        lines.append(f"• Today: {t['task_title']} ({t['duration_minutes'] or 0} min)")
    if summary["overdue_tasks"]:
        lines.append(f"• {len(summary['overdue_tasks'])} missed plan task(s) — use "
                     "'Reschedule Missed' to fit them back in before your exam")
    for e in summary["exams_soon"]:
        lines.append(f"• Exam {e['date']} {e['start_time'] or ''}: {e['module_code']} "
                     f"{e['name']}".rstrip())
    for d in summary["deadlines_soon"]:
        lines.append(f"• Deadline {str(d['due_date'])[:16]}: {d['module_code']} {d['title']}")
    if not lines:
        return None
    subject = f"Study companion: your plan for {summary['date']}"
    body = ("Here is what your AI Study Companion has for you today:\n\n" + "\n".join(lines)
            + "\n\nYou can turn these reminders off in the companion's Settings tab.")
    return subject, body


def _email_for(conn, student_id):
    for sql in ("SELECT email_address FROM students WHERE student_id = ?",
                "SELECT email FROM users WHERE username = ? OR student_id = ?"):
        try:
            params = (str(student_id),) if sql.count("?") == 1 else (str(student_id),) * 2
            row = conn.execute(sql, params).fetchone()
        except Exception:
            row = None
        if row and row[0] and "@" in str(row[0]):
            return str(row[0])
    return None


def send_for(conn, student_id, today=None) -> dict:
    """Send ``student_id`` today's reminder unless already sent, turned off or
    empty. ``{sent, reason, emails}``."""
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    day = _today(today)
    prefs = settings(conn, student_id)
    if not prefs["reminders_enabled"]:
        return {"sent": False, "reason": "turned off", "emails": []}
    message = message_for(today_summary(conn, student_id, day))
    if message is None:
        return {"sent": False, "reason": "nothing due", "emails": []}
    subject, body = message
    cur = conn.execute("INSERT OR IGNORE INTO study_companion_reminders "
                       "(student_id, reminder_date, kind, summary) VALUES (?, ?, 'daily', ?)",
                       (str(student_id), day.isoformat(), body))
    if not cur.rowcount:
        return {"sent": False, "reason": "already sent today", "emails": []}
    deliver_inbox_message_on(conn, str(student_id), subject, body)
    emails = []
    if prefs["email_reminders"]:
        address = _email_for(conn, student_id)
        if address:
            emails.append((address, subject, body))
    return {"sent": True, "reason": "", "emails": emails}


def companion_users(conn) -> list[str]:
    """Everyone with flashcards or an active study plan."""
    return [r[0] for r in conn.execute(
        "SELECT student_id FROM flashcards UNION SELECT student_id FROM study_plans "
        "WHERE COALESCE(status, 'Active') = 'Active' ORDER BY 1").fetchall()]


def send_all(conn, today=None) -> dict:
    """:func:`send_for` everyone who uses the companion. ``{sent, checked, emails}``."""
    sent, emails, users = 0, [], companion_users(conn)
    for sid in users:
        result = send_for(conn, sid, today)
        sent += int(result["sent"])
        emails += result["emails"]
    return {"sent": sent, "checked": len(users), "emails": emails}
