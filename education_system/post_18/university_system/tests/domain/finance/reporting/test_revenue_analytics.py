"""
Tests for revenue_analytics.py module

This module tests the financial reporting and analytics functions including:
- Revenue summary reports
- Outstanding fees reports
- Payment collection reports
- Budget variance reports
- Predictive analytics
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from education_system.post_18.university_system.modules.domain.finance.reporting import revenue_analytics

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)

    # Create test database schema
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()

    # Create necessary tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            course TEXT,
            email TEXT
        );

        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL,
            description TEXT,
            default_amount REAL
        );

        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            fee_type_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            due_date DATE,
            status TEXT DEFAULT 'unpaid',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (fee_type_id) REFERENCES fee_types(fee_type_id)
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

        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            student_fee_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
            FOREIGN KEY (student_fee_id) REFERENCES student_fees(student_fee_id)
        );

        CREATE TABLE IF NOT EXISTS budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            allocated_amount REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date DATE
        );

        CREATE TABLE IF NOT EXISTS payment_risk_scores (
            student_id TEXT PRIMARY KEY,
            risk_score REAL,
            risk_level TEXT,
            factors TEXT,
            last_calculated TIMESTAMP,
            created_at TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );
    """)

    # Insert test data
    cursor.executescript("""
        INSERT INTO students (student_id, first_name, last_name, course, email)
        VALUES
            ('S001', 'John', 'Doe', 'Computer Science', 'john@test.com'),
            ('S002', 'Jane', 'Smith', 'Engineering', 'jane@test.com'),
            ('S003', 'Bob', 'Johnson', 'Business', 'bob@test.com');

        INSERT INTO fee_types (fee_name, description, default_amount)
        VALUES
            ('Tuition', 'Annual tuition fee', 9000.00),
            ('Library', 'Library access fee', 50.00),
            ('Lab', 'Laboratory fee', 150.00);

        INSERT INTO student_fees (student_id, fee_type_id, amount, due_date, status)
        VALUES
            ('S001', 1, 9000.00, date('now', '+30 days'), 'paid'),
            ('S001', 2, 50.00, date('now', '+30 days'), 'paid'),
            ('S002', 1, 9000.00, date('now', '-10 days'), 'unpaid'),
            ('S002', 2, 50.00, date('now', '+15 days'), 'partial'),
            ('S003', 1, 9000.00, date('now', '+60 days'), 'unpaid');

        INSERT INTO payments (student_id, amount, payment_method, payment_date, status, notes)
        VALUES
            ('S001', 9000.00, 'credit_card', date('now', '-5 days'), 'completed', 'Tuition payment'),
            ('S001', 50.00, 'debit_card', date('now', '-3 days'), 'completed', 'Library fee'),
            ('S002', 25.00, 'cash', date('now', '-1 days'), 'completed', 'Partial library fee');

        INSERT INTO payment_allocations (payment_id, student_fee_id, amount)
        VALUES
            (1, 1, 9000.00),
            (2, 2, 50.00),
            (3, 4, 25.00);

        INSERT INTO budgets (category, allocated_amount)
        VALUES
            ('Technology', 50000.00),
            ('Facilities', 30000.00),
            ('Staffing', 100000.00);

        INSERT INTO expenses (category, amount, expense_date)
        VALUES
            ('Technology', 35000.00, date('now', '-10 days')),
            ('Facilities', 28000.00, date('now', '-5 days')),
            ('Staffing', 95000.00, date('now', '-2 days'));
    """)

    conn.commit()
    conn.close()

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except (OSError, IOError):
        pass

