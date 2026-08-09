"""visa sponsorship tables

Revision ID: b7f2c1d83e44
Revises: a4c91b7d2e10
Create Date: 2026-05-09 09:30:00.000000

Creates the schema for the international student / Tier-4 sponsorship
module under modules/domain/student_affairs/international_compliance/.

Six tables:
- visa_records              one-row-per-student visa profile
- cas_records               history of CAS issuances
- engagement_checks         termly engagement evidence (sponsor duty)
- change_of_circumstance    UKVI-reportable changes (10-day clock)
- right_to_study_checks     pre-enrolment ID check log
- atas_clearances           ATAS certificate per restricted module
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7f2c1d83e44'
down_revision: Union[str, Sequence[str], None] = 'a4c91b7d2e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS visa_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            nationality TEXT,
            passport_number TEXT,
            passport_expiry TEXT,
            visa_type TEXT NOT NULL DEFAULT 'student_route',
            visa_number TEXT,
            visa_start_date TEXT,
            visa_expiry_date TEXT,
            brp_number TEXT,
            brp_expiry_date TEXT,
            sponsor_licence_ref TEXT,
            atas_required INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_visa_records_status ON visa_records(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_visa_records_visa_expiry ON visa_records(visa_expiry_date)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS cas_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            cas_number TEXT NOT NULL UNIQUE,
            issued_at TEXT NOT NULL DEFAULT (datetime('now')),
            issued_by INTEGER,
            programme TEXT,
            course_start_date TEXT,
            course_end_date TEXT,
            tuition_fee_gbp REAL,
            tuition_fee_paid_gbp REAL DEFAULT 0,
            living_costs_gbp REAL,
            status TEXT NOT NULL DEFAULT 'issued',
            withdrawn_reason TEXT,
            withdrawn_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cas_records_student_id ON cas_records(student_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cas_records_status ON cas_records(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS visa_engagement_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            check_date TEXT NOT NULL DEFAULT (date('now')),
            term TEXT,
            method TEXT,
            evidence TEXT,
            outcome TEXT NOT NULL DEFAULT 'engaged',
            recorded_by INTEGER,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_engage_student_id ON visa_engagement_checks(student_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_engage_outcome ON visa_engagement_checks(outcome)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS visa_change_of_circumstance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            occurred_on TEXT NOT NULL DEFAULT (date('now')),
            details TEXT,
            ukvi_report_due TEXT,
            ukvi_reported_at TEXT,
            ukvi_report_reference TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            recorded_by INTEGER,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_coc_student_id ON visa_change_of_circumstance(student_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_coc_status ON visa_change_of_circumstance(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS right_to_study_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            checked_at TEXT NOT NULL DEFAULT (datetime('now')),
            checked_by INTEGER,
            method TEXT,
            documents_seen TEXT,
            outcome TEXT NOT NULL DEFAULT 'pass',
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rts_student_id ON right_to_study_checks(student_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS atas_clearances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT,
            certificate_number TEXT,
            issued_on TEXT,
            expires_on TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_atas_student_id ON atas_clearances(student_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_atas_status ON atas_clearances(status)")


def downgrade() -> None:
    for tbl in (
        "atas_clearances",
        "right_to_study_checks",
        "visa_change_of_circumstance",
        "visa_engagement_checks",
        "cas_records",
        "visa_records",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tbl}")
