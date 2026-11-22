"""Graduation: who runs it, the audit trail, holds, the name on the
certificate, conferrals (the award given, in a ceremony or in absentia) and
everything hanging off them — certificate print jobs, transcript shares,
HEAR achievements — plus ceremony cohorts, invitations, named guest tickets,
extra-ticket requests and attendance.

The existing ceremony tables (``graduation_ceremonies``, ``ceremony_rsvps``,
``ceremony_gown_orders``, ``ceremony_seat_assignments``) and record tables
(``certificates``, ``blockchain_credentials``, ``transcript_freezes``,
``transcript_access_tokens``) gain the columns the workflows need.

Shared by migration ``d5f7a9b1c3e6`` and :func:`apply_to_connection`
(``university/application/graduation/``). Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    ("graduation_ceremonies", "gown_order_deadline", "TEXT"),
    ("ceremony_rsvps", "access_needs", "TEXT"),
    ("ceremony_rsvps", "attended_at", "TEXT"),
    ("ceremony_rsvps", "checked_in_by", "TEXT"),
    ("ceremony_rsvps", "no_show", "INTEGER DEFAULT 0"),
    ("ceremony_rsvps", "transferred_to", "INTEGER"),
    ("ceremony_rsvps", "recorded_by", "TEXT"),
    ("ceremony_gown_orders", "cancelled_at", "TEXT"),
    ("ceremony_gown_orders", "cancel_reason", "TEXT"),
    ("ceremony_gown_orders", "refund_id", "INTEGER"),
    ("transcript_freezes", "conferral_id", "INTEGER"),
    ("transcript_freezes", "superseded_at", "TEXT"),
    ("transcript_freezes", "revoked_at", "TEXT"),
    ("transcript_access_tokens", "consent_reference", "TEXT"),
    ("transcript_access_tokens", "access_count", "INTEGER DEFAULT 0"),
    ("transcript_access_tokens", "created_by", "TEXT"),
    ("blockchain_credentials", "revoked_at", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS graduation_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('graduation_office', 'ceremony_staff')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role)
    )""",
    """CREATE TABLE IF NOT EXISTS graduation_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_graduation_audit_entity ON graduation_audit (entity, entity_id)",
    """CREATE TABLE IF NOT EXISTS graduation_holds (
        hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('appeal', 'misconduct', 'registry', 'finance',
                                           'other')),
        reason TEXT NOT NULL,
        placed_by TEXT,
        placed_at TEXT NOT NULL DEFAULT (datetime('now')),
        released_by TEXT,
        released_at TEXT,
        release_note TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_graduation_holds_student ON graduation_holds "
    "(student_id, released_at)",
    """CREATE TABLE IF NOT EXISTS certificate_names (
        student_id TEXT PRIMARY KEY,
        certificate_name TEXT NOT NULL,
        confirmed_by_student INTEGER NOT NULL DEFAULT 0,
        confirmed_at TEXT,
        set_by TEXT,
        evidence TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS graduation_conferrals (
        conferral_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        award_id INTEGER NOT NULL,
        programme_code TEXT,
        award_name TEXT NOT NULL,
        classification TEXT,
        academic_year TEXT,
        conferral_date TEXT NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('ceremony', 'in_absentia')),
        ceremony_id INTEGER,
        certificate_name TEXT NOT NULL,
        certificate_id INTEGER,
        certificate_number TEXT,
        credential_id INTEGER,
        verification_code TEXT,
        freeze_id INTEGER,
        status TEXT NOT NULL DEFAULT 'conferred'
            CHECK (status IN ('conferred', 'suspended', 'revoked', 'superseded')),
        conferred_by TEXT,
        conferred_at TEXT NOT NULL DEFAULT (datetime('now')),
        status_changed_at TEXT,
        status_changed_by TEXT,
        status_reason TEXT,
        replaces_conferral_id INTEGER
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_graduation_conferrals_live ON graduation_conferrals "
    "(student_id, award_id) WHERE status IN ('conferred', 'suspended')",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_graduation_conferrals_code ON graduation_conferrals "
    "(verification_code) WHERE verification_code IS NOT NULL",
    """CREATE TABLE IF NOT EXISTS certificate_print_jobs (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        conferral_id INTEGER,
        student_id TEXT NOT NULL,
        certificate_id INTEGER,
        certificate_number TEXT,
        kind TEXT NOT NULL DEFAULT 'original' CHECK (kind IN ('original', 'replacement')),
        delivery TEXT NOT NULL DEFAULT 'ceremony' CHECK (delivery IN ('ceremony', 'post',
                                                                       'collect')),
        ceremony_id INTEGER,
        address TEXT,
        fee REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'printing',
            'printed', 'dispatched', 'collected', 'cancelled', 'failed')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        printed_at TEXT,
        dispatched_at TEXT,
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ceremony_cohorts (
        ceremony_id INTEGER NOT NULL REFERENCES graduation_ceremonies(ceremony_id)
            ON DELETE CASCADE,
        kind TEXT NOT NULL CHECK (kind IN ('programme', 'department', 'award_year')),
        value TEXT NOT NULL,
        PRIMARY KEY (ceremony_id, kind, value)
    )""",
    """CREATE TABLE IF NOT EXISTS ceremony_invitations (
        ceremony_id INTEGER NOT NULL REFERENCES graduation_ceremonies(ceremony_id)
            ON DELETE CASCADE,
        student_id TEXT NOT NULL,
        invited_at TEXT NOT NULL DEFAULT (datetime('now')),
        invited_by TEXT,
        last_reminded_at TEXT,
        PRIMARY KEY (ceremony_id, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS ceremony_guests (
        guest_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ceremony_id INTEGER NOT NULL REFERENCES graduation_ceremonies(ceremony_id)
            ON DELETE CASCADE,
        student_id TEXT NOT NULL,
        guest_name TEXT NOT NULL,
        ticket_ref TEXT NOT NULL UNIQUE,
        access_needs TEXT,
        status TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'cancelled')),
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_ceremony_guests_student ON ceremony_guests "
    "(ceremony_id, student_id, status)",
    """CREATE TABLE IF NOT EXISTS ceremony_ticket_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ceremony_id INTEGER NOT NULL REFERENCES graduation_ceremonies(ceremony_id)
            ON DELETE CASCADE,
        student_id TEXT NOT NULL,
        requested INTEGER NOT NULL CHECK (requested > 0),
        granted INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'waiting'
            CHECK (status IN ('waiting', 'granted', 'partly_granted', 'declined', 'withdrawn')),
        requested_at TEXT NOT NULL DEFAULT (datetime('now')),
        decided_at TEXT,
        UNIQUE (ceremony_id, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS hear_achievements (
        achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        verified_by TEXT,
        verified_at TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
)

#: The old per-ceremony print queue becomes print jobs (no conferral behind them).
COPY_PRINT_QUEUE = (
    "INSERT INTO certificate_print_jobs (student_id, certificate_id, certificate_number, kind, "
    "delivery, ceremony_id, status, created_at, printed_at, dispatched_at, notes) SELECT "
    "q.student_id, q.certificate_id, q.certificate_number, 'original', 'ceremony', q.ceremony_id, "
    "q.status, q.created_at, q.printed_at, q.dispatched_at, COALESCE(q.notes, '') || ' (from the "
    "old print queue)' FROM graduation_print_queue q WHERE NOT EXISTS (SELECT 1 FROM "
    "certificate_print_jobs j WHERE j.certificate_number = q.certificate_number)"
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        execute(ddl)
    if _columns(execute, "graduation_print_queue"):
        execute(COPY_PRINT_QUEUE)


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