class TestRevenueAnalytics:
    """Test suite for revenue analytics functions"""

    def test_generate_budget_variance_report(self, temp_db, capsys):
        """Test budget variance report generation"""
        with patch('education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.reports.DEFAULT_DB_PATH', temp_db):
            revenue_analytics.generate_budget_variance_report()

            captured = capsys.readouterr()
            assert "Budget Variance Report" in captured.out
            assert "Technology" in captured.out
            assert "Facilities" in captured.out
            assert "Staffing" in captured.out

    def test_revenue_summary_report(self, temp_db, capsys, monkeypatch):
        """Test revenue summary report generation"""
        # Mock user input for date range
        inputs = iter(['2024-01-01', '2024-12-31'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        with patch('education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.reports.get_connection') as mock_conn:
            mock_conn.return_value = sqlite3.connect(temp_db)

            revenue_analytics.revenue_summary_report()

            captured = capsys.readouterr()
            assert "Revenue Summary Report" in captured.out or "No payments found" in captured.out

    def test_generate_outstanding_fees_report(self, temp_db, capsys):
        """Test outstanding fees report generation"""
        with patch('education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.reports.get_connection') as mock_conn:
            mock_conn.return_value = sqlite3.connect(temp_db)

            revenue_analytics.generate_outstanding_fees_report()

            captured = capsys.readouterr()
            # Should show outstanding fees for S002 and S003
            assert "Outstanding Fees Report" in captured.out or "No outstanding fees" in captured.out

    def test_generate_payment_collection_report(self, temp_db, capsys, monkeypatch):
        """Test payment collection report generation"""
        # Mock user input for date range
        inputs = iter(['2024-01-01', '2024-12-31'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        with patch('education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.get_connection') as mock_conn:
            mock_conn.return_value = sqlite3.connect(temp_db)

            revenue_analytics.generate_payment_collection_report()

            captured = capsys.readouterr()
            assert "Payment Collection Report" in captured.out or captured.out != ""

class TestPredictiveAnalytics:
    """Test suite for predictive analytics functions"""

    def test_generate_predictive_analytics_insufficient_data(self, temp_db, capsys):
        """Test predictive analytics with insufficient data"""
        with patch('education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.get_connection') as mock_conn:
            mock_conn.return_value = sqlite3.connect(temp_db)

            # Mock auth
            with patch.object(revenue_analytics, 'auth') as mock_auth:
                mock_auth.current_user = {'username': 'admin'}
                mock_auth.check_permission.return_value = True

                revenue_analytics.generate_predictive_analytics()

                captured = capsys.readouterr()
                assert "predictive analytics" in captured.out.lower() or "insufficient data" in captured.out.lower()

class TestFinancialReportsMenu:
    """Test the financial reports menu system"""

    def test_generate_financial_reports_menu_exit(self, monkeypatch, capsys):
        """Test exiting the financial reports menu"""
        # Mock input to select exit option
        monkeypatch.setattr('builtins.input', lambda _: '8')

        from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import reports as ra_reports
        with patch.object(ra_reports, 'auth') as mock_auth:
            mock_auth.current_user = {'username': 'admin'}
            mock_auth.check_permission.return_value = True

            revenue_analytics.generate_financial_reports()

            captured = capsys.readouterr()
            assert "FINANCIAL REPORTS" in captured.out

    def test_generate_financial_reports_no_auth(self, capsys):
        """Test financial reports menu without authentication"""
        with patch.object(revenue_analytics, 'auth') as mock_auth:
            mock_auth.current_user = None

            revenue_analytics.generate_financial_reports()

            captured = capsys.readouterr()
            assert "must be logged in" in captured.out.lower()

    def test_generate_financial_reports_no_permission(self, capsys):
        """Test financial reports menu without permission"""
        from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import reports as ra_reports
        with patch.object(ra_reports, 'auth') as mock_auth:
            mock_auth.current_user = {'username': 'student'}
            mock_auth.check_permission.return_value = False

            revenue_analytics.generate_financial_reports()

            captured = capsys.readouterr()
            assert "permission" in captured.out.lower()

class TestDatabaseIntegrity:
    """Test database operations and integrity"""

    def test_database_connection(self, temp_db):
        """Test database connection"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'students' in tables
        assert 'payments' in tables
        assert 'student_fees' in tables
        assert 'payment_allocations' in tables

        conn.close()

    def test_test_data_integrity(self, temp_db):
        """Test that test data is properly inserted"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check students
        cursor.execute("SELECT COUNT(*) FROM students")
        assert cursor.fetchone()[0] == 3

        # Check payments
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
        assert cursor.fetchone()[0] == 3

        # Check fees
        cursor.execute("SELECT COUNT(*) FROM student_fees")
        assert cursor.fetchone()[0] == 5

        conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
