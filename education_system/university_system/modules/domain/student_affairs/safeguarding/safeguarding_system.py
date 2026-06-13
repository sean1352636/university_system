"""
University Portal Safeguarding System
--------------------------------------
A GUI application that screens messages/posts submitted through a
university portal for safeguarding concerns (self-harm, bullying,
harassment, exploitation, academic distress, etc.) and routes flagged
content to the appropriate support team.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. There is no in-app login screen. Users
with role=='student' see the submission form; everyone else (staff,
instructor, admin, dsl, ...) gets the staff review console.

Persistence: rows live in the central `student_records.db` table
`safeguarding_submissions`. The legacy local `safeguarding.db` file
is removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.

NOTE: This is an educational/demonstration tool. A real safeguarding
system requires trained professionals, robust NLP (not keyword matching),
compliance with GDPR/Data Protection law, and integration with
institutional safeguarding policy.
"""

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


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# Legacy local DB file — data now lives in the central student_records.db.
_LEGACY_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "safeguarding.db")


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    full_name = os.environ.get('EDU_AUTH_FULL_NAME') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or username,
            'user_id': user_id or username,
            'username': username or user_id,
            'role': role or 'student',
            'email': email,
            'full_name': full_name or username or user_id or 'Unknown User',
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            u = dict(ga.current_user)
            u.setdefault('full_name', u.get('username', 'Unknown User'))
            u.setdefault('role', 'student')
            return u
        return None
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _is_staff_role(role: str) -> bool:
    """Anyone who isn't a student sees the staff review console."""
    return (role or '').lower() not in ('student', '', 'guest')


# ---------------------------------------------------------------------------
# Risk classification engine
# ---------------------------------------------------------------------------

class RiskCategory:
    SELF_HARM       = "Self-harm / Suicide"
    MENTAL_HEALTH   = "Mental Health"
    BULLYING        = "Bullying / Harassment"
    EXPLOITATION    = "Exploitation / Abuse"
    SUBSTANCE       = "Substance Misuse"
    ACADEMIC        = "Academic Distress"
    DISCRIMINATION  = "Discrimination / Hate"
    EXTREMISM       = "Radicalisation Concern"


# Keyword patterns grouped by concern category. Using word-boundary
# regexes to reduce false positives (e.g. "kill" matching "skill").
RISK_PATTERNS = {
    RiskCategory.SELF_HARM: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bkill\s+myself\b", r"\bend\s+(it|my\s+life)\b",
            r"\bsuicid\w*\b", r"\bself[\s-]?harm\b", r"\bcut\s+myself\b",
            r"\bdon't\s+want\s+to\s+(live|be\s+here)\b",
            r"\bwant\s+to\s+die\b", r"\bno\s+reason\s+to\s+live\b",
            r"\boverdos\w*\b",
        ],
    },
    RiskCategory.MENTAL_HEALTH: {
        "severity": "HIGH",
        "patterns": [
            r"\bdepress\w*\b", r"\banxiety\b", r"\bpanic\s+attack\b",
            r"\bcan't\s+cope\b", r"\bhopeless\b", r"\bworthless\b",
            r"\bbreakdown\b", r"\bmental\s+health\b", r"\bisolat\w+\b",
            r"\bcrying\s+(all|every)\b",
        ],
    },
    RiskCategory.BULLYING: {
        "severity": "HIGH",
        "patterns": [
            r"\bbull(y|ied|ying)\b", r"\bharass\w*\b", r"\bthreaten\w*\b",
            r"\bstalk\w*\b", r"\bintimidat\w*\b", r"\bhate\s+me\b",
            r"\bmaking\s+fun\s+of\s+me\b", r"\bpicking\s+on\s+me\b",
        ],
    },
    RiskCategory.EXPLOITATION: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bassault\w*\b", r"\brape\w*\b", r"\bgroom\w*\b",
            r"\bcoerc\w*\b", r"\bforc\w+\s+(me|to)\b",
            r"\binappropriate\s+touch\w*\b", r"\bsexual\s+abuse\b",
            r"\bdomestic\s+(abuse|violence)\b",
        ],
    },
    RiskCategory.SUBSTANCE: {
        "severity": "MEDIUM",
        "patterns": [
            r"\bdrunk\s+every\b", r"\baddict\w*\b", r"\boverdose\b",
            r"\bdrug\s+problem\b", r"\balcohol\s+problem\b",
            r"\bcan't\s+stop\s+drinking\b",
        ],
    },
    RiskCategory.ACADEMIC: {
        "severity": "LOW",
        "patterns": [
            r"\bfail\w+\s+(everything|all)\b", r"\bdrop\s+out\b",
            r"\bquit\s+uni\w*\b", r"\bcan't\s+keep\s+up\b",
            r"\boverwhelmed\b", r"\btoo\s+much\s+pressure\b",
            r"\bburn\s?out\b",
        ],
    },
    RiskCategory.DISCRIMINATION: {
        "severity": "HIGH",
        "patterns": [
            r"\bracis\w*\b", r"\bsexis\w*\b", r"\bhomophob\w*\b",
            r"\btransphob\w*\b", r"\bdiscriminat\w*\b",
            r"\bhate\s+crime\b", r"\bslur\w*\b",
        ],
    },
    RiskCategory.EXTREMISM: {
        "severity": "CRITICAL",
        "patterns": [
            r"\bradicali[sz]\w*\b", r"\bextremis\w*\b",
            r"\bterroris\w*\b", r"\bjoin\s+a\s+cause\b",
        ],
    },
}

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
SEVERITY_COLOUR = {
    "LOW":      "#f5c518",
    "MEDIUM":   "#f38b00",
    "HIGH":     "#d9480f",
    "CRITICAL": "#b00020",
    "NONE":     "#2e7d32",
}


def analyse_text(text: str):
    """Return a dict of {category: [matched_snippets]} and overall severity."""
    text_lower = text.lower()
    matches = {}

    for category, cfg in RISK_PATTERNS.items():
        hits = []
        for pattern in cfg["patterns"]:
            for m in re.finditer(pattern, text_lower):
                # Capture a little surrounding context for the reviewer
                start = max(0, m.start() - 25)
                end   = min(len(text_lower), m.end() + 25)
                hits.append("…" + text_lower[start:end].strip() + "…")
        if hits:
            matches[category] = {
                "severity": cfg["severity"],
                "snippets": hits,
            }

    # Overall severity = highest across all categories
    if not matches:
        overall = "NONE"
    else:
        overall = max(
            (m["severity"] for m in matches.values()),
            key=lambda s: SEVERITY_ORDER[s],
        )

    return matches, overall


# ---------------------------------------------------------------------------
# Persistence layer — central student_records.db
# ---------------------------------------------------------------------------


def _connect():
    from education_system.university_system.infrastructure.database.db import get_connection
    return get_connection()


_EXTRA_COLUMNS = [
    ("anonymous",          "INTEGER DEFAULT 0"),
    ("contact_token",      "TEXT"),       # sha256 hash; raw token shown once to user
    ("on_behalf_of",       "INTEGER DEFAULT 0"),
    ("reporter_username",  "TEXT"),       # actual reporter when on_behalf_of=1
    ("subject_relation",   "TEXT"),       # "Friend", "Classmate", etc.
    ("triage",             "TEXT"),       # JSON of wizard answers
    ("attachments",        "TEXT"),       # JSON list of stored filenames
    ("audio_path",         "TEXT"),
    ("transcription",      "TEXT"),
    ("language",           "TEXT"),
    ("consent_disclosure", "INTEGER DEFAULT 0"),
    ("consent_contact",    "INTEGER DEFAULT 0"),
    ("duplicate_of",       "INTEGER"),
    # Features 11-25
    ("likelihood",         "INTEGER"),       # 1..5 — feature 11
    ("impact",             "INTEGER"),       # 1..5 — feature 11
    ("risk_score",         "INTEGER"),       # likelihood*impact — feature 11
    ("nlp_score",          "REAL"),          # 0..1 confidence — feature 12
    ("nlp_categories",     "TEXT"),          # JSON {category: score} — feature 12
    ("sla_due_at",         "TEXT"),          # ISO datetime — feature 14
    ("sla_breached",       "INTEGER DEFAULT 0"),  # feature 14
    ("assigned_to",        "TEXT"),          # username of DSL — feature 15
    ("assigned_at",        "TEXT"),          # feature 15
    ("linked_subject_id",  "TEXT"),          # canonical subject id — feature 16
    ("vulnerability_flags","TEXT"),          # JSON list — feature 17
    ("lifecycle_state",    "TEXT DEFAULT 'Open'"),  # feature 21
    ("case_location",      "TEXT"),          # building/campus — feature 19
    ("case_department",    "TEXT"),          # department/school — feature 19
    # Features 26-40
    ("next_review_at",         "TEXT"),                  # feature 27
    ("review_interval_days",   "INTEGER"),               # feature 27
    ("outcome_code",           "TEXT"),                  # feature 28
    ("closure_reason",         "TEXT"),                  # feature 28
    ("content_encrypted",      "INTEGER DEFAULT 0"),     # feature 37
    ("content_blob",           "BLOB"),                  # feature 37
    ("transcription_encrypted","INTEGER DEFAULT 0"),     # feature 37
    ("transcription_blob",     "BLOB"),                  # feature 37
    ("merged_into",            "INTEGER"),               # feature 30
    ("split_from",             "INTEGER"),               # feature 30
    ("retention_until",        "TEXT"),                  # feature 39
    ("purged",                 "INTEGER DEFAULT 0"),     # feature 39
    # Features 41-50
    ("mandatory_reporting",        "INTEGER DEFAULT 0"),     # feature 41
    ("mandatory_status",           "TEXT"),                  # feature 41
    ("mandatory_reported_at",      "TEXT"),                  # feature 41
    ("whistleblowing",             "INTEGER DEFAULT 0"),     # feature 42
    ("wb_independent_reviewer",    "TEXT"),                  # feature 42
    ("linked_wellbeing_appt",      "TEXT"),                  # feature 43
    ("linked_conduct_case",        "TEXT"),                  # feature 44
    ("linked_halls_incident",      "TEXT"),                  # feature 45
    ("health_referral_consent",    "INTEGER DEFAULT 0"),     # feature 46
    ("health_referral_sent_at",    "TEXT"),                  # feature 46
    ("tutor_notified_at",          "TEXT"),                  # feature 47
    ("tutor_notification_redacted","TEXT"),                  # feature 47
]


def init_db():
    """Create the safeguarding_submissions table and migrate new columns."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_submissions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            full_name    TEXT,
            role         TEXT,
            content      TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            severity     TEXT NOT NULL,
            categories   TEXT NOT NULL,      -- JSON
            status       TEXT NOT NULL DEFAULT 'Pending',
            reviewer     TEXT,
            review_note  TEXT,
            reviewed_at  TEXT
        )
    """)
    cur.execute("PRAGMA table_info(safeguarding_submissions)")
    existing = {row[1] for row in cur.fetchall()}
    for col, decl in _EXTRA_COLUMNS:
        if col not in existing:
            cur.execute(f"ALTER TABLE safeguarding_submissions ADD COLUMN {col} {decl}")

    # Feature 24 — append-only confidential notes timeline
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_case_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id    INTEGER NOT NULL,
            author     TEXT NOT NULL,
            note       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(case_id) REFERENCES safeguarding_submissions(id)
        )
    """)
    # Feature 23 — action plan items
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_action_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id    INTEGER NOT NULL,
            title      TEXT NOT NULL,
            owner      TEXT,
            due_date   TEXT,
            status     TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(case_id) REFERENCES safeguarding_submissions(id)
        )
    """)
    # Feature 22 — reassignment audit trail
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_assignments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id     INTEGER NOT NULL,
            assignee    TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            note        TEXT,
            FOREIGN KEY(case_id) REFERENCES safeguarding_submissions(id)
        )
    """)
    # Feature 25 — external referrals
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_case_referrals (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id       INTEGER NOT NULL,
            agency        TEXT NOT NULL,
            contact       TEXT,
            reference_no  TEXT,
            sent_at       TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'Sent',
            note          TEXT,
            FOREIGN KEY(case_id) REFERENCES safeguarding_submissions(id)
        )
    """)
    # Feature 15 — DSL on-call rota
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_dsl_oncall (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL,
            full_name  TEXT,
            starts_at  TEXT NOT NULL,
            ends_at    TEXT NOT NULL
        )
    """)
    # Feature 38 — full GDPR audit log of view/edit/export
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT NOT NULL,
            actor      TEXT NOT NULL,
            actor_role TEXT,
            action     TEXT NOT NULL,
            case_id    INTEGER,
            details    TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sg_audit_case "
                "ON safeguarding_audit_log(case_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sg_audit_ts "
                "ON safeguarding_audit_log(ts)")
    # Features 31, 33, 34, 35 — notification outbox.
    # Real send is attempted via the shared email service when available;
    # rows here are always written so there's a queryable history.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id    INTEGER,
            channel    TEXT NOT NULL,        -- email / sms / pager / digest
            recipient  TEXT NOT NULL,
            subject    TEXT,
            body       TEXT,
            queued_at  TEXT NOT NULL,
            sent_at    TEXT,
            status     TEXT NOT NULL DEFAULT 'Queued'   -- Queued / Sent / Failed
        )
    """)
    # Feature 48 — webhook registry + delivery log
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_webhooks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            url          TEXT NOT NULL,
            secret       TEXT NOT NULL,
            event_filter TEXT,                -- comma-separated event names or '*'
            active       INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL,
            last_status  TEXT,
            last_sent_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_webhook_deliveries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id    INTEGER NOT NULL,
            case_id       INTEGER,
            event         TEXT NOT NULL,
            payload       TEXT NOT NULL,
            sent_at       TEXT NOT NULL,
            response_code INTEGER,
            response_body TEXT,
            FOREIGN KEY(webhook_id) REFERENCES safeguarding_webhooks(id)
        )
    """)
    # Feature 50 — staff safeguarding-training records
    cur.execute("""
        CREATE TABLE IF NOT EXISTS safeguarding_training (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            full_name    TEXT,
            module       TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            expires_at   TEXT,
            UNIQUE(username, module, completed_at)
        )
    """)
    conn.commit()
    conn.close()


def save_submission(user, content, severity, categories, *,
                    anonymous=False, contact_token_hash=None,
                    on_behalf_of=False, reporter_username=None,
                    subject_relation=None, triage=None,
                    attachments=None, audio_path=None,
                    transcription=None, language=None,
                    consent_disclosure=False, consent_contact=False,
                    duplicate_of=None,
                    vulnerability_flags=None,
                    case_location=None, case_department=None,
                    nlp_score=None, nlp_categories=None,
                    whistleblowing=False, wb_independent_reviewer=None):
    """Persist a submission and derive risk/SLA/assignment metadata.

    Returns the new row id. Side-effects (audit-trail assignment row, etc.)
    happen via helpers called below.
    """
    likelihood, impact, risk_score = compute_risk_score(
        severity, triage or {}, vulnerability_flags or [])
    sla_due = compute_sla_due(severity)
    subject_id = canonical_subject_id(user, anonymous=anonymous)
    oncall = get_oncall_dsl()
    assignee = oncall.get("username") if oncall else None
    now = datetime.now().isoformat()

    # Feature 37 — field-level encryption of the free-text content and
    # any transcription. Toggle via FIELD_ENCRYPTION_ENABLED below.
    content_blob, content_encrypted = _encrypt_field(content)
    trans_blob, trans_encrypted     = _encrypt_field(transcription)
    if content_encrypted:
        stored_content = ""   # raw text not held in plaintext
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
        (user.get('username') or '', user.get('full_name') or '',
         user.get('role') or '', stored_content,
         now, severity, json.dumps(categories),
         1 if anonymous else 0, contact_token_hash,
         1 if on_behalf_of else 0, reporter_username, subject_relation,
         json.dumps(triage) if triage else None,
         json.dumps(attachments) if attachments else None,
         audio_path, stored_transcription, language,
         1 if consent_disclosure else 0, 1 if consent_contact else 0,
         duplicate_of,
         likelihood, impact, risk_score,
         nlp_score, json.dumps(nlp_categories) if nlp_categories else None,
         sla_due.isoformat() if sla_due else None, 0,
         assignee, now if assignee else None,
         subject_id, json.dumps(vulnerability_flags) if vulnerability_flags else None,
         'Triage' if severity in ('CRITICAL', 'HIGH') else 'Open',
         case_location, case_department,
         1 if content_encrypted else 0, content_blob,
         1 if trans_encrypted else 0, trans_blob,
         retention_until.isoformat() if retention_until else None),
    )
    sid = cur.lastrowid
    if assignee:
        cur.execute(
            "INSERT INTO safeguarding_assignments(case_id, assignee, assigned_by, "
            "assigned_at, note) VALUES (?,?,?,?,?)",
            (sid, assignee, 'auto-rota', now, 'Auto-assigned via on-call rota'),
        )
    conn.commit()
    conn.close()

    # Feature 42 — whistleblowing flag is set on a separate update so the
    # main INSERT stays compact. Whistleblowing rows are hidden from regular
    # staff lists and routed to the named independent reviewer instead.
    if whistleblowing:
        conn = _connect(); cur = conn.cursor()
        cur.execute(
            "UPDATE safeguarding_submissions "
            "SET whistleblowing=1, wb_independent_reviewer=?, assigned_to=?, "
            "    assigned_at=? WHERE id=?",
            (wb_independent_reviewer, wb_independent_reviewer or None,
             now if wb_independent_reviewer else None, sid),
        )
        conn.commit(); conn.close()

    # Audit + escalation side-effects (features 31, 32, 38)
    audit_log(actor=(reporter_username or user.get('username') or 'anon'),
              actor_role=user.get('role') or 'student',
              action='create', case_id=sid,
              details=f"severity={severity} risk={risk_score} "
                      f"wb={1 if whistleblowing else 0}")
    if severity == 'CRITICAL':
        escalation_notify_dsl(sid, severity, assignee, oncall)

    # Feature 41 — mandatory-reporting check (KCSIE / Prevent)
    check_mandatory_reporting(sid, categories,
                              vulnerability_flags or [],
                              actor=user.get('username') or 'system')

    # Feature 48 — emit case.created webhook to any registered SIEM endpoint
    emit_webhook_event("case.created", {
        "case_id": sid, "severity": severity, "risk_score": risk_score,
        "categories": list(categories.keys()) if categories else [],
        "anonymous": bool(anonymous), "whistleblowing": bool(whistleblowing),
        "submitted_at": now,
    }, case_id=sid)

    return sid


# ---------------------------------------------------------------------------
# Case-management mutators (features 21-25)
# ---------------------------------------------------------------------------


_LIFECYCLE_STATES = ("Open", "Triage", "Action", "Monitoring", "Closed")


def set_lifecycle_state(case_id, state, actor=""):
    if state not in _LIFECYCLE_STATES:
        raise ValueError(f"Invalid lifecycle state: {state}")
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE safeguarding_submissions SET lifecycle_state=? WHERE id=?",
                (state, case_id))
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) "
        "VALUES (?,?,?,?)",
        (case_id, actor or 'system',
         f"[lifecycle] state changed to {state}", datetime.now().isoformat()),
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
        (case_id, assignee, assigned_by or '?', now, note or None),
    )
    conn.commit()
    conn.close()


def list_assignments(case_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT assignee, assigned_by, assigned_at, note "
        "FROM safeguarding_assignments WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall(); conn.close()
    return rows


def add_case_note(case_id, author, note):
    """Append-only — there's no update or delete API on purpose."""
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) "
        "VALUES (?,?,?,?)",
        (case_id, author or '?', note, datetime.now().isoformat()),
    )
    conn.commit(); conn.close()


def list_case_notes(case_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT author, note, created_at FROM safeguarding_case_notes "
        "WHERE case_id=? ORDER BY id ASC", (case_id,),
    )
    rows = cur.fetchall(); conn.close()
    return rows


