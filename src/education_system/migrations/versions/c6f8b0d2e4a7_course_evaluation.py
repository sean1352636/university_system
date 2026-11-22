"""course evaluation: one survey per course and year, course team,
invitations, comment screening, course leader response; replace stored
student ids with random tokens

Revision ID: c6f8b0d2e4a7
Revises: b5e7a9c1d3f6
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/course_evaluation_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c6f8b0d2e4a7'
down_revision: Union[str, Sequence[str], None] = 'b5e7a9c1d3f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        course_evaluation_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The anonymised tokens are not reverted: storing student ids was the flaw.
    op.execute('DROP INDEX IF EXISTS "ux_course_team_leader"')
    for table in ("course_eval_responses_to_students", "course_eval_comment_reviews",
                  "course_eval_invitations", "course_team"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
