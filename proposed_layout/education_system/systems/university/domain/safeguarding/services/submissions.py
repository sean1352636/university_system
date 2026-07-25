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

from education_system.systems.university.domain.safeguarding.crypto import (
    _decrypt_field,
    _encrypt_field,
)
from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)
from education_system.systems.university.domain.safeguarding.permissions import (
    audit_log,
)
from education_system.systems.university.domain.safeguarding.services.analytics import (
    canonical_subject_id,
)
from education_system.systems.university.domain.safeguarding.services.compliance import (
    check_mandatory_reporting,
)
from education_system.systems.university.domain.safeguarding.services.notifications import (
    escalation_notify_dsl,
)
from education_system.systems.university.domain.safeguarding.services.oncall import (
    get_oncall_dsl,
)
from education_system.systems.university.domain.safeguarding.services.retention import (
    _compute_retention_until,
)
from education_system.systems.university.domain.safeguarding.services.risk import (
    compute_risk_score,
    compute_sla_due,
)
from education_system.systems.university.domain.safeguarding.services.webhooks import (
    emit_webhook_event,
)


def save_submission(
    user,
    content,
    severity,
    categories,
    *,
    anonymous=False,
    contact_token_hash=None,
    on_behalf_of=False,
    reporter_username=None,
    subject_relation=None,
    triage=None,
    attachments=None,
    audio_path=None,
    transcription=None,
    language=None,
    consent_disclosure=False,
    consent_contact=False,
    duplicate_of=None,
    vulnerability_flags=None,
    case_location=None,
    case_department=None,
    nlp_score=None,
    nlp_categories=None,
    whistleblowing=False,
    wb_independent_reviewer=None,
):
    """Persist a submission and derive risk/SLA/assignment metadata.

    Returns the new row id. Side-effects (audit-trail assignment row, etc.)
    happen via helpers called below.
    """
    likelihood, impact, risk_score = compute_risk_score(
        severity, triage or {}, vulnerability_flags or []
    )
    sla_due = compute_sla_due(severity)
    subject_id = canonical_subject_id(user, anonymous=anonymous)
    oncall = get_oncall_dsl()
    assignee = oncall.get("username") if oncall else None
    now = datetime.now().isoformat()

    # Feature 37 — field-level encryption of the free-text content and
    # any transcription. Toggle via FIELD_ENCRYPTION_ENABLED below.
    content_blob, content_encrypted = _encrypt_field(content)
    trans_blob, trans_encrypted = _encrypt_field(transcription)
    if content_encrypted:
        stored_content = ""  # raw text not held in plaintext
    else:
        stored_content = content
    if trans_encrypted:
        stored_transcription = None
    else:
        stored_transcription = transcription

    # Feature 39 — provisional retention horizon set on intake; recomputed on
    # closure (longer/shorter horizon depending on outcome severity).
    retention_until = _compute_retention_until(severity, outcome=None)

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_submissions"
        "(username, full_name, role, content, submitted_at, severity, categories,"
        " anonymous, contact_token, on_behalf_of, reporter_username, subject_relation,"
        " triage, attachments, audio_path, transcription, language,"
        " consent_disclosure, consent_contact, duplicate_of,"
        " likelihood, impact, risk_score, nlp_score, nlp_categories,"
        " sla_due_at, sla_breached, assigned_to, assigned_at,"
        " linked_subject_id, vulnerability_flags, lifecycle_state,"
        " case_location, case_department,"
        " content_encrypted, content_blob,"
        " transcription_encrypted, transcription_blob, retention_until) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            user.get("username") or "",
            user.get("full_name") or "",
            user.get("role") or "",
            stored_content,
            now,
            severity,
            json.dumps(categories),
            1 if anonymous else 0,
            contact_token_hash,
            1 if on_behalf_of else 0,
            reporter_username,
            subject_relation,
            json.dumps(triage) if triage else None,
            json.dumps(attachments) if attachments else None,
            audio_path,
            stored_transcription,
            language,
            1 if consent_disclosure else 0,
            1 if consent_contact else 0,
            duplicate_of,
            likelihood,
            impact,
            risk_score,
            nlp_score,
            json.dumps(nlp_categories) if nlp_categories else None,
            sla_due.isoformat() if sla_due else None,
            0,
            assignee,
            now if assignee else None,
            subject_id,
            json.dumps(vulnerability_flags) if vulnerability_flags else None,
            "Triage" if severity in ("CRITICAL", "HIGH") else "Open",
            case_location,
            case_department,
            1 if content_encrypted else 0,
            content_blob,
            1 if trans_encrypted else 0,
            trans_blob,
            retention_until.isoformat() if retention_until else None,
        ),
    )
    sid = cur.lastrowid
    if assignee:
        cur.execute(
            "INSERT INTO safeguarding_assignments(case_id, assignee, assigned_by, "
            "assigned_at, note) VALUES (?,?,?,?,?)",
            (sid, assignee, "auto-rota", now, "Auto-assigned via on-call rota"),
        )
    conn.commit()
    conn.close()

    # Feature 42 — whistleblowing flag is set on a separate update so the
    # main INSERT stays compact. Whistleblowing rows are hidden from regular
    # staff lists and routed to the named independent reviewer instead.
    if whistleblowing:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE safeguarding_submissions "
            "SET whistleblowing=1, wb_independent_reviewer=?, assigned_to=?, "
            "    assigned_at=? WHERE id=?",
            (
                wb_independent_reviewer,
                wb_independent_reviewer or None,
                now if wb_independent_reviewer else None,
                sid,
            ),
        )
        conn.commit()
        conn.close()

    # Audit + escalation side-effects (features 31, 32, 38)
    audit_log(
        actor=(reporter_username or user.get("username") or "anon"),
        actor_role=user.get("role") or "student",
        action="create",
        case_id=sid,
        details=f"severity={severity} risk={risk_score} wb={1 if whistleblowing else 0}",
    )
    if severity == "CRITICAL":
        escalation_notify_dsl(sid, severity, assignee, oncall)

    # Feature 41 — mandatory-reporting check (KCSIE / Prevent)
    check_mandatory_reporting(
        sid, categories, vulnerability_flags or [], actor=user.get("username") or "system"
    )

    # Feature 48 — emit case.created webhook to any registered SIEM endpoint
    emit_webhook_event(
        "case.created",
        {
            "case_id": sid,
            "severity": severity,
            "risk_score": risk_score,
            "categories": list(categories.keys()) if categories else [],
            "anonymous": bool(anonymous),
            "whistleblowing": bool(whistleblowing),
            "submitted_at": now,
        },
        case_id=sid,
    )

    return sid


