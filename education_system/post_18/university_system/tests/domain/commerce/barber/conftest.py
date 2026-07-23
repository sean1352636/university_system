"""Shared fixtures for the barber-shop core-service tests.

barber_core imports ``transaction`` and ``get_db_connection`` into its own
namespace and calls them with no arguments, so we patch those two names on the
module (the same approach the sibling nailbar test uses) to redirect every
manager at a throwaway temp DB.

The barber tables are created by the module's own ``init_barber_db`` /
``init_extended_barber_db`` (run under the patched ``transaction``); the
unified ``transactions`` / ``payments`` tables are not owned by this module, so
we create them by hand. ``process_payment`` also fans out to the finance
``record_payment`` — which would use the *real* DB — so we stub it to a no-op.
"""

import sqlite3
from contextlib import contextmanager

import pytest

MODULE = (
    "education_system.post_18.university_system.modules.domain."
    "commerce.barber.services.barber_core"
)

# Column set matching the real unified transactions table (status defaults to
# 'completed', mirroring the seeded schema used by the other commerce shops).
_TRANSACTIONS_DDL = """
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        reference_id INTEGER,
        reference_type TEXT,
        customer_id TEXT,
        amount DECIMAL(10,2),
        payment_method TEXT,
        tip_amount DECIMAL(10,2) DEFAULT 0,
        reference_number TEXT,
        processed_by TEXT,
        receipt_sent INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT, amount DECIMAL(10,2), payment_method TEXT,
        payment_date TEXT, status TEXT, notes TEXT, created_by TEXT
    );
"""


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=OFF")
    return conn


@pytest.fixture()
def barber(tmp_path, monkeypatch):
    db_path = str(tmp_path / "barber.db")

    @contextmanager
    def _fake_transaction(*a, **k):
        conn = _connect(db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _fake_get_db(*a, **k):
        conn = _connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    monkeypatch.setattr(f"{MODULE}.transaction", _fake_transaction)
    monkeypatch.setattr(f"{MODULE}.get_db_connection", _fake_get_db)

    # Don't let process_payment reach the real finance DB.
    monkeypatch.setattr(
        "education_system.post_18.university_system.modules.domain.finance."
        "core.unified_payments.record_payment",
        lambda *a, **k: None,
    )

    import education_system.post_18.university_system.modules.domain.commerce.barber.services.barber_core as bc

    bc.init_barber_db()
    bc.init_extended_barber_db()
    # Create the non-barber-owned unified tables and clear the seeded default
    # services so service-count assertions start from a clean slate.
    conn = _connect(db_path)
    conn.executescript(_TRANSACTIONS_DDL)
    conn.execute("DELETE FROM barber_services")
    conn.commit()
    conn.close()

    return bc


@pytest.fixture()
def seeded(barber):
    """A barber module with one service and one staff member seeded."""
    service_id = barber.ServiceManager.add_service("Standard Haircut", "haircut", 15.0, 30)
    staff_id = barber.StaffManager.add_staff("Dev Barber", employee_id="EMP1")
    return barber, service_id, staff_id