def add_action_item(case_id, title, owner, due_date):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_action_items"
        "(case_id, title, owner, due_date, created_at) "
        "VALUES (?,?,?,?,?)",
        (case_id, title, owner or None, due_date or None,
         datetime.now().isoformat()),
    )
    conn.commit(); conn.close()


def list_action_items(case_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, title, owner, due_date, status, completed_at "
        "FROM safeguarding_action_items WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall(); conn.close()
    return rows


def complete_action_item(item_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_action_items SET status='Done', completed_at=? "
        "WHERE id=?", (datetime.now().isoformat(), item_id),
    )
    conn.commit(); conn.close()


def add_referral(case_id, agency, contact, reference_no, note=""):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_case_referrals"
        "(case_id, agency, contact, reference_no, sent_at, note) "
        "VALUES (?,?,?,?,?,?)",
        (case_id, agency, contact or None, reference_no or None,
         datetime.now().isoformat(), note or None),
    )
    conn.commit(); conn.close()


def list_referrals(case_id):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, agency, contact, reference_no, sent_at, status, note "
        "FROM safeguarding_case_referrals WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    rows = cur.fetchall(); conn.close()
    return rows


# ---------------------------------------------------------------------------
# Risk scoring, SLA, NLP, on-call rota, vulnerability, linked-cases, trends
# ---------------------------------------------------------------------------

# Feature 11 — configurable matrix.
DEFAULT_RISK_MATRIX = {
    # severity -> (default likelihood, default impact)
    "CRITICAL": (5, 5),
    "HIGH":     (4, 4),
    "MEDIUM":   (3, 3),
    "LOW":      (2, 2),
    "NONE":     (1, 1),
}

# Feature 17 — recognised vulnerability flags. Each one bumps impact by 1
# (capped at 5) to recognise heightened safeguarding duty.
VULNERABILITY_FLAGS = (
    "Minor (<18)",
    "Care-leaver",
    "Disability",
    "PREVENT concern",
    "International student",
    "Estranged from family",
    "Pregnant",
)


def compute_risk_score(severity, triage, vulnerability_flags):
    """Return (likelihood, impact, score) on a 1..25 scale."""
    likelihood, impact = DEFAULT_RISK_MATRIX.get(severity or "NONE", (1, 1))
    # Triage answers can amplify likelihood/impact
    if (triage or {}).get("q3") == "yes":         # immediate danger
        impact = min(5, impact + 1)
        likelihood = min(5, likelihood + 1)
    if (triage or {}).get("q4") == "no":          # nobody else knows yet
        likelihood = min(5, likelihood + 1)
    for _flag in vulnerability_flags or ():
        impact = min(5, impact + 1)
    return likelihood, impact, likelihood * impact


# Feature 14 — SLA budgets per severity.
SLA_HOURS = {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 24, "LOW": 72, "NONE": 168}


def compute_sla_due(severity):
    hours = SLA_HOURS.get(severity)
    if not hours:
        return None
    return datetime.now() + timedelta(hours=hours)


def refresh_sla_breach_flags():
    """Mark any pending case whose SLA has passed as breached. Called on staff
    dashboard refresh. Cheap — only touches the small subset of open rows."""
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET sla_breached=1 "
        "WHERE sla_breached=0 AND lifecycle_state!='Closed' "
        "AND sla_due_at IS NOT NULL AND sla_due_at < ?",
        (now,),
    )
    conn.commit(); conn.close()


# Feature 12 — lightweight NLP categoriser.
# Per-category vocabulary; matches use token-overlap with stemming so we
# catch variants the strict regex set misses ("hurting", "hurts" etc.).
_NLP_VOCAB = {
    RiskCategory.SELF_HARM: {
        "die", "death", "kill", "killing", "suicide", "suicidal", "harm",
        "hurt", "hurting", "pain", "blade", "overdose", "tablets",
        "end", "alive", "live", "living",
    },
    RiskCategory.MENTAL_HEALTH: {
        "depressed", "depression", "anxious", "anxiety", "panic", "stress",
        "lonely", "alone", "cry", "crying", "sad", "tired", "exhausted",
        "hopeless", "worthless", "empty",
    },
    RiskCategory.BULLYING: {
        "bully", "bullies", "bullying", "harass", "harassment", "threaten",
        "threats", "stalk", "stalking", "mean", "horrible", "mocking",
    },
    RiskCategory.EXPLOITATION: {
        "force", "forced", "forcing", "touch", "touched", "rape", "raped",
        "abuse", "abused", "assault", "groomed", "coerce", "coerced",
    },
    RiskCategory.SUBSTANCE: {
        "drunk", "drinking", "alcohol", "drugs", "pills", "weed", "cocaine",
        "addict", "addiction",
    },
    RiskCategory.ACADEMIC: {
        "fail", "failing", "exam", "exams", "deadline", "behind", "drop",
        "overwhelmed", "burnout", "pressure",
    },
    RiskCategory.DISCRIMINATION: {
        "racist", "sexist", "homophobic", "transphobic", "slur", "slurs",
        "discriminated", "hate",
    },
    RiskCategory.EXTREMISM: {
        "radical", "radicalised", "extremist", "extremism", "terrorist",
        "terrorism", "cause",
    },
}

_NLP_THRESHOLD = 0.10  # min normalized score to flag a category


def _crude_stem(word):
    for suf in ("ings", "ing", "ied", "ies", "ed", "es", "s"):
        if word.endswith(suf) and len(word) > len(suf) + 2:
            return word[: -len(suf)]
    return word


def nlp_classify(text):
    """Return ({category: score}, overall_confidence). Complements the regex
    classifier — both are stored so reviewers can see *why* a case was flagged."""
    if not text:
        return {}, 0.0
    tokens = [_crude_stem(t.lower()) for t in re.findall(r"[A-Za-z']+", text)]
    if not tokens:
        return {}, 0.0
    bag = {}
    for t in tokens:
        bag[t] = bag.get(t, 0) + 1
    total = len(tokens)
    scores = {}
    for cat, vocab in _NLP_VOCAB.items():
        stemmed = {_crude_stem(w) for w in vocab}
        hits = sum(bag.get(w, 0) for w in stemmed)
        score = hits / total
        if score >= _NLP_THRESHOLD:
            scores[cat] = round(score, 3)
    overall = max(scores.values()) if scores else 0.0
    return scores, overall


# Feature 13 — self-harm escalation copy + helper.
SELF_HARM_ESCALATION = (
    "Immediate-risk pathway triggered.\n\n"
    "ACTION CHECKLIST (DSL):\n"
    "  1. Attempt direct contact with the student now.\n"
    "  2. If unable to reach them and concern is acute, request a welfare\n"
    "     check via campus security and/or emergency services.\n"
    "  3. Notify the Designated Safeguarding Lead and log all actions.\n\n"
    "HOTLINES TO SHARE WITH STUDENT:\n"
    "  • Samaritans (UK)        116 123 — free, 24/7\n"
    "  • Shout (UK text)        Text SHOUT to 85258\n"
    "  • CALM (UK, men)         0800 58 58 58\n"
    "  • Papyrus HOPELINEUK     0800 068 4141 (under 35)\n"
    "  • Emergency services     999 / 112"
)


def is_self_harm_case(matches, nlp_scores):
    if (matches or {}).get(RiskCategory.SELF_HARM):
        return True
    if (nlp_scores or {}).get(RiskCategory.SELF_HARM, 0) >= 0.15:
        return True
    return False


# Feature 15 — DSL on-call rota lookup.
def add_oncall_window(username, full_name, starts_at, ends_at):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_dsl_oncall(username, full_name, starts_at, ends_at) "
        "VALUES (?,?,?,?)", (username, full_name, starts_at, ends_at),
    )
    conn.commit(); conn.close()


def get_oncall_dsl():
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT username, full_name FROM safeguarding_dsl_oncall "
        "WHERE starts_at<=? AND ends_at>=? ORDER BY id DESC LIMIT 1",
        (now, now),
    )
    row = cur.fetchone(); conn.close()
    if not row:
        return None
    return {"username": row[0], "full_name": row[1]}


# Feature 16 — case linking by canonical subject.
def canonical_subject_id(user, anonymous=False):
    """Stable id for grouping cases about the same person. Anonymous cases
    get a per-submission unique id so they don't all collide."""
    if anonymous:
        return None
    uname = (user or {}).get("username") or ""
    fname = (user or {}).get("full_name") or ""
    seed = (uname or fname).lower().strip()
    if not seed:
        return None
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def find_linked_cases(subject_id, exclude_id=None):
    if not subject_id:
        return []
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, submitted_at, severity, status, lifecycle_state "
        "FROM safeguarding_submissions WHERE linked_subject_id=? "
        "ORDER BY submitted_at DESC", (subject_id,),
    )
    rows = cur.fetchall(); conn.close()
    if exclude_id is not None:
        rows = [r for r in rows if r[0] != exclude_id]
    return rows


# Feature 18 — cumulative concern across multiple lower-severity reports.
_CUMULATIVE_WINDOW_DAYS = 30
_CUMULATIVE_THRESHOLD = 3   # >=3 LOW/MEDIUM/HIGH in window -> escalate flag


def cumulative_concern(subject_id):
    """Return (count_in_window, should_escalate) for the given subject."""
    if not subject_id:
        return 0, False
    cutoff = (datetime.now() - timedelta(days=_CUMULATIVE_WINDOW_DAYS)).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE linked_subject_id=? AND submitted_at>=? "
        "AND severity IN ('LOW','MEDIUM','HIGH')",
        (subject_id, cutoff),
    )
    n = cur.fetchone()[0]; conn.close()
    return n, n >= _CUMULATIVE_THRESHOLD


# Feature 19 — incident heatmap (department × severity).
def incident_heatmap(days=90):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(case_department,'(unspecified)'), severity, COUNT(*) "
        "FROM safeguarding_submissions WHERE submitted_at>=? "
        "GROUP BY case_department, severity",
        (cutoff,),
    )
    rows = cur.fetchall(); conn.close()
    grid = {}
    for dept, sev, n in rows:
        grid.setdefault(dept, {})[sev or "NONE"] = n
    return grid


# Feature 20 — risk trend across weeks/months.
def risk_trend(weeks=8):
    cutoff = (datetime.now() - timedelta(weeks=weeks)).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT strftime('%Y-W%W', submitted_at) AS wk, severity, COUNT(*) "
        "FROM safeguarding_submissions WHERE submitted_at>=? "
        "GROUP BY wk, severity ORDER BY wk ASC",
        (cutoff,),
    )
    rows = cur.fetchall(); conn.close()
    out = {}
    for wk, sev, n in rows:
        out.setdefault(wk, {})[sev or "NONE"] = n
    return out


# ---------------------------------------------------------------------------
# Features 26-40
# ---------------------------------------------------------------------------

# Feature 37 — field-level encryption toggle. Disable in tests if you need to
# inspect plaintext rows directly; production should leave this on.
FIELD_ENCRYPTION_ENABLED = True


def _encrypt_field(text):
    """Return (blob, encrypted_flag). If encryption is disabled or unavailable,
    returns (None, False) and the caller stores the plaintext column instead."""
    if not text or not FIELD_ENCRYPTION_ENABLED:
        return None, False
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_or_create_key())
        return f.encrypt(text.encode("utf-8")), True
    except Exception:
        logger.warning("Field encryption unavailable; storing plaintext",
                       exc_info=True)
        return None, False


def _decrypt_field(blob):
    if not blob:
        return ""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_or_create_key())
        return f.decrypt(blob).decode("utf-8")
    except Exception:
        logger.warning("Could not decrypt field", exc_info=True)
        return ""


def resolve_content(case_id):
    """Return the decrypted content + transcription for a case row."""
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT content, content_encrypted, content_blob, "
        "       transcription, transcription_encrypted, transcription_blob "
        "FROM safeguarding_submissions WHERE id=?", (case_id,),
    )
    row = cur.fetchone(); conn.close()
    if not row:
        return "", ""
    c_pt, c_enc, c_bl, t_pt, t_enc, t_bl = row
    content = _decrypt_field(c_bl) if c_enc else (c_pt or "")
    trans   = _decrypt_field(t_bl) if t_enc else (t_pt or "")
    return content, trans


# Feature 26 — support-plan templates per category.
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
    audit_log(actor=actor, action="apply_support_template", case_id=case_id,
              details=f"category={category} items={count}")
    return count


# Feature 27 — periodic case-review reminders.
def schedule_review(case_id, days, actor="system"):
    """Set next_review_at to now+days and persist the interval."""
    due = (datetime.now() + timedelta(days=int(days))).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET next_review_at=?, review_interval_days=? WHERE id=?",
        (due, int(days), case_id),
    )
    conn.commit(); conn.close()
    audit_log(actor=actor, action="schedule_review", case_id=case_id,
              details=f"next_review_at={due} interval_days={days}")


def due_reviews(within_days=0):
    """Return cases whose next_review_at has passed (or is within N days)."""
    horizon = (datetime.now() + timedelta(days=within_days)).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, username, severity, next_review_at, "
        "       lifecycle_state, assigned_to "
        "FROM safeguarding_submissions "
        "WHERE next_review_at IS NOT NULL AND next_review_at <= ? "
        "AND lifecycle_state != 'Closed' AND COALESCE(purged,0) = 0 "
        "ORDER BY next_review_at ASC",
        (horizon,),
    )
    rows = cur.fetchall(); conn.close()
    return rows


# Feature 28 — outcome / closure taxonomy.
OUTCOME_CODES = (
    ("NFA",         "No further action — no concern substantiated"),
    ("SUPPORT",     "Internal support provided"),
    ("REFERRED",    "Referred to external agency"),
    ("DISCIPLINE",  "Student conduct / disciplinary route"),
    ("WITHDRAWN",   "Withdrawn / not pursued by reporter"),
    ("DUPLICATE",   "Closed as duplicate"),
    ("MERGED",      "Merged into another case"),
    ("UNFOUNDED",   "Concern unfounded"),
    ("MONITORING",  "Closed with ongoing monitoring plan"),
)
OUTCOME_CODE_SET = {code for code, _ in OUTCOME_CODES}


def close_case(case_id, outcome_code, reason, actor):
    if outcome_code not in OUTCOME_CODE_SET:
        raise ValueError(f"Unknown outcome code: {outcome_code}")
    now = datetime.now().isoformat()
    retention = _compute_retention_until_for_id(case_id, outcome_code)
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET status='Closed', lifecycle_state='Closed', "
        "    outcome_code=?, closure_reason=?, "
        "    reviewer=?, review_note=COALESCE(review_note,'') || ?, "
        "    reviewed_at=?, retention_until=? "
        "WHERE id=?",
        (outcome_code, reason, actor,
         f"\n[CLOSED] {outcome_code}: {reason}", now,
         retention.isoformat() if retention else None, case_id),
    )
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) "
        "VALUES (?,?,?,?)",
        (case_id, actor or 'system',
         f"[closure] {outcome_code} — {reason}", now),
    )
    conn.commit(); conn.close()
    audit_log(actor=actor, action="close", case_id=case_id,
              details=f"outcome={outcome_code} reason={reason[:80]}")


# Feature 29 — bulk CSV export for statutory reporting.
EXPORT_COLUMNS = (
    "id", "submitted_at", "severity", "categories", "status",
    "lifecycle_state", "risk_score", "outcome_code", "closure_reason",
    "case_location", "case_department", "anonymous", "on_behalf_of",
    "assigned_to", "sla_due_at", "sla_breached",
)


def export_cases_csv(out_path, *, since=None, until=None,
                     include_anonymous=True, actor="system"):
    """Write a CSV of cases matching the date filter. Does NOT include raw
    free-text content — that requires the SAR bundle which carries its own
    audit trail."""
    import csv
    q = "SELECT " + ", ".join(EXPORT_COLUMNS) + \
        " FROM safeguarding_submissions WHERE COALESCE(purged,0)=0"
    params = []
    if since:
        q += " AND submitted_at >= ?"; params.append(since)
    if until:
        q += " AND submitted_at <= ?"; params.append(until)
    if not include_anonymous:
        q += " AND COALESCE(anonymous,0)=0"
    q += " ORDER BY submitted_at ASC"
    conn = _connect(); cur = conn.cursor()
    cur.execute(q, params)
    rows = cur.fetchall(); conn.close()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(EXPORT_COLUMNS)
        for r in rows:
            w.writerow(r)
    audit_log(actor=actor, action="bulk_export",
              details=f"rows={len(rows)} path={out_path} "
                      f"since={since} until={until}")
    return out_path, len(rows)


# Feature 30 — case merge & split.
def merge_cases(primary_id, other_ids, actor):
    """Mark each `other_id` as merged_into=primary_id, copy across their notes
    and action items to the primary, and close them with outcome=MERGED."""
    if not other_ids:
        return 0
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
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
    conn.commit(); conn.close()
    audit_log(actor=actor, action="merge_cases", case_id=primary_id,
              details=f"merged_ids={list(other_ids)}")
    return merged


def split_case(case_id, extract_text, actor, severity=None):
    """Create a derivative case copying identity/subject fields and recording
    `split_from`. Reviewer note explains the split."""
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT username, full_name, role, anonymous, on_behalf_of, "
        "       reporter_username, subject_relation, linked_subject_id, "
        "       case_location, case_department, language "
        "FROM safeguarding_submissions WHERE id=?", (case_id,),
    )
    src = cur.fetchone()
    conn.close()
    if not src:
        return None
    user = {"username": src[0], "full_name": src[1], "role": src[2]}
    matches, overall = analyse_text(extract_text)
    categories = {cat: info["snippets"] for cat, info in matches.items()}
    new_id = save_submission(
        user, extract_text, severity or overall, categories,
        anonymous=bool(src[3]), on_behalf_of=bool(src[4]),
        reporter_username=src[5], subject_relation=src[6],
        case_location=src[8], case_department=src[9],
        language=src[10],
    )
    # Tag the new row with split_from
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET split_from=? WHERE id=?",
        (case_id, new_id),
    )
    cur.execute(
        "INSERT INTO safeguarding_case_notes(case_id, author, note, created_at) "
        "VALUES (?,?,?,?)",
        (case_id, actor or 'system',
         f"[split] portion extracted into new case #{new_id}",
         datetime.now().isoformat()),
    )
    conn.commit(); conn.close()
    audit_log(actor=actor, action="split_case", case_id=case_id,
              details=f"new_case_id={new_id}")
    return new_id


# ---- Notifications (31-35) -------------------------------------------------
# Notifications are *always* written to safeguarding_notifications. If a
# shared transport is available we also attempt to send; failures flip the
# row to status='Failed' but never raise to the caller.

def _try_send_email(recipient, subject, body):
    try:
        from education_system.shared.email import send_email  # type: ignore
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
            status = "Queued"   # left for an outbox worker to retry
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_notifications"
        "(case_id, channel, recipient, subject, body, queued_at, sent_at, status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (case_id, channel, recipient, subject, body, now, sent_at, status),
    )
    nid = cur.lastrowid
    conn.commit(); conn.close()
    return nid


def list_notifications(case_id=None, limit=200):
    conn = _connect(); cur = conn.cursor()
    if case_id is None:
        cur.execute(
            "SELECT id, case_id, channel, recipient, subject, queued_at, "
            "       sent_at, status FROM safeguarding_notifications "
            "ORDER BY id DESC LIMIT ?", (limit,),
        )
    else:
        cur.execute(
            "SELECT id, case_id, channel, recipient, subject, queued_at, "
            "       sent_at, status FROM safeguarding_notifications "
            "WHERE case_id=? ORDER BY id DESC LIMIT ?", (case_id, limit),
        )
    rows = cur.fetchall(); conn.close()
    return rows


