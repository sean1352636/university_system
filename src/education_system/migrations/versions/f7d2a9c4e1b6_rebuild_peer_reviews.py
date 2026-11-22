"""rebuild peer_reviews so student reviews can be allocated

Revision ID: f7d2a9c4e1b6
Revises: e4b81c6d2a57
Create Date: 2026-10-16 00:00:00.000000

The established ``peer_reviews`` table came from ``attendance_warning_schemas``:
``reviewer_id`` was an INTEGER foreign key to ``users.id`` and
``reviewee_submission_id`` was NOT NULL. Reviewers are students, identified by
student number, and no writer ever filled ``reviewee_submission_id``, so every
attempt to allocate a peer review — CLI or GUI — failed with a constraint
error. The table has never held a row on the established database.

This rebuilds it to the one definition in
``infrastructure/database/schemas/peer_reviews_table.py``: reviewer and
reviewee are foreign keys to ``students``, the reviewed work is
``submission_id``. Rows are copied across; a reviewer recorded as a users.id
is translated to that user's student number where one exists.

SQLite cannot change a foreign key in place, so the table is rebuilt with
foreign keys suspended and the result checked afterwards (scoped to this
table: unrelated tables carry pre-existing violations). Idempotent: a table
already in the canonical shape is left alone.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f7d2a9c4e1b6'
down_revision: Union[str, Sequence[str], None] = 'e4b81c6d2a57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table):
    return [r[1] for r in bind.execute(sa.text(f'PRAGMA table_info("{table}")'))]


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        peer_reviews_table as prt,
    )

    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'peer_reviews'")).fetchone()
    if row is None:
        # Not created yet; the runtime bootstraps create the canonical table.
        return
    if not prt.needs_rebuild(row[0]):
        for ddl in prt.INDEXES:
            op.execute(ddl)
        return

    old = set(_columns(bind, "peer_reviews"))
    canonical = [name for name, _ in prt.PEER_REVIEW_COLUMNS]
    shared = [c for c in canonical if c in old]

    # Source expressions for the copy: shared columns as-is, plus the two
    # translations described in the module docstring.
    select = {c: c for c in shared}
    if "submission_id" in canonical and "reviewee_submission_id" in old:
        select["submission_id"] = ("COALESCE(submission_id, reviewee_submission_id)"
                                   if "submission_id" in old else "reviewee_submission_id")
    if "users" in {r[0] for r in bind.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type = 'table'"))}:
        user_cols = set(_columns(bind, "users"))
        if "student_id" in user_cols:
            select["reviewer_id"] = (
                "COALESCE((SELECT u.student_id FROM users u WHERE u.id = peer_reviews.reviewer_id "
                "          AND NOT EXISTS (SELECT 1 FROM students s "
                "                          WHERE s.student_id = CAST(peer_reviews.reviewer_id AS TEXT))), "
                "         CAST(reviewer_id AS TEXT))")

    targets = ", ".join(select)
    sources = ", ".join(select.values())

    # PRAGMA foreign_keys is a no-op inside a transaction, which is how
    # alembic runs this. Dropping peer_reviews could then cascade-delete
    # peer_review_criteria rows (ON DELETE CASCADE), so keep a copy of them.
    tables = {r[0] for r in bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type = 'table'"))}
    keep_criteria = "peer_review_criteria" in tables
    if keep_criteria:
        op.execute("DROP TABLE IF EXISTS peer_review_criteria__keep")
        op.execute("CREATE TABLE peer_review_criteria__keep AS SELECT * FROM peer_review_criteria")

    op.execute("PRAGMA foreign_keys=OFF")
    try:
        op.execute("DROP TABLE IF EXISTS peer_reviews__new")
        op.execute(prt.create_peer_reviews_sql("peer_reviews__new"))
        op.execute(f"INSERT INTO peer_reviews__new ({targets}) "
                   f"SELECT {sources} FROM peer_reviews")  # nosec B608 - names from PRAGMA/canonical list
        op.execute("DROP TABLE peer_reviews")
        op.execute("ALTER TABLE peer_reviews__new RENAME TO peer_reviews")
        for ddl in prt.INDEXES:
            op.execute(ddl)
    finally:
        op.execute("PRAGMA foreign_keys=ON")

    if keep_criteria:
        crit_cols = ", ".join(f'"{c}"' for c in _columns(bind, "peer_review_criteria"))
        op.execute(f"INSERT OR IGNORE INTO peer_review_criteria ({crit_cols}) "
                   f"SELECT {crit_cols} FROM peer_review_criteria__keep")  # nosec B608 - names from PRAGMA
        op.execute("DROP TABLE peer_review_criteria__keep")

    violations = bind.execute(sa.text("PRAGMA foreign_key_check(peer_reviews)")).fetchall()
    if violations:
        raise RuntimeError(f"rebuilding peer_reviews left foreign key violations: {violations[:5]}")


def downgrade() -> None:
    # The old shape could not hold a valid review; nothing to go back to.
    pass
