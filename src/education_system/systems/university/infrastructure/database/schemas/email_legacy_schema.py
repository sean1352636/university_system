"""The university's older e-mail tables: the in-app copy (``stored_emails``),
the send log (``email_log``), the inbox (``messages``), daily counts
(``email_metrics``), scheduled template e-mails (``scheduled_emails``) and
the e-mail module's own ``schema_migrations`` marker table.

These used to be created at runtime by ``infrastructure/email/
email_db_utilities.initialize_email_db`` and ``reports``; that DDL now lives
here, along with the outbox tables (``email_outbox_schema``), so one call
readies everything the e-mail code needs. Idempotent; a pre-2025
``scheduled_emails`` (``scheduled_for`` column) is rebuilt in the new shape.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.database.schemas import (
    email_outbox_schema,
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS stored_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        sender_email TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        cc_recipients TEXT,
        bcc_recipients TEXT,
        attachment_paths TEXT,
        created_date TEXT NOT NULL,
        template_name TEXT,
        template_vars TEXT,
        related_to TEXT,
        student_id TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS email_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT,
        subject TEXT,
        message TEXT,
        sent_date TEXT,
        status TEXT,
        related_to TEXT,
        student_id TEXT,
        sender_email TEXT,
        sender_name TEXT,
        cc_recipients TEXT,
        bcc_recipients TEXT,
        attachment_info TEXT,
        template_name TEXT,
        template_vars TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        recipient_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT,
        content TEXT,
        attachment_path TEXT,
        assignment_id INTEGER,
        is_read INTEGER DEFAULT 0,
        is_archived INTEGER DEFAULT 0,
        is_deleted_by_sender INTEGER DEFAULT 0,
        is_deleted_by_recipient INTEGER DEFAULT 0,
        sent_at TEXT NOT NULL,
        read_at TEXT,
        reply_to INTEGER,
        FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,
        FOREIGN KEY (reply_to) REFERENCES messages (id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS email_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        opened_count INTEGER DEFAULT 0,
        clicked_count INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS schema_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL UNIQUE,
        migration_name TEXT NOT NULL,
        applied_at TEXT NOT NULL,
        status TEXT DEFAULT 'success',
        error_message TEXT,
        rollback_sql TEXT
    )""",
)

_SCHEDULED = """CREATE TABLE IF NOT EXISTS scheduled_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT,
        recipient_email TEXT NOT NULL,
        template_vars TEXT,
        scheduled_date TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL
    )"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_recipient_id ON messages(recipient_id)",
    "CREATE INDEX IF NOT EXISTS idx_sender_id ON messages(sender_id)",
    "CREATE INDEX IF NOT EXISTS idx_email_metrics_date ON email_metrics(date)",
    "CREATE INDEX IF NOT EXISTS idx_scheduled_emails_date ON scheduled_emails(scheduled_date)",
)

COLUMNS = (
    ("messages", "message", "TEXT"),
    ("messages", "content", "TEXT"),
    ("messages", "attachment_path", "TEXT"),
    ("messages", "assignment_id", "INTEGER"),
    ("messages", "is_archived", "INTEGER DEFAULT 0"),
    ("messages", "is_deleted_by_sender", "INTEGER DEFAULT 0"),
    ("messages", "is_deleted_by_recipient", "INTEGER DEFAULT 0"),
    ("messages", "read_at", "TEXT"),
    ("messages", "reply_to", "INTEGER"),
    ("email_log", "sender_email", "TEXT"),
    ("email_log", "sender_name", "TEXT"),
    ("email_log", "cc_recipients", "TEXT"),
    ("email_log", "bcc_recipients", "TEXT"),
    ("email_log", "attachment_info", "TEXT"),
    ("email_log", "template_name", "TEXT"),
    ("email_log", "template_vars", "TEXT"),
    ("email_log", "opened_at", "TEXT"),
    ("email_log", "clicked_at", "TEXT"),
    ("email_log", "delivery_status", "TEXT"),
    ("email_log", "bounce_reason", "TEXT"),
    ("email_log", "body", "TEXT"),
    ("email_log", "sent_at", "TEXT"),
    ("email_log", "error_message", "TEXT"),
    ("scheduled_emails", "template_name", "TEXT"),
    ("scheduled_emails", "recipient_email", "TEXT NOT NULL DEFAULT ''"),
    ("scheduled_emails", "template_vars", "TEXT"),
    ("scheduled_emails", "scheduled_date", "TEXT NOT NULL DEFAULT '2024-01-01 00:00:00'"),
    ("scheduled_emails", "status", "TEXT DEFAULT 'pending'"),
    ("scheduled_emails", "created_at", "TEXT NOT NULL DEFAULT ''"),
    ("scheduled_emails", "body", "TEXT"),
    ("scheduled_emails", "error_message", "TEXT"),
    ("scheduled_emails", "recipient", "TEXT"),
    ("scheduled_emails", "scheduled_time", "TEXT"),
    ("scheduled_emails", "sent_at", "TEXT"),
    ("scheduled_emails", "subject", "TEXT"),
)


def _columns(execute, table) -> set[str]:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _rebuild_legacy_scheduled(execute) -> None:
    """Pre-2025 ``scheduled_emails`` (recipient/subject/body/scheduled_for)."""
    cols = _columns(execute, "scheduled_emails")
    if "scheduled_for" not in cols or "scheduled_date" in cols:
        return
    execute('ALTER TABLE "scheduled_emails" RENAME TO "scheduled_emails_old"')
    execute(_SCHEDULED)
    execute("INSERT INTO scheduled_emails (id, recipient_email, template_vars, scheduled_date, "
            "status, created_at) SELECT id, recipient, json_object('subject', subject, 'body', "
            "body), scheduled_for, COALESCE(status, 'pending'), COALESCE(created_at, "
            "datetime('now')) FROM scheduled_emails_old")
    execute('DROP TABLE "scheduled_emails_old"')


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)
    _rebuild_legacy_scheduled(execute)
    execute(_SCHEDULED)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in INDEXES:
        execute(ddl)
    email_outbox_schema.apply(execute)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
