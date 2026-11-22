"""Schema for medical accommodations reaching the rest of the university.

An approved accommodation in ``accommodations`` (the health portal's
record) is carried into the tables exams and assessments read —
``exam_accommodations``, ``student_accommodations`` and, where the type
implies one, approved ``extension_requests`` — each derived row carrying
``source_accommodation_id`` so withdrawal or expiry removes exactly what it
created. ``accommodation_shares`` records which module staff were told
(with the student's ``share_with_accommodation`` consent), so a notice goes
once and a "no longer applies" notice follows withdrawal.

``ACCOMMODATIONS_DDL`` is the one definition of ``accommodations``; the
accessibility service used to declare a different one (``accommodation_id``,
``is_active``, ``expiration_date NOT NULL``) that only "worked" because the
table already existed.

Shared by migration ``9c1e3a5d7f0b`` and
``services/bus/accommodation_bus``. Idempotent.
"""

from __future__ import annotations

ACCOMMODATIONS_DDL = """CREATE TABLE IF NOT EXISTS accommodations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    accommodation_type TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'active',
    approved_by TEXT,
    approval_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expiration_date DATE,
    request_id INTEGER,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
)"""

TABLES = (
    ACCOMMODATIONS_DDL,
    """CREATE TABLE IF NOT EXISTS accommodation_shares (
        accommodation_id INTEGER NOT NULL,
        recipient        TEXT NOT NULL,
        state            TEXT NOT NULL CHECK (state IN ('shared', 'withdrawn')),
        changed_at       TEXT NOT NULL,
        PRIMARY KEY (accommodation_id, recipient)
    )""",
)

# Derived-row links; only added where the table exists (it belongs to exams /
# assessment, which create it).
COLUMNS = (
    ("exam_accommodations", "source_accommodation_id", "INTEGER"),
    ("student_accommodations", "source_accommodation_id", "INTEGER"),
    ("extension_requests", "source_accommodation_id", "INTEGER"),
    ("accommodations", "request_id", "INTEGER"),
)

INDEXES = (
    ("exam_accommodations", "CREATE INDEX IF NOT EXISTS ix_exam_accommodations_source "
                            "ON exam_accommodations (source_accommodation_id)"),
    ("student_accommodations", "CREATE INDEX IF NOT EXISTS ix_student_accommodations_source "
                               "ON student_accommodations (source_accommodation_id)"),
    ("extension_requests", "CREATE INDEX IF NOT EXISTS ix_extension_requests_source "
                           "ON extension_requests (source_accommodation_id)"),
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
    for table, ddl in INDEXES:
        if _columns(execute, table):
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
