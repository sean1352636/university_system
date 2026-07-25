"""
Tests for restaurant financial reporting operations module.
Tests daily sales reports, monthly summaries, tax reports, and financial exports.
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

# Import the module to test
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations import financial_reporting
from education_system.systems.university.infrastructure import paths

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
            tax_amount REAL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
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
        CREATE TABLE restaurant_customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_expenses (
            expense_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            payment_method TEXT,
            vendor TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_daily_sales (
            date TEXT PRIMARY KEY,
            total_revenue REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            avg_order_value REAL DEFAULT 0,
            cash_sales REAL DEFAULT 0,
            card_sales REAL DEFAULT 0,
            meal_plan_sales REAL DEFAULT 0,
            total_costs REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            customer_count INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE restaurant_system_settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
    ''')

    # Insert test data
    today = datetime.now().strftime('%Y-%m-%d')

    # Insert test orders
    cursor.execute('''
        INSERT INTO restaurant_orders VALUES
        ('ORD001', 'C001', 'T001', ?, 25.50, 'Completed', 'Cash', 2.50),
        ('ORD002', 'C002', 'T002', ?, 35.75, 'Completed', 'Credit Card', 3.75),
        ('ORD003', 'C003', 'T003', ?, 42.00, 'Completed', 'Meal Plan', 4.00)
    ''', (f'{today} 12:00:00', f'{today} 13:30:00', f'{today} 14:15:00'))

    # Insert menu items
    cursor.execute('''
        INSERT INTO menu_items VALUES
        ('M001', 'Burger', 'Main'),
        ('M002', 'Salad', 'Main'),
        ('M003', 'Fries', 'Side')
    ''')

    # Insert order items
    cursor.execute('''
        INSERT INTO restaurant_order_items VALUES
        (1, 'ORD001', 'M001', 1, 25.50),
        (2, 'ORD002', 'M002', 1, 35.75),
        (3, 'ORD003', 'M003', 2, 21.00)
    ''')

    # Insert system settings
    cursor.execute('''
        INSERT INTO restaurant_system_settings VALUES
        ('tax_rate', '0.20')
    ''')

    # Insert test expenses
    cursor.execute('''
        INSERT INTO restaurant_expenses VALUES
        ('EXP001', 'Food', 50.00, ?, 'Cash', 'Vendor1'),
        ('EXP002', 'Utilities', 100.00, ?, 'Bank Transfer', 'Vendor2')
    ''', (today, today))

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

class TestDailySalesReport:
    """Test daily sales report generation"""

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_daily_sales_report_today(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test generating daily sales report for today"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        # Mock input to use today's date
        with patch('builtins.input', return_value=''):
            financial_reporting.daily_sales_report()

        captured = capsys.readouterr()
        assert 'DAILY SALES REPORT' in captured.out
        assert 'Total Orders:' in captured.out
        assert 'Total Revenue:' in captured.out

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_daily_sales_report_specific_date(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test generating daily sales report for specific date"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        test_date = datetime.now().strftime('%Y-%m-%d')

        with patch('builtins.input', return_value=test_date):
            financial_reporting.daily_sales_report()

        captured = capsys.readouterr()
        assert test_date in captured.out
        assert '£' in captured.out  # Check for currency formatting

class TestMonthlySummary:
    """Test monthly financial summary"""

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_monthly_summary_valid_month(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test generating monthly summary with valid inputs"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        current_date = datetime.now()

        with patch('builtins.input', side_effect=[str(current_date.month), str(current_date.year)]):
            financial_reporting.monthly_financial_summary()

        captured = capsys.readouterr()
        assert 'MONTHLY FINANCIAL SUMMARY' in captured.out
        assert 'REVENUE:' in captured.out
        assert 'EXPENSES:' in captured.out

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_monthly_summary_invalid_month(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test handling of invalid month input"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        with patch('builtins.input', side_effect=['13', '2024']):
            financial_reporting.monthly_financial_summary()

        captured = capsys.readouterr()
        assert 'Invalid month' in captured.out

class TestTaxReports:
    """Test tax reporting functions"""

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_generate_vat_report(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test VAT report generation"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        today = datetime.now().strftime('%Y-%m-%d')

        with patch('builtins.input', side_effect=[today, today]):
            financial_reporting.generate_vat_report()

        captured = capsys.readouterr()
        assert 'VAT REPORT' in captured.out
        assert 'VAT Rate:' in captured.out
        assert 'Net VAT Due:' in captured.out

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_generate_sales_tax_summary(self, mock_get_conn, test_db, mock_auth, capsys):
        """Test sales tax summary generation"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        current_date = datetime.now()

        with patch('builtins.input', side_effect=[str(current_date.month), str(current_date.year)]):
            financial_reporting.generate_sales_tax_summary()

        captured = capsys.readouterr()
        assert 'SALES TAX SUMMARY' in captured.out

