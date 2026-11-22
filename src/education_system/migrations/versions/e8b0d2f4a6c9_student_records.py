"""student records: contact and entry details, field-level change history,
erasure requests

Revision ID: e8b0d2f4a6c9
Revises: d7a9c1e3f5b8
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/student_records_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e8b0d2f4a6c9'
down_revision: Union[str, Sequence[str], None] = 'd7a9c1e3f5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        student_records_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The new students columns are left in place (SQLite cannot drop them
    # without rebuilding a table that 190 foreign keys point at).
    op.execute('DROP INDEX IF EXISTS "ix_student_record_changes_student"')
    for table in ("student_erasure_requests", "student_record_changes"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
