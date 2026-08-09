"""external quality assurance tables (OfS / TEF / REF)

Revision ID: e8c4197a3b21
Revises: d6e34a915fb0
Create Date: 2026-05-09 13:30:00.000000

Schema for the new external_quality_assurance module under
modules/domain/research/external_quality_assurance/.

Seven tables:
- qa_submissions             one row per (framework, year)
- ofs_b3_metrics             continuation / completion / progression
- ofs_app_milestones         Access & Participation Plan milestones
- ofs_protection_plans       Student Protection Plan revisions
- tef_provider_narratives    TEF narrative drafts by section
- ref_impact_cases           Impact case studies per UoA
- ref_environment_statements Environment narrative per UoA
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e8c4197a3b21'
down_revision: Union[str, Sequence[str], None] = 'd6e34a915fb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS qa_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            framework TEXT NOT NULL,
            submission_year INTEGER NOT NULL,
            submission_date TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            assigned_to INTEGER,
            notes TEXT,
            signed_off_by INTEGER,
            signed_off_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (framework, submission_year)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_qa_sub_status ON qa_submissions(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ofs_b3_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cohort_year INTEGER NOT NULL,
            course TEXT,
            metric_type TEXT NOT NULL,
            value_pct REAL NOT NULL,
            numerator INTEGER NOT NULL,
            denominator INTEGER NOT NULL,
            computed_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (cohort_year, course, metric_type)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ofs_b3_cohort ON ofs_b3_metrics(cohort_year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ofs_b3_metric ON ofs_b3_metrics(metric_type)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ofs_app_milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_year INTEGER NOT NULL,
            milestone_text TEXT NOT NULL,
            target_value REAL,
            target_date TEXT,
            current_value REAL,
            achieved INTEGER NOT NULL DEFAULT 0,
            achieved_date TEXT,
            owner_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ofs_app_year ON ofs_app_milestones(plan_year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ofs_app_achieved ON ofs_app_milestones(achieved)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ofs_protection_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            in_force_from TEXT NOT NULL,
            in_force_to TEXT,
            plan_text TEXT NOT NULL,
            approved_by INTEGER,
            approved_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (version)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tef_provider_narratives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_year INTEGER NOT NULL,
            section TEXT NOT NULL,
            narrative_text TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            drafted_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (submission_year, section, version)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tef_narr_year ON tef_provider_narratives(submission_year)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ref_impact_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uoa TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            lead_author_id INTEGER,
            status TEXT NOT NULL DEFAULT 'draft',
            reach_significance TEXT,
            beneficiaries TEXT,
            evidence_links TEXT,
            quality_rating TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ref_impact_uoa ON ref_impact_cases(uoa)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ref_impact_status ON ref_impact_cases(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ref_environment_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uoa TEXT NOT NULL,
            narrative_text TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            drafted_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (uoa, version)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ref_env_uoa ON ref_environment_statements(uoa)")


def downgrade() -> None:
    for tbl in (
        "ref_environment_statements",
        "ref_impact_cases",
        "tef_provider_narratives",
        "ofs_protection_plans",
        "ofs_app_milestones",
        "ofs_b3_metrics",
        "qa_submissions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tbl}")
