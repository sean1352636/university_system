"""university academic integrity, second step: integrity_cases becomes the
one case record (wider case types, source, module, tariff, response
deadline; old academic_misconduct_cases copied in), student statements,
case evidence, failed automatic checks, reminders, AI-detection reviews,
external-source searches, paraphrase / obfuscation scores, collaboration
and misconduct-penalty columns

Revision ID: d1f3a5c7e9b2
Revises: c0e2a4b6d8f1
Create Date: 2026-10-17 12:00:00.000000

See ``infrastructure/database/schemas/academic_integrity_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd1f3a5c7e9b2'
down_revision: Union[str, Sequence[str], None] = 'c0e2a4b6d8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("integrity_external_searches", "integrity_ai_reviews", "integrity_reminders",
           "integrity_check_failures", "integrity_evidence", "integrity_statements")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        academic_integrity_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The widened integrity_cases, its new columns and the copied cases stay.
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
