"""Schema for first aid: incidents (with RIDDOR assessment and the link to
the Health & Safety incident a serious one becomes), the first-aider
certificate register, first aid kits / AEDs with their inspections, real
training course sessions, and reminder bookkeeping. Incidents are archived
(``archived`` / ``archived_at`` / ``archived_by`` / ``archive_reason``),
never hard-deleted.

Shared by migrations ``9c1e3a5d7f0b`` / ``a0d2f4b6c8e1`` and :func:`apply_to_connection`
(``domain/health/first_aid/first_aid_service.IncidentDB``,
``application/health/first_aid``). Idempotent.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS first_aid_incidents (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        submitted_at    TEXT NOT NULL,
        reporter_user   TEXT,
        reporter_name   TEXT NOT NULL,
        reporter_id     TEXT,
        phone           TEXT,
        email           TEXT,
        location        TEXT,
        incident_type   TEXT,
        severity        TEXT,
        description     TEXT NOT NULL,
        status          TEXT DEFAULT 'Open'
    )""",
    """CREATE TABLE IF NOT EXISTS first_aid_training_registrations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        submitted_at    TEXT NOT NULL,
        course          TEXT NOT NULL,
        user_id         TEXT,
        name            TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        preferred_date  TEXT,
        notes           TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS first_aiders (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        username            TEXT,
        name                TEXT NOT NULL,
        email               TEXT,
        qualification       TEXT NOT NULL,
        certificate_number  TEXT,
        issued_on           TEXT,
        expires_on          TEXT NOT NULL,
        location            TEXT,
        status              TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'lapsed', 'withdrawn')),
        notes               TEXT,
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_first_aiders_expiry ON first_aiders (expires_on, status)",
    """CREATE TABLE IF NOT EXISTS first_aid_kits (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        kind                TEXT NOT NULL CHECK (kind IN ('kit', 'aed', 'eyewash', 'burns')),
        label               TEXT NOT NULL,
        location            TEXT NOT NULL,
        detail              TEXT,
        last_checked        TEXT,
        check_every_days    INTEGER NOT NULL DEFAULT 30,
        contents_expiry     TEXT,
        aed_pads_expiry     TEXT,
        aed_battery_expiry  TEXT,
        status              TEXT NOT NULL DEFAULT 'in_service'
                            CHECK (status IN ('in_service', 'needs_restock', 'out_of_service',
                                              'retired')),
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS first_aid_kit_inspections (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        kit_id          INTEGER NOT NULL REFERENCES first_aid_kits (id) ON DELETE CASCADE,
        inspected_at    TEXT NOT NULL,
        inspected_by    TEXT NOT NULL,
        outcome         TEXT NOT NULL CHECK (outcome IN ('ok', 'restocked', 'faulty')),
        notes           TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_first_aid_kit_inspections ON first_aid_kit_inspections (kit_id)",
    """CREATE TABLE IF NOT EXISTS first_aid_course_sessions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        course      TEXT NOT NULL,
        starts_at   TEXT NOT NULL,
        ends_at     TEXT,
        location    TEXT,
        trainer     TEXT,
        capacity    INTEGER NOT NULL DEFAULT 12,
        description TEXT,
        status      TEXT NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled', 'cancelled', 'completed')),
        created_by  TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_first_aid_course_sessions ON first_aid_course_sessions "
    "(starts_at, status)",
    """CREATE TABLE IF NOT EXISTS first_aid_reminders (
        kind    TEXT NOT NULL,
        ref     TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY (kind, ref)
    )""",
)

COLUMNS = (
    ("first_aid_incidents", "email", "TEXT"),
    ("first_aid_incidents", "status", "TEXT DEFAULT 'Open'"),
    ("first_aid_incidents", "incident_date", "TEXT"),
    ("first_aid_incidents", "person_type", "TEXT"),
    ("first_aid_incidents", "riddor_category", "TEXT"),
    ("first_aid_incidents", "riddor_reportable", "INTEGER"),
    ("first_aid_incidents", "riddor_deadline", "TEXT"),
    ("first_aid_incidents", "riddor_status", "TEXT DEFAULT 'not_assessed'"),
    ("first_aid_incidents", "riddor_notes", "TEXT"),
    ("first_aid_incidents", "hse_reference", "TEXT"),
    ("first_aid_incidents", "riddor_assessed_by", "TEXT"),
    ("first_aid_incidents", "riddor_assessed_at", "TEXT"),
    ("first_aid_incidents", "riddor_reported_at", "TEXT"),
    ("first_aid_incidents", "hs_incident_id", "INTEGER"),
    # Soft delete, as health_records: an archived incident is hidden from
    # lists, the RIDDOR queue, reminders and exports, never removed.
    ("first_aid_incidents", "archived", "INTEGER DEFAULT 0"),
    ("first_aid_incidents", "archived_at", "TEXT"),
    ("first_aid_incidents", "archived_by", "TEXT"),
    ("first_aid_incidents", "archive_reason", "TEXT"),
    ("first_aid_training_registrations", "session_id", "INTEGER"),
)

INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_first_aid_incidents_riddor ON first_aid_incidents "
    "(riddor_status, riddor_deadline)",
    "CREATE INDEX IF NOT EXISTS ix_first_aid_incidents_archived ON first_aid_incidents (archived)",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in INDEXES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file; inside a caller's open
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
