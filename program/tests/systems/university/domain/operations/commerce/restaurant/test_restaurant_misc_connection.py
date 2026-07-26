"""
Tests for university_system/modules/core/services/restaurant_misc/connection.py
"""
from __future__ import annotations

from education_system.systems.university.infrastructure.database.db import sqlite3
import tempfile
from io import StringIO
from unittest import mock

import pytest

from education_system.systems.university.domain.operations.commerce.services.restaurant.operations import connection

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    yield temp_file.name
    import os
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)

class TestSetAuth:
    """Tests for set_auth function"""

    def test_set_auth_sets_context(self):
        """Test that set_auth sets the auth context"""
        mock_auth = mock.MagicMock()

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.ctx') as mock_ctx:
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.HAS_AUTH', True):
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.set_auth_instance') as mock_set_auth_instance:
                    connection.set_auth(mock_auth)

                    assert mock_ctx.auth == mock_auth
                    mock_set_auth_instance.assert_called_once_with(mock_auth)

    def test_set_auth_without_global_auth(self):
        """Test set_auth when global auth is not available"""
        mock_auth = mock.MagicMock()

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.ctx') as mock_ctx:
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.HAS_AUTH', False):
                connection.set_auth(mock_auth)

                assert mock_ctx.auth == mock_auth

