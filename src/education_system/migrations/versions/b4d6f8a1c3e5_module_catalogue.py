"""module catalogue: specification, change control, designations, exclusions,
waitlist, teaching team, external examiners

Revision ID: b4d6f8a1c3e5
Revises: e9b2d4f6a8c1
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/module_catalogue_schema.py`` for why
each table exists and which look-alike tables it deliberately does not reuse.
Adds ``modules.level`` (FHEQ level). Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b4d6f8a1c3e5'
down_revision: Union[str, Sequence[str], None] = 'e9b2d4f6a8c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = (
    "module_external_examiners", "module_staff", "module_waitlist", "module_exclusions",
    "module_programme_designations", "module_change_history", "module_change_requests",
    "module_assessment_plan", "module_specifications",
)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        module_catalogue_schema as schema,
    )
    bind = op.get_bind()
    schema.apply(bind.exec_driver_sql)


def downgrade() -> None:
    # modules.level is left in place: SQLite cannot drop a column without a
    # table rebuild, and an unused nullable column is harmless.
    for table in _NEW_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
