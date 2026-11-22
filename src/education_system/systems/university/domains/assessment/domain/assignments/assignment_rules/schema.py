"""Columns and tables for the assignment rules. The migration and the runtime
bootstrap (``core/database.py``) both call :func:`apply`, so they can't drift.

``assignments.status`` already held the state of an assignment; it now takes
``draft``, ``hidden`` and ``scheduled`` as well as ``active``, and
``is_active`` stays the switch every student screen already reads.
"""

ASSIGNMENT_COLUMNS = (
    ("available_from", "TEXT"),
    ("max_late_days", "INTEGER"),
    ("max_attempts", "INTEGER"),
    ("automatic_checks", "INTEGER DEFAULT 1"),
    ("notify_on_submission", "INTEGER DEFAULT 1"),
    ("reminder_days", "INTEGER DEFAULT 2"),
    ("announced_at", "TEXT"),
)

SUBMISSION_COLUMNS = (
    ("declaration_at", "TEXT"),
    ("virus_scan", "TEXT"),
    ("withdrawn_at", "TEXT"),
)

TABLES = (
    """
    CREATE TABLE IF NOT EXISTS assignment_reminders_sent (
        assignment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY (assignment_id, student_id),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assignment_marker_allocations (
        assignment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        marker_username TEXT NOT NULL,
        allocated_by TEXT,
        allocated_at TEXT NOT NULL,
        PRIMARY KEY (assignment_id, student_id),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_assignment_marker_allocations_marker "
    "ON assignment_marker_allocations (marker_username)",
    # Name and maximum are copied so a later edit of the rubric can't change
    # what a student was marked against.
    """
    CREATE TABLE IF NOT EXISTS submission_rubric_scores (
        submission_id INTEGER NOT NULL,
        criterion_id INTEGER NOT NULL,
        criterion_name TEXT NOT NULL,
        score REAL NOT NULL,
        max_points REAL NOT NULL,
        marked_at TEXT NOT NULL,
        PRIMARY KEY (submission_id, criterion_id),
        FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id) ON DELETE CASCADE
    )
    """,
)


def apply(execute, existing_columns):
    """``execute(sql)`` runs one statement; ``existing_columns(table)`` returns
    a table's column names (empty if it is missing)."""
    for table, columns in (("assignments", ASSIGNMENT_COLUMNS),
                           ("assignment_submissions", SUBMISSION_COLUMNS)):
        present = existing_columns(table)
        if not present:
            continue
        for name, decl in columns:
            if name not in present:
                execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {decl}')
                if name == "announced_at":
                    # Already visible: students have been told.
                    execute("UPDATE assignments SET announced_at = COALESCE(created_at, "
                            "CURRENT_TIMESTAMP) WHERE is_active = 1")
    if existing_columns("assignments") and existing_columns("assignment_submissions"):
        for ddl in TABLES:
            execute(ddl)


def apply_to_connection(conn):
    apply(conn.execute,
          lambda table: {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')})
