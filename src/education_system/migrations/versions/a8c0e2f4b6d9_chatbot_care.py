"""university chatbot: support cases (human help, crisis alerts), staff
roles, contact settings, unanswered questions, answer feedback, audit;
FAQ status and conversation-log columns

Revision ID: a8c0e2f4b6d9
Revises: f7b9d1e3a5c8
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/chatbot_care_schema.py``. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a8c0e2f4b6d9'
down_revision: Union[str, Sequence[str], None] = 'f7b9d1e3a5c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("chatbot_audit", "chatbot_feedback", "chatbot_unanswered", "chatbot_cases",
           "chatbot_settings", "chatbot_roles")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        chatbot_care_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Columns added to faqs / chatbot_conversations stay in place.
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
