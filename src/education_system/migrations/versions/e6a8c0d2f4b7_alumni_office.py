"""alumni office: roles, audit, contact consent and suppression, data
requests, Gift Aid declarations and claims, pledges, newsletter deliveries
and unsubscribe tokens, mentor vetting, mentoring concerns, content reports;
one chapter-membership table and one donations table

Revision ID: e6a8c0d2f4b7
Revises: d5f7a9b1c3e6
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/alumni_office_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e6a8c0d2f4b7'
down_revision: Union[str, Sequence[str], None] = 'd5f7a9b1c3e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "alumni_connections", "alumni_content_reports", "mentoring_concerns", "mentor_vetting", "donation_pledges",
    "gift_aid_claims", "gift_aid_declarations", "newsletter_deliveries",
    "alumni_unsubscribe_tokens", "alumni_data_requests", "alumni_audit", "alumni_roles",
)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        alumni_office_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Added columns and copied rows stay where they are.
    op.execute('DROP INDEX IF EXISTS "ux_chapter_memberships"')
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
