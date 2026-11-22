"""university: student_modules is the one module-enrolment record;
module_enrolments follows it by trigger

Before (live, 2026-10-18): student_modules 198 rows, module_enrolments 132;
72 enrolments only in student_modules (none of their 4 students had a
programme registration, so nothing had ever been copied), 6 only in
module_enrolments, 6 statuses disagreeing.

The 6 module_enrolments-only rows (ids 7–12, CIS0001, CIS0002, CIS1003,
CIS1004, CIS3001, CIS3002, all 'enrolled', 'legacy' year, effective
2026-05-06) and programme registration 13 (programme DS, 'legacy') belong to
student 8940853, who no longer exists anywhere else in the database (a record
deleted before erasure was dual-control). They broke the foreign keys to
``students`` and are removed — no enrolment is invented for them.

module_enrolments stays a table because ``attendance_events`` has a foreign
key to it (a view cannot be one); triggers on student_modules keep it in step
(``infrastructure/database/schemas/enrolment_mirror_schema.py``).

Revision ID: 1a3c5e7f9b2d
Revises: e8a0c2d4f6b1
Create Date: 2026-10-18 10:00:00.000000

Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '1a3c5e7f9b2d'
down_revision: Union[str, Sequence[str], None] = 'e8a0c2d4f6b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRIGGERS = ("student_modules_mirror_insert", "student_modules_mirror_update",
             "student_modules_mirror_rekey", "student_modules_mirror_delete")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        enrolment_mirror_schema,
    )
    enrolment_mirror_schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # The reconciled rows stay (they match student_modules); only the
    # triggers go, so module_enrolments stops following.
    for name in _TRIGGERS:
        op.execute(f'DROP TRIGGER IF EXISTS "{name}"')
