"""
Tests for the Commerce Restaurant Management service module.
Tests initialization, menu management, order management, and core functionality.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from education_system.post_18.university_system.modules.domain.commerce.services import restaurant_management

@pytest.fixture
def mock_auth():
    """Create a mock authentication instance."""
    auth = Mock()
    auth.current_user = {
        'id': 'USER001',
        'username': 'testuser',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    auth.has_permission = Mock(return_value=True)
    auth.is_logged_in = Mock(return_value=True)
    auth.check_session = Mock(return_value=True)
    return auth

@pytest.fixture
def mock_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_restaurant.db"

class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_init_db_success(self, mock_db_path):
        """Test successful database initialization."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            # Execute
            result = restaurant_management.init_db()

            # Verify
            assert result is True
            assert mock_db_path.exists()

            # Verify tables were created
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()

            # Check menu_items table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='menu_items'")
            assert cursor.fetchone() is not None

            # restaurant_orders table was replaced by unified 'orders' table
            # init_db no longer creates it, so we just check the other tables

            # Check inventory table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'")
            assert cursor.fetchone() is not None

            # Check staff_schedules table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_schedules'")
            assert cursor.fetchone() is not None

            conn.close()

class TestMenuManagement:
    """Tests for menu management functionality."""

    def test_view_menu_empty(self, mock_db_path, capsys):
        """Test viewing menu when no items exist."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Execute
            restaurant_management.view_menu()

            # Verify
            captured = capsys.readouterr()
            assert "No menu items found" in captured.out

    def test_view_menu_with_items(self, mock_db_path, capsys):
        """Test viewing menu with items."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Add test items
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()

            items = [
                ('Burger', 'Classic burger', 12.99, 'Main Course', 'Gluten', True),
                ('Salad', 'Fresh salad', 8.99, 'Main Course', 'None', True),
                ('Ice Cream', 'Vanilla', 4.99, 'Dessert', 'Dairy', True),
            ]

            for name, desc, price, cat, allergens, avail in items:
                cursor.execute('''
                    INSERT INTO menu_items
                    (name, description, price, category, allergens, available)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, desc, price, cat, allergens, avail))
            conn.commit()
            conn.close()

            # Execute
            restaurant_management.view_menu()

            # Verify
            captured = capsys.readouterr()
            assert "Current Menu" in captured.out
            assert "Burger" in captured.out
            assert "Salad" in captured.out
            assert "Ice Cream" in captured.out
            assert "MAIN COURSE:" in captured.out
            assert "DESSERT:" in captured.out

    @patch('builtins.input')
    def test_add_menu_item_success(self, mock_input, mock_db_path):
        """Test adding a new menu item."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Mock user inputs
            mock_input.side_effect = [
                'Pizza',  # name
                'Cheese pizza',  # description
                '14.99',  # price
                '2',  # category (Main Course)
                'Tomatoes, Cheese',  # ingredients
                'Dairy, Gluten'  # allergens
            ]

            # Execute
            restaurant_management.add_menu_item()

            # Verify
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM menu_items WHERE name = 'Pizza'")
            item = cursor.fetchone()
            conn.close()

            assert item is not None
            assert item[1] == 'Pizza'
            assert item[3] == 14.99
            assert item[4] == 'Main Course'

    @patch('builtins.input')
    def test_add_menu_item_invalid_price(self, mock_input, mock_db_path, capsys):
        """Test adding menu item with invalid price."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Mock user inputs
            mock_input.side_effect = [
                'Pizza',  # name
                'Cheese pizza',  # description
                'invalid'  # invalid price
            ]

            # Execute
            restaurant_management.add_menu_item()

            # Verify
            captured = capsys.readouterr()
            assert "Invalid price format" in captured.out

    @patch('builtins.input')
    def test_add_menu_item_negative_price(self, mock_input, mock_db_path, capsys):
        """Test adding menu item with negative price."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Mock user inputs
            mock_input.side_effect = [
                'Pizza',  # name
                'Cheese pizza',  # description
                '-5.99'  # negative price
            ]

            # Execute
            restaurant_management.add_menu_item()

            # Verify
            captured = capsys.readouterr()
            assert "Price cannot be negative" in captured.out

    @patch('builtins.input')
    def test_update_menu_item_success(self, mock_input, mock_db_path):
        """Test updating menu item."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Add test item
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO menu_items (name, description, price, category, available)
                VALUES (?, ?, ?, ?, ?)
            ''', ('Pizza', 'Cheese pizza', 14.99, 'Main Course', True))
            item_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Mock user inputs
            mock_input.side_effect = [
                str(item_id),  # item_id
                '',  # keep name
                '',  # keep description
                '16.99',  # new price
                '',  # keep category
                'y'  # available
            ]

            # Execute
            restaurant_management.update_menu_item()

            # Verify
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM menu_items WHERE id = ?", (item_id,))
            price = cursor.fetchone()[0]
            conn.close()

            assert price == 16.99

    @patch('builtins.input')
    def test_remove_menu_item_success(self, mock_input, mock_db_path):
        """Test removing menu item."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Add test item
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO menu_items (name, description, price, category, available)
                VALUES (?, ?, ?, ?, ?)
            ''', ('Pizza', 'Cheese pizza', 14.99, 'Main Course', True))
            item_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Mock user inputs
            mock_input.side_effect = [
                str(item_id),  # item_id
                'y'  # confirm
            ]

            # Execute
            restaurant_management.remove_menu_item()

            # Verify
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
            item = cursor.fetchone()
            conn.close()

            assert item is None

    @patch('builtins.input')
    def test_toggle_availability_success(self, mock_input, mock_db_path):
        """Test toggling menu item availability."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()

            # Add test item
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO menu_items (name, description, price, category, available)
                VALUES (?, ?, ?, ?, ?)
            ''', ('Pizza', 'Cheese pizza', 14.99, 'Main Course', True))
            item_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Mock user input
            mock_input.side_effect = [str(item_id)]

            # Execute
            restaurant_management.toggle_availability()

            # Verify
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT available FROM menu_items WHERE id = ?", (item_id,))
            available = cursor.fetchone()[0]
            conn.close()

            assert available == 0  # Should be toggled to unavailable

class TestOrderManagement:
    """Tests for order management functionality."""

    def _create_orders_table(self, db_path):
        """Helper to create the unified orders table used by the source code."""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                items TEXT,
                total_amount REAL,
                status TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivery_address TEXT,
                special_instructions TEXT,
                payment_method TEXT,
                completed_at TIMESTAMP,
                source_type TEXT DEFAULT 'restaurant'
            )
        ''')
        conn.commit()
        conn.close()

    def test_view_all_orders_empty(self, mock_db_path, capsys):
        """Test viewing orders when none exist."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Execute
            restaurant_management.view_all_orders()

            # Verify
            captured = capsys.readouterr()
            assert "No orders found" in captured.out

    def test_view_all_orders_with_data(self, mock_db_path, capsys):
        """Test viewing orders with data."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Add test orders
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()

            orders = [
                ('CUST001', '{"items": ["Pizza"]}', 14.99, 'pending'),
                ('CUST002', '{"items": ["Burger"]}', 12.99, 'completed'),
            ]

            for customer_id, items, total, status in orders:
                cursor.execute('''
                    INSERT INTO orders
                    (customer_id, items, total_amount, status)
                    VALUES (?, ?, ?, ?)
                ''', (customer_id, items, total, status))
            conn.commit()
            conn.close()

            # Execute
            restaurant_management.view_all_orders()

            # Verify
            captured = capsys.readouterr()
            assert "All Orders" in captured.out
            assert "CUST001" in captured.out
            assert "CUST002" in captured.out

    def test_view_pending_orders(self, mock_db_path, capsys):
        """Test viewing pending orders."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Add test orders
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders
                (customer_id, items, total_amount, status, special_instructions)
                VALUES (?, ?, ?, ?, ?)
            ''', ('CUST001', '{"items": ["Pizza"]}', 14.99, 'pending', 'No onions'))
            conn.commit()
            conn.close()

            # Execute
            restaurant_management.view_pending_orders()

            # Verify
            captured = capsys.readouterr()
            assert "Pending Orders" in captured.out
            assert "CUST001" in captured.out
            assert "No onions" in captured.out

    @patch('builtins.input')
    def test_update_order_status_success(self, mock_input, mock_db_path):
        """Test updating order status."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Add test order
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders
                (customer_id, items, total_amount, status)
                VALUES (?, ?, ?, ?)
            ''', ('CUST001', '{"items": ["Pizza"]}', 14.99, 'pending'))
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Mock user inputs
            mock_input.side_effect = [
                str(order_id),  # order_id
                '3'  # status (ready)
            ]

            # Execute
            restaurant_management.update_order_status()

            # Verify
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
            status = cursor.fetchone()[0]
            conn.close()

            assert status == 'ready'

    @patch('builtins.input')
    def test_view_order_details(self, mock_input, mock_db_path, capsys):
        """Test viewing order details."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Add test order
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders
                (customer_id, items, total_amount, status, delivery_address, special_instructions, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('CUST001', '{"items": ["Pizza", "Salad"]}', 23.98, 'pending',
                  '123 Main St', 'Ring doorbell', 'Credit Card'))
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Mock user input
            mock_input.side_effect = [str(order_id)]

            # Execute
            restaurant_management.view_order_details()

            # Verify
            captured = capsys.readouterr()
            assert "Order Details" in captured.out or "Order #" in captured.out
            assert "CUST001" in captured.out
            assert "23.98" in captured.out

    def test_daily_order_summary(self, mock_db_path, capsys):
        """Test daily order summary."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Add test orders for today
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()

            for i in range(3):
                cursor.execute('''
                    INSERT INTO orders
                    (customer_id, items, total_amount, status, order_date)
                    VALUES (?, ?, ?, ?, DATE('now'))
                ''', (f'CUST00{i+1}', '{"items": ["Pizza"]}', 14.99, 'pending'))
            conn.commit()
            conn.close()

            # Execute
            restaurant_management.daily_order_summary()

            # Verify
            captured = capsys.readouterr()
            assert "Order Summary" in captured.out or "Today" in captured.out

class TestSalesReports:
    """Tests for sales reporting functionality."""

    def _create_orders_table(self, db_path):
        """Helper to create the unified orders table used by the source code."""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                items TEXT,
                total_amount REAL,
                status TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivery_address TEXT,
                special_instructions TEXT,
                payment_method TEXT,
                completed_at TIMESTAMP,
                source_type TEXT DEFAULT 'restaurant'
            )
        ''')
        conn.commit()
        conn.close()

    def test_sales_reports_with_data(self, mock_db_path, capsys):
        """Test sales reports with order data."""
        # Setup
        with patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.DB_PATH', str(mock_db_path)):
            restaurant_management.init_db()
            self._create_orders_table(mock_db_path)

            # Add test orders
            conn = sqlite3.connect(str(mock_db_path))
            cursor = conn.cursor()

            # Today's orders
            for i in range(3):
                cursor.execute('''
                    INSERT INTO orders
                    (customer_id, items, total_amount, status, order_date)
                    VALUES (?, ?, ?, ?, DATE('now'))
                ''', (f'CUST00{i+1}', '{"items": ["Pizza"]}', 14.99, 'completed'))

            # This week's orders
            for i in range(5):
                cursor.execute('''
                    INSERT INTO orders
                    (customer_id, items, total_amount, status, order_date)
                    VALUES (?, ?, ?, ?, DATE('now', '-2 days'))
                ''', (f'CUST10{i+1}', '{"items": ["Burger"]}', 12.99, 'completed'))

            conn.commit()
            conn.close()

            # Execute
            restaurant_management.sales_reports(Mock())

            # Verify
            captured = capsys.readouterr()
            assert "Sales Summary" in captured.out
            assert "Today's Orders:" in captured.out
            assert "Weekly Orders:" in captured.out

class TestAuthIntegration:
    """Tests for authentication integration."""

    def test_set_auth(self, mock_auth):
        """Test setting auth instance."""
        # Execute
        restaurant_management.set_auth(mock_auth)

        # Verify
        assert restaurant_management._auth_instance == mock_auth

    @patch('education_system.post_18.university_system.modules.domain.commerce.services.restaurant_management.display_fallback_menu')
    def test_display_main_menu_not_logged_in(self, mock_fallback, capsys):
        """Test main menu when not logged in."""
        # Setup
        auth = Mock()
        auth.check_session = Mock(return_value=False)

        # Execute
        restaurant_management.display_main_menu(auth)

        # Verify
        captured = capsys.readouterr()
        assert "Please log in" in captured.out
        mock_fallback.assert_not_called()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
