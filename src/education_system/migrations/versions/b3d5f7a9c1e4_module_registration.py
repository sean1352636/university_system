"""module registration: credit rules per course and year, optional module
choices awaiting approval; registration periods table

Revision ID: b3d5f7a9c1e4
Revises: a2c4e6f8b0d1
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/module_registration_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b3d5f7a9c1e4'
down_revision: Union[str, Sequence[str], None] = 'a2c4e6f8b0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        module_registration_schema as schema,
    )
    from education_system.systems.university.services.bus import registration_calendar
    execute = op.get_bind().exec_driver_sql
    schema.apply(execute)
    for ddl in registration_calendar._SCHEMA:     # periods + status changes
        execute(ddl)


def downgrade() -> None:
    # registration_periods / enrolment_status_changes belong to the
    # registration calendar and are left in place.
    op.execute('DROP INDEX IF EXISTS "ix_module_choice_submissions_student"')
    for table in ("module_choice_items", "module_choice_submissions", "programme_credit_rules"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
