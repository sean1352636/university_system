"""
Tests for revenue_by_source_report.py module

This module tests revenue reporting functions by transaction source:
- Revenue breakdown by source (Library, Housing, Shop, Restaurant, Alumni, etc.)
- Revenue trend analysis by source
- Period comparison for sources
- CSV export functionality
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tempfile
import os
import csv
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from university_system.modules.domain.finance.reporting import revenue_by_source_report

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)

    # Create test database schema
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT
        );

        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT,
            payment_date DATE,
            status TEXT DEFAULT 'completed',
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );
    """)

    # Insert test data with various sources
    today = datetime.now().strftime('%Y-%m-%d')
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    two_months_ago = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

    cursor.executescript(f"""
        INSERT INTO students (student_id, first_name, last_name, email)
        VALUES
            ('S001', 'John', 'Doe', 'john@test.com'),
            ('S002', 'Jane', 'Smith', 'jane@test.com'),
            ('EXTERNAL', 'External', 'User', 'external@test.com');

        INSERT INTO payments (student_id, amount, payment_method, payment_date, status, notes)
        VALUES
            -- Library payments
            ('S001', 50.00, 'credit_card', '{today}', 'completed', '[Library] Late return fine'),
            ('S002', 25.00, 'cash', '{month_ago}', 'completed', '[Library] Lost book fee'),
            ('S001', 15.00, 'debit_card', '{two_months_ago}', 'completed', '[Library] Printing fee'),

            -- Housing payments
            ('S001', 800.00, 'bank_transfer', '{today}', 'completed', '[Housing] Monthly rent'),
            ('S002', 850.00, 'bank_transfer', '{month_ago}', 'completed', '[Housing] Monthly rent'),

            -- Shop payments
            ('S001', 45.00, 'credit_card', '{today}', 'completed', '[Shop] Textbook purchase'),
            ('S002', 30.00, 'cash', '{month_ago}', 'completed', '[Shop] Supplies'),

            -- Restaurant payments
            ('S001', 12.50, 'debit_card', '{today}', 'completed', '[Restaurant] Lunch'),
            ('S002', 15.00, 'credit_card', '{today}', 'completed', '[Restaurant] Dinner'),
            ('EXTERNAL', 20.00, 'cash', '{today}', 'completed', '[Restaurant] Guest meal'),

            -- Alumni payments
            ('EXTERNAL', 500.00, 'bank_transfer', '{month_ago}', 'completed', '[Alumni] Donation'),

            -- Student Union payments
            ('S001', 100.00, 'credit_card', '{today}', 'completed', '[Student Union] Membership'),

            -- Trip Management payments
            ('S001', 250.00, 'bank_transfer', '{month_ago}', 'completed', '[Trip Management] Field trip'),

            -- Tuition (no prefix)
            ('S001', 9000.00, 'bank_transfer', '{today}', 'completed', 'Tuition payment'),
            ('S002', 9000.00, 'bank_transfer', '{month_ago}', 'completed', 'Annual tuition'),

            -- Pending payment (should not be included)
            ('S001', 100.00, 'credit_card', '{today}', 'pending', '[Shop] Order pending');
    """)

    conn.commit()
    conn.close()

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except (OSError, IOError):
        pass

class TestRevenueBySource:
    """Test suite for revenue by source functions"""

    def test_get_revenue_by_source_all_time(self, temp_db):
        """Test getting revenue by source for all time"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            result = revenue_by_source_report.get_revenue_by_source()

            assert isinstance(result, dict)
            assert len(result) > 0

            # Check that major sources are present
            sources = list(result.keys())
            assert 'Tuition & Fees' in sources  # Default category

            # Check data structure
            for source, data in result.items():
                assert 'count' in data
                assert 'total' in data
                assert 'average' in data
                assert 'min' in data
                assert 'max' in data
                assert data['count'] > 0
                assert data['total'] > 0

    def test_get_revenue_by_source_with_date_filter(self, temp_db):
        """Test getting revenue by source with date filters"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            today = datetime.now().strftime('%Y-%m-%d')
            result = revenue_by_source_report.get_revenue_by_source(
                start_date=today,
                end_date=today
            )

            assert isinstance(result, dict)
            # Should have fewer results than all-time query

    def test_get_revenue_by_source_exclude_external(self, temp_db):
        """Test excluding external transactions"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            result_with_external = revenue_by_source_report.get_revenue_by_source(include_external=True)
            result_without_external = revenue_by_source_report.get_revenue_by_source(include_external=False)

            # Calculate totals
            total_with = sum(data['total'] for data in result_with_external.values())
            total_without = sum(data['total'] for data in result_without_external.values())

            # Total without external should be less
            assert total_without <= total_with

    def test_get_revenue_by_source_invalid_db(self):
        """Test handling of invalid database path"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = '/nonexistent/path/to/db.db'

            result = revenue_by_source_report.get_revenue_by_source()

            # Should return empty dict on error
            assert result == {}

