"""helpdesk: SLA pause, links, time, followers, incidents, e-mail in

``student_support/schema.apply`` — the one support ticket DDL — now also
carries:

1. ``support_tickets.sla_paused_at`` / ``sla_paused_hours``: the resolution
   clock stops while a ticket waits on the student. Tickets already waiting
   start their pause at the first pass of the support jobs (``sla.sync_all_pauses``);
   time waited before this migration is not credited.
2. ``ticket_links`` and ``ticket_time_tracking`` (the Helpdesk's tables, now
   created here too; ``ticket_time_tracking.username`` added).
3. ``support_ticket_followers`` — staff following a ticket.
4. ``support_incidents`` and ``support_tickets.incident_id`` — major incidents.
5. ``support_inbound_mail`` — the log of e-mail read into tickets.
6. ``helpdesk_system_settings`` (if missing) — where the automation
   settings live; defaults apply until an administrator changes them
   (auto-close after 7 days, SLA pause on, e-mail in off).

Idempotent; nothing is dropped on downgrade (new tables and nullable
columns are harmless to older code).

Revision ID: 8c1e3a5f7b9d
Revises: 5d7f9b1c3e8a
Create Date: 2026-10-19 21:00:00.000000
"""
import logging
from typing import Sequence, Union

from alembic import op


revision: str = '8c1e3a5f7b9d'
down_revision: Union[str, Sequence[str], None] = '5d7f9b1c3e8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
        settings,
    )
    execute = op.get_bind().exec_driver_sql
    schema.apply(execute)
    execute(settings.TABLE_SQL)


def downgrade() -> None:
    logger.info("helpdesk collaboration tables and columns kept on downgrade")
