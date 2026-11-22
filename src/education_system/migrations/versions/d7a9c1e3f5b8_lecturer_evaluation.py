"""lecturer evaluation: per module survey and lecturer, anonymous tokens,
invitations, comment screening, lecturer reflections; link instructors to
staff records

Revision ID: d7a9c1e3f5b8
Revises: c6f8b0d2e4a7
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/lecturer_evaluation_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd7a9c1e3f5b8'
down_revision: Union[str, Sequence[str], None] = 'c6f8b0d2e4a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        lecturer_evaluation_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The old instructor-id table is not recreated: it stored student ids and
    # its insert never worked. instructors.staff_id is left in place.
    for table in ("lecturer_reflections", "lecturer_eval_comment_reviews",
                  "lecturer_eval_invitations"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
    op.execute('DROP INDEX IF EXISTS "ix_lecturer_evaluations_lecturer"')
    op.execute('DROP TABLE IF EXISTS "lecturer_evaluations"')
