"""Tests for the housing deposit lifecycle state machine.

The core functions (``current_state``, ``is_terminal``, ``transition``,
``reconcile_from_deductions``) all take a raw sqlite cursor, so tests build a
self-contained in-memory DB with the tables they touch — no patching needed.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import (
    deposit_state as ds,
)


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE housing_assignments (
            assignment_id TEXT PRIMARY KEY,
            deposit_state TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE housing_deposit_state_log (
            log_id TEXT PRIMARY KEY,
            assignment_id TEXT,
            from_state TEXT,
            to_state TEXT,
            reason TEXT,
            actor TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE housing_deposit_deductions (
            deduction_id TEXT PRIMARY KEY,
            assignment_id TEXT,
            status TEXT,
            acknowledgement_status TEXT
        )
    """)
    return conn


@pytest.fixture
def cursor():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO housing_assignments (assignment_id, deposit_state) VALUES ('ASG1', NULL)"
    )
    conn.commit()
    cur = conn.cursor()
    yield cur
    conn.close()


# ---------------------------------------------------------------------------
# Pure predicates
# ---------------------------------------------------------------------------

class TestIsTerminal:
    def test_terminal_states(self):
        assert ds.is_terminal(ds.REFUNDED)
        assert ds.is_terminal(ds.PARTIALLY_REFUNDED)
        assert ds.is_terminal(ds.FORFEITED)

    def test_non_terminal_states(self):
        assert not ds.is_terminal(ds.HELD)
        assert not ds.is_terminal(ds.DEDUCTIONS_PROPOSED)
        assert not ds.is_terminal(ds.DISPUTED)
        assert not ds.is_terminal(None)


# ---------------------------------------------------------------------------
# current_state / transition
# ---------------------------------------------------------------------------

class TestTransition:
    def test_initial_set_to_held(self, cursor):
        prev = ds.transition(cursor, "ASG1", ds.HELD, reason="deposit received", actor="staff")
        assert prev is None
        assert ds.current_state(cursor, "ASG1") == ds.HELD

    def test_transition_logs_row(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r1", actor="staff")
        ds.transition(cursor, "ASG1", ds.DEDUCTIONS_PROPOSED, reason="r2", actor="staff")
        logs = cursor.execute(
            "SELECT from_state, to_state FROM housing_deposit_state_log ORDER BY created_at"
        ).fetchall()
        assert (None, ds.HELD) in [(r[0], r[1]) for r in logs]
        assert (ds.HELD, ds.DEDUCTIONS_PROPOSED) in [(r[0], r[1]) for r in logs]

    def test_idempotent_transition_is_noop(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        prev = ds.transition(cursor, "ASG1", ds.HELD, reason="again", actor="staff")
        assert prev == ds.HELD
        # No second log row written for the idempotent move
        n = cursor.execute("SELECT COUNT(*) FROM housing_deposit_state_log").fetchone()[0]
        assert n == 1

    def test_illegal_transition_raises(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        # HELD -> DISPUTED is not permitted
        with pytest.raises(ds.IllegalTransition):
            ds.transition(cursor, "ASG1", ds.DISPUTED, reason="bad", actor="staff")

    def test_unknown_state_raises(self, cursor):
        with pytest.raises(ds.IllegalTransition):
            ds.transition(cursor, "ASG1", "Nonsense", reason="r", actor="staff")

    def test_cannot_leave_terminal_state(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        ds.transition(cursor, "ASG1", ds.REFUNDED, reason="refund", actor="staff")
        with pytest.raises(ds.IllegalTransition):
            ds.transition(cursor, "ASG1", ds.DEDUCTIONS_PROPOSED, reason="r", actor="staff")


# ---------------------------------------------------------------------------
# reconcile_from_deductions
# ---------------------------------------------------------------------------

class TestReconcile:
    def _add_deduction(self, cursor, ded_id, status, ack):
        cursor.execute(
            "INSERT INTO housing_deposit_deductions "
            "(deduction_id, assignment_id, status, acknowledgement_status) VALUES (?, 'ASG1', ?, ?)",
            (ded_id, status, ack),
        )

    def test_no_deductions_reconciles_to_held(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        ds.transition(cursor, "ASG1", ds.DEDUCTIONS_PROPOSED, reason="r", actor="staff")
        target = ds.reconcile_from_deductions(cursor, "ASG1")
        assert target == ds.HELD

    def test_proposed_deduction_reconciles_to_proposed(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        self._add_deduction(cursor, "D1", "Proposed", "Pending")
        target = ds.reconcile_from_deductions(cursor, "ASG1")
        assert target == ds.DEDUCTIONS_PROPOSED

    def test_disputed_deduction_reconciles_to_disputed(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        self._add_deduction(cursor, "D2", "Proposed", "Disputed")
        target = ds.reconcile_from_deductions(cursor, "ASG1")
        assert target == ds.DISPUTED

    def test_reconcile_noop_on_terminal(self, cursor):
        ds.transition(cursor, "ASG1", ds.HELD, reason="r", actor="staff")
        ds.transition(cursor, "ASG1", ds.FORFEITED, reason="r", actor="staff")
        # Even with a proposed deduction, terminal state is preserved
        self._add_deduction(cursor, "D3", "Proposed", "Pending")
        target = ds.reconcile_from_deductions(cursor, "ASG1")
        assert target == ds.FORFEITED
