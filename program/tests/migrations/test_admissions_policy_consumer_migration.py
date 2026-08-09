from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_policy_and_consumer_receipt_schema_is_reversible(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'policy.db'}")
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "91d4e6f2a8b0_admissions_policy_and_consumer_receipts"
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE admission_applications(application_id INTEGER PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE student_lifecycle_actions(action_id INTEGER PRIMARY KEY)"
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert {
            "admission_deposit_decisions",
            "admission_sponsorship_decisions",
            "admission_right_to_study_decisions",
            "student_lifecycle_consumer_receipts",
        } <= tables
        migration.downgrade()
        assert "admission_deposit_decisions" not in set(
            sa.inspect(connection).get_table_names()
        )
