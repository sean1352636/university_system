"""assignment assessment QA: anonymity, moderation, release, reassessment

Revision ID: e4b81c6d2a57
Revises: d5f28a1b9e73
Create Date: 2026-10-16 00:00:00.000000

Adds the columns and tables behind ``AssessmentQAService``: candidate
numbers for anonymous marking, moderation samples, non-submission records,
referral/deferral sittings, word limits, feedback and release dates, and the
formative/summative flag. The DDL lives in ``assessment_qa/schema.py`` so this
migration and the runtime bootstrap cannot drift.

Backfill: until now a mark was visible to the student the moment it was
saved. Grades are now hidden until the assignment is released, so every
assignment that already has a marked submission is stamped as released (at
its latest marking time). Without that, marks students have already seen
would disappear from their view. Later marks on those assignments keep
appearing immediately, as they always did.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e4b81c6d2a57'
down_revision: Union[str, Sequence[str], None] = 'd5f28a1b9e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
        schema,
    )

    bind = op.get_bind()

    def columns(table):
        return {row[1] for row in bind.exec_driver_sql(f'PRAGMA table_info("{table}")')}

    if not columns("assignments") or not columns("assignment_submissions"):
        # The assignment bootstrap has not run on this database yet; it
        # applies the same schema when it does.
        return

    already_migrated = "grades_released_at" in columns("assignments")
    schema.apply(bind.exec_driver_sql, columns)

    if not already_migrated:
        # graded_at only exists on databases that grew it; graded_date and
        # submission_date are on every definition.
        when = [c for c in ("graded_date", "graded_at", "submission_date")
                if c in columns("assignment_submissions")]
        stamp = "COALESCE(" + ", ".join(f"s.{c}" for c in when) + ")" if len(when) > 1 else f"s.{when[0]}"
        bind.exec_driver_sql(
            "UPDATE assignments "
            "   SET grades_released_at = COALESCE("
            f"           (SELECT MAX({stamp}) "
            "              FROM assignment_submissions s "
            "             WHERE s.assignment_id = assignments.id AND s.grade IS NOT NULL), "
            "           datetime('now')), "
            "       grades_released_by = 'migration: marked before release control' "
            " WHERE grades_released_at IS NULL "
            "   AND EXISTS (SELECT 1 FROM assignment_submissions s "
            "                WHERE s.assignment_id = assignments.id AND s.grade IS NOT NULL)"
        )


def downgrade() -> None:
    # Additive only; the columns and tables are harmless to older code.
    pass
