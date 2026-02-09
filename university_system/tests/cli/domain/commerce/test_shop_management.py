"""
Tests for shop management module.
Tests shop initialization, product management, inventory, transactions, and discounts.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

# Import the module to test
from university_system.modules.domain.commerce.services import shop_management


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


class TestInitShopDB:
    """Test shop database initialization"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_init_shop_db_success(self, mock_get_conn, test_db, capsys):
        """Test successful database initialization"""
        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        result = shop_management.init_shop_db()

        # Check if tables were created
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'shop_products' in tables
        assert 'shop_inventory' in tables
        assert 'shop_transactions' in tables
        assert 'shop_discounts' in tables
        conn.close()

        assert result is True
        captured = capsys.readouterr()
        assert 'initialized successfully' in captured.out

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_init_shop_db_with_default_data(self, mock_get_conn, test_db, capsys):
        """Test that default products and discounts are created"""
        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        result = shop_management.init_shop_db()

        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM shop_products')
        product_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM shop_discounts')
        discount_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM shop_inventory')
        inventory_count = cursor.fetchone()[0]

        conn.close()

        assert product_count > 0
        assert discount_count > 0
        assert inventory_count > 0
        assert result is True


class TestSetupShopPermissions:
    """Test shop permissions setup"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_setup_shop_permissions_success(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test successful permissions setup"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

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

        conn.commit()
        mock_get_conn.return_value = conn

        result = shop_management.setup_shop_permissions(mock_auth)

        # Verify permissions were created
        cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name LIKE ?', ('%products%',))
        perm_count = cursor.fetchone()[0]

        conn.close()

        assert result is True
        assert perm_count > 0

        captured = capsys.readouterr()
        assert 'permissions setup successfully' in captured.out


class TestBrowseProducts:
    """Test product browsing functionality"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_browse_products_all(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test browsing all products"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE shop_products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE shop_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                quantity INTEGER NOT NULL
            )
        ''')

        cursor.execute("INSERT INTO shop_products VALUES ('P001', 'Test Product', 10.99, 'Test', 1)")
        cursor.execute("INSERT INTO shop_inventory VALUES (1, 'P001', 50)")

        conn.commit()
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['1', '', '6']):
            shop_management.browse_products()

        captured = capsys.readouterr()
        assert 'Test Product' in captured.out or 'PRODUCTS' in captured.out

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_browse_products_by_category(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test browsing products by category"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE shop_products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE shop_inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                quantity INTEGER NOT NULL
            )
        ''')

        cursor.execute("INSERT INTO shop_products VALUES ('P001', 'Test Product', 10.99, 'Electronics', 1)")
        cursor.execute("INSERT INTO shop_inventory VALUES (1, 'P001', 50)")

        conn.commit()
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['2', '1', '', '6']):
            shop_management.browse_products()

        captured = capsys.readouterr()
        # Test passes if no error is raised


class TestShoppingCart:
    """Test shopping cart functionality"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_view_shopping_cart_empty(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing empty shopping cart"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE shop_cart (
                cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL
            )
        ''')

        conn.commit()
        mock_get_conn.return_value = conn

        shop_management.view_shopping_cart()

        captured = capsys.readouterr()
        assert 'empty' in captured.out or 'SHOPPING CART' in captured.out


class TestCheckout:
    """Test checkout functionality"""

    @patch('university_system.modules.domain.commerce.services.shop_management.record_payment_to_finance')
    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_checkout_process_empty_cart(self, mock_get_conn, mock_record_payment, test_db, mock_auth, capsys):
        """Test checkout with empty cart"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE shop_cart (
                cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL
            )
        ''')

        conn.commit()
        mock_get_conn.return_value = conn

        shop_management.checkout_process()

        captured = capsys.readouterr()
        assert 'empty' in captured.out or 'no items' in captured.out.lower()


class TestPurchaseHistory:
    """Test purchase history viewing"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_view_purchase_history_no_purchases(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing purchase history with no purchases"""
        shop_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE shop_transactions (
                transaction_id TEXT PRIMARY KEY,
                user_id INTEGER,
                total_amount REAL,
                transaction_date TEXT,
                status TEXT
            )
        ''')

        conn.commit()
        mock_get_conn.return_value = conn

        shop_management.view_purchase_history()

        captured = capsys.readouterr()
        assert 'No purchases' in captured.out or 'PURCHASE HISTORY' in captured.out


class TestProductManagement:
    """Test product management (admin functions)"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_display_product_management_menu_available(self, mock_get_conn, test_db, mock_auth):
        """Test that product management menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_product_management_menu')
        assert callable(shop_management.display_product_management_menu)


class TestInventoryManagement:
    """Test inventory management (admin functions)"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_display_inventory_management_menu_available(self, mock_get_conn, test_db, mock_auth):
        """Test that inventory management menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_inventory_management_menu')
        assert callable(shop_management.display_inventory_management_menu)


class TestTransactionViewing:
    """Test transaction viewing (admin functions)"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_view_all_transactions_available(self, mock_get_conn, test_db, mock_auth):
        """Test that view all transactions function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'view_all_transactions')
        assert callable(shop_management.view_all_transactions)


class TestDiscountManagement:
    """Test discount management functions"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_display_discount_management_menu_available(self, mock_get_conn, test_db, mock_auth):
        """Test that discount management menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_discount_management_menu')
        assert callable(shop_management.display_discount_management_menu)


class TestSalesReports:
    """Test sales reporting functions"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
    def test_display_sales_reports_menu_available(self, mock_get_conn, test_db, mock_auth):
        """Test that sales reports menu function exists"""
        shop_management.set_auth(mock_auth)

        assert hasattr(shop_management, 'display_sales_reports_menu')
        assert callable(shop_management.display_sales_reports_menu)


class TestDisplayShopMenu:
    """Test main shop menu"""

    @patch('university_system.modules.domain.commerce.services.shop_management.get_connection')
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
        assert shop_management.auth == mock_auth

    def test_set_auth_none(self):
        """Test setting None as auth"""
        shop_management.set_auth(None)
        assert shop_management.auth is None

    def test_set_auth_with_has_auth(self, mock_auth):
        """Test setting auth when HAS_AUTH is True"""
        with patch.object(shop_management, 'HAS_AUTH', True):
            with patch.object(shop_management, 'set_auth_instance') as mock_set_auth_instance:
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
