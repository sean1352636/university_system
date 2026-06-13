"""
Tests for restaurant inventory management operations module.
Tests supplier management, waste tracking, inventory reports, and stock operations.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

# Import the module to test
from education_system.university_system.modules.domain.commerce.services.restaurant.operations import inventory_management
from education_system.university_system.core import paths

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute('''
        CREATE TABLE restaurant_inventory (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            cost_per_unit REAL DEFAULT 0,
            reorder_level REAL DEFAULT 0,
            max_level REAL DEFAULT 0,
            supplier_id TEXT,
            category TEXT,
            expiry_date TEXT,
            batch_number TEXT,
            last_updated TEXT,
            location TEXT,
            temperature_req TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_inventory_transactions (
            transaction_id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL,
            reference_id TEXT,
            transaction_date TEXT,
            notes TEXT,
            performed_by TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            rating REAL DEFAULT 0,
            payment_terms TEXT,
            delivery_schedule TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_waste_tracking (
            waste_id TEXT PRIMARY KEY,
            item_id TEXT,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            waste_reason TEXT NOT NULL,
            cost_impact REAL DEFAULT 0,
            recorded_date TEXT NOT NULL,
            recorded_by TEXT,
            location TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE menu_items (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_purchase_orders (
            po_id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            expected_delivery TEXT,
            actual_delivery TEXT,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending',
            notes TEXT,
            created_by TEXT
        )
    ''')

    # Insert test data
    today = datetime.now().strftime('%Y-%m-%d')

    # Insert test suppliers
    cursor.execute('''
        INSERT INTO restaurant_suppliers VALUES
        ('SUP001', 'Fresh Foods Ltd', 'John Smith', 'john@freshfoods.com', '555-1234',
         '123 Main St', 4.5, 'Net 30', 'Weekly', 'Good supplier', 'Active'),
        ('SUP002', 'Quality Meats Inc', 'Jane Doe', 'jane@qualitymeats.com', '555-5678',
         '456 Oak Ave', 4.0, 'Net 15', 'Bi-weekly', NULL, 'Active')
    ''')

    # Insert test inventory items
    cursor.execute('''
        INSERT INTO restaurant_inventory VALUES
        ('INV001', 'Tomatoes', 50.0, 'kg', 2.50, 10.0, 100.0, 'SUP001', 'Vegetables',
         ?, NULL, ?, 'Cold Storage', '2-4°C'),
        ('INV002', 'Chicken Breast', 5.0, 'kg', 8.00, 15.0, 50.0, 'SUP002', 'Meat',
         ?, NULL, ?, 'Freezer', '-18°C'),
        ('INV003', 'Rice', 80.0, 'kg', 1.50, 20.0, 150.0, 'SUP001', 'Grains',
         NULL, NULL, ?, 'Dry Storage', 'Room Temp')
    ''', (
        (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
        today,
        (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
        today,
        today
    ))

    # Insert test transactions
    cursor.execute('''
        INSERT INTO restaurant_inventory_transactions VALUES
        ('TXN001', 'INV001', 'Stock In', 50.0, 2.50, 'PO001', ?, 'Initial stock', 'admin'),
        ('TXN002', 'INV001', 'Stock Out', 10.0, 2.50, 'ORD001', ?, 'Used in kitchen', 'chef')
    ''', (today, today))

    # Insert test waste records
    cursor.execute('''
        INSERT INTO restaurant_waste_tracking VALUES
        ('WST001', 'INV001', 2.0, 'kg', 'Spoiled', 5.00, ?, 'admin', 'Kitchen')
    ''', (today,))

    # Insert menu items
    cursor.execute('''
        INSERT INTO menu_items VALUES
        ('M001', 'Tomato Pasta', 'Main'),
        ('M002', 'Grilled Chicken', 'Main')
    ''')

    # Insert purchase orders
    cursor.execute('''
        INSERT INTO restaurant_purchase_orders VALUES
        ('PO001', 'SUP001', ?, ?, ?, 125.00, 'Delivered', NULL, 'admin')
    ''', (
        (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
        today,
        today
    ))

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {'id': 'user123', 'username': 'testuser', 'role': 'admin'}
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    return auth

class TestSupplierManagement:
    """Test supplier management functions"""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_view_all_suppliers(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing all suppliers"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inventory_management.view_all_suppliers()

        captured = capsys.readouterr()
        assert 'SUPPLIERS' in captured.out
        assert 'Fresh Foods Ltd' in captured.out
        assert 'Quality Meats Inc' in captured.out

    def test_add_new_supplier_function_exists(self):
        """Test that add_new_supplier function exists"""
        # This function exists in the module
        assert hasattr(inventory_management, 'add_new_supplier')
        assert callable(inventory_management.add_new_supplier)

    def test_update_supplier_function_exists(self):
        """Test that update_supplier function exists"""
        assert hasattr(inventory_management, 'update_supplier')
        assert callable(inventory_management.update_supplier)

class TestWasteTracking:
    """Test waste tracking functions"""

    def test_record_waste_function_exists(self):
        """Test that record_waste function exists"""
        assert hasattr(inventory_management, 'record_waste')
        assert callable(inventory_management.record_waste)

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_view_waste_reports_daily_summary(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing daily waste summary"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        today = datetime.now().strftime('%Y-%m-%d')

        with patch('builtins.input', side_effect=['1', '', '5']):
            inventory_management.view_waste_reports()

        captured = capsys.readouterr()
        assert 'WASTE REPORTS' in captured.out

class TestInventoryReports:
    """Test inventory reporting functions"""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_inventory_valuation_report(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test inventory valuation report"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inventory_management.inventory_valuation_report()

        captured = capsys.readouterr()
        assert 'INVENTORY VALUATION REPORT' in captured.out
        assert 'Total Value' in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_stock_movement_report(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test stock movement report"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        today = datetime.now().strftime('%Y-%m-%d')

        with patch('builtins.input', side_effect=[today, today]):
            inventory_management.stock_movement_report()

        captured = capsys.readouterr()
        assert 'STOCK MOVEMENT REPORT' in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_low_stock_report(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test low stock alert report"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inventory_management.low_stock_report()

        captured = capsys.readouterr()
        assert 'LOW STOCK REPORT' in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_expiry_report(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test expiry report showing expiring items"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inventory_management.expiry_report()

        captured = capsys.readouterr()
        assert 'EXPIRY REPORT' in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_abc_analysis(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test ABC analysis of inventory"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inventory_management.abc_analysis()

        captured = capsys.readouterr()
        assert 'ABC INVENTORY ANALYSIS' in captured.out

class TestInventoryOperations:
    """Test inventory CRUD operations"""

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_view_inventory_all_items(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing all inventory items"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', return_value='1'):
            inventory_management.view_inventory()

        captured = capsys.readouterr()
        assert 'INVENTORY' in captured.out
        assert 'Tomatoes' in captured.out

    def test_add_inventory_item_function_exists(self):
        """Test that add_inventory_item function exists"""
        assert hasattr(inventory_management, 'add_inventory_item')
        assert callable(inventory_management.add_inventory_item)

    def test_update_stock_levels_function_exists(self):
        """Test that update_stock_levels function exists"""
        assert hasattr(inventory_management, 'update_stock_levels')
        assert callable(inventory_management.update_stock_levels)

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_low_stock_alerts(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing low stock alerts"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        inventory_management.low_stock_alerts()

        captured = capsys.readouterr()
        assert 'LOW STOCK ALERTS' in captured.out

    @patch('education_system.university_system.modules.domain.commerce.services.restaurant.operations.inventory_management.get_db_connection')
    def test_inventory_transactions(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing inventory transactions"""
        inventory_management.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', return_value='1'):
            inventory_management.inventory_transactions()

        captured = capsys.readouterr()
        assert 'INVENTORY TRANSACTIONS' in captured.out

class TestSetAuth:
    """Test authentication setup"""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance"""
        inventory_management.set_auth(mock_auth)
        assert inventory_management.auth == mock_auth

class TestSupplierPerformance:
    """Test supplier performance tracking"""

    def test_supplier_performance_note(self):
        """Note: supplier_performance is in staff_administration module, not inventory_management"""
        # This test documents that supplier_performance is in a different module
        assert True

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
