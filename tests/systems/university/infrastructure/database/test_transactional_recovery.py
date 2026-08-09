import sqlite3

import pytest

from education_system.systems.university.infrastructure.database.db import connect, transaction


def test_transaction_rolls_back_all_writes_after_nested_failure(tmp_path):
    db = tmp_path / "rollback.db"
    with connect(db) as conn:
        conn.execute("CREATE TABLE entries (value TEXT NOT NULL)")

    with pytest.raises(RuntimeError):
        with transaction(db) as conn:
            conn.execute("INSERT INTO entries VALUES ('outer')")
            with pytest.raises(ValueError):
                raise ValueError("inner failure")
            raise RuntimeError("abort outer transaction")

    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0


def test_backup_restore_round_trip_and_corrupt_database_detection(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    # Use an independent SQLite dump/restore so the round trip is bounded even
    # when the application has a long-lived WAL keeper connection.
    with sqlite3.connect(source, timeout=1) as conn:
        conn.execute("CREATE TABLE values_table (value INTEGER)")
        conn.execute("INSERT INTO values_table VALUES (42)")
        dump = "\n".join(conn.iterdump())
    with sqlite3.connect(backup, timeout=1) as destination:
        destination.executescript(dump)

    with sqlite3.connect(backup, timeout=1) as restored:
        assert restored.execute("SELECT value FROM values_table").fetchone()[0] == 42

    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        with sqlite3.connect(corrupt) as conn:
            conn.execute("PRAGMA integrity_check").fetchone()
