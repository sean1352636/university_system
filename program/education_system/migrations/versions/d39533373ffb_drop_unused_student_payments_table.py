"""drop unused student_payments table

Revision ID: d39533373ffb
Revises: d1bde3fa4179
Create Date: 2026-05-05 20:06:46.309428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd39533373ffb'
down_revision: Union[str, Sequence[str], None] = 'd1bde3fa4179'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the unused ``student_payments`` table.

    8.117.102 audit found zero production writers anywhere in the
    runtime app — only a finance archive routine read from it (also
    removed) and a one-shot bootstrap script. The canonical payments
    ledger is the ``payments`` table.
    """
    op.execute("DROP TABLE IF EXISTS student_payments")


def downgrade() -> None:
    """Recreate the table for rollback parity. Empty — nothing
    populates it in either direction."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS student_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_id INTEGER,
            student_id TEXT NOT NULL,
            amount_paid REAL NOT NULL,
            payment_method TEXT,
            reference TEXT,
            payment_date TEXT DEFAULT (date('now'))
        )
    """)
