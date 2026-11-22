"""research office: roles, audit, ethics review workflow, grant costing /
approvals / spend / reports, output authors and internal review, REF staff,
IP deadlines and inventor payments, declarations of interest, data
management plans

Revision ID: c4e6f8a0b2d5
Revises: b3d5f7a9c1e4
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/research_office_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4e6f8a0b2d5'
down_revision: Union[str, Sequence[str], None] = 'b3d5f7a9c1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "research_data_plans", "research_interest_declarations", "ip_inventor_payments",
    "ip_deadlines", "ref_staff_uoa", "research_output_reviews", "research_output_authors",
    "grant_reports", "grant_spend", "grant_cost_lines", "ethics_conditions",
    "ethics_reviewer_allocations", "research_audit", "research_office_roles",
)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        research_office_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Columns added to the existing research tables are left in place.
    op.execute('DROP INDEX IF EXISTS "ux_research_team_active"')
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
