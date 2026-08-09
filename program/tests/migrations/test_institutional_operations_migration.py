from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_institutional_operations_schema_is_reversible(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'institutional.db'}")
    migration = importlib.import_module(
        "education_system.migrations.versions.a83f5c7d9e12_institutional_operations"
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE governed_programmes("
            "programme_id INTEGER PRIMARY KEY, programme_code TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE student_registrations("
            "registration_id INTEGER PRIMARY KEY, programme_code TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE student_lifecycle_history(history_id INTEGER PRIMARY KEY)"
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert {
            "institutional_cases",
            "student_identity_merges",
            "timetable_versions",
            "connector_configurations",
            "alumni_transition_steps",
            "pgr_overdue_escalations",
            "historical_degree_audits",
        } <= tables
        columns = {
            column["name"]
            for column in sa.inspect(connection).get_columns("student_registrations")
        }
        assert "regulation_version_id" in columns
        migration.downgrade()
        assert "institutional_cases" not in set(sa.inspect(connection).get_table_names())
