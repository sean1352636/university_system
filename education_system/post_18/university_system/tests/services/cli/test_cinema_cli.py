"""Behavioral tests for the Cinema CLI package (``modules.services.cli.cinema_cli``).

The ``cinema_cli`` package splits its logic across submodules (``db``, ``utils``,
``constants``, ``membership``, ``booking``, ``movies``, ``screenings`` ...). The
testable surface mirrors the gym-CLI template:

* pure catalog constants and the points calculator,
* auth resolution (``utils.get_current_user`` / ``is_staff_or_admin``),
* DB-backed membership actions driven with scripted ``input()`` against a temp DB,
* read views that must render without raising.

Isolation: repoint the shared ``DEFAULT_DB_PATH`` at a temp file (``get_connection``
/ ``transaction`` read it at call time), build the schema via the package's own
``init_cinema_db()``, and stub the ``get_auth`` seam in ``utils`` (every submodule
resolves the user through ``utils.get_current_user``). Activity logging is disabled.
"""

import sqlite3
from unittest.mock import patch

import pytest

from education_system.post_18.university_system.modules.services.cli.cinema_cli import (
    booking,
    constants,
    db,
    membership,
    utils,
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


@pytest.fixture()
def cinema_db(tmp_path, monkeypatch):
    """Temp DB + cinema schema, a logged-in student, side effects neutralised."""
    db_path = str(tmp_path / "cinema.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert db.init_cinema_db() is True

    fake = _FakeAuth(
        {
            "username": "alice",
            "full_name": "Alice Anderson",
            "email": "alice@uni.ac.uk",
            "role": "student",
        }
    )
    monkeypatch.setattr(utils, "get_auth", lambda: fake)
    # Never touch the activity store from within write actions.
    monkeypatch.setattr(membership, "ACTIVITY_LOGGING", False)
    monkeypatch.setattr(booking, "ACTIVITY_LOGGING", False)
    return db_path, fake


# ---------------------------------------------------------------------------
# Pure catalog + points math
# ---------------------------------------------------------------------------


class TestConstantsAndMath:
    def test_ticket_types_wellformed(self):
        assert "Adult" in constants.TICKET_TYPES
        assert all(isinstance(p, (int, float)) for p in constants.TICKET_TYPES.values())

    def test_snacks_menu_wellformed(self):
        assert constants.SNACKS_MENU
        assert all(isinstance(p, (int, float)) and p > 0 for p in constants.SNACKS_MENU.values())

    def test_combo_deals_wellformed(self):
        for details in constants.COMBO_DEALS.values():
            assert isinstance(details["items"], list) and details["items"]
            assert isinstance(details["price"], (int, float))

    def test_membership_pricing_constants(self):
        assert constants.MEMBERSHIP_PRICE > 0
        assert 0 < constants.MEMBER_DISCOUNT < 1

    def test_calculate_points_earned_floors_to_int(self):
        assert membership.calculate_points_earned(12.99) == 12
        assert membership.calculate_points_earned(0) == 0
        assert isinstance(membership.calculate_points_earned(50.5), int)


# ---------------------------------------------------------------------------
# Auth resolution
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    def test_returns_current_user_dict(self, cinema_db):
        assert utils.get_current_user()["username"] == "alice"

    def test_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(utils, "get_auth", lambda: None)
        assert utils.get_current_user() is None

    def test_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(utils, "get_auth", lambda: _FakeAuth(None))
        assert utils.get_current_user() is None

    def test_is_staff_or_admin(self):
        assert utils.is_staff_or_admin({"role": "admin"}) is True
        assert utils.is_staff_or_admin({"role": "staff"}) is True
        assert utils.is_staff_or_admin({"role": "student"}) is False
        assert utils.is_staff_or_admin(None) is False


# ---------------------------------------------------------------------------
# init_cinema_db seeds catalog
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_seeds_movies_and_screenings(self, cinema_db):
        db_path, _ = cinema_db
        movies = _rows(db_path, "SELECT * FROM cinema_movies")
        assert len(movies) > 0
        screenings = _rows(db_path, "SELECT * FROM cinema_screenings")
        assert len(screenings) > 0


# ---------------------------------------------------------------------------
# join_membership (scripted input) + points helpers
# ---------------------------------------------------------------------------


class TestMembershipWrites:
    @patch("builtins.print")
    def test_join_requires_login(self, _p, monkeypatch):
        monkeypatch.setattr(utils, "get_auth", lambda: None)
        assert membership.join_membership() is None

    @patch("builtins.print")
    def test_join_happy_path_persists_active_member(self, _p, cinema_db):
        db_path, _ = cinema_db
        with patch("builtins.input", side_effect=["yes", ""]):
            membership.join_membership()

        rows = _rows(db_path, "SELECT * FROM cinema_memberships WHERE user_id = 'alice'")
        assert len(rows) == 1
        assert rows[0]["status"] == "active"
        assert rows[0]["points_balance"] == 100  # welcome bonus
        # A welcome-bonus points transaction is recorded.
        txns = _rows(db_path, "SELECT * FROM cinema_points_transactions WHERE user_id = 'alice'")
        assert any(t["description"] == "Welcome bonus" for t in txns)

    @patch("builtins.print")
    def test_join_declined_writes_nothing(self, _p, cinema_db):
        db_path, _ = cinema_db
        with patch("builtins.input", side_effect=["no", ""]):
            membership.join_membership()
        assert _rows(db_path, "SELECT * FROM cinema_memberships") == []

    @patch("builtins.print")
    def test_join_blocks_second_membership(self, _p, cinema_db):
        db_path, _ = cinema_db
        with patch("builtins.input", side_effect=["yes", ""]):
            membership.join_membership()
        with patch("builtins.input", side_effect=["yes", ""]):
            membership.join_membership()
        assert len(_rows(db_path, "SELECT * FROM cinema_memberships")) == 1


# ---------------------------------------------------------------------------
# award / redeem points (called directly, as book_tickets does)
# ---------------------------------------------------------------------------


class TestPointsLedger:
    @patch("builtins.print")
    def _join(self, _p, cinema_db):
        with patch("builtins.input", side_effect=["yes", ""]):
            membership.join_membership()

    def test_get_user_membership_none_before_join(self, cinema_db):
        assert membership.get_user_membership("alice") is None

    def test_award_points_increases_balance(self, cinema_db):
        db_path, _ = cinema_db
        self._join(cinema_db)
        assert membership.award_points("alice", 50, "CINEMA-X", "test award") is True
        m = membership.get_user_membership("alice")
        assert m["points_balance"] == 150  # 100 welcome + 50
        assert m["total_points_earned"] == 50

    def test_redeem_points_deducts_when_affordable(self, cinema_db):
        self._join(cinema_db)
        assert membership.redeem_points("alice", 40, "test redeem") is True
        assert membership.get_user_membership("alice")["points_balance"] == 60

    def test_redeem_points_rejected_when_insufficient(self, cinema_db):
        self._join(cinema_db)
        assert membership.redeem_points("alice", 500, "too many") is False
        assert membership.get_user_membership("alice")["points_balance"] == 100


# ---------------------------------------------------------------------------
# read views render cleanly
# ---------------------------------------------------------------------------


class TestReadViews:
    @patch("builtins.print")
    def test_view_my_bookings_empty(self, _p, cinema_db):
        with patch("builtins.input", return_value=""):
            assert booking.view_my_bookings() is None

    @patch("builtins.print")
    def test_view_my_bookings_requires_login(self, _p, monkeypatch):
        monkeypatch.setattr(utils, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert booking.view_my_bookings() is None

    @patch("builtins.print")
    def test_view_points_history_after_join(self, _p, cinema_db):
        with patch("builtins.input", side_effect=["yes", ""]):
            membership.join_membership()
        with patch("builtins.input", return_value=""):
            assert membership.view_points_history() is None
