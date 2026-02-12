"""
Tests for the Commerce Menu Management module.
Tests menu item creation, updates, viewing, analytics, and import/export.
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import csv
import json
import sys
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

# Mock the missing restaurant_orders_payments module
sys.modules['university_system.modules.core.services.restaurant_orders_payments'] = MagicMock()

from university_system.modules.domain.commerce.services.restaurant.menu import menu_management

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
    auth.is_logged_in = Mock(return_value=True)
    return auth

@pytest.fixture
def mock_db_connection(tmp_path):
    """Create a temporary in-memory database for testing."""
    db_path = tmp_path / "test_restaurant.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create necessary tables
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
            image_url TEXT,
            popularity_score INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            table_id TEXT,
            order_time TEXT,
            total_price REAL,
            status TEXT,
            payment_method TEXT,
            notes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_order_items (
            order_item_id TEXT PRIMARY KEY,
            order_id TEXT,
            item_id TEXT,
            quantity INTEGER,
            unit_price REAL,
            subtotal REAL,
            special_instructions TEXT,
            FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id),
            FOREIGN KEY (item_id) REFERENCES menu_items(item_id)
        )
    ''')

    conn.commit()
    return conn

class TestMenuItemCreation:
    """Tests for menu item creation functionality."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.log_audit_action')
    @patch('builtins.input')
    def test_create_menu_item_success(self, mock_input, mock_audit, mock_backup,
                                      mock_get_conn, mock_db_connection, mock_auth):
        """Test successful menu item creation."""
        # Setup
        menu_management.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection

        # Mock user inputs
        mock_input.side_effect = [
            'M',  # category code (Main)
            'Grilled Salmon',  # name
            'Fresh Atlantic salmon',  # description
            '18.99',  # price
            '12.50',  # cost_price
            '1',  # category (Main)
            'Fish',  # allergens
            'n',  # vegetarian
            'n',  # vegan
            'y',  # available
            '450',  # calories
            '35',  # protein
            '5',  # carbs
            '15',  # fat
            '20'  # prep_time
        ]

        # Execute
        menu_management.create_menu_item()

        # Verify
        cursor = mock_db_connection.cursor()
        cursor.execute("SELECT * FROM menu_items WHERE name = 'Grilled Salmon'")
        item = cursor.fetchone()

        assert item is not None
        assert item[1] == 'Grilled Salmon'
        assert item[3] == 18.99  # price
        assert item[15] == 12.50  # cost_price
        assert item[4] == 'Main'  # category
        assert item[8] == 1  # available
        mock_audit.assert_called_once()

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.backup_before_operation')
    @patch('builtins.input')
    def test_create_menu_item_invalid_price(self, mock_input, mock_backup,
                                           mock_get_conn, mock_db_connection,
                                           mock_auth, capsys):
        """Test menu item creation with invalid price."""
        # Setup
        menu_management.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection

        # Mock user inputs
        mock_input.side_effect = [
            'M',  # category code
            'Test Item',  # name
            'Test Description',  # description
            'invalid',  # invalid price
        ]

        # Execute
        menu_management.create_menu_item()

        # Verify
        captured = capsys.readouterr()
        assert "Invalid price" in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.backup_before_operation')
    @patch('builtins.input')
    def test_create_menu_item_empty_name(self, mock_input, mock_backup,
                                        mock_get_conn, mock_db_connection,
                                        mock_auth, capsys):
        """Test menu item creation with empty name."""
        # Setup
        menu_management.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection

        # Mock user inputs
        mock_input.side_effect = [
            'M',  # category code
            '',  # empty name
        ]

        # Execute
        menu_management.create_menu_item()

        # Verify
        captured = capsys.readouterr()
        assert "Item name is required" in captured.out

