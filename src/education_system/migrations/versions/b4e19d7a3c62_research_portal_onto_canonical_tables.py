"""repoint the Research Portal at existing tables

Revision ID: b4e19d7a3c62
Revises: c8a2f5b71d09
Create Date: 2026-08-26 17:10:00.000000

The Research Portal authored six ``research_*`` tables of its own and
seeded them with demo rows, duplicating concepts the university already
modelled. This widens the existing tables so the portal can use them:

* ``research_publications``  += REF fields (the Outputs tab's whole point)
* ``ethics_reviews``         += application fields; ``project_id`` relaxed
* ``research_milestones``    += ``thesis_id``;      ``project_id`` relaxed
* ``student_supervisions``   += viva / examiner / outcome fields
* ``ip_disclosures``         += reference / inventor / jurisdiction / route

Every added column is nullable, so existing readers and writers of these
tables are unaffected. The two ``project_id NOT NULL`` constraints are
relaxed by table rebuild — both tables are empty, so no rows move, and
relaxing NOT NULL cannot break a writer that already supplies the value.

The portal's own ``research_*`` tables are deliberately left in place and
untouched: dropping them is a separate, destructive decision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4e19d7a3c62'
down_revision: Union[str, Sequence[str], None] = 'c8a2f5b71d09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: table -> [(column, type)] — all nullable, all additive.
_ADDITIONS = {
    "research_publications": [
        ("uoa", "TEXT"),                    # REF unit of assessment
        ("ref_submitted", "INTEGER DEFAULT 0"),
        ("open_access", "INTEGER DEFAULT 0"),
        ("quality_rating", "TEXT"),
        ("lead_author_id", "TEXT"),
        ("venue", "TEXT"),                  # journal_name/conference_name rollup
    ],
    "ethics_reviews": [
        ("reference", "TEXT"),
        ("title", "TEXT"),
        ("principal_investigator_id", "TEXT"),
        ("department", "TEXT"),
        ("risk_level", "TEXT"),
        ("category", "TEXT"),
        ("notes", "TEXT"),
    ],
    "research_milestones": [
        ("thesis_id", "INTEGER"),
        ("notes", "TEXT"),
    ],
    "student_supervisions": [
        ("degree", "TEXT"),
        ("department", "TEXT"),
        ("secondary_supervisor_id", "TEXT"),
        ("submission_date", "TEXT"),
        ("viva_date", "TEXT"),
        ("internal_examiner_id", "TEXT"),
        ("external_examiner_id", "TEXT"),
        ("outcome", "TEXT"),
    ],
    "ip_disclosures": [
        ("reference", "TEXT"),
        ("inventor_id", "TEXT"),
        ("jurisdiction", "TEXT"),
        ("commercial_route", "TEXT"),
    ],
}

#: table -> (rebuild DDL, column list to copy)
#  Only difference from the original DDL is project_id losing NOT NULL.
_RELAX_NOT_NULL = {
    "ethics_reviews": (
        """
        CREATE TABLE ethics_reviews__new (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            review_type TEXT NOT NULL,
            submission_date TEXT NOT NULL,
            review_date TEXT,
            decision TEXT DEFAULT 'pending',
            decision_date TEXT,
            reviewer_comments TEXT,
            conditions TEXT,
            approval_expiry_date TEXT,
            reference TEXT,
            title TEXT,
            principal_investigator_id TEXT,
            department TEXT,
            risk_level TEXT,
            category TEXT,
            notes TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        """,
        "review_id, project_id, review_type, submission_date, review_date, "
        "decision, decision_date, reviewer_comments, conditions, "
        "approval_expiry_date, reference, title, principal_investigator_id, "
        "department, risk_level, category, notes",
    ),
    "research_milestones": (
        """
        CREATE TABLE research_milestones__new (
            milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            milestone_name TEXT NOT NULL,
            milestone_description TEXT,
            target_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            deliverables TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            thesis_id INTEGER,
            notes TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        """,
        "milestone_id, project_id, milestone_name, milestone_description, "
        "target_date, completion_date, status, deliverables, created_at, "
        "thesis_id, notes",
    ),
}


def _columns(bind, table):
    return {
        r[0]
        for r in bind.execute(
            sa.text(f"SELECT name FROM pragma_table_info('{table}')")
        ).fetchall()
    }


def _table_exists(bind, table):
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table},
        ).fetchone()
    )


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Additive columns first, so the rebuild below copies a full row.
    for table, additions in _ADDITIONS.items():
        if not _table_exists(bind, table):
            continue
        existing = _columns(bind, table)
        for column, ddl in additions:
            if column not in existing:
                op.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # 2. Relax the two NOT NULL project_id constraints by rebuild. SQLite
    #    cannot ALTER a column's nullability in place. Foreign keys are
    #    force-enabled in this application, so they are suspended for the
    #    swap and re-checked afterwards.
    for table, (ddl, columns) in _RELAX_NOT_NULL.items():
        if not _table_exists(bind, table):
            continue
        # Already relaxed? pragma_table_info.notnull is column index 3.
        rows = bind.execute(
            sa.text(f"SELECT name, \"notnull\" FROM pragma_table_info('{table}')")
        ).fetchall()
        notnull = {r[0]: r[1] for r in rows}
        if not notnull.get("project_id"):
            continue

        op.execute("PRAGMA foreign_keys=OFF")
        try:
            op.execute(f"DROP TABLE IF EXISTS {table}__new")
            op.execute(ddl)
            op.execute(
                f"INSERT INTO {table}__new ({columns}) SELECT {columns} FROM {table}"
            )
            op.execute(f"DROP TABLE {table}")
            op.execute(f"ALTER TABLE {table}__new RENAME TO {table}")
        finally:
            op.execute("PRAGMA foreign_keys=ON")
        # Scope the check to the rebuilt table. A bare `PRAGMA
        # foreign_key_check` scans every table, and this database carries
        # pre-existing violations in unrelated ones (orphaned
        # medical_conditions / module_enrolments rows), which would abort a
        # migration that did nothing wrong.
        violations = bind.execute(
            sa.text(f"PRAGMA foreign_key_check({table})")
        ).fetchall()
        if violations:
            raise RuntimeError(
                f"rebuilding {table} left foreign key violations: {violations[:5]}"
            )

    # 3. Helpful lookups for the portal's list queries.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_research_pub_ref "
        "ON research_publications(ref_submitted)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_milestones_thesis "
        "ON research_milestones(thesis_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_research_pub_ref")
    op.execute("DROP INDEX IF EXISTS ix_milestones_thesis")
    # Column drops and the NOT NULL restoration are omitted: both need a
    # table rewrite, and a nullable column nothing reads is harmless.
