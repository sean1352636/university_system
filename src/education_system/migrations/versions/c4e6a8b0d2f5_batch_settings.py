"""university batch operations settings: back up before imports, the
duplicate rule, job notifications, default column mappings and the history
window (batch_settings)

Revision ID: c4e6a8b0d2f5
Revises: b8d0f2a4c6e9
Create Date: 2026-10-17 21:00:00.000000

See ``infrastructure/database/schemas/batch_jobs_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4e6a8b0d2f5'
down_revision: Union[str, Sequence[str], None] = 'b8d0f2a4c6e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        batch_jobs_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "batch_settings"')