# Feature 31 + 32 — email/SMS escalation to DSL on Critical, with pager fallback.
def escalation_notify_dsl(case_id, severity, assignee, oncall):
    if severity != 'CRITICAL':
        return
    if not oncall:
        queue_notification("pager", "duty-officer",
                           "Safeguarding CRITICAL — no on-call DSL configured",
                           f"Case #{case_id} created at CRITICAL severity. "
                           "No DSL is on call; please assign manually.",
                           case_id=case_id)
        return
    subject = f"[SAFEGUARDING CRITICAL] case #{case_id}"
    body = (f"A CRITICAL safeguarding case (#{case_id}) has been auto-assigned "
            f"to you as on-call DSL.\n\nPlease review and respond within the "
            f"1-hour SLA.")
    # Email + SMS + pager — recipient address-book lookup is out of scope here.
    queue_notification("email", f"{oncall['username']}@example.edu",
                       subject, body, case_id=case_id)
    queue_notification("sms",   oncall['username'], subject, body,
                       case_id=case_id)
    queue_notification("pager", oncall['username'], subject, body,
                       case_id=case_id)


# Feature 33 — auto-notify reporter on status change (only with consent).
def notify_reporter_on_status_change(case_id, new_status, actor):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT consent_contact, anonymous, reporter_username, username "
        "FROM safeguarding_submissions WHERE id=?", (case_id,),
    )
    row = cur.fetchone(); conn.close()
    if not row:
        return
    consent, anon, reporter_user, subject_user = row
    if not consent or anon:
        return
    recipient = reporter_user or subject_user
    if not recipient:
        return
    queue_notification(
        "email", f"{recipient}@example.edu",
        f"Update on your safeguarding submission #{case_id}",
        f"Your case is now '{new_status}'. The safeguarding team will be in "
        f"touch if further information is needed.",
        case_id=case_id,
    )
    audit_log(actor=actor, action="notify_reporter", case_id=case_id,
              details=f"status={new_status} recipient={recipient}")


# Feature 34 — alert when any case breaches SLA.
def stuck_case_alerts(actor="system"):
    refresh_sla_breach_flags()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, severity, assigned_to FROM safeguarding_submissions "
        "WHERE sla_breached=1 AND lifecycle_state!='Closed' "
        "AND COALESCE(purged,0)=0",
    )
    rows = cur.fetchall(); conn.close()
    sent = 0
    for sid, sev, assignee in rows:
        recipient = assignee or "duty-officer"
        queue_notification(
            "email", f"{recipient}@example.edu",
            f"[SLA BREACH] safeguarding case #{sid}",
            f"Case #{sid} (severity {sev}) has missed its SLA. "
            "Please action immediately.",
            case_id=sid,
        )
        sent += 1
    if sent:
        audit_log(actor=actor, action="sla_alerts",
                  details=f"sent={sent}")
    return sent


# Feature 35 — daily DSL digest of new + open cases.
def daily_dsl_digest(actor="system"):
    cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at >= ?", (cutoff_24h,),
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
    body = (f"Daily safeguarding digest\n\n"
            f"  • New cases in last 24h: {new_24h}\n"
            f"  • Open cases by severity: {open_by_sev}\n"
            f"  • SLA breaches outstanding: {breached}\n")
    oncall = get_oncall_dsl()
    recipient = (oncall.get("username") if oncall else "duty-officer")
    queue_notification("digest", f"{recipient}@example.edu",
                       "Safeguarding daily digest", body)
    audit_log(actor=actor, action="daily_digest",
              details=f"new24h={new_24h} breached={breached}")
    return body


# ---- RBAC (36) -------------------------------------------------------------

# Permission names are coarse; pair them with case-level checks where needed.
_ROLE_PERMISSIONS = {
    "student":       {"view_own", "submit"},
    "staff":         {"view_own", "submit", "view_case", "add_note", "add_action"},
    "instructor":    {"view_own", "submit", "view_case", "add_note", "add_action"},
    "dsl":           {"view_own", "submit", "view_case", "add_note", "add_action",
                      "assign", "close", "export", "merge_split"},
    "safeguarding":  {"view_own", "submit", "view_case", "add_note", "add_action",
                      "assign", "close", "export", "merge_split"},
    "admin":         {"*"},      # all permissions
    "superadmin":    {"*"},
}


def can(user, permission):
    role = (user or {}).get("role", "").lower()
    perms = _ROLE_PERMISSIONS.get(role)
    if not perms:
        return False
    if "*" in perms:
        return True
    return permission in perms


def require(user, permission, raise_=False):
    if can(user, permission):
        return True
    audit_log(actor=(user or {}).get("username", "?"),
              actor_role=(user or {}).get("role", "?"),
              action="permission_denied",
              details=f"permission={permission}")
    if raise_:
        raise PermissionError(f"Role lacks permission: {permission}")
    return False


# ---- Audit log (38) --------------------------------------------------------

def audit_log(actor="?", action="?", case_id=None, details="", actor_role=None):
    try:
        conn = _connect(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO safeguarding_audit_log"
            "(ts, actor, actor_role, action, case_id, details) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), actor, actor_role, action,
             case_id, details),
        )
        conn.commit(); conn.close()
    except sqlite3.OperationalError:
        # init_db hasn't run yet — drop on the floor rather than crash callers
        pass


def list_audit_log(case_id=None, limit=200):
    conn = _connect(); cur = conn.cursor()
    if case_id is None:
        cur.execute(
            "SELECT id, ts, actor, actor_role, action, case_id, details "
            "FROM safeguarding_audit_log ORDER BY id DESC LIMIT ?", (limit,),
        )
    else:
        cur.execute(
            "SELECT id, ts, actor, actor_role, action, case_id, details "
            "FROM safeguarding_audit_log WHERE case_id=? "
            "ORDER BY id DESC LIMIT ?", (case_id, limit),
        )
    rows = cur.fetchall(); conn.close()
    return rows


# ---- Data retention (39) ---------------------------------------------------

# Default retention in days, keyed by closure outcome. Open cases get the
# longest horizon until closed.
RETENTION_DAYS_BY_OUTCOME = {
    None:         365 * 7,   # open / not yet closed: 7y default
    "NFA":        365 * 1,
    "UNFOUNDED":  365 * 1,
    "DUPLICATE":  365 * 1,
    "WITHDRAWN":  365 * 1,
    "SUPPORT":    365 * 3,
    "MONITORING": 365 * 5,
    "REFERRED":   365 * 7,
    "DISCIPLINE": 365 * 7,
    "MERGED":     365 * 1,
}


def _compute_retention_until(severity, outcome):
    days = RETENTION_DAYS_BY_OUTCOME.get(outcome,
                                         RETENTION_DAYS_BY_OUTCOME[None])
    # Critical cases get +3 years statutory retention bump.
    if severity == "CRITICAL":
        days += 365 * 3
    return datetime.now() + timedelta(days=days)


def _compute_retention_until_for_id(case_id, outcome):
    conn = _connect(); cur = conn.cursor()
    cur.execute("SELECT severity FROM safeguarding_submissions WHERE id=?",
                (case_id,))
    row = cur.fetchone(); conn.close()
    sev = row[0] if row else "NONE"
    return _compute_retention_until(sev, outcome)


def purge_due_records(actor="system", dry_run=False):
    """Soft-purge any closed case whose retention horizon has passed.
    Blanks out free-text content, attachments, audio, transcription and
    triage answers; preserves the row + categorical/aggregate fields so
    statutory counts stay accurate."""
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id FROM safeguarding_submissions "
        "WHERE COALESCE(purged,0)=0 AND lifecycle_state='Closed' "
        "AND retention_until IS NOT NULL AND retention_until < ?",
        (now,),
    )
    ids = [r[0] for r in cur.fetchall()]
    if dry_run or not ids:
        conn.close()
        return len(ids), ids
    placeholders = ",".join("?" for _ in ids)
    cur.execute(
        f"UPDATE safeguarding_submissions "
        f"SET content='', content_blob=NULL, content_encrypted=0, "
        f"    transcription='', transcription_blob=NULL, "
        f"    transcription_encrypted=0, attachments=NULL, audio_path=NULL, "
        f"    triage=NULL, review_note=NULL, purged=1 "
        f"WHERE id IN ({placeholders})",
        ids,
    )
    # Also drop case notes which are free-text by nature.
    cur.execute(
        f"DELETE FROM safeguarding_case_notes WHERE case_id IN ({placeholders})",
        ids,
    )
    conn.commit(); conn.close()
    audit_log(actor=actor, action="purge_due",
              details=f"ids={ids}")
    return len(ids), ids


# Feature 40 — Subject Access Request bundle.
def generate_sar_bundle(subject_username, out_dir, actor):
    """Build a zip containing all rows + notes + actions + referrals +
    notifications + audit entries for a given subject. Returns the zip path."""
    import csv
    import io
    import zipfile

    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", subject_username)[:40]
    out_path = os.path.join(out_dir, f"sar_{safe_user}_{stamp}.zip")

    subj_hash = hashlib.sha1(subject_username.lower().strip().encode("utf-8")
                             ).hexdigest()[:16]
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id FROM safeguarding_submissions "
        "WHERE username=? OR reporter_username=? OR linked_subject_id=?",
        (subject_username, subject_username, subj_hash),
    )
    ids = [r[0] for r in cur.fetchall()]
    conn.close()

    def _q_to_csv(query, params):
        conn = _connect(); cur = conn.cursor()
        cur.execute(query, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
        return buf.getvalue()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Top-level submissions (rich, with decrypted content)
        rich_rows = []
        for sid in ids:
            conn = _connect(); cur = conn.cursor()
            cur.execute("SELECT * FROM safeguarding_submissions WHERE id=?",
                        (sid,))
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            conn.close()
            row_dict = dict(zip(cols, row))
            # Resolve encrypted fields for the SAR copy.
            ct, tr = resolve_content(sid)
            row_dict["content"] = ct
            row_dict["transcription"] = tr
            row_dict.pop("content_blob", None)
            row_dict.pop("transcription_blob", None)
            rich_rows.append(row_dict)
        zf.writestr("submissions.json",
                    json.dumps(rich_rows, indent=2, default=str))

        placeholders = ",".join("?" for _ in ids) or "''"
        if ids:
            zf.writestr("case_notes.csv",
                        _q_to_csv(
                            f"SELECT * FROM safeguarding_case_notes "
                            f"WHERE case_id IN ({placeholders})",
                            ids))
            zf.writestr("action_items.csv",
                        _q_to_csv(
                            f"SELECT * FROM safeguarding_action_items "
                            f"WHERE case_id IN ({placeholders})",
                            ids))
            zf.writestr("referrals.csv",
                        _q_to_csv(
                            f"SELECT * FROM safeguarding_case_referrals "
                            f"WHERE case_id IN ({placeholders})",
                            ids))
            zf.writestr("assignments.csv",
                        _q_to_csv(
                            f"SELECT * FROM safeguarding_assignments "
                            f"WHERE case_id IN ({placeholders})",
                            ids))
            zf.writestr("notifications.csv",
                        _q_to_csv(
                            f"SELECT * FROM safeguarding_notifications "
                            f"WHERE case_id IN ({placeholders})",
                            ids))
            zf.writestr("audit_log.csv",
                        _q_to_csv(
                            f"SELECT * FROM safeguarding_audit_log "
                            f"WHERE case_id IN ({placeholders})",
                            ids))

        zf.writestr("README.txt",
                    f"Subject Access Request bundle\n"
                    f"Subject: {subject_username}\n"
                    f"Generated: {datetime.now().isoformat()}\n"
                    f"Cases included: {ids}\n")

    audit_log(actor=actor, action="sar_export",
              details=f"subject={subject_username} cases={ids} path={out_path}")
    return out_path, len(ids)


# ---------------------------------------------------------------------------
# Features 41-50
# ---------------------------------------------------------------------------

# Feature 41 — Mandatory reporting (KCSIE / Prevent / safeguarding statute).
# Categories that always trigger a mandatory-reporting workflow, plus any
# case touching a Minor or PREVENT vulnerability flag.
MANDATORY_TRIGGER_CATEGORIES = {
    RiskCategory.SELF_HARM,
    RiskCategory.EXPLOITATION,
    RiskCategory.EXTREMISM,
}
MANDATORY_TRIGGER_VULNS = {"Minor (<18)", "PREVENT concern"}


def check_mandatory_reporting(case_id, categories, vulnerability_flags,
                              actor="system"):
    """Flag the case as mandatory if its risk profile crosses the statutory
    threshold and queue a notification to the safeguarding lead inbox."""
    cats = set((categories or {}).keys())
    vulns = set(vulnerability_flags or [])
    triggered = bool(cats & MANDATORY_TRIGGER_CATEGORIES) or \
                bool(vulns & MANDATORY_TRIGGER_VULNS)
    if not triggered:
        return False
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET mandatory_reporting=1, mandatory_status=COALESCE(mandatory_status, 'Pending') "
        "WHERE id=?", (case_id,),
    )
    conn.commit(); conn.close()
    queue_notification(
        "email", "safeguarding-lead@example.edu",
        f"[MANDATORY REPORTING] case #{case_id}",
        f"Case #{case_id} meets statutory mandatory-reporting criteria. "
        f"Categories: {sorted(cats)}. Vulnerabilities: {sorted(vulns)}.\n"
        f"Please acknowledge in the Safeguarding portal.",
        case_id=case_id,
    )
    audit_log(actor=actor, action="mandatory_flag", case_id=case_id,
              details=f"cats={sorted(cats)} vulns={sorted(vulns)}")
    return True


def acknowledge_mandatory_report(case_id, actor, external_reference=""):
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET mandatory_status='Reported', mandatory_reported_at=? "
        "WHERE id=? AND mandatory_reporting=1",
        (now, case_id),
    )
    conn.commit(); conn.close()
    audit_log(actor=actor, action="mandatory_reported", case_id=case_id,
              details=f"ref={external_reference}")
    emit_webhook_event("case.mandatory_reported",
                       {"case_id": case_id, "reported_at": now,
                        "external_reference": external_reference},
                       case_id=case_id)


def list_mandatory_cases(status=None):
    q = ("SELECT id, full_name, username, severity, mandatory_status, "
         "       mandatory_reported_at "
         "FROM safeguarding_submissions WHERE mandatory_reporting=1 "
         "AND COALESCE(purged,0)=0")
    params = []
    if status:
        q += " AND COALESCE(mandatory_status, 'Pending')=?"
        params.append(status)
    q += " ORDER BY submitted_at DESC"
    conn = _connect(); cur = conn.cursor()
    cur.execute(q, params)
    rows = cur.fetchall(); conn.close()
    return rows


# Feature 42 — Whistleblowing channel separation.
# Whistleblowing cases are invisible to regular staff and only listable by
# users whose role is in WB_REVIEWER_ROLES.
WB_REVIEWER_ROLES = {"audit", "governance", "ombuds", "superadmin"}


def can_view_whistleblowing(user):
    return (user or {}).get("role", "").lower() in WB_REVIEWER_ROLES


def list_whistleblowing_cases(user):
    if not can_view_whistleblowing(user):
        return []
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, username, submitted_at, severity, status, "
        "       wb_independent_reviewer "
        "FROM safeguarding_submissions WHERE whistleblowing=1 "
        "AND COALESCE(purged,0)=0 ORDER BY submitted_at DESC",
    )
    rows = cur.fetchall(); conn.close()
    audit_log(actor=user.get("username", "?"),
              actor_role=user.get("role", "?"),
              action="wb_list", details=f"count={len(rows)}")
    return rows


# Feature 43 — Wellbeing / counselling appointment booking integration.
def create_wellbeing_appointment(case_id, when_iso, service="Wellbeing",
                                 notes="", actor="system"):
    """Try to forward to the shared wellbeing booking module if importable;
    otherwise store a stub reference. Returns the booking reference."""
    ref = f"WB-{case_id}-{datetime.now():%Y%m%d%H%M%S}"
    try:
        from education_system.university_system.modules.domain.health.wellness \
            import book_appointment  # type: ignore
        booked = book_appointment(case_id=case_id, when=when_iso,
                                  service=service, notes=notes)
        if booked:
            ref = str(booked)
    except Exception:
        logger.debug("Wellbeing booking module unavailable; using stub ref",
                     exc_info=True)
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_wellbeing_appt=? "
        "WHERE id=?", (ref, case_id),
    )
    conn.commit(); conn.close()
    add_case_note(case_id, actor,
                  f"[wellbeing] appointment booked: {ref} @ {when_iso} ({service})")
    audit_log(actor=actor, action="wellbeing_booked", case_id=case_id,
              details=f"ref={ref} when={when_iso}")
    return ref


# Feature 44 — Conduct / Academic Misconduct case link.
def link_conduct_case(case_id, conduct_ref, actor="system"):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_conduct_case=? WHERE id=?",
        (conduct_ref, case_id),
    )
    conn.commit(); conn.close()
    add_case_note(case_id, actor,
                  f"[conduct] linked to conduct case {conduct_ref}")
    audit_log(actor=actor, action="link_conduct", case_id=case_id,
              details=f"ref={conduct_ref}")


# Feature 45 — Halls / Accommodation incident cross-reference.
def link_halls_incident(case_id, incident_ref, actor="system"):
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_halls_incident=? "
        "WHERE id=?", (incident_ref, case_id),
    )
    conn.commit(); conn.close()
    add_case_note(case_id, actor,
                  f"[halls] linked to accommodation incident {incident_ref}")
    audit_log(actor=actor, action="link_halls", case_id=case_id,
              details=f"ref={incident_ref}")


# Feature 46 — Health-Centre referral with explicit consent.
def create_health_referral(case_id, consent, notes="", actor="system"):
    if not consent:
        raise PermissionError(
            "Health-Centre referrals require explicit student consent.")
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET health_referral_consent=1, health_referral_sent_at=? WHERE id=?",
        (now, case_id),
    )
    conn.commit(); conn.close()
    add_referral(case_id, "Health Centre",
                 contact="health-centre@example.edu",
                 reference_no=f"HC-{case_id}-{datetime.now():%Y%m%d%H%M%S}",
                 note=notes)
    audit_log(actor=actor, action="health_referral", case_id=case_id,
              details=f"consent=1 notes={notes[:60]}")


# Feature 47 — Tutor / Personal-Advisor notification with content redaction.
_PII_PATTERNS = [
    re.compile(r"\b\d{1,4}[ -]?\d{2,4}[ -]?\d{2,6}\b"),         # phone-ish
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),          # email
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
    """Send a redacted, high-level note to the personal tutor about a case
    needing pastoral awareness. Stores the exact text sent on the row."""
    content, _trans = resolve_content(case_id)
    redacted = (
        "A safeguarding concern about a student you support has been logged. "
        "Please be available for pastoral conversation. Operational detail "
        "is restricted.\n\nSummary (redacted):\n" + redact_for_tutor(content)
    )
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET tutor_notified_at=?, tutor_notification_redacted=? WHERE id=?",
        (now, redacted, case_id),
    )
    conn.commit(); conn.close()
    queue_notification(
        "email", f"{tutor_username}@example.edu",
        f"Pastoral awareness — case #{case_id}", redacted, case_id=case_id,
    )
    audit_log(actor=actor, action="tutor_notified", case_id=case_id,
              details=f"tutor={tutor_username}")


# Feature 48 — Webhook publisher for SIEM / external compliance tools.
def register_webhook(url, secret, event_filter="*", active=True,
                     actor="system"):
    now = datetime.now().isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_webhooks(url, secret, event_filter, active, "
        "created_at) VALUES (?,?,?,?,?)",
        (url, secret, event_filter, 1 if active else 0, now),
    )
    wid = cur.lastrowid
    conn.commit(); conn.close()
    audit_log(actor=actor, action="webhook_register",
              details=f"id={wid} url={url} filter={event_filter}")
    return wid


def list_webhooks():
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT id, url, event_filter, active, created_at, last_status, "
        "       last_sent_at FROM safeguarding_webhooks ORDER BY id ASC"
    )
    rows = cur.fetchall(); conn.close()
    return rows


