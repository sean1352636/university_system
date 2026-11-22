"""university: column types that disagree with what they reference

``student_id`` declared INTEGER in 32 tables though ``students.student_id``
is TEXT, foreign keys whose column type differs from the referenced column
(course, parent, parking, attendance-session, workflow, restaurant, shop and
grocery ids), and ``unified_events.source_event_id``, declared INTEGER but
holding text keys only (it becomes TEXT, matching the eleven columns that
reference it). Tables are rebuilt with their rows, indexes, triggers and
AUTOINCREMENT counters kept; a column whose values can't be converted is
left and reported in the log. See
``infrastructure/database/schemas/column_types.py``.

Revision ID: 5e7a9c1d3f6b
Revises: 4d6f8b0c2e5a
Create Date: 2026-10-18 12:00:00.000000

Idempotent.
"""
import logging
from typing import Sequence, Union

from alembic import op


revision: str = '5e7a9c1d3f6b'
down_revision: Union[str, Sequence[str], None] = '4d6f8b0c2e5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        column_types,
    )
    for report in column_types.apply(op.get_bind().exec_driver_sql):
        if report["changed"]:
            logger.info("Retyped %s.%s (%s rows)", report["table"],
                        ", ".join(report["changed"]), report["rows"])
        for column, reason in report["skipped"]:
            if column != "*":
                logger.warning("Left %s.%s as it is: %s", report["table"], column, reason)


def downgrade() -> None:
    # The old types were wrong (they did not match the columns they reference);
    # there is nothing useful to restore.
    pass
