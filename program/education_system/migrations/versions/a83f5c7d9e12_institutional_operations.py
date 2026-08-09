"""Institutional workflow, identity, timetable and integration controls.

Revision ID: a83f5c7d9e12
Revises: 91d4e6f2a8b0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a83f5c7d9e12"
down_revision: Union[str, Sequence[str], None] = "91d4e6f2a8b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("student_registrations") as batch:
        batch.add_column(sa.Column("regulation_version_id", sa.Integer()))
    op.execute("""
        CREATE TRIGGER require_registration_regulation_version
        BEFORE INSERT ON student_registrations
        WHEN EXISTS (
            SELECT 1 FROM governed_programmes
             WHERE programme_code = NEW.programme_code
        ) AND NEW.regulation_version_id IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'governed registration requires regulation version');
        END
    """)
    op.execute("""
        CREATE TABLE student_lifecycle_corrections (
            correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_id INTEGER NOT NULL, reversal_history_id INTEGER,
            reason TEXT NOT NULL, requested_by TEXT NOT NULL,
            approved_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(history_id), FOREIGN KEY(history_id) REFERENCES student_lifecycle_history(history_id)
        )
    """)
    op.execute("""
        CREATE TABLE pgr_overdue_escalations (
            escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL, source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL, due_date TEXT NOT NULL,
            severity TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            escalated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_type, source_id, status)
        )
    """)
    op.execute("""
        CREATE TABLE historical_degree_audits (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL, assignment_id INTEGER NOT NULL,
            regulation_version_id INTEGER NOT NULL, input_json TEXT NOT NULL,
            result_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
            calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE institutional_cases (
            case_id TEXT PRIMARY KEY, case_type TEXT NOT NULL,
            subject_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            summary TEXT NOT NULL, owner_id TEXT, confidentiality TEXT NOT NULL,
            opened_by TEXT NOT NULL, opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed_at TEXT, UNIQUE(case_type, subject_id, summary)
        )
    """)
    op.execute("""
        CREATE TABLE institutional_case_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
            event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
            actor_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(case_id) REFERENCES institutional_cases(case_id)
        )
    """)
    op.execute("""
        CREATE TABLE student_identity_changes (
            change_id TEXT PRIMARY KEY, student_id TEXT NOT NULL,
            change_type TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            reason TEXT NOT NULL, requested_by TEXT NOT NULL, approved_by TEXT NOT NULL,
            reversed_at TEXT, reversed_by TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE student_identity_merges (
            merge_id TEXT PRIMARY KEY, survivor_id TEXT NOT NULL, merged_id TEXT NOT NULL UNIQUE,
            reason TEXT NOT NULL, requested_by TEXT NOT NULL, approved_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', reversed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE timetable_versions (
            version_id TEXT PRIMARY KEY, academic_year TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft', input_hash TEXT NOT NULL,
            schedule_json TEXT NOT NULL, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, published_at TEXT
        )
    """)
    op.execute("""
        CREATE TABLE timetable_change_requests (
            request_id TEXT PRIMARY KEY, version_id TEXT NOT NULL, reason TEXT NOT NULL,
            proposed_json TEXT NOT NULL, requested_by TEXT NOT NULL,
            approved_by TEXT, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE connector_configurations (
            connector_name TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
            config_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'unconfigured',
            last_checked_at TEXT, last_error TEXT
        )
    """)
    op.execute("""
        CREATE TABLE connector_receipts (
            connector_name TEXT NOT NULL, idempotency_key TEXT NOT NULL,
            external_reference TEXT, outcome TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(connector_name, idempotency_key)
        )
    """)
    op.execute("""
        CREATE TABLE alumni_transition_steps (
            student_id TEXT NOT NULL, step_name TEXT NOT NULL,
            status TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}',
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, step_name)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS require_registration_regulation_version")
    for table in (
        "alumni_transition_steps", "connector_receipts", "connector_configurations",
        "timetable_change_requests", "timetable_versions", "student_identity_merges",
        "student_identity_changes", "institutional_case_events", "institutional_cases",
        "historical_degree_audits", "pgr_overdue_escalations",
        "student_lifecycle_corrections",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    with op.batch_alter_table("student_registrations") as batch:
        batch.drop_column("regulation_version_id")
