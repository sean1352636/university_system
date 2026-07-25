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

from education_system.systems.university.domain.safeguarding.analysis import (
    RiskCategory,
)
from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)
from education_system.systems.university.domain.safeguarding.permissions import (
    audit_log,
)
from education_system.systems.university.domain.safeguarding.services.notifications import (
    queue_notification,
)
from education_system.systems.university.domain.safeguarding.services.webhooks import (
    emit_webhook_event,
)

MANDATORY_TRIGGER_CATEGORIES = {
    RiskCategory.SELF_HARM,
    RiskCategory.EXPLOITATION,
    RiskCategory.EXTREMISM,
}
MANDATORY_TRIGGER_VULNS = {"Minor (<18)", "PREVENT concern"}


def check_mandatory_reporting(case_id, categories, vulnerability_flags, actor="system"):
    """Flag the case as mandatory if its risk profile crosses the statutory
    threshold and queue a notification to the safeguarding lead inbox."""
    cats = set((categories or {}).keys())
    vulns = set(vulnerability_flags or [])
    triggered = bool(cats & MANDATORY_TRIGGER_CATEGORIES) or bool(vulns & MANDATORY_TRIGGER_VULNS)
    if not triggered:
        return False
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET mandatory_reporting=1, mandatory_status=COALESCE(mandatory_status, 'Pending') "
        "WHERE id=?",
        (case_id,),
    )
    conn.commit()
    conn.close()
    queue_notification(
        "email",
        "safeguarding-lead@example.edu",
        f"[MANDATORY REPORTING] case #{case_id}",
        f"Case #{case_id} meets statutory mandatory-reporting criteria. "
        f"Categories: {sorted(cats)}. Vulnerabilities: {sorted(vulns)}.\n"
        f"Please acknowledge in the Safeguarding portal.",
        case_id=case_id,
    )
    audit_log(
        actor=actor,
        action="mandatory_flag",
        case_id=case_id,
        details=f"cats={sorted(cats)} vulns={sorted(vulns)}",
    )
    return True


def acknowledge_mandatory_report(case_id, actor, external_reference=""):
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET mandatory_status='Reported', mandatory_reported_at=? "
        "WHERE id=? AND mandatory_reporting=1",
        (now, case_id),
    )
    conn.commit()
    conn.close()
    audit_log(
        actor=actor,
        action="mandatory_reported",
        case_id=case_id,
        details=f"ref={external_reference}",
    )
    emit_webhook_event(
        "case.mandatory_reported",
        {"case_id": case_id, "reported_at": now, "external_reference": external_reference},
        case_id=case_id,
    )


def list_mandatory_cases(status=None):
    q = (
        "SELECT id, full_name, username, severity, mandatory_status, "
        "       mandatory_reported_at "
        "FROM safeguarding_submissions WHERE mandatory_reporting=1 "
        "AND COALESCE(purged,0)=0"
    )
    params = []
    if status:
        q += " AND COALESCE(mandatory_status, 'Pending')=?"
        params.append(status)
    q += " ORDER BY submitted_at DESC"
    conn = _connect()
    cur = conn.cursor()
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows


WB_REVIEWER_ROLES = {"audit", "governance", "ombuds", "superadmin"}


def can_view_whistleblowing(user):
    return (user or {}).get("role", "").lower() in WB_REVIEWER_ROLES


def list_whistleblowing_cases(user):
    if not can_view_whistleblowing(user):
        return []
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, username, submitted_at, severity, status, "
        "       wb_independent_reviewer "
        "FROM safeguarding_submissions WHERE whistleblowing=1 "
        "AND COALESCE(purged,0)=0 ORDER BY submitted_at DESC",
    )
    rows = cur.fetchall()
    conn.close()
    audit_log(
        actor=user.get("username", "?"),
        actor_role=user.get("role", "?"),
        action="wb_list",
        details=f"count={len(rows)}",
    )
    return rows


__all__ = [
    "MANDATORY_TRIGGER_CATEGORIES",
    "MANDATORY_TRIGGER_VULNS",
    "check_mandatory_reporting",
    "acknowledge_mandatory_report",
    "list_mandatory_cases",
    "WB_REVIEWER_ROLES",
    "can_view_whistleblowing",
    "list_whistleblowing_cases",
]
