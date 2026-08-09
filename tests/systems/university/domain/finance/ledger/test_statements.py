"""Tests for the periodic statement-run service."""

import sqlite3
import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domain.finance.statements import (
    init_statements, run_statements_batch, list_runs, list_statements, get_statement,
)


@pytest.fixture
def stmt_db(tmp_path, monkeypatch):
    """Fresh DB with operational tables seeded with realistic AR scenarios."""
    db_path = str(tmp_path / "statements_test.db")
    monkeypatch.setattr(db_module, 'DEFAULT_DB_PATH', db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, fee_type_id INTEGER, amount DECIMAL(10,2),
            currency TEXT, status TEXT, due_date TEXT, created_at TEXT
        );
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), payment_date TEXT,
            status TEXT, created_at TEXT
        );
        CREATE TABLE payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER, student_fee_id INTEGER,
            amount DECIMAL(10,2), created_at TEXT
        );
        CREATE TABLE unified_refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), refund_date TEXT,
            source_type TEXT, status TEXT, created_at TEXT
        );
    """)
    conn.commit()
    conn.close()
    init_statements()
    return db_path


def _seed_fee(db_path, student_id, amount, created_at):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO student_fees (student_id, amount, status, created_at) "
        "VALUES (?, ?, 'unpaid', ?)",
        (student_id, amount, created_at),
    )
    fee_id = cur.lastrowid
    conn.commit()
    conn.close()
    return fee_id


def _seed_payment_with_alloc(db_path, student_id, fee_id, amount, payment_date):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO payments (student_id, amount, payment_date, status) "
        "VALUES (?, ?, ?, 'completed')",
        (student_id, amount, payment_date),
    )
    pid = cur.lastrowid
    conn.execute(
        "INSERT INTO payment_allocations (payment_id, student_fee_id, amount) "
        "VALUES (?, ?, ?)",
        (pid, fee_id, amount),
    )
    conn.commit()
    conn.close()
    return pid


class TestSchema:
    def test_init_creates_tables(self, stmt_db):
        conn = sqlite3.connect(stmt_db)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert {'statement_runs', 'student_statements'} <= names

    def test_init_idempotent(self, stmt_db):
        init_statements()
        init_statements()  # no error


class TestRunBatch:
    def test_empty_db_produces_empty_run(self, stmt_db):
        result = run_statements_batch('2026-04-30')
        assert result['total_students'] == 0
        assert result['total_with_balance'] == 0
        assert list_statements(result['run_id']) == []

    def test_single_student_unpaid_fee(self, stmt_db):
        # Student has £100 fee, no payment → closing balance = £100
        _seed_fee(stmt_db, 'S001', 100.00, '2026-04-15')
        result = run_statements_batch('2026-04-30')
        assert result['total_students'] == 1
        assert result['total_with_balance'] == 1

        stmts = list_statements(result['run_id'])
        s = stmts[0]
        assert s['student_id'] == 'S001'
        assert s['charges_in_period'] == 100.00
        assert s['payments_in_period'] == 0
        assert s['closing_balance'] == 100.00

    def test_paid_in_full_zero_balance(self, stmt_db):
        fee_id = _seed_fee(stmt_db, 'S002', 50.00, '2026-04-01')
        _seed_payment_with_alloc(stmt_db, 'S002', fee_id, 50.00, '2026-04-10')

        result = run_statements_batch('2026-04-30')
        assert result['total_students'] == 1
        assert result['total_with_balance'] == 0  # zero balance

        s = list_statements(result['run_id'])[0]
        assert s['closing_balance'] == 0.0
        assert s['charges_in_period'] == 50.00
        assert s['payments_in_period'] == 50.00

    def test_partial_payment_remaining_balance(self, stmt_db):
        fee_id = _seed_fee(stmt_db, 'S003', 200.00, '2026-04-01')
        _seed_payment_with_alloc(stmt_db, 'S003', fee_id, 75.00, '2026-04-15')

        result = run_statements_batch('2026-04-30')
        s = list_statements(result['run_id'])[0]
        assert s['closing_balance'] == 125.00

    def test_period_window_opening_balance(self, stmt_db):
        # Charge raised before period_start should land in opening_balance,
        # not charges_in_period
        _seed_fee(stmt_db, 'S004', 300.00, '2026-03-15')   # before
        _seed_fee(stmt_db, 'S004', 50.00,  '2026-04-15')   # in-period

        result = run_statements_batch(
            '2026-04-30', period_start='2026-04-01',
        )
        s = list_statements(result['run_id'])[0]
        assert s['opening_balance'] == 300.00
        assert s['charges_in_period'] == 50.00
        assert s['closing_balance'] == 350.00

    def test_only_with_balance_filter(self, stmt_db):
        _seed_fee(stmt_db, 'S005', 100.00, '2026-04-15')
        fee_id = _seed_fee(stmt_db, 'S006', 80.00, '2026-04-15')
        _seed_payment_with_alloc(stmt_db, 'S006', fee_id, 80.00, '2026-04-20')

        result = run_statements_batch('2026-04-30')
        all_rows = list_statements(result['run_id'])
        outstanding = list_statements(result['run_id'], only_with_balance=True)

        assert len(all_rows) == 2
        assert len(outstanding) == 1
        assert outstanding[0]['student_id'] == 'S005'

    def test_two_runs_create_two_rows_per_student(self, stmt_db):
        # Each run is a separate snapshot — re-running doesn't replace.
        _seed_fee(stmt_db, 'S007', 100.00, '2026-04-01')
        r1 = run_statements_batch('2026-04-30')
        r2 = run_statements_batch('2026-05-31')
        assert r1['run_id'] != r2['run_id']
        # Each run has its own statement row for S007
        assert get_statement(r1['run_id'], 'S007') is not None
        assert get_statement(r2['run_id'], 'S007') is not None

    def test_refunds_in_period(self, stmt_db):
        _seed_fee(stmt_db, 'S008', 100.00, '2026-04-01')
        # Refund recorded in-period (no fee linkage required for the by-student aggregation)
        conn = sqlite3.connect(stmt_db)
        conn.execute(
            "INSERT INTO unified_refunds (student_id, amount, refund_date, status) "
            "VALUES (?, ?, ?, 'processed')",
            ('S008', 25.00, '2026-04-20'),
        )
        conn.commit()
        conn.close()
        result = run_statements_batch(
            '2026-04-30', period_start='2026-04-01',
        )
        s = list_statements(result['run_id'])[0]
        assert s['refunds_in_period'] == 25.00


class TestListRuns:
    def test_runs_listed_newest_first(self, stmt_db):
        _seed_fee(stmt_db, 'S100', 10.00, '2026-04-01')
        run_statements_batch('2026-03-31')
        run_statements_batch('2026-04-30')
        run_statements_batch('2026-05-31')
        runs = list_runs()
        assert [r['period_end'] for r in runs] == ['2026-05-31', '2026-04-30', '2026-03-31']
