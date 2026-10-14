"""normalise course status casing

Revision ID: d5f28a1b9e73
Revises: c7a3e91f4d20
Create Date: 2026-09-10 00:00:00.000000

The ``courses.status`` column held mixed casing: 'active' on most rows and
'Inactive' on others, while the status dialogs offered title-case
Active/Inactive/Archived/Cancelled. Student enrolment matches
``status='active'`` exactly, so a course saved as 'Active' silently became
invisible to enrolment, and two call sites had grown
``(status='Active' OR status='active')`` workarounds.

CourseLifecycleService now normalises every write to lower case and reads
compare case-insensitively. This migration brings the rows already on disk
into line so the data matches what the code writes from here on.

Lower case is the canonical form: enrolment already depended on it and it was
already the majority.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5f28a1b9e73'
down_revision: Union[str, Sequence[str], None] = 'c7a3e91f4d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: The canonical vocabulary, matching CourseLifecycleService.STATUSES.
_CANONICAL = ("active", "inactive", "archived", "cancelled")


def upgrade() -> None:
    conn = op.get_bind()
    if conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='courses'"
    ).fetchone() is None:
        return

    # Lower-case every recognised status, and trim stray whitespace. Rows
    # already lower case are untouched, so this is safe to re-run.
    conn.exec_driver_sql(
        "UPDATE courses "
        "   SET status = LOWER(TRIM(status)) "
        " WHERE status IS NOT NULL "
        "   AND status <> LOWER(TRIM(status))"
    )

    # A blank or NULL status meant 'active' everywhere it was read; make that
    # explicit rather than leaving it to each caller's COALESCE.
    conn.exec_driver_sql(
        "UPDATE courses SET status = 'active' "
        " WHERE status IS NULL OR TRIM(status) = ''"
    )

    # Anything outside the vocabulary is left alone and reported: inventing a
    # mapping for an unknown value would lose information silently.
    placeholders = ", ".join(f"'{value}'" for value in _CANONICAL)
    stray = conn.exec_driver_sql(
        f"SELECT DISTINCT status FROM courses WHERE status NOT IN ({placeholders})"  # nosec B608
    ).fetchall()
    if stray:
        print("  note: course statuses outside the canonical vocabulary were "
              "left unchanged: " + ", ".join(repr(row[0]) for row in stray))


def downgrade() -> None:
    # Casing carried no information, so there is nothing to restore: the
    # pre-migration mixture cannot be reconstructed and re-introducing it
    # would only bring back the enrolment bug.
    pass
