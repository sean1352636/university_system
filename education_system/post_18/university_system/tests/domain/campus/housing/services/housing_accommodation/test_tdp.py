"""Tests for UK Tenancy Deposit Protection (TDP) tracking helpers.

Focuses on the pure date/classification logic and the cursor-based
deadline helpers, which are built against a self-contained in-memory DB.
"""

import datetime as _dt

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    tdp,
)


# ---------------------------------------------------------------------------
# Pure logic — _compute_deadline
# ---------------------------------------------------------------------------

class TestComputeDeadline:
    def test_adds_30_days(self):
        assert tdp._compute_deadline("2026-01-01") == "2026-01-31"

    def test_handles_datetime_prefix(self):
        # Only the date portion is used
        assert tdp._compute_deadline("2026-06-10 14:22:00") == "2026-07-10"

    def test_none_returns_none(self):
        assert tdp._compute_deadline(None) is None


# ---------------------------------------------------------------------------
# Pure logic — _classify
# ---------------------------------------------------------------------------

class TestClassify:
    def test_exempt(self):
        assert tdp._classify("Exempt", None, None, None) == ("Exempt", None)

    def test_protected_when_all_present(self):
        state, delta = tdp._classify("DPS", "2026-01-05", "2026-01-06", "2026-01-31")
        assert state == "Protected"
        assert delta is None

    def test_pending_before_deadline(self):
        future = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
        state, delta = tdp._classify(None, None, None, future)
        assert state == "Pending"
        assert delta == 10

    def test_overdue_past_deadline(self):
        past = (_dt.date.today() - _dt.timedelta(days=5)).isoformat()
        state, delta = tdp._classify(None, None, None, past)
        assert state == "Overdue"
        assert delta == -5

    def test_unprotected_without_deadline(self):
        state, delta = tdp._classify(None, None, None, None)
        assert state == "Unprotected"
        assert delta is None


# ---------------------------------------------------------------------------
# Cursor-based helpers
# ---------------------------------------------------------------------------

def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE housing_assignments (
            assignment_id TEXT PRIMARY KEY,
            tdp_deadline TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT,
            payment_type TEXT,
            status TEXT,
            reference_id TEXT,
            payment_date TEXT,
            amount REAL
        )
    """)
    return conn


@pytest.fixture
def cursor():
    conn = _make_conn()
    conn.execute("INSERT INTO housing_assignments (assignment_id) VALUES ('ASG1')")
    conn.commit()
    cur = conn.cursor()
    yield cur
    conn.close()


class TestFirstDepositDate:
    def test_returns_earliest_completed_deposit(self, cursor):
        cursor.executemany(
            "INSERT INTO payments (source_type, payment_type, status, reference_id, payment_date, amount) "
            "VALUES ('housing', 'Deposit', 'Completed', 'ASG1', ?, 500)",
            [("2026-03-15",), ("2026-02-01",)],
        )
        assert tdp._first_deposit_date(cursor, "ASG1") == "2026-02-01"

    def test_none_when_no_deposits(self, cursor):
        assert tdp._first_deposit_date(cursor, "ASG1") is None


class TestSetDeadlineIfUnset:
    def test_sets_deadline_from_payment_date(self, cursor):
        deadline = tdp.set_deposit_deadline_if_unset(cursor, "ASG1", "2026-01-01")
        assert deadline == "2026-01-31"
        stored = cursor.execute(
            "SELECT tdp_deadline FROM housing_assignments WHERE assignment_id='ASG1'"
        ).fetchone()[0]
        assert stored == "2026-01-31"

    def test_idempotent_leaves_existing_deadline(self, cursor):
        tdp.set_deposit_deadline_if_unset(cursor, "ASG1", "2026-01-01")
        # A later payment must not slide the already-set deadline
        result = tdp.set_deposit_deadline_if_unset(cursor, "ASG1", "2026-05-01")
        assert result == "2026-01-31"

    def test_unknown_assignment_returns_none(self, cursor):
        assert tdp.set_deposit_deadline_if_unset(cursor, "NOPE", "2026-01-01") is None
