"""
Tests for restaurant order processing operations module.
Tests order viewing, payment processing, refunds, and purchase orders.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import os
import tempfile

# Import the module to test
from education_system.university_system.modules.domain.commerce.services.restaurant.operations import order_processing
from education_system.university_system.modules.shared.constants import paths

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute('''
        CREATE TABLE restaurant_orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            table_id TEXT,
            order_time TEXT NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL,
            payment_method TEXT,
            discount_applied REAL DEFAULT 0,
            tip_amount REAL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            special_instructions TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE menu_items (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_tables (
            table_id TEXT PRIMARY KEY,
            capacity INTEGER,
            status TEXT DEFAULT 'Available',
            current_order_id TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_meal_plans (
            plan_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            balance REAL NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_meal_plan_transactions (
            transaction_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            balance_before REAL,
            balance_after REAL,
            reference_id TEXT,
            transaction_date TEXT,
            description TEXT
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

    cursor.execute('''
        CREATE TABLE restaurant_purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            unit_cost REAL NOT NULL,
            total_cost REAL NOT NULL,
            received_quantity REAL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_inventory (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            quantity REAL NOT NULL
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

    # Insert test data
    today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        INSERT INTO restaurant_orders VALUES
        ('ORD001', 'C001', 'T001', ?, 50.00, 'Pending', NULL, 0, 0),
        ('ORD002', 'C002', 'T002', ?, 75.50, 'Completed', 'Cash', 0, 5.00)
    ''', (today, today))

    cursor.execute('''
        INSERT INTO menu_items VALUES
        ('M001', 'Burger'),
        ('M002', 'Salad')
    ''')

    cursor.execute('''
        INSERT INTO restaurant_order_items VALUES
        (1, 'ORD001', 'M001', 2, 25.00, 'No onions'),
        (2, 'ORD002', 'M002', 1, 75.50, NULL)
    ''')

    cursor.execute('''
        INSERT INTO restaurant_customers VALUES
        ('C001', 'John Doe', 'john@example.com'),
        ('C002', 'Jane Smith', 'jane@example.com')
    ''')

    cursor.execute('''
        INSERT INTO restaurant_tables VALUES
        ('T001', 4, 'Occupied', 'ORD001'),
        ('T002', 2, 'Available', NULL)
    ''')

    cursor.execute('''
        INSERT INTO restaurant_meal_plans VALUES
        ('MP001', 'C001', 100.00, 'Active')
    ''')

    cursor.execute('''
        INSERT INTO restaurant_suppliers VALUES
        ('SUP001', 'Fresh Foods Ltd', 'Active')
    ''')

    cursor.execute('''
        INSERT INTO restaurant_inventory VALUES
        ('INV001', 'Tomatoes', 50.0)
    ''')

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

class TestViewOrders:
    """Test order viewing functions"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_view_orders_all(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing all orders"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['1', '']):
            order_processing.view_orders()

        captured = capsys.readouterr()
        assert 'ORDERS' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_view_order_details(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing specific order details"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        order_processing.view_order_details('ORD001')

        captured = capsys.readouterr()
        assert 'ORDER DETAILS' in captured.out
        assert 'ORD001' in captured.out

class TestPaymentProcessing:
    """Test payment processing functions"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.record_payment_to_finance')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_process_cash_payment(self, mock_get_conn, mock_log, mock_record_payment, test_db, mock_auth, capsys):
        """Test processing cash payment"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn
        mock_record_payment.return_value = 'PAY123'

        with patch('builtins.input', side_effect=['ORD001', '60.00']):
            order_processing.process_cash_payment()

        captured = capsys.readouterr()
        assert 'Payment processed successfully' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.record_payment_to_finance')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_process_card_payment(self, mock_sleep, mock_get_conn, mock_log, mock_record_payment, test_db, mock_auth, capsys):
        """Test processing card payment"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn
        mock_record_payment.return_value = 'PAY124'

        with patch('builtins.input', side_effect=['ORD001', '1']):
            order_processing.process_card_payment()

        captured = capsys.readouterr()
        assert 'Card payment approved' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.record_payment_to_finance')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_process_meal_plan_payment(self, mock_get_conn, mock_log, mock_record_payment, test_db, mock_auth, capsys):
        """Test processing meal plan payment"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn
        mock_record_payment.return_value = 'PAY125'

        with patch('builtins.input', return_value='ORD001'):
            order_processing.process_meal_plan_payment()

        captured = capsys.readouterr()
        assert 'Meal plan payment' in captured.out or 'processed' in captured.out.lower()

class TestTipManagement:
    """Test tip functionality"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_add_tip_custom(self, mock_get_conn, mock_log, test_db, mock_auth, capsys):
        """Test adding custom tip amount"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['ORD002', '1', '10.00']):
            order_processing.add_tip()

        captured = capsys.readouterr()
        assert 'Tip added' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_add_tip_percentage(self, mock_get_conn, mock_log, test_db, mock_auth, capsys):
        """Test adding percentage-based tip"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['ORD002', '2']):  # 10%
            order_processing.add_tip()

        captured = capsys.readouterr()
        assert 'Tip added' in captured.out

class TestRefundProcessing:
    """Test refund functionality"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_refund_order_full(self, mock_get_conn, mock_log, mock_backup, test_db, mock_auth, capsys):
        """Test processing full refund"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['ORD002', 'Customer dissatisfied', '1']):
            order_processing.refund_order()

        captured = capsys.readouterr()
        assert 'Refund processed' in captured.out

class TestDiscountApplication:
    """Test discount functionality"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_apply_discount_percentage(self, mock_get_conn, mock_log, test_db, mock_auth, capsys):
        """Test applying percentage discount"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['ORD001', '1', '10']):  # 10% discount
            order_processing.apply_discount()

        captured = capsys.readouterr()
        assert 'Discount applied' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_apply_discount_fixed(self, mock_get_conn, mock_log, test_db, mock_auth, capsys):
        """Test applying fixed amount discount"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['ORD001', '2', '5.00']):
            order_processing.apply_discount()

        captured = capsys.readouterr()
        assert 'Discount applied' in captured.out

class TestOrderStatusUpdate:
    """Test order status management"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_update_order_status(self, mock_get_conn, mock_log, mock_backup, test_db, mock_auth, capsys):
        """Test updating order status"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['ORD001', '4']):  # Set to Completed
            order_processing.update_order_status()

        captured = capsys.readouterr()
        assert 'status updated' in captured.out

class TestPurchaseOrders:
    """Test purchase order management"""

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_view_purchase_orders(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test viewing purchase orders"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert test PO
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO restaurant_purchase_orders VALUES
            ('PO001', 'SUP001', ?, ?, NULL, 100.00, 'Pending', NULL, 'admin')
        ''', (today, today))
        conn.commit()

        mock_get_conn.return_value = conn

        with patch('builtins.input', return_value='1'):
            order_processing.view_purchase_orders()

        captured = capsys.readouterr()
        assert 'PURCHASE ORDERS' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_create_purchase_order(self, mock_get_conn, mock_log, mock_backup, test_db, mock_auth, capsys):
        """Test creating a purchase order"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        today = datetime.now().strftime('%Y-%m-%d')

        inputs = ['1', today, 'Test notes', 'Test Item', '10', 'kg', '5.00', 'done']

        with patch('builtins.input', side_effect=inputs):
            order_processing.create_purchase_order()

        captured = capsys.readouterr()
        assert 'Purchase Order created successfully' in captured.out

    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.backup_before_operation')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.log_audit_action')
    @patch('university_system.modules.domain.commerce.services.restaurant.operations.order_processing.get_db_connection')
    def test_update_purchase_order(self, mock_get_conn, mock_log, mock_backup, test_db, mock_auth, capsys):
        """Test updating purchase order status"""
        order_processing.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert test PO
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO restaurant_purchase_orders VALUES
            ('PO002', 'SUP001', ?, ?, NULL, 100.00, 'Pending', NULL, 'admin')
        ''', (today, today))
        conn.commit()

        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['PO002', '2']):  # Update to Ordered
            order_processing.update_purchase_order()

        captured = capsys.readouterr()
        assert 'status updated' in captured.out

class TestSetAuth:
    """Test authentication setup"""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance"""
        order_processing.set_auth(mock_auth)
        assert order_processing.auth == mock_auth

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
