"""exam operations: timetable publication, results link, invigilation, incidents, papers

Revision ID: c6e8a1d3f5b7
Revises: a3c5e7f9b2d4
Create Date: 2026-10-16 00:00:00.000000

Adds ``infrastructure/database/schemas/exam_operations_schema.py``: the
``exams`` → ``assessments`` link that routes exam results through the marking
rules, draft/published timetable status, invigilator allocation, exam-room
incidents and the exam paper workflow.

Existing exams are left ``published`` (students have already been told about
them). No results are moved: earlier exam results were written to
``student_grades``, which keeps them for transcripts; they are re-entered in
the Results tab when an exam is next marked.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c6e8a1d3f5b7'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7f9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        exam_operations_schema as schema,
    )

    bind = op.get_bind()

    def columns(table):
        return {r[1] for r in bind.exec_driver_sql(f'PRAGMA table_info("{table}")')}

    # Returns False when the exams table has not been created yet; the exam
    # scheduler's bootstrap applies the same schema when it is.
    schema.apply(bind.exec_driver_sql, columns)


def downgrade() -> None:
    # Additive only.
    pass
