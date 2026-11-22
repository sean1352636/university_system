"""module evaluation: survey window, question sources and per-lecturer
questions, invitations, comment screening, module leader response;
replace reversible student hashes with random tokens

Revision ID: b5e7a9c1d3f6
Revises: a4d6f8b2c3e5
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/module_evaluation_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b5e7a9c1d3f6'
down_revision: Union[str, Sequence[str], None] = 'a4d6f8b2c3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        module_evaluation_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The anonymised tokens are not reverted: the old hashes were the flaw.
    for table in ("eval_form_responses_to_students", "eval_form_comment_reviews",
                  "eval_form_invitations"):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
