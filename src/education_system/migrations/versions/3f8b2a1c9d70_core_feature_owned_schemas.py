"""Move core feature-owned schemas into Alembic.

Revision ID: 3f8b2a1c9d70
Revises: 0a7d9c3e5f21
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from education_system.migrations.feature_schema_sql import FEATURE_SCHEMAS

revision: str = "3f8b2a1c9d70"
down_revision: Union[str, Sequence[str], None] = "0a7d9c3e5f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for schema in FEATURE_SCHEMAS:
        for statement in schema.split(";"):
            if statement.strip():
                op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pgr_history")
    op.execute("DROP TABLE IF EXISTS pgr_milestones")
    op.execute("DROP TABLE IF EXISTS pgr_final_deposits")
    op.execute("DROP TABLE IF EXISTS pgr_corrections")
    op.execute("DROP TABLE IF EXISTS pgr_vivas")
    op.execute("DROP TABLE IF EXISTS pgr_examiners")
    op.execute("DROP TABLE IF EXISTS pgr_thesis_submissions")
    op.execute("DROP TABLE IF EXISTS pgr_upgrades")
    op.execute("DROP TABLE IF EXISTS pgr_approvals")
    op.execute("DROP TABLE IF EXISTS pgr_progress_reviews")
    op.execute("DROP TABLE IF EXISTS pgr_training_needs")
    op.execute("DROP TABLE IF EXISTS pgr_supervision_meetings")
    op.execute("DROP TABLE IF EXISTS pgr_supervision_team")
    op.execute("DROP TABLE IF EXISTS pgr_projects")
    op.execute("DROP TABLE IF EXISTS programme_governance_history")
    op.execute("DROP TABLE IF EXISTS student_regulation_assignments")
    op.execute("DROP TABLE IF EXISTS programme_teach_out_plans")
    op.execute("DROP TABLE IF EXISTS programme_accreditations")
    op.execute("DROP TABLE IF EXISTS programme_validations")
    op.execute("DROP TABLE IF EXISTS approval_committees")
    op.execute("DROP TABLE IF EXISTS programme_amendments")
    op.execute("DROP TABLE IF EXISTS programme_versions")
    op.execute("DROP TABLE IF EXISTS programme_business_cases")
    op.execute("DROP TABLE IF EXISTS programme_proposals")
    op.execute("DROP TABLE IF EXISTS governed_programmes")
    op.execute("DROP TABLE IF EXISTS assessment_board_corrections")
    op.execute("DROP TABLE IF EXISTS ratified_student_awards")
    op.execute("DROP TABLE IF EXISTS assessment_board_minutes")
    op.execute("DROP TABLE IF EXISTS assessment_board_decisions")
    op.execute("DROP TABLE IF EXISTS assessment_board_agenda")
    op.execute("DROP TABLE IF EXISTS assessment_board_rules")
    op.execute("DROP TABLE IF EXISTS assessment_board_members")
    op.execute("DROP TABLE IF EXISTS assessment_boards")
