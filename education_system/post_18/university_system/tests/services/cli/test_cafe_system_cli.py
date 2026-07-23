"""Behavioral tests for the Cafe System CLI (``modules.services.cli.cafe_system_cli``).

Unlike the gym CLI, this module reaches the DB through its own
``get_db_connection()`` helper, which opens ``sqlite3.connect(str(DEFAULT_DB_PATH))``
against the *module-level* ``DEFAULT_DB_PATH`` it imported at load time. Isolation
therefore repoints ``cafe_system_cli.DEFAULT_DB_PATH`` (not the shared db module's copy)
at a per-test temp file and builds the schema via the module's own ``init_cafe_db()``.

The testable surface is:

* the catalog constant (``CATEGORIES``) and ``get_db_connection`` plumbing,
* the non-interactive data-access functions (menu items, suppliers, loyalty,
  reservations) driven directly with real assertions against the temp DB,
* one interactive read view (``view_menu_cli``) driven with scripted ``input()``.

Side-effecting seams (activity logger, student-finance integration) are switched off
so nothing escapes the test.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import cafe_system_cli as cafe


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def cafe_db(tmp_path, monkeypatch):
    """Temp DB + cafe schema with side effects neutralised.

    Returns the db path so tests can inspect rows directly.
    """
    db_path = str(tmp_path / "cafe.db")
    # get_db_connection reads the *module-level* DEFAULT_DB_PATH at call time.
    monkeypatch.setattr(cafe, "DEFAULT_DB_PATH", db_path)
    # Don't write to the activity store or hit the student-finance ledger.
    monkeypatch.setattr(cafe, "ACTIVITY_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(cafe, "FINANCE_ACCOUNT_AVAILABLE", False)
    assert cafe.init_cafe_db() is True
    return db_path


# ---------------------------------------------------------------------------
# Catalog constant & connection plumbing
# ---------------------------------------------------------------------------

class TestPlumbing:
    def test_categories_wellformed(self):
        assert "Hot Drinks" in cafe.CATEGORIES
        assert all(isinstance(c, str) and c for c in cafe.CATEGORIES)

    def test_get_db_connection_opens_temp_db(self, cafe_db):
        conn = cafe.get_db_connection()
        assert conn is not None
        conn.close()

    def test_init_seeds_sample_items(self, cafe_db):
        rows = _rows(cafe_db, "SELECT COUNT(*) AS n FROM products WHERE source_type = 'cafe'")
        assert rows[0]["n"] == 20


# ---------------------------------------------------------------------------
# Menu item CRUD
# ---------------------------------------------------------------------------

class TestMenuItems:
    def test_add_menu_item_persists(self, cafe_db):
        assert cafe.add_menu_item("Flat White", "Hot Drinks", "Smooth", 3.40, 12) is True
        rows = _rows(cafe_db, "SELECT * FROM products WHERE name = 'Flat White'")
        assert len(rows) == 1
        assert rows[0]["price"] == 3.40
        assert rows[0]["stock_quantity"] == 12
        assert rows[0]["source_type"] == "cafe"

    def test_get_all_menu_items_category_filter(self, cafe_db):
        hot = cafe.get_all_menu_items(category="Hot Drinks")
        assert hot  # seeded hot drinks exist
        assert all(row[2] == "Hot Drinks" for row in hot)

    def test_get_menu_item_roundtrip(self, cafe_db):
        cafe.add_menu_item("Chai", "Hot Drinks", "Spiced", 3.10, 8)
        new_id = _rows(cafe_db, "SELECT product_id FROM products WHERE name = 'Chai'")[0][
            "product_id"
        ]
        item = cafe.get_menu_item(new_id)
        assert item is not None
        assert item[1] == "Chai"

    def test_get_menu_item_missing_returns_none(self, cafe_db):
        assert cafe.get_menu_item(999999) is None

    def test_update_menu_item(self, cafe_db):
        cafe.add_menu_item("Mocha", "Hot Drinks", "Choc", 3.90, 5)
        pid = _rows(cafe_db, "SELECT product_id FROM products WHERE name = 'Mocha'")[0][
            "product_id"
        ]
        assert cafe.update_menu_item(pid, "Mocha Deluxe", "Hot Drinks", 4.20, 3, True) is True
        row = _rows(cafe_db, "SELECT * FROM products WHERE product_id = ?", (pid,))[0]
        assert row["name"] == "Mocha Deluxe"
        assert row["price"] == 4.20
        assert row["stock_quantity"] == 3

    def test_delete_menu_item(self, cafe_db):
        cafe.add_menu_item("Temp", "Food", "x", 1.0, 1)
        pid = _rows(cafe_db, "SELECT product_id FROM products WHERE name = 'Temp'")[0][
            "product_id"
        ]
        assert cafe.delete_menu_item(pid) is True
        assert _rows(cafe_db, "SELECT * FROM products WHERE product_id = ?", (pid,)) == []

    def test_get_low_stock_items(self, cafe_db):
        cafe.add_menu_item("Rare", "Food", "x", 2.0, 2)
        names = [r[0] for r in cafe.get_low_stock_items(threshold=5)]
        assert "Rare" in names


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

class TestSuppliers:
    def test_add_and_fetch_supplier(self, cafe_db):
        sid = cafe.add_supplier("Beans Ltd", "Jo", "jo@beans.uk", "123", "Addr", "Net 30")
        assert isinstance(sid, int)
        got = cafe.get_supplier(sid)
        assert got is not None
        assert got[1] == "Beans Ltd"
        assert sid in [s[0] for s in cafe.get_all_suppliers()]

    def test_delete_supplier(self, cafe_db):
        sid = cafe.add_supplier("Gone Ltd", "", "", "", "", "")
        assert cafe.delete_supplier(sid) is True
        assert cafe.get_supplier(sid) is None


# ---------------------------------------------------------------------------
# Loyalty points (includes the insufficient-balance guard)
# ---------------------------------------------------------------------------

class TestLoyalty:
    def test_get_or_create_then_add(self, cafe_db):
        acct = cafe.get_or_create_loyalty_account("S001", "Alice")
        assert acct is not None
        assert acct[3] == 0  # starts at zero points
        assert cafe.add_loyalty_points("S001", 50, "signup") is True
        assert cafe.get_loyalty_account("S001")[3] == 50

    def test_redeem_happy_path(self, cafe_db):
        cafe.get_or_create_loyalty_account("S002", "Bob")
        cafe.add_loyalty_points("S002", 30)
        assert cafe.redeem_loyalty_points("S002", 20, "coffee") is True
        assert cafe.get_loyalty_account("S002")[3] == 10

    def test_redeem_insufficient_points_refused(self, cafe_db):
        cafe.get_or_create_loyalty_account("S003", "Cara")
        cafe.add_loyalty_points("S003", 5)
        # Guard: cannot redeem more than the balance; nothing changes.
        assert cafe.redeem_loyalty_points("S003", 100) is False
        assert cafe.get_loyalty_account("S003")[3] == 5


# ---------------------------------------------------------------------------
# Reservations
# ---------------------------------------------------------------------------

class TestReservations:
    def test_create_and_cancel(self, cafe_db):
        rid = cafe.create_reservation("Dana", "S004", "2026-08-01", "12:30", 4, "window")
        assert isinstance(rid, int)
        res = cafe.get_reservation(rid)
        assert res[1] == "Dana"
        assert res[6] == "confirmed"
        assert cafe.cancel_reservation(rid) is True
        assert cafe.get_reservation(rid)[6] == "cancelled"

    def test_get_all_reservations_empty(self, cafe_db):
        assert cafe.get_all_reservations() == []


# ---------------------------------------------------------------------------
# Interactive read view runs cleanly (empty + seeded)
# ---------------------------------------------------------------------------

class TestViewMenuCli:
    @patch("builtins.print")
    def test_seeded_menu_renders(self, _p, cafe_db):
        # filter choice "" -> All; then the trailing "Press Enter".
        with patch("builtins.input", return_value=""):
            assert cafe.view_menu_cli() is None

    @patch("builtins.print")
    def test_empty_menu_renders(self, _p, cafe_db):
        conn = sqlite3.connect(cafe_db)
        conn.execute("DELETE FROM products WHERE source_type = 'cafe'")
        conn.commit()
        conn.close()
        with patch("builtins.input", return_value=""):
            assert cafe.view_menu_cli() is None
