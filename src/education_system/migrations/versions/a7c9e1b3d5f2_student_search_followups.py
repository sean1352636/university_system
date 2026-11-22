"""university student search: favourite students, follow-ups and
duplicate-pair decisions

Revision ID: a7c9e1b3d5f2
Revises: f3b5d7f9a1c4
Create Date: 2026-10-17 21:00:00.000000

See ``infrastructure/database/schemas/student_search_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c9e1b3d5f2'
down_revision: Union[str, Sequence[str], None] = 'f3b5d7f9a1c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        student_search_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    for table in ("student_duplicate_reviews", "student_followups", "student_search_favourites"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
