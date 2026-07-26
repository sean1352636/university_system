"""Behavioral tests for the Bar/Pub CLI (``modules.services.cli.bar_cli``).

Mirrors the gym-CLI test approach: repoint the shared ``DEFAULT_DB_PATH`` at a
temp file (``get_connection``/``transaction`` read it at call time), build the
schema via the module's own ``init_bar_db()``, and stub the seams
(``get_auth``, ``log_activity``, finance fan-out). Interactive actions are driven
with scripted ``input()`` and inspected against the temp DB.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import bar_cli


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
def bar_db(tmp_path, monkeypatch):
    """Temp DB + bar schema, a logged-in staff user, side effects neutralised."""
    db_path = str(tmp_path / "bar.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert bar_cli.init_bar_db() is True

    fake = _FakeAuth({"id": "U1", "username": "boss", "role": "staff", "email": "boss@uni.ac.uk"})
    monkeypatch.setattr(bar_cli, "get_auth", lambda: fake)
    if hasattr(bar_cli, "log_activity"):
        monkeypatch.setattr(bar_cli, "log_activity", lambda *a, **k: None)
    if hasattr(bar_cli, "FINANCE_AVAILABLE"):
        monkeypatch.setattr(bar_cli, "FINANCE_AVAILABLE", False)
    # Isolate the module-level shopping cart between tests.
    bar_cli.current_order = []
    return db_path, fake


# ---------------------------------------------------------------------------
# init / seed data
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_seeds_bar_products(self, bar_db):
        db_path, _ = bar_db
        rows = _rows(db_path, "SELECT * FROM products WHERE source_type = 'bar'")
        assert len(rows) == 25
        # Alcohol flag is honoured for a beer vs a soft drink.
        cats = {r["name"]: r["is_alcoholic"] for r in rows}
        assert cats["Lager"] == 1
        assert cats["Cola"] == 0

    def test_init_is_idempotent(self, bar_db):
        db_path, _ = bar_db
        assert bar_cli.init_bar_db() is True
        rows = _rows(db_path, "SELECT COUNT(*) AS n FROM products WHERE source_type = 'bar'")
        assert rows[0]["n"] == 25


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_current_user_dict(self, bar_db):
        assert bar_cli.get_current_user()["username"] == "boss"

    def test_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(bar_cli, "get_auth", lambda: None)
        assert bar_cli.get_current_user() is None

    def test_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(bar_cli, "get_auth", lambda: _FakeAuth(None))
        assert bar_cli.get_current_user() is None


# ---------------------------------------------------------------------------
# add_to_order (global cart, no DB write)
# ---------------------------------------------------------------------------

class TestAddToOrder:
    @patch("builtins.print")
    def test_adds_item_to_cart(self, _p, bar_db):
        # Product 1 is Lager (stock 100); add 2.
        with patch("builtins.input", side_effect=["1", "2", ""]):
            bar_cli.add_to_order()
        assert len(bar_cli.current_order) == 1
        assert bar_cli.current_order[0]["quantity"] == 2
        assert bar_cli.current_order[0]["name"] == "Lager"

    @patch("builtins.print")
    def test_unknown_item_adds_nothing(self, _p, bar_db):
        with patch("builtins.input", side_effect=["99999", ""]):
            bar_cli.add_to_order()
        assert bar_cli.current_order == []


# ---------------------------------------------------------------------------
# add_menu_item (write action + staff guard)
# ---------------------------------------------------------------------------

class TestAddMenuItem:
    @patch("builtins.print")
    def test_happy_path_persists_item(self, _p, bar_db):
        db_path, _ = bar_db
        script = ["Craft IPA", "Beer", "Hoppy", "5.25", "12", "yes", ""]
        with patch("builtins.input", side_effect=script):
            bar_cli.add_menu_item()
        rows = _rows(db_path, "SELECT * FROM products WHERE name = 'Craft IPA'")
        assert len(rows) == 1
        assert rows[0]["price"] == 5.25
        assert rows[0]["stock_quantity"] == 12
        assert rows[0]["is_alcoholic"] == 1

    @patch("builtins.print")
    def test_blank_name_writes_nothing(self, _p, bar_db):
        db_path, _ = bar_db
        before = _rows(db_path, "SELECT COUNT(*) AS n FROM products")[0]["n"]
        with patch("builtins.input", side_effect=[""]):
            assert bar_cli.add_menu_item() is None
        after = _rows(db_path, "SELECT COUNT(*) AS n FROM products")[0]["n"]
        assert before == after


class TestManageMenuGuard:
    @patch("builtins.print")
    def test_non_staff_refused(self, _p, bar_db, monkeypatch):
        monkeypatch.setattr(
            bar_cli, "get_auth",
            lambda: _FakeAuth({"id": "S1", "username": "stu", "role": "student"}),
        )
        with patch("builtins.input", return_value=""):
            assert bar_cli.manage_menu_items() is None

    @patch("builtins.print")
    def test_no_user_refused(self, _p, bar_db, monkeypatch):
        monkeypatch.setattr(bar_cli, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert bar_cli.view_sales_report() is None


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_menu(self, _p, bar_db):
        with patch("builtins.input", return_value=""):
            assert bar_cli.view_menu() is None

    @patch("builtins.print")
    def test_view_all_items(self, _p, bar_db):
        with patch("builtins.input", return_value=""):
            assert bar_cli.view_all_items() is None