def disable_webhook(webhook_id, actor="system"):
    conn = _connect(); cur = conn.cursor()
    cur.execute("UPDATE safeguarding_webhooks SET active=0 WHERE id=?",
                (webhook_id,))
    conn.commit(); conn.close()
    audit_log(actor=actor, action="webhook_disable",
              details=f"id={webhook_id}")


def _matches_filter(event, event_filter):
    if not event_filter or event_filter.strip() == "*":
        return True
    return event in {e.strip() for e in event_filter.split(",") if e.strip()}


def emit_webhook_event(event, payload, case_id=None):
    """POST a signed JSON payload to every active matching webhook. Network
    errors never raise; status is recorded on the delivery row + parent."""
    try:
        conn = _connect(); cur = conn.cursor()
        cur.execute(
            "SELECT id, url, secret, event_filter "
            "FROM safeguarding_webhooks WHERE active=1"
        )
        hooks = cur.fetchall(); conn.close()
    except sqlite3.OperationalError:
        return 0
    if not hooks:
        return 0

    import hmac
    import urllib.request

    body = json.dumps({"event": event, "payload": payload,
                       "ts": datetime.now().isoformat()}).encode("utf-8")
    sent = 0
    for wid, url, secret, event_filter in hooks:
        if not _matches_filter(event, event_filter or "*"):
            continue
        sig = hmac.new((secret or "").encode("utf-8"),
                       body, hashlib.sha256).hexdigest()
        code, resp = None, ""
        try:
            req = urllib.request.Request(
                url, data=body, method="POST",
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
        now = datetime.now().isoformat()
        try:
            conn = _connect(); cur = conn.cursor()
            cur.execute(
                "INSERT INTO safeguarding_webhook_deliveries"
                "(webhook_id, case_id, event, payload, sent_at, "
                " response_code, response_body) VALUES (?,?,?,?,?,?,?)",
                (wid, case_id, event, body.decode("utf-8"),
                 now, code, resp),
            )
            cur.execute(
                "UPDATE safeguarding_webhooks SET last_status=?, last_sent_at=? "
                "WHERE id=?", (str(code), now, wid),
            )
            conn.commit(); conn.close()
        except sqlite3.OperationalError:
            pass
        sent += 1
    return sent


# Feature 49 — Anonymised statistics dashboard for senior leadership.
# Returns aggregate counts only — no usernames, no free text, no per-case rows.
def leadership_stats(days=90):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND COALESCE(purged,0)=0", (cutoff,))
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT severity, COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND COALESCE(purged,0)=0 GROUP BY severity",
        (cutoff,))
    by_sev = dict(cur.fetchall())
    cur.execute(
        "SELECT lifecycle_state, COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND COALESCE(purged,0)=0 "
        "GROUP BY lifecycle_state", (cutoff,))
    by_lifecycle = dict(cur.fetchall())
    cur.execute(
        "SELECT outcome_code, COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND outcome_code IS NOT NULL "
        "AND COALESCE(purged,0)=0 GROUP BY outcome_code", (cutoff,))
    by_outcome = dict(cur.fetchall())
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND sla_breached=1 "
        "AND COALESCE(purged,0)=0", (cutoff,))
    sla_breaches = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND mandatory_reporting=1 "
        "AND COALESCE(purged,0)=0", (cutoff,))
    mandatory = cur.fetchone()[0]
    # Average days-to-close for closed cases in window
    cur.execute(
        "SELECT submitted_at, reviewed_at FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND lifecycle_state='Closed' "
        "AND reviewed_at IS NOT NULL", (cutoff,))
    diffs = []
    for sub, rev in cur.fetchall():
        try:
            diffs.append((datetime.fromisoformat(rev)
                          - datetime.fromisoformat(sub)).total_seconds() / 86400)
        except (TypeError, ValueError):
            pass
    avg_days = round(sum(diffs) / len(diffs), 1) if diffs else None
    conn.close()
    return {
        "period_days": days,
        "total": total,
        "by_severity": by_sev,
        "by_lifecycle": by_lifecycle,
        "by_outcome": by_outcome,
        "sla_breaches": sla_breaches,
        "mandatory_flags": mandatory,
        "avg_days_to_close": avg_days,
    }


# Feature 50 — Safeguarding-training tracker.
DEFAULT_TRAINING_VALIDITY_DAYS = 365 * 3   # statutory 3-year refresh


def record_training(username, full_name, module, completed_at=None,
                    valid_days=DEFAULT_TRAINING_VALIDITY_DAYS, actor="system"):
    completed = completed_at or datetime.now().isoformat()
    try:
        completed_dt = datetime.fromisoformat(completed)
    except ValueError:
        completed_dt = datetime.now()
    expires = (completed_dt + timedelta(days=valid_days)).isoformat()
    conn = _connect(); cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO safeguarding_training"
            "(username, full_name, module, completed_at, expires_at) "
            "VALUES (?,?,?,?,?)",
            (username, full_name, module, completed, expires),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass        # duplicate completion record — already on file
    conn.close()
    audit_log(actor=actor, action="training_record",
              details=f"user={username} module={module} expires={expires}")
    return expires


def training_status(username):
    """Return per-module status: 'Current' / 'Expiring soon' (≤60d) / 'Expired' / 'Missing'."""
    now = datetime.now()
    conn = _connect(); cur = conn.cursor()
    cur.execute(
        "SELECT module, MAX(completed_at), MAX(expires_at) "
        "FROM safeguarding_training WHERE username=? GROUP BY module",
        (username,),
    )
    rows = cur.fetchall(); conn.close()
    out = {}
    for module, _completed, expires in rows:
        if not expires:
            out[module] = "Current"
            continue
        try:
            ex_dt = datetime.fromisoformat(expires)
        except ValueError:
            out[module] = "Current"
            continue
        if ex_dt < now:
            out[module] = "Expired"
        elif (ex_dt - now).days <= 60:
            out[module] = "Expiring soon"
        else:
            out[module] = "Current"
    return out


def training_compliance_summary():
    """Aggregate compliance across everyone with a training record on file."""
    conn = _connect(); cur = conn.cursor()
    cur.execute("SELECT DISTINCT username FROM safeguarding_training")
    users = [r[0] for r in cur.fetchall()]
    conn.close()
    if not users:
        return {"users_tracked": 0, "current_pct": 0.0, "expired": 0,
                "expiring_soon": 0, "current": 0}
    current = expired = expiring = 0
    for u in users:
        status = training_status(u)
        # User counts as current only if every recorded module is current.
        states = set(status.values()) or {"Current"}
        if "Expired" in states:
            expired += 1
        elif "Expiring soon" in states:
            expiring += 1
        else:
            current += 1
    return {
        "users_tracked": len(users),
        "current": current,
        "expiring_soon": expiring,
        "expired": expired,
        "current_pct": round(100 * current / len(users), 1),
    }


# ---------------------------------------------------------------------------
# Feature helpers: encryption, drafts, duplicates, contact token, i18n, exit
# ---------------------------------------------------------------------------

_MODULE_DIR     = os.path.dirname(os.path.abspath(__file__))
_SECURE_DIR     = os.path.join(_MODULE_DIR, "secure_uploads")
_KEY_FILE       = os.path.join(_MODULE_DIR, ".safeguard.key")
_DRAFT_DIR      = os.path.join(_MODULE_DIR, "drafts")
_QUICK_EXIT_URL = "https://www.google.com/search?q=weather"


def _ensure_dirs():
    for d in (_SECURE_DIR, _DRAFT_DIR):
        os.makedirs(d, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass


def _get_or_create_key() -> bytes:
    """Return the Fernet key for at-rest attachment encryption. Generated once."""
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read().strip()
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
    except Exception:
        key = base64.urlsafe_b64encode(secrets.token_bytes(32))
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    try:
        os.chmod(_KEY_FILE, 0o600)
    except OSError:
        pass
    return key


def encrypt_and_store(src_path: str) -> str | None:
    """Encrypt the file at src_path with Fernet and store it under secure_uploads/.
    Returns the stored filename (not full path) or None on failure. Falls back to
    plain copy with a .plain suffix if cryptography is unavailable."""
    if not src_path or not os.path.isfile(src_path):
        return None
    _ensure_dirs()
    base = os.path.basename(src_path)
    safe_base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:80]
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    token = secrets.token_hex(4)
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_or_create_key())
        with open(src_path, "rb") as r:
            blob = f.encrypt(r.read())
        out_name = f"{stamp}_{token}_{safe_base}.enc"
        with open(os.path.join(_SECURE_DIR, out_name), "wb") as w:
            w.write(blob)
        return out_name
    except Exception:
        logger.warning("Encryption unavailable; storing attachment in plain form", exc_info=True)
        out_name = f"{stamp}_{token}_{safe_base}.plain"
        shutil.copy2(src_path, os.path.join(_SECURE_DIR, out_name))
        return out_name


def decrypt_to_temp(stored_name: str) -> str | None:
    """Decrypt a stored attachment to a temp file and return that path."""
    if not stored_name:
        return None
    path = os.path.join(_SECURE_DIR, stored_name)
    if not os.path.isfile(path):
        return None
    if stored_name.endswith(".plain"):
        return path
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_or_create_key())
        with open(path, "rb") as r:
            data = f.decrypt(r.read())
        import tempfile
        out = tempfile.NamedTemporaryFile(
            delete=False,
            suffix="_" + re.sub(r"\.enc$", "", stored_name.split("_", 3)[-1]),
        )
        out.write(data)
        out.close()
        return out.name
    except Exception:
        logger.warning("Could not decrypt attachment %s", stored_name, exc_info=True)
        return None


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
_DUP_RATIO      = 0.85


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


