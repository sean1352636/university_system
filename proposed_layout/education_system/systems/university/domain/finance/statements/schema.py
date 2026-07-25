"""Schema for student statement runs."""

from education_system.systems.university.infrastructure.database.db import get_connection


_STATEMENTS = {
    "statement_runs": """
        CREATE TABLE IF NOT EXISTS statement_runs (
            run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start      TEXT,
            period_end        TEXT NOT NULL,
            generated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            generated_by      TEXT,
            status            TEXT NOT NULL DEFAULT 'completed',
            total_students    INTEGER NOT NULL DEFAULT 0,
            total_with_balance INTEGER NOT NULL DEFAULT 0
        )
    """,
    "student_statements": """
        CREATE TABLE IF NOT EXISTS student_statements (
            statement_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id              INTEGER NOT NULL REFERENCES statement_runs(run_id) ON DELETE CASCADE,
            student_id          TEXT    NOT NULL,
            period_start        TEXT,
            period_end          TEXT    NOT NULL,
            opening_balance     REAL    NOT NULL DEFAULT 0,
            charges_in_period   REAL    NOT NULL DEFAULT 0,
            payments_in_period  REAL    NOT NULL DEFAULT 0,
            refunds_in_period   REAL    NOT NULL DEFAULT 0,
            closing_balance     REAL    NOT NULL DEFAULT 0
        )
    """,
}

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_statements_run ON student_statements(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_statements_student ON student_statements(student_id)",
]


def init_statements():
    """Create statement_runs + student_statements tables. Idempotent."""
    conn = get_connection()
    cur = conn.cursor()
    for stmt in _STATEMENTS.values():
        cur.execute(stmt)
    for ix in _INDEXES:
        cur.execute(ix)
    conn.commit()
    conn.close()
    return True
