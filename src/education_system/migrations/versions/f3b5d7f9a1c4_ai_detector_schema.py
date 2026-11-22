"""university AI content detector: its alerts, persisted audit chain, model
versions, federated updates and analytics tables, declared once instead of
created at runtime by the detector

Revision ID: f3b5d7f9a1c4
Revises: e2a4c6e8f0b3
Create Date: 2026-10-17 20:00:00.000000

See ``infrastructure/database/schemas/ai_detector_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f3b5d7f9a1c4'
down_revision: Union[str, Sequence[str], None] = 'e2a4c6e8f0b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        academic_integrity_schema, ai_detector_schema,
    )
    academic_integrity_schema.apply(op.get_bind().exec_driver_sql)
    ai_detector_schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The detector's tables hold audit history and models; they stay.
    pass
