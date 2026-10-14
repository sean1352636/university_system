"""The ``modules`` and ``student_modules`` tables, plus an enrolment-status repair.

Fourteen disagreeing definitions across 12 files, and two of the
disagreements had teeth:

* ``student_modules.status`` was declared ``DEFAULT 'Enrolled'`` in some
  definitions and ``DEFAULT 'enrolled'`` in others. 42 places in the tree
  filter on the exact string ``'Enrolled'`` — including
  ``student_lifecycle``, which pauses a student's modules on interruption
  with ``WHERE status = 'Enrolled'`` — so every row created under the
  lowercase default was invisible to all of them. Six rows on the
  established database are affected. This migration normalises them; the
  canonical default is ``'Enrolled'``.
* ``modules.instructor_id`` is read by ``dashboard_routes`` and the parent
  portal's grade view and was declared by no definition that ever ran, so
  both queries failed with ``no such column``. It is added here, nullable.

``modules`` keeps ``module_id`` as its primary key, as the established
table has it, with the unique index on ``module_code`` that every join in
the tree depends on.

Revision ID: c3e58a7b91f4
Revises: a91c47e2f8d3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3e58a7b91f4"
down_revision: Union[str, Sequence[str], None] = "a91c47e2f8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        modules_table as mt,
    )

    bind = op.get_bind()

    # The DDL lives with the module that owns these tables so the runtime
    # bootstrap and a migrated database cannot drift.
    op.execute(mt.create_modules_sql())
    op.execute(mt.create_student_modules_sql())

    for table, columns in (("modules", mt.MODULE_COLUMNS),
                           ("student_modules", mt.STUDENT_MODULE_COLUMNS)):
        existing = {
            row[1] for row in
            bind.execute(sa.text(f'PRAGMA table_info("{table}")'))
        }
        for name, decl in columns:
            if name in existing or "PRIMARY KEY" in decl.upper():
                continue
            op.execute(
                f'ALTER TABLE "{table}" ADD COLUMN "{name}" {mt._addable(decl)}')

    for statement in (*mt._MODULE_INDEXES, *mt._STUDENT_MODULE_INDEXES):
        op.execute(statement)
    for statement in mt._MODULE_UNIQUE_INDEXES:
        try:
            op.execute(statement)
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not enforce {statement}: {exc}")

    # Repair the mis-cased statuses. Done here rather than left to the
    # application because every reader assumes the canonical form, and a
    # row that no reader can see is not something a default can fix
    # retrospectively.
    for canonical in mt.ENROLMENT_STATUSES:
        result = bind.execute(
            sa.text("UPDATE student_modules SET status = :canonical "
                    "WHERE status IS NOT NULL AND status <> :canonical "
                    "  AND LOWER(status) = LOWER(:canonical)"),
            {"canonical": canonical},
        )
        if result.rowcount:
            print(f"normalised {result.rowcount} student_modules row(s) "
                  f"to status {canonical!r}")


def downgrade() -> None:
    # Not reversible. Re-lowercasing the repaired statuses would put the
    # rows back out of reach of every query that reads them, and dropping
    # instructor_id would re-break two live endpoints.
    pass
