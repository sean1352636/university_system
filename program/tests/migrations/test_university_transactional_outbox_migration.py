from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_transactional_outbox_and_lifecycle_governance_are_reversible(tmp_path) -> None:
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "7c2e4a9b1d63_university_transactional_outbox"
    )
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'outbox.db'}")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert {
            "university_event_outbox",
            "university_legal_holds",
            "university_disposition_log",
        } <= tables
        migration.downgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert "university_event_outbox" not in tables
        assert "university_legal_holds" not in tables
        assert "university_disposition_log" not in tables