class TestFinancialExports:
    """Test financial data export functions"""

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_export_complete_financial_data(self, mock_get_conn, test_db, mock_auth, capsys, tmp_path):
        """Test complete financial data export"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        today = datetime.now().strftime('%Y-%m-%d')

        # Change to temp directory for file creation
        os.chdir(tmp_path)

        financial_reporting.export_complete_financial_data(today, today)

        captured = capsys.readouterr()
        assert 'exported' in captured.out.lower()

        # Check that CSV file was created
        csv_files = list(tmp_path.glob('*.csv'))
        assert len(csv_files) > 0

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_export_sales_data(self, mock_get_conn, test_db, mock_auth, capsys, tmp_path):
        """Test sales data export"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        mock_get_conn.return_value = conn

        today = datetime.now().strftime('%Y-%m-%d')

        os.chdir(tmp_path)

        financial_reporting.export_sales_data(today, today)

        captured = capsys.readouterr()
        assert 'sales data exported' in captured.out.lower()

class TestPayrollExport:
    """Test payroll export functionality"""

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.get_db_connection')
    def test_export_payroll_report(self, mock_get_conn, test_db, mock_auth, capsys, tmp_path):
        """Test payroll report export"""
        financial_reporting.set_auth(mock_auth)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Add staff and schedule tables
        cursor.execute('''
            CREATE TABLE restaurant_staff (
                staff_id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                hourly_rate REAL,
                status TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE restaurant_staff_schedules (
                schedule_id TEXT PRIMARY KEY,
                staff_id TEXT,
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                actual_start TEXT,
                actual_end TEXT,
                status TEXT
            )
        ''')

        # Insert test staff
        cursor.execute('''
            INSERT INTO restaurant_staff VALUES
            ('STF001', 'John Doe', 'Chef', 15.50, 'Active')
        ''')

        today = datetime.now().strftime('%Y-%m-%d')

        # Insert test schedule
        cursor.execute('''
            INSERT INTO restaurant_staff_schedules VALUES
            ('SCH001', 'STF001', ?, '09:00:00', '17:00:00', '09:00:00', '17:00:00', 'Completed')
        ''', (today,))

        conn.commit()
        mock_get_conn.return_value = conn

        os.chdir(tmp_path)

        with patch('builtins.input', side_effect=[today, today]):
            financial_reporting.export_payroll_report()

        captured = capsys.readouterr()
        assert 'payroll' in captured.out.lower()

class TestSetAuth:
    """Test authentication setup"""

    def test_set_auth(self, mock_auth):
        """Test setting authentication instance"""
        financial_reporting.set_auth(mock_auth)
        assert financial_reporting.auth == mock_auth

    def test_set_auth_none(self):
        """Test setting None as auth"""
        financial_reporting.set_auth(None)
        assert financial_reporting.auth is None

class TestFinancialReportsMenu:
    """Test financial reports menu"""

    @patch('education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting.daily_sales_report')
    def test_display_financial_reports_daily_sales(self, mock_daily_sales, mock_auth):
        """Test selecting daily sales report from menu"""
        financial_reporting.set_auth(mock_auth)

        with patch('builtins.input', side_effect=['1', '10']):
            financial_reporting.display_financial_reports()

        mock_daily_sales.assert_called_once()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
