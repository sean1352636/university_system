"""GL schema definitions and idempotent init.

Multi-entity ready: gl_entities + entity_id on gl_journals. Single entity
seeded by default; additional entities can be inserted later without schema
change. Periods are shared across entities in v1 (a future change can add
entity_id to gl_periods if entities adopt different fiscal calendars).
"""

from education_system.post_18.university_system.infrastructure.database.db import get_connection


SCHEMA_STATEMENTS = [
    # Entities — institutions and any subsidiary trading companies
    """
    CREATE TABLE IF NOT EXISTS gl_entities (
        entity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_code TEXT    NOT NULL UNIQUE,
        entity_name TEXT    NOT NULL,
        is_active   INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # Chart of accounts. Hierarchical via parent_account_id.
    # account_type drives sign conventions in reports.
    """
    CREATE TABLE IF NOT EXISTS gl_accounts (
        account_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        account_code      TEXT    NOT NULL UNIQUE,
        account_name      TEXT    NOT NULL,
        account_type      TEXT    NOT NULL CHECK (account_type IN ('asset','liability','equity','revenue','expense')),
        parent_account_id INTEGER REFERENCES gl_accounts(account_id),
        is_active         INTEGER NOT NULL DEFAULT 1,
        created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gl_accounts_type ON gl_accounts(account_type)",

    # Periods. status: open -> closed -> locked.
    # 'closed' can be reopened by admin; 'locked' cannot.
    """
    CREATE TABLE IF NOT EXISTS gl_periods (
        period_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        fiscal_year INTEGER NOT NULL,
        period_no   INTEGER NOT NULL,
        start_date  TEXT    NOT NULL,
        end_date    TEXT    NOT NULL,
        status      TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','locked')),
        closed_at   TEXT,
        closed_by   TEXT,
        UNIQUE (fiscal_year, period_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gl_periods_dates ON gl_periods(start_date, end_date)",

    # Journal headers. UNIQUE(source_type, source_id) gives idempotent posting.
    """
    CREATE TABLE IF NOT EXISTS gl_journals (
        journal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id      INTEGER NOT NULL REFERENCES gl_entities(entity_id),
        journal_date   TEXT    NOT NULL,
        period_id      INTEGER NOT NULL REFERENCES gl_periods(period_id),
        description    TEXT    NOT NULL,
        source_type    TEXT    NOT NULL,
        source_id      INTEGER,
        posted_by      TEXT    NOT NULL,
        posted_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        reversed_by_id INTEGER REFERENCES gl_journals(journal_id),
        is_reversal_of INTEGER REFERENCES gl_journals(journal_id),
        UNIQUE (source_type, source_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gl_journals_period ON gl_journals(period_id)",
    "CREATE INDEX IF NOT EXISTS idx_gl_journals_entity_date ON gl_journals(entity_id, journal_date)",

    # Lines. Balanced-journal invariant (SUM debit = SUM credit) is enforced
    # at the posting service layer; the per-line CHECK enforces no mixed lines.
    """
    CREATE TABLE IF NOT EXISTS gl_journal_lines (
        line_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        journal_id INTEGER NOT NULL REFERENCES gl_journals(journal_id) ON DELETE CASCADE,
        account_id INTEGER NOT NULL REFERENCES gl_accounts(account_id),
        debit      DECIMAL(12,2) NOT NULL DEFAULT 0,
        credit     DECIMAL(12,2) NOT NULL DEFAULT 0,
        memo       TEXT,
        CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_gl_lines_journal ON gl_journal_lines(journal_id)",
    "CREATE INDEX IF NOT EXISTS idx_gl_lines_account ON gl_journal_lines(account_id)",
]


def init_ledger():
    """Create GL schema (if absent) and seed default entity, chart, and periods.

    Idempotent — safe to call repeatedly. Returns True on success.
    Also runs the VAT column migration for `payments` and `unified_refunds`,
    which is non-destructive (ALTER TABLE ADD COLUMN with default NULL).
    """
    conn = get_connection()
    cur = conn.cursor()
    for stmt in SCHEMA_STATEMENTS:
        cur.execute(stmt)
    conn.commit()

    # VAT migration on operational tables. Idempotent: only adds columns
    # that don't yet exist. Existing rows get NULL, which the posting
    # service treats as "use the default classification by source_type".
    _add_column_if_missing(cur, 'payments', 'vat_rate', 'TEXT')
    _add_column_if_missing(cur, 'payments', 'vat_amount', 'REAL')
    _add_column_if_missing(cur, 'unified_refunds', 'vat_rate', 'TEXT')
    _add_column_if_missing(cur, 'unified_refunds', 'vat_amount', 'REAL')
    conn.commit()

    # Seed in dependency order. Each helper is itself idempotent.
    from education_system.post_18.university_system.modules.domain.finance.ledger.seed import (
        seed_default_entity, seed_chart_of_accounts, seed_current_fiscal_year_periods,
    )
    seed_default_entity(conn)
    seed_chart_of_accounts(conn)
    seed_current_fiscal_year_periods(conn)
    conn.commit()
    conn.close()
    return True


def _add_column_if_missing(cursor, table, column, decl):
    """Idempotent ADD COLUMN — silently skips if `table` doesn't exist or
    `column` is already on it."""
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if not existing:
            return  # table doesn't exist — caller may not have seeded operational tables yet
        if column in existing:
            return
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    except Exception:
        # Pre-existing columns under a different declaration, locked tables,
        # or read-only DBs — never raise from migration.
        pass
