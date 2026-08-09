"""Admissions policy decisions and lifecycle consumer receipts.

Revision ID: 91d4e6f2a8b0
Revises: 7c2e4a9b1d63
"""

from typing import Sequence, Union

from alembic import op

revision: str = "91d4e6f2a8b0"
down_revision: Union[str, Sequence[str], None] = "7c2e4a9b1d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE admission_deposit_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL UNIQUE,
            required_amount REAL NOT NULL,
            currency TEXT NOT NULL,
            received_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            payment_reference TEXT,
            decided_by TEXT NOT NULL,
            decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(application_id) REFERENCES admission_applications(application_id)
        )
    """)
    op.execute("""
        CREATE TABLE admission_sponsorship_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL UNIQUE,
            sponsor_name TEXT NOT NULL,
            reference TEXT NOT NULL,
            amount REAL,
            valid_until TEXT,
            status TEXT NOT NULL,
            decided_by TEXT NOT NULL,
            decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(application_id) REFERENCES admission_applications(application_id)
        )
    """)
    op.execute("""
        CREATE TABLE admission_right_to_study_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL UNIQUE,
            route TEXT NOT NULL,
            evidence_reference TEXT NOT NULL,
            valid_until TEXT,
            status TEXT NOT NULL,
            decided_by TEXT NOT NULL,
            decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(application_id) REFERENCES admission_applications(application_id)
        )
    """)
    op.execute("""
        CREATE TABLE student_lifecycle_consumer_receipts (
            action_id INTEGER NOT NULL,
            target_system TEXT NOT NULL,
            handler_version INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(action_id, target_system, handler_version),
            FOREIGN KEY(action_id) REFERENCES student_lifecycle_actions(action_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS student_lifecycle_consumer_receipts")
    op.execute("DROP TABLE IF EXISTS admission_right_to_study_decisions")
    op.execute("DROP TABLE IF EXISTS admission_sponsorship_decisions")
    op.execute("DROP TABLE IF EXISTS admission_deposit_decisions")
