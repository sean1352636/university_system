"""External statutory returns and feeds: HESA Data Futures (coding frames,
HESA student identifiers, the built return on ``hesa_returns``), the SLC
attendance-confirmation worklist per census point and change-of-circumstance
notices, UCAS applicant imports and decision files, CAS requests for the Home
Office Sponsor Management System and UKVI reporting batches, and Graduate
Outcomes census periods with their contact extracts, plus one audit trail.

Applied by :func:`apply_to_connection` from
``university/application/statutory/``. Additive and idempotent: new tables
only, and new nullable columns on ``hesa_returns`` and
``visa_change_of_circumstance`` when those tables exist.
"""

from __future__ import annotations

COLUMNS = (
    ("hesa_returns", "reference_period", "TEXT"),
    ("hesa_returns", "period_start", "TEXT"),
    ("hesa_returns", "period_end", "TEXT"),
    ("hesa_returns", "validation_json", "TEXT"),
    ("hesa_returns", "entity_counts_json", "TEXT"),
    ("hesa_returns", "output_path", "TEXT"),
    ("hesa_returns", "built_at", "TEXT"),
    ("hesa_returns", "built_by", "TEXT"),
    ("visa_change_of_circumstance", "ukvi_batch_id", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS statutory_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        area TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        action TEXT NOT NULL,
        actor TEXT NOT NULL,
        detail_json TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_statutory_audit_area ON statutory_audit (area, at)",
    # HESA coding frames: field (SEXID, NATION, ...) -> code -> label.
    """CREATE TABLE IF NOT EXISTS hesa_coding_frames (
        field TEXT NOT NULL,
        code TEXT NOT NULL,
        label TEXT NOT NULL,
        notes TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (field, code)
    )""",
    # The HESA student identifier (SID) is issued outside this system.
    """CREATE TABLE IF NOT EXISTS hesa_student_identifiers (
        student_id TEXT PRIMARY KEY,
        sid TEXT NOT NULL UNIQUE,
        recorded_by TEXT,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # SLC: one decision per student per census point.
    """CREATE TABLE IF NOT EXISTS slc_census_confirmations (
        confirmation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        census_date TEXT NOT NULL,
        year_code TEXT,
        census_title TEXT,
        student_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('confirmed', 'held', 'not_attending',
                                                'withdrawn')),
        reason TEXT,
        attendance_pct REAL,
        decided_by TEXT NOT NULL,
        decided_at TEXT NOT NULL DEFAULT (datetime('now')),
        batch_id TEXT,
        UNIQUE (census_date, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS slc_change_notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        history_id INTEGER NOT NULL UNIQUE,
        student_id TEXT NOT NULL,
        change_type TEXT NOT NULL,
        effective_date TEXT NOT NULL,
        from_status TEXT,
        to_status TEXT,
        details TEXT,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'exported', 'acknowledged', 'not_required')),
        batch_id TEXT,
        slc_reference TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_by TEXT,
        updated_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_slc_change_status ON slc_change_notifications (status)",
    # UCAS applicant files and decision files.
    """CREATE TABLE IF NOT EXISTS ucas_import_batches (
        batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_format TEXT NOT NULL,
        imported_by TEXT NOT NULL,
        imported_at TEXT NOT NULL DEFAULT (datetime('now')),
        rows_total INTEGER NOT NULL DEFAULT 0,
        created INTEGER NOT NULL DEFAULT 0,
        updated INTEGER NOT NULL DEFAULT 0,
        linked INTEGER NOT NULL DEFAULT 0,
        errors_json TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ucas_import_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL REFERENCES ucas_import_batches(batch_id),
        personal_id TEXT NOT NULL,
        scheme TEXT,
        choice_number TEXT,
        course_code TEXT NOT NULL,
        campus_code TEXT,
        entry_year TEXT NOT NULL,
        point_of_entry TEXT,
        ucas_status TEXT,
        ucas_decision TEXT,
        application_id INTEGER,
        link_id INTEGER,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (personal_id, course_code, entry_year)
    )""",
    """CREATE TABLE IF NOT EXISTS ucas_decision_exports (
        export_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        personal_id TEXT NOT NULL,
        decision_code TEXT NOT NULL,
        decision_date TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        exported_by TEXT NOT NULL,
        exported_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (application_id, decision_code, decision_date)
    )""",
    # CAS: requests made in the Sponsor Management System by staff.
    """CREATE TABLE IF NOT EXISTS cas_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        programme TEXT NOT NULL,
        course_start_date TEXT NOT NULL,
        course_end_date TEXT NOT NULL,
        tuition_fee_gbp REAL NOT NULL,
        fee_paid_gbp REAL NOT NULL DEFAULT 0,
        living_costs_gbp REAL NOT NULL DEFAULT 0,
        english_evidence TEXT,
        atas_required INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'requested'
            CHECK (status IN ('requested', 'submitted', 'assigned', 'cancelled')),
        requested_by TEXT NOT NULL,
        requested_at TEXT NOT NULL DEFAULT (datetime('now')),
        submitted_by TEXT,
        submitted_at TEXT,
        cas_number TEXT UNIQUE,
        assigned_at TEXT,
        notes TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_cas_requests_status ON cas_requests (status)",
    """CREATE TABLE IF NOT EXISTS ukvi_report_batches (
        batch_id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        item_count INTEGER NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # Graduate Outcomes: one row per cohort census period.
    """CREATE TABLE IF NOT EXISTS go_census_periods (
        census_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cohort TEXT NOT NULL UNIQUE,
        qualified_from TEXT NOT NULL,
        qualified_to TEXT NOT NULL,
        contact_file_due TEXT,
        status TEXT NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'extracted', 'submitted', 'closed')),
        extracted_at TEXT,
        extracted_by TEXT,
        file_name TEXT,
        contacts INTEGER NOT NULL DEFAULT 0,
        excluded INTEGER NOT NULL DEFAULT 0,
        submitted_at TEXT,
        submitted_by TEXT,
        notes TEXT,
        CHECK (qualified_to >= qualified_from)
    )""",
    """CREATE TABLE IF NOT EXISTS go_census_contacts (
        census_id INTEGER NOT NULL REFERENCES go_census_periods(census_id) ON DELETE CASCADE,
        student_id TEXT NOT NULL,
        qualified_on TEXT,
        included INTEGER NOT NULL,
        reason TEXT,
        PRIMARY KEY (census_id, student_id)
    )""",
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


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching. ``hesa_returns``
    and ``visa_change_of_circumstance`` are created by their own services;
    until both exist the columns are re-checked on every call."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    complete = all(_columns(conn.execute, t) for t in ("hesa_returns",
                                                        "visa_change_of_circumstance"))
    if busy:
        return
    conn.commit()
    if key and complete:
        _APPLIED.add(key)
