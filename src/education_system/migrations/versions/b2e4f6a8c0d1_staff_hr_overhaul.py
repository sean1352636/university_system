"""staff HR: HR roles + audit, staff-only discipline, one staff identity,
leave/absence, pay structure, hiring checks, compliance

Applies every Staff HR schema module listed in
``domains/staff/infrastructure/database/staff_hr_ddl.MODULES`` with its
data changes:

* ``staff_hr_access_schema`` — ``staff_hr_roles``, ``staff_hr_audit`` and
  ``staff_disciplinary_*``; person columns holding a numeric ``users.id``
  become the username; ``staff_profiles.manager_id`` employee numbers become
  usernames; staff cases leave the student ``disciplinary_records``.
* ``staff_hr_absence_schema``, ``staff_hr_pay_schema``,
  ``staff_hr_hiring_schema``, ``staff_hr_compliance_schema`` — see each.

Idempotent; nothing is dropped on downgrade.

Revision ID: b2e4f6a8c0d1
Revises: 9d2f4b6a8c0e
Create Date: 2026-10-20 15:00:00.000000
"""
import logging
from typing import Sequence, Union

from alembic import op


revision: str = 'b2e4f6a8c0d1'
down_revision: Union[str, Sequence[str], None] = '9d2f4b6a8c0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_ddl,
    )
    staff_hr_ddl.apply(op.get_bind().exec_driver_sql, data=True)


def downgrade() -> None:
    logger.info("Staff HR tables, columns and data changes kept on downgrade")
