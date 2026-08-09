"""Canonical university lifecycle and student-record tables.

Revision ID: 0a7d9c3e5f21
Revises: f1a2b3c4d5e6

This migration adopts tables created by early runtime initialisers by using
``IF NOT EXISTS`` and conditional column additions. New application code must
not create or alter these tables during a request.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0a7d9c3e5f21"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _table_exists(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Applicant/application lifecycle additions.
    for column in (
        sa.Column("journey_id", sa.Text()),
        sa.Column("accepted_choice_id", sa.Integer()),
        sa.Column("converted_student_id", sa.Text()),
        sa.Column("lifecycle_updated_at", sa.Text()),
    ):
        _add_column_if_missing("admission_applications", column)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admission_application_choices (
            choice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            programme_code TEXT NOT NULL,
            programme_name TEXT,
            entry_year TEXT,
            rank INTEGER NOT NULL DEFAULT 1 CHECK (rank > 0),
            choice_status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (application_id, rank),
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admission_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            requirement_type TEXT NOT NULL,
            description TEXT NOT NULL,
            due_date TEXT,
            required INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'outstanding',
            verified_by TEXT,
            verified_at TEXT,
            evidence_document_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admission_interviews (
            interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL CHECK (
                activity_type IN ('interview', 'audition')
            ),
            scheduled_at TEXT NOT NULL,
            format TEXT,
            location TEXT,
            panel TEXT,
            outcome TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admission_conditions (
            condition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            condition_type TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL,
            currency TEXT,
            sponsor_name TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'outstanding',
            satisfied_at TEXT,
            evidence_reference TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admission_status_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            reason TEXT,
            actor_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id) ON DELETE CASCADE
        )
    """)
    _add_column_if_missing(
        "admission_status_history",
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Canonical student record. Legacy tables are retained until backfill and
    # compatibility readers have been deployed.
    op.execute("""
        CREATE TABLE IF NOT EXISTS programme_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            programme_code TEXT NOT NULL,
            regulation_version_id INTEGER,
            academic_year TEXT NOT NULL,
            occurrence_code TEXT NOT NULL DEFAULT 'MAIN',
            mode_of_study TEXT NOT NULL DEFAULT 'full-time',
            status TEXT NOT NULL DEFAULT 'registration_pending',
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            registered_at TEXT,
            registered_by TEXT,
            source_application_id INTEGER,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (student_id, programme_code, academic_year, occurrence_code),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (source_application_id)
                REFERENCES admission_applications(application_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS module_enrolments (
            module_enrolment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            teaching_period TEXT,
            attempt_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'enrolled',
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (
                student_id, module_code, academic_year,
                teaching_period, attempt_number
            ),
            FOREIGN KEY (registration_id)
                REFERENCES programme_registrations(registration_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS attendance_events (
            attendance_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_enrolment_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('present', 'late', 'absent', 'authorised', 'unknown')
            ),
            source TEXT NOT NULL,
            recorded_by TEXT,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            supersedes_event_id INTEGER,
            reason TEXT,
            UNIQUE (module_enrolment_id, session_id, recorded_at),
            FOREIGN KEY (module_enrolment_id)
                REFERENCES module_enrolments(module_enrolment_id),
            FOREIGN KEY (supersedes_event_id)
                REFERENCES attendance_events(attendance_event_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS student_charges (
            charge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            registration_id INTEGER,
            charge_type TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
            due_at TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_type, source_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (registration_id)
                REFERENCES programme_registrations(registration_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS student_payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
            provider TEXT NOT NULL,
            provider_reference TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            received_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (provider, provider_reference),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            charge_id INTEGER NOT NULL,
            amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (payment_id, charge_id),
            FOREIGN KEY (payment_id)
                REFERENCES student_payments(payment_id),
            FOREIGN KEY (charge_id) REFERENCES student_charges(charge_id)
        )
    """)

    # Effective-dated status decisions and downstream reconciliation.
    for column in (
        sa.Column("academic_year", sa.Text()),
        sa.Column("mode_of_study", sa.Text(), server_default="full-time"),
        sa.Column("campus_code", sa.Text()),
        sa.Column("expected_return_date", sa.Text()),
        sa.Column("record_closed_at", sa.Text()),
    ):
        _add_column_if_missing("students", column)

    op.execute("""
        CREATE TABLE IF NOT EXISTS student_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            registration_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            mode_of_study TEXT,
            programme_code TEXT,
            campus_code TEXT,
            registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            registered_by TEXT,
            declarations_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(student_id, academic_year),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS student_lifecycle_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            action TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            effective_date TEXT NOT NULL,
            academic_year TEXT,
            old_programme TEXT,
            new_programme TEXT,
            old_mode TEXT,
            new_mode TEXT,
            old_campus TEXT,
            new_campus TEXT,
            repeat_year INTEGER,
            expected_return_date TEXT,
            reason TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS student_lifecycle_actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            target_system TEXT NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(history_id, target_system),
            FOREIGN KEY (history_id)
                REFERENCES student_lifecycle_history(history_id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS operational_degraded_states (
            state_id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT NOT NULL,
            code TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            retryable INTEGER NOT NULL DEFAULT 0,
            correlation_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'open',
            occurrence_count INTEGER NOT NULL DEFAULT 1,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            resolved_by TEXT,
            resolution_notes TEXT,
            UNIQUE(component, code, status)
        )
    """)

    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_app_status_history "
        "ON admission_status_history(application_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_programme_reg_student "
        "ON programme_registrations(student_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_module_enrolment_student "
        "ON module_enrolments(student_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_student_time "
        "ON attendance_events(student_id, occurred_at)",
        "CREATE INDEX IF NOT EXISTS idx_charge_student_status "
        "ON student_charges(student_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_lifecycle_action_status "
        "ON student_lifecycle_actions(status, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_degraded_state_status "
        "ON operational_degraded_states(status, severity, last_seen_at)",
    ):
        op.execute(statement)

    _backfill_legacy_records()
    _create_compatibility_views()


