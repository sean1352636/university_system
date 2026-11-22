"""Tables for Support to Study and trusted contacts (``student_records.db``).

Additive only (``CREATE TABLE IF NOT EXISTS``), created on first use by
:func:`ensure` on the caller's connection — no migration, so nothing has to
be applied before the screens work. Free text about a student's health or
wellbeing (a case's reason, meeting summaries, the circumstances of using a
trusted contact) is sealed by the callers (``wellbeing_bus.seal_text``).
"""

from __future__ import annotations

_DONE: set[str] = set()

SUPPORT_TO_STUDY = (
    """CREATE TABLE IF NOT EXISTS sts_cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        stage INTEGER NOT NULL DEFAULT 1 CHECK (stage BETWEEN 1 AND 3),
        status TEXT NOT NULL DEFAULT 'open',
        reason TEXT,
        case_manager TEXT,
        opened_by TEXT NOT NULL,
        opened_at TEXT NOT NULL DEFAULT (datetime('now')),
        closed_by TEXT,
        closed_at TEXT,
        closed_reason TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_sts_cases_student ON sts_cases (student_id, status)",
    """CREATE TABLE IF NOT EXISTS sts_stage_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES sts_cases (case_id),
        from_stage INTEGER,
        to_stage INTEGER NOT NULL,
        reason TEXT,
        changed_by TEXT NOT NULL,
        changed_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sts_meetings (
        meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES sts_cases (case_id),
        stage INTEGER NOT NULL,
        meeting_date TEXT NOT NULL,
        meeting_time TEXT,
        location TEXT,
        attendees TEXT,
        panel_members TEXT,
        supporter TEXT,
        status TEXT NOT NULL DEFAULT 'scheduled',
        student_attended INTEGER,
        summary TEXT,
        scheduled_by TEXT NOT NULL,
        recorded_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sts_actions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES sts_cases (case_id),
        stage INTEGER NOT NULL,
        action_text TEXT NOT NULL,
        owner TEXT NOT NULL DEFAULT 'student',
        due_date TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sts_outcomes (
        outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES sts_cases (case_id),
        stage INTEGER NOT NULL,
        outcome_type TEXT NOT NULL,
        decision TEXT,
        review_date TEXT,
        lifecycle_history_id INTEGER,
        expected_return_date TEXT,
        decided_by TEXT NOT NULL,
        decided_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sts_letters (
        letter_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES sts_cases (case_id),
        kind TEXT NOT NULL,
        ref_id INTEGER,
        path TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sts_links (
        link_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES sts_cases (case_id),
        kind TEXT NOT NULL,
        ref_id TEXT NOT NULL,
        note TEXT,
        linked_by TEXT NOT NULL,
        linked_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (case_id, kind, ref_id)
    )""",
)

TRUSTED_CONTACTS = (
    """CREATE TABLE IF NOT EXISTS trusted_contact_consents (
        student_id TEXT PRIMARY KEY,
        consent_given INTEGER NOT NULL DEFAULT 0,
        statement TEXT,
        recorded_by TEXT NOT NULL,
        given_at TEXT,
        withdrawn_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS trusted_contact_consent_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        action TEXT NOT NULL,
        statement TEXT,
        by_user TEXT NOT NULL,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS trusted_contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        name TEXT NOT NULL,
        relationship TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        priority INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        removed_reason TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_trusted_contacts_student ON trusted_contacts (student_id)",
    """CREATE TABLE IF NOT EXISTS trusted_contact_uses (
        use_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        contact_id INTEGER NOT NULL REFERENCES trusted_contacts (contact_id),
        reason TEXT NOT NULL,
        circumstances TEXT,
        basis TEXT NOT NULL DEFAULT 'consent',
        emergency INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'requested',
        requested_by TEXT NOT NULL,
        requested_at TEXT NOT NULL DEFAULT (datetime('now')),
        approved_by TEXT,
        approved_at TEXT,
        approval_note TEXT,
        contacted_by TEXT,
        contacted_at TEXT,
        method TEXT,
        outcome TEXT,
        student_informed INTEGER NOT NULL DEFAULT 0,
        informed_at TEXT,
        informed_by TEXT,
        inform_deferred_reason TEXT,
        inform_review_date TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_trusted_contact_uses_student "
    "ON trusted_contact_uses (student_id)",
)


def _key(conn, group: str) -> str:
    try:
        path = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        path = ""
    return f"{group}:{path}"


def _apply(conn, group: str, statements) -> None:
    key = _key(conn, group)
    if key in _DONE:
        return
    for sql in statements:
        conn.execute(sql)
    _DONE.add(key)


def ensure_support_to_study(conn) -> None:
    _apply(conn, "sts", SUPPORT_TO_STUDY)


def ensure_trusted_contacts(conn) -> None:
    _apply(conn, "trusted", TRUSTED_CONTACTS)
