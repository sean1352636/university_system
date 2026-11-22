"""university AI-writing indicators: the detector tables keep real ids
(assignment submission, student number, module, assignment), the method,
level and checker; students' comments on a result

Revision ID: e2a4c6e8f0b3
Revises: d1f3a5c7e9b2
Create Date: 2026-10-17 18:00:00.000000

See ``infrastructure/database/schemas/academic_integrity_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e2a4c6e8f0b3'
down_revision: Union[str, Sequence[str], None] = 'd1f3a5c7e9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        academic_integrity_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The detector tables and their added columns stay; they predate this.
    op.execute('DROP TABLE IF EXISTS "ai_result_comments"')
