"""Email as a universal bus subscriber.

Every domain has been sending one-off emails of its own. This
module is the bridge: it subscribes to ~12 cross-domain events,
checks the recipient's per-event opt-in preference, renders a
template, and logs the send to ``email_log`` (which already exists).

Public surface:

* ``set_pref(user_id, event_kind, enabled)`` — opt-in/out per event.
* ``get_prefs(user_id)`` — list current prefs (defaults to all-on).
* ``send_templated(user_id, template_id, context, *, related_to=)``
  — explicit ad-hoc send (templated; logs + publishes EVENT_EMAIL_SENT).
* ``register_subscribers()`` — wire bus subscriptions; called once at
  module import. Idempotent.

The actual SMTP send is delegated to the existing email service when
available; otherwise this module logs the attempt only. The bus
event ``EVENT_EMAIL_SENT`` fires either way so chain-of-custody
panels (DM evidence) can pick it up.

Includes the chatbot-inbox symmetry hook: a small helper
``mirror_inbox_to_email(user_id, message, source)`` that lets
``chatbot_inbox`` post to email as well when a pref is enabled.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Iterable

from education_system.systems.university.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


# Default prefs: every event is on unless the user opts out. This list
# also drives ``register_subscribers``.
_TRACKED_EVENTS = (
    "finance.charge.raised",
    "finance.hold.changed",
    "library.loan.changed",
    "case.opened",
    "case.sanction.applied",
    "careers.engagement.started",
    "careers.hours.logged",
    "careers.job.posted",
    "trip.registration.changed",
    "parking.violation",
    "hs.incident.logged",
    "su.advocacy.requested",
    # Exam lifecycle. integration_bus publishes these with action=
    # 'published' / 'graded' / 'pending_grade' so a single template
    # entry per event_kind covers each shape.
    "exam.scheduled",
    "exam.graded",
    "exam.pending_grade",
    "exam.room_conflict",
    "finance.report.sent",
    "mail.overdue",
)


_PREFS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS email_preferences (
    user_id     TEXT NOT NULL,
    event_kind  TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, event_kind)
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_email_prefs_user "
    "ON email_preferences(user_id)",
)


def _ensure_prefs(conn: sqlite3.Connection) -> None:
    conn.executescript(_PREFS_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def set_pref(user_id: str | int, event_kind: str, enabled: bool) -> bool:
    if not user_id or not event_kind:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            _ensure_prefs(conn)
            conn.execute(
                "INSERT INTO email_preferences "
                "(user_id, event_kind, enabled, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, event_kind) DO UPDATE "
                "  SET enabled = excluded.enabled, "
                "      updated_at = excluded.updated_at",
                (str(user_id), event_kind, 1 if enabled else 0, now),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("set_pref(%s, %s) failed: %s",
                       user_id, event_kind, exc)
        return False


def is_enabled(user_id: str | int, event_kind: str) -> bool:
    """Default-on: only opt-out rows return False."""
    if not user_id or not event_kind:
        return False
    try:
        with get_connection() as conn:
            _ensure_prefs(conn)
            row = conn.execute(
                "SELECT enabled FROM email_preferences "
                "WHERE user_id = ? AND event_kind = ? LIMIT 1",
                (str(user_id), event_kind),
            ).fetchone()
            return bool(row[0]) if row else True
    except Exception:
        return True


def get_prefs(user_id: str | int) -> dict[str, bool]:
    out: dict[str, bool] = {evt: True for evt in _TRACKED_EVENTS}
    if not user_id:
        return out
    try:
        with get_connection() as conn:
            _ensure_prefs(conn)
            for r in conn.execute(
                "SELECT event_kind, enabled FROM email_preferences "
                "WHERE user_id = ?",
                (str(user_id),),
            ).fetchall():
                out[r["event_kind"]] = bool(r["enabled"])
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Templating + delivery
# ---------------------------------------------------------------------------

# Lightweight built-in templates keyed by event_kind. Each value is
# ``(subject_template, body_template)`` with ``{key}`` placeholders
# filled from the bus payload.
_BUILTIN_TEMPLATES: dict[str, tuple[str, str]] = {
    "finance.charge.raised": (
        "Charge added: £{amount}",
        "A charge of £{amount} was added to your account "
        "({source}). Description: {description}.",
    ),
    "finance.hold.changed": (
        "Finance hold {action}",
        "An action ({action}) was recorded on a finance hold "
        "({reason}). Source: {source}.",
    ),
    "library.loan.changed": (
        "Library: {action}",
        "Loan #{loan_id} change: {action}. Fine: £{fine_amount}.",
    ),
    "case.opened": (
        "Case opened: #{case_id}",
        "A {kind} case (#{case_id}, {severity}) has been opened. "
        "Please check the relevant portal for details.",
    ),
    "case.sanction.applied": (
        "Sanction applied",
        "A {sanction_type} sanction was recorded against case "
        "#{case_id}. Reason: {reason}.",
    ),
    "careers.engagement.started": (
        "Engagement started",
        "A new {kind} engagement has been recorded for you "
        "(role: {role}). Required hours: {hours_required}.",
    ),
    "careers.hours.logged": (
        "Hours logged: {hours}",
        "{hours} hours logged on engagement #{engagement_id}. "
        "Total to date: {hours_logged}.",
    ),
    "careers.job.posted": (
        "New job: {job_title}",
        "{company_name} posted '{job_title}'.",
    ),
    "trip.registration.changed": (
        "Trip registration {action}",
        "Trip #{trip_id} registration: {action}.",
    ),
    "parking.violation": (
        "Parking violation: £{fine_amount}",
        "Vehicle {plate}: {kind} — fine £{fine_amount}.",
    ),
    "hs.incident.logged": (
        "Incident logged",
        "Incident #{incident_id} ({severity}) at {location}.",
    ),
    "su.advocacy.requested": (
        "SU advocacy requested",
        "Advocacy request #{request_id} on case #{case_id} "
        "({case_kind}).",
    ),
    "exam.scheduled": (
        "Exam scheduled: {exam_title}",
        "Exam '{exam_title}' (module {module_code}) is scheduled "
        "for {start_time}. Duration: {duration_minutes} min. "
        "Pass mark: {pass_mark}%.",
    ),
    "exam.graded": (
        "Exam result: {exam_title}",
        "Your attempt on '{exam_title}' has been graded. "
        "Score: {score}/{total_marks} ({percentage}%). "
        "Result: {result}.",
    ),
    "exam.pending_grade": (
        "Reminder: ungraded attempts on {exam_title}",
        "{count} attempts on '{exam_title}' are still awaiting "
        "manual grading (oldest: {oldest_submitted}). Please "
        "complete grading in the Exam portal.",
    ),
    "exam.room_conflict": (
        "Exam room conflict: {exam_title}",
        "Module reschedule for {module_code} now collides with "
        "exam '{exam_title}' on {when}. Please review the "
        "timetable.",
    ),
    "finance.report.sent": (
        "Finance report: {report_title}",
        "{report_title} generated {generated_at}.\n\n{summary}",
    ),
    "mail.overdue": (
        "Mail awaiting collection: {tracking_number}",
        "Your package {tracking_number} has been held {days_over} day(s) "
        "past the free-storage window. A storage fee of £{amount} has "
        "been added to your finance account. Please collect it from the "
        "mail room.",
    ),
}


def _resolve_recipient_email(user_id: str | int) -> str | None:
    """Walk students → users → staff to find an email."""
    sid = str(user_id)
    try:
        with get_connection() as conn:
            for sql in (
                "SELECT email_address FROM students WHERE student_id = ? LIMIT 1",
                "SELECT email FROM users WHERE id = ? OR username = ? LIMIT 1",
                "SELECT email FROM staff WHERE id = ? OR username = ? LIMIT 1",
            ):
                if "?" in sql and sql.count("?") == 2:
                    row = conn.execute(sql, (sid, sid)).fetchone()
                else:
                    row = conn.execute(sql, (sid,)).fetchone()
                if row and row[0]:
                    return row[0]
    except Exception:
        pass
    return None


def _render(template: str, context: dict[str, Any]) -> str:
    """Fill {key} placeholders, surviving missing keys gracefully."""
    class _Defaultable(dict):
        def __missing__(self, key):
            return f"{{{key}}}"
    try:
        return template.format_map(_Defaultable(context))
    except Exception:
        return template


def _attempt_send(recipient: str, subject: str, body: str) -> bool:
    """Best-effort delegation to the existing email service.

    Returns True if a real send happened, False if we only logged.
    """
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        return bool(send_email(recipient, subject, body))
    except Exception:
        # Fall through to logging-only mode.
        return False


def send_templated(user_id: str | int, event_kind: str,
                   context: dict[str, Any] | None = None,
                   *, related_to: str | None = None,
                   force: bool = False) -> str | None:
    """Render + send (best-effort) + log + publish ``email.sent``.

    Returns the message_id on success. Honours user prefs unless
    ``force=True``.
    """
    if not user_id or not event_kind:
        return None
    if not force and not is_enabled(user_id, event_kind):
        return None

    payload = dict(context or {})
    template = _BUILTIN_TEMPLATES.get(event_kind)
    if not template:
        # Generic fallback so brand-new event kinds still get an email.
        template = (f"Notification: {event_kind}",
                    f"Event {event_kind} payload: {json.dumps(payload)[:400]}")
    subject = _render(template[0], payload)
    body = _render(template[1], payload)

    recipient = _resolve_recipient_email(user_id) or ""
    delivered = bool(recipient) and _attempt_send(recipient, subject, body)

    msg_id = uuid.uuid4().hex
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO email_log "
                "(recipient, subject, message, sent_date, status, "
                " related_to, student_id, template_name, sent_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (recipient, subject, body, now,
                 "sent" if delivered else "queued",
                 related_to, str(user_id), event_kind, now),
            )
            conn.commit()
    except Exception:
        logger.warning(
            "Failed to write comms_log for recipient=%s subject=%s",
            recipient, subject, exc_info=True)

    # Auto-link to a case evidence pack when the event carries one.
    if payload.get("case_id"):
        try:
            from education_system.systems.university.services.bus.document_bus import (
                publish_document_changed,
            )
            publish_document_changed(
                document_id=None, action="email_logged",
                domain="case", ref_id=str(payload["case_id"]),
                event_kind=event_kind, msg_id=msg_id,
            )
        except Exception:
            pass

    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import (
            publish,
        )
        publish("email.sent",
                msg_id=msg_id, user_id=str(user_id),
                event_kind=event_kind, recipient=recipient,
                delivered=delivered, related_to=related_to)
    except Exception:
        pass
    return msg_id


def mirror_inbox_to_email(user_id: str | int, message: str,
                          *, source: str = "chatbot") -> bool:
    """Optional companion to ``chatbot_inbox.queue_message_for``.

    Sends the same message via email when the user has opted in
    (``event_kind='chatbot_inbox'``). Defaults to opt-IN — pass
    ``set_pref(user_id, 'chatbot_inbox', False)`` to silence.
    """
    if not is_enabled(user_id, "chatbot_inbox"):
        return False
    return bool(send_templated(
        user_id, "chatbot_inbox",
        {"message": message, "source": source},
    ))


# ---------------------------------------------------------------------------
# Bus subscriptions — wired at module import (idempotent)
# ---------------------------------------------------------------------------

_subscribed = False


def register_subscribers() -> None:
    """Subscribe to every tracked event so each fires an email when
    the user has it enabled. Idempotent — repeated calls are no-ops."""
    global _subscribed
    if _subscribed:
        return
    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import (
            subscribe,
        )
    except Exception:
        return

    def _make_handler(event_kind: str):
        def _handler(**payload):
            uid = (payload.get("user_id")
                   or payload.get("student_id")
                   or payload.get("subject_id")
                   or payload.get("holder_id")
                   or payload.get("staff_id"))
            if not uid:
                return
            try:
                send_templated(uid, event_kind, payload,
                               related_to=payload.get("reference_id"))
            except Exception as exc:
                logger.debug("email handler %s failed: %s",
                             event_kind, exc)
        return _handler

    for evt in _TRACKED_EVENTS:
        try:
            subscribe(evt, _make_handler(evt))
        except Exception:
            pass
    _subscribed = True


# Auto-wire on import. Cheap (one Lock take + len(_TRACKED_EVENTS) appends).
register_subscribers()


__all__ = [
    "set_pref", "is_enabled", "get_prefs",
    "send_templated", "mirror_inbox_to_email",
    "register_subscribers",
]
