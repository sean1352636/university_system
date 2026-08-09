from __future__ import annotations

import importlib
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration():
    return importlib.import_module(
        "education_system.migrations.versions."
        "3f8b2a1c9d70_core_feature_owned_schemas"
    )


def test_feature_schema_upgrade_and_downgrade(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'features.db'}")
    migration = _migration()
    representative_tables = {
        "assessment_boards",
        "programme_versions",
        "pgr_projects",
    }

    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()

        installed = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert representative_tables <= installed

        migration.downgrade()
        remaining = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert not representative_tables & remaining


def test_feature_services_contain_no_runtime_schema_ddl() -> None:
    modules = (
        "education_system.systems.university.domains.assessment.domain.boards.service",
        "education_system.systems.university.domains.academics.domain."
        "programme_governance.service",
        "education_system.systems.university.domains.academics.domain.research.pgr.service",
    )
    for name in modules:
        module = importlib.import_module(name)
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "CREATE TABLE" not in source.upper()
        assert "ALTER TABLE" not in source.upper()
