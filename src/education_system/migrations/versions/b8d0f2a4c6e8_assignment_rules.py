"""university: assignment settings that were on the form but never saved, plus
withdrawal, declarations, marker allocation and rubric scores by criterion

Purely additive. Assignments already visible count as announced, so nobody is
told about them again. Everything else about existing assignments stays as it
was: no attempt or late-day limit, automatic checks on.

Revision ID: b8d0f2a4c6e8
Revises: a7c9e1b3d5f7
Create Date: 2026-11-01 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import (
    schema,
)

revision: str = 'b8d0f2a4c6e8'
down_revision: Union[str, Sequence[str], None] = 'a7c9e1b3d5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def columns(table):
        if not inspector.has_table(table):
            return set()
        return {c["name"] for c in sa.inspect(bind).get_columns(table)}

    schema.apply(op.execute, columns)


def downgrade() -> None:
    for table in ("submission_rubric_scores", "assignment_marker_allocations",
                  "assignment_reminders_sent"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
