"""Database models and initialisation for GDPR data retention.

Creates three tables in the shared retention database:
  - retention_policies  — rules defining what to do with data after N days
  - retention_jobs      — audit trail of every policy execution
  - data_subject_requests — DSAR / erasure / portability request tracking

Also seeds a set of sensible default policies on first run.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

_RETENTION_DB: Path | None = None


def get_retention_db_path() -> Path:
    """Return the path to the shared retention database, creating dirs if needed."""
    if _RETENTION_DB is not None:
        return _RETENTION_DB
    shared_root = Path(__file__).resolve().parent.parent.parent.parent  # education_system/shared
    db_dir = shared_root / "data" / "db_files"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "retention.db"


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = str(db_path or get_retention_db_path())
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL_RETENTION_POLICIES = """
CREATE TABLE IF NOT EXISTS retention_policies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type   TEXT    NOT NULL,
    system_key    TEXT    NOT NULL DEFAULT 'all',
    retention_days INTEGER NOT NULL,
    action        TEXT    NOT NULL CHECK (action IN ('archive', 'anonymize', 'delete')),
    description   TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
)
"""

_DDL_RETENTION_JOBS = """
CREATE TABLE IF NOT EXISTS retention_jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id        INTEGER NOT NULL REFERENCES retention_policies(id),
    status           TEXT    NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at       TEXT,
    completed_at     TEXT,
    records_affected INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT
)
"""

_DDL_DATA_SUBJECT_REQUESTS = """
CREATE TABLE IF NOT EXISTS data_subject_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_email    TEXT    NOT NULL,
    subject_name     TEXT,
    request_type     TEXT    NOT NULL
                         CHECK (request_type IN ('access', 'erasure', 'rectification', 'portability')),
    status           TEXT    NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'in_progress', 'completed', 'rejected')),
    systems_affected TEXT,
    requested_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    completed_at     TEXT,
    processed_by     TEXT
)
"""

# ---------------------------------------------------------------------------
# Default policies
# ---------------------------------------------------------------------------

_DEFAULT_POLICIES = [
    {
        "entity_type": "graduated_students",
        "system_key": "all",
        "retention_days": 7 * 365,   # 7 years
        "action": "anonymize",
        "description": (
            "Anonymize personal details of graduated/left students after 7 years "
            "while preserving academic records for reference."
        ),
    },
    {
        "entity_type": "attendance_records",
        "system_key": "all",
        "retention_days": 3 * 365,   # 3 years
        "action": "archive",
        "description": (
            "Archive attendance records after 3 years. "
            "Aggregate statistics are retained."
        ),
    },
    {
        "entity_type": "chat_messages",
        "system_key": "university",
        "retention_days": 365,        # 1 year
        "action": "delete",
        "description": "Delete internal chat messages older than 1 year.",
    },
    {
        "entity_type": "session_data",
        "system_key": "all",
        "retention_days": 90,
        "action": "delete",
        "description": "Delete expired authentication sessions older than 90 days.",
    },
    {
        "entity_type": "audit_logs",
        "system_key": "all",
        "retention_days": 5 * 365,   # 5 years
        "action": "archive",
        "description": (
            "Archive audit / activity logs after 5 years for compliance purposes."
        ),
    },
    {
        "entity_type": "temporary_files",
        "system_key": "all",
        "retention_days": 30,
        "action": "delete",
        "description": "Delete temporary export / upload files older than 30 days.",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_retention_db(db_path: str | Path | None = None) -> None:
    """Create tables and seed default policies (idempotent)."""
    conn = _connect(db_path)
    try:
        conn.execute(_DDL_RETENTION_POLICIES)
        conn.execute(_DDL_RETENTION_JOBS)
        conn.execute(_DDL_DATA_SUBJECT_REQUESTS)
        conn.commit()

        # Seed defaults only if the table is empty
        existing = conn.execute(
            "SELECT COUNT(*) FROM retention_policies"
        ).fetchone()[0]
        if existing == 0:
            _seed_defaults(conn)

        logger.info("Retention DB initialised at %s", db_path or get_retention_db_path())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _seed_defaults(conn: sqlite3.Connection) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    for p in _DEFAULT_POLICIES:
        conn.execute(
            """
            INSERT INTO retention_policies
                (entity_type, system_key, retention_days, action, description,
                 is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                p["entity_type"],
                p["system_key"],
                p["retention_days"],
                p["action"],
                p["description"],
                now,
                now,
            ),
        )
    conn.commit()
    logger.info("Seeded %d default retention policies", len(_DEFAULT_POLICIES))
