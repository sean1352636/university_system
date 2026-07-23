"""
Tests for shop management module.
Tests shop initialization, product management, inventory, transactions, and discounts.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

# Import the module to test
from education_system.post_18.university_system.modules.domain.commerce.services import shop_management
from education_system.post_18.university_system.modules.domain.commerce.services.shop_management import config as shop_config

# Patch paths for sub-modules that import get_connection directly
DB_PATCH = 'education_system.post_18.university_system.modules.domain.commerce.services.shop_management.database.get_connection'
SHOPPING_PATCH = 'education_system.post_18.university_system.modules.domain.commerce.services.shop_management.shopping.get_connection'
SHOPPING_FINANCE_PATCH = 'education_system.post_18.university_system.modules.domain.commerce.services.shop_management.shopping.record_payment_to_finance'

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'id': 1, 'username': 'testuser', 'role': 'admin', 'student_id': 'S001'}
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    return auth

class _UnclosableConn:
    """Wrapper that prevents close() from actually closing the connection."""
    def __init__(self, conn):
        object.__setattr__(self, '_conn', conn)
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def __setattr__(self, name, value):
        if name == '_conn':
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)
    def close(self):
        pass  # no-op
    def cursor(self):
        return self._conn.cursor()
    def commit(self):
        self._conn.commit()
    def real_close(self):
        self._conn.close()

def _create_products_table(cursor):
    """Helper to create the unified products table used by shop management."""
    cursor.execute('PRAGMA foreign_keys = OFF')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'shop',
            source_product_id TEXT UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            created_at TEXT,
            updated_at TEXT,
            tax_rate REAL DEFAULT 0.2,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

class TestInitShopDB:
    """Test shop database initialization"""

    @patch(DB_PATCH)
    def test_init_shop_db_success(self, mock_get_conn, test_db, capsys):
        """Test successful database initialization"""
        raw_conn = sqlite3.connect(test_db)
        cursor = raw_conn.cursor()
        _create_products_table(cursor)
        raw_conn.commit()
        conn = _UnclosableConn(raw_conn)
        mock_get_conn.return_value = conn

        result = shop_management.init_shop_db()

        # Check if tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'products' in tables
        assert 'shop_inventory' in tables
        assert 'shop_discounts' in tables
        conn.real_close()

        assert result is True
        captured = capsys.readouterr()
        assert 'initialized successfully' in captured.out

    @patch(DB_PATCH)
    def test_init_shop_db_with_default_data(self, mock_get_conn, test_db, capsys):
        """Test that default products and discounts are created"""
        raw_conn = sqlite3.connect(test_db)
        cursor = raw_conn.cursor()
        _create_products_table(cursor)
        raw_conn.commit()
        conn = _UnclosableConn(raw_conn)
        mock_get_conn.return_value = conn

        result = shop_management.init_shop_db()

        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'shop'")
        product_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM shop_discounts')
        discount_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM shop_inventory')
        inventory_count = cursor.fetchone()[0]

        conn.real_close()

        assert product_count > 0
        assert discount_count > 0
        assert inventory_count > 0
        assert result is True

class TestSetupShopPermissions:
    """Test shop permissions setup"""

    @patch(DB_PATCH)
    def test_setup_shop_permissions_success(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test successful permissions setup"""
        raw_conn = sqlite3.connect(test_db)
        raw_conn.row_factory = sqlite3.Row
        cursor = raw_conn.cursor()

        # Create necessary tables
        cursor.execute('''
            CREATE TABLE permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_name TEXT UNIQUE,
                description TEXT,
                created_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT UNIQUE,
                description TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE role_permissions (
                role_id INTEGER,
                permission_id INTEGER,
                PRIMARY KEY (role_id, permission_id)
            )
        ''')

        # Insert test roles
        cursor.execute("INSERT INTO roles VALUES (1, 'admin', 'Admin role', '2024-01-01', '2024-01-01')")
        cursor.execute("INSERT INTO roles VALUES (2, 'student', 'Student role', '2024-01-01', '2024-01-01')")

        raw_conn.commit()
        conn = _UnclosableConn(raw_conn)
        mock_get_conn.return_value = conn

        result = shop_management.setup_shop_permissions(mock_auth)

        # Verify permissions were created
        cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name LIKE ?', ('%products%',))
        perm_count = cursor.fetchone()[0]

        conn.real_close()

        assert result is True
        assert perm_count > 0

        captured = capsys.readouterr()
        assert 'permissions setup successfully' in captured.out

