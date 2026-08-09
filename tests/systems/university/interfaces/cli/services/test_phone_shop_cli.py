"""Behavioural tests for the Phone Shop CLI (``modules.services.cli.phone_shop_cli``).

Isolation mirrors the gym-CLI harness: repoint the shared ``DEFAULT_DB_PATH`` at a
temp file (``get_connection`` reads it at call time), build the schema via the
module's own ``init_phoneshop_database()``, and stub the auth seam (the module
resolves the current user through ``get_user``, aliased from shared_context).

Testable surface exercised here:

* pure helpers (``generate_order_number``, catalog/status constants),
* auth resolution (``get_current_user``) across three cases,
* data actions (``get_all_products`` / ``get_product_by_id`` / ``create_order`` /
  ``get_all_orders``) asserted against temp-DB rows,
* input-driven actions (``add_to_cart_menu`` guard + happy path, ``checkout_menu``
  happy path + empty-cart guard).
"""

import sqlite3
from unittest.mock import patch

import pytest

from education_system.systems.university.interfaces.cli.shell.services import phone_shop_cli


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def shop_db(tmp_path, monkeypatch):
    """Temp DB + seeded phone-shop schema, logged-in user, empty cart."""
    db_path = str(tmp_path / "phoneshop.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert phone_shop_cli.init_phoneshop_database() is True

    user = {"username": "alice", "role": "student", "email": "a@uni.ac.uk",
            "id": "S001", "name": "Alice Example"}
    monkeypatch.setattr(phone_shop_cli, "get_user", lambda: user)
    # Reset the module-level shopping cart between tests.
    monkeypatch.setattr(phone_shop_cli, "cart", [])
    return db_path, user


# ---------------------------------------------------------------------------
# Pure helpers / constants
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_order_number_shape(self):
        num = phone_shop_cli.generate_order_number()
        assert num.startswith("ORD-")
        assert len(num) > len("ORD-")

    def test_category_and_status_constants(self):
        assert "Smartphone" in phone_shop_cli.PHONE_CATEGORIES
        assert "Pending" in phone_shop_cli.ORDER_STATUSES
        assert all(isinstance(c, str) for c in phone_shop_cli.PHONE_CATEGORIES)


# ---------------------------------------------------------------------------
# get_current_user (3 cases)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_authenticated_user(self, shop_db):
        assert phone_shop_cli.get_current_user()["username"] == "alice"

    def test_guest_when_user_none(self, monkeypatch):
        monkeypatch.setattr(phone_shop_cli, "get_user", lambda: None)
        assert phone_shop_cli.get_current_user()["username"] == "guest"

    def test_guest_when_get_user_unavailable(self, monkeypatch):
        monkeypatch.setattr(phone_shop_cli, "get_user", None)
        assert phone_shop_cli.get_current_user()["role"] == "guest"


# ---------------------------------------------------------------------------
# read data helpers
# ---------------------------------------------------------------------------

class TestProductQueries:
    def test_get_all_products_lists_seeded(self, shop_db):
        products = phone_shop_cli.get_all_products()
        assert len(products) == 12
        assert all("price" in p for p in products)

    def test_get_all_products_category_filter(self, shop_db):
        smartphones = phone_shop_cli.get_all_products(category="Smartphone")
        assert len(smartphones) > 0
        assert all(p["category"] == "Smartphone" for p in smartphones)

    def test_get_all_products_search(self, shop_db):
        results = phone_shop_cli.get_all_products(search="iPhone")
        assert results
        assert all("iphone" in p["name"].lower() for p in results)

    def test_get_product_by_id(self, shop_db):
        product = phone_shop_cli.get_product_by_id(1)
        assert product is not None
        assert product["product_id"] == 1

    def test_get_product_by_id_missing(self, shop_db):
        assert phone_shop_cli.get_product_by_id(999999) is None


# ---------------------------------------------------------------------------
# create_order / get_all_orders (write + read)
# ---------------------------------------------------------------------------

class TestCreateOrder:
    def test_create_order_persists_and_decrements_stock(self, shop_db):
        db_path, _ = shop_db
        before = phone_shop_cli.get_product_by_id(1)["stock"]

        order_data = {
            "order_number": "ORD-TEST-1",
            "customer_name": "Alice Example",
            "customer_email": "a@uni.ac.uk",
            "customer_phone": "",
            "student_id": "S001",
            "total_amount": 999.0 * 2,
            "payment_method": "Cash",
            "payment_status": "Paid",
            "order_status": "Processing",
            "order_date": "2026-07-22 10:00:00",
        }
        cart_items = [{"product_id": 1, "name": "iPhone 15 Pro",
                       "price": 999.0, "quantity": 2}]
        assert phone_shop_cli.create_order(order_data, cart_items) is True

        orders = _rows(db_path, "SELECT * FROM orders WHERE order_number = 'ORD-TEST-1'")
        assert len(orders) == 1
        assert orders[0]["total_amount"] == 1998.0
        items = _rows(db_path, "SELECT * FROM order_items")
        assert len(items) == 1
        assert items[0]["quantity"] == 2
        assert phone_shop_cli.get_product_by_id(1)["stock"] == before - 2

    def test_get_all_orders_reflects_created(self, shop_db):
        order_data = {
            "order_number": "ORD-TEST-2", "customer_name": "Bob",
            "total_amount": 19.0, "payment_method": "Card",
            "payment_status": "Paid", "order_status": "Processing",
            "order_date": "2026-07-22 11:00:00",
        }
        cart_items = [{"product_id": 10, "name": "USB-C Cable",
                       "price": 19.0, "quantity": 1}]
        assert phone_shop_cli.create_order(order_data, cart_items) is True
        orders = phone_shop_cli.get_all_orders()
        assert any(o["order_number"] == "ORD-TEST-2" for o in orders)


# ---------------------------------------------------------------------------
# add_to_cart_menu (input-driven action)
# ---------------------------------------------------------------------------

class TestAddToCart:
    @patch("builtins.print")
    def test_invalid_product_id_leaves_cart_empty(self, _p, shop_db):
        with patch("builtins.input", side_effect=["not-a-number"]):
            phone_shop_cli.add_to_cart_menu()
        assert phone_shop_cli.cart == []

    @patch("builtins.print")
    def test_happy_path_adds_item(self, _p, shop_db):
        with patch("builtins.input", side_effect=["1", "2"]):
            phone_shop_cli.add_to_cart_menu()
        assert len(phone_shop_cli.cart) == 1
        assert phone_shop_cli.cart[0]["product_id"] == 1
        assert phone_shop_cli.cart[0]["quantity"] == 2


# ---------------------------------------------------------------------------
# checkout_menu (input-driven action)
# ---------------------------------------------------------------------------

class TestCheckout:
    @patch("builtins.print")
    def test_empty_cart_creates_no_order(self, _p, shop_db):
        db_path, _ = shop_db
        with patch("builtins.input", side_effect=[]):
            phone_shop_cli.checkout_menu()
        assert _rows(db_path, "SELECT * FROM orders") == []

    @patch("builtins.print")
    def test_happy_path_places_order_and_clears_cart(self, _p, shop_db, monkeypatch):
        db_path, _ = shop_db
        monkeypatch.setattr(
            phone_shop_cli, "cart",
            [{"product_id": 1, "name": "iPhone 15 Pro", "price": 999.0, "quantity": 2}],
        )
        before = phone_shop_cli.get_product_by_id(1)["stock"]
        # name, email, phone, student_id, payment(1=Cash), confirm
        script = ["Test Customer", "", "", "", "1", "yes"]
        with patch("builtins.input", side_effect=script):
            phone_shop_cli.checkout_menu()

        orders = _rows(db_path, "SELECT * FROM orders")
        assert len(orders) == 1
        assert orders[0]["customer_name"] == "Test Customer"
        assert orders[0]["total_amount"] == 1998.0
        assert orders[0]["payment_method"] == "Cash"
        assert phone_shop_cli.get_product_by_id(1)["stock"] == before - 2
        assert phone_shop_cli.cart == []
