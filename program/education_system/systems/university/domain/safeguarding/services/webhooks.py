import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
from education_system.systems.university.infrastructure.database.db import (
    sqlite3 as _db_errors,
)
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
from education_system.systems.university.services.operations import (
    OperationResult,
    OperationalIssue,
)


def register_webhook(url, secret, event_filter="*", active=True, actor="system"):
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_webhooks(url, secret, event_filter, active, "
        "created_at) VALUES (?,?,?,?,?)",
        (url, secret, event_filter, 1 if active else 0, now),
    )
    wid = cur.lastrowid
    conn.commit()
    conn.close()
    audit_log(
        actor=actor, action="webhook_register", details=f"id={wid} url={url} filter={event_filter}"
    )
    return wid


def list_webhooks():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, url, event_filter, active, created_at, last_status, "
        "       last_sent_at FROM safeguarding_webhooks ORDER BY id ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def disable_webhook(webhook_id, actor="system"):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE safeguarding_webhooks SET active=0 WHERE id=?", (webhook_id,))
    conn.commit()
    conn.close()
    audit_log(actor=actor, action="webhook_disable", details=f"id={webhook_id}")


def _matches_filter(event, event_filter):
    if not event_filter or event_filter.strip() == "*":
        return True
    return event in {e.strip() for e in event_filter.split(",") if e.strip()}


def emit_webhook_event(event, payload, case_id=None):
    """Deliver an event and return an observable success/degraded outcome."""
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url, secret, event_filter FROM safeguarding_webhooks WHERE active=1"
        )
        hooks = cur.fetchall()
        conn.close()
    except _db_errors.OperationalError as exc:
        return OperationResult.failure(
            OperationalIssue.from_exception(
                exc, component="safeguarding_webhook_registry", retryable=True
            )
        )
    if not hooks:
        return OperationResult.success(0)

    import hmac
    import urllib.request

    body = json.dumps(
        {"event": event, "payload": payload, "ts": datetime.now().isoformat()}
    ).encode("utf-8")
    sent = 0
    issues = []
    for wid, url, secret, event_filter in hooks:
        if not _matches_filter(event, event_filter or "*"):
            continue
        sig = hmac.new((secret or "").encode("utf-8"), body, hashlib.sha256).hexdigest()
        code, resp = None, ""
        try:
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Safeguarding-Event": event,
                    "X-Safeguarding-Signature": f"sha256={sig}",
                },
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                code = r.status
                resp = r.read(2048).decode("utf-8", errors="replace")
        except Exception as e:
            code = -1
            resp = f"{type(e).__name__}: {e}"[:512]
            issues.append(
                OperationalIssue.from_exception(
                    e,
                    component=f"safeguarding_webhook:{wid}",
                    retryable=True,
                )
            )
        now = datetime.now().isoformat()
        try:
            conn = _connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO safeguarding_webhook_deliveries"
                "(webhook_id, case_id, event, payload, sent_at, "
                " response_code, response_body) VALUES (?,?,?,?,?,?,?)",
                (wid, case_id, event, body.decode("utf-8"), now, code, resp),
            )
            cur.execute(
                "UPDATE safeguarding_webhooks SET last_status=?, last_sent_at=? WHERE id=?",
                (str(code), now, wid),
            )
            conn.commit()
            conn.close()
        except _db_errors.OperationalError as exc:
            issues.append(
                OperationalIssue.from_exception(
                    exc,
                    component=f"safeguarding_delivery_store:{wid}",
                    retryable=True,
                )
            )
        sent += 1
    if issues:
        return OperationResult.degraded(sent, *issues)
    return OperationResult.success(sent)


__all__ = [
    "register_webhook",
    "list_webhooks",
    "disable_webhook",
    "_matches_filter",
    "emit_webhook_event",
]
