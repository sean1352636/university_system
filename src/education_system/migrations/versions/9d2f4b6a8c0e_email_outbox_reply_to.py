"""university e-mail: ``email_outbox.reply_to`` (the Reply-To header)

Support e-mails to a requester carry the support address as Reply-To when
e-mail into tickets is on, so a plain reply reaches the support mailbox.
See ``infrastructure/database/schemas/email_outbox_schema.py``
(``ADDED_COLUMNS``). Idempotent; the column is kept on downgrade (a
nullable column is harmless to older code).

Revision ID: 9d2f4b6a8c0e
Revises: 8c1e3a5f7b9d
Create Date: 2026-10-20 12:00:00.000000
"""
import logging
from typing import Sequence, Union

from alembic import op


revision: str = '9d2f4b6a8c0e'
down_revision: Union[str, Sequence[str], None] = '8c1e3a5f7b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        email_outbox_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    logger.info("email_outbox.reply_to kept on downgrade")
