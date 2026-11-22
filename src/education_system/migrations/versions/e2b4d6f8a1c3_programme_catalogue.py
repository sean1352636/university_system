"""programme record: specification, exit awards, intake targets, programme
external examiners, outcome-to-module map, survey results

Revision ID: e2b4d6f8a1c3
Revises: c7e9a2b4d6f8
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/programme_catalogue_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e2b4d6f8a1c3'
down_revision: Union[str, Sequence[str], None] = 'c7e9a2b4d6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("course_survey_results", "course_outcome_modules", "course_external_examiners",
           "course_intake_targets", "course_exit_awards", "course_specifications")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        programme_catalogue_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