class TestGetDbConnection:
    """Tests for get_db_connection function"""

    def test_get_db_connection_success(self, temp_db):
        """Test successful database connection"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            conn = connection.get_db_connection()

            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

            # Verify foreign keys are enabled
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1

            conn.close()

    def test_get_db_connection_failure(self):
        """Test database connection failure"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', '/invalid/path/db.db'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.logging.error') as mock_log:
                    conn = connection.get_db_connection()

                    assert conn is None
                    output = fake_out.getvalue()
                    assert 'Database connection error' in output
                    mock_log.assert_called_once()

    def test_get_db_connection_enables_foreign_keys(self, temp_db):
        """Test that foreign keys are enabled on connection"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            conn = connection.get_db_connection()

            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()

            assert result[0] == 1
            conn.close()

class TestSafeDbOperation:
    """Tests for safe_db_operation function"""

    def test_safe_db_operation_success(self):
        """Test successful database operation"""
        def test_func(x, y):
            return x + y

        result = connection.safe_db_operation(test_func, 2, 3)
        assert result == 5

    def test_safe_db_operation_sqlite_error(self):
        """Test handling of SQLite errors"""
        def test_func():
            raise sqlite3.Error("Database error")

        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.logging.error') as mock_log:
                result = connection.safe_db_operation(test_func)

                assert result is None
                output = fake_out.getvalue()
                assert 'Database error' in output
                mock_log.assert_called_once()

    def test_safe_db_operation_general_exception(self):
        """Test handling of general exceptions"""
        def test_func():
            raise ValueError("Test error")

        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.logging.error') as mock_log:
                result = connection.safe_db_operation(test_func)

                assert result is None
                output = fake_out.getvalue()
                assert 'An unexpected error occurred' in output
                mock_log.assert_called_once()

    def test_safe_db_operation_with_kwargs(self):
        """Test safe operation with keyword arguments"""
        def test_func(a, b, c=10):
            return a + b + c

        result = connection.safe_db_operation(test_func, 1, 2, c=5)
        assert result == 8

class TestInitDb:
    """Tests for init_db function"""

    def test_init_db_success(self, temp_db):
        """Test successful database initialization"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                result = connection.init_db()

                assert result is True
                output = fake_out.getvalue()
                assert 'Enhanced restaurant database initialized successfully!' in output

    def test_init_db_creates_all_tables(self, temp_db):
        """Test that all required tables are created"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            connection.init_db()

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            # Check for key tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = [
                'menu_items',
                'restaurant_orders',
                'restaurant_order_items',
                'restaurant_customers',
                'restaurant_tables',
                'restaurant_staff',
                'restaurant_inventory',
                'restaurant_expenses',
                'restaurant_budgets',
                'restaurant_audit_logs',
                'restaurant_meal_plans',
                'restaurant_suppliers'
            ]

            for table in required_tables:
                assert table in tables, f"Table {table} not created"

            conn.close()

    def test_init_db_creates_indexes(self, temp_db):
        """Test that indexes are created"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            connection.init_db()

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]

            expected_indexes = [
                'idx_restaurant_orders_date',
                'idx_restaurant_orders_customer',
                'idx_restaurant_orders_status',
                'idx_restaurant_customer_email',
                'idx_restaurant_inventory_reorder',
                'idx_restaurant_staff_schedules_date',
                'idx_restaurant_audit_logs_timestamp'
            ]

            for index in expected_indexes:
                assert index in indexes, f"Index {index} not created"

            conn.close()

    def test_init_db_initializes_default_data(self, temp_db):
        """Test that default data is initialized"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            connection.init_db()

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            # Check for default menu items
            cursor.execute("SELECT COUNT(*) FROM menu_items")
            menu_count = cursor.fetchone()[0]
            assert menu_count > 0

            # Check for default tables
            cursor.execute("SELECT COUNT(*) FROM restaurant_tables")
            table_count = cursor.fetchone()[0]
            assert table_count > 0

            # Check for default settings
            cursor.execute("SELECT COUNT(*) FROM restaurant_system_settings")
            settings_count = cursor.fetchone()[0]
            assert settings_count > 0

            conn.close()

    def test_init_db_connection_failure(self):
        """Test init_db when connection fails"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.get_db_connection', return_value=None):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                result = connection.init_db()

                assert result is False

    def test_init_db_sqlite_error(self, temp_db):
        """Test init_db when SQLite error occurs"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.get_db_connection') as mock_conn:
                mock_cursor = mock.MagicMock()
                mock_cursor.execute.side_effect = sqlite3.Error("Table creation error")
                mock_connection = mock.MagicMock()
                mock_connection.cursor.return_value = mock_cursor
                mock_conn.return_value = mock_connection

                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.logging.error') as mock_log:
                        result = connection.init_db()

                        assert result is False
                        output = fake_out.getvalue()
                        assert 'Database initialization error' in output
                        mock_log.assert_called()

    def test_init_db_enables_foreign_keys(self, temp_db):
        """Test that foreign keys are enabled during initialization"""
        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.connection.DATABASE_FILE', temp_db):
            connection.init_db()

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()
            assert result[0] == 1

            conn.close()

class TestInitializeDefaultData:
    """Tests for initialize_default_data function"""

    def test_initialize_default_data_menu_items(self, temp_db):
        """Test initialization of default menu items"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Create menu_items table
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

        connection.initialize_default_data(cursor)

        cursor.execute("SELECT COUNT(*) FROM menu_items")
        count = cursor.fetchone()[0]
        assert count > 0

        # Check specific items
        cursor.execute("SELECT name FROM menu_items WHERE item_id = 'M001'")
        result = cursor.fetchone()
        assert result[0] == 'University Burger'

        conn.close()

    def test_initialize_default_data_tables(self, temp_db):
        """Test initialization of default restaurant tables"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Create restaurant_tables table
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

        connection.initialize_default_data(cursor)

        cursor.execute("SELECT COUNT(*) FROM restaurant_tables")
        count = cursor.fetchone()[0]
        assert count > 0

        # Check table capacities
        cursor.execute("SELECT capacity FROM restaurant_tables WHERE table_id = 'T003'")
        result = cursor.fetchone()
        assert result[0] == 6

        conn.close()

    def test_initialize_default_data_system_settings(self, temp_db):
        """Test initialization of default system settings"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Create system_settings table
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

        connection.initialize_default_data(cursor)

        cursor.execute("SELECT COUNT(*) FROM restaurant_system_settings")
        count = cursor.fetchone()[0]
        assert count > 0

        # Check specific settings
        cursor.execute("SELECT setting_value FROM restaurant_system_settings WHERE setting_name = 'tax_rate'")
        result = cursor.fetchone()
        assert result[0] == '0.08'

        conn.close()

    def test_initialize_default_data_idempotent(self, temp_db):
        """Test that initialize_default_data is idempotent"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Create tables
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

        # Call twice - should not duplicate data
        connection.initialize_default_data(cursor)
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        count1 = cursor.fetchone()[0]

        connection.initialize_default_data(cursor)
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        count2 = cursor.fetchone()[0]

        assert count1 == count2  # No duplicates

        conn.close()

    def test_initialize_default_data_error_handling(self, temp_db):
        """Test error handling in initialize_default_data"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Don't create tables - should raise error
        with pytest.raises(sqlite3.Error):
            connection.initialize_default_data(cursor)

        conn.close()
