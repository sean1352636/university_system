"""university: tables and a column that shipped screens already read and write

Each of these fails today with "no such table / column" when it is used:

* ``job_interests`` - alumni "Express interest" on a job posting.
* ``mentorship_ratings`` - Student Union "Rate mentorship" dialog.
* ``collection_notices`` - structured history of finance collection notices
  (``send_case_notice`` already writes it once the table exists).
* ``integration_catalog.min_version`` - integration marketplace compatibility
  filter.

Additive and idempotent: nothing existing changes.

Revision ID: c3f5a7b9d1e2
Revises: b2e4f6a8c0d1
Create Date: 2026-10-31 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3f5a7b9d1e2'
down_revision: Union[str, Sequence[str], None] = 'b2e4f6a8c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    """CREATE TABLE IF NOT EXISTS job_interests (
        interest_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES job_postings (job_id),
        user_id TEXT NOT NULL,
        expressed_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'interested',
        UNIQUE (job_id, user_id))""",
    """CREATE TABLE IF NOT EXISTS mentorship_ratings (
        rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES mentorship_sessions (session_id),
        rater_id TEXT NOT NULL,
        rating INTEGER,
        feedback TEXT,
        is_anonymous INTEGER DEFAULT 0,
        rating_date TEXT,
        UNIQUE (session_id, rater_id))""",
    """CREATE TABLE IF NOT EXISTS collection_notices (
        notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES collection_cases (case_id),
        student_id TEXT,
        notice_type TEXT,
        subject TEXT,
        message TEXT,
        sent_by TEXT,
        sent_at TEXT)""",
)


def upgrade() -> None:
    bind = op.get_bind()
    for ddl in TABLES:
        bind.exec_driver_sql(ddl)
    columns = {row[1] for row in
               bind.exec_driver_sql("PRAGMA table_info(integration_catalog)").fetchall()}
    if columns and "min_version" not in columns:
        bind.exec_driver_sql("ALTER TABLE integration_catalog ADD COLUMN min_version TEXT")


def downgrade() -> None:
    """Additive; left in place so no recorded data is lost."""
