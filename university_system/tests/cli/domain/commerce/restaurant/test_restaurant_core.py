"""
Tests for restaurant core module.
Tests database initialization and main menu display functions.
"""

import pytest
import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import os
import tempfile

# Import the module to test
from university_system.modules.domain.commerce.services.restaurant.operations import restaurant_core


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
    auth.current_user = {'id': 'user123', 'username': 'testuser', 'role': 'admin'}
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    auth.logout = Mock()
    return auth


class TestSetAuth:
    """Test authentication setup"""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance"""
        restaurant_core.set_auth(mock_auth)
        assert restaurant_core.auth == mock_auth

    def test_set_auth_with_has_auth(self, mock_auth):
        """Test setting auth when HAS_AUTH is True"""
        with patch.object(restaurant_core, 'HAS_AUTH', True):
            with patch.object(restaurant_core, 'set_auth_instance') as mock_set_auth_instance:
                restaurant_core.set_auth(mock_auth)
                mock_set_auth_instance.assert_called_once_with(mock_auth)


class TestGetDBConnection:
    """Test database connection function"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.restaurant_core.get_connection')
    def test_get_db_connection_success(self, mock_get_connection):
        """Test successful database connection"""
        mock_conn = Mock()
        mock_get_connection.return_value = mock_conn

        result = restaurant_core.get_db_connection()
        assert result == mock_conn

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.restaurant_core.sqlite3.connect')
    def test_get_db_connection_with_database_file(self, mock_connect, test_db):
        """Test database connection with DATABASE_FILE"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        result = restaurant_core.get_db_connection()
        assert result is not None


class TestSafeDBOperation:
    """Test safe database operation wrapper"""

    def test_safe_db_operation_success(self):
        """Test successful database operation"""
        def test_operation(x, y):
            return x + y

        result = restaurant_core.safe_db_operation(test_operation, 2, 3)
        assert result == 5

    def test_safe_db_operation_with_sqlite_error(self, capsys):
        """Test handling of SQLite error"""
        def failing_operation():
            raise sqlite3.Error("Database error")

        result = restaurant_core.safe_db_operation(failing_operation)
        assert result is None

        captured = capsys.readouterr()
        assert 'Database error' in captured.out

    def test_safe_db_operation_with_generic_error(self, capsys):
        """Test handling of generic error"""
        def failing_operation():
            raise ValueError("Some error")

        result = restaurant_core.safe_db_operation(failing_operation)
        assert result is None

        captured = capsys.readouterr()
        assert 'unexpected error' in captured.out.lower()


class TestInitDB:
    """Test database initialization"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.restaurant_core.get_db_connection')
    def test_init_db_success(self, mock_get_conn, test_db, capsys):
        """Test successful database initialization"""
        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        result = restaurant_core.init_db()

        # Check if tables were created
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'menu_items' in tables
        assert 'restaurant_orders' in tables
        assert 'restaurant_customers' in tables
        conn.close()

        assert result is True
        captured = capsys.readouterr()
        assert 'initialized successfully' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.restaurant_core.get_db_connection')
    def test_init_db_failure(self, mock_get_conn, capsys):
        """Test database initialization failure"""
        mock_get_conn.side_effect = sqlite3.Error("Cannot create database")

        result = restaurant_core.init_db()

        assert result is False
        captured = capsys.readouterr()
        assert 'error' in captured.out.lower()


