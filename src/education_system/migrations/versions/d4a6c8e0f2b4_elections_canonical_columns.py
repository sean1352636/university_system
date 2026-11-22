"""university: ``elections`` is the one Student Union election table

Every election screen reads and writes ``elections``, but the extra columns
they need were only added when the Student Union start-up reconcile ran, so a
database that never reached it fails with "no such column" on department and
the nomination and voting dates.

This adds those columns, folds any ``union_elections`` rows across (same ids,
so child rows still match) and pairs the voting window with start/end date.
It matches ``student_union_elections_schema`` and is safe to run after it.
``union_elections`` stays in place as the old record.

Revision ID: d4a6c8e0f2b4
Revises: c3f5a7b9d1e2
Create Date: 2026-10-31 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4a6c8e0f2b4'
down_revision: Union[str, Sequence[str], None] = 'c3f5a7b9d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXTRA_COLUMNS = (
    "department", "nomination_start", "nomination_end",
    "voting_start", "voting_end", "created_at",
)

FOLD_ROWS = """
    INSERT INTO elections (id, title, description, start_date, end_date, status,
                           department, nomination_start, nomination_end,
                           voting_start, voting_end, created_at)
    SELECT u.election_id,
           COALESCE(NULLIF(TRIM(u.position), ''), 'Election ' || u.election_id),
           COALESCE(u.description, u.department), u.voting_start, u.voting_end,
           COALESCE(u.status, 'upcoming'),
           u.department, u.nomination_start, u.nomination_end,
           u.voting_start, u.voting_end, u.created_at
    FROM union_elections u
    WHERE NOT EXISTS (SELECT 1 FROM elections e WHERE e.id = u.election_id)
"""

BACKFILL_ROWS = """
    UPDATE elections SET
        department = COALESCE(department,
            (SELECT u.department FROM union_elections u WHERE u.election_id = elections.id)),
        nomination_start = COALESCE(nomination_start,
            (SELECT u.nomination_start FROM union_elections u WHERE u.election_id = elections.id)),
        nomination_end = COALESCE(nomination_end,
            (SELECT u.nomination_end FROM union_elections u WHERE u.election_id = elections.id))
    WHERE id IN (SELECT election_id FROM union_elections)
"""

PAIR_VOTING_WINDOW = """
    UPDATE elections SET
        voting_start = COALESCE(voting_start, start_date),
        voting_end = COALESCE(voting_end, end_date),
        start_date = COALESCE(start_date, voting_start),
        end_date = COALESCE(end_date, voting_end)
"""


def _columns(bind, table: str) -> set:
    return {row[1] for row in bind.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}


def upgrade() -> None:
    bind = op.get_bind()
    have = _columns(bind, "elections")
    if not have:
        return  # no elections table on this database: nothing to do
    for column in EXTRA_COLUMNS:
        if column not in have:
            bind.exec_driver_sql(f"ALTER TABLE elections ADD COLUMN {column} TEXT")
    if _columns(bind, "union_elections"):
        bind.exec_driver_sql(FOLD_ROWS)
        bind.exec_driver_sql(BACKFILL_ROWS)
    bind.exec_driver_sql(PAIR_VOTING_WINDOW)


def downgrade() -> None:
    """Additive; left in place so no recorded data is lost."""
