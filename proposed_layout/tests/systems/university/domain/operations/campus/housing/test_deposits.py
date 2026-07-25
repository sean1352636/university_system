"""Tests for the end-of-tenancy deposit refund helpers.

The interactive ``process_deposit_refund`` / dispute workflows are driven by
``input()`` and permission checks; here we cover the deterministic query
helpers (which take a raw cursor) against a self-contained in-memory DB, plus
the pure guard in ``_post_refund_journal``.
"""

from unittest.mock import MagicMock

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import (
    deposits,
)


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT);
        CREATE TABLE housing_buildings (building_id TEXT PRIMARY KEY, building_name TEXT);
        CREATE TABLE housing_rooms (room_id TEXT PRIMARY KEY, room_number TEXT, building_id TEXT);
        CREATE TABLE housing_assignments (
            assignment_id TEXT PRIMARY KEY, student_id TEXT, room_id TEXT
        );
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_payment_id TEXT,
            source_type TEXT, payment_type TEXT, status TEXT,
            reference_id TEXT, payment_date TEXT, amount REAL
        );
        CREATE TABLE housing_inspections (
            inspection_id TEXT PRIMARY KEY, room_id TEXT, inspection_date TEXT,
            inspection_type TEXT, status TEXT, findings TEXT, action_required TEXT
        );
        CREATE TABLE users (id INTEGER PRIMARY KEY, student_id TEXT);
    """)
    return conn


@pytest.fixture
def conn():
    c = _make_conn()
    c.execute("INSERT INTO students VALUES ('S1', 'Ada', 'Lovelace')")
    c.execute("INSERT INTO housing_buildings VALUES ('B1', 'Newton Hall')")
    c.execute("INSERT INTO housing_rooms VALUES ('R1', '101', 'B1')")
    c.execute("INSERT INTO housing_assignments VALUES ('A1', 'S1', 'R1')")
    c.commit()
    yield c
    c.close()


class TestFetchAssignmentsWithHeldDeposit:
    def test_returns_assignment_with_completed_deposit(self, conn):
        conn.execute(
            "INSERT INTO payments (source_type, payment_type, status, reference_id, amount) "
            "VALUES ('housing', 'Deposit', 'Completed', 'A1', 500)"
        )
        conn.commit()
        rows = deposits._fetch_assignments_with_held_deposit(conn.cursor())
        assert len(rows) == 1
        # (assignment_id, student_id, first, last, room_number, building_name, deposit_held)
        assert rows[0][0] == "A1"
        assert rows[0][6] == 500

    def test_excludes_non_deposit_and_incomplete(self, conn):
        conn.execute(
            "INSERT INTO payments (source_type, payment_type, status, reference_id, amount) "
            "VALUES ('housing', 'Rent', 'Completed', 'A1', 400)"
        )
        conn.execute(
            "INSERT INTO payments (source_type, payment_type, status, reference_id, amount) "
            "VALUES ('housing', 'Deposit', 'Pending', 'A1', 300)"
        )
        conn.commit()
        assert deposits._fetch_assignments_with_held_deposit(conn.cursor()) == []


class TestDepositPaymentIds:
    def test_returns_only_completed_deposits(self, conn):
        conn.execute(
            "INSERT INTO payments (source_payment_id, source_type, payment_type, status, reference_id, payment_date, amount) "
            "VALUES ('P1', 'housing', 'Deposit', 'Completed', 'A1', '2026-01-01', 500)"
        )
        conn.execute(
            "INSERT INTO payments (source_payment_id, source_type, payment_type, status, reference_id, payment_date, amount) "
            "VALUES ('P2', 'housing', 'Deposit', 'Refunded', 'A1', '2026-02-01', 500)"
        )
        conn.commit()
        rows = deposits._deposit_payment_ids(conn.cursor(), "A1")
        assert len(rows) == 1
        assert rows[0][0] == "P1"


class TestLatestMoveOutInspection:
    def test_returns_most_recent_moveout(self, conn):
        conn.execute(
            "INSERT INTO housing_inspections VALUES ('I1', 'R1', '2026-01-01', 'Move-out', 'Passed', 'ok', NULL)"
        )
        conn.execute(
            "INSERT INTO housing_inspections VALUES ('I2', 'R1', '2026-03-01', 'Move-out', 'Issues found', 'damage', 'repaint')"
        )
        conn.commit()
        row = deposits._latest_move_out_inspection(conn.cursor(), "R1")
        assert row[0] == "I2"

    def test_none_when_no_moveout(self, conn):
        assert deposits._latest_move_out_inspection(conn.cursor(), "R1") is None


class TestResolveCurrentStudentId:
    def test_returns_linked_student(self, conn):
        conn.execute("INSERT INTO users VALUES (7, 'S1')")
        conn.commit()
        auth = MagicMock()
        auth.current_user = {"id": 7}
        assert deposits._resolve_current_student_id(conn.cursor(), auth) == "S1"

    def test_returns_none_when_unlinked(self, conn):
        conn.execute("INSERT INTO users VALUES (8, NULL)")
        conn.commit()
        auth = MagicMock()
        auth.current_user = {"id": 8}
        assert deposits._resolve_current_student_id(conn.cursor(), auth) is None


class TestPostRefundJournalGuard:
    def test_returns_none_when_no_principal_held(self):
        # deposit_held <= 0 short-circuits before any ledger import
        result = deposits._post_refund_journal(
            deposit_held=0, total_deductions=0, refund_amount=0,
            assignment_id="A1", posted_by="staff",
        )
        assert result is None
