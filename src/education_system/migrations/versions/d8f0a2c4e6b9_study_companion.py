"""AI study companion: plan lifecycle, task status, SM-2 flashcards, review
history, explanation source, reminder settings and log

Revision ID: d8f0a2c4e6b9
Revises: a0d2f4b6c8e1
Create Date: 2026-10-18 00:00:00.000000

See ``infrastructure/database/schemas/study_companion_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd8f0a2c4e6b9'
down_revision: Union[str, Sequence[str], None] = 'a0d2f4b6c8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        study_companion_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Added columns and the four base tables stay (SQLite cannot drop columns
    # without a rebuild, and the base tables predate this revision).
    op.execute('DROP TABLE IF EXISTS "study_companion_reminders"')
    op.execute('DROP TABLE IF EXISTS "study_companion_settings"')
    op.execute('DROP TABLE IF EXISTS "flashcard_reviews"')
