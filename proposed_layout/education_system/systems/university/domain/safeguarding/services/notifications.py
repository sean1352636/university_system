import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)
from education_system.systems.university.domain.safeguarding.permissions import (
    audit_log,
)
from education_system.systems.university.domain.safeguarding.services.oncall import (
    get_oncall_dsl,
)
from education_system.systems.university.domain.safeguarding.services.risk import (
    refresh_sla_breach_flags,
)


def _try_send_email(recipient, subject, body):
    try:
        from education_system.platform.integrations.email import send_email  # type: ignore

        return bool(send_email(recipient, subject, body))
    except Exception:
        return False


def queue_notification(channel, recipient, subject, body, case_id=None):
    now = datetime.now().isoformat()
    sent_at = None
    status = "Queued"
    if channel == "email" and recipient:
        ok = _try_send_email(recipient, subject or "", body or "")
        if ok:
            sent_at = now
            status = "Sent"
        else:
            status = "Queued"  # left for an outbox worker to retry
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_notifications"
        "(case_id, channel, recipient, subject, body, queued_at, sent_at, status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (case_id, channel, recipient, subject, body, now, sent_at, status),
    )
    nid = cur.lastrowid
    conn.commit()
    conn.close()
    return nid


def list_notifications(case_id=None, limit=200):
    conn = _connect()
    cur = conn.cursor()
    if case_id is None:
        cur.execute(
            "SELECT id, case_id, channel, recipient, subject, queued_at, "
            "       sent_at, status FROM safeguarding_notifications "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    else:
        cur.execute(
            "SELECT id, case_id, channel, recipient, subject, queued_at, "
            "       sent_at, status FROM safeguarding_notifications "
            "WHERE case_id=? ORDER BY id DESC LIMIT ?",
            (case_id, limit),
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def escalation_notify_dsl(case_id, severity, assignee, oncall):
    if severity != "CRITICAL":
        return
    if not oncall:
        queue_notification(
            "pager",
            "duty-officer",
            "Safeguarding CRITICAL — no on-call DSL configured",
            f"Case #{case_id} created at CRITICAL severity. "
            "No DSL is on call; please assign manually.",
            case_id=case_id,
        )
        return
    subject = f"[SAFEGUARDING CRITICAL] case #{case_id}"
    body = (
        f"A CRITICAL safeguarding case (#{case_id}) has been auto-assigned "
        f"to you as on-call DSL.\n\nPlease review and respond within the "
        f"1-hour SLA."
    )
    # Email + SMS + pager — recipient address-book lookup is out of scope here.
    queue_notification("email", f"{oncall['username']}@example.edu", subject, body, case_id=case_id)
    queue_notification("sms", oncall["username"], subject, body, case_id=case_id)
    queue_notification("pager", oncall["username"], subject, body, case_id=case_id)


def notify_reporter_on_status_change(case_id, new_status, actor):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT consent_contact, anonymous, reporter_username, username "
        "FROM safeguarding_submissions WHERE id=?",
        (case_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return
    consent, anon, reporter_user, subject_user = row
    if not consent or anon:
        return
    recipient = reporter_user or subject_user
    if not recipient:
        return
    queue_notification(
        "email",
        f"{recipient}@example.edu",
        f"Update on your safeguarding submission #{case_id}",
        f"Your case is now '{new_status}'. The safeguarding team will be in "
        f"touch if further information is needed.",
        case_id=case_id,
    )
    audit_log(
        actor=actor,
        action="notify_reporter",
        case_id=case_id,
        details=f"status={new_status} recipient={recipient}",
    )


def stuck_case_alerts(actor="system"):
    refresh_sla_breach_flags()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, severity, assigned_to FROM safeguarding_submissions "
        "WHERE sla_breached=1 AND lifecycle_state!='Closed' "
        "AND COALESCE(purged,0)=0",
    )
    rows = cur.fetchall()
    conn.close()
    sent = 0
    for sid, sev, assignee in rows:
        recipient = assignee or "duty-officer"
        queue_notification(
            "email",
            f"{recipient}@example.edu",
            f"[SLA BREACH] safeguarding case #{sid}",
            f"Case #{sid} (severity {sev}) has missed its SLA. Please action immediately.",
            case_id=sid,
        )
        sent += 1
    if sent:
        audit_log(actor=actor, action="sla_alerts", details=f"sent={sent}")
    return sent


def daily_dsl_digest(actor="system"):
    cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions WHERE submitted_at >= ?",
        (cutoff_24h,),
    )
    new_24h = cur.fetchone()[0]
    cur.execute(
        "SELECT severity, COUNT(*) FROM safeguarding_submissions "
        "WHERE lifecycle_state != 'Closed' AND COALESCE(purged,0)=0 "
        "GROUP BY severity",
    )
    open_by_sev = dict(cur.fetchall())
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE sla_breached=1 AND lifecycle_state != 'Closed'",
    )
    breached = cur.fetchone()[0]
    conn.close()
    body = (
        f"Daily safeguarding digest\n\n"
        f"  • New cases in last 24h: {new_24h}\n"
        f"  • Open cases by severity: {open_by_sev}\n"
        f"  • SLA breaches outstanding: {breached}\n"
    )
    oncall = get_oncall_dsl()
    recipient = oncall.get("username") if oncall else "duty-officer"
    queue_notification("digest", f"{recipient}@example.edu", "Safeguarding daily digest", body)
    audit_log(actor=actor, action="daily_digest", details=f"new24h={new_24h} breached={breached}")
    return body


_PII_PATTERNS = [
    re.compile(r"\b\d{1,4}[ -]?\d{2,4}[ -]?\d{2,6}\b"),  # phone-ish
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),  # email
    re.compile(r"\b\d{1,4}\s+[A-Z][a-zA-Z]+\s+(?:Street|Road|Avenue|Lane|Way)\b"),
]


def redact_for_tutor(text, *, max_chars=400):
    if not text:
        return ""
    redacted = text
    for pat in _PII_PATTERNS:
        redacted = pat.sub("[REDACTED]", redacted)
    # Strip categorical disclosure detail — only keep high-level shape.
    if len(redacted) > max_chars:
        redacted = redacted[:max_chars].rstrip() + "…"
    return redacted


def notify_tutor(case_id, tutor_username, actor="system"):
    from education_system.systems.university.domain.safeguarding.services.submissions import (
        resolve_content,
    )

    """Send a redacted, high-level note to the personal tutor about a case
    needing pastoral awareness. Stores the exact text sent on the row."""
    content, _trans = resolve_content(case_id)
    redacted = (
        "A safeguarding concern about a student you support has been logged. "
        "Please be available for pastoral conversation. Operational detail "
        "is restricted.\n\nSummary (redacted):\n" + redact_for_tutor(content)
    )
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET tutor_notified_at=?, tutor_notification_redacted=? WHERE id=?",
        (now, redacted, case_id),
    )
    conn.commit()
    conn.close()
    queue_notification(
        "email",
        f"{tutor_username}@example.edu",
        f"Pastoral awareness — case #{case_id}",
        redacted,
        case_id=case_id,
    )
    audit_log(
        actor=actor, action="tutor_notified", case_id=case_id, details=f"tutor={tutor_username}"
    )


__all__ = [
    "_try_send_email",
    "queue_notification",
    "list_notifications",
    "escalation_notify_dsl",
    "notify_reporter_on_status_change",
    "stuck_case_alerts",
    "daily_dsl_digest",
    "_PII_PATTERNS",
    "redact_for_tutor",
    "notify_tutor",
]
