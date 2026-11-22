"""Health Portal e-mails (report summaries, "your record is ready" notices)
and an honest account of what happened to them.

Every health e-mail goes through the university outbox
(``email_service`` → ``outbox_delivery.enqueue``). Whether a message then
reaches the student depends on the outbox delivery mode, so screens never
say "sent" without saying which mode it was queued under:

* ``inbox_only`` — stored in the outbox and the in-app inbox only; nothing
  leaves the university;
* ``sandbox`` — written to the sandbox folder for checking, not sent;
* ``live`` — queued and delivered by the outbox worker (retries, bounces).

Record contents are never e-mailed: the record message is a notice with a
pointer to the portal. Used by the Health Portal GUI and the health CLI.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

REPORT_TYPES = ("Blood Test Results", "Physical Exam", "Vaccination Record", "Medical Clearance")
RECORD_TYPES = ("Complete Health History", "Vaccination Record", "Visit Summary",
                "Emergency Information")
_HEALTH_SUBJECTS = ("%Health%", "%health%")


def delivery_mode() -> str:
    try:
        from education_system.systems.university.infrastructure.email import outbox_delivery
        return outbox_delivery.delivery_mode()
    except Exception:
        logger.debug("Outbox delivery mode unreadable", exc_info=True)
        return "unknown"


def delivery_note(mode: str | None = None) -> str:
    """One sentence on what "sent" means right now."""
    mode = mode or delivery_mode()
    return {
        "inbox_only": "E-mail delivery is off (inbox-only mode): the message is stored in the "
                      "university outbox and in-app inbox, and does not leave the university.",
        "sandbox": "E-mail is in sandbox mode: the message is written to the sandbox folder "
                   "for checking and is not sent.",
        "live": "The message is queued in the university outbox and delivered by the outbox "
                "worker; failures and bounces show in the Email Manager.",
    }.get(mode, "The e-mail outbox could not be read, so delivery is unknown.")


def student_contact(conn, student_id) -> tuple[str, str] | None:
    """``(name, e-mail)`` for a student number, or ``None``."""
    row = conn.execute("SELECT first_name, last_name, email_address FROM students "
                       "WHERE student_id = ?", (str(student_id),)).fetchone()
    if not row:
        return None
    return f"{row[0] or ''} {row[1] or ''}".strip(), row[2] or ""


def send_report_email(email, name, *, title, report_type, summary, practitioner) -> bool:
    """A report summary e-mail (template ``health_report``); True = queued."""
    if not email:
        return False
    from education_system.systems.university.infrastructure.email.email_service import (
        send_template_email,
    )
    return bool(send_template_email("campus_services/health/health_report", email, {
        "patient_name": name,
        "report_title": title or "Health Report",
        "report_type": report_type or "N/A",
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "practitioner": practitioner or "University Health Centre",
        "report_summary": summary or "The full report is in the Health Portal.",
        "next_steps": "Please follow up with your healthcare provider if you have any "
                      "questions about this report.",
    }))


def send_record_notice(email, name, *, record_type, date_range) -> bool:
    """"Your record is ready in the portal" (no record contents); True = queued."""
    if not email:
        return False
    from education_system.systems.university.infrastructure.email.email_service import (
        send_template_email,
    )
    return bool(send_template_email("campus_services/health/health_record_available", email, {
        "patient_name": name,
        "record_type": record_type or "health record",
        "date_range": date_range or "all dates",
        "portal_link": "Health Portal > My Health Records",
    }))


def recent_health_emails(conn, limit=50) -> list[dict]:
    """The latest health e-mails in the outbox with their real status
    (``stored`` / ``queued`` / ``sent`` / ``failed`` / ``suppressed``)."""
    from education_system.systems.university.application.mail import outbox as email_outbox
    email_outbox.ensure(conn)
    cur = conn.execute(
        "SELECT message_id, to_address, subject, status, mode, attempts, last_error, "
        "created_at, sent_at FROM email_outbox WHERE subject LIKE ? OR subject LIKE ? "
        "ORDER BY message_id DESC LIMIT ?", (*_HEALTH_SUBJECTS, int(limit)))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


__all__ = ["REPORT_TYPES", "RECORD_TYPES", "delivery_mode", "delivery_note", "student_contact",
           "send_report_email", "send_record_notice", "recent_health_emails"]