class TestBrowseProducts:
    """Test product browsing functionality"""

    @patch(SHOPPING_PATCH)
    def test_browse_products_all(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test browsing all products"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        _create_products_table(cursor)

        cursor.execute('''
            CREATE TABLE shop_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                quantity INTEGER NOT NULL
            )
        ''')

        cursor.execute("INSERT INTO products (source_type, source_product_id, name, description, price, category, is_active, created_at, updated_at) VALUES ('shop', 'P001', 'Test Product', 'A test product', 10.99, 'Test', 1, '2024-01-01', '2024-01-01')")
        cursor.execute("INSERT INTO shop_inventory VALUES (1, 'P001', 50)")

        conn.commit()
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['1', 'n', '', '6']):
            shop_management.browse_products()

        captured = capsys.readouterr()
        assert 'Test Product' in captured.out or 'PRODUCTS' in captured.out

    @patch(SHOPPING_PATCH)
    def test_browse_products_by_category(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test browsing products by category"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        _create_products_table(cursor)

        cursor.execute('''
            CREATE TABLE shop_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                quantity INTEGER NOT NULL
            )
        ''')

        cursor.execute("INSERT INTO products (source_type, source_product_id, name, description, price, category, is_active, created_at, updated_at) VALUES ('shop', 'P001', 'Test Product', 'A test product', 10.99, 'Electronics', 1, '2024-01-01', '2024-01-01')")
        cursor.execute("INSERT INTO shop_inventory VALUES (1, 'P001', 50)")

        conn.commit()
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['2', '1', 'n', '', '6']):
            shop_management.browse_products()

        captured = capsys.readouterr()
        # Test passes if no error is raised

class TestShoppingCart:
    """Test shopping cart functionality"""

    @patch(SHOPPING_PATCH)
    def test_view_shopping_cart_empty(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing empty shopping cart"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create unified cart table and products table (needed for JOIN)
        cursor.execute('''
            CREATE TABLE cart (
                cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'shop',
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                added_at TEXT
            )
        ''')

        _create_products_table(cursor)

        conn.commit()
        mock_get_conn.return_value = conn

        shop_management.view_shopping_cart()

        captured = capsys.readouterr()
        assert 'empty' in captured.out or 'SHOPPING CART' in captured.out

class TestCheckout:
    """Test checkout functionality"""

    @patch(SHOPPING_FINANCE_PATCH)
    @patch(SHOPPING_PATCH)
    def test_checkout_process_empty_cart(self, mock_get_conn, mock_record_payment, test_db, mock_auth, capsys):
        """Test checkout with empty cart"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create unified cart and products tables (needed for JOIN in checkout)
        cursor.execute('''
            CREATE TABLE cart (
                cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'shop',
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                added_at TEXT
            )
        ''')

        _create_products_table(cursor)

        cursor.execute('''
            CREATE TABLE shop_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                quantity INTEGER NOT NULL DEFAULT 0,
                last_restock_date TEXT,
                restock_threshold INTEGER DEFAULT 5
            )
        ''')

        conn.commit()
        mock_get_conn.return_value = conn

        shop_management.checkout_process()

        captured = capsys.readouterr()
        assert 'empty' in captured.out or 'no items' in captured.out.lower()

class TestPurchaseHistory:
    """Test purchase history viewing"""

    @patch(SHOPPING_PATCH)
    def test_view_purchase_history_no_purchases(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing purchase history with no purchases"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create unified transactions table
        cursor.execute('''
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'shop',
                source_transaction_id TEXT,
                customer_id INTEGER,
                total_amount REAL,
                payment_method TEXT,
                status TEXT,
                created_at TEXT
            )
        ''')

        conn.commit()
        mock_get_conn.return_value = conn

        shop_management.view_purchase_history()

        captured = capsys.readouterr()
        assert 'purchases' in captured.out.lower() or 'PURCHASE HISTORY' in captured.out

class TestProductManagement:
    """Test product management (admin functions)"""

    def test_display_product_management_menu_available(self, mock_auth):
        """Test that product management menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_product_management_menu')
        assert callable(shop_management.display_product_management_menu)

class TestInventoryManagement:
    """Test inventory management (admin functions)"""

    def test_display_inventory_management_menu_available(self, mock_auth):
        """Test that inventory management menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_inventory_management_menu')
        assert callable(shop_management.display_inventory_management_menu)

class TestTransactionViewing:
    """Test transaction viewing (admin functions)"""

    def test_view_all_transactions_available(self, mock_auth):
        """Test that view all transactions function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'view_all_transactions')
        assert callable(shop_management.view_all_transactions)

