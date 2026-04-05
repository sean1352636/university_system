"""
Tests for music shop core services.
Tests product management, orders, transactions, wishlists, and reports.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import patch

from education_system.university_system.modules.domain.musicshop.services.musicshop_core import (
    ProductManager, OrderManager, TransactionManager, WishlistManager,
    ReportManager, init_musicshop_db,
)

PATCH_TARGET = 'education_system.university_system.modules.domain.musicshop.services.musicshop_core.get_musicshop_db_path'


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def _init_extra_tables(path):
    """Create the unified transactions table that the service expects."""
    conn = sqlite3.connect(path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT,
            reference_id INTEGER,
            reference_type TEXT,
            customer_id TEXT,
            transaction_type TEXT,
            amount DECIMAL(10,2),
            payment_method TEXT,
            reference_number TEXT,
            processed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def _add_sample_product(sku='VIN-001', title='Abbey Road', category='Vinyl Records',
                        price=29.99, **kwargs):
    """Helper to add a product and return its ID."""
    return ProductManager.add_product(sku=sku, title=title, category=category,
                                      price=price, **kwargs)


def _add_sample_order(product_id, customer_id='CUST001', customer_name='Alice Smith'):
    """Helper to create an order with one item."""
    items = [{
        'product_id': product_id,
        'product_title': 'Abbey Road',
        'artist': 'The Beatles',
        'quantity': 1,
        'unit_price': 29.99,
    }]
    return OrderManager.create_order(
        customer_id=customer_id, customer_name=customer_name, items=items,
    )


# ---------------------------------------------------------------------------
# ProductManager
# ---------------------------------------------------------------------------

class TestProductManager:
    def test_add_product(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product()
            assert pid is not None
            assert isinstance(pid, int)

    def test_add_product_duplicate_sku(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='DUP-001')
            pid2 = _add_sample_product(sku='DUP-001')
            assert pid2 is None

    def test_get_product(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product()
            product = ProductManager.get_product(pid)
            assert product is not None
            assert product['name'] == 'Abbey Road'
            assert product['price'] == 29.99

    def test_get_product_not_found(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            assert ProductManager.get_product(9999) is None

    def test_get_all_products(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='P1', title='Album 1')
            _add_sample_product(sku='P2', title='Album 2')
            products = ProductManager.get_all_products()
            assert len(products) == 2

    def test_get_products_by_category(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='V1', category='Vinyl Records')
            _add_sample_product(sku='C1', category='CDs')
            vinyl = ProductManager.get_products_by_category('Vinyl Records')
            assert len(vinyl) == 1
            assert vinyl[0]['category'] == 'Vinyl Records'

    def test_get_products_by_genre(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='R1', genre='Rock')
            _add_sample_product(sku='J1', genre='Jazz')
            rock = ProductManager.get_products_by_genre('Rock')
            assert len(rock) == 1

    def test_update_product(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product()
            ok = ProductManager.update_product(pid, price=34.99, description='Remastered')
            assert ok is True
            updated = ProductManager.get_product(pid)
            assert updated['price'] == 34.99
            assert updated['description'] == 'Remastered'

    def test_update_stock(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product(stock_quantity=10)
            ok = ProductManager.update_stock(pid, 5)
            assert ok is True
            product = ProductManager.get_product(pid)
            assert product['stock_quantity'] == 15

    def test_update_stock_decrease(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product(stock_quantity=10)
            ProductManager.update_stock(pid, -3)
            product = ProductManager.get_product(pid)
            assert product['stock_quantity'] == 7

    def test_get_low_stock_products(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='LOW1', stock_quantity=1, min_stock_level=5)
            _add_sample_product(sku='OK1', stock_quantity=20, min_stock_level=3)
            low = ProductManager.get_low_stock_products()
            assert len(low) == 1
            assert low[0]['sku'] == 'LOW1'

    def test_get_rare_items(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='RARE1', is_rare=True)
            _add_sample_product(sku='NORM1', is_rare=False)
            rare = ProductManager.get_rare_items()
            assert len(rare) == 1

    def test_search_products_by_name(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='S1', title='Dark Side of the Moon')
            _add_sample_product(sku='S2', title='The Wall')
            results = ProductManager.search_products('Dark Side')
            assert len(results) == 1

    def test_search_products_by_artist(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='A1', artist='Pink Floyd')
            _add_sample_product(sku='A2', artist='Led Zeppelin')
            results = ProductManager.search_products('Floyd')
            assert len(results) == 1


# ---------------------------------------------------------------------------
# OrderManager
# ---------------------------------------------------------------------------

class TestOrderManager:
    def test_create_order(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=10)
            oid = _add_sample_order(pid)
            assert oid is not None
            assert isinstance(oid, int)

    def test_create_order_reduces_stock(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=10)
            _add_sample_order(pid)
            product = ProductManager.get_product(pid)
            assert product['stock_quantity'] == 9

    def test_get_order(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=5)
            oid = _add_sample_order(pid)
            order = OrderManager.get_order(oid)
            assert order is not None
            assert order['customer_name'] == 'Alice Smith'
            assert len(order['items']) == 1

    def test_get_order_not_found(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            assert OrderManager.get_order(9999) is None

    def test_get_orders_by_status(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=20)
            _add_sample_order(pid)
            pending = OrderManager.get_orders_by_status('pending')
            assert len(pending) == 1

    def test_get_customer_orders(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=20)
            _add_sample_order(pid, customer_id='C100')
            _add_sample_order(pid, customer_id='C200')
            orders = OrderManager.get_customer_orders('C100')
            assert len(orders) == 1

    def test_update_order_status(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=10)
            oid = _add_sample_order(pid)
            ok = OrderManager.update_order_status(oid, 'shipped')
            assert ok is True
            order = OrderManager.get_order(oid)
            assert order['order_status'] == 'shipped'

    def test_cancel_order_restores_stock(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=10)
            oid = _add_sample_order(pid)
            product_before = ProductManager.get_product(pid)
            assert product_before['stock_quantity'] == 9
            ok = OrderManager.cancel_order(oid, reason='Customer request')
            assert ok is True
            product_after = ProductManager.get_product(pid)
            assert product_after['stock_quantity'] == 10
            order = OrderManager.get_order(oid)
            assert order['order_status'] == 'cancelled'


# ---------------------------------------------------------------------------
# TransactionManager
# ---------------------------------------------------------------------------

class TestTransactionManager:
    def test_record_payment(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=5)
            oid = _add_sample_order(pid)
            tid = TransactionManager.record_payment(
                order_id=oid, customer_id='CUST001',
                amount=35.99, payment_method='card',
            )
            assert tid is not None
            order = OrderManager.get_order(oid)
            assert order['payment_status'] == 'completed'
            assert order['order_status'] == 'confirmed'

    def test_process_refund(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=5)
            oid = _add_sample_order(pid)
            TransactionManager.record_payment(
                order_id=oid, customer_id='CUST001',
                amount=35.99, payment_method='card',
            )
            rid = TransactionManager.process_refund(oid, amount=35.99, reason='Defective')
            assert rid is not None
            order = OrderManager.get_order(oid)
            assert order['payment_status'] == 'refunded'
            assert order['order_status'] == 'refunded'


# ---------------------------------------------------------------------------
# WishlistManager
# ---------------------------------------------------------------------------

class TestWishlistManager:
    def test_add_to_wishlist(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product()
            ok = WishlistManager.add_to_wishlist('CUST001', pid)
            assert ok is True

    def test_add_duplicate_to_wishlist(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product()
            WishlistManager.add_to_wishlist('CUST001', pid)
            ok = WishlistManager.add_to_wishlist('CUST001', pid)
            assert ok is True  # INSERT OR IGNORE, no error

    def test_get_wishlist(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid1 = _add_sample_product(sku='W1', title='Wish Album 1')
            pid2 = _add_sample_product(sku='W2', title='Wish Album 2')
            WishlistManager.add_to_wishlist('CUST010', pid1)
            WishlistManager.add_to_wishlist('CUST010', pid2)
            wl = WishlistManager.get_wishlist('CUST010')
            assert len(wl) == 2

    def test_remove_from_wishlist(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            pid = _add_sample_product()
            WishlistManager.add_to_wishlist('CUST001', pid)
            ok = WishlistManager.remove_from_wishlist('CUST001', pid)
            assert ok is True
            wl = WishlistManager.get_wishlist('CUST001')
            assert len(wl) == 0

    def test_remove_nonexistent_from_wishlist(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            ok = WishlistManager.remove_from_wishlist('CUST001', 9999)
            assert ok is False


# ---------------------------------------------------------------------------
# ReportManager
# ---------------------------------------------------------------------------

class TestReportManager:
    def test_get_sales_summary_empty(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            summary = ReportManager.get_sales_summary()
            assert summary['total_orders'] == 0
            assert summary['total_revenue'] == 0

    def test_get_sales_summary_with_orders(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=20)
            _add_sample_order(pid)
            summary = ReportManager.get_sales_summary()
            assert summary['total_orders'] == 1
            assert summary['pending_orders'] == 1

    def test_get_inventory_summary(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _add_sample_product(sku='INV1', stock_quantity=10, price=20.00)
            _add_sample_product(sku='INV2', stock_quantity=5, price=15.00, is_rare=True)
            summary = ReportManager.get_inventory_summary()
            assert summary['total_products'] == 2
            assert summary['total_stock'] == 15
            assert summary['rare_items_count'] == 1

    def test_get_sales_by_genre(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(sku='G1', genre='Rock', stock_quantity=10)
            _add_sample_order(pid)
            genres = ReportManager.get_sales_by_genre()
            assert len(genres) >= 1
            assert genres[0]['genre'] == 'Rock'

    def test_get_top_selling_products(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=20)
            _add_sample_order(pid)
            top = ReportManager.get_top_selling_products(limit=5)
            assert len(top) >= 1

    def test_get_top_artists(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(sku='TA1', artist='The Beatles', stock_quantity=20)
            _add_sample_order(pid)
            artists = ReportManager.get_top_artists(limit=5)
            assert len(artists) >= 1
            assert artists[0]['artist'] == 'The Beatles'

    def test_generate_admin_report(self, temp_db):
        with patch(PATCH_TARGET, return_value=temp_db):
            init_musicshop_db()
            _init_extra_tables(temp_db)
            pid = _add_sample_product(stock_quantity=10, artist='Queen', genre='Rock')
            _add_sample_order(pid)
            report = ReportManager.generate_admin_report()
            assert 'MUSIC SHOP ADMIN REPORT' in report
            assert 'SALES SUMMARY' in report
            assert 'INVENTORY SUMMARY' in report
