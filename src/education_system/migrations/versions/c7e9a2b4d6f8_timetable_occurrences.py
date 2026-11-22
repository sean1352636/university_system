"""timetable: delivery, teaching weeks and online link on weekly slots;
one-off session changes

Revision ID: c7e9a2b4d6f8
Revises: b4d6f8a1c3e5
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/timetable_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c7e9a2b4d6f8'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a1c3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        timetable_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The added module_schedule columns stay: SQLite cannot drop a column
    # without rebuilding a table other tables point at.
    op.execute('DROP TABLE IF EXISTS "module_session_changes"')
