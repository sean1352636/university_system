"""graduation: roles, audit, holds, certificate names, conferrals,
certificate print jobs, ceremony cohorts / invitations / named guests /
extra-ticket requests / attendance, transcript share consent, HEAR
achievements

Revision ID: d5f7a9b1c3e6
Revises: c4e6f8a0b2d5
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/graduation_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd5f7a9b1c3e6'
down_revision: Union[str, Sequence[str], None] = 'c4e6f8a0b2d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "hear_achievements", "ceremony_ticket_requests", "ceremony_guests", "ceremony_invitations",
    "ceremony_cohorts", "certificate_print_jobs", "graduation_conferrals", "certificate_names",
    "graduation_holds", "graduation_audit", "graduation_roles",
)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        graduation_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Columns added to the existing ceremony and record tables are left in place.
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
