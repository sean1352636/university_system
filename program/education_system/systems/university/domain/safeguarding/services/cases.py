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
    analyse_text,
)
from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)
from education_system.systems.university.domain.safeguarding.permissions import (
    audit_log,
)
from education_system.systems.university.domain.safeguarding.services.retention import (
    _compute_retention_until_for_id,
)
from education_system.systems.university.domain.safeguarding.services.submissions import (
    save_submission,
)

_LIFECYCLE_STATES = ("Open", "Triage", "Action", "Monitoring", "Closed")


def set_lifecycle_state(case_id, state, actor=""):
    if state not in _LIFECYCLE_STATES:
        raise ValueError(f"Invalid lifecycle state: {state}")
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET lifecycle_state=? WHERE id=?", (state, case_id)
    )
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) VALUES (?,?,?,?)",
        (
            case_id,
            actor or "system",
            f"[lifecycle] state changed to {state}",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def assign_case(case_id, assignee, assigned_by, note=""):
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET assigned_to=?, assigned_at=? WHERE id=?",
        (assignee, now, case_id),
    )
    cur.execute(
        "INSERT INTO safeguarding_assignments(case_id, assignee, assigned_by, "
        "assigned_at, note) VALUES (?,?,?,?,?)",
        (case_id, assignee, assigned_by or "?", now, note or None),
    )
    conn.commit()
    conn.close()


