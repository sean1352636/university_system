"""University e-mail: one outbox every message goes through, delivery
attempts and bounces, address suppressions and unsubscribes, sender roles,
bulk sends, an audit of who sent what, and per-user e-mail preferences
(``email_preferences`` was created at runtime by the e-mail bus).

Shared by migration ``b9d1f3a5c7e0`` and :func:`apply_to_connection`
(``university/application/mail/outbox``). Idempotent.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS email_outbox (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        to_address TEXT NOT NULL COLLATE NOCASE,
        to_ref TEXT,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        cc TEXT,
        bcc TEXT,
        reply_to TEXT,
        attachments TEXT,
        kind TEXT NOT NULL DEFAULT 'transactional'
            CHECK (kind IN ('transactional', 'bulk', 'marketing')),
        category TEXT NOT NULL DEFAULT 'general',
        status TEXT NOT NULL DEFAULT 'queued'
            CHECK (status IN ('queued', 'sending', 'sent', 'failed', 'bounced', 'suppressed',
                              'stored', 'cancelled')),
        mode TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT,
        last_error TEXT,
        bulk_id INTEGER,
        stored_email_id INTEGER,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        sent_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        body_purged INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS ix_email_outbox_due ON email_outbox (status, next_attempt_at)",
    "CREATE INDEX IF NOT EXISTS ix_email_outbox_to ON email_outbox (to_address)",
    "CREATE INDEX IF NOT EXISTS ix_email_outbox_bulk ON email_outbox (bulk_id)",
    """CREATE TABLE IF NOT EXISTS email_attempts (
        attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL REFERENCES email_outbox (message_id) ON DELETE CASCADE,
        mode TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK (outcome IN ('sent', 'temporary', 'permanent',
                                              'rejected')),
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_email_attempts_msg ON email_attempts (message_id)",
    """CREATE TABLE IF NOT EXISTS email_suppressions (
        address TEXT NOT NULL COLLATE NOCASE,
        category TEXT NOT NULL DEFAULT '*',
        reason TEXT NOT NULL CHECK (reason IN ('bounce', 'complaint', 'unsubscribe', 'manual')),
        detail TEXT,
        added_by TEXT,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (address, category)
    )""",
    """CREATE TABLE IF NOT EXISTS email_unsubscribe_tokens (
        token TEXT PRIMARY KEY,
        address TEXT NOT NULL COLLATE NOCASE,
        category TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        used_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_email_unsub_address ON email_unsubscribe_tokens (address)",
    """CREATE TABLE IF NOT EXISTS email_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('bulk_sender', 'email_admin')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role)
    )""",
    """CREATE TABLE IF NOT EXISTS email_bulk_sends (
        bulk_id INTEGER PRIMARY KEY AUTOINCREMENT,
        audience TEXT NOT NULL,
        category TEXT NOT NULL,
        subject TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'bulk',
        recipients INTEGER NOT NULL DEFAULT 0,
        suppressed INTEGER NOT NULL DEFAULT 0,
        sent_by TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS email_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS email_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS email_preferences (
        user_id     TEXT NOT NULL,
        event_kind  TEXT NOT NULL,
        enabled     INTEGER NOT NULL DEFAULT 1,
        updated_at  TEXT NOT NULL,
        PRIMARY KEY (user_id, event_kind)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_email_prefs_user ON email_preferences(user_id)",
)


#: Columns added after a table was first created: ``(table, column, type)``.
ADDED_COLUMNS = (
    ('email_outbox', 'reply_to', 'TEXT'),       # Reply-To header (support mail, e.g.)
)


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)
    for table, column, kind in ADDED_COLUMNS:
        have = {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}
        if column not in have:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {kind}')


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
