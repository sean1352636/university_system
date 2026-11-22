"""student search: per-user saved searches, search/export/bulk/report audit,
scheduled reports

Revision ID: f9c1e3a5b7d0
Revises: e8b0d2f4a6c9
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/student_search_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f9c1e3a5b7d0'
down_revision: Union[str, Sequence[str], None] = 'e8b0d2f4a6c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        student_search_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_student_search_audit_at"')
    for table in ("student_report_schedules", "student_search_audit",
                  "student_saved_searches"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
