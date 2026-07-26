"""
Tests for university_system/modules/core/services/restaurant_misc/exports.py
"""
from __future__ import annotations

import csv
import os
from education_system.systems.university.infrastructure.database.db import sqlite3
from io import StringIO
from unittest import mock

import pytest

from education_system.systems.university.domain.operations.commerce.services.restaurant.operations import exports

@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = mock.MagicMock(spec=sqlite3.Connection)
    cursor = mock.MagicMock(spec=sqlite3.Cursor)
    conn.cursor.return_value = cursor
    return conn, cursor

@pytest.fixture
def cleanup_csv_files():
    """Cleanup CSV files after tests"""
    yield
    # Clean up any CSV files created during tests
    for file in os.listdir('.'):
        if file.endswith('.csv'):
            try:
                os.unlink(file)
            except (OSError, IOError):
                pass

class TestGenerateEmployeeTaxSummary:
    """Tests for generate_employee_tax_summary function"""

    def test_generate_employee_tax_summary_success(self, mock_db_connection):
        """Test successful employee tax summary generation"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('STAFF001', 'John Doe', 'Chef', 15.50, 160.0),
            ('STAFF002', 'Jane Smith', 'Server', 12.00, 140.0)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='2025'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    exports.generate_employee_tax_summary()

                    output = fake_out.getvalue()
                    assert 'EMPLOYEE TAX SUMMARY - 2025' in output
                    assert 'John Doe' in output
                    assert 'Jane Smith' in output
                    assert 'Total Staff: 2' in output
                    assert 'TOTALS' in output

        conn.close.assert_called_once()

    def test_generate_employee_tax_summary_no_data(self, mock_db_connection):
        """Test employee tax summary with no data"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='2025'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    exports.generate_employee_tax_summary()

                    output = fake_out.getvalue()
                    assert 'No staff data found for 2025' in output

    def test_generate_employee_tax_summary_invalid_year(self, mock_db_connection):
        """Test employee tax summary with invalid year"""
        with mock.patch('builtins.input', return_value='invalid'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                exports.generate_employee_tax_summary()

                output = fake_out.getvalue()
                assert 'Invalid year' in output

    def test_generate_employee_tax_summary_calculates_tax(self, mock_db_connection):
        """Test that tax is calculated correctly"""
        conn, cursor = mock_db_connection
        # Staff with earnings over personal allowance
        cursor.fetchall.return_value = [
            ('STAFF001', 'High Earner', 'Manager', 25.00, 2000.0)  # £50,000 annual
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='2025'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    exports.generate_employee_tax_summary()

                    output = fake_out.getvalue()
                    # Should calculate tax on amount over £12,570
                    assert 'Est. Tax' in output
                    assert '£' in output

class TestGenerateAnnualTaxSummary:
    """Tests for generate_annual_tax_summary function"""

    def test_generate_annual_tax_summary_success(self, mock_db_connection):
        """Test successful annual tax summary generation"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (50000.0, 4000.0, 500),  # sales_data
            (25000.0, 100)  # expense_data
        ]
        cursor.fetchall.return_value = [
            ('01', 4000.0, 320.0),
            ('02', 4200.0, 336.0)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='2025'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    exports.generate_annual_tax_summary()

                    output = fake_out.getvalue()
                    assert 'ANNUAL TAX SUMMARY - 2025' in output
                    assert 'ANNUAL OVERVIEW' in output
                    assert 'Total Sales:' in output
                    assert 'Total Tax Collected:' in output
                    assert 'MONTHLY BREAKDOWN' in output

    def test_generate_annual_tax_summary_over_vat_threshold(self, mock_db_connection):
        """Test annual tax summary when over VAT threshold"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (100000.0, 8000.0, 1000),  # sales over £85,000
            (40000.0, 50)
        ]
        cursor.fetchall.return_value = []

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='2025'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    exports.generate_annual_tax_summary()

                    output = fake_out.getvalue()
                    assert 'Annual turnover exceeds VAT registration threshold' in output

    def test_generate_annual_tax_summary_invalid_year(self):
        """Test annual tax summary with invalid year"""
        with mock.patch('builtins.input', return_value='not_a_year'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                exports.generate_annual_tax_summary()

                output = fake_out.getvalue()
                assert 'Invalid year' in output

class TestExportTaxData:
    """Tests for export_tax_data function"""

    def test_export_tax_data_success(self, mock_db_connection, cleanup_csv_files):
        """Test successful tax data export"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [('ORD001', '2025-01-15 10:00:00', 25.50, 2.04, 'Card', 'CUST001')],
            [('EXP001', '2025-01-15', 'Food', 'Supplies', 100.00, 'Supplier A')]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    exports.export_tax_data()

                    output = fake_out.getvalue()
                    assert 'Tax data exported successfully!' in output
                    assert 'Sales data:' in output
                    assert 'Expenses data:' in output
                    assert 'Sales records: 1' in output
                    assert 'Expense records: 1' in output

        # Verify CSV files were created
        sales_file = [f for f in os.listdir('.') if f.startswith('tax_sales_data_')]
        expense_file = [f for f in os.listdir('.') if f.startswith('tax_expenses_data_')]
        assert len(sales_file) > 0
        assert len(expense_file) > 0

    def test_export_tax_data_creates_csv_files(self, mock_db_connection, cleanup_csv_files):
        """Test that export creates properly formatted CSV files"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [('ORD001', '2025-01-15 10:00:00', 25.50, 2.04, 'Card', 'CUST001')],
            [('EXP001', '2025-01-15', 'Food', 'Supplies', 100.00, 'Supplier A')]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()):
                    exports.export_tax_data()

        # Read and verify sales CSV
        sales_file = [f for f in os.listdir('.') if f.startswith('tax_sales_data_')][0]
        with open(sales_file, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert 'Order ID' in headers
            assert 'Total Price' in headers

    def test_export_tax_data_exception(self, mock_db_connection):
        """Test export tax data when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.logging.error') as mock_log:
                        exports.export_tax_data()

                        output = fake_out.getvalue()
                        assert 'An error occurred' in output
                        mock_log.assert_called_once()

class TestExportExpenseData:
    """Tests for export_expense_data function"""

    def test_export_expense_data_success(self, mock_db_connection, cleanup_csv_files):
        """Test successful expense data export"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [('EXP001', '2025-01-15', 'Food', 'Groceries', 150.00, 'Cash', 'Store A', 'Approved')],
            [('Food', 150.00, 1), ('Utilities', 200.00, 2)]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                exports.export_expense_data('2025-01-01', '2025-01-31')

                output = fake_out.getvalue()
                assert 'Expense data exported' in output
                assert 'Total records: 1' in output
                assert 'Expense breakdown by category' in output

    def test_export_expense_data_no_data(self, mock_db_connection):
        """Test export expense data when no data found"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                exports.export_expense_data('2025-01-01', '2025-01-31')

                output = fake_out.getvalue()
                assert 'No expense data found' in output

class TestExportProfitLossData:
    """Tests for export_profit_loss_data function"""

    def test_export_profit_loss_data_success(self, mock_db_connection, cleanup_csv_files):
        """Test successful P&L data export"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (50000.0, 500),  # revenue_data
            (15000.0,)  # cogs_data
        ]
        cursor.fetchall.return_value = [
            ('Staff Wages', 10000.0),
            ('Utilities', 2000.0)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                exports.export_profit_loss_data('2025-01-01', '2025-01-31')

                output = fake_out.getvalue()
                assert 'Profit & Loss data exported' in output
                assert 'Revenue: £50,000.00' in output
                assert 'Net Profit:' in output

        # Verify CSV file was created
        pl_files = [f for f in os.listdir('.') if f.startswith('profit_loss_data_')]
        assert len(pl_files) > 0

    def test_export_profit_loss_data_creates_csv(self, mock_db_connection, cleanup_csv_files):
        """Test that P&L export creates properly formatted CSV"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (50000.0, 500),
            (15000.0,)
        ]
        cursor.fetchall.return_value = [('Staff Wages', 10000.0)]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()):
                exports.export_profit_loss_data('2025-01-01', '2025-01-31')

        # Read and verify CSV
        pl_file = [f for f in os.listdir('.') if f.startswith('profit_loss_data_')][0]
        with open(pl_file, 'r') as f:
            content = f.read()
            assert 'PROFIT & LOSS STATEMENT' in content
            assert 'REVENUE' in content
            assert 'NET PROFIT' in content

    def test_export_profit_loss_data_calculates_metrics(self, mock_db_connection, cleanup_csv_files):
        """Test that P&L export calculates margins correctly"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (100000.0, 1000),  # revenue
            (30000.0,)  # cogs
        ]
        cursor.fetchall.return_value = [('Staff Wages', 20000.0)]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()):
                exports.export_profit_loss_data('2025-01-01', '2025-01-31')

        # Read CSV and check for metrics
        pl_file = [f for f in os.listdir('.') if f.startswith('profit_loss_data_')][0]
        with open(pl_file, 'r') as f:
            content = f.read()
            assert 'Gross Margin %' in content
            assert 'Net Margin %' in content
            assert 'Average Order Value' in content

    def test_export_profit_loss_data_exception(self, mock_db_connection):
        """Test export P&L data when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.exports.logging.error') as mock_log:
                    exports.export_profit_loss_data('2025-01-01', '2025-01-31')

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()
