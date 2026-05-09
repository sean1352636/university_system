"""link visa_engagement_checks to ukvi_engagement_events

Revision ID: d6e34a915fb0
Revises: c5d83e1f97a2
Create Date: 2026-05-09 12:00:00.000000

Adds ``source_event_id`` to ``visa_engagement_checks`` so engagement
rows imported from the attendance pipeline's ``ukvi_engagement_events``
table can be deduplicated by source. NULL for rows entered via the
visa GUI itself.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd6e34a915fb0'
down_revision: Union[str, Sequence[str], None] = 'c5d83e1f97a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {r[0] for r in bind.execute(
        sa.text("SELECT name FROM pragma_table_info('visa_engagement_checks')")
    ).fetchall()}
    if "source_event_id" not in cols:
        op.execute("ALTER TABLE visa_engagement_checks ADD COLUMN source_event_id INTEGER")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_visa_engage_source "
        "ON visa_engagement_checks(source_event_id) "
        "WHERE source_event_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uniq_visa_engage_source")
    # Column drop omitted — SQLite ALTER DROP COLUMN requires table rewrite
    # and the column is harmless to leave in place.
