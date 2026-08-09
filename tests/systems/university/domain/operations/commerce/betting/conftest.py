"""Shared fixtures for the Betting Shop **service-layer** test suite
(``modules.domain.commerce.betting.services.betting_core``).

Every manager (`AccountManager`, `SportsBettingManager`,
`PredictionMarketManager`, `CasinoManager`, `ReportManager`) talks to the DB
only through the shared ``get_connection`` / ``transaction`` chokepoints, both
of which resolve ``DEFAULT_DB_PATH`` at call time. So we isolate exactly like
the betting CLI suite does: repoint ``DEFAULT_DB_PATH`` at a throwaway file,
build the betting schema via the module's own ``init_betting_db()``, and add
the unified ``transactions`` table the account managers write into (the betting
schema does not own it).

Casino/roulette RNG lives on ``betting_core.random``; tests that need a
deterministic outcome monkeypatch that attribute directly.
"""

import sqlite3

import pytest

from education_system.systems.university.domain.operations.commerce.betting.services import (
    betting_core,
)

_DB_MODULE = (
    "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH"
)


def _exec(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def bet_db(tmp_path, monkeypatch):
    """Temp DB + betting schema + the unified ``transactions`` table.

    Returns the on-disk path so tests can read rows back directly, independent
    of the managers under test.
    """
    db_path = str(tmp_path / "betting.db")
    monkeypatch.setattr(_DB_MODULE, db_path)

    assert betting_core.init_betting_db() is True

    # The account managers record into the shared 'transactions' table with the
    # full column set their INSERTs reference (reference_number/processed_by are
    # betting-specific extras the CLI-only schema omits).
    _exec(
        db_path,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type      TEXT,
            student_id       TEXT,
            transaction_type TEXT,
            amount           REAL,
            balance_before   REAL,
            balance_after    REAL,
            reference_number TEXT,
            description      TEXT,
            payment_method   TEXT,
            processed_by     TEXT,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    return db_path


@pytest.fixture()
def account(bet_db):
    """A funded account for 'bob' (balance 1000) plus the db path.

    Most manager flows deduct a stake before doing anything else, so a funded
    account is the common starting point. Returns ``(db_path, user_id)``.
    """
    betting_core.AccountManager.get_or_create_account("bob", "bob", "bob@uni.ac.uk")
    _exec(bet_db, "UPDATE betting_accounts SET balance = 1000 WHERE user_id = 'bob'")
    return bet_db, "bob"
