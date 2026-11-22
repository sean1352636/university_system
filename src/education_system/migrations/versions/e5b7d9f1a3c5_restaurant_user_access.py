"""university: restaurant user access, and the restaurant audit log it writes to

``restaurant_user_access`` links a login to a ``restaurant_staff`` record and a
restaurant role. Removed access keeps its row, so the history stays.

``restaurant_audit_logs`` is the table the restaurant Audit Logs screen already
reads. It was only created when the command-line restaurant start-up ran, so
without it that screen fails and audit writes are silently lost.

Additive and idempotent.

Revision ID: e5b7d9f1a3c5
Revises: d4a6c8e0f2b4
Create Date: 2026-10-31 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5b7d9f1a3c5'
down_revision: Union[str, Sequence[str], None] = 'd4a6c8e0f2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS restaurant_user_access (
        access_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL COLLATE NOCASE UNIQUE,
        staff_id INTEGER REFERENCES restaurant_staff (staff_id) ON DELETE SET NULL,
        staff_name TEXT,
        role TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        granted_by TEXT,
        granted_at TEXT,
        removed_by TEXT,
        removed_at TEXT,
        removed_reason TEXT)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_restaurant_user_access_active_staff
        ON restaurant_user_access (staff_id) WHERE active = 1""",
    """CREATE TABLE IF NOT EXISTS restaurant_audit_logs (
        log_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        table_name TEXT,
        record_id TEXT,
        old_values TEXT,
        new_values TEXT,
        timestamp TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT)""",
)


def upgrade() -> None:
    bind = op.get_bind()
    for statement in STATEMENTS:
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    """Additive; left in place so no recorded data is lost."""