def list_assignments(case_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT assignee, assigned_by, assigned_at, note "
        "FROM safeguarding_assignments WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_case_note(case_id, author, note):
    """Append-only — there's no update or delete API on purpose."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) VALUES (?,?,?,?)",
        (case_id, author or "?", note, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def list_case_notes(case_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT author, note, created_at FROM safeguarding_case_notes "
        "WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_action_item(case_id, title, owner, due_date):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_action_items"
        "(case_id, title, owner, due_date, created_at) "
        "VALUES (?,?,?,?,?)",
        (case_id, title, owner or None, due_date or None, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def list_action_items(case_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, owner, due_date, status, completed_at "
        "FROM safeguarding_action_items WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def complete_action_item(item_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_action_items SET status='Done', completed_at=? WHERE id=?",
        (datetime.now().isoformat(), item_id),
    )
    conn.commit()
    conn.close()


def add_referral(case_id, agency, contact, reference_no, note=""):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_case_referrals"
        "(case_id, agency, contact, reference_no, sent_at, note) "
        "VALUES (?,?,?,?,?,?)",
        (
            case_id,
            agency,
            contact or None,
            reference_no or None,
            datetime.now().isoformat(),
            note or None,
        ),
    )
    conn.commit()
    conn.close()


def list_referrals(case_id):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, agency, contact, reference_no, sent_at, status, note "
        "FROM safeguarding_case_referrals WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


SUPPORT_PLAN_TEMPLATES = {
    RiskCategory.SELF_HARM: [
        ("Contact student within 1 hour", 0),
        ("Refer to Wellbeing / Mental Health team", 1),
        ("Arrange welfare check if no contact", 0),
        ("Notify personal tutor (with consent)", 2),
        ("Schedule 7-day review", 7),
    ],
    RiskCategory.MENTAL_HEALTH: [
        ("Contact student within 24 hours", 1),
        ("Offer Wellbeing appointment", 2),
        ("Provide self-help resources", 1),
        ("Schedule 14-day review", 14),
    ],
    RiskCategory.BULLYING: [
        ("Confidential meeting with reporter", 2),
        ("Capture details and any evidence", 3),
        ("Refer to Student Conduct if perpetrator known", 5),
        ("Schedule 14-day review", 14),
    ],
    RiskCategory.EXPLOITATION: [
        ("Contact student within 1 hour", 0),
        ("Refer to specialist support service", 1),
        ("Consider external referral (Police / Social Care)", 1),
        ("Risk assessment by DSL", 1),
        ("Schedule 7-day review", 7),
    ],
    RiskCategory.SUBSTANCE: [
        ("Offer Wellbeing / Health Centre referral", 3),
        ("Provide harm-reduction information", 3),
        ("Schedule 21-day review", 21),
    ],
    RiskCategory.ACADEMIC: [
        ("Arrange tutor meeting", 5),
        ("Refer to Academic Skills service", 7),
        ("Consider mitigating-circumstances guidance", 7),
        ("Schedule 21-day review", 21),
    ],
    RiskCategory.DISCRIMINATION: [
        ("Confidential meeting with student", 2),
        ("Refer to EDI office", 3),
        ("Consider Student Conduct referral", 5),
        ("Schedule 14-day review", 14),
    ],
    RiskCategory.EXTREMISM: [
        ("Notify Prevent lead immediately", 0),
        ("DSL risk assessment", 1),
        ("Coordinate with regional Prevent team", 3),
        ("Schedule 7-day review", 7),
    ],
}


def apply_support_plan_template(case_id, category, owner=None, actor="system"):
    template = SUPPORT_PLAN_TEMPLATES.get(category)
    if not template:
        return 0
    today = datetime.now()
    count = 0
    for title, offset_days in template:
        due = (today + timedelta(days=offset_days)).date().isoformat()
        add_action_item(case_id, title, owner, due)
        count += 1
    audit_log(
        actor=actor,
        action="apply_support_template",
        case_id=case_id,
        details=f"category={category} items={count}",
    )
    return count


def schedule_review(case_id, days, actor="system"):
    """Set next_review_at to now+days and persist the interval."""
    due = (datetime.now() + timedelta(days=int(days))).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET next_review_at=?, review_interval_days=? WHERE id=?",
        (due, int(days), case_id),
    )
    conn.commit()
    conn.close()
    audit_log(
        actor=actor,
        action="schedule_review",
        case_id=case_id,
        details=f"next_review_at={due} interval_days={days}",
    )


def due_reviews(within_days=0):
    """Return cases whose next_review_at has passed (or is within N days)."""
    horizon = (datetime.now() + timedelta(days=within_days)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, username, severity, next_review_at, "
        "       lifecycle_state, assigned_to "
        "FROM safeguarding_submissions "
        "WHERE next_review_at IS NOT NULL AND next_review_at <= ? "
        "AND lifecycle_state != 'Closed' AND COALESCE(purged,0) = 0 "
        "ORDER BY next_review_at ASC",
        (horizon,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


OUTCOME_CODES = (
    ("NFA", "No further action — no concern substantiated"),
    ("SUPPORT", "Internal support provided"),
    ("REFERRED", "Referred to external agency"),
    ("DISCIPLINE", "Student conduct / disciplinary route"),
    ("WITHDRAWN", "Withdrawn / not pursued by reporter"),
    ("DUPLICATE", "Closed as duplicate"),
    ("MERGED", "Merged into another case"),
    ("UNFOUNDED", "Concern unfounded"),
    ("MONITORING", "Closed with ongoing monitoring plan"),
)
OUTCOME_CODE_SET = {code for code, _ in OUTCOME_CODES}


def close_case(case_id, outcome_code, reason, actor):
    if outcome_code not in OUTCOME_CODE_SET:
        raise ValueError(f"Unknown outcome code: {outcome_code}")
    now = datetime.now().isoformat()
    retention = _compute_retention_until_for_id(case_id, outcome_code)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET status='Closed', lifecycle_state='Closed', "
        "    outcome_code=?, closure_reason=?, "
        "    reviewer=?, review_note=COALESCE(review_note,'') || ?, "
        "    reviewed_at=?, retention_until=? "
        "WHERE id=?",
        (
            outcome_code,
            reason,
            actor,
            f"\n[CLOSED] {outcome_code}: {reason}",
            now,
            retention.isoformat() if retention else None,
            case_id,
        ),
    )
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) VALUES (?,?,?,?)",
        (case_id, actor or "system", f"[closure] {outcome_code} — {reason}", now),
    )
    conn.commit()
    conn.close()
    audit_log(
        actor=actor,
        action="close",
        case_id=case_id,
        details=f"outcome={outcome_code} reason={reason[:80]}",
    )


EXPORT_COLUMNS = (
    "id",
    "submitted_at",
    "severity",
    "categories",
    "status",
    "lifecycle_state",
    "risk_score",
    "outcome_code",
    "closure_reason",
    "case_location",
    "case_department",
    "anonymous",
    "on_behalf_of",
    "assigned_to",
    "sla_due_at",
    "sla_breached",
)


def export_cases_csv(out_path, *, since=None, until=None, include_anonymous=True, actor="system"):
    """Write a CSV of cases matching the date filter. Does NOT include raw
    free-text content — that requires the SAR bundle which carries its own
    audit trail."""
    import csv

    q = (
        "SELECT "
        + ", ".join(EXPORT_COLUMNS)
        + " FROM safeguarding_submissions WHERE COALESCE(purged,0)=0"
    )
    params = []
    if since:
        q += " AND submitted_at >= ?"
        params.append(since)
    if until:
        q += " AND submitted_at <= ?"
        params.append(until)
    if not include_anonymous:
        q += " AND COALESCE(anonymous,0)=0"
    q += " ORDER BY submitted_at ASC"
    conn = _connect()
    cur = conn.cursor()
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(EXPORT_COLUMNS)
        for r in rows:
            w.writerow(r)
    audit_log(
        actor=actor,
        action="bulk_export",
        details=f"rows={len(rows)} path={out_path} since={since} until={until}",
    )
    return out_path, len(rows)


def merge_cases(primary_id, other_ids, actor):
    """Mark each `other_id` as merged_into=primary_id, copy across their notes
    and action items to the primary, and close them with outcome=MERGED."""
    if not other_ids:
        return 0
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    merged = 0
    for oid in other_ids:
        if oid == primary_id:
            continue
        # Move notes
        cur.execute(
            "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) "
            "SELECT ?, author, '[merged from #' || ? || '] ' || note, created_at "
            "FROM safeguarding_case_notes WHERE case_id=?",
            (primary_id, oid, oid),
        )
        # Move action items
        cur.execute(
            "UPDATE safeguarding_action_items SET case_id=? WHERE case_id=?",
            (primary_id, oid),
        )
        # Mark merged & closed
        cur.execute(
            "UPDATE safeguarding_submissions "
            "SET merged_into=?, status='Closed', lifecycle_state='Closed', "
            "    outcome_code='MERGED', closure_reason=?, reviewed_at=? "
            "WHERE id=?",
            (primary_id, f"Merged into #{primary_id}", now, oid),
        )
        merged += 1
    conn.commit()
    conn.close()
    audit_log(
        actor=actor,
        action="merge_cases",
        case_id=primary_id,
        details=f"merged_ids={list(other_ids)}",
    )
    return merged


def split_case(case_id, extract_text, actor, severity=None):
    """Create a derivative case copying identity/subject fields and recording
    `split_from`. Reviewer note explains the split."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, full_name, role, anonymous, on_behalf_of, "
        "       reporter_username, subject_relation, linked_subject_id, "
        "       case_location, case_department, language "
        "FROM safeguarding_submissions WHERE id=?",
        (case_id,),
    )
    src = cur.fetchone()
    conn.close()
    if not src:
        return None
    user = {"username": src[0], "full_name": src[1], "role": src[2]}
    matches, overall = analyse_text(extract_text)
    categories = {cat: info["snippets"] for cat, info in matches.items()}
    new_id = save_submission(
        user,
        extract_text,
        severity or overall,
        categories,
        anonymous=bool(src[3]),
        on_behalf_of=bool(src[4]),
        reporter_username=src[5],
        subject_relation=src[6],
        case_location=src[8],
        case_department=src[9],
        language=src[10],
    )
    # Tag the new row with split_from
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET split_from=? WHERE id=?",
        (case_id, new_id),
    )
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) VALUES (?,?,?,?)",
        (
            case_id,
            actor or "system",
            f"[split] portion extracted into new case #{new_id}",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    audit_log(actor=actor, action="split_case", case_id=case_id, details=f"new_case_id={new_id}")
    return new_id


__all__ = [
    "_LIFECYCLE_STATES",
    "set_lifecycle_state",
    "assign_case",
    "list_assignments",
    "add_case_note",
    "list_case_notes",
    "add_action_item",
    "list_action_items",
    "complete_action_item",
    "add_referral",
    "list_referrals",
    "SUPPORT_PLAN_TEMPLATES",
    "apply_support_plan_template",
    "schedule_review",
    "due_reviews",
    "OUTCOME_CODES",
    "OUTCOME_CODE_SET",
    "close_case",
    "EXPORT_COLUMNS",
    "export_cases_csv",
    "merge_cases",
    "split_case",
]
