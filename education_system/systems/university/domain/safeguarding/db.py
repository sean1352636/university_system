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

from education_system.systems.university.domain.safeguarding.config import (
    _LEGACY_DB_FILE,
)


def _connect():
    from education_system.systems.university.infrastructure.database.db import get_connection

    return get_connection()


_EXTRA_COLUMNS = [
    ("anonymous", "INTEGER DEFAULT 0"),
    ("contact_token", "TEXT"),  # sha256 hash; raw token shown once to user
    ("on_behalf_of", "INTEGER DEFAULT 0"),
    ("reporter_username", "TEXT"),  # actual reporter when on_behalf_of=1
    ("subject_relation", "TEXT"),  # "Friend", "Classmate", etc.
    ("triage", "TEXT"),  # JSON of wizard answers
    ("attachments", "TEXT"),  # JSON list of stored filenames
    ("audio_path", "TEXT"),
    ("transcription", "TEXT"),
    ("language", "TEXT"),
    ("consent_disclosure", "INTEGER DEFAULT 0"),
    ("consent_contact", "INTEGER DEFAULT 0"),
    ("duplicate_of", "INTEGER"),
    # Features 11-25
    ("likelihood", "INTEGER"),  # 1..5 — feature 11
    ("impact", "INTEGER"),  # 1..5 — feature 11
    ("risk_score", "INTEGER"),  # likelihood*impact — feature 11
    ("nlp_score", "REAL"),  # 0..1 confidence — feature 12
    ("nlp_categories", "TEXT"),  # JSON {category: score} — feature 12
    ("sla_due_at", "TEXT"),  # ISO datetime — feature 14
    ("sla_breached", "INTEGER DEFAULT 0"),  # feature 14
    ("assigned_to", "TEXT"),  # username of DSL — feature 15
    ("assigned_at", "TEXT"),  # feature 15
    ("linked_subject_id", "TEXT"),  # canonical subject id — feature 16
    ("vulnerability_flags", "TEXT"),  # JSON list — feature 17
    ("lifecycle_state", "TEXT DEFAULT 'Open'"),  # feature 21
    ("case_location", "TEXT"),  # building/campus — feature 19
    ("case_department", "TEXT"),  # department/school — feature 19
    # Features 26-40
    ("next_review_at", "TEXT"),  # feature 27
    ("review_interval_days", "INTEGER"),  # feature 27
    ("outcome_code", "TEXT"),  # feature 28
    ("closure_reason", "TEXT"),  # feature 28
    ("content_encrypted", "INTEGER DEFAULT 0"),  # feature 37
    ("content_blob", "BLOB"),  # feature 37
    ("transcription_encrypted", "INTEGER DEFAULT 0"),  # feature 37
    ("transcription_blob", "BLOB"),  # feature 37
    ("merged_into", "INTEGER"),  # feature 30
    ("split_from", "INTEGER"),  # feature 30
    ("retention_until", "TEXT"),  # feature 39
    ("purged", "INTEGER DEFAULT 0"),  # feature 39
    # Features 41-50
    ("mandatory_reporting", "INTEGER DEFAULT 0"),  # feature 41
    ("mandatory_status", "TEXT"),  # feature 41
    ("mandatory_reported_at", "TEXT"),  # feature 41
    ("whistleblowing", "INTEGER DEFAULT 0"),  # feature 42
    ("wb_independent_reviewer", "TEXT"),  # feature 42
    ("linked_wellbeing_appt", "TEXT"),  # feature 43
    ("linked_conduct_case", "TEXT"),  # feature 44
    ("linked_halls_incident", "TEXT"),  # feature 45
    ("health_referral_consent", "INTEGER DEFAULT 0"),  # feature 46
    ("health_referral_sent_at", "TEXT"),  # feature 46
    ("tutor_notified_at", "TEXT"),  # feature 47
    ("tutor_notification_redacted", "TEXT"),  # feature 47
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sg_audit_case ON safeguarding_audit_log(case_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sg_audit_ts ON safeguarding_audit_log(ts)")
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
                logger.warning("Could not remove legacy DB file %s", path, exc_info=True)


__all__ = ["_connect", "_EXTRA_COLUMNS", "init_db", "_remove_legacy_db"]
