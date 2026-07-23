"""Behavioral tests for the Betting Shop CLI package
(``modules.services.cli.betting_shop_cli``).

The package spreads its logic over submodules (``constants``, ``helpers``,
``account``, ``sports``, ``predictions``, ``casino`` ...). All interactive money
math is inline in the action functions, so the highest-value assertions come from
driving those functions against a temp DB with a scripted ``input()`` and a
*deterministic* RNG, then reading back the rows they wrote.

Isolation mirrors the gym/cinema template: repoint ``DEFAULT_DB_PATH`` at a temp
file, build the schema via the package's own ``init_betting_db()`` (from
betting_core), add the unified ``transactions`` table the account funcs write to,
and stub ``helpers.get_auth`` (every submodule resolves the user through
``helpers.get_current_user``).
"""

import sqlite3
from unittest.mock import patch

import pytest

from education_system.post_18.university_system.modules.services.cli.betting_shop_cli import (
    account,
    casino,
    constants,
    helpers,
    sports,
)


class _FakeAuth:
    def __init__(self, current_user):
        self.current_user = current_user


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _exec(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def bet_db(tmp_path, monkeypatch):
    """Temp DB + betting schema + unified transactions table + logged-in student."""
    db_path = str(tmp_path / "betting.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert constants.init_betting_db() is True
    # The account funcs record to the shared 'transactions' table, which the
    # betting schema does not own. Create the minimal columns they touch.
    _exec(
        db_path,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT,
            student_id TEXT,
            transaction_type TEXT,
            amount REAL,
            balance_before REAL,
            balance_after REAL,
            description TEXT,
            payment_method TEXT,
            created_at TEXT
        )
        """,
    )

    fake = _FakeAuth({"username": "bob", "email": "bob@uni.ac.uk", "role": "student"})
    monkeypatch.setattr(helpers, "get_auth", lambda: fake)
    return db_path, fake


def _seed_account(db_path, balance=0.0):
    _exec(
        db_path,
        "INSERT INTO betting_accounts (user_id, username, email, balance) VALUES (?, ?, ?, ?)",
        ("bob", "bob", "bob@uni.ac.uk", balance),
    )


# ---------------------------------------------------------------------------
# Pure helpers / constants
# ---------------------------------------------------------------------------


class TestHelpersAndConstants:
    def test_get_current_user_returns_dict(self, bet_db):
        assert helpers.get_current_user()["username"] == "bob"

    def test_get_current_user_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(helpers, "get_auth", lambda: None)
        assert helpers.get_current_user() is None

    def test_get_current_user_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(helpers, "get_auth", lambda: _FakeAuth(None))
        assert helpers.get_current_user() is None

    def test_is_admin_gate(self, monkeypatch):
        monkeypatch.setattr(helpers, "get_auth", lambda: _FakeAuth({"role": "admin"}))
        assert helpers.is_admin() is True
        monkeypatch.setattr(helpers, "get_auth", lambda: _FakeAuth({"role": "student"}))
        assert helpers.is_admin() is False
        monkeypatch.setattr(helpers, "get_auth", lambda: None)
        assert helpers.is_admin() is False

    def test_bet_limits_sane(self):
        assert constants.MIN_BET < constants.MAX_BET
        assert constants.MIN_DEPOSIT < constants.MAX_DEPOSIT
        assert "slots" in constants.CASINO_GAMES


class TestInitDb:
    def test_creates_core_tables(self, bet_db):
        db_path, _ = bet_db
        names = {
            r["name"]
            for r in _rows(db_path, "SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"betting_accounts", "sports_bets", "casino_games"} <= names


# ---------------------------------------------------------------------------
# Account: view / deposit / withdraw
# ---------------------------------------------------------------------------


class TestAccount:
    @patch("builtins.print")
    def test_view_balance_requires_login(self, _p, bet_db, monkeypatch):
        monkeypatch.setattr(helpers, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert account.view_balance() is None

    @patch("builtins.print")
    def test_view_balance_autocreates_account(self, _p, bet_db):
        db_path, _ = bet_db
        with patch("builtins.input", return_value=""):
            account.view_balance()
        rows = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id = 'bob'")
        assert len(rows) == 1
        assert float(rows[0]["balance"]) == 0.0

    @patch("builtins.print")
    def test_deposit_happy_path(self, _p, bet_db):
        db_path, _ = bet_db
        # method=Cash(1), amount=100, final Enter
        with patch("builtins.input", side_effect=["1", "100", ""]):
            account.deposit_funds()
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id = 'bob'")[0]
        assert float(acct["balance"]) == 100.0
        assert float(acct["total_deposited"]) == 100.0
        txns = _rows(db_path, "SELECT * FROM transactions WHERE source_type='betting'")
        assert len(txns) == 1
        assert txns[0]["transaction_type"] == "deposit"
        assert float(txns[0]["balance_after"]) == 100.0

    @patch("builtins.print")
    def test_deposit_below_minimum_rejected(self, _p, bet_db):
        db_path, _ = bet_db
        with patch("builtins.input", side_effect=["1", "5", ""]):
            account.deposit_funds()
        assert _rows(db_path, "SELECT * FROM betting_accounts") == []
        assert _rows(db_path, "SELECT * FROM transactions") == []

    @patch("builtins.print")
    def test_deposit_cancel(self, _p, bet_db):
        db_path, _ = bet_db
        with patch("builtins.input", side_effect=["0"]):
            account.deposit_funds()
        assert _rows(db_path, "SELECT * FROM transactions") == []

    @patch("builtins.print")
    def test_withdraw_happy_path(self, _p, bet_db):
        db_path, _ = bet_db
        _seed_account(db_path, balance=200.0)
        # method=Bank(1), amount=50, confirm yes, final Enter
        with patch("builtins.input", side_effect=["1", "50", "yes", ""]):
            account.withdraw_funds()
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id = 'bob'")[0]
        assert float(acct["balance"]) == 150.0
        assert float(acct["total_withdrawn"]) == 50.0
        txns = _rows(db_path, "SELECT * FROM transactions WHERE transaction_type='withdrawal'")
        assert len(txns) == 1

    @patch("builtins.print")
    def test_withdraw_insufficient_balance(self, _p, bet_db):
        db_path, _ = bet_db
        _seed_account(db_path, balance=30.0)
        with patch("builtins.input", side_effect=["1", "500", ""]):
            account.withdraw_funds()
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id = 'bob'")[0]
        assert float(acct["balance"]) == 30.0  # unchanged
        assert _rows(db_path, "SELECT * FROM transactions") == []

    @patch("builtins.print")
    def test_view_transaction_history_empty(self, _p, bet_db):
        with patch("builtins.input", return_value=""):
            assert account.view_transaction_history() is None


# ---------------------------------------------------------------------------
# Casino: deterministic win/loss math via patched RNG
# ---------------------------------------------------------------------------


class TestCasinoSlots:
    @patch("builtins.print")
    def test_slots_jackpot_pays_100x(self, _p, bet_db, monkeypatch):
        db_path, _ = bet_db
        _seed_account(db_path, balance=500.0)
        monkeypatch.setattr(casino.time, "sleep", lambda *a, **k: None)
        # Force three 7s -> 100x payout.
        monkeypatch.setattr(casino.random, "choices", lambda *a, **k: ["7️⃣"])
        with patch("builtins.input", side_effect=["10", ""]):
            casino.play_slots()

        game = _rows(db_path, "SELECT * FROM casino_games WHERE user_id='bob'")[0]
        assert game["result"] == "win"
        assert float(game["win_amount"]) == 1000.0  # 10 * 100
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        # 500 - 10 stake + 1000 win
        assert float(acct["balance"]) == 1490.0
        assert float(acct["total_wagered"]) == 10.0
        assert float(acct["total_won"]) == 1000.0

    @patch("builtins.print")
    def test_slots_loss_deducts_stake_only(self, _p, bet_db, monkeypatch):
        db_path, _ = bet_db
        _seed_account(db_path, balance=100.0)
        monkeypatch.setattr(casino.time, "sleep", lambda *a, **k: None)
        # Three distinct non-cherry symbols -> no match, no win.
        monkeypatch.setattr(
            casino.random, "choices", lambda *a, **k: [["🍋"], ["🍊"], ["🍇"]].pop(0)
        )
        with patch("builtins.input", side_effect=["10", ""]):
            casino.play_slots()

        game = _rows(db_path, "SELECT * FROM casino_games WHERE user_id='bob'")[0]
        assert game["result"] == "lose"
        assert float(game["win_amount"]) == 0.0
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 90.0

    @patch("builtins.print")
    def test_slots_requires_account(self, _p, bet_db):
        # No account seeded -> guard fires, nothing written.
        db_path, _ = bet_db
        with patch("builtins.input", return_value=""):
            casino.play_slots()
        assert _rows(db_path, "SELECT * FROM casino_games") == []


# ---------------------------------------------------------------------------
# Sports betting: place a single bet + balance guard
# ---------------------------------------------------------------------------


def _seed_event(db_path):
    _exec(
        db_path,
        """
        INSERT INTO betting_events
        (event_name, event_type, sport_type, team_a, team_b, odds_a, odds_b, odds_draw,
         event_date, event_time, status)
        VALUES ('Reds vs Blues', 'match', 'football', 'Reds', 'Blues', 2.00, 3.00, 3.50,
                '2030-01-01', '15:00', 'upcoming')
        """,
    )


class TestSportsBet:
    @patch("builtins.print")
    def test_place_single_bet_happy_path(self, _p, bet_db):
        db_path, _ = bet_db
        _seed_event(db_path)
        _seed_account(db_path, balance=200.0)
        # event 1, bet type single(1), selection team_a(1), stake 20, confirm yes, Enter
        with patch("builtins.input", side_effect=["1", "1", "1", "20", "yes", ""]):
            sports.place_sports_bet()

        bets = _rows(db_path, "SELECT * FROM sports_bets WHERE user_id='bob'")
        assert len(bets) == 1
        assert bets[0]["status"] == "pending"
        assert bets[0]["selection"] == "Reds"
        assert float(bets[0]["stake"]) == 20.0
        assert float(bets[0]["potential_return"]) == 40.0  # 20 * 2.00
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 180.0
        assert float(acct["total_wagered"]) == 20.0

    @patch("builtins.print")
    def test_place_bet_insufficient_balance(self, _p, bet_db):
        db_path, _ = bet_db
        _seed_event(db_path)
        _seed_account(db_path, balance=5.0)
        with patch("builtins.input", side_effect=["1", "1", "1", "20", ""]):
            sports.place_sports_bet()
        assert _rows(db_path, "SELECT * FROM sports_bets") == []
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 5.0  # unchanged

    @patch("builtins.print")
    def test_place_bet_requires_login(self, _p, bet_db, monkeypatch):
        monkeypatch.setattr(helpers, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert sports.place_sports_bet() is None

    @patch("builtins.print")
    def test_view_my_bets_empty(self, _p, bet_db):
        with patch("builtins.input", side_effect=["1", ""]):
            assert sports.view_my_bets() is None
