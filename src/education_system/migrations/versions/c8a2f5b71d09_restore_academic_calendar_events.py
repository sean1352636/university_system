"""restore the missing academic_calendar_events table

Revision ID: c8a2f5b71d09
Revises: c3e58a7b91f4
Create Date: 2026-08-26 17:35:00.000000

``academic_calendar_events`` is the canonical calendar table created by the
baseline migration and kept by f1a2b3c4d5e6 (which folded four duplicate
calendar tables into it). It is absent from the live database, so every
Academic Calendar write fails with::

    no such table: main.academic_calendar_events

Its satellite tables all survived — ``event_categories`` (4 rows),
``event_templates`` (1), ``event_dependencies``, ``event_sequences``,
``event_timezones``, ``event_tag_assignments`` — which is consistent with
the parent being lost during the 2026-08-20 rebuild rather than dropped on
purpose. None of the survivors carries a foreign key to it in the live
database, so recreating it cannot conflict with existing rows.

The DDL is copied verbatim from 877b10b0175b_baseline, including the
superset columns that f1a2b3c4d5e6's fold added.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8a2f5b71d09'
down_revision: Union[str, Sequence[str], None] = 'c3e58a7b91f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DDL = """
CREATE TABLE IF NOT EXISTS "academic_calendar_events" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date TEXT,
    date_start TEXT,
    date_end TEXT,
    description TEXT,
    event_type TEXT DEFAULT 'Academic',
    date_added TEXT NOT NULL,
    last_modified TEXT,
    created_by TEXT,
    start_time TEXT,
    end_time TEXT,
    location TEXT,
    audience TEXT,
    assignment_id INTEGER,
    trip_id INTEGER,
    organizer TEXT,
    participants TEXT,
    status TEXT,
    country_code TEXT,
    region TEXT,
    is_active BOOLEAN DEFAULT 1,
    CONSTRAINT valid_event_dates CHECK (
        date_start IS NULL OR date_end IS NULL OR date_start <= date_end
    )
)
"""


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='academic_calendar_events'"
        )
    ).fetchone()
    if exists:
        return
    op.execute(_DDL)
    # The calendar filters heavily by date and by type.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_acad_cal_events_date "
        'ON "academic_calendar_events"(date)'
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_acad_cal_events_type "
        'ON "academic_calendar_events"(event_type)'
    )


def downgrade() -> None:
    # Deliberately not dropped: this migration restores a table the schema
    # has always been expected to have, and dropping it would reintroduce
    # the failure it fixes.
    pass
