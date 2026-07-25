"""Tests for scripts.fix_finance_refunds_table."""
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

from education_system.systems.university.scripts import fix_finance_refunds_table as script


@contextmanager
def _fake_tx(conn):
    yield conn


class TestModuleSurface:
    def test_fix_function_callable(self):
        assert callable(script.fix_finance_refunds_table)


class TestFixFinanceRefundsTable:
    def test_creates_table_when_missing(self):
        conn = sqlite3.connect(":memory:")
        with patch.object(script, "transaction", lambda: _fake_tx(conn)):
            assert script.fix_finance_refunds_table() is True
        cols = [r[1] for r in conn.execute("PRAGMA table_info(finance_refunds)").fetchall()]
        assert "student_id" in cols
        conn.close()

    def test_adds_missing_column(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE finance_refunds (id INTEGER PRIMARY KEY, refund_reference TEXT)")
        with patch.object(script, "transaction", lambda: _fake_tx(conn)):
            assert script.fix_finance_refunds_table() is True
        cols = [r[1] for r in conn.execute("PRAGMA table_info(finance_refunds)").fetchall()]
        assert "student_id" in cols
        conn.close()

    def test_no_op_when_column_present(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE finance_refunds (id INTEGER PRIMARY KEY, student_id TEXT)"
        )
        with patch.object(script, "transaction", lambda: _fake_tx(conn)):
            assert script.fix_finance_refunds_table() is True
        conn.close()

    def test_returns_false_on_failure(self):
        with patch.object(script, "transaction", side_effect=RuntimeError("nope")):
            assert script.fix_finance_refunds_table() is False