class TestInitializeDefaultData:
    """Test default data initialization"""

    def test_initialize_default_data(self, test_db):
        """Test initialization of default data"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create tables first
        cursor.execute('''
            CREATE TABLE menu_items (
                item_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                allergens TEXT,
                vegetarian INTEGER DEFAULT 0,
                vegan INTEGER DEFAULT 0,
                available INTEGER DEFAULT 1,
                creation_date TEXT,
                calories INTEGER,
                protein REAL,
                carbs REAL,
                fat REAL,
                prep_time INTEGER,
                cost_price REAL,
                image_path TEXT,
                popularity_score INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE restaurant_tables (
                table_id TEXT PRIMARY KEY,
                capacity INTEGER NOT NULL,
                status TEXT DEFAULT 'Available',
                current_order_id TEXT,
                location TEXT,
                table_type TEXT,
                last_cleaned TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE restaurant_system_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                description TEXT,
                category TEXT,
                last_updated TEXT,
                updated_by TEXT
            )
        ''')

        conn.commit()

        # Initialize default data
        restaurant_core.initialize_default_data(cursor)
        conn.commit()

        # Verify data was inserted
        cursor.execute('SELECT COUNT(*) FROM menu_items')
        menu_count = cursor.fetchone()[0]
        assert menu_count > 0

        cursor.execute('SELECT COUNT(*) FROM restaurant_tables')
        table_count = cursor.fetchone()[0]
        assert table_count > 0

        cursor.execute('SELECT COUNT(*) FROM restaurant_system_settings')
        settings_count = cursor.fetchone()[0]
        assert settings_count > 0

        conn.close()


class TestDisplayMainMenu:
    """Test main menu display function"""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.display_menu_items_menu')
    @patch('builtins.input')
    def test_display_main_menu_menu_items(self, mock_input, mock_display_menu, mock_auth, capsys):
        """Test selecting menu items option"""
        restaurant_core.set_auth(mock_auth)

        # First input '1' for menu items, then '10' to logout
        mock_input.side_effect = ['1', '10']

        restaurant_core.display_main_menu()

        mock_display_menu.assert_called_once()

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.display_orders_menu')
    @patch('builtins.input')
    def test_display_main_menu_orders(self, mock_input, mock_display_orders, mock_auth):
        """Test selecting orders option"""
        restaurant_core.set_auth(mock_auth)

        mock_input.side_effect = ['2', '10']

        restaurant_core.display_main_menu()

        mock_display_orders.assert_called_once()

    @patch('builtins.input')
    def test_display_main_menu_logout(self, mock_input, mock_auth, capsys):
        """Test logout option"""
        restaurant_core.set_auth(mock_auth)

        mock_input.return_value = '10'

        restaurant_core.display_main_menu()

        mock_auth.logout.assert_called_once()
        captured = capsys.readouterr()
        assert 'Logged out successfully' in captured.out

    @patch('builtins.input')
    def test_display_main_menu_exit(self, mock_input, mock_auth, capsys):
        """Test exit option"""
        restaurant_core.set_auth(mock_auth)

        mock_input.return_value = '11'

        restaurant_core.display_main_menu()

        captured = capsys.readouterr()
        assert 'Thank you' in captured.out

    @patch('builtins.input')
    def test_display_main_menu_invalid_choice(self, mock_input, mock_auth, capsys):
        """Test invalid menu choice"""
        restaurant_core.set_auth(mock_auth)

        mock_input.side_effect = ['99', '11']

        restaurant_core.display_main_menu()

        captured = capsys.readouterr()
        assert 'Invalid choice' in captured.out


class TestImports:
    """Test that restaurant module functions can be imported"""

    def test_display_menu_items_menu_can_import(self):
        """Test that display_menu_items_menu can be imported"""
        from university_system.modules.domain.commerce.services.restaurant.menu.menu_management import display_menu_items_menu
        assert callable(display_menu_items_menu)

    def test_display_orders_menu_can_import(self):
        """Test that display_orders_menu can be imported"""
        from university_system.modules.domain.commerce.services.restaurant.menu.menu_management import display_orders_menu
        assert callable(display_orders_menu)

    def test_display_customer_menu_can_import(self):
        """Test that display_customer_menu can be imported"""
        from university_system.modules.domain.commerce.services.restaurant.menu.menu_management import display_customer_menu
        assert callable(display_customer_menu)

    def test_display_staff_management_can_import(self):
        """Test that display_staff_management can be imported"""
        from university_system.modules.domain.commerce.services.restaurant.staff.staff_administration import display_staff_management
        assert callable(display_staff_management)

    def test_display_inventory_management_can_import(self):
        """Test that display_inventory_management can be imported"""
        from university_system.modules.domain.commerce.services.restaurant.operations.inventory_management import display_inventory_management
        assert callable(display_inventory_management)

    def test_display_financial_reports_can_import(self):
        """Test that display_financial_reports can be imported"""
        from university_system.modules.domain.commerce.services.restaurant.operations.financial_reporting import display_financial_reports
        assert callable(display_financial_reports)


class TestConstants:
    """Test module constants"""

    def test_database_file_constant(self):
        """Test that DATABASE_FILE constant is defined"""
        assert hasattr(restaurant_core, 'DATABASE_FILE')
        assert restaurant_core.DATABASE_FILE is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
