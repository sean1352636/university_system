"""Behavioral tests for the Butcher Shop CLI (``modules.services.cli.butcher_cli``).

CLI modules are interactive: they read the current user via ``get_auth()`` and drive
menus with ``input()`` / ``print()``. The testable surface is:

* pure helpers (currency/date formatting, unit conversion, validation, stock icons),
* auth resolution (``get_current_user`` / ``is_admin``),
* DB-backed actions, driven directly or with a scripted ``input()`` sequence.

Isolation mirrors the gym-CLI tests: repoint the shared ``DEFAULT_DB_PATH`` at a temp
file (``get_connection``/``transaction`` read it at call time) and stub the seams
(``get_auth``, finance/email fan-out). The butcher CLI stores products/orders in the
unified ``products`` / ``orders`` / ``order_items`` tables, so the fixture creates those
stand-ins first, then calls the module's own ``init_butcher_db()`` which builds the
butcher-specific tables and seeds 13 sample products.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import butcher_cli as butcher


# Unified stand-in schema for the tables the butcher CLI reads/writes. Columns are
# the union of what the CLI's SQL touches (both ``product_id`` and
# ``source_product_id`` are referenced across different code paths).
_SEED_SCHEMA = """
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_product_id INTEGER,
    source_type TEXT,
    product_name TEXT,
    category TEXT,
    price_per_kg REAL,
    stock_kg REAL,
    description TEXT,
    supplier TEXT,
    reorder_point REAL DEFAULT 5.0,
    status TEXT DEFAULT 'available',
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT,
    order_number TEXT,
    user_id TEXT,
    user_name TEXT,
    user_email TEXT,
    customer_id TEXT,
    customer_name TEXT,
    total_amount REAL,
    payment_method TEXT,
    payment_status TEXT DEFAULT 'pending',
    order_status TEXT DEFAULT 'pending',
    order_date TEXT,
    pickup_date TEXT,
    notes TEXT,
    completed_date TEXT,
    payment_reference TEXT,
    updated_at TEXT
);
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT,
    order_id INTEGER,
    product_id INTEGER,
    item_name TEXT,
    quantity_kg REAL,
    unit_price REAL,
    subtotal REAL
);
"""


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


def _printed(mock_print):
    """Flatten everything a patched ``print`` was called with into one string."""
    return "\n".join(" ".join(str(a) for a in c.args) for c in mock_print.call_args_list)


@pytest.fixture()
def butcher_db(tmp_path, monkeypatch):
    """Temp DB with unified stand-in tables + the butcher schema, logged in as admin.

    Returns the db path so tests can inspect rows directly. Finance/email fan-out
    is disabled so nothing escapes the test.
    """
    db_path = str(tmp_path / "butcher.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Create the unified stand-in tables the butcher CLI depends on.
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SEED_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    # The module's own initialiser builds the butcher_* tables and seeds 13 products.
    assert butcher.init_butcher_db() is True

    # Logged-in admin by default; tests can override current_user.
    fake = _FakeAuth({"id": "A001", "username": "admin", "email": "admin@uni.ac.uk", "role": "admin"})
    monkeypatch.setattr(butcher, "get_auth", lambda: fake)
    monkeypatch.setattr(butcher, "FINANCE_AVAILABLE", False)
    monkeypatch.setattr(butcher, "EMAIL_AVAILABLE", False)
    return db_path, fake


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_format_currency(self):
        assert butcher.format_currency(12.5) == "GBP 12.50"

    def test_validate_positive_number_ok(self):
        assert butcher.validate_positive_number("3.5", "Price") == 3.5

    def test_validate_positive_number_zero_or_negative(self):
        assert butcher.validate_positive_number("0", "Price") is None
        assert butcher.validate_positive_number("-2", "Price") is None

    def test_validate_positive_number_invalid(self):
        assert butcher.validate_positive_number("abc", "Price") is None

    def test_convert_units(self):
        assert butcher.convert_units(2.0, "kg") == 2.0
        assert butcher.convert_units(500, "g") == pytest.approx(0.5)
        assert butcher.convert_units(1, "lb") == pytest.approx(0.453592)
        assert butcher.convert_units(1, "oz") == pytest.approx(0.0283495)

    def test_convert_units_unknown(self):
        assert butcher.convert_units(1, "furlong") is None

    def test_stock_status_icons(self):
        assert butcher.get_stock_status_icon(20) == "🟢"
        assert butcher.get_stock_status_icon(7) == "🟡"
        assert butcher.get_stock_status_icon(2) == "🟠"
        assert butcher.get_stock_status_icon(0) == "🔴"

    def test_format_date(self):
        assert butcher.format_date("") == "N/A"
        assert butcher.format_date("2026-07-22T10:30:00") == "2026-07-22 10:30"

    def test_product_categories(self):
        assert "Beef" in butcher.PRODUCT_CATEGORIES


# ---------------------------------------------------------------------------
# get_current_user / is_admin
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_current_user_dict(self, butcher_db):
        assert butcher.get_current_user()["username"] == "admin"

    def test_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(butcher, "get_auth", lambda: None)
        assert butcher.get_current_user() is None

    def test_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(butcher, "get_auth", lambda: _FakeAuth(None))
        assert butcher.get_current_user() is None

    def test_is_admin_true_for_staff(self, monkeypatch):
        monkeypatch.setattr(butcher, "get_auth", lambda: _FakeAuth({"role": "staff"}))
        assert butcher.is_admin() is True

    def test_is_admin_false_for_student(self, monkeypatch):
        monkeypatch.setattr(butcher, "get_auth", lambda: _FakeAuth({"role": "student"}))
        assert butcher.is_admin() is False


# ---------------------------------------------------------------------------
# add_product (write: happy path + guard)
# ---------------------------------------------------------------------------

class TestAddProduct:
    @patch("builtins.print")
    def test_non_admin_blocked(self, _p, butcher_db, monkeypatch):
        db_path, _ = butcher_db
        monkeypatch.setattr(butcher, "get_auth", lambda: _FakeAuth({"role": "student"}))
        with patch("builtins.input", return_value=""):
            butcher.add_product()
        assert _rows(db_path, "SELECT * FROM products WHERE product_name = 'Venison Steak'") == []

    @patch("builtins.print")
    def test_happy_path_persists(self, _p, butcher_db):
        db_path, _ = butcher_db
        # name, category(1=Beef), price, stock, description, supplier, reorder(blank), confirm, enter
        script = ["Venison Steak", "1", "12.50", "20", "", "", "", "yes", ""]
        with patch("builtins.input", side_effect=script):
            butcher.add_product()

        rows = _rows(db_path, "SELECT * FROM products WHERE product_name = 'Venison Steak'")
        assert len(rows) == 1
        assert rows[0]["category"] == "Beef"
        assert rows[0]["price_per_kg"] == 12.50
        assert rows[0]["stock_kg"] == 20.0
        assert rows[0]["status"] == "available"

    @patch("builtins.print")
    def test_declined_confirmation_writes_nothing(self, _p, butcher_db):
        db_path, _ = butcher_db
        script = ["Venison Steak", "1", "12.50", "20", "", "", "", "no", ""]
        with patch("builtins.input", side_effect=script):
            butcher.add_product()
        assert _rows(db_path, "SELECT * FROM products WHERE product_name = 'Venison Steak'") == []


# ---------------------------------------------------------------------------
# adjust_inventory (write: happy path + guard)
# ---------------------------------------------------------------------------

class TestAdjustInventory:
    def _seed_product(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """INSERT INTO products
                   (source_product_id, source_type, product_name, category,
                    price_per_kg, stock_kg, reorder_point, status)
                   VALUES (100, 'butcher', 'Test Cut', 'Beef', 10.0, 20.0, 5.0, 'available')""",
            )
            conn.commit()
        finally:
            conn.close()

    @patch("builtins.print")
    def test_non_admin_blocked(self, _p, butcher_db, monkeypatch):
        monkeypatch.setattr(butcher, "get_auth", lambda: _FakeAuth({"role": "student"}))
        with patch("builtins.input", return_value=""):
            butcher.adjust_inventory()  # must not raise

    @patch("builtins.print")
    def test_add_stock_happy_path(self, _p, butcher_db):
        db_path, _ = butcher_db
        self._seed_product(db_path)
        # product id, adj type(1=add), quantity, reason(1=Restocking), notes(blank), confirm, enter
        script = ["100", "1", "5", "1", "", "yes", ""]
        with patch("builtins.input", side_effect=script):
            butcher.adjust_inventory()

        rows = _rows(db_path, "SELECT stock_kg FROM products WHERE source_product_id = 100")
        assert rows[0]["stock_kg"] == pytest.approx(25.0)
        adj = _rows(db_path, "SELECT * FROM butcher_inventory_adjustments WHERE product_id = '100'")
        assert len(adj) == 1
        assert adj[0]["quantity_change"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Read views (empty + seeded)
# ---------------------------------------------------------------------------

class TestSearchProducts:
    @patch("builtins.print")
    def test_no_match(self, mock_print, butcher_db):
        with patch("builtins.input", side_effect=["Zzzznomatch", ""]):
            assert butcher.search_products() is None
        assert "No products found" in _printed(mock_print)

    @patch("builtins.print")
    def test_seeded_match(self, mock_print, butcher_db):
        # init_butcher_db seeds "Ribeye Steak" and "Sirloin Steak".
        with patch("builtins.input", side_effect=["Steak", ""]):
            assert butcher.search_products() is None
        out = _printed(mock_print)
        assert "SEARCH RESULTS" in out
        assert "Steak" in out


class TestViewInventory:
    @patch("builtins.print")
    def test_empty(self, mock_print, butcher_db):
        db_path, _ = butcher_db
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM products")
            conn.commit()
        finally:
            conn.close()
        with patch("builtins.input", return_value=""):
            assert butcher.view_inventory() is None
        assert "No products in inventory" in _printed(mock_print)

    @patch("builtins.print")
    def test_seeded(self, mock_print, butcher_db):
        with patch("builtins.input", return_value=""):
            assert butcher.view_inventory() is None
        out = _printed(mock_print)
        assert "INVENTORY SUMMARY" in out
        assert "Ribeye Steak" in out

    @patch("builtins.print")
    def test_non_admin_blocked(self, mock_print, butcher_db, monkeypatch):
        monkeypatch.setattr(butcher, "get_auth", lambda: _FakeAuth({"role": "student"}))
        with patch("builtins.input", return_value=""):
            assert butcher.view_inventory() is None
        assert "permission" in _printed(mock_print).lower()
