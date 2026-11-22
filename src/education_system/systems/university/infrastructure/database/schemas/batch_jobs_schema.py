"""Batch operations: a job per import / bulk run with its per-row results
(and what undoing each row needs), saved column mappings, and watched
folders for scheduled imports.

Later (migration ``b8d0f2a4c6e9``): watched folders can run daily at a set
time (``run_at``) instead of only when someone presses Run, and batch
reports can be e-mailed on a schedule (``batch_report_schedules``).

Later still (migration ``c4e6a8b0d2f5``): the window's settings
(``batch_settings``: back up before imports, the duplicate rule, who is told
when a job finishes, default column mappings, the history window).

Shared by migrations ``a2c4e6f8b0d1`` / ``b8d0f2a4c6e9`` / ``c4e6a8b0d2f5`` and :func:`apply_to_connection`
(``university/application/batch/jobs``). Idempotent.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS batch_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL CHECK (kind IN ('students', 'marks', 'staff', 'actions')),
        source TEXT,
        mode TEXT,
        actor TEXT NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'undone')),
        total INTEGER NOT NULL DEFAULT 0,
        succeeded INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0,
        failed INTEGER NOT NULL DEFAULT 0,
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT,
        undone_by TEXT,
        undone_at TEXT,
        undo_reason TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS batch_job_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
        row_no INTEGER NOT NULL,
        ref TEXT,
        outcome TEXT NOT NULL CHECK (outcome IN ('created', 'updated', 'unchanged', 'skipped',
                                                 'failed', 'undone')),
        message TEXT,
        undo_json TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_batch_job_rows_job ON batch_job_rows (job_id, row_no)",
    """CREATE TABLE IF NOT EXISTS batch_import_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('students', 'marks', 'staff')),
        name TEXT NOT NULL,
        mapping_json TEXT NOT NULL,
        shared INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (owner, kind, name)
    )""",
    """CREATE TABLE IF NOT EXISTS batch_watch_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('students', 'marks')),
        folder TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'create',
        mapping_id INTEGER REFERENCES batch_import_mappings(id) ON DELETE SET NULL,
        reason TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        last_run_at TEXT,
        last_result TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS batch_report_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        report TEXT NOT NULL CHECK (report IN ('success', 'errors', 'performance',
                                              'comprehensive', 'statistics')),
        frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
        recipients TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        last_sent_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS batch_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
)

COLUMNS = (
    ("batch_watch_folders", "run_at", "TEXT"),
    ("batch_watch_folders", "last_scheduled_on", "TEXT"),
)


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)
    for table, column, decl in COLUMNS:
        existing = {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')


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
