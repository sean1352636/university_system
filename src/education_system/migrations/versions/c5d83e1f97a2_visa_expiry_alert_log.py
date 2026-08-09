"""visa expiry alert log

Revision ID: c5d83e1f97a2
Revises: b7f2c1d83e44
Create Date: 2026-05-09 11:00:00.000000

Adds the dedup log used by the scheduled visa-expiry alerts so the
07:00 daily run doesn't re-email the same student at the same threshold.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c5d83e1f97a2'
down_revision: Union[str, Sequence[str], None] = 'b7f2c1d83e44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS visa_expiry_alert_log (
            student_id      TEXT    NOT NULL,
            threshold_days  INTEGER NOT NULL,
            sent_at         TEXT    NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (student_id, threshold_days)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS visa_expiry_alert_log")
