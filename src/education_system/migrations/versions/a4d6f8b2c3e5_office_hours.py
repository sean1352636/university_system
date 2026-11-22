"""office hours: appointment slots, booking rules, online sessions, one-off
cancellations, waitlist, meeting records, reminders, directory link

Revision ID: a4d6f8b2c3e5
Revises: f3c5e7a9b1d2
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/office_hours_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a4d6f8b2c3e5'
down_revision: Union[str, Sequence[str], None] = 'f3c5e7a9b1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        office_hours_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Added columns stay (SQLite cannot drop them without a rebuild).
    op.execute('DROP TABLE IF EXISTS "office_hour_waitlist"')
    op.execute('DROP TABLE IF EXISTS "office_hour_exceptions"')