def _draft_path(username: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", username or "anon")
    return os.path.join(_DRAFT_DIR, f"{safe}.draft.json")


def save_draft(username: str, payload: dict) -> None:
    if not username:
        return
    _ensure_dirs()
    try:
        with open(_draft_path(username), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        logger.debug("Failed to save draft for %s", username, exc_info=True)


def load_draft(username: str) -> dict:
    try:
        with open(_draft_path(username), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def clear_draft(username: str) -> None:
    p = _draft_path(username)
    if os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass


def quick_exit():
    """Safe-exit: blank the screen, navigate browser to an innocuous page, then quit."""
    try:
        webbrowser.open_new_tab(_QUICK_EXIT_URL)
    except Exception:
        pass
    try:
        for w in tk._default_root.winfo_children() if tk._default_root else []:
            try:
                w.destroy()
            except tk.TclError:
                pass
        if tk._default_root is not None:
            tk._default_root.destroy()
    except Exception:
        pass
    os._exit(0)


def maybe_transcribe(audio_path: str) -> str | None:
    """Best-effort transcription. Returns None if no engine is available."""
    if not audio_path:
        return None
    try:
        import speech_recognition as sr  # type: ignore
        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as src:
            audio = r.record(src)
        return r.recognize_google(audio)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# i18n — translations live in
#   university_system/data/locales/<lang>/safeguarding/safeguarding.json
# loaded via the shared i18n engine and looked up under the "safeguarding.*"
# namespace. English is the automatic fallback for any missing key/language.
# ---------------------------------------------------------------------------

_LANG_NAMES = {
    "en": "English", "es": "Español", "fr": "Français", "de": "Deutsch",
    "zh": "中文", "ar": "العربية",
    "pt": "Português", "pl": "Polski",
    "ur": "اردو", "cy": "Cymraeg",
}

_I18N_READY = False


def _ensure_i18n_loaded():
    global _I18N_READY
    if _I18N_READY:
        return
    try:
        from education_system.university_system.core.i18n import init_i18n
        init_i18n()
        _I18N_READY = True
    except Exception:
        logger.debug("Shared i18n unavailable; tr() will fall back to keys",
                     exc_info=True)


def tr(key: str, lang: str = "en", **kwargs) -> str:
    """Translate ``safeguarding.<key>`` in *lang* with English fallback.

    Translations live in ``university_system/data/locales/<lang>/safeguarding/
    safeguarding.json`` and are loaded via the shared i18n engine.
    """
    _ensure_i18n_loaded()
    full_key = f"safeguarding.{key}"
    try:
        from education_system.shared.i18n.core import _translations, _ensure_loaded
        _ensure_loaded()
        for code in (lang, "en"):
            node = _translations.get(code) or {}
            for part in full_key.split("."):
                if isinstance(node, dict):
                    node = node.get(part)
                else:
                    node = None
                    break
                if node is None:
                    break
            if isinstance(node, str):
                try:
                    return node.format(**kwargs) if kwargs else node
                except (KeyError, IndexError):
                    return node
    except Exception:
        logger.debug("tr() lookup failed for %s", full_key, exc_info=True)
    return key


def fetch_submissions(status_filter=None, severity_filter=None,
                      lifecycle_filter=None, include_whistleblowing=False):
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
    q += " ORDER BY CASE severity " \
         "WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 " \
         "WHEN 'MEDIUM' THEN 3 WHEN 'LOW' THEN 4 ELSE 5 END, " \
         "submitted_at DESC"
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


def _remove_legacy_db():
    """Delete the old per-module safeguarding.db (and WAL/SHM siblings)
    — data now lives in the central student_records.db."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = _LEGACY_DB_FILE + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy safeguarding DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

SUPPORT_RESOURCES = """If you are struggling right now, please reach out:

  • Samaritans (UK)   116 123  — free, 24/7
  • Nightline (student peer support)  — nightline.ac.uk
  • University Wellbeing Service      — contact via portal
  • Emergency services                — 999 / 112

You are not alone. Speaking to someone can help."""


class SafeguardingApp(tk.Tk):
    def __init__(self, host=None):
        """Build the Safeguarding portal.

        ``host`` may be:
          * ``None`` (legacy / subprocess) — initialise as a ``tk.Tk``
            root and own the window/mainloop.
          * a workspace tab ``Frame`` (passed by ``open_in_workspace``)
            — skip Tk init and build widgets onto the host frame.
            ``mainloop()`` becomes a no-op (caller owns it).

        Same shape as ComplaintsPortal (8.117.49).
        """
        if host is None:
            super().__init__()
            self.title("University Portal — Safeguarding System")
            self.geometry("1000x680")
            self.configure(bg="#f4f6fa")
            self._host = self
            self._owns_root = True
        else:
            self._host = host
            self._owns_root = False
            try:
                host.configure(bg="#f4f6fa")
            except tk.TclError:
                pass

        self.user = _get_current_user()
        # Default language — student wizard may overwrite this later. Set
        # unconditionally because tk.Misc.__getattr__ proxies missing
        # attributes to self.tk, which recurses in embedded mode.
        self.lang = (self.user or {}).get("language") or "en"

        # Ensure schema exists — when launched embedded from the main GUI,
        # ``main()`` is bypassed so init_db() would not otherwise run.
        try:
            init_db()
        except Exception:
            logger.warning("init_db() failed during embedded launch",
                           exc_info=True)

        # ttk theming — process-global style; only configure named styles
        # to avoid leaking into the host main GUI when embedded.
        style = ttk.Style(self._host)
        style.configure("Header.TLabel",
                        font=("Segoe UI", 16, "bold"),
                        background="#f4f6fa")
        style.configure("Sub.TLabel",
                        font=("Segoe UI", 10),
                        background="#f4f6fa", foreground="#555")

        self.container = tk.Frame(self._host, bg="#f4f6fa")
        self.container.pack(fill="both", expand=True)

        if not self.user:
            self.show_no_auth()
        elif _is_staff_role(self.user.get('role')):
            logger.info("Safeguarding starting console=staff user=%s role=%s",
                        self.user.get('username'), self.user.get('role'))
            self.show_staff_dashboard()
        else:
            logger.info("Safeguarding starting console=student user=%s role=%s",
                        self.user.get('username'), self.user.get('role'))
            self.show_student_dashboard()

    # ---------- embedded-mode shims ----------
    # When ``host`` was supplied, ``super().__init__()`` was skipped,
    # so any inherited ``tk.Misc`` method that touches ``self.tk``
    # (mainloop / destroy / bind / unbind) crashes. Redirect those
    # calls to the host frame.
    def mainloop(self, n: int = 0):
        if not self._owns_root:
            return
        super().mainloop(n)

    def destroy(self):
        if self._owns_root:
            super().destroy()
        else:
            try:
                self._host.destroy()
            except tk.TclError:
                pass

    def unbind(self, sequence, funcid=None):
        try:
            return self._host.unbind(sequence, funcid)
        except tk.TclError:
            pass

    def bind(self, sequence=None, func=None, add=None):
        return self._host.bind(sequence, func, add)

    # ---------- helpers ----------
    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    # ---------- no-auth fallback ----------
    def show_no_auth(self):
        self._clear()
        frame = tk.Frame(self.container, bg="#f4f6fa")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(frame, text="🔒 Authentication Required",
                  style="Header.TLabel").pack(pady=(0, 8))
        ttk.Label(frame,
                  text="Please launch this portal from the main\n"
                       "University System after signing in.",
                  style="Sub.TLabel", justify="center").pack(pady=(0, 14))
        ttk.Button(frame, text="Close",
                   command=self.destroy).pack()

    # ---------- student dashboard (wizard) ----------
    def show_student_dashboard(self):
        self._clear()
        self.unbind("<Return>")
        self._build_topbar(f"Welcome, {self.user['full_name']}")

        # Per-user state held on the instance
        self.lang = (self.user.get("language") or "en")
        self.wizard_step = 0
        self.wizard_state = {
            "consent_disclosure": False,
            "consent_contact": False,
            "anonymous": False,
            "on_behalf_of": False,
            "subject_relation": "",
            "triage": {"q1": "", "q2": "", "q3": "", "q4": ""},
            "content": "",
            "attachments": [],   # list of dicts: {"orig": str, "stored": str|None}
            "audio_orig": "",
            "audio_stored": "",
            "transcription": "",
            "vulnerability_flags": [],
            "case_location": "",
            "case_department": "",
            "whistleblowing": False,
            "wb_independent_reviewer": "",
        }
        existing_draft = load_draft(self.user.get("username") or "")
        if existing_draft:
            try:
                self.wizard_state.update(existing_draft.get("state") or {})
                self.lang = existing_draft.get("lang") or self.lang
                messagebox.showinfo("Draft", tr("draft_restored", self.lang))
            except Exception:
                pass

        # Layout: wizard on left, history + support on right
        body = tk.Frame(self.container, bg="#f4f6fa")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        left = tk.Frame(body, bg="#f4f6fa")
        right = tk.Frame(body, bg="#f4f6fa", width=300)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y", padx=(15, 0))

        self.wizard_host = tk.Frame(left, bg="#f4f6fa")
        self.wizard_host.pack(fill="both", expand=True)
        self._render_wizard()

        # Right column: anonymous check + history + support
        anon_btn = ttk.Button(right, text=tr("check_anon", self.lang),
                              command=self._open_anon_check)
        anon_btn.pack(anchor="w", pady=(0, 8))

        ttk.Label(right, text="Your recent submissions",
                  style="Sub.TLabel").pack(anchor="w")
        self.history_list = tk.Listbox(right, width=40, height=10,
                                       font=("Segoe UI", 9))
        self.history_list.pack(fill="x", pady=(2, 15))
        self._refresh_student_history()

        support = tk.Frame(right, bg="#eaf4ec", bd=1, relief="solid")
        support.pack(fill="x")
        tk.Label(support, text="Need help now?", bg="#eaf4ec",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                    padx=10, pady=(8, 4))
        tk.Label(support, text=SUPPORT_RESOURCES, bg="#eaf4ec",
                 justify="left", font=("Segoe UI", 9),
                 wraplength=280).pack(anchor="w", padx=10, pady=(0, 10))

    # ---- wizard rendering ----
    def _render_wizard(self):
        for w in self.wizard_host.winfo_children():
            w.destroy()

        # Step pills
        steps = [tr("step_consent", self.lang), tr("step_triage", self.lang),
                 tr("step_details", self.lang), tr("step_review", self.lang)]
        pill = tk.Frame(self.wizard_host, bg="#f4f6fa")
        pill.pack(fill="x", pady=(0, 8))
        for i, name in enumerate(steps):
            active = (i == self.wizard_step)
            tk.Label(pill, text=f"  {i+1}. {name}  ",
                     bg="#1f3a5f" if active else "#d0d6e0",
                     fg="white" if active else "#333",
                     font=("Segoe UI", 9, "bold" if active else "normal"),
                     padx=6, pady=4).pack(side="left", padx=2)

        body = tk.Frame(self.wizard_host, bg="white", bd=1, relief="solid")
        body.pack(fill="both", expand=True)
        renderer = (self._step_consent, self._step_triage,
                    self._step_details, self._step_review)[self.wizard_step]
        renderer(body)

        # Nav row
        nav = tk.Frame(self.wizard_host, bg="#f4f6fa")
        nav.pack(fill="x", pady=8)
        if self.wizard_step > 0:
            ttk.Button(nav, text=tr("back", self.lang),
                       command=self._wizard_back).pack(side="left")
        if self.wizard_step < 3:
            ttk.Button(nav, text=tr("next", self.lang),
                       command=self._wizard_next).pack(side="right")
        else:
            ttk.Button(nav, text=tr("submit", self.lang),
                       command=self._wizard_submit).pack(side="right")

    def _wizard_back(self):
        self._collect_current_step()
        self.wizard_step = max(0, self.wizard_step - 1)
        self._render_wizard()

    def _wizard_next(self):
        if not self._collect_current_step(validate=True):
            return
        self._persist_draft()
        self.wizard_step = min(3, self.wizard_step + 1)
        self._render_wizard()

    def _persist_draft(self):
        save_draft(self.user.get("username") or "",
                   {"lang": self.lang, "state": self.wizard_state})

    # ---- step 1: consent / options / language ----
    def _step_consent(self, host):
        pad = dict(padx=14, pady=4)
        tk.Label(host, text=tr("consent_heading", self.lang), bg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(host, text=tr("consent_body", self.lang), bg="white",
                 wraplength=520, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", **pad)

        # Language selector
        lang_row = tk.Frame(host, bg="white")
        lang_row.pack(fill="x", **pad)
        tk.Label(lang_row, text=tr("language", self.lang) + ":",
                 bg="white").pack(side="left")
        self._lang_var = tk.StringVar(value=self.lang)
        codes = list(_LANG_NAMES.keys())
        names = [_LANG_NAMES[c] for c in codes]
        combo = ttk.Combobox(lang_row, values=names, state="readonly", width=18)
        combo.current(codes.index(self.lang) if self.lang in codes else 0)
        combo.pack(side="left", padx=6)

        def on_lang(_e):
            new = codes[combo.current()]
            if new != self.lang:
                self.lang = new
                self._collect_current_step()
                self._render_wizard()
        combo.bind("<<ComboboxSelected>>", on_lang)

        # Consent checkboxes
        self._cv_disclose = tk.BooleanVar(value=self.wizard_state["consent_disclosure"])
        self._cv_contact  = tk.BooleanVar(value=self.wizard_state["consent_contact"])
        self._cv_anon     = tk.BooleanVar(value=self.wizard_state["anonymous"])
        self._cv_obo      = tk.BooleanVar(value=self.wizard_state["on_behalf_of"])

        tk.Checkbutton(host, text=tr("consent_disclose", self.lang),
                       variable=self._cv_disclose, bg="white",
                       wraplength=520, justify="left").pack(anchor="w", **pad)
        tk.Checkbutton(host, text=tr("consent_contact", self.lang),
                       variable=self._cv_contact, bg="white",
                       wraplength=520, justify="left").pack(anchor="w", **pad)
        tk.Checkbutton(host, text=tr("anonymous", self.lang),
                       variable=self._cv_anon, bg="white").pack(anchor="w", **pad)
        tk.Checkbutton(host, text=tr("on_behalf", self.lang),
                       variable=self._cv_obo, bg="white",
                       command=self._toggle_obo_field).pack(anchor="w", **pad)

        self._obo_row = tk.Frame(host, bg="white")
        self._obo_row.pack(fill="x", **pad)
        self._toggle_obo_field()

        # Feature 17 — vulnerability flags
        tk.Label(host, text="Vulnerability factors (optional):", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        self._vuln_vars = {}
        existing = set(self.wizard_state.get("vulnerability_flags") or [])
        vuln_row = tk.Frame(host, bg="white")
        vuln_row.pack(anchor="w", padx=20)
        for i, flag in enumerate(VULNERABILITY_FLAGS):
            var = tk.BooleanVar(value=(flag in existing))
            self._vuln_vars[flag] = var
            tk.Checkbutton(vuln_row, text=flag, variable=var,
                           bg="white").grid(row=i // 2, column=i % 2,
                                            sticky="w", padx=4)

        # Feature 19 — location & department for the incident
        loc_row = tk.Frame(host, bg="white")
        loc_row.pack(fill="x", **pad)
        tk.Label(loc_row, text="Location:", bg="white", width=12,
                 anchor="w").pack(side="left")
        self._loc_entry = ttk.Entry(loc_row, width=22)
        self._loc_entry.insert(0, self.wizard_state.get("case_location") or "")
        self._loc_entry.pack(side="left", padx=4)
        tk.Label(loc_row, text="  Department:", bg="white").pack(side="left")
        self._dept_entry = ttk.Entry(loc_row, width=22)
        self._dept_entry.insert(0, self.wizard_state.get("case_department") or "")
        self._dept_entry.pack(side="left", padx=4)

        # Feature 42 — Whistleblowing channel
        self._cv_wb = tk.BooleanVar(value=self.wizard_state["whistleblowing"])
        tk.Checkbutton(host,
                       text="This is a whistleblowing disclosure "
                            "(handled by independent reviewers only)",
                       variable=self._cv_wb, bg="white",
                       command=self._toggle_wb_field,
                       wraplength=520, justify="left").pack(anchor="w", **pad)
        self._wb_row = tk.Frame(host, bg="white")
        self._wb_row.pack(fill="x", **pad)
        self._toggle_wb_field()

    def _toggle_wb_field(self):
        for w in self._wb_row.winfo_children():
            w.destroy()
        if self._cv_wb.get():
            tk.Label(self._wb_row,
                     text="Preferred independent reviewer (optional username):",
                     bg="white").pack(side="left")
            self._wb_entry = ttk.Entry(self._wb_row, width=22)
            self._wb_entry.insert(
                0, self.wizard_state.get("wb_independent_reviewer") or "")
            self._wb_entry.pack(side="left", padx=6)

    def _toggle_obo_field(self):
        for w in self._obo_row.winfo_children():
            w.destroy()
        if self._cv_obo.get():
            tk.Label(self._obo_row, text=tr("subject_relation", self.lang) + ":",
                     bg="white").pack(side="left")
            self._obo_entry = ttk.Entry(self._obo_row, width=30)
            self._obo_entry.insert(0, self.wizard_state.get("subject_relation") or "")
            self._obo_entry.pack(side="left", padx=6)

    # ---- step 2: triage ----
    def _step_triage(self, host):
        pad = dict(padx=14, pady=(6, 2))
        tk.Label(host, text=tr("step_triage", self.lang), bg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(14, 4))

        self._tr_q1 = self._labelled_entry(host, tr("triage_q1", self.lang),
                                           self.wizard_state["triage"].get("q1", ""))
        self._tr_q2 = self._labelled_entry(host, tr("triage_q2", self.lang),
                                           self.wizard_state["triage"].get("q2", ""))

        # q3 — immediate danger (radio)
        tk.Label(host, text=tr("triage_q3", self.lang), bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        self._tr_q3 = tk.StringVar(value=self.wizard_state["triage"].get("q3", "no"))
        row = tk.Frame(host, bg="white")
        row.pack(anchor="w", padx=20)
        for code, label in (("yes", tr("yes", self.lang)),
                            ("no", tr("no", self.lang)),
                            ("unsure", tr("unsure", self.lang))):
            tk.Radiobutton(row, text=label, value=code, variable=self._tr_q3,
                           bg="white").pack(side="left", padx=4)

        # q4 — told anyone
        tk.Label(host, text=tr("triage_q4", self.lang), bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        self._tr_q4 = tk.StringVar(value=self.wizard_state["triage"].get("q4", "no"))
        row2 = tk.Frame(host, bg="white")
        row2.pack(anchor="w", padx=20, pady=(0, 10))
        for code, label in (("yes", tr("yes", self.lang)), ("no", tr("no", self.lang))):
            tk.Radiobutton(row2, text=label, value=code, variable=self._tr_q4,
                           bg="white").pack(side="left", padx=4)

    def _labelled_entry(self, host, label, initial):
        tk.Label(host, text=label, bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(6, 2))
        e = ttk.Entry(host, width=70)
        e.insert(0, initial or "")
        e.pack(anchor="w", padx=14)
        return e

    # ---- step 3: details + attachments + audio ----
    def _step_details(self, host):
        tk.Label(host, text=tr("step_details", self.lang), bg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(14, 4))

        self.txt_input = scrolledtext.ScrolledText(
            host, wrap="word", font=("Segoe UI", 11),
            relief="flat", padx=10, pady=10, height=10,
        )
        if self.wizard_state.get("content"):
            self.txt_input.insert("1.0", self.wizard_state["content"])
        self.txt_input.pack(fill="both", expand=True, padx=14, pady=4)
        # Auto-save on each key release
        self.txt_input.bind("<KeyRelease>", lambda _e: self._autosave_content())

        # Attachments
        tk.Label(host, text=tr("attachments", self.lang) + ":",
                 bg="white", font=("Segoe UI", 9, "bold")
                 ).pack(anchor="w", padx=14, pady=(8, 2))
        self._att_list = tk.Listbox(host, height=4, font=("Segoe UI", 9))
        for a in self.wizard_state.get("attachments", []):
            self._att_list.insert("end", os.path.basename(a.get("orig") or "(file)"))
        self._att_list.pack(fill="x", padx=14)

        row = tk.Frame(host, bg="white")
        row.pack(anchor="w", padx=14, pady=4)
        ttk.Button(row, text=tr("add_file", self.lang),
                   command=self._add_attachment).pack(side="left")
        ttk.Button(row, text=tr("add_audio", self.lang),
                   command=self._add_audio).pack(side="left", padx=6)
        ttk.Button(row, text=tr("remove", self.lang),
                   command=self._remove_attachment).pack(side="left")
        if self.wizard_state.get("audio_orig"):
            tk.Label(row, text="🎙 " + os.path.basename(self.wizard_state["audio_orig"]),
                     bg="white", fg="#1f3a5f").pack(side="left", padx=8)

    def _autosave_content(self):
        try:
            self.wizard_state["content"] = self.txt_input.get("1.0", "end").strip()
            self._persist_draft()
        except tk.TclError:
            pass

    def _add_attachment(self):
        path = filedialog.askopenfilename(
            title=tr("add_file", self.lang),
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return
        stored = encrypt_and_store(path)
        self.wizard_state["attachments"].append({"orig": path, "stored": stored})
        self._att_list.insert("end", os.path.basename(path))
        self._persist_draft()

    def _remove_attachment(self):
        sel = list(self._att_list.curselection())
        for idx in reversed(sel):
            try:
                entry = self.wizard_state["attachments"].pop(idx)
                if entry.get("stored"):
                    p = os.path.join(_SECURE_DIR, entry["stored"])
                    if os.path.exists(p):
                        os.remove(p)
            except (IndexError, OSError):
                pass
            self._att_list.delete(idx)
        self._persist_draft()

    def _add_audio(self):
        path = filedialog.askopenfilename(
            title=tr("add_audio", self.lang),
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.ogg *.flac"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        stored = encrypt_and_store(path)
        transcription = maybe_transcribe(path) or ""
        self.wizard_state["audio_orig"] = path
        self.wizard_state["audio_stored"] = stored or ""
        self.wizard_state["transcription"] = transcription
        self._persist_draft()
        if transcription:
            messagebox.showinfo(
                "Audio attached",
                f"Auto-transcribed:\n\n{transcription[:400]}",
            )
        else:
            messagebox.showinfo(
                "Audio attached",
                "Audio note saved. Automatic transcription is not available; "
                "a reviewer will listen to the note.",
            )
        # Re-render to show the audio chip
        self._render_wizard()

    # ---- step 4: review & submit ----
    def _step_review(self, host):
        tk.Label(host, text=tr("step_review", self.lang), bg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        s = self.wizard_state

        def line(label, value):
            row = tk.Frame(host, bg="white")
            row.pack(fill="x", padx=14, pady=2)
            tk.Label(row, text=label + ":", bg="white",
                     font=("Segoe UI", 9, "bold"), width=24, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=str(value), bg="white",
                     wraplength=400, justify="left",
                     font=("Segoe UI", 9)).pack(side="left")

        line("Language", _LANG_NAMES.get(self.lang, self.lang))
        line("Anonymous", "Yes" if s["anonymous"] else "No")
        line("On behalf of another", "Yes" if s["on_behalf_of"] else "No")
        if s["on_behalf_of"]:
            line("Relation", s.get("subject_relation") or "(unspecified)")
        line("Immediate danger", s["triage"].get("q3", "no"))
        line("Summary", (s["triage"].get("q1") or "")[:120])
        line("Attachments", len(s.get("attachments") or []))
        if s.get("audio_orig"):
            line("Audio note", os.path.basename(s["audio_orig"]))
        line("Message length", f"{len(s.get('content') or '')} chars")

    # ---- step collection / submit ----
    def _collect_current_step(self, validate: bool = False) -> bool:
        try:
            if self.wizard_step == 0:
                self.wizard_state["consent_disclosure"] = bool(self._cv_disclose.get())
                self.wizard_state["consent_contact"]    = bool(self._cv_contact.get())
                self.wizard_state["anonymous"]          = bool(self._cv_anon.get())
                self.wizard_state["on_behalf_of"]       = bool(self._cv_obo.get())
                if self._cv_obo.get() and hasattr(self, "_obo_entry"):
                    self.wizard_state["subject_relation"] = self._obo_entry.get().strip()
                if hasattr(self, "_vuln_vars"):
                    self.wizard_state["vulnerability_flags"] = [
                        flag for flag, var in self._vuln_vars.items() if var.get()
                    ]
                if hasattr(self, "_loc_entry"):
                    self.wizard_state["case_location"] = self._loc_entry.get().strip()
                if hasattr(self, "_dept_entry"):
                    self.wizard_state["case_department"] = self._dept_entry.get().strip()
                if hasattr(self, "_cv_wb"):
                    self.wizard_state["whistleblowing"] = bool(self._cv_wb.get())
                if hasattr(self, "_wb_entry") and self._cv_wb.get():
                    self.wizard_state["wb_independent_reviewer"] = \
                        self._wb_entry.get().strip()
                if validate and not self._cv_disclose.get():
                    messagebox.showwarning("Consent required",
                                           tr("consent_disclose", self.lang))
                    return False
            elif self.wizard_step == 1:
                self.wizard_state["triage"] = {
                    "q1": self._tr_q1.get().strip(),
                    "q2": self._tr_q2.get().strip(),
                    "q3": self._tr_q3.get(),
                    "q4": self._tr_q4.get(),
                }
                if validate and not self.wizard_state["triage"]["q1"]:
                    messagebox.showwarning("Required",
                                           tr("triage_q1", self.lang))
                    return False
            elif self.wizard_step == 2:
                self.wizard_state["content"] = self.txt_input.get("1.0", "end").strip()
                if validate and not self.wizard_state["content"]:
                    messagebox.showwarning("Required", tr("step_details", self.lang))
                    return False
        except (tk.TclError, AttributeError):
            pass
        return True

    def _wizard_submit(self):
        if not self._collect_current_step(validate=True):
            return
        s = self.wizard_state
        text = s.get("content") or ""
        if not text:
            messagebox.showwarning("Empty", tr("step_details", self.lang))
            self.wizard_step = 2
            self._render_wizard()
            return

        # Duplicate detection
        username = self.user.get("username") or ""
        dup_id = find_duplicate(username, text)
        if dup_id and not messagebox.askyesno(
                "Possible duplicate",
                tr("duplicate_warn", self.lang, sid=dup_id)):
            return

        matches, overall = analyse_text(text)
        # Also analyse the audio transcription if present
        if s.get("transcription"):
            tr_matches, tr_overall = analyse_text(s["transcription"])
            for cat, info in tr_matches.items():
                matches.setdefault(cat, info)
            if SEVERITY_ORDER.get(tr_overall, 0) > SEVERITY_ORDER.get(overall, 0):
                overall = tr_overall

        # Feature 12 — NLP categorisation alongside the regex matches.
        nlp_scores, nlp_overall_conf = nlp_classify(
            (text or "") + " " + (s.get("transcription") or "")
        )
        # If NLP flags a CRITICAL-tier category not already in regex matches,
        # incorporate it so it's surfaced to staff.
        for cat in nlp_scores:
            if cat not in matches:
                matches[cat] = {
                    "severity": RISK_PATTERNS.get(cat, {}).get("severity", "MEDIUM"),
                    "snippets": [f"(NLP score {nlp_scores[cat]:.2f})"],
                }
                cat_sev = matches[cat]["severity"]
                if SEVERITY_ORDER.get(cat_sev, 0) > SEVERITY_ORDER.get(overall, 0):
                    overall = cat_sev

        categories = {cat: info["snippets"] for cat, info in matches.items()}

        # Anonymous flow: issue contact token
        raw_token, token_hash = (None, None)
        if s["anonymous"]:
            raw_token, token_hash = issue_contact_token()

        # The DB row's "username" reflects who the case is *about*.
        # For anonymous submissions we strip identity; for on-behalf-of we
        # record reporter_username separately.
        store_user = dict(self.user)
        reporter_username = None
        if s["anonymous"]:
            store_user = {"username": "(anonymous)", "full_name": "(anonymous)",
                          "role": self.user.get("role")}
        elif s["on_behalf_of"]:
            reporter_username = self.user.get("username")

        attachments_meta = [
            {"orig_name": os.path.basename(a.get("orig") or ""),
             "stored": a.get("stored")}
            for a in (s.get("attachments") or [])
        ]

        sid = save_submission(
            store_user, text, overall, categories,
            anonymous=s["anonymous"], contact_token_hash=token_hash,
            on_behalf_of=s["on_behalf_of"],
            reporter_username=reporter_username,
            subject_relation=s.get("subject_relation"),
            triage=s.get("triage"),
            attachments=attachments_meta,
            audio_path=s.get("audio_stored") or None,
            transcription=s.get("transcription") or None,
            language=self.lang,
            consent_disclosure=s["consent_disclosure"],
            consent_contact=s["consent_contact"],
            duplicate_of=dup_id,
            vulnerability_flags=s.get("vulnerability_flags"),
            case_location=s.get("case_location"),
            case_department=s.get("case_department"),
            nlp_score=nlp_overall_conf,
            nlp_categories=nlp_scores,
            whistleblowing=s.get("whistleblowing", False),
            wb_independent_reviewer=s.get("wb_independent_reviewer") or None,
        )
        logger.info("Safeguarding submission saved id=%s severity=%s anon=%s obo=%s dup_of=%s nlp=%.2f",
                    sid, overall, s["anonymous"], s["on_behalf_of"], dup_id,
                    nlp_overall_conf)

        # Feature 18 — cumulative-concern check fires a back-end note so
        # the staff dashboard can highlight the pattern.
        if not s["anonymous"]:
            subj_id = canonical_subject_id(self.user, anonymous=False)
            count, escalate = cumulative_concern(subj_id)
            if escalate:
                add_case_note(
                    sid, "system",
                    f"[cumulative] {count} concerns logged about this subject "
                    f"in the last {_CUMULATIVE_WINDOW_DAYS} days — review pattern.",
                )

        clear_draft(self.user.get("username") or "")

        if raw_token:
            messagebox.showwarning(
                tr("anon_token_heading", self.lang),
                tr("anon_token_body", self.lang, token=raw_token),
            )

        # Feature 13 — self-harm pathway
        if is_self_harm_case(matches, nlp_scores):
            messagebox.showwarning(
                "Immediate support",
                "Please know help is available right now.\n\n"
                + SUPPORT_RESOURCES,
            )
        elif overall == "CRITICAL":
            messagebox.showwarning(
                "We're here for you",
                "Thank you for reaching out. A member of the safeguarding "
                "team has been alerted.\n\n" + SUPPORT_RESOURCES,
            )
        elif overall in ("HIGH", "MEDIUM"):
            messagebox.showinfo("Submitted",
                                "Your submission has been flagged for review.\n\n"
                                + SUPPORT_RESOURCES)
        else:
            messagebox.showinfo("Submitted",
                                f"Thank you. Submission #{sid} received.")

        # Reset wizard
        self.show_student_dashboard()

    def _refresh_student_history(self):
        self.history_list.delete(0, "end")
        for sid, ts, sev, status in fetch_user_submissions(
                self.user.get("username") or ""):
            date = ts.split("T")[0]
            self.history_list.insert(
                "end", f"#{sid}  {date}   {sev:<8}  {status}")

    def _open_anon_check(self):
        win = tk.Toplevel(self._host)
        win.title(tr("check_anon", self.lang))
        win.configure(bg="#f4f6fa")
        tk.Label(win, text=tr("check_anon_prompt", self.lang),
                 bg="#f4f6fa").pack(padx=14, pady=(14, 4))
        entry = ttk.Entry(win, width=36)
        entry.pack(padx=14, pady=4)
        out = tk.Label(win, text="", bg="#f4f6fa", justify="left",
                       font=("Segoe UI", 9))
        out.pack(padx=14, pady=8)

        def do_lookup():
            row = lookup_by_contact_token(entry.get())
            if not row:
                out.config(text=tr("check_anon_not_found", self.lang), fg="#b00020")
                return
            sid, ts, sev, status, note = row
            msg = tr("check_anon_result", self.lang, sid=sid,
                     ts=ts.replace("T", " ")[:19], sev=sev, status=status)
            if note:
                msg += f"\n\nReviewer note:\n{note}"
            out.config(text=msg, fg="#1f3a5f")

        ttk.Button(win, text="Check", command=do_lookup).pack(pady=(0, 12))

    # ---------- staff dashboard ----------
    def show_staff_dashboard(self):
        self._clear()
        self.unbind("<Return>")
        oncall = get_oncall_dsl()
        oncall_label = (f"  •  On-call DSL: {oncall['full_name']} ({oncall['username']})"
                        if oncall else "  •  No on-call DSL configured")
        self._build_topbar(f"Staff console — {self.user['full_name']}{oncall_label}")

        # Recompute SLA breach flags on every dashboard mount
        refresh_sla_breach_flags()

        body = tk.Frame(self.container, bg="#f4f6fa")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        nb = ttk.Notebook(body)
        nb.pack(fill="both", expand=True)

        cases_tab = tk.Frame(nb, bg="#f4f6fa")
        dash_tab  = tk.Frame(nb, bg="#f4f6fa")
        nb.add(cases_tab, text="Cases")
        nb.add(dash_tab, text="Dashboard")

        self._build_cases_tab(cases_tab)
        self._build_dashboard_tab(dash_tab)

    def _build_cases_tab(self, host):
        # Filters
        filt = tk.Frame(host, bg="#f4f6fa")
        filt.pack(fill="x", pady=(8, 8))

        tk.Label(filt, text="Status:", bg="#f4f6fa").pack(side="left")
        self.status_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self.status_var,
                     values=["All", "Pending", "In progress", "Closed"],
                     state="readonly", width=12
                     ).pack(side="left", padx=(4, 12))

        tk.Label(filt, text="Severity:", bg="#f4f6fa").pack(side="left")
        self.sev_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self.sev_var,
                     values=["All", "CRITICAL", "HIGH",
                             "MEDIUM", "LOW", "NONE"],
                     state="readonly", width=12
                     ).pack(side="left", padx=(4, 12))

        tk.Label(filt, text="Lifecycle:", bg="#f4f6fa").pack(side="left")
        self.lifecycle_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self.lifecycle_var,
                     values=["All", *_LIFECYCLE_STATES],
                     state="readonly", width=12
                     ).pack(side="left", padx=(4, 12))

        ttk.Button(filt, text="Refresh",
                   command=self._refresh_staff_list).pack(side="left")

        split = tk.Frame(host, bg="#f4f6fa")
        split.pack(fill="both", expand=True)

        list_frame = tk.Frame(split, bg="#f4f6fa")
        list_frame.pack(side="left", fill="both", expand=True)

        columns = ("id", "student", "submitted", "severity",
                   "lifecycle", "risk", "sla")
        self.tree = ttk.Treeview(list_frame, columns=columns,
                                 show="headings", height=20)
        widths = (40, 160, 120, 80, 90, 50, 90)
        for col, w in zip(columns, widths):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        for sev, col in SEVERITY_COLOUR.items():
            self.tree.tag_configure(sev, background=col,
                                    foreground="white" if sev != "LOW" else "black")
        self.tree.tag_configure("BREACH",
                                background="#5b0011", foreground="white")

        self.tree.bind("<<TreeviewSelect>>", self._on_select_submission)

        # Detail panel — wider for tabs
        self.detail = tk.Frame(split, bg="white", bd=1, relief="solid",
                               width=520)
        self.detail.pack(side="right", fill="both", padx=(12, 0))
        self.detail.pack_propagate(False)
        self._render_empty_detail()

        self._refresh_staff_list()

    def _build_dashboard_tab(self, host):
        # Heatmap (department × severity over last 90 days)
        tk.Label(host, text="Incident heatmap — department × severity (90 days)",
                 bg="#f4f6fa", font=("Segoe UI", 11, "bold")
                 ).pack(anchor="w", padx=12, pady=(12, 4))

        heat_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        heat_frame.pack(fill="x", padx=12, pady=4)

        grid = incident_heatmap(days=90)
        sevs = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE")
        # Header row
        tk.Label(heat_frame, text="Department", bg="#1f3a5f", fg="white",
                 font=("Segoe UI", 9, "bold"), padx=6, pady=4
                 ).grid(row=0, column=0, sticky="we")
        for ci, sev in enumerate(sevs, start=1):
            tk.Label(heat_frame, text=sev, bg="#1f3a5f", fg="white",
                     font=("Segoe UI", 9, "bold"), padx=6, pady=4
                     ).grid(row=0, column=ci, sticky="we")
        if not grid:
            tk.Label(heat_frame, text="(no data yet)", bg="white",
                     fg="#888", padx=8, pady=6
                     ).grid(row=1, column=0, columnspan=len(sevs)+1)
        else:
            for ri, (dept, by_sev) in enumerate(sorted(grid.items()), start=1):
                tk.Label(heat_frame, text=dept, bg="white", anchor="w",
                         padx=6, pady=3).grid(row=ri, column=0, sticky="we")
                for ci, sev in enumerate(sevs, start=1):
                    n = by_sev.get(sev, 0)
                    bg = SEVERITY_COLOUR.get(sev, "#fff") if n else "#f5f5f5"
                    fg = ("white" if n and sev != "LOW" else "#333")
                    tk.Label(heat_frame, text=str(n or ""), bg=bg, fg=fg,
                             font=("Segoe UI", 9, "bold" if n else "normal"),
                             padx=6, pady=3
                             ).grid(row=ri, column=ci, sticky="we")

        # Risk trend (last 8 weeks)
        tk.Label(host, text="Risk trend — last 8 weeks",
                 bg="#f4f6fa", font=("Segoe UI", 11, "bold")
                 ).pack(anchor="w", padx=12, pady=(18, 4))

        trend = risk_trend(weeks=8)
        trend_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        trend_frame.pack(fill="x", padx=12, pady=4)
        tk.Label(trend_frame, text="Week", bg="#1f3a5f", fg="white",
                 font=("Segoe UI", 9, "bold"), padx=6, pady=4
                 ).grid(row=0, column=0, sticky="we")
        for ci, sev in enumerate(sevs, start=1):
            tk.Label(trend_frame, text=sev, bg="#1f3a5f", fg="white",
                     font=("Segoe UI", 9, "bold"), padx=6, pady=4
                     ).grid(row=0, column=ci, sticky="we")
        if not trend:
            tk.Label(trend_frame, text="(no data yet)", bg="white",
                     fg="#888", padx=8, pady=6
                     ).grid(row=1, column=0, columnspan=len(sevs)+1)
        else:
            for ri, (wk, by_sev) in enumerate(sorted(trend.items()), start=1):
                tk.Label(trend_frame, text=wk, bg="white", anchor="w",
                         padx=6, pady=3).grid(row=ri, column=0, sticky="we")
                for ci, sev in enumerate(sevs, start=1):
                    n = by_sev.get(sev, 0)
                    tk.Label(trend_frame, text=str(n or ""), bg="white",
                             padx=6, pady=3,
                             font=("Segoe UI", 9)).grid(row=ri, column=ci,
                                                        sticky="we")

        # Feature 27 — reviews due now or in next 7 days
        tk.Label(host, text="Reviews due (now or within 7 days)",
                 bg="#f4f6fa", font=("Segoe UI", 11, "bold")
                 ).pack(anchor="w", padx=12, pady=(18, 4))
        rev_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        rev_frame.pack(fill="x", padx=12, pady=4)
        rev_rows = due_reviews(within_days=7)
        if not rev_rows:
            tk.Label(rev_frame, text="(none due)", bg="white", fg="#888",
                     padx=8, pady=6).pack(anchor="w")
        else:
            for rid, fname, uname, rsev, due, lc, assigned in rev_rows[:12]:
                line = (f"#{rid}  {fname} ({uname})  —  {rsev}  —  "
                        f"due {due.replace('T', ' ')[:16]}  —  "
                        f"{lc or 'Open'}  →  {assigned or '(unassigned)'}")
                tk.Label(rev_frame, text=line, bg="white", anchor="w",
                         font=("Segoe UI", 9), padx=8, pady=2
                         ).pack(anchor="w", fill="x")

    def _refresh_staff_list(self):
        if not hasattr(self, "tree"):
            return
        refresh_sla_breach_flags()
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = fetch_submissions(
            self.status_var.get(), self.sev_var.get(),
            self.lifecycle_var.get(),
            include_whistleblowing=can_view_whistleblowing(self.user),
        )
        self._rows_cache = {r[0]: r for r in rows}
        # Pull risk/lifecycle/sla data in one shot
        ids = [r[0] for r in rows]
        meta = {}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn = _connect(); cur = conn.cursor()
            cur.execute(
                f"SELECT id, lifecycle_state, risk_score, sla_due_at, "
                f" sla_breached FROM safeguarding_submissions "
                f"WHERE id IN ({placeholders})",
                ids,
            )
            for sid, lc, risk, sla_due, breach in cur.fetchall():
                meta[sid] = (lc or "Open", risk or 0, sla_due, bool(breach))
            conn.close()
        for r in rows:
            sid, name, username, ts, sev, _cats, _status, *_ = r
            lc, risk, sla_due, breach = meta.get(sid, ("Open", 0, None, False))
            sla_disp = ""
            if sla_due:
                sla_disp = sla_due.replace("T", " ")[:16]
            tags = ("BREACH",) if breach else (sev,)
            self.tree.insert(
                "", "end", iid=str(sid),
                values=(sid, f"{name} ({username})",
                        ts.replace("T", " ")[:16], sev, lc,
                        risk, sla_disp),
                tags=tags,
            )

    def _render_empty_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        tk.Label(self.detail, text="Select a submission to review.",
                 bg="white", fg="#888",
                 font=("Segoe UI", 10)).pack(expand=True)

    def _on_select_submission(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        sid = int(sel[0])
        # Feature 36 — gate viewing on role permission and log every access.
        if not require(self.user, "view_case"):
            messagebox.showerror("Permission denied",
                                 "Your role cannot view safeguarding cases.")
            return
        audit_log(actor=self.user.get("username", "?"),
                  actor_role=self.user.get("role", "?"),
                  action="view_case", case_id=sid)
        row = self._rows_cache[sid]
        (sid, name, username, ts, sev, cats_json,
         status, content, reviewer, note, reviewed_at) = row
        # Feature 37 — decrypt content + transcription for display.
        decrypted_content, decrypted_trans = resolve_content(sid)
        if decrypted_content:
            content = decrypted_content

        for w in self.detail.winfo_children():
            w.destroy()

        # Fetch all the extended metadata for this submission
        extra = {}
        try:
            conn = _connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT anonymous, on_behalf_of, reporter_username, subject_relation, "
                "       attachments, audio_path, transcription, language, "
                "       consent_disclosure, consent_contact, duplicate_of, "
                "       likelihood, impact, risk_score, nlp_score, nlp_categories, "
                "       sla_due_at, sla_breached, assigned_to, assigned_at, "
                "       linked_subject_id, vulnerability_flags, lifecycle_state, "
                "       case_location, case_department, "
                "       outcome_code, closure_reason, "
                "       mandatory_reporting, mandatory_status, mandatory_reported_at, "
                "       whistleblowing, wb_independent_reviewer, "
                "       linked_wellbeing_appt, linked_conduct_case, "
                "       linked_halls_incident, health_referral_consent, "
                "       health_referral_sent_at, tutor_notified_at, "
                "       tutor_notification_redacted "
                "FROM safeguarding_submissions WHERE id=?", (sid,))
            r = cur.fetchone()
            conn.close()
            if r:
                keys = ("anonymous", "on_behalf_of", "reporter_username",
                        "subject_relation", "attachments_json", "audio_path",
                        "transcription", "language", "consent_disclosure",
                        "consent_contact", "duplicate_of",
                        "likelihood", "impact", "risk_score", "nlp_score",
                        "nlp_categories_json", "sla_due_at", "sla_breached",
                        "assigned_to", "assigned_at", "linked_subject_id",
                        "vulnerability_flags_json", "lifecycle_state",
                        "case_location", "case_department",
                        "outcome_code", "closure_reason",
                        "mandatory_reporting", "mandatory_status",
                        "mandatory_reported_at",
                        "whistleblowing", "wb_independent_reviewer",
                        "linked_wellbeing_appt", "linked_conduct_case",
                        "linked_halls_incident", "health_referral_consent",
                        "health_referral_sent_at", "tutor_notified_at",
                        "tutor_notification_redacted")
                extra = dict(zip(keys, r))
                # Decrypted transcription overrides the plaintext column for display.
                if decrypted_trans:
                    extra["transcription"] = decrypted_trans
        except Exception:
            logger.debug("Could not fetch extra metadata for #%s", sid, exc_info=True)

        # Header strip
        header = tk.Frame(self.detail, bg="white")
        header.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(header, text=f"Case #{sid}", bg="white",
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        badge = tk.Label(header, text=f" {sev} ",
                         bg=SEVERITY_COLOUR.get(sev, "#666"), fg="white",
                         font=("Segoe UI", 9, "bold"), padx=6, pady=1)
        badge.pack(side="left", padx=8)
        risk_score = extra.get("risk_score") or 0
        risk_bg = ("#b00020" if risk_score >= 16 else
                   "#d9480f" if risk_score >= 9 else
                   "#f38b00" if risk_score >= 4 else "#2e7d32")
        tk.Label(header,
                 text=f" Risk {risk_score} ({extra.get('likelihood') or 0}×{extra.get('impact') or 0}) ",
                 bg=risk_bg, fg="white", font=("Segoe UI", 9, "bold"),
                 padx=6, pady=1).pack(side="left")
        if extra.get("sla_breached"):
            tk.Label(header, text=" SLA BREACHED ", bg="#5b0011", fg="white",
                     font=("Segoe UI", 9, "bold"), padx=6, pady=1
                     ).pack(side="left", padx=4)
        if extra.get("mandatory_reporting"):
            mstatus = extra.get("mandatory_status") or "Pending"
            mcolor = "#5b0011" if mstatus == "Pending" else "#1f3a5f"
            tk.Label(header, text=f" MANDATORY: {mstatus} ", bg=mcolor,
                     fg="white", font=("Segoe UI", 9, "bold"),
                     padx=6, pady=1).pack(side="left", padx=4)
        if extra.get("whistleblowing"):
            tk.Label(header, text=" WHISTLEBLOWING ", bg="#4527a0",
                     fg="white", font=("Segoe UI", 9, "bold"),
                     padx=6, pady=1).pack(side="left", padx=4)

        # Lifecycle dropdown right under the header
        lc_row = tk.Frame(self.detail, bg="white")
        lc_row.pack(fill="x", padx=12, pady=(6, 4))
        tk.Label(lc_row, text="Lifecycle:", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        lc_var = tk.StringVar(value=extra.get("lifecycle_state") or "Open")
        lc_combo = ttk.Combobox(lc_row, textvariable=lc_var,
                                values=list(_LIFECYCLE_STATES),
                                state="readonly", width=14)
        lc_combo.pack(side="left", padx=6)

        def _on_lc_change(_e):
            set_lifecycle_state(sid, lc_var.get(),
                                actor=self.user.get("username") or "")
            self._refresh_staff_list()
        lc_combo.bind("<<ComboboxSelected>>", _on_lc_change)

        # Tabbed detail body
        nb = ttk.Notebook(self.detail)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        overview = tk.Frame(nb, bg="white"); nb.add(overview, text="Overview")
        notes_tab = tk.Frame(nb, bg="white"); nb.add(notes_tab, text="Notes")
        actions_tab = tk.Frame(nb, bg="white"); nb.add(actions_tab, text="Actions")
        referrals_tab = tk.Frame(nb, bg="white"); nb.add(referrals_tab, text="Referrals")
        integ_tab = tk.Frame(nb, bg="white"); nb.add(integ_tab, text="Integrations")
        linked_tab = tk.Frame(nb, bg="white"); nb.add(linked_tab, text="Linked")
        audit_tab = tk.Frame(nb, bg="white"); nb.add(audit_tab, text="Audit")

        self._render_overview_tab(overview, sid, name, username, ts, sev,
                                  cats_json, status, content, reviewer,
                                  note, reviewed_at, extra)
        self._render_notes_tab(notes_tab, sid)
        self._render_actions_tab(actions_tab, sid)
        self._render_referrals_tab(referrals_tab, sid)
        self._render_integrations_tab(integ_tab, sid, extra)
        self._render_linked_tab(linked_tab, sid, extra)
        self._render_audit_tab(audit_tab, sid, extra)

    def _render_overview_tab(self, host, sid, name, username, ts, sev,
                             cats_json, status, content, reviewer, note,
                             reviewed_at, extra):
        pad = dict(padx=12, pady=4)

        if extra.get("anonymous"):
            student_label = "(anonymous)"
        elif extra.get("on_behalf_of"):
            student_label = (f"{name} ({username})  "
                             f"— reported by {extra.get('reporter_username') or '?'}"
                             f" ({extra.get('subject_relation') or 'relation unspecified'})")
        else:
            student_label = f"{name} ({username})"

        meta = (f"Student: {student_label}\n"
                f"Submitted: {ts.replace('T', ' ')[:19]}\n"
                f"Status: {status}")
        if extra.get("language"):
            meta += f"\nLanguage: {_LANG_NAMES.get(extra['language'], extra['language'])}"
        if extra.get("case_location") or extra.get("case_department"):
            meta += (f"\nLocation: {extra.get('case_location') or '?'}"
                     f"  |  Department: {extra.get('case_department') or '?'}")
        if extra.get("assigned_to"):
            meta += f"\nAssigned to: {extra['assigned_to']}"
        if extra.get("sla_due_at"):
            meta += f"\nSLA due: {extra['sla_due_at'].replace('T', ' ')[:19]}"
        if extra.get("duplicate_of"):
            meta += f"\n⚠ Possible duplicate of #{extra['duplicate_of']}"
        if reviewer:
            meta += f"\nLast reviewed by: {reviewer} at {reviewed_at[:19]}"
        tk.Label(host, text=meta, bg="white", justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", **pad)

        # Vulnerability flag chips
        try:
            vflags = json.loads(extra.get("vulnerability_flags_json") or "null") or []
        except (TypeError, ValueError):
            vflags = []
        if vflags:
            chip_row = tk.Frame(host, bg="white")
            chip_row.pack(anchor="w", padx=12, pady=(0, 4))
            tk.Label(chip_row, text="Vulnerability:", bg="white",
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            for f in vflags:
                tk.Label(chip_row, text=f" {f} ", bg="#fff3e0",
                         fg="#b71c1c", font=("Segoe UI", 8, "bold"),
                         padx=4, pady=1, bd=1, relief="solid"
                         ).pack(side="left", padx=2)

        # Attachments + audio + transcription block
        try:
            atts = json.loads(extra.get("attachments_json") or "null") or []
        except (TypeError, ValueError):
            atts = []
        if atts or extra.get("audio_path") or extra.get("transcription"):
            tk.Label(host, text="Attachments:", bg="white",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
            for a in atts:
                row = tk.Frame(host, bg="white")
                row.pack(anchor="w", padx=24, pady=1)
                tk.Label(row, text="📎 " + (a.get("orig_name") or "(file)"),
                         bg="white", font=("Segoe UI", 9)).pack(side="left")
                if a.get("stored"):
                    ttk.Button(
                        row, text="Open",
                        command=lambda s=a["stored"]: self._open_attachment(s),
                    ).pack(side="left", padx=4)
            if extra.get("audio_path"):
                row = tk.Frame(host, bg="white")
                row.pack(anchor="w", padx=24, pady=1)
                tk.Label(row, text="🎙 audio note", bg="white",
                         font=("Segoe UI", 9)).pack(side="left")
                ttk.Button(
                    row, text="Open",
                    command=lambda s=extra["audio_path"]: self._open_attachment(s),
                ).pack(side="left", padx=4)
            if extra.get("transcription"):
                tk.Label(host, text="Transcript:", bg="white",
                         font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
                tk.Label(host, text=extra["transcription"],
                         bg="white", wraplength=460, justify="left",
                         font=("Segoe UI", 9, "italic"), fg="#444"
                         ).pack(anchor="w", padx=24)

        # Flagged categories — regex + NLP merged for display.
        try:
            cats = json.loads(cats_json) if cats_json else {}
        except (TypeError, ValueError):
            cats = {}
        if isinstance(cats, list):
            cats = {str(c): [] for c in cats}
        elif not isinstance(cats, dict):
            cats = {}
        try:
            nlp_cats = json.loads(extra.get("nlp_categories_json") or "null") or {}
        except (TypeError, ValueError):
            nlp_cats = {}
        if cats or nlp_cats:
            tk.Label(host, text="Flagged categories:",
                     bg="white", font=("Segoe UI", 9, "bold")
                     ).pack(anchor="w", **pad)
            for cat, snippets in cats.items():
                line = f"• {cat}"
                if cat in nlp_cats:
                    line += f"   (NLP {nlp_cats[cat]:.2f})"
                tk.Label(host, text=line, bg="white", font=("Segoe UI", 9),
                         fg="#b00020").pack(anchor="w", padx=24)
                if not isinstance(snippets, (list, tuple)):
                    snippets = []
                for snip in snippets[:3]:
                    tk.Label(host, text=f"   “{snip}”",
                             bg="white", font=("Segoe UI", 8),
                             fg="#555", wraplength=460, justify="left"
                             ).pack(anchor="w", padx=24)
            for cat, score in nlp_cats.items():
                if cat in cats:
                    continue
                tk.Label(host, text=f"• {cat}   (NLP {score:.2f})",
                         bg="white", font=("Segoe UI", 9),
                         fg="#d9480f").pack(anchor="w", padx=24)
        else:
            tk.Label(host, text="No automated flags.",
                     bg="white", fg="#2e7d32",
                     font=("Segoe UI", 9)).pack(anchor="w", **pad)

        # Original content
        tk.Label(host, text="Content:", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        content_box = scrolledtext.ScrolledText(
            host, wrap="word", height=6,
            font=("Segoe UI", 9), bg="#fafafa")
        content_box.insert("1.0", content)
        content_box.config(state="disabled")
        content_box.pack(fill="x", padx=12, pady=4)

        # Review note + status buttons
        tk.Label(host, text="Review note:", bg="white",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        note_box = tk.Text(host, height=3, font=("Segoe UI", 9))
        if note:
            note_box.insert("1.0", note)
        note_box.pack(fill="x", padx=12)

        actions = tk.Frame(host, bg="white")
        actions.pack(fill="x", padx=12, pady=10)

        def set_status(new_status):
            update_submission_status(
                sid, new_status, self.user["full_name"],
                note_box.get("1.0", "end").strip(),
            )
            audit_log(actor=self.user.get("username", "?"),
                      actor_role=self.user.get("role"),
                      action="status_change", case_id=sid,
                      details=f"-> {new_status}")
            notify_reporter_on_status_change(
                sid, new_status, actor=self.user.get("username", "?"))
            logger.info("Safeguarding submission %s status->%s by %s",
                        sid, new_status, self.user.get('username'))
            messagebox.showinfo("Updated",
                                f"Submission #{sid} marked as '{new_status}'.")
            self._refresh_staff_list()
            self._render_empty_detail()

        ttk.Button(actions, text="Mark In progress",
                   command=lambda: set_status("In progress")
                   ).pack(side="left", padx=2)
        ttk.Button(actions, text="Close case…",
                   command=lambda: self._open_close_dialog(sid)
                   ).pack(side="left", padx=2)
        ttk.Button(actions, text="Escalate (DSL)",
                   command=lambda: self._escalate_to_dsl(sid, note_box)
                   ).pack(side="left", padx=2)

        # Feature 26 / 27 / 30 — extra tooling row.
        more = tk.Frame(host, bg="white")
        more.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(more, text="Apply support template…",
                   command=lambda: self._open_template_dialog(sid)
                   ).pack(side="left", padx=2)
        ttk.Button(more, text="Schedule review…",
                   command=lambda: self._open_review_dialog(sid)
                   ).pack(side="left", padx=2)
        ttk.Button(more, text="Merge…",
                   command=lambda: self._open_merge_dialog(sid)
                   ).pack(side="left", padx=2)
        ttk.Button(more, text="Split…",
                   command=lambda: self._open_split_dialog(sid)
                   ).pack(side="left", padx=2)

        # Feature 28 — show closure context if already closed.
        if extra.get("outcome_code"):
            tk.Label(host,
                     text=f"Outcome: {extra['outcome_code']}  —  "
                          f"{(extra.get('closure_reason') or '')[:120]}",
                     bg="white", fg="#1f3a5f",
                     font=("Segoe UI", 9, "italic")
                     ).pack(anchor="w", padx=12, pady=(4, 0))

    def _escalate_to_dsl(self, sid, note_box):
        oncall = get_oncall_dsl()
        if oncall:
            assign_case(sid, oncall["username"],
                        assigned_by=self.user.get("username") or "?",
                        note="Escalated to on-call DSL")
        update_submission_status(
            sid, "In progress", self.user["full_name"],
            (note_box.get("1.0", "end").strip() + "\n[ESCALATED]").strip(),
        )
        set_lifecycle_state(sid, "Action", actor=self.user.get("username") or "")
        logger.warning("Safeguarding submission %s ESCALATED by %s -> %s",
                       sid, self.user.get('username'),
                       (oncall or {}).get("username", "(no on-call)"))
        msg = "Case escalated to senior safeguarding lead."
        if oncall:
            msg += f"\nAssigned to on-call DSL: {oncall['full_name']} ({oncall['username']})."
        else:
            msg += "\n⚠ No on-call DSL configured — please assign manually."
        messagebox.showwarning("Escalated",
                               msg + "\n\n" + SELF_HARM_ESCALATION)
        self._refresh_staff_list()
        self._render_empty_detail()

    # ---- Feature 26/27/28/30 dialogs ----------------------------------

    def _open_close_dialog(self, sid):
        if not require(self.user, "close"):
            messagebox.showerror("Permission denied",
                                 "Your role cannot close cases.")
            return
        win = tk.Toplevel(self._host)
        win.title(f"Close case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Outcome code:", bg="#f4f6fa"
                 ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        code_var = tk.StringVar(value=OUTCOME_CODES[0][0])
        opts = [f"{c} — {d}" for c, d in OUTCOME_CODES]
        combo = ttk.Combobox(win, values=opts, state="readonly", width=46)
        combo.current(0)
        combo.grid(row=0, column=1, padx=12, pady=(12, 4))
        tk.Label(win, text="Reason / detail:", bg="#f4f6fa"
                 ).grid(row=1, column=0, sticky="nw", padx=12, pady=4)
        reason = tk.Text(win, width=46, height=5, font=("Segoe UI", 9))
        reason.grid(row=1, column=1, padx=12, pady=4)

        def _do():
            code = OUTCOME_CODES[combo.current()][0]
            close_case(sid, code, reason.get("1.0", "end").strip(),
                       actor=self.user.get("username", "?"))
            notify_reporter_on_status_change(
                sid, "Closed", actor=self.user.get("username", "?"))
            messagebox.showinfo("Closed",
                                f"Case #{sid} closed with outcome '{code}'.")
            win.destroy()
            self._refresh_staff_list()
            self._render_empty_detail()
        ttk.Button(win, text="Close case", command=_do
                   ).grid(row=2, column=1, sticky="e", padx=12, pady=(0, 12))

    def _open_template_dialog(self, sid):
        win = tk.Toplevel(self._host)
        win.title(f"Apply support template — case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Category template:", bg="#f4f6fa"
                 ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        cats = list(SUPPORT_PLAN_TEMPLATES.keys())
        combo = ttk.Combobox(win, values=cats, state="readonly", width=34)
        combo.current(0)
        combo.grid(row=0, column=1, padx=12, pady=(12, 4))
        tk.Label(win, text="Default owner (username):", bg="#f4f6fa"
                 ).grid(row=1, column=0, sticky="w", padx=12, pady=4)
        owner = ttk.Entry(win, width=20)
        owner.grid(row=1, column=1, padx=12, pady=4, sticky="w")

        def _apply():
            cat = combo.get()
            n = apply_support_plan_template(
                sid, cat, owner=owner.get().strip() or None,
                actor=self.user.get("username", "?"))
            messagebox.showinfo("Template applied",
                                f"Added {n} action items from '{cat}'.")
            win.destroy()
            self._render_empty_detail()
            self._refresh_staff_list()
        ttk.Button(win, text="Apply", command=_apply
                   ).grid(row=2, column=1, sticky="e", padx=12, pady=(8, 12))

    def _open_review_dialog(self, sid):
        win = tk.Toplevel(self._host)
        win.title(f"Schedule review — case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Days until next review:", bg="#f4f6fa"
                 ).grid(row=0, column=0, sticky="w", padx=12, pady=12)
        days_var = tk.StringVar(value="14")
        ttk.Entry(win, textvariable=days_var, width=8
                  ).grid(row=0, column=1, padx=12, pady=12, sticky="w")

        def _go():
            try:
                d = int(days_var.get())
            except ValueError:
                messagebox.showerror("Invalid", "Enter a whole number of days.")
                return
            schedule_review(sid, d, actor=self.user.get("username", "?"))
            messagebox.showinfo("Scheduled",
                                f"Next review in {d} days.")
            win.destroy()
            self._render_empty_detail()
        ttk.Button(win, text="Schedule", command=_go
                   ).grid(row=1, column=1, sticky="e", padx=12, pady=(0, 12))

    def _open_merge_dialog(self, sid):
        if not require(self.user, "merge_split"):
            messagebox.showerror("Permission denied",
                                 "Your role cannot merge cases.")
            return
        win = tk.Toplevel(self._host)
        win.title(f"Merge cases into #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win,
                 text=f"Comma-separated case ids to merge INTO #{sid}:",
                 bg="#f4f6fa").pack(padx=12, pady=(12, 4))
        entry = ttk.Entry(win, width=36)
        entry.pack(padx=12)

        def _go():
            try:
                ids = [int(p.strip()) for p in entry.get().split(",")
                       if p.strip()]
            except ValueError:
                messagebox.showerror("Invalid", "Numeric ids only.")
                return
            n = merge_cases(sid, ids, actor=self.user.get("username", "?"))
            messagebox.showinfo("Merged",
                                f"{n} case(s) merged into #{sid}.")
            win.destroy()
            self._refresh_staff_list()
            self._render_empty_detail()
        ttk.Button(win, text="Merge", command=_go).pack(pady=10)

    def _open_split_dialog(self, sid):
        if not require(self.user, "merge_split"):
            messagebox.showerror("Permission denied",
                                 "Your role cannot split cases.")
            return
        win = tk.Toplevel(self._host)
        win.title(f"Split case #{sid}")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Extract text that should become a separate case:",
                 bg="#f4f6fa").pack(padx=12, pady=(12, 4))
        box = scrolledtext.ScrolledText(win, wrap="word", height=8, width=60,
                                        font=("Segoe UI", 9))
        box.pack(padx=12)

        def _go():
            text = box.get("1.0", "end").strip()
            if not text:
                messagebox.showinfo("Empty", "Please paste extract text.")
                return
            nid = split_case(sid, text, actor=self.user.get("username", "?"))
            messagebox.showinfo("Split",
                                f"Created case #{nid} from #{sid}.")
            win.destroy()
            self._refresh_staff_list()
            self._render_empty_detail()
        ttk.Button(win, text="Create split case", command=_go
                   ).pack(pady=10)

    # ---- Feature 35/29/40 tools menu ---------------------------------
    def _open_tools_menu(self):
        win = tk.Toplevel(self._host)
        win.title("Safeguarding tools")
        win.configure(bg="#f4f6fa")
        tk.Label(win, text="Privacy / reporting tools", bg="#f4f6fa",
                 font=("Segoe UI", 11, "bold")
                 ).pack(padx=14, pady=(12, 6))

        def _bulk_export():
            if not require(self.user, "export"):
                messagebox.showerror("Permission denied",
                                     "Your role cannot export cases.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"safeguarding_export_{datetime.now():%Y%m%d}.csv",
            )
            if not path:
                return
            _, n = export_cases_csv(path,
                                    actor=self.user.get("username", "?"))
            messagebox.showinfo("Export",
                                f"Wrote {n} rows to {path}.")

        def _sar_export():
            if not require(self.user, "export"):
                messagebox.showerror("Permission denied",
                                     "Your role cannot export SAR bundles.")
                return
            who = self._prompt("SAR — subject username", "Enter username:")
            if not who:
                return
            out_dir = filedialog.askdirectory(title="Choose output folder")
            if not out_dir:
                return
            path, n = generate_sar_bundle(
                who, out_dir, actor=self.user.get("username", "?"))
            messagebox.showinfo("SAR bundle",
                                f"Wrote {n} case(s) to {path}.")

        def _audit_log():
            self._show_audit_log()

        def _purge():
            if not require(self.user, "*"):
                # Only admin-tier roles (which have * via _ROLE_PERMISSIONS).
                if not can(self.user, "export"):
                    messagebox.showerror("Permission denied",
                                         "Only admins may run retention purge.")
                    return
            n, ids = purge_due_records(
                actor=self.user.get("username", "?"), dry_run=True)
            if not n:
                messagebox.showinfo("Retention",
                                    "No records past retention horizon.")
                return
            if messagebox.askyesno("Retention purge",
                                   f"{n} case(s) past retention. Purge now?"):
                purge_due_records(actor=self.user.get("username", "?"))
                messagebox.showinfo("Retention",
                                    f"Purged {n} case(s).")

        def _sla_alerts():
            n = stuck_case_alerts(actor=self.user.get("username", "?"))
            messagebox.showinfo("SLA alerts",
                                f"Queued {n} SLA-breach notification(s).")

        def _digest():
            body = daily_dsl_digest(actor=self.user.get("username", "?"))
            messagebox.showinfo("Daily digest", body)

        def _mandatory_panel():
            self._show_mandatory_panel()

        def _wb_panel():
            if not can_view_whistleblowing(self.user):
                messagebox.showerror("Permission denied",
                                     "Only independent reviewers can open the "
                                     "whistleblowing channel.")
                return
            self._show_wb_panel()

        def _webhooks():
            self._show_webhook_panel()

        def _leadership():
            self._show_leadership_stats()

        def _training():
            self._show_training_panel()

        for label, cmd in (
            ("Bulk CSV export (statutory)…", _bulk_export),
            ("Subject Access Request bundle…", _sar_export),
            ("View audit log", _audit_log),
            ("Run retention purge", _purge),
            ("Queue SLA-breach alerts now", _sla_alerts),
            ("Send daily DSL digest now", _digest),
            ("Mandatory-reporting queue", _mandatory_panel),
            ("Whistleblowing channel (independent)", _wb_panel),
            ("Webhook endpoints (SIEM)…", _webhooks),
            ("Leadership stats (anonymised)", _leadership),
            ("Training tracker", _training),
        ):
            ttk.Button(win, text=label, command=cmd, width=34
                       ).pack(padx=14, pady=4)
        ttk.Button(win, text="Close", command=win.destroy
                   ).pack(padx=14, pady=(8, 12))

    def _prompt(self, title, prompt):
        from tkinter import simpledialog
        return simpledialog.askstring(title, prompt, parent=self._host)

    def _show_mandatory_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Mandatory-reporting queue")
        win.configure(bg="#f4f6fa")
        cols = ("id", "student", "severity", "status", "reported_at")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 220, 90, 100, 160)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in list_mandatory_cases():
            sid, fname, uname, sev, mstatus, rep_at = r
            tree.insert("", "end", iid=str(sid),
                        values=(sid, f"{fname} ({uname})", sev,
                                mstatus or "Pending",
                                (rep_at or "")[:19]))

        def _ack():
            sel = tree.selection()
            if not sel:
                return
            self._ack_mandatory(int(sel[0]))
            win.destroy()
        ttk.Button(win, text="Mark selected as Reported…",
                   command=_ack).pack(pady=(0, 8))

    def _show_wb_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Whistleblowing channel — independent reviewers only")
        win.configure(bg="#f4f6fa")
        cols = ("id", "student", "submitted", "severity", "status", "reviewer")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 200, 130, 90, 100, 140)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in list_whistleblowing_cases(self.user):
            sid, fname, uname, ts, sev, status, reviewer = r
            tree.insert("", "end", iid=str(sid),
                        values=(sid, f"{fname} ({uname})",
                                ts.replace("T", " ")[:16], sev, status,
                                reviewer or "(unassigned)"))

    def _show_webhook_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Webhook endpoints")
        win.configure(bg="#f4f6fa")
        cols = ("id", "url", "filter", "active", "last_status", "last_sent")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (40, 280, 120, 60, 90, 140)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=8, pady=8)

        def _reload():
            for it in tree.get_children():
                tree.delete(it)
            for wid, url, evf, active, _created, ls, lst in list_webhooks():
                tree.insert("", "end", iid=str(wid),
                            values=(wid, url, evf or "*",
                                    "Yes" if active else "No",
                                    ls or "—", (lst or "")[:19]))
        _reload()

        form = tk.Frame(win, bg="#f4f6fa")
        form.pack(fill="x", padx=8, pady=8)
        tk.Label(form, text="URL:", bg="#f4f6fa"
                 ).grid(row=0, column=0, sticky="w")
        u_e = ttk.Entry(form, width=40); u_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Secret:", bg="#f4f6fa"
                 ).grid(row=0, column=2, sticky="w")
        s_e = ttk.Entry(form, width=20); s_e.grid(row=0, column=3, padx=4)
        tk.Label(form, text="Events (comma or *):",
                 bg="#f4f6fa").grid(row=1, column=0, sticky="w", pady=4)
        f_e = ttk.Entry(form, width=30); f_e.insert(0, "*")
        f_e.grid(row=1, column=1, sticky="w", padx=4)

        def _add():
            if not require(self.user, "*"):
                messagebox.showerror("Permission denied",
                                     "Admins only.")
                return
            url = u_e.get().strip(); sec = s_e.get().strip()
            if not url or not sec:
                messagebox.showerror("Invalid",
                                     "URL and secret are required.")
                return
            register_webhook(url, sec, f_e.get().strip() or "*",
                             actor=self.user.get("username", "?"))
            u_e.delete(0, "end"); s_e.delete(0, "end")
            _reload()

        def _disable():
            sel = tree.selection()
            if not sel:
                return
            if not require(self.user, "*"):
                return
            disable_webhook(int(sel[0]),
                            actor=self.user.get("username", "?"))
            _reload()

        ttk.Button(form, text="Add webhook", command=_add
                   ).grid(row=1, column=3, padx=4)
        ttk.Button(form, text="Disable selected", command=_disable
                   ).grid(row=1, column=4, padx=4)

    def _show_leadership_stats(self):
        win = tk.Toplevel(self._host)
        win.title("Leadership stats (90 days, anonymised)")
        win.configure(bg="#f4f6fa")
        stats = leadership_stats(days=90)
        body = (f"Period: last {stats['period_days']} days\n"
                f"Total cases: {stats['total']}\n"
                f"SLA breaches: {stats['sla_breaches']}\n"
                f"Mandatory-reporting flags: {stats['mandatory_flags']}\n"
                f"Avg days to close: {stats['avg_days_to_close']}\n\n"
                f"By severity: {stats['by_severity']}\n"
                f"By lifecycle: {stats['by_lifecycle']}\n"
                f"By outcome: {stats['by_outcome']}\n")
        tk.Label(win, text=body, bg="#f4f6fa", justify="left",
                 font=("Segoe UI", 10), padx=14, pady=14).pack()

    def _show_training_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Safeguarding training tracker")
        win.configure(bg="#f4f6fa")
        summary = training_compliance_summary()
        tk.Label(win,
                 text=(f"Staff tracked: {summary['users_tracked']}  •  "
                       f"Current: {summary['current']} ({summary['current_pct']}%)  •  "
                       f"Expiring soon: {summary['expiring_soon']}  •  "
                       f"Expired: {summary['expired']}"),
                 bg="#f4f6fa", font=("Segoe UI", 10, "bold"), padx=14, pady=10
                 ).pack()

        # Per-user lookup
        row = tk.Frame(win, bg="#f4f6fa"); row.pack(fill="x", padx=14)
        tk.Label(row, text="Lookup username:", bg="#f4f6fa"
                 ).pack(side="left")
        u = ttk.Entry(row, width=18); u.pack(side="left", padx=4)
        out = tk.Label(win, text="", bg="#f4f6fa", justify="left",
                       font=("Segoe UI", 9))
        out.pack(padx=14, pady=4, anchor="w")

        def _go():
            st = training_status(u.get().strip())
            out.config(text=str(st) if st else "(no records on file)")
        ttk.Button(row, text="Check", command=_go).pack(side="left")

        # Record completion
        form = tk.Frame(win, bg="#f4f6fa"); form.pack(fill="x", padx=14,
                                                     pady=(12, 14))
        tk.Label(form, text="Record completion — username:",
                 bg="#f4f6fa").grid(row=0, column=0, sticky="w")
        ru = ttk.Entry(form, width=16); ru.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Module:", bg="#f4f6fa"
                 ).grid(row=0, column=2, sticky="w")
        rm = ttk.Combobox(form, width=24, values=[
            "KCSIE basics", "Prevent duty", "Online safety",
            "Trauma-informed practice", "GDPR refresher",
        ])
        rm.grid(row=0, column=3, padx=4)

        def _record():
            if not (ru.get().strip() and rm.get().strip()):
                return
            record_training(ru.get().strip(), ru.get().strip(),
                            rm.get().strip(),
                            actor=self.user.get("username", "?"))
            messagebox.showinfo("Recorded",
                                f"Training recorded for {ru.get().strip()}.")
            win.destroy()
        ttk.Button(form, text="Record", command=_record
                   ).grid(row=0, column=4, padx=6)

    def _show_audit_log(self):
        win = tk.Toplevel(self._host)
        win.title("Safeguarding audit log")
        win.configure(bg="#f4f6fa")
        cols = ("ts", "actor", "role", "action", "case", "details")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=20)
        for c, w in zip(cols, (140, 110, 90, 130, 60, 320)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for _id, ts, actor, role, action, cid, details in list_audit_log(
                limit=500):
            tree.insert("", "end", values=(
                ts.replace("T", " ")[:19], actor, role or "", action,
                cid if cid is not None else "", details or ""))

    # ---- new tab renderers ----
    def _render_notes_tab(self, host, sid):
        tk.Label(host, text="Confidential case notes (append-only)",
                 bg="white", font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 6))
        lst = scrolledtext.ScrolledText(host, wrap="word", height=12,
                                        font=("Segoe UI", 9), bg="#fafafa")
        for author, note, ts in list_case_notes(sid):
            lst.insert("end",
                       f"[{ts.replace('T', ' ')[:19]}] {author}\n{note}\n\n")
        lst.config(state="disabled")
        lst.pack(fill="both", expand=True, padx=12)

        row = tk.Frame(host, bg="white")
        row.pack(fill="x", padx=12, pady=8)
        entry = tk.Text(row, height=3, font=("Segoe UI", 9))
        entry.pack(side="left", fill="x", expand=True)

        def _add():
            txt = entry.get("1.0", "end").strip()
            if not txt:
                return
            add_case_note(sid, self.user.get("username") or "?", txt)
            entry.delete("1.0", "end")
            # Re-render the tab
            for w in host.winfo_children():
                w.destroy()
            self._render_notes_tab(host, sid)
        ttk.Button(row, text="Append", command=_add).pack(side="right", padx=4)

    def _render_actions_tab(self, host, sid):
        tk.Label(host, text="Action plan", bg="white",
                 font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 6))
        cols = ("id", "title", "owner", "due", "status")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (40, 200, 100, 100, 80)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=12)
        for item in list_action_items(sid):
            iid, title, owner, due, status, _completed = item
            tree.insert("", "end", iid=str(iid),
                        values=(iid, title, owner or "", due or "", status))

        form = tk.Frame(host, bg="white")
        form.pack(fill="x", padx=12, pady=8)
        tk.Label(form, text="Title:", bg="white").grid(row=0, column=0,
                                                       sticky="w")
        t_e = ttk.Entry(form, width=32); t_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Owner:", bg="white").grid(row=0, column=2,
                                                       sticky="w")
        o_e = ttk.Entry(form, width=14); o_e.grid(row=0, column=3, padx=4)
        tk.Label(form, text="Due (YYYY-MM-DD):", bg="white"
                 ).grid(row=1, column=0, sticky="w", pady=4)
        d_e = ttk.Entry(form, width=14); d_e.grid(row=1, column=1,
                                                  sticky="w", padx=4)

        def _add():
            title = t_e.get().strip()
            if not title:
                return
            add_action_item(sid, title, o_e.get().strip(), d_e.get().strip())
            for w in host.winfo_children():
                w.destroy()
            self._render_actions_tab(host, sid)

        def _complete():
            sel = tree.selection()
            if not sel:
                return
            complete_action_item(int(sel[0]))
            for w in host.winfo_children():
                w.destroy()
            self._render_actions_tab(host, sid)

        ttk.Button(form, text="Add", command=_add
                   ).grid(row=1, column=3, padx=4)
        ttk.Button(form, text="Mark complete", command=_complete
                   ).grid(row=1, column=4, padx=4)

    def _render_referrals_tab(self, host, sid):
        tk.Label(host, text="External referrals (Police, LA, Social Care…)",
                 bg="white", font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 6))
        cols = ("agency", "contact", "ref", "sent", "status")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (140, 130, 90, 130, 70)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=12)
        for ref in list_referrals(sid):
            _iid, agency, contact, refno, sent_at, status, _note = ref
            tree.insert("", "end",
                        values=(agency, contact or "", refno or "",
                                sent_at.replace("T", " ")[:16], status))

        form = tk.Frame(host, bg="white")
        form.pack(fill="x", padx=12, pady=8)
        tk.Label(form, text="Agency:", bg="white").grid(row=0, column=0,
                                                        sticky="w")
        a_e = ttk.Combobox(form, width=18, values=[
            "Police", "Local Authority", "Children's Social Care",
            "Adult Social Care", "NHS", "Charity / NGO", "Other",
        ])
        a_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Contact:", bg="white").grid(row=0, column=2,
                                                         sticky="w")
        c_e = ttk.Entry(form, width=16); c_e.grid(row=0, column=3, padx=4)
        tk.Label(form, text="Ref #:", bg="white").grid(row=1, column=0,
                                                       sticky="w", pady=4)
        r_e = ttk.Entry(form, width=14); r_e.grid(row=1, column=1,
                                                  sticky="w", padx=4)
        tk.Label(form, text="Note:", bg="white").grid(row=1, column=2,
                                                      sticky="w", pady=4)
        n_e = ttk.Entry(form, width=20); n_e.grid(row=1, column=3, padx=4)

        def _add():
            agency = a_e.get().strip()
            if not agency:
                return
            add_referral(sid, agency, c_e.get().strip(),
                         r_e.get().strip(), n_e.get().strip())
            for w in host.winfo_children():
                w.destroy()
            self._render_referrals_tab(host, sid)
        ttk.Button(form, text="Log referral", command=_add
                   ).grid(row=1, column=4, padx=6)

    def _render_integrations_tab(self, host, sid, extra):
        pad = dict(padx=12, pady=4)
        tk.Label(host, text="Cross-system links & external notifications",
                 bg="white", font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 6))

        # Mandatory-reporting status + acknowledge
        if extra.get("mandatory_reporting"):
            mrow = tk.Frame(host, bg="#fff3e0", bd=1, relief="solid")
            mrow.pack(fill="x", padx=12, pady=4)
            tk.Label(mrow,
                     text=f"Mandatory reporting: {extra.get('mandatory_status') or 'Pending'}"
                          + (f"  (reported {extra.get('mandatory_reported_at','')[:19]})"
                             if extra.get("mandatory_reported_at") else ""),
                     bg="#fff3e0", fg="#5b0011",
                     font=("Segoe UI", 9, "bold"), padx=8, pady=4
                     ).pack(side="left")
            if (extra.get("mandatory_status") or "Pending") == "Pending":
                ttk.Button(mrow, text="Acknowledge / mark reported…",
                           command=lambda: self._ack_mandatory(sid)
                           ).pack(side="right", padx=6)

        # Whistleblowing reviewer assignment notice
        if extra.get("whistleblowing"):
            tk.Label(host,
                     text=f"Whistleblowing — independent reviewer: "
                          f"{extra.get('wb_independent_reviewer') or '(unassigned)'}",
                     bg="white", fg="#4527a0",
                     font=("Segoe UI", 9, "bold")
                     ).pack(anchor="w", **pad)

        # Live link summary
        def _link_line(label, value, button_label=None, button_cmd=None):
            row = tk.Frame(host, bg="white")
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=label + ":", bg="white", width=24,
                     anchor="w", font=("Segoe UI", 9, "bold")
                     ).pack(side="left")
            tk.Label(row, text=value or "—", bg="white",
                     font=("Segoe UI", 9)).pack(side="left")
            if button_label:
                ttk.Button(row, text=button_label,
                           command=button_cmd).pack(side="right")

        _link_line("Wellbeing appointment",
                   extra.get("linked_wellbeing_appt"),
                   "Book…", lambda: self._book_wellbeing(sid))
        _link_line("Conduct case",
                   extra.get("linked_conduct_case"),
                   "Link…", lambda: self._link_conduct(sid))
        _link_line("Halls incident",
                   extra.get("linked_halls_incident"),
                   "Link…", lambda: self._link_halls(sid))
        _link_line("Health Centre referral",
                   (extra.get("health_referral_sent_at") or "—")[:19],
                   "Refer (consent)…", lambda: self._health_referral(sid))
        _link_line("Tutor notified",
                   (extra.get("tutor_notified_at") or "—")[:19],
                   "Notify tutor…", lambda: self._notify_tutor(sid))
        if extra.get("tutor_notification_redacted"):
            tk.Label(host, text="Last sent to tutor (redacted):",
                     bg="white", font=("Segoe UI", 9, "bold")
                     ).pack(anchor="w", **pad)
            tk.Label(host, text=extra["tutor_notification_redacted"][:400],
                     bg="white", wraplength=460, justify="left",
                     fg="#555", font=("Segoe UI", 9, "italic")
                     ).pack(anchor="w", padx=24)

    def _ack_mandatory(self, sid):
        ref = self._prompt("Mandatory report",
                           "External reference (LADO / Prevent / Police):") or ""
        acknowledge_mandatory_report(sid, actor=self.user.get("username", "?"),
                                     external_reference=ref)
        messagebox.showinfo("Mandatory report",
                            f"Case #{sid} marked as reported.")
        self._refresh_staff_list()
        self._render_empty_detail()

    def _book_wellbeing(self, sid):
        when = self._prompt("Wellbeing booking",
                            "Appointment datetime ISO (e.g. 2026-05-22T14:00):")
        if not when:
            return
        ref = create_wellbeing_appointment(
            sid, when, actor=self.user.get("username", "?"))
        messagebox.showinfo("Booked", f"Wellbeing appointment ref: {ref}")
        self._render_empty_detail()

    def _link_conduct(self, sid):
        ref = self._prompt("Conduct link", "Conduct case reference:")
        if not ref:
            return
        link_conduct_case(sid, ref, actor=self.user.get("username", "?"))
        messagebox.showinfo("Linked", f"Linked to conduct case {ref}")
        self._render_empty_detail()

    def _link_halls(self, sid):
        ref = self._prompt("Halls link", "Accommodation incident reference:")
        if not ref:
            return
        link_halls_incident(sid, ref, actor=self.user.get("username", "?"))
        messagebox.showinfo("Linked", f"Linked to halls incident {ref}")
        self._render_empty_detail()

    def _health_referral(self, sid):
        if not messagebox.askyesno(
                "Health referral consent",
                "Has the student given explicit consent for a Health Centre "
                "referral to be made?"):
            return
        notes = self._prompt("Health referral", "Referral notes:") or ""
        try:
            create_health_referral(sid, consent=True, notes=notes,
                                   actor=self.user.get("username", "?"))
        except PermissionError as e:
            messagebox.showerror("Consent required", str(e))
            return
        messagebox.showinfo("Referred", "Health Centre referral logged.")
        self._render_empty_detail()

    def _notify_tutor(self, sid):
        tutor = self._prompt("Notify tutor",
                             "Tutor / Personal Advisor username:")
        if not tutor:
            return
        notify_tutor(sid, tutor, actor=self.user.get("username", "?"))
        messagebox.showinfo("Notified",
                            f"Redacted pastoral note sent to {tutor}.")
        self._render_empty_detail()

    def _render_linked_tab(self, host, sid, extra):
        tk.Label(host, text="Linked cases — same subject",
                 bg="white", font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 6))
        subj = extra.get("linked_subject_id")
        if not subj:
            tk.Label(host,
                     text="No subject id (anonymous case) — cannot link.",
                     bg="white", fg="#666",
                     font=("Segoe UI", 9, "italic")
                     ).pack(anchor="w", padx=12, pady=8)
            return
        cols = ("id", "submitted", "severity", "status", "lifecycle")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (50, 140, 90, 90, 90)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=12)
        related = find_linked_cases(subj, exclude_id=sid)
        for lid, lts, lsev, lstatus, llifecycle in related:
            tree.insert("", "end",
                        values=(lid, lts.replace("T", " ")[:16], lsev,
                                lstatus, llifecycle or "Open"))

        n, escalate = cumulative_concern(subj)
        warn = (f"⚠ {n} concerns in the last {_CUMULATIVE_WINDOW_DAYS} days"
                if escalate else
                f"{n} concerns in the last {_CUMULATIVE_WINDOW_DAYS} days")
        tk.Label(host, text=warn, bg="white",
                 fg="#b00020" if escalate else "#1f3a5f",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12,
                                                   pady=(8, 0))

    def _render_audit_tab(self, host, sid, extra):
        tk.Label(host, text="Assignment history", bg="white",
                 font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=12, pady=(10, 6))
        cols = ("assignee", "by", "at", "note")
        tree = ttk.Treeview(host, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (110, 110, 140, 200)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=12)
        for assignee, by, at, note in list_assignments(sid):
            tree.insert("", "end",
                        values=(assignee, by, at.replace("T", " ")[:16],
                                note or ""))

        # Reassignment form
        form = tk.Frame(host, bg="white")
        form.pack(fill="x", padx=12, pady=8)
        tk.Label(form, text="Reassign to (username):", bg="white"
                 ).grid(row=0, column=0, sticky="w")
        u_e = ttk.Entry(form, width=18); u_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Note:", bg="white"
                 ).grid(row=0, column=2, sticky="w")
        n_e = ttk.Entry(form, width=24); n_e.grid(row=0, column=3, padx=4)

        def _reassign():
            who = u_e.get().strip()
            if not who:
                return
            assign_case(sid, who,
                        assigned_by=self.user.get("username") or "?",
                        note=n_e.get().strip())
            for w in host.winfo_children():
                w.destroy()
            self._render_audit_tab(host, sid, extra)
        ttk.Button(form, text="Reassign", command=_reassign
                   ).grid(row=0, column=4, padx=6)

    def _open_attachment(self, stored_name: str):
        path = decrypt_to_temp(stored_name)
        if not path:
            messagebox.showerror("Attachment", "Could not open attachment.")
            return
        try:
            webbrowser.open_new("file://" + path)
        except Exception:
            messagebox.showinfo("Attachment", f"Decrypted to:\n{path}")

    # ---------- top bar ----------
    def _build_topbar(self, title):
        bar = tk.Frame(self.container, bg="#1f3a5f", height=55)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text=title, bg="#1f3a5f", fg="white",
                 font=("Segoe UI", 12, "bold")).pack(side="left",
                                                    padx=20)

        # Safe-exit button always visible — disguised label, immediate effect.
        exit_lang = self.__dict__.get("lang", "en")
        exit_btn = tk.Button(
            bar, text=tr("safe_exit", exit_lang),
            bg="#d9480f", fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), padx=12, pady=4,
            activebackground="#b00020", activeforeground="white",
            command=quick_exit,
        )
        exit_btn.pack(side="right", padx=12, pady=10)
        # Bind ESC anywhere as a panic key
        self._host.bind_all("<Escape>", lambda _e: quick_exit())

        # Tools menu — staff only (gates inside the dialogs further restrict).
        if self.user and _is_staff_role(self.user.get('role')):
            tk.Button(bar, text="Tools",
                      bg="#1f3a5f", fg="white", relief="flat",
                      font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                      activebackground="#274875", activeforeground="white",
                      command=self._open_tools_menu
                      ).pack(side="right", padx=4, pady=10)

        role = (self.user or {}).get('role') or '—'
        tk.Label(bar,
                 text=f"Signed in: {(self.user or {}).get('username') or 'Guest'}  ({role})",
                 bg="#1f3a5f", fg="#cfe0ff",
                 font=("Segoe UI", 9)).pack(side="right", padx=20)


# ---------------------------------------------------------------------------

def main():
    _remove_legacy_db()
    init_db()
    app = SafeguardingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
