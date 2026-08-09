"""Compatibility and recovery checks for feature-owned SQLite schemas."""

import sqlite3

import pytest

from education_system.systems.university.infrastructure.database.schemas import (
    ai_features_schemas,
    finance_schemas,
)


@pytest.fixture
def feature_db(tmp_path, monkeypatch):
    path = tmp_path / "feature-compatibility.sqlite3"
    monkeypatch.setattr(finance_schemas, "get_connection", lambda: sqlite3.connect(path))
    monkeypatch.setattr(ai_features_schemas, "get_connection", lambda: sqlite3.connect(path))
    yield path


def _tables(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


@pytest.mark.parametrize(
    ("module", "initializer", "sentinel", "recovery"),
    [
        (finance_schemas, "init_finance_system_db", "fee_types", "program_fees"),
        (ai_features_schemas, "init_ai_features_system_db", "ai_chatbot_conversations", "ai_chatbot_messages"),
    ],
)
def test_schema_upgrade_is_repeatable_and_recovers_partial_install(
    feature_db, module, initializer, sentinel, recovery
):
    """A partially-created feature database can safely be completed later."""
    connection = sqlite3.connect(feature_db)
    # Simulate an older release which already contains one feature table and data.
    if sentinel == "fee_types":
        connection.execute(
            "CREATE TABLE fee_types (fee_type_id INTEGER PRIMARY KEY, fee_name TEXT)"
        )
        connection.execute(
            "INSERT INTO fee_types VALUES (7, 'Legacy tuition')"
        )
    else:
        connection.execute(
            "CREATE TABLE ai_chatbot_conversations (conversation_id INTEGER PRIMARY KEY, user_id TEXT)"
        )
        connection.execute("INSERT INTO ai_chatbot_conversations VALUES (7, 'legacy-user')")
    connection.commit()

    connection.close()
    getattr(module, initializer)()
    connection = sqlite3.connect(feature_db)
    first_tables = _tables(connection)
    assert sentinel in first_tables
    assert connection.execute(
        f"SELECT COUNT(*) FROM {sentinel}"
    ).fetchone()[0] == 1

    # Simulate an interrupted migration, then retry it.
    connection.execute(f"DROP TABLE {recovery}")
    connection.commit()
    connection.close()
    getattr(module, initializer)()
    connection = sqlite3.connect(feature_db)
    second_tables = _tables(connection)
    assert recovery in second_tables
    assert sentinel in second_tables
    assert connection.execute(
        f"SELECT COUNT(*) FROM {sentinel}"
    ).fetchone()[0] == 1
    connection.close()

    # A third run must not duplicate tables or legacy rows.
    getattr(module, initializer)()
    connection = sqlite3.connect(feature_db)
    assert _tables(connection) == second_tables
    assert connection.execute(
        f"SELECT COUNT(*) FROM {sentinel}"
    ).fetchone()[0] == 1
    connection.close()