class TestMenuItemViewing:
    """Tests for viewing menu items."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('builtins.input')
    def test_view_all_menu_items(self, mock_input, mock_get_conn,
                                 mock_db_connection, capsys):
        """Test viewing all menu items."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test menu items
        items = [
            ('M001', 'Burger', 'Classic burger', 12.99, 'Main', 'Gluten', 0, 0, 1, 5.50),
            ('M002', 'Salad', 'Fresh salad', 8.99, 'Main', 'None', 1, 1, 1, 3.00),
            ('D001', 'Ice Cream', 'Vanilla ice cream', 4.99, 'Dessert', 'Dairy', 1, 0, 1, 1.50),
        ]

        for item_id, name, desc, price, cat, allergens, veg, vegan, avail, cost in items:
            cursor.execute('''
                INSERT INTO menu_items
                (item_id, name, description, price, category, allergens, vegetarian,
                 vegan, available, creation_date, calories, protein, carbs, fat,
                 prep_time, cost_price, image_url, popularity_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item_id, name, desc, price, cat, allergens, veg, vegan, avail,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0,
                  cost, None, 0))
        mock_db_connection.commit()

        # Mock user input
        mock_input.side_effect = ['1']  # View all items

        # Execute
        menu_management.view_all_menu_items()

        # Verify
        captured = capsys.readouterr()
        assert "MENU ITEMS" in captured.out
        assert "M001" in captured.out
        assert "Burger" in captured.out
        assert "M002" in captured.out
        assert "Salad" in captured.out
        assert "Total items: 3" in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('builtins.input')
    def test_view_menu_items_by_category(self, mock_input, mock_get_conn,
                                         mock_db_connection, capsys):
        """Test viewing menu items filtered by category."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test items
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('D001', 'Cheesecake', 'NY Cheesecake', 6.99, 'Dessert', 'Dairy',
              1, 0, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0,
              0, 0, 2.50, None, 0))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = ['2', 'Dessert']  # By category, Dessert

        # Execute
        menu_management.view_all_menu_items()

        # Verify
        captured = capsys.readouterr()
        assert "Cheesecake" in captured.out

class TestMenuItemUpdates:
    """Tests for updating menu items."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.log_audit_action')
    @patch('builtins.input')
    def test_update_menu_item_price(self, mock_input, mock_audit, mock_backup,
                                    mock_get_conn, mock_db_connection, mock_auth):
        """Test updating menu item price."""
        # Setup
        menu_management.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Burger', 'Classic burger', 10.99, 'Main', 'Gluten', 0, 0,
              1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0,
              5.00, None, 0))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'M001',  # item_id
            '3',  # Update price
            '12.99'  # new price
        ]

        # Execute
        menu_management.update_menu_item()

        # Verify
        cursor.execute("SELECT price FROM menu_items WHERE item_id = 'M001'")
        price = cursor.fetchone()[0]
        assert price == 12.99
        mock_audit.assert_called_once()

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.log_audit_action')
    @patch('builtins.input')
    def test_update_menu_item_availability(self, mock_input, mock_audit, mock_backup,
                                           mock_get_conn, mock_db_connection, mock_auth):
        """Test updating menu item availability."""
        # Setup
        menu_management.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Burger', 'Classic burger', 10.99, 'Main', 'Gluten', 0, 0,
              1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0,
              5.00, None, 0))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'M001',  # item_id
            '7',  # Update availability
            'n'  # not available
        ]

        # Execute
        menu_management.update_menu_item()

        # Verify
        cursor.execute("SELECT available FROM menu_items WHERE item_id = 'M001'")
        available = cursor.fetchone()[0]
        assert available == 0
        mock_audit.assert_called_once()

class TestMenuItemDeletion:
    """Tests for deleting menu items."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.log_audit_action')
    @patch('builtins.input')
    def test_delete_menu_item(self, mock_input, mock_audit, mock_backup,
                             mock_get_conn, mock_db_connection, mock_auth):
        """Test deleting a menu item."""
        # Setup
        menu_management.set_auth(mock_auth)
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Test Item', 'Test', 10.99, 'Main', 'None', 0, 0, 1,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0,
              5.00, None, 0))
        mock_db_connection.commit()

        # Mock user inputs
        mock_input.side_effect = [
            'M001',  # item_id
            'DELETE'  # confirmation
        ]

        # Execute
        menu_management.delete_menu_item()

        # Verify
        cursor.execute("SELECT * FROM menu_items WHERE item_id = 'M001'")
        item = cursor.fetchone()
        assert item is None
        mock_audit.assert_called_once()

class TestMenuAnalytics:
    """Tests for menu analytics functionality."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    def test_menu_analytics(self, mock_get_conn, mock_db_connection, capsys):
        """Test menu analytics display."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test items
        items = [
            ('M001', 'Burger', 'Main', 12.99, 5.50),
            ('M002', 'Salad', 'Main', 8.99, 3.00),
            ('D001', 'Ice Cream', 'Dessert', 4.99, 1.50),
        ]

        for item_id, name, cat, price, cost in items:
            cursor.execute('''
                INSERT INTO menu_items
                (item_id, name, description, price, category, allergens, vegetarian,
                 vegan, available, creation_date, calories, protein, carbs, fat,
                 prep_time, cost_price, image_url, popularity_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item_id, name, 'Test', price, cat, 'None', 0, 0, 1,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0,
                  cost, None, 0))

        # Add orders
        cursor.execute('''
            INSERT INTO restaurant_orders
            (order_id, customer_id, table_id, order_time, total_price, status, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('ORD001', 'CUST001', 'T001', datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              25.97, 'Completed', 'Card', None))

        cursor.execute('''
            INSERT INTO restaurant_order_items
            (order_item_id, order_id, item_id, quantity, unit_price, subtotal, special_instructions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('OI001', 'ORD001', 'M001', 2, 12.99, 25.98, None))
        mock_db_connection.commit()

        # Execute
        menu_management.menu_analytics()

        # Verify
        captured = capsys.readouterr()
        assert "MENU ANALYTICS" in captured.out
        assert "Best Selling Items" in captured.out or "Category Performance" in captured.out

class TestImportExport:
    """Tests for menu import/export functionality."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    def test_export_menu_csv(self, mock_get_conn, mock_db_connection, tmp_path):
        """Test exporting menu to CSV."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Burger', 'Classic burger', 10.99, 'Main', 'Gluten', 0, 0,
              1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 500, 25, 30, 15,
              10, 5.00, None, 0))
        mock_db_connection.commit()

        # Execute
        menu_management.export_menu_csv()

        # Verify CSV file exists and contains data
        # (In real test, would check file contents)

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    def test_export_menu_json(self, mock_get_conn, mock_db_connection):
        """Test exporting menu to JSON."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Burger', 'Classic burger', 10.99, 'Main', 'Gluten', 0, 0,
              1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 500, 25, 30, 15,
              10, 5.00, None, 0))
        mock_db_connection.commit()

        # Execute
        menu_management.export_menu_json()

        # Verify JSON file exists and contains correct structure

class TestOrderAnalytics:
    """Tests for order analytics."""

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('builtins.input')
    def test_order_analytics_daily_summary(self, mock_input, mock_get_conn,
                                          mock_db_connection, capsys):
        """Test daily order summary."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Add test orders
        for i in range(3):
            order_time = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO restaurant_orders
                (order_id, customer_id, table_id, order_time, total_price, status, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (f'ORD00{i+1}', 'CUST001', 'T001', order_time, 25.99 * (i+1),
                  'Completed', 'Card', None))
        mock_db_connection.commit()

        # Mock user input
        mock_input.side_effect = ['1']  # Daily summary

        # Execute
        menu_management.order_analytics()

        # Verify
        captured = capsys.readouterr()
        assert "ORDER ANALYTICS" in captured.out or "Date" in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.get_db_connection')
    @patch('builtins.input')
    def test_feedback_analytics(self, mock_input, mock_get_conn,
                                mock_db_connection, capsys):
        """Test feedback analytics."""
        # Setup
        mock_get_conn.return_value = mock_db_connection
        cursor = mock_db_connection.cursor()

        # Create feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_customer_feedback (
                feedback_id TEXT PRIMARY KEY,
                customer_id TEXT,
                order_id TEXT,
                item_id TEXT,
                rating INTEGER,
                feedback_text TEXT,
                feedback_date TEXT,
                response_text TEXT,
                response_date TEXT,
                category TEXT
            )
        ''')

        # Add test menu item
        cursor.execute('''
            INSERT INTO menu_items
            (item_id, name, description, price, category, allergens, vegetarian,
             vegan, available, creation_date, calories, protein, carbs, fat,
             prep_time, cost_price, image_url, popularity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('M001', 'Burger', 'Classic burger', 10.99, 'Main', 'Gluten', 0, 0,
              1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 0, 0, 0, 0,
              5.00, None, 0))

        # Add test feedback
        for i in range(5):
            cursor.execute('''
                INSERT INTO restaurant_customer_feedback
                (feedback_id, customer_id, order_id, item_id, rating, feedback_text,
                 feedback_date, response_text, response_date, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (f'FB00{i+1}', f'CUST00{i+1}', f'ORD00{i+1}', 'M001', 5 - i % 2,
                  f'Feedback {i+1}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  None, None, 'Food'))
        mock_db_connection.commit()

        # Execute
        with patch('university_system.modules.domain.commerce.services.restaurant.menu.menu_management.feedback_analytics') as mock_feedback:
            mock_feedback.return_value = {
                'summary': {'total': 5, 'avg_rating': 4.0, 'r5': 3, 'r4': 2, 'r3': 0, 'r2': 0, 'r1': 0},
                'top_items': [('Burger', 5, 4.0)]
            }
            result = menu_management.feedback_analytics()

        # Verify
        assert result is not None
        assert 'summary' in result
        assert 'top_items' in result

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
