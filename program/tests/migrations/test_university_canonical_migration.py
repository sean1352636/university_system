from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _legacy_schema(connection) -> None:
    connection.exec_driver_sql("""
        CREATE TABLE admission_prospects (
            prospect_id INTEGER PRIMARY KEY,
            first_name TEXT, last_name TEXT, email TEXT
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE admission_applications (
            application_id INTEGER PRIMARY KEY,
            prospect_id INTEGER NOT NULL,
            status TEXT
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            course TEXT NOT NULL,
            enrollment_date TEXT,
            registration_datetime TEXT,
            status TEXT,
            grade_level TEXT
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE student_modules (
            id INTEGER PRIMARY KEY,
            student_id TEXT,
            module_code TEXT,
            enrollment_date TEXT,
            status TEXT
        )
    """)
    connection.exec_driver_sql(
        "INSERT INTO students VALUES "
        "('S1', 'Ada', 'Lovelace', 'CS', '2026-09-01', NULL, 'Active', '1')"
    )
    connection.exec_driver_sql(
        "INSERT INTO modules VALUES ('CS101', 'Introduction')"
    )
    connection.exec_driver_sql(
        "INSERT INTO student_modules VALUES "
        "(1, 'S1', 'CS101', '2026-09-01', 'Enrolled')"
    )


def test_upgrade_backfills_and_exposes_compatibility_views(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "0a7d9c3e5f21_canonical_university_lifecycles"
    )
    with engine.begin() as connection:
        _legacy_schema(connection)
        context = MigrationContext.configure(connection)
        migration.op = Operations(context)
        migration.upgrade()

        registration = connection.exec_driver_sql(
            "SELECT student_id, programme_code FROM programme_registrations"
        ).one()
        module = connection.exec_driver_sql(
            "SELECT student_id, module_code FROM module_enrolments"
        ).one()
        compat = connection.exec_driver_sql(
            "SELECT student_id, module_code FROM legacy_student_modules_compat"
        ).one()

        assert tuple(registration) == ("S1", "CS")
        assert tuple(module) == ("S1", "CS101")
        assert tuple(compat) == ("S1", "CS101")


def test_upgrade_is_idempotent_and_downgrade_is_reversible(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "0a7d9c3e5f21_canonical_university_lifecycles"
    )
    with engine.begin() as connection:
        _legacy_schema(connection)
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM programme_registrations"
        ).scalar_one() == 1
        migration.downgrade()
        assert connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE name='programme_registrations'"
        ).first() is None
