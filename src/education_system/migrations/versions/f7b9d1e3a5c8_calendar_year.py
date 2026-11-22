"""academic calendar: years with draft/publish, terms, key dates, published
snapshots (for change notices), calendar roles and audit, personal feed
tokens, event reminders; source columns on academic_terms and holidays

Revision ID: f7b9d1e3a5c8
Revises: e6a8c0d2f4b7
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/calendar_year_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f7b9d1e3a5c8'
down_revision: Union[str, Sequence[str], None] = 'e6a8c0d2f4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "calendar_notification_preferences", "calendar_reminders", "calendar_feed_tokens", "calendar_audit", "calendar_roles",
    "calendar_published_snapshots", "calendar_key_dates", "calendar_terms", "calendar_years",
)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        calendar_year_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The source columns added to academic_terms / holidays stay in place, and so
    # does course_events: it predates this migration (created at run time) and
    # holds live rows, so downgrading must not drop it.
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