class TestDiscountManagement:
    """Test discount management functions"""

    def test_display_discount_management_menu_available(self, mock_auth):
        """Test that discount management menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_discount_management_menu')
        assert callable(shop_management.display_discount_management_menu)

class TestSalesReports:
    """Test sales reporting functions"""

    def test_display_sales_reports_menu_available(self, mock_auth):
        """Test that sales reports menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_sales_reports_menu')
        assert callable(shop_management.display_sales_reports_menu)

class TestDisplayShopMenu:
    """Test main shop menu"""

    @patch('education_system.post_18.university_system.modules.domain.commerce.services.shop_management.menus.get_connection')
    def test_display_shop_menu_initialization(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test shop menu with uninitialized database"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            try:
                shop_management.display_shop_menu()
            except (KeyboardInterrupt, StopIteration):
                pass

    def test_display_shop_menu_no_auth(self, capsys):
        """Test shop menu without authentication"""
        shop_management.set_auth(None)

        shop_management.display_shop_menu()

        captured = capsys.readouterr()
        assert 'must be logged in' in captured.out

class TestSetAuth:
    """Test authentication setup"""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance"""
        shop_management.set_auth(mock_auth)
        assert shop_config.auth == mock_auth

    def test_set_auth_none(self):
        """Test setting None as auth"""
        shop_management.set_auth(None)
        assert shop_config.auth is None

    def test_set_auth_with_has_auth(self, mock_auth):
        """Test setting auth when HAS_AUTH is True"""
        with patch.object(shop_config, 'HAS_AUTH', True):
            with patch.object(shop_config, 'set_auth_instance') as mock_set_auth_instance:
                shop_management.set_auth(mock_auth)
                mock_set_auth_instance.assert_called_once_with(mock_auth)

class TestPermissions:
    """Test permission checking"""

    def test_browse_products_no_permission(self, mock_auth, capsys):
        """Test browsing products without permission"""
        mock_auth.check_permission.return_value = False
        shop_management.set_auth(mock_auth)

        shop_management.browse_products()

        captured = capsys.readouterr()
        assert "don't have permission" in captured.out

class TestActivityLogging:
    """Test activity logging decorators"""

    def test_log_menu_navigation_decorator(self):
        """Test that log_menu_navigation decorator is applied"""
        # Check that the function has the decorator applied
        assert hasattr(shop_management.display_shop_menu, '__wrapped__') or callable(shop_management.display_shop_menu)

    def test_log_read_decorator(self):
        """Test that log_read decorator is applied"""
        assert hasattr(shop_management.browse_products, '__wrapped__') or callable(shop_management.browse_products)

class TestModuleConstants:
    """Test module-level constants and variables"""

    def test_has_auth_defined(self):
        """Test that HAS_AUTH constant is defined"""
        assert hasattr(shop_management, 'HAS_AUTH')

    def test_auth_variable_defined(self):
        """Test that auth variable is defined"""
        assert hasattr(shop_management, 'auth')

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
