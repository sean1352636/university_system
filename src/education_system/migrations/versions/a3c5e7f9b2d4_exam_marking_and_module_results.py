"""exam marking control, combined module results and board locks

Revision ID: a3c5e7f9b2d4
Revises: f7d2a9c4e1b6
Create Date: 2026-10-16 00:00:00.000000

Adds the schema in ``infrastructure/database/schemas/grade_results_schema.py``:
exam anonymity, absence codes, moderation, release, resits, the grade change
log, module-result standing (provisional/confirmed, outcome, credits) and the
triggers that refuse changes to first-sit marks once an exam board has
ratified the module result.

Two backfills, both one-off:

* Exam and test marks were visible to students the moment they were entered.
  They are now hidden until the assessment is released, so every assessment
  that already has marks is stamped as released — students keep seeing what
  they have already seen.
* ``module_grades`` held results from two calculations that each saw only half
  the work (exams or assignments). Every existing result, and every student
  with a recorded mark, is recalculated with the single combined rule in
  ``application/module_results.py``. ``final_grade`` becomes the UK band
  (First, 2:1, 2:2, Third, Fail) instead of a US letter.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a3c5e7f9b2d4'
down_revision: Union[str, Sequence[str], None] = 'f7d2a9c4e1b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _students_with_results(raw):
    pairs = set()
    queries = (
        "SELECT student_id, module_code FROM module_grades",
        "SELECT g.student_id, a.module_code FROM grades g "
        "JOIN assessments a ON a.assessment_id = g.assessment_id",
        "SELECT s.student_id, a.module_code FROM assignment_submissions s "
        "JOIN assignments a ON a.id = s.assignment_id WHERE s.grade IS NOT NULL",
    )
    for sql in queries:
        pairs.update((str(r[0]), r[1]) for r in raw.execute(sql) if r[0] and r[1])
    return sorted(pairs)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        grade_results_schema as schema,
    )

    bind = op.get_bind()

    def columns(table):
        return {r[1] for r in bind.exec_driver_sql(f'PRAGMA table_info("{table}")')}

    already = "marks_released_at" in columns("assessments")
    if not schema.apply(bind.exec_driver_sql, columns):
        # The grade tables have not been created on this database yet; the
        # runtime bootstraps apply the same schema when they are.
        return
    if already:
        return

    bind.exec_driver_sql(
        "UPDATE assessments SET marks_released_at = datetime('now'), "
        "marks_released_by = 'migration: marked before release control' "
        "WHERE marks_released_at IS NULL "
        "AND EXISTS (SELECT 1 FROM grades g WHERE g.assessment_id = assessments.assessment_id)")
    bind.exec_driver_sql(
        "UPDATE grades SET released_at = datetime('now') WHERE released_at IS NULL "
        "AND assessment_id IN (SELECT assessment_id FROM assessments "
        "                      WHERE marks_released_at IS NOT NULL)")

    from education_system.systems.university.application.assessment import module_results

    # The application rules speak sqlite3; this is the same connection and
    # transaction alembic is using.
    raw = bind.connection.driver_connection
    for student_id, module_code in _students_with_results(raw):
        module_results.recompute(raw, student_id, module_code)


def downgrade() -> None:
    # Additive; older code ignores the new columns. Drop the lock triggers so
    # an older build can still edit marks.
    for name in ("grades_board_lock_insert", "grades_board_lock_update", "grades_board_lock_delete",
                 "submissions_board_lock_update", "submissions_board_lock_delete"):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
