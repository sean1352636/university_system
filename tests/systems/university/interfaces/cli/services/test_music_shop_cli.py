"""Behavioral tests for the Music Shop CLI
(``modules.services.cli.music_shop_cli``).

The module uses the shared ``get_connection`` (which reads the db module's
``DEFAULT_DB_PATH`` at call time), so we repoint that at a temp file and build the
schema via the module's own ``init_musicshop_database()``. Auth is resolved via the
``get_user`` seam wrapped by ``get_current_user`` (falls back to a guest dict).
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import music_shop_cli as shop


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def shop_db(tmp_path, monkeypatch):
    """Temp DB + seeded music-shop schema; reset the global cart per test."""
    db_path = str(tmp_path / "music.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert shop.init_musicshop_database() is True
    shop.cart = []
    return db_path


# ---------------------------------------------------------------------------
# pure helpers & catalog constants
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_order_number_shape(self):
        assert shop.generate_order_number().startswith("MUS-")

    def test_catalog_constants_wellformed(self):
        assert "Albums" in shop.MUSIC_CATEGORIES
        assert "Jazz" in shop.GENRES
        assert "New" in shop.CONDITION_TYPES

    def test_init_seeds_products(self, shop_db):
        rows = _rows(shop_db, "SELECT COUNT(*) AS n FROM products WHERE source_type = 'music_shop'")
        assert rows[0]["n"] == 12


# ---------------------------------------------------------------------------
# get_current_user (3 cases via the get_user seam)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_user_from_seam(self, monkeypatch):
        monkeypatch.setattr(shop, "get_user", lambda: {"username": "dave", "name": "Dave"})
        assert shop.get_current_user()["username"] == "dave"

    def test_guest_when_seam_missing(self, monkeypatch):
        monkeypatch.setattr(shop, "get_user", None)
        assert shop.get_current_user()["username"] == "guest"

    def test_guest_when_seam_returns_none(self, monkeypatch):
        monkeypatch.setattr(shop, "get_user", lambda: None)
        assert shop.get_current_user()["role"] == "guest"


# ---------------------------------------------------------------------------
# write action: create_order (persists order/items + decrements stock)
# ---------------------------------------------------------------------------

class TestCreateOrder:
    def test_happy_path_persists_and_decrements_stock(self, shop_db):
        product = shop.get_all_products()[0]
        before = product["stock"]
        order_data = {
            "order_number": "MUS-TEST-1",
            "customer_name": "Buyer",
            "customer_email": "b@uni.ac.uk",
            "customer_phone": "",
            "student_id": "",
            "total_amount": product["price"] * 2,
            "payment_method": "Card",
            "payment_status": "Paid",
            "order_status": "Processing",
            "order_date": "2024-01-01 10:00:00",
        }
        cart = [{
            "product_id": product["product_id"],
            "title": product["title"],
            "price": product["price"],
            "quantity": 2,
        }]
        assert shop.create_order(order_data, cart) is True

        orders = _rows(shop_db, "SELECT * FROM orders WHERE order_number = 'MUS-TEST-1'")
        assert len(orders) == 1
        items = _rows(shop_db, "SELECT * FROM order_items WHERE order_id = ?", (orders[0]["order_id"],))
        assert len(items) == 1
        assert items[0]["quantity"] == 2
        after = shop.get_product_by_id(product["product_id"])["stock"]
        assert after == before - 2


class TestCheckoutGuard:
    @patch("builtins.print")
    def test_empty_cart_writes_no_order(self, _p, shop_db):
        shop.cart = []
        assert shop.checkout_menu() is None
        assert _rows(shop_db, "SELECT * FROM orders") == []


# ---------------------------------------------------------------------------
# add_to_cart_menu (global cart)
# ---------------------------------------------------------------------------

class TestAddToCart:
    @patch("builtins.print")
    def test_adds_valid_product(self, _p, shop_db):
        pid = shop.get_all_products()[0]["product_id"]
        with patch("builtins.input", side_effect=[str(pid), "1"]):
            shop.add_to_cart_menu()
        assert len(shop.cart) == 1
        assert shop.cart[0]["quantity"] == 1

    @patch("builtins.print")
    def test_rejects_non_numeric_id(self, _p, shop_db):
        with patch("builtins.input", side_effect=["abc"]):
            shop.add_to_cart_menu()
        assert shop.cart == []


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_orders_menu(self, _p, shop_db):
        assert shop.view_orders_menu() is None

    @patch("builtins.print")
    def test_statistics_menu(self, _p, shop_db):
        assert shop.statistics_menu() is None
