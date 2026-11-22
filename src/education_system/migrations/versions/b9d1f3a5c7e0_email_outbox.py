"""university e-mail: one outbox with delivery attempts, suppressions and
unsubscribe tokens, sender roles, bulk sends, audit, settings; e-mail
preferences moved out of the runtime bus schema

Revision ID: b9d1f3a5c7e0
Revises: a8c0e2f4b6d9
Create Date: 2026-10-17 00:00:00.000000

See ``infrastructure/database/schemas/email_outbox_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b9d1f3a5c7e0'
down_revision: Union[str, Sequence[str], None] = 'a8c0e2f4b6d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# email_preferences predates this migration (created at runtime) and stays.
_TABLES = ("email_settings", "email_audit", "email_bulk_sends", "email_roles",
           "email_unsubscribe_tokens", "email_suppressions", "email_attempts", "email_outbox")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        email_outbox_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
