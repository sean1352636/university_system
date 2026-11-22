"""student records: preferred name, address lines, town, postcode and notes on
students (add-form parity with the other systems)

Revision ID: c9e1a3b5d7f2
Revises: b8d0f2a4c6e8
Create Date: 2026-11-06 00:00:00.000000

See ``infrastructure/database/schemas/student_records_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c9e1a3b5d7f2'
down_revision: Union[str, Sequence[str], None] = 'b8d0f2a4c6e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        student_records_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The columns are left in place: SQLite cannot drop them without
    # rebuilding a table that ~190 foreign keys point at.
    pass
