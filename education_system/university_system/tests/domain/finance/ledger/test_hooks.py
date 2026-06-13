"""Hook tests — the never-raises contract is the core invariant."""

import sqlite3
import pytest
from datetime import date

from education_system.university_system.infrastructure.database import db as db_module
from education_system.university_system.modules.domain.finance.ledger import (
    init_ledger, notify_ledger, LEDGER_HOOK_FAILURES,
)


@pytest.fixture(autouse=True)
def _clear_failures():
    """Each test starts with an empty failure list."""
    LEDGER_HOOK_FAILURES.clear()
    yield
    LEDGER_HOOK_FAILURES.clear()


@pytest.fixture
def hook_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "hook_test.db")
    monkeypatch.setattr(db_module, 'DEFAULT_DB_PATH', db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), currency TEXT,
            payment_method TEXT, transaction_id TEXT, payment_date TEXT,
            source_type TEXT, status TEXT, notes TEXT,
            created_by TEXT, created_at TEXT
        );
        CREATE TABLE unified_refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), refund_date TEXT,
            source_type TEXT, refund_method TEXT, notes TEXT, status TEXT,
            requested_by TEXT, approved_by TEXT, processed_by TEXT
        );
        CREATE TABLE fee_types (fee_type_id INTEGER PRIMARY KEY, fee_name TEXT);
        CREATE TABLE student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, fee_type_id INTEGER, amount DECIMAL(10,2),
            currency TEXT, status TEXT, due_date TEXT, created_at TEXT
        );
    """)
    conn.commit()
    conn.close()
    init_ledger()
    return db_path


class TestNeverRaises:
    """The hook's primary contract: it must never raise into operational code."""

    def test_unknown_source_type(self, hook_db):
        result = notify_ledger('not_a_real_type', 1)
        assert result is False
        assert any('not_a_real_type' in msg for _, _, msg in LEDGER_HOOK_FAILURES)

    def test_missing_source_id(self, hook_db):
        # Posting a payment_id that doesn't exist should fail gracefully
        result = notify_ledger('payment', 99999)
        assert result is False
        assert len(LEDGER_HOOK_FAILURES) == 1

    def test_none_source_id(self, hook_db):
        result = notify_ledger('payment', None)
        assert result is False
        # None source_id is a no-op, not a failure
        assert len(LEDGER_HOOK_FAILURES) == 0

    def test_no_ledger_tables(self, tmp_path, monkeypatch):
        """If gl_* tables don't exist, hook silently no-ops."""
        db_path = str(tmp_path / "no_ledger.db")
        monkeypatch.setattr(db_module, 'DEFAULT_DB_PATH', db_path)
        # Don't init the ledger — schema absent
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE foo (id INTEGER)")
        conn.close()

        result = notify_ledger('payment', 1)
        assert result is False
        # No failure recorded — this is a deliberate no-op, not an error
        assert len(LEDGER_HOOK_FAILURES) == 0


class TestHappyPath:
    def test_payment_creates_journal(self, hook_db):
        conn = sqlite3.connect(hook_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (student_id, amount, payment_date, source_type, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ('S001', 50.00, date.today().isoformat(), 'general', 'completed'),
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()

        assert notify_ledger('payment', pid) is True
        # Idempotent — second call still returns True (existing journal returned)
        assert notify_ledger('payment', pid) is True

        conn = sqlite3.connect(hook_db)
        n = conn.execute("SELECT COUNT(*) FROM gl_journals WHERE source_type='payment'").fetchone()[0]
        assert n == 1
        assert len(LEDGER_HOOK_FAILURES) == 0


class TestCentralHelperWiring:
    """End-to-end: writing through record_payment_to_finance auto-posts."""

    def test_record_payment_to_finance_auto_posts(self, hook_db):
        from education_system.university_system.modules.shared.utils import finance_integration

        # The helper uses get_connection() and transaction(); both honour our
        # monkeypatched DEFAULT_DB_PATH because they read the module-level value.
        payment_id = finance_integration.record_payment_to_finance(
            student_id='S001',
            amount=125.00,
            payment_method='Card',
            transaction_source='Library',
            transaction_ref='FINE-001',
        )
        assert payment_id is not None

        conn = sqlite3.connect(hook_db)
        n = conn.execute(
            "SELECT COUNT(*) FROM gl_journals WHERE source_type='payment' AND source_id=?",
            (payment_id,),
        ).fetchone()[0]
        assert n == 1, "central helper should have triggered the auto-post hook"

    def test_record_payment_skips_post_for_pending_status(self, hook_db):
        from education_system.university_system.modules.shared.utils import finance_integration

        payment_id = finance_integration.record_payment_to_finance(
            student_id='S002',
            amount=50.00,
            payment_method='Card',
            transaction_source='Test',
            transaction_ref='PENDING-1',
            status='pending',
        )
        assert payment_id is not None
        conn = sqlite3.connect(hook_db)
        n = conn.execute(
            "SELECT COUNT(*) FROM gl_journals WHERE source_type='payment' AND source_id=?",
            (payment_id,),
        ).fetchone()[0]
        assert n == 0, "pending payments should not auto-post"
