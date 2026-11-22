"""university academic integrity: checks tied to submissions, matched
sources with passages, result review, integrity case stages, appeals,
reviewer roles, settings, student notice acknowledgements, audit

Revision ID: c0e2a4b6d8f1
Revises: b9d1f3a5c7e0
Create Date: 2026-10-17 00:00:00.000000

See ``infrastructure/database/schemas/academic_integrity_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c0e2a4b6d8f1'
down_revision: Union[str, Sequence[str], None] = 'b9d1f3a5c7e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# course_integrity_settings predates this migration (created at runtime) and stays.
_TABLES = ("integrity_audit", "integrity_acknowledgements", "integrity_appeals",
           "integrity_case_events", "integrity_settings", "integrity_roles",
           "plagiarism_matches")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        academic_integrity_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Columns added to existing tables stay in place.
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