def _backfill_legacy_records() -> None:
    """Idempotently adopt supported legacy enrolment/attendance/payment rows."""
    bind = op.get_bind()
    if _table_exists("student_modules"):
        bind.exec_driver_sql("""
            INSERT OR IGNORE INTO programme_registrations
                (student_id, programme_code, academic_year, occurrence_code,
                 mode_of_study, status, effective_from, registered_at)
            SELECT DISTINCT
                   s.student_id,
                   COALESCE(NULLIF(s.course, ''), 'UNDECLARED'),
                   COALESCE(NULLIF(s.academic_year, ''), 'legacy'),
                   'MAIN',
                   COALESCE(NULLIF(s.mode_of_study, ''), 'full-time'),
                   CASE lower(COALESCE(s.status, 'active'))
                       WHEN 'active' THEN 'registered'
                       ELSE lower(COALESCE(s.status, 'registered'))
                   END,
                   COALESCE(s.enrollment_date, date('now')),
                   s.registration_datetime
              FROM students s
              JOIN student_modules sm ON sm.student_id = s.student_id
        """)
        bind.exec_driver_sql("""
            INSERT OR IGNORE INTO module_enrolments
                (registration_id, student_id, module_code, academic_year,
                 teaching_period, attempt_number, status, effective_from)
            SELECT pr.registration_id, sm.student_id, sm.module_code,
                   pr.academic_year, NULL, 1,
                   lower(COALESCE(sm.status, 'enrolled')),
                   COALESCE(sm.enrollment_date, date('now'))
              FROM student_modules sm
              JOIN programme_registrations pr
                ON pr.student_id = sm.student_id
               AND pr.academic_year = COALESCE(
                   (SELECT NULLIF(s.academic_year, '')
                      FROM students s WHERE s.student_id = sm.student_id),
                   'legacy'
               )
        """)

    if _table_exists("enrollments"):
        columns = _columns("enrollments")
        if {"student_id", "course_id"} <= columns:
            bind.exec_driver_sql("""
                INSERT OR IGNORE INTO programme_registrations
                    (student_id, programme_code, academic_year, occurrence_code,
                     mode_of_study, status, effective_from)
                SELECT e.student_id, CAST(e.course_id AS TEXT),
                       COALESCE(NULLIF(s.academic_year, ''), 'legacy'),
                       'MAIN', COALESCE(NULLIF(s.mode_of_study, ''), 'full-time'),
                       lower(COALESCE(e.status, 'registered')),
                       COALESCE(e.enrollment_date, date('now'))
                  FROM enrollments e
                  JOIN students s ON s.student_id = e.student_id
            """)

    if _table_exists("attendance_records") and _table_exists("attendance_sessions"):
        attendance_columns = _columns("attendance_records")
        if {"record_id", "session_id", "student_id", "status"} <= attendance_columns:
            bind.exec_driver_sql("""
                INSERT OR IGNORE INTO attendance_events
                    (module_enrolment_id, session_id, student_id, occurred_at,
                     status, source, recorded_at, reason)
                SELECT me.module_enrolment_id,
                       CAST(ar.session_id AS TEXT),
                       ar.student_id,
                       COALESCE(ar.check_in_time,
                                ats.session_date || 'T' || ats.session_time),
                       CASE lower(COALESCE(ar.status, 'unknown'))
                           WHEN 'present' THEN 'present'
                           WHEN 'late' THEN 'late'
                           WHEN 'absent' THEN 'absent'
                           WHEN 'authorised' THEN 'authorised'
                           ELSE 'unknown'
                       END,
                       COALESCE(ar.check_in_method, 'legacy'),
                       COALESCE(ar.check_in_time, CURRENT_TIMESTAMP),
                       ar.notes
                  FROM attendance_records ar
                  JOIN attendance_sessions ats ON ats.session_id = ar.session_id
                  JOIN module_enrolments me
                    ON me.student_id = ar.student_id
                   AND me.module_code = ats.module_code
            """)

    if _table_exists("payments"):
        payment_columns = _columns("payments")
        student_col = "student_id" if "student_id" in payment_columns else None
        amount_col = "amount" if "amount" in payment_columns else None
        id_col = (
            "payment_id" if "payment_id" in payment_columns
            else "id" if "id" in payment_columns else None
        )
        if student_col and amount_col and id_col:
            status_expr = (
                "lower(COALESCE(status, 'received'))"
                if "status" in payment_columns
                else "'received'"
            )
            date_expr = (
                "COALESCE(payment_date, CURRENT_TIMESTAMP)"
                if "payment_date" in payment_columns
                else "CURRENT_TIMESTAMP"
            )
            bind.exec_driver_sql(f"""
                INSERT OR IGNORE INTO student_payments
                    (student_id, currency, amount_minor, provider,
                     provider_reference, idempotency_key, status, received_at)
                SELECT CAST({student_col} AS TEXT), 'GBP',
                       CAST(ROUND(ABS({amount_col}) * 100) AS INTEGER),
                       'legacy',
                       'payments:' || CAST({id_col} AS TEXT),
                       'legacy:payments:' || CAST({id_col} AS TEXT),
                       {status_expr},
                       {date_expr}
                  FROM payments
                 WHERE {student_col} IS NOT NULL AND {amount_col} IS NOT NULL
                   AND ABS({amount_col}) > 0
            """)


