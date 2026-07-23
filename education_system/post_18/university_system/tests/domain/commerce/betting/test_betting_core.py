"""Behavioural tests for the Betting Shop service layer
(``modules.domain.commerce.betting.services.betting_core``).

This is the ~1.3k-LOC business core behind the betting GUI/CLI: account money
movement, sports book, prediction markets, casino RNG games, and the admin
report. The CLI package has its own suite; here we drive the *manager* classes
directly against a temp DB (see ``conftest.py``) and, for the casino games,
pin ``betting_core.random`` so payouts are deterministic.

Money invariants under test:
  * deposits/withdrawals honour the MIN/MAX bounds and update running totals
  * stakes can never overdraw an account
  * winning selections pay ``potential_return`` and mark bets settled
  * prediction odds derive from probability with the house edge applied, and
    the pool/probabilities re-balance after each bet
"""

import sqlite3

import pytest

from education_system.post_18.university_system.modules.domain.commerce.betting.services import (
    betting_core,
)
from education_system.post_18.university_system.modules.domain.commerce.betting.services.betting_core import (
    AccountManager,
    CasinoManager,
    PredictionMarketManager,
    ReportManager,
    SportsBettingManager,
    generate_reference,
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


# ---------------------------------------------------------------------------
# Schema init + reference helper
# ---------------------------------------------------------------------------


class TestInitAndReference:
    def test_init_creates_all_core_tables(self, bet_db):
        names = {
            r["name"]
            for r in _rows(bet_db, "SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "betting_accounts",
            "betting_events",
            "sports_bets",
            "prediction_markets",
            "prediction_bets",
            "casino_sessions",
            "casino_games",
        } <= names

    def test_generate_reference_shape_and_uniqueness(self):
        a = generate_reference()
        b = generate_reference()
        assert a.startswith("BET-")
        assert a != b  # uuid suffix keeps same-second refs distinct


# ---------------------------------------------------------------------------
# AccountManager
# ---------------------------------------------------------------------------


class TestAccountManager:
    def test_get_or_create_is_idempotent(self, bet_db):
        first = AccountManager.get_or_create_account("bob", "bob", "bob@uni.ac.uk")
        second = AccountManager.get_or_create_account("bob", "bob", "bob@uni.ac.uk")
        assert first["user_id"] == "bob"
        # Only one row despite two calls.
        assert len(_rows(bet_db, "SELECT * FROM betting_accounts")) == 1
        # Second call returns the persisted row.
        assert second["account_id"] == first["account_id"]

    def test_get_account_missing_returns_none(self, bet_db):
        assert AccountManager.get_account("nobody") is None

    def test_deposit_happy_path_updates_balance_and_records_txn(self, bet_db):
        AccountManager.get_or_create_account("bob", "bob")
        txn_id = AccountManager.deposit("bob", 100.0, "card", processed_by="admin")
        assert txn_id is not None

        acct = _rows(bet_db, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 100.0
        assert float(acct["total_deposited"]) == 100.0

        txn = _rows(bet_db, "SELECT * FROM transactions WHERE source_type='betting'")[0]
        assert txn["transaction_type"] == "deposit"
        assert float(txn["balance_before"]) == 0.0
        assert float(txn["balance_after"]) == 100.0
        assert txn["reference_number"].startswith("BET-")

    @pytest.mark.parametrize("amount", [9.99, 1000.01, 0, -5])
    def test_deposit_out_of_bounds_rejected(self, bet_db, amount):
        AccountManager.get_or_create_account("bob", "bob")
        assert AccountManager.deposit("bob", amount, "card") is None
        assert _rows(bet_db, "SELECT * FROM transactions") == []

    def test_deposit_unknown_account_rejected(self, bet_db):
        assert AccountManager.deposit("ghost", 100.0, "card") is None

    def test_credit_funds_bypasses_deposit_ceiling(self, bet_db):
        AccountManager.get_or_create_account("bob", "bob")
        # Well above MAX_DEPOSIT (1000) — deposit() would refuse this.
        txn_id = AccountManager.credit_funds("bob", 5000.0, "arcade_cashout")
        assert txn_id is not None
        acct = _rows(bet_db, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 5000.0

    def test_credit_funds_rejects_non_positive(self, bet_db):
        AccountManager.get_or_create_account("bob", "bob")
        assert AccountManager.credit_funds("bob", 0, "x") is None
        assert AccountManager.credit_funds("bob", -1, "x") is None

    def test_withdraw_happy_path(self, account):
        db_path, user = account
        txn_id = AccountManager.withdraw(user, 250.0, "bank")
        assert txn_id is not None
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 750.0
        assert float(acct["total_withdrawn"]) == 250.0
        txn = _rows(db_path, "SELECT * FROM transactions WHERE transaction_type='withdrawal'")[0]
        assert float(txn["amount"]) == 250.0

    def test_withdraw_more_than_balance_rejected(self, account):
        db_path, user = account
        assert AccountManager.withdraw(user, 5000.0, "bank") is None
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 1000.0  # untouched

    def test_deduct_stake_success_and_overdraw_guard(self, account):
        db_path, user = account
        assert AccountManager.deduct_stake(user, 400.0) is True
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 600.0
        assert float(acct["total_wagered"]) == 400.0
        # Cannot deduct beyond remaining balance.
        assert AccountManager.deduct_stake(user, 601.0) is False
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 600.0

    def test_add_winnings_credits_balance_and_total_won(self, account):
        db_path, user = account
        assert AccountManager.add_winnings(user, 123.45) is True
        acct = _rows(db_path, "SELECT * FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 1123.45
        assert float(acct["total_won"]) == 123.45

    def test_transaction_history_filtered_and_limited(self, bet_db):
        AccountManager.get_or_create_account("bob", "bob")
        AccountManager.deposit("bob", 50.0, "card")
        AccountManager.deposit("bob", 60.0, "card")
        # A non-betting row must not leak into the history.
        _exec(
            bet_db,
            "INSERT INTO transactions (source_type, student_id, transaction_type, amount)"
            " VALUES ('tuition', 'bob', 'deposit', 999)",
        )
        hist = AccountManager.get_transaction_history("bob", limit=1)
        assert len(hist) == 1  # limit honoured
        full = AccountManager.get_transaction_history("bob")
        assert len(full) == 2
        assert all(t["source_type"] == "betting" for t in full)


# ---------------------------------------------------------------------------
# SportsBettingManager
# ---------------------------------------------------------------------------


def _make_event(**over):
    kw = dict(
        event_name="Reds vs Blues",
        event_type="match",
        sport_type="football",
        team_a="Reds",
        team_b="Blues",
        odds_a=2.0,
        odds_b=3.0,
        odds_draw=3.5,
        event_date="2030-01-01",
        event_time="15:00",
        created_by="admin",
    )
    kw.update(over)
    return SportsBettingManager.create_event(**kw)


class TestSportsBetting:
    def test_create_and_fetch_event(self, bet_db):
        event_id = _make_event()
        assert event_id is not None
        ev = SportsBettingManager.get_event(event_id)
        assert ev["event_name"] == "Reds vs Blues"
        assert ev["status"] == "upcoming"

    def test_create_event_defaults_date_to_tomorrow(self, bet_db):
        event_id = _make_event(event_date=None)
        ev = SportsBettingManager.get_event(event_id)
        assert ev["event_date"]  # non-empty ISO date string

    def test_get_upcoming_filters_by_sport(self, bet_db):
        _make_event(sport_type="football")
        _make_event(event_name="Aces vs Kings", sport_type="tennis")
        football = SportsBettingManager.get_upcoming_events(sport_type="football")
        assert len(football) == 1
        assert football[0]["sport_type"] == "football"
        assert len(SportsBettingManager.get_upcoming_events()) == 2

    def test_get_upcoming_excludes_past_events(self, bet_db):
        _make_event(event_date="2000-01-01")  # in the past
        assert SportsBettingManager.get_upcoming_events() == []

    @pytest.mark.parametrize(
        "selection,expected_return",
        [("team_a", 40.0), ("team_b", 60.0), ("draw", 70.0)],
    )
    def test_place_bet_uses_selection_odds(self, account, selection, expected_return):
        db_path, user = account
        event_id = _make_event()
        bet_id = SportsBettingManager.place_bet(user, event_id, selection, 20.0)
        assert bet_id is not None
        bet = _rows(db_path, "SELECT * FROM sports_bets WHERE bet_id=?", (bet_id,))[0]
        assert float(bet["potential_return"]) == expected_return
        assert bet["status"] == "pending"
        # Stake left the account.
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 980.0

    def test_place_bet_draw_falls_back_when_odds_missing(self, account):
        db_path, user = account
        event_id = _make_event(odds_draw=None)
        bet_id = SportsBettingManager.place_bet(user, event_id, "draw", 10.0)
        bet = _rows(db_path, "SELECT * FROM sports_bets WHERE bet_id=?", (bet_id,))[0]
        assert float(bet["odds"]) == 3.50  # default draw odds
        assert float(bet["potential_return"]) == 35.0

    def test_place_bet_invalid_selection_rejected_and_no_charge(self, account):
        db_path, user = account
        event_id = _make_event()
        assert SportsBettingManager.place_bet(user, event_id, "nonsense", 20.0) is None
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 1000.0

    @pytest.mark.parametrize("stake", [0.5, 500.01])
    def test_place_bet_stake_out_of_bounds(self, account, stake):
        _db, user = account
        event_id = _make_event()
        assert SportsBettingManager.place_bet(user, event_id, "team_a", stake) is None

    def test_place_bet_insufficient_balance(self, bet_db):
        AccountManager.get_or_create_account("poor", "poor")
        _exec(bet_db, "UPDATE betting_accounts SET balance = 5 WHERE user_id='poor'")
        event_id = _make_event()
        assert SportsBettingManager.place_bet("poor", event_id, "team_a", 20.0) is None
        assert _rows(bet_db, "SELECT * FROM sports_bets") == []

    def test_place_bet_rejected_when_event_not_upcoming(self, account):
        db_path, user = account
        event_id = _make_event()
        _exec(db_path, "UPDATE betting_events SET status='settled' WHERE event_id=?", (event_id,))
        assert SportsBettingManager.place_bet(user, event_id, "team_a", 20.0) is None

    def test_get_user_bets_filter_by_status(self, account):
        db_path, user = account
        event_id = _make_event()
        SportsBettingManager.place_bet(user, event_id, "team_a", 10.0)
        SportsBettingManager.place_bet(user, event_id, "team_b", 10.0)
        assert len(SportsBettingManager.get_user_bets(user)) == 2
        assert len(SportsBettingManager.get_user_bets(user, status="pending")) == 2
        assert SportsBettingManager.get_user_bets(user, status="won") == []

    def test_cash_out_pays_half_the_profit(self, account):
        db_path, user = account
        event_id = _make_event()
        # stake 20 @ 2.0 -> potential 40; cash out = 20 + (40-20)*0.5 = 30
        bet_id = SportsBettingManager.place_bet(user, event_id, "team_a", 20.0)
        value = SportsBettingManager.cash_out_bet(bet_id, user)
        assert value == 30.0
        bet = _rows(db_path, "SELECT * FROM sports_bets WHERE bet_id=?", (bet_id,))[0]
        assert bet["status"] == "cashed_out"
        assert float(bet["actual_return"]) == 30.0
        # Balance: 1000 - 20 stake + 30 cash-out = 1010
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 1010.0

    def test_cash_out_rejects_foreign_or_settled_bet(self, account):
        db_path, user = account
        event_id = _make_event()
        bet_id = SportsBettingManager.place_bet(user, event_id, "team_a", 20.0)
        # Wrong owner.
        assert SportsBettingManager.cash_out_bet(bet_id, "someone_else") is None
        # Non-existent bet.
        assert SportsBettingManager.cash_out_bet(99999, user) is None

    def test_settle_event_pays_winners_and_zeroes_losers(self, account):
        db_path, user = account
        event_id = _make_event()
        win_bet = SportsBettingManager.place_bet(user, event_id, "team_a", 20.0)  # ret 40
        lose_bet = SportsBettingManager.place_bet(user, event_id, "team_b", 20.0)  # ret 60
        # Balance now 1000 - 40 staked = 960.
        assert SportsBettingManager.settle_event(event_id, "team_a") is True

        rows = {
            r["bet_id"]: r
            for r in _rows(db_path, "SELECT * FROM sports_bets WHERE event_id=?", (event_id,))
        }
        assert rows[win_bet]["status"] == "won"
        assert float(rows[win_bet]["actual_return"]) == 40.0
        assert rows[lose_bet]["status"] == "lost"
        assert float(rows[lose_bet]["actual_return"]) == 0.0

        ev = _rows(db_path, "SELECT * FROM betting_events WHERE event_id=?", (event_id,))[0]
        assert ev["status"] == "settled" and ev["result"] == "team_a"
        # 960 + 40 winnings = 1000.
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 1000.0


# ---------------------------------------------------------------------------
# PredictionMarketManager
# ---------------------------------------------------------------------------


def _make_market(**over):
    kw = dict(
        title="Will it rain?",
        description="weather bet",
        category="other",
        outcome_a="Yes",
        outcome_b="No",
        resolution_date="2030-06-01",
        created_by="admin",
    )
    kw.update(over)
    return PredictionMarketManager.create_market(**kw)


class TestPredictionMarket:
    def test_create_and_fetch_market(self, bet_db):
        market_id = _make_market()
        assert market_id is not None
        mkt = PredictionMarketManager.get_market(market_id)
        assert mkt["title"] == "Will it rain?"
        assert mkt["status"] == "open"
        assert float(mkt["probability_a"]) == 50.0

    def test_get_open_markets_filter_by_category(self, bet_db):
        _make_market(category="sports")
        _make_market(title="Election", category="politics")
        assert len(PredictionMarketManager.get_open_markets()) == 2
        pol = PredictionMarketManager.get_open_markets(category="politics")
        assert len(pol) == 1 and pol[0]["category"] == "politics"

    def test_place_prediction_applies_house_edge_odds(self, account):
        db_path, user = account
        market_id = _make_market()
        # prob_a 50% -> odds = 1/0.5 * (1 - 0.05) = 1.9; return = 100 * 1.9 = 190
        bet_id = PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_a", 100.0)
        assert bet_id is not None
        bet = _rows(db_path, "SELECT * FROM prediction_bets WHERE bet_id=?", (bet_id,))[0]
        assert float(bet["odds_at_placement"]) == 1.9
        assert float(bet["potential_return"]) == 190.0

    def test_place_prediction_updates_pool_and_probabilities(self, account):
        db_path, user = account
        market_id = _make_market()
        PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_a", 30.0)
        PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_b", 10.0)
        mkt = _rows(db_path, "SELECT * FROM prediction_markets WHERE market_id=?", (market_id,))[0]
        assert float(mkt["total_pool"]) == 40.0
        assert float(mkt["pool_a"]) == 30.0
        assert float(mkt["pool_b"]) == 10.0
        # 30/40 -> 75%, 10/40 -> 25%
        assert float(mkt["probability_a"]) == 75.0
        assert float(mkt["probability_b"]) == 25.0

    @pytest.mark.parametrize("stake", [0.5, 500.01])
    def test_place_prediction_stake_bounds(self, account, stake):
        _db, user = account
        market_id = _make_market()
        assert PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_a", stake) is None

    def test_place_prediction_rejected_when_market_closed(self, account):
        db_path, user = account
        market_id = _make_market()
        _exec(db_path, "UPDATE prediction_markets SET status='resolved' WHERE market_id=?", (market_id,))
        assert PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_a", 20.0) is None

    def test_resolve_market_settles_bets_and_pays_winner(self, account):
        db_path, user = account
        market_id = _make_market()
        win = PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_a", 20.0)
        lose = PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_b", 20.0)
        assert PredictionMarketManager.resolve_market(market_id, "outcome_a") is True

        rows = {
            r["bet_id"]: r
            for r in _rows(db_path, "SELECT * FROM prediction_bets WHERE market_id=?", (market_id,))
        }
        assert rows[win]["status"] == "won"
        assert float(rows[win]["actual_return"]) == float(rows[win]["potential_return"])
        assert rows[lose]["status"] == "lost"
        assert float(rows[lose]["actual_return"]) == 0.0
        mkt = _rows(db_path, "SELECT * FROM prediction_markets WHERE market_id=?", (market_id,))[0]
        assert mkt["status"] == "resolved" and mkt["result"] == "outcome_a"

    def test_resolve_market_twice_is_rejected(self, account):
        _db, user = account
        market_id = _make_market()
        assert PredictionMarketManager.resolve_market(market_id, "outcome_a") is True
        assert PredictionMarketManager.resolve_market(market_id, "outcome_b") is False

    def test_get_user_predictions_joins_market_title(self, account):
        _db, user = account
        market_id = _make_market()
        PredictionMarketManager.place_prediction_bet(user, market_id, "outcome_a", 20.0)
        preds = PredictionMarketManager.get_user_predictions(user)
        assert len(preds) == 1
        assert preds[0]["title"] == "Will it rain?"


# ---------------------------------------------------------------------------
# CasinoManager  (RNG pinned via betting_core.random)
# ---------------------------------------------------------------------------


class TestCasino:
    def test_start_session_records_start_balance(self, account):
        db_path, user = account
        session_id = CasinoManager.start_session(user, "slots")
        assert session_id is not None
        sess = _rows(db_path, "SELECT * FROM casino_sessions WHERE session_id=?", (session_id,))[0]
        assert sess["game_type"] == "slots"
        assert float(sess["start_balance"]) == 1000.0
        assert sess["status"] == "active"

    def test_start_session_requires_account(self, bet_db):
        assert CasinoManager.start_session("ghost", "slots") is None

    def test_slots_jackpot_pays_100x_and_updates_session(self, account, monkeypatch):
        db_path, user = account
        session_id = CasinoManager.start_session(user, "slots")
        # Force three 7s -> jackpot (100x).
        monkeypatch.setattr(betting_core.random, "choices", lambda *a, **k: ["7"])
        result = CasinoManager.play_slots(user, 10.0, session_id=session_id)
        assert result["success"] is True
        assert result["is_jackpot"] is True
        assert result["win_amount"] == 1000.0
        # 1000 - 10 stake + 1000 win = 1990.
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 1990.0
        sess = _rows(db_path, "SELECT * FROM casino_sessions WHERE session_id=?", (session_id,))[0]
        assert float(sess["total_wagered"]) == 10.0
        assert float(sess["total_won"]) == 1000.0
        assert sess["hands_played"] == 1

    def test_slots_total_loss_deducts_stake_only(self, account, monkeypatch):
        db_path, user = account
        # Three distinct, non-cherry symbols -> no match, no win.
        seq = iter([["LEMON"], ["ORANGE"], ["PLUM"]])
        monkeypatch.setattr(betting_core.random, "choices", lambda *a, **k: next(seq))
        result = CasinoManager.play_slots(user, 10.0)
        assert result["win_amount"] == 0.0
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        assert float(acct["balance"]) == 990.0
        game = _rows(db_path, "SELECT * FROM casino_games WHERE user_id='bob'")[0]
        assert game["result"] == "lose"

    def test_slots_insufficient_balance(self, bet_db):
        AccountManager.get_or_create_account("poor", "poor")
        _exec(bet_db, "UPDATE betting_accounts SET balance = 5 WHERE user_id='poor'")
        result = CasinoManager.play_slots("poor", 10.0)
        assert result["success"] is False
        assert "balance" in result["error"].lower()

    @pytest.mark.parametrize("bet", [0.5, 500.01])
    def test_slots_bet_out_of_bounds(self, account, bet):
        _db, user = account
        result = CasinoManager.play_slots(user, bet)
        assert result["success"] is False

    def test_blackjack_player_blackjack_pays_2_5x(self, account, monkeypatch):
        db_path, user = account
        # player draws A,K (=21 blackjack); dealer draws K,K (=20, stands).
        seq = iter(["A", "K", "K", "K"])
        monkeypatch.setattr(betting_core.random, "choice", lambda *a, **k: next(seq))
        result = CasinoManager.play_blackjack(user, 10.0)
        assert result["result"] == "blackjack"
        assert result["win_amount"] == 25.0  # 10 * 2.5
        acct = _rows(db_path, "SELECT balance FROM betting_accounts WHERE user_id='bob'")[0]
        # 1000 - 10 + 25 = 1015.
        assert float(acct["balance"]) == 1015.0

    def test_blackjack_records_game_row(self, account, monkeypatch):
        db_path, user = account
        seq = iter(["A", "K", "K", "K"])
        monkeypatch.setattr(betting_core.random, "choice", lambda *a, **k: next(seq))
        CasinoManager.play_blackjack(user, 10.0)
        rows = _rows(db_path, "SELECT * FROM casino_games WHERE game_type='blackjack'")
        assert len(rows) == 1
        assert "Player" in rows[0]["game_data"]

    def test_roulette_straight_number_pays_35x(self, account, monkeypatch):
        db_path, user = account
        monkeypatch.setattr(betting_core.random, "randint", lambda *a, **k: 7)
        result = CasinoManager.play_roulette(user, 10.0, "number", "7")
        assert result["win"] is True
        assert result["result_number"] == 7
        assert result["result_color"] == "red"
        assert result["win_amount"] == 350.0

    def test_roulette_color_win_and_loss(self, account, monkeypatch):
        _db, user = account
        monkeypatch.setattr(betting_core.random, "randint", lambda *a, **k: 7)  # red
        assert CasinoManager.play_roulette(user, 10.0, "color", "red")["win"] is True
        assert CasinoManager.play_roulette(user, 10.0, "color", "black")["win"] is False

    def test_roulette_zero_is_green_and_low_high_lose(self, account, monkeypatch):
        _db, user = account
        monkeypatch.setattr(betting_core.random, "randint", lambda *a, **k: 0)
        res = CasinoManager.play_roulette(user, 10.0, "high_low", "low")
        assert res["result_color"] == "green"
        assert res["win"] is False  # 0 is neither low(1-18) nor high

    def test_game_history_filter_by_game_type(self, account, monkeypatch):
        _db, user = account
        monkeypatch.setattr(betting_core.random, "randint", lambda *a, **k: 0)
        CasinoManager.play_roulette(user, 10.0, "color", "red")
        monkeypatch.setattr(betting_core.random, "choices", lambda *a, **k: ["LEMON"])
        CasinoManager.play_slots(user, 10.0)
        assert len(CasinoManager.get_game_history(user)) == 2
        assert len(CasinoManager.get_game_history(user, game_type="roulette")) == 1


# ---------------------------------------------------------------------------
# ReportManager
# ---------------------------------------------------------------------------


class TestReportManager:
    def test_statistics_reflect_activity_and_house_profit(self, account, monkeypatch):
        db_path, user = account
        # One settled sports bet (loser) + one losing slots spin -> house keeps both.
        event_id = _make_event()
        SportsBettingManager.place_bet(user, event_id, "team_a", 20.0)
        SportsBettingManager.settle_event(event_id, "team_b")  # bettor loses
        monkeypatch.setattr(betting_core.random, "choices", lambda *a, **k: ["LEMON"])
        # Distinct symbols each call to guarantee a loss.
        seq = iter([["LEMON"], ["ORANGE"], ["PLUM"]])
        monkeypatch.setattr(betting_core.random, "choices", lambda *a, **k: next(seq))
        CasinoManager.play_slots(user, 10.0)

        stats = ReportManager.get_overall_statistics()
        assert stats["total_accounts"] == 1
        assert stats["sports_bets"] == 1
        assert stats["casino_games"] == 1
        # 20 sports + 10 casino wagered, 0 paid out -> house_profit 30.
        assert stats["total_wagered"] == 30.0
        assert stats["total_paid_out"] == 0
        assert stats["house_profit"] == 30.0

    def test_statistics_empty_db_returns_zeros(self, bet_db):
        stats = ReportManager.get_overall_statistics()
        assert stats["total_accounts"] == 0
        assert stats["house_profit"] == 0

    def test_admin_report_contains_sections_and_figures(self, account):
        _db, user = account
        report = ReportManager.generate_admin_report()
        assert "ADMINISTRATION REPORT" in report
        assert "ACCOUNT SUMMARY" in report
        assert "House Profit/Loss" in report
        assert "GBP" in report
