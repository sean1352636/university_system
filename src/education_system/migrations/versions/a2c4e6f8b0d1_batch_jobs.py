"""batch operations: jobs with per-row results and undo data, saved import
mappings, watched folders

Revision ID: a2c4e6f8b0d1
Revises: f9c1e3a5b7d0
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/batch_jobs_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a2c4e6f8b0d1'
down_revision: Union[str, Sequence[str], None] = 'f9c1e3a5b7d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        batch_jobs_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_batch_job_rows_job"')
    for table in ("batch_watch_folders", "batch_import_mappings", "batch_job_rows", "batch_jobs"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
