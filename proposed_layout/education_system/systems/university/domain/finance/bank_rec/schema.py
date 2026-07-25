"""Bank reconciliation schema. Idempotent init.

Two tables:
- bank_statements: one row per imported statement file
- bank_statement_lines: one row per statement line, linked to a statement,
  carrying match status and pointers to the matched payment or refund
"""

from education_system.systems.university.infrastructure.database.db import get_connection


_STATEMENTS = {
    "bank_statements": """
        CREATE TABLE IF NOT EXISTS bank_statements (
            statement_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name    TEXT    NOT NULL,
            period_start    TEXT,
            period_end      TEXT,
            opening_balance REAL,
            closing_balance REAL,
            imported_at     TEXT    NOT NULL DEFAULT (datetime('now')),
            imported_by     TEXT,
            source_file     TEXT
        )
    """,
    "bank_statement_lines": """
        CREATE TABLE IF NOT EXISTS bank_statement_lines (
            line_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_id       INTEGER NOT NULL REFERENCES bank_statements(statement_id) ON DELETE CASCADE,
            line_no            INTEGER NOT NULL,
            txn_date           TEXT    NOT NULL,
            amount             REAL    NOT NULL,
            description        TEXT,
            reference          TEXT,
            status             TEXT    NOT NULL DEFAULT 'unmatched'
                                CHECK (status IN ('unmatched','matched_auto','matched_manual','discarded')),
            matched_payment_id INTEGER,
            matched_refund_id  INTEGER,
            matched_at         TEXT,
            matched_by         TEXT,
            notes              TEXT
        )
    """,
}

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_bsl_statement ON bank_statement_lines(statement_id)",
    "CREATE INDEX IF NOT EXISTS idx_bsl_status    ON bank_statement_lines(status)",
    "CREATE INDEX IF NOT EXISTS idx_bsl_amount    ON bank_statement_lines(amount)",
    "CREATE INDEX IF NOT EXISTS idx_bsl_date      ON bank_statement_lines(txn_date)",
]


def init_bank_rec():
    """Create the bank_statements + bank_statement_lines tables. Idempotent."""
    conn = get_connection()
    cur = conn.cursor()
    for stmt in _STATEMENTS.values():
        cur.execute(stmt)
    for ix in _INDEXES:
        cur.execute(ix)
    conn.commit()
    conn.close()
    return True
