"""Add the university source-transaction event outbox.

Revision ID: 7c2e4a9b1d63
Revises: 3f8b2a1c9d70
"""

from typing import Sequence, Union

from alembic import op

revision: str = "7c2e4a9b1d63"
down_revision: Union[str, Sequence[str], None] = "3f8b2a1c9d70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE university_event_outbox (
            event_id TEXT PRIMARY KEY,
            event_name TEXT NOT NULL,
            event_version INTEGER NOT NULL CHECK (event_version > 0),
            aggregate_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            causation_id TEXT,
            idempotency_key TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            available_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            delivered_at TEXT,
            dead_lettered_at TEXT,
            last_error TEXT
        )
    """)
    op.execute(
        "CREATE INDEX ix_university_outbox_pending "
        "ON university_event_outbox(delivered_at, dead_lettered_at, available_at)"
    )
    op.execute("""
        CREATE TABLE university_legal_holds (
            hold_id TEXT PRIMARY KEY,
            record_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            placed_by TEXT NOT NULL,
            placed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            released_by TEXT,
            released_at TEXT,
            UNIQUE(record_type, record_id, hold_id)
        )
    """)
    op.execute("""
        CREATE TABLE university_disposition_log (
            disposition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('delete', 'redact', 'archive')),
            actor_id TEXT NOT NULL,
            disposed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS university_disposition_log")
    op.execute("DROP TABLE IF EXISTS university_legal_holds")
    op.execute("DROP INDEX IF EXISTS ix_university_outbox_pending")
    op.execute("DROP TABLE IF EXISTS university_event_outbox")