class TestRevenueBySourceReport:
    """Test suite for formatted report output"""

    def test_print_revenue_by_source_report(self, temp_db, capsys):
        """Test printing revenue by source report"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            revenue_by_source_report.print_revenue_by_source_report()

            captured = capsys.readouterr()
            assert "REVENUE BY SOURCE REPORT" in captured.out
            assert "Source" in captured.out
            assert "Total Revenue" in captured.out

    def test_print_revenue_by_source_report_with_dates(self, temp_db, capsys):
        """Test printing report with date range"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            start_date = '2024-01-01'
            end_date = '2024-12-31'

            revenue_by_source_report.print_revenue_by_source_report(start_date, end_date)

            captured = capsys.readouterr()
            assert "REVENUE BY SOURCE REPORT" in captured.out
            assert start_date in captured.out
            assert end_date in captured.out

    def test_print_revenue_by_source_report_no_data(self, temp_db, capsys):
        """Test printing report with no data"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            # Use future dates where no data exists
            start_date = '2099-01-01'
            end_date = '2099-12-31'

            revenue_by_source_report.print_revenue_by_source_report(start_date, end_date)

            captured = capsys.readouterr()
            assert "No revenue data found" in captured.out

class TestSourceRevenueTrend:
    """Test suite for revenue trend analysis"""

    def test_get_source_revenue_trend(self, temp_db):
        """Test getting monthly revenue trend for a source"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            result = revenue_by_source_report.get_source_revenue_trend('Library', months=12)

            assert isinstance(result, list)
            # Each tuple should have (month, revenue, transaction_count)
            for item in result:
                assert len(item) == 3
                assert isinstance(item[0], str)  # month
                assert isinstance(item[1], float)  # revenue
                assert isinstance(item[2], int)  # transaction count

    def test_get_source_revenue_trend_housing(self, temp_db):
        """Test trend for Housing source"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            result = revenue_by_source_report.get_source_revenue_trend('Housing', months=6)

            assert isinstance(result, list)
            # Should have at least one month of housing data
            assert len(result) > 0

    def test_get_source_revenue_trend_invalid_source(self, temp_db):
        """Test trend for non-existent source"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            result = revenue_by_source_report.get_source_revenue_trend('NonExistentSource', months=12)

            # Should return empty list for non-existent source
            assert result == []

class TestPeriodComparison:
    """Test suite for period comparison"""

    def test_compare_source_revenue_periods(self, temp_db):
        """Test comparing revenue between two periods"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            today = datetime.now()
            period1_end = (today - timedelta(days=45)).strftime('%Y-%m-%d')
            period1_start = (today - timedelta(days=75)).strftime('%Y-%m-%d')
            period2_end = today.strftime('%Y-%m-%d')
            period2_start = (today - timedelta(days=30)).strftime('%Y-%m-%d')

            result = revenue_by_source_report.compare_source_revenue_periods(
                'Library',
                period1_start, period1_end,
                period2_start, period2_end
            )

            assert isinstance(result, dict)
            assert 'source' in result
            assert 'period1' in result
            assert 'period2' in result
            assert 'changes' in result

            # Check period1 structure
            assert 'start' in result['period1']
            assert 'end' in result['period1']
            assert 'transactions' in result['period1']
            assert 'revenue' in result['period1']

            # Check period2 structure
            assert 'start' in result['period2']
            assert 'end' in result['period2']
            assert 'transactions' in result['period2']
            assert 'revenue' in result['period2']

            # Check changes structure
            assert 'transaction_count' in result['changes']
            assert 'transaction_pct' in result['changes']
            assert 'revenue_amount' in result['changes']
            assert 'revenue_pct' in result['changes']

class TestCSVExport:
    """Test suite for CSV export functionality"""

    def test_export_revenue_by_source_csv(self, temp_db, tmp_path):
        """Test exporting revenue by source to CSV"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            csv_file = tmp_path / "revenue_by_source.csv"

            result = revenue_by_source_report.export_revenue_by_source_csv(str(csv_file))

            assert result is True
            assert csv_file.exists()

            # Verify CSV content
            with open(csv_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)

                assert len(rows) > 0
                # Check header
                assert rows[0] == ['Source', 'Transaction Count', 'Total Revenue',
                                   'Average Transaction', 'Min Amount', 'Max Amount']

    def test_export_revenue_by_source_csv_with_dates(self, temp_db, tmp_path):
        """Test CSV export with date filters"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            csv_file = tmp_path / "revenue_filtered.csv"
            start_date = '2024-01-01'
            end_date = '2024-12-31'

            result = revenue_by_source_report.export_revenue_by_source_csv(
                str(csv_file),
                start_date,
                end_date
            )

            assert result is True
            assert csv_file.exists()

    def test_export_revenue_by_source_csv_invalid_path(self, temp_db):
        """Test CSV export with invalid path"""
        with patch('university_system.modules.domain.finance.reporting.revenue_by_source_report.paths') as mock_paths:
            mock_paths.DEFAULT_DB_PATH = temp_db

            result = revenue_by_source_report.export_revenue_by_source_csv('/invalid/path/file.csv')

            assert result is False

class TestCLIMenu:
    """Test suite for CLI menu interface"""

    def test_revenue_by_source_menu_exit(self, monkeypatch, capsys):
        """Test exiting the menu"""
        monkeypatch.setattr('builtins.input', lambda _: '6')

        revenue_by_source_report.revenue_by_source_menu()

        captured = capsys.readouterr()
        assert "REVENUE BY SOURCE REPORTS" in captured.out

    def test_revenue_by_source_menu_invalid_option(self, monkeypatch, capsys):
        """Test invalid menu option"""
        inputs = iter(['99', '6'])  # Invalid option, then exit
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        revenue_by_source_report.revenue_by_source_menu()

        captured = capsys.readouterr()
        assert "Invalid option" in captured.out

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
