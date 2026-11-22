"""University chatbot: support cases (people asking for a human, crisis
alerts), staff roles, configurable contacts, the FAQ knowledge base,
unanswered questions, answer feedback, and conversation logs kept in the
database with a retention period.

``faqs`` and ``chatbot_conversations`` already exist; this adds the columns
the workflows need.

Shared by migration ``a8c0e2f4b6d9`` and :func:`apply_to_connection`
(``university/application/chatbot/``). Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    ("faqs", "status", "TEXT DEFAULT 'published'"),
    ("faqs", "updated_by", "TEXT"),
    ("faqs", "not_helpful_votes", "INTEGER DEFAULT 0"),
    ("faqs", "source", "TEXT"),
    ("chatbot_conversations", "crisis", "INTEGER DEFAULT 0"),
    ("chatbot_conversations", "case_id", "INTEGER"),
    ("chatbot_conversations", "faq_id", "INTEGER"),
    ("chatbot_conversations", "answered", "INTEGER DEFAULT 1"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS chatbot_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('agent', 'editor')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role)
    )""",
    """CREATE TABLE IF NOT EXISTS chatbot_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS chatbot_cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('human_help', 'crisis')),
        message TEXT NOT NULL,
        conversation_id INTEGER,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'answered',
                                                              'closed')),
        assigned_to TEXT,
        answer TEXT,
        answered_by TEXT,
        answered_at TEXT,
        safeguarding_case_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        closed_at TEXT,
        closed_by TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_chatbot_cases_status ON chatbot_cases (status, created_at)",
    """CREATE TABLE IF NOT EXISTS chatbot_unanswered (
        question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        normalised TEXT NOT NULL UNIQUE,
        times_asked INTEGER NOT NULL DEFAULT 1,
        first_asked_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_asked_at TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'answered', 'dismissed')),
        faq_id INTEGER,
        handled_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS chatbot_feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_row_id INTEGER NOT NULL,
        username TEXT,
        helpful INTEGER NOT NULL,
        comment TEXT,
        given_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (conversation_row_id, username)
    )""",
    """CREATE TABLE IF NOT EXISTS chatbot_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
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
