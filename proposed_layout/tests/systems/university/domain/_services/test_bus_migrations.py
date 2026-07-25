"""Unit tests for the centralised bus-schema bootstrap (``modules.services.bus_migrations``).

``ensure_all_bus_schemas()`` aggregates every bus's idempotent ``CREATE TABLE IF NOT
EXISTS`` / ``ALTER TABLE ... ADD COLUMN`` into one call, going through the shared
``get_connection`` helper. Repointing ``DEFAULT_DB_PATH`` at a per-test temp file
isolates each run. We assert the expected tables, indexes, and columns exist after a
single call, that a second call is a no-op (idempotent), and that column additions
only fire when the parent table already exists.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import bus_migrations


@pytest.fixture()
def mig_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "mig.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    sqlite3.connect(db_path).close()
    return db_path


def _tables(db_path):
    conn = sqlite3.connect(db_path)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    return names


def _indexes(db_path):
    conn = sqlite3.connect(db_path)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()}
    conn.close()
    return names


def _columns(db_path, table):
    conn = sqlite3.connect(db_path)
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    conn.close()
    return cols


class TestEnsureAllBusSchemas:
    def test_creates_expected_tables(self, mig_db):
        bus_migrations.ensure_all_bus_schemas()
        tables = _tables(mig_db)
        for expected in ("finance_holds", "su_advocacy_requests",
                         "loyalty_ledger", "gym_day_passes"):
            assert expected in tables

    def test_creates_expected_indexes(self, mig_db):
        bus_migrations.ensure_all_bus_schemas()
        idx = _indexes(mig_db)
        for expected in ("idx_finance_holds_student",
                         "idx_su_advocacy_student",
                         "idx_su_advocacy_case",
                         "idx_loyalty_ledger_student"):
            assert expected in idx

    def test_table_columns_match_spec(self, mig_db):
        bus_migrations.ensure_all_bus_schemas()
        holds_cols = _columns(mig_db, "finance_holds")
        assert {"hold_id", "student_id", "amount", "reason",
                "source", "reference_id", "is_active"} <= holds_cols
        advocacy_cols = _columns(mig_db, "su_advocacy_requests")
        assert {"request_id", "student_id", "case_id", "case_kind",
                "status", "su_rep_id"} <= advocacy_cols

    def test_idempotent_second_call_is_noop(self, mig_db):
        bus_migrations.ensure_all_bus_schemas()
        tables_first = _tables(mig_db)
        idx_first = _indexes(mig_db)
        # Second call must not raise and must not change the schema.
        bus_migrations.ensure_all_bus_schemas()
        assert _tables(mig_db) == tables_first
        assert _indexes(mig_db) == idx_first

    def test_column_additions_applied_when_parent_exists(self, mig_db):
        # Pre-create the parent tables WITHOUT the new columns.
        conn = sqlite3.connect(mig_db)
        conn.executescript(
            "CREATE TABLE student_union_clubs (id INTEGER PRIMARY KEY, name TEXT);"
            "CREATE TABLE restaurant_customers (id INTEGER PRIMARY KEY, name TEXT);"
            "CREATE TABLE risks (id INTEGER PRIMARY KEY, title TEXT);"
        )
        conn.commit()
        conn.close()

        bus_migrations.ensure_all_bus_schemas()

        assert "hall_id" in _columns(mig_db, "student_union_clubs")
        assert "student_id" in _columns(mig_db, "restaurant_customers")
        risk_cols = _columns(mig_db, "risks")
        assert {"reference_id", "next_review_date",
                "expires_at", "closed_at"} <= risk_cols

    def test_column_additions_skipped_when_parent_missing(self, mig_db):
        # No parent tables → column-add specs silently skip (no table created).
        bus_migrations.ensure_all_bus_schemas()
        tables = _tables(mig_db)
        assert "student_union_clubs" not in tables
        assert "risks" not in tables

    def test_column_additions_idempotent(self, mig_db):
        conn = sqlite3.connect(mig_db)
        conn.executescript(
            "CREATE TABLE risks (id INTEGER PRIMARY KEY, title TEXT);"
        )
        conn.commit()
        conn.close()
        bus_migrations.ensure_all_bus_schemas()
        cols_first = _columns(mig_db, "risks")
        # Re-running must not error or duplicate columns.
        bus_migrations.ensure_all_bus_schemas()
        assert _columns(mig_db, "risks") == cols_first


class TestBootstrapAllBusSubscribers:
    def test_callable_without_raising(self, mig_db):
        # Swallows every per-module import/wire error internally; returns None.
        assert bus_migrations.bootstrap_all_bus_subscribers() is None