def resolve_content(case_id):
    """Return the decrypted content + transcription for a case row."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT content, content_encrypted, content_blob, "
        "       transcription, transcription_encrypted, transcription_blob "
        "FROM safeguarding_submissions WHERE id=?",
        (case_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return "", ""
    c_pt, c_enc, c_bl, t_pt, t_enc, t_bl = row
    content = _decrypt_field(c_bl) if c_enc else (c_pt or "")
    trans = _decrypt_field(t_bl) if t_enc else (t_pt or "")
    return content, trans


def issue_contact_token() -> tuple[str, str]:
    """Return (raw_token_for_user, sha256_hash_for_db)."""
    raw = secrets.token_urlsafe(9)  # e.g. "Xy3-aBcD9_kL"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, h


def lookup_by_contact_token(raw_token: str):
    """Return the submission row matching this raw anonymous follow-up token."""
    if not raw_token:
        return None
    h = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, submitted_at, severity, status, review_note "
        "FROM safeguarding_submissions WHERE contact_token=?",
        (h,),
    )
    row = cur.fetchone()
    conn.close()
    return row


_DUP_WINDOW_DAYS = 30
_DUP_RATIO = 0.85


def find_duplicate(username: str, content: str) -> int | None:
    """Return the ID of a recent very-similar submission by the same author, if any."""
    if not username or not content:
        return None
    norm = re.sub(r"\s+", " ", content.strip().lower())
    if len(norm) < 20:
        return None
    cutoff = (datetime.now() - timedelta(days=_DUP_WINDOW_DAYS)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content FROM safeguarding_submissions "
        "WHERE username=? AND submitted_at>=? ORDER BY id DESC LIMIT 25",
        (username, cutoff),
    )
    rows = cur.fetchall()
    conn.close()
    for sid, prev in rows:
        prev_norm = re.sub(r"\s+", " ", (prev or "").strip().lower())
        if not prev_norm:
            continue
        if SequenceMatcher(None, norm, prev_norm).ratio() >= _DUP_RATIO:
            return sid
    return None


def fetch_submissions(
    status_filter=None, severity_filter=None, lifecycle_filter=None, include_whistleblowing=False
):
    """Return rows shaped like the previous version expected:
    (id, full_name, username, submitted_at, severity, categories,
     status, content, reviewer, review_note, reviewed_at)."""
    conn = _connect()
    cur = conn.cursor()
    q = """SELECT id, full_name, username, submitted_at,
                  severity, categories, status, content,
                  reviewer, review_note, reviewed_at
           FROM safeguarding_submissions WHERE 1=1"""
    params = []
    if status_filter and status_filter != "All":
        q += " AND status = ?"
        params.append(status_filter)
    if severity_filter and severity_filter != "All":
        q += " AND severity = ?"
        params.append(severity_filter)
    if lifecycle_filter and lifecycle_filter != "All":
        q += " AND lifecycle_state = ?"
        params.append(lifecycle_filter)
    if not include_whistleblowing:
        q += " AND COALESCE(whistleblowing, 0) = 0"
    q += " AND COALESCE(purged, 0) = 0"
    q += (
        " ORDER BY CASE severity "
        "WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 "
        "WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 ELSE 5 END, "
        "submitted_at DESC"
    )
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_submission_status(sub_id, status, reviewer, note):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET status=?, reviewer=?, review_note=?, reviewed_at=? "
        "WHERE id=?",
        (status, reviewer, note, datetime.now().isoformat(), sub_id),
    )
    conn.commit()
    conn.close()


def fetch_user_submissions(username):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, submitted_at, severity, status FROM safeguarding_submissions "
        "WHERE username=? ORDER BY submitted_at DESC",
        (username,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_submission(case_id):
    """Return a single case as a dict of its non-blob columns, or None.

    Free-text `content`/`transcription` are excluded — use `resolve_content`
    to fetch (and decrypt) those with the appropriate audit trail."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, full_name, role, submitted_at, severity, categories,"
        " status, reviewer, review_note, reviewed_at, lifecycle_state, risk_score,"
        " likelihood, impact, assigned_to, assigned_at, sla_due_at, sla_breached,"
        " outcome_code, closure_reason, case_location, case_department, anonymous,"
        " on_behalf_of, mandatory_reporting, mandatory_status, retention_until,"
        " next_review_at, purged"
        " FROM safeguarding_submissions WHERE id=?",
        (case_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


__all__ = [
    "save_submission",
    "resolve_content",
    "issue_contact_token",
    "lookup_by_contact_token",
    "_DUP_WINDOW_DAYS",
    "_DUP_RATIO",
    "find_duplicate",
    "fetch_submissions",
    "update_submission_status",
    "fetch_user_submissions",
    "get_submission",
]
