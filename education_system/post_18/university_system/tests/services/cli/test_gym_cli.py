"""Behavioral tests for the Gym CLI (``modules.services.cli.gym_cli``).

CLI modules are interactive: they read the current user via ``get_auth()`` and drive
menus with ``input()`` / ``print()``. The testable surface is:

* pure helpers (id/ref generators, catalog constants),
* auth resolution (``get_current_user``),
* DB-backed actions, driven with a scripted ``input()`` sequence against a temp DB.

Isolation mirrors the service-bus tests: repoint the shared ``DEFAULT_DB_PATH`` at a
temp file (``get_connection``/``transaction`` read it at call time), create the schema
via the module's own ``init_gym_db()``, and stub the seams (``get_auth``,
``log_activity``, finance/email fan-out) so nothing escapes the test.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import gym_cli


class _FakeAuth:
    def __init__(self, current_user):
        self.current_user = current_user


@pytest.fixture()
def gym_db(tmp_path, monkeypatch):
    """Temp DB + gym schema, with a logged-in student and neutralised side effects.

    Returns the db path so tests can inspect rows directly.
    """
    db_path = str(tmp_path / "gym.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Build the gym tables via the module's own initialiser.
    assert gym_cli.init_gym_db() is True

    # A logged-in student by default; tests can override current_user.
    fake = _FakeAuth({"id": "S001", "username": "alice", "email": "alice@uni.ac.uk"})
    monkeypatch.setattr(gym_cli, "get_auth", lambda: fake)
    # Don't write to the activity store; don't hit finance.
    if hasattr(gym_cli, "log_activity"):
        monkeypatch.setattr(gym_cli, "log_activity", lambda *a, **k: None)
    if hasattr(gym_cli, "FINANCE_AVAILABLE"):
        monkeypatch.setattr(gym_cli, "FINANCE_AVAILABLE", False)
    return db_path, fake


# ---------------------------------------------------------------------------
# Pure helpers & catalog
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_membership_id_shape(self):
        mid = gym_cli.generate_membership_id()
        assert mid.startswith("GYM-")
        assert len(mid) > len("GYM-")

    def test_generate_booking_ref_shape(self):
        assert gym_cli.generate_booking_ref().startswith("BK-")

    def test_generate_reference_shape(self):
        assert gym_cli.generate_reference().startswith("REF-")

    def test_generated_ids_are_unique(self):
        assert gym_cli.generate_membership_id() != gym_cli.generate_membership_id()

    def test_membership_catalog_wellformed(self):
        assert "student" in gym_cli.MEMBERSHIP_TYPES
        for details in gym_cli.MEMBERSHIP_TYPES.values():
            assert "name" in details
            assert isinstance(details["monthly_fee"], (int, float))
            assert isinstance(details["features"], list)


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_current_user_dict(self, gym_db):
        user = gym_cli.get_current_user()
        assert user["username"] == "alice"

    def test_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(gym_cli, "get_auth", lambda: None)
        assert gym_cli.get_current_user() is None

    def test_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(gym_cli, "get_auth", lambda: _FakeAuth(None))
        assert gym_cli.get_current_user() is None


# ---------------------------------------------------------------------------
# register_membership (scripted input)
# ---------------------------------------------------------------------------

def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


class TestRegisterMembership:
    @patch("builtins.print")
    def test_requires_login(self, _p, monkeypatch):
        # No temp DB needed; guard fires before any DB access.
        monkeypatch.setattr(gym_cli, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert gym_cli.register_membership() is None

    @patch("builtins.print")
    def test_happy_path_persists_active_membership(self, _p, gym_db):
        db_path, _ = gym_db
        # select type 4 (student), 6-month duration, confirm yes, final Enter.
        script = ["4", "6", "yes", ""]
        with patch("builtins.input", side_effect=script):
            gym_cli.register_membership()

        rows = _rows(db_path, "SELECT * FROM gym_memberships WHERE user_id = 'S001'")
        assert len(rows) == 1
        assert rows[0]["status"] == "active"
        assert rows[0]["membership_type"] == "student"
        assert rows[0]["user_name"] == "alice"

    @patch("builtins.print")
    def test_declined_confirmation_writes_nothing(self, _p, gym_db):
        db_path, _ = gym_db
        script = ["4", "6", "no", ""]
        with patch("builtins.input", side_effect=script):
            gym_cli.register_membership()
        assert _rows(db_path, "SELECT * FROM gym_memberships") == []

    @patch("builtins.print")
    def test_invalid_selection_writes_nothing(self, _p, gym_db):
        db_path, _ = gym_db
        script = ["999", ""]  # out-of-range choice -> early return
        with patch("builtins.input", side_effect=script):
            gym_cli.register_membership()
        assert _rows(db_path, "SELECT * FROM gym_memberships") == []

    @patch("builtins.print")
    def test_blocks_second_active_membership(self, _p, gym_db):
        db_path, _ = gym_db
        with patch("builtins.input", side_effect=["4", "6", "yes", ""]):
            gym_cli.register_membership()
        # Second attempt must be refused by the active-membership guard.
        with patch("builtins.input", side_effect=["4", "6", "yes", ""]):
            gym_cli.register_membership()
        assert len(_rows(db_path, "SELECT * FROM gym_memberships")) == 1


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_membership_no_membership(self, _p, gym_db):
        # Logged-in user with no membership: must not raise.
        with patch("builtins.input", return_value=""):
            assert gym_cli.view_membership() is None

    @patch("builtins.print")
    def test_view_classes_lists_seeded_classes(self, _p, gym_db):
        # init_gym_db seeds sample classes; the view must render without error.
        with patch("builtins.input", return_value=""):
            assert gym_cli.view_classes() is None
