"""Tests for Phone Shop Core Services."""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch

MODULE = "education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core"


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.remove(path)


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_tables(conn):
    """Create phoneshop tables including unified transactions."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'phone_shop',
            source_product_id TEXT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            brand TEXT,
            model TEXT,
            category TEXT NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            cost_price DECIMAL(10,2),
            stock_quantity INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 5,
            specifications TEXT,
            warranty_months INTEGER DEFAULT 12,
            is_active BOOLEAN DEFAULT 1,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'phone_shop',
            source_order_id TEXT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            shipping_address TEXT,
            subtotal DECIMAL(10,2) NOT NULL,
            tax_amount DECIMAL(10,2) DEFAULT 0,
            shipping_fee DECIMAL(10,2) DEFAULT 0,
            discount_amount DECIMAL(10,2) DEFAULT 0,
            total_amount DECIMAL(10,2) NOT NULL,
            order_status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'pending',
            payment_method TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'phone_shop',
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            warranty_id TEXT,
            serial_number TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            reference_id INTEGER,
            reference_type TEXT,
            customer_id TEXT,
            transaction_type TEXT,
            amount DECIMAL(10,2),
            payment_method TEXT,
            reference_number TEXT,
            processed_by TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS phoneshop_warranties (
            warranty_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_item_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            serial_number TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            warranty_type TEXT DEFAULT 'standard',
            status TEXT DEFAULT 'active',
            customer_id TEXT NOT NULL,
            FOREIGN KEY (order_item_id) REFERENCES order_items(item_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)
    conn.commit()


def _seed_product(path, sku="PHN001", name="iPhone 15", category="Smartphone",
                  price=999.99, brand="Apple", model="15", stock=50):
    conn = _connect(path)
    conn.execute(
        "INSERT INTO products (source_type,sku,name,brand,model,category,price,stock_quantity) "
        "VALUES ('phone_shop',?,?,?,?,?,?,?)",
        (sku, name, brand, model, category, price, stock),
    )
    conn.commit()
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return pid


# ── ProductManager ──────────────────────────────────────────────────────

class TestProductManager:

    def test_add_product(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            pid = ProductManager.add_product("SKU001", "Galaxy S24", "Smartphone", 849.99, brand="Samsung", model="S24", stock_quantity=20)
        assert isinstance(pid, int) and pid > 0

    def test_add_product_duplicate_sku(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_product(temp_db, sku="DUP001")

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            result = ProductManager.add_product("DUP001", "Duplicate", "Smartphone", 100)
        assert result is None

    def test_get_product(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        pid = _seed_product(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            product = ProductManager.get_product(pid)
        assert product is not None
        assert product["name"] == "iPhone 15"

    def test_get_product_not_found(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            assert ProductManager.get_product(999) is None

    def test_get_all_products(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_product(temp_db, "P1", "Phone A", "Smartphone", 500)
        _seed_product(temp_db, "P2", "Phone B", "Smartphone", 600)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            products = ProductManager.get_all_products()
        assert len(products) == 2

    def test_get_products_by_category(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_product(temp_db, "S1", "Phone", "Smartphone", 500)
        _seed_product(temp_db, "A1", "Case", "Accessories", 20)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            results = ProductManager.get_products_by_category("Accessories")
        assert len(results) == 1
        assert results[0]["category"] == "Accessories"

    def test_update_product(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        pid = _seed_product(temp_db, price=500)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            assert ProductManager.update_product(pid, price=549.99) is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT price FROM products WHERE product_id=?", (pid,)).fetchone()
        conn.close()
        assert float(row["price"]) == 549.99

    def test_update_product_no_fields(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            assert ProductManager.update_product(1) is False

    def test_update_stock(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        pid = _seed_product(temp_db, stock=10)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            assert ProductManager.update_stock(pid, 5) is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT stock_quantity FROM products WHERE product_id=?", (pid,)).fetchone()
        conn.close()
        assert row["stock_quantity"] == 15

    def test_get_low_stock_products(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_product(temp_db, "LOW1", "Low Stock Phone", "Smartphone", 300, stock=2)
        _seed_product(temp_db, "HI1", "High Stock Phone", "Smartphone", 300, stock=100)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            low = ProductManager.get_low_stock_products()
        assert len(low) == 1
        assert low[0]["sku"] == "LOW1"

    def test_search_products(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_product(temp_db, "IP15", "iPhone 15 Pro", "Smartphone", 1199, brand="Apple")
        _seed_product(temp_db, "GS24", "Galaxy S24", "Smartphone", 849, brand="Samsung")

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ProductManager
            results = ProductManager.search_products("iPhone")
        assert len(results) == 1
        assert "iPhone" in results[0]["name"]


# ── OrderManager ────────────────────────────────────────────────────────

class TestOrderManager:

    def _create_order(self, temp_db):
        """Seed a product and create an order, return (order_id, product_id)."""
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        pid = _seed_product(temp_db, stock=50)

        items = [{"product_id": pid, "product_name": "iPhone 15", "quantity": 1, "unit_price": 999.99}]
        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            oid = OrderManager.create_order("CUST01", "John Doe", items)
        return oid, pid

    def test_create_order(self, temp_db):
        oid, _ = self._create_order(temp_db)
        assert isinstance(oid, int) and oid > 0

    def test_create_order_reduces_stock(self, temp_db):
        oid, pid = self._create_order(temp_db)
        conn = _connect(temp_db)
        row = conn.execute("SELECT stock_quantity FROM products WHERE product_id=?", (pid,)).fetchone()
        conn.close()
        assert row["stock_quantity"] == 49

    def test_get_order_with_items(self, temp_db):
        oid, _ = self._create_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            order = OrderManager.get_order(oid)
        assert order is not None
        assert order["customer_name"] == "John Doe"
        assert len(order["items"]) == 1

    def test_get_orders_by_status(self, temp_db):
        self._create_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            pending = OrderManager.get_orders_by_status("pending")
        assert len(pending) == 1

    def test_get_customer_orders(self, temp_db):
        self._create_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            orders = OrderManager.get_customer_orders("CUST01")
        assert len(orders) == 1

    def test_update_order_status(self, temp_db):
        oid, _ = self._create_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            assert OrderManager.update_order_status(oid, "shipped") is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT order_status FROM orders WHERE order_id=?", (oid,)).fetchone()
        conn.close()
        assert row["order_status"] == "shipped"

    def test_cancel_order_restores_stock(self, temp_db):
        oid, pid = self._create_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            assert OrderManager.cancel_order(oid, "Customer request") is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT stock_quantity FROM products WHERE product_id=?", (pid,)).fetchone()
        conn.close()
        assert row["stock_quantity"] == 50  # restored


# ── TransactionManager ──────────────────────────────────────────────────

class TestTransactionManager:

    def _setup_order(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        pid = _seed_product(temp_db, stock=50)

        items = [{"product_id": pid, "product_name": "iPhone 15", "quantity": 1, "unit_price": 999.99}]
        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager
            oid = OrderManager.create_order("CUST01", "John Doe", items)
        return oid

    def test_record_payment(self, temp_db):
        oid = self._setup_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import TransactionManager
            txn_id = TransactionManager.record_payment(oid, "CUST01", 1199.99, "card")
        assert isinstance(txn_id, int) and txn_id > 0

        conn = _connect(temp_db)
        row = conn.execute("SELECT payment_status FROM orders WHERE order_id=?", (oid,)).fetchone()
        conn.close()
        assert row["payment_status"] == "completed"

    def test_process_refund(self, temp_db):
        oid = self._setup_order(temp_db)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import TransactionManager
            TransactionManager.record_payment(oid, "CUST01", 1199.99, "card")
            refund_id = TransactionManager.process_refund(oid, 1199.99, reason="Defective")
        assert isinstance(refund_id, int) and refund_id > 0

        conn = _connect(temp_db)
        row = conn.execute("SELECT payment_status FROM orders WHERE order_id=?", (oid,)).fetchone()
        conn.close()
        assert row["payment_status"] == "refunded"

    def test_process_refund_nonexistent_order(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import TransactionManager
            assert TransactionManager.process_refund(999, 100.0) is None


# ── ReportManager ────────────────────────────────────────────────────────

class TestReportManager:

    def test_get_sales_summary_empty(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ReportManager
            summary = ReportManager.get_sales_summary()
        assert summary["total_orders"] == 0
        assert summary["total_revenue"] == 0

    def test_get_inventory_summary(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_product(temp_db, "INV1", "Phone A", "Smartphone", 500, stock=10)
        _seed_product(temp_db, "INV2", "Phone B", "Smartphone", 300, stock=20)

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ReportManager
            inv = ReportManager.get_inventory_summary()
        assert inv["total_products"] == 2
        assert inv["total_stock"] == 30

    def test_get_top_selling_products(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        pid = _seed_product(temp_db, stock=50)

        # Create an order so the product has sales
        items = [{"product_id": pid, "product_name": "iPhone 15", "quantity": 2, "unit_price": 999.99}]
        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import OrderManager, ReportManager
            OrderManager.create_order("CUST01", "Buyer", items)
            top = ReportManager.get_top_selling_products(limit=5)
        assert len(top) == 1
        assert top[0]["total_sold"] == 2

    def test_generate_admin_report(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_phoneshop_db_path", return_value=temp_db):
            from education_system.university_system.modules.domain.commerce.phoneshop.services.phoneshop_core import ReportManager
            text = ReportManager.generate_admin_report()
        assert "PHONE SHOP" in text
        assert "INVENTORY SUMMARY" in text
