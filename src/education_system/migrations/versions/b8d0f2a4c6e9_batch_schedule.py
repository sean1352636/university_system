"""university batch operations: watched folders run daily at a set time,
scheduled batch reports by e-mail

Revision ID: b8d0f2a4c6e9
Revises: a7c9e1b3d5f2
Create Date: 2026-10-17 22:00:00.000000

See ``infrastructure/database/schemas/batch_jobs_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b8d0f2a4c6e9'
down_revision: Union[str, Sequence[str], None] = 'a7c9e1b3d5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        batch_jobs_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The added watched-folder columns stay.
    op.execute('DROP TABLE IF EXISTS "batch_report_schedules"')
