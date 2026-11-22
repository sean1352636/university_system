"""university: repoint stored file paths left under the old tree

Rows written before the repository moved out of the home directory
(2026-08-09) still hold absolute paths under
``~/education_system/post_18/university_system/…``; the files now live under
``var/``. Each path is rewritten only when the file really exists at its new
home (``infrastructure/stored_files.resolve``); missing files are left as
they are, so screens keep reporting them missing.

Revision ID: e8a0c2d4f6b1
Revises: c4e6a8b0d2f5
Create Date: 2026-10-17 22:00:00.000000

Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e8a0c2d4f6b1'
down_revision: Union[str, Sequence[str], None] = 'c4e6a8b0d2f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (("assignment_submissions", "id", "file_path"),
            ("backups", "id", "backup_path"))
_OLD = "%/education_system/post_18/%"


def upgrade() -> None:
    from education_system.systems.university.infrastructure.stored_files import resolve
    execute = op.get_bind().exec_driver_sql
    for table, key, column in _COLUMNS:
        if not execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                       (table,)).fetchone():
            continue
        columns = {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}
        if not {key, column} <= columns:
            continue
        rows = execute(f'SELECT "{key}", "{column}" FROM "{table}" '  # nosec B608
                       f'WHERE "{column}" LIKE ?', (_OLD,)).fetchall()
        for row_id, stored in rows:
            current = resolve(stored)
            if str(current) != str(stored) and current.exists():
                execute(f'UPDATE "{table}" SET "{column}" = ? WHERE "{key}" = ?',  # nosec B608
                        (str(current), row_id))


def downgrade() -> None:
    # The old tree no longer exists; there is nothing to point back to.
    pass