def _create_compatibility_views() -> None:
    statements = (
        """CREATE VIEW IF NOT EXISTS legacy_enrollments_compat AS
           SELECT registration_id AS enrollment_id, student_id,
                  programme_code AS course_id, academic_year,
                  effective_from AS enrollment_date, status
             FROM programme_registrations""",
        """CREATE VIEW IF NOT EXISTS legacy_student_modules_compat AS
           SELECT module_enrolment_id AS id, student_id, module_code,
                  effective_from AS enrollment_date, status
             FROM module_enrolments""",
        """CREATE VIEW IF NOT EXISTS legacy_attendance_compat AS
           SELECT attendance_event_id AS record_id, session_id, student_id,
                  occurred_at AS check_in_time, source AS check_in_method,
                  status, reason AS notes
             FROM attendance_events""",
        """CREATE VIEW IF NOT EXISTS legacy_payments_compat AS
           SELECT payment_id, student_id, amount_minor / 100.0 AS amount,
                  currency, provider_reference, status,
                  received_at AS payment_date
             FROM student_payments""",
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    # Do not remove adopted admissions columns: SQLite cannot safely drop them
    # on every supported version and they may contain pre-migration data.
    for view in (
        "legacy_payments_compat",
        "legacy_attendance_compat",
        "legacy_student_modules_compat",
        "legacy_enrollments_compat",
    ):
        op.execute(f"DROP VIEW IF EXISTS {view}")
    for table in (
        "student_lifecycle_actions",
        "operational_degraded_states",
        "student_lifecycle_history",
        "student_registrations",
        "payment_allocations",
        "student_payments",
        "student_charges",
        "attendance_events",
        "module_enrolments",
        "programme_registrations",
        "admission_status_history",
        "admission_conditions",
        "admission_interviews",
        "admission_requirements",
        "admission_application_choices",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
