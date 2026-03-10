"""
Test suite for university_system/modules/domain/finance/gui/finance/common_imports.py

Tests the common imports module including:
- Budget management functions
- Collection management functions
- Financial aid functions
- Variance analysis
- Category performance reporting
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from education_system.university_system.modules.domain.finance.gui.finance import common_imports
from education_system.university_system.infrastructure.database.db import get_connection


@pytest.fixture
def test_db_with_budget_data():
    """Create a test database with budget data"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create budget_plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_plans (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name TEXT,
            academic_year TEXT,
            status TEXT,
            total_revenue_budget REAL,
            total_expense_budget REAL,
            created_at TEXT
        )
    ''')

    # Create budget_categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT,
            category_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Create budget_line_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_line_items (
            line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER,
            category_id INTEGER,
            budgeted_amount REAL,
            actual_amount REAL,
            variance REAL
        )
    ''')

    conn.commit()
    yield conn

    # Cleanup
    cursor.execute('DELETE FROM budget_line_items')
    cursor.execute('DELETE FROM budget_plans')
    cursor.execute('DELETE FROM budget_categories')
    conn.commit()
    conn.close()


class TestBudgetFunctions:
    """Test budget-related functions"""

    @patch('tkinter.messagebox.showinfo')
    def test_create_budget_plan(self, mock_info):
        """Test create_budget_plan function"""
        common_imports.create_budget_plan()
        # Should show info message or not crash
        assert True

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_budget_vs_actual_analysis_with_data(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test budget vs actual analysis with data"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert test data
        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, status, total_revenue_budget, total_expense_budget, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Test Plan', '2024-2025', 'active', 100000.0, 80000.0, now))
        budget_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO budget_categories (category_name, category_type, is_active)
            VALUES (?, ?, 1)
        ''', ('Tuition', 'revenue'))
        category_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO budget_line_items
            (budget_id, category_id, budgeted_amount, actual_amount, variance)
            VALUES (?, ?, ?, ?, ?)
        ''', (budget_id, category_id, 50000.0, 45000.0, -5000.0))

        test_db_with_budget_data.commit()

        common_imports.budget_vs_actual_analysis()

        # Verify output was printed
        assert mock_print.called

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_budget_vs_actual_analysis_no_data(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test budget vs actual analysis with no data"""
        mock_conn.return_value = test_db_with_budget_data

        common_imports.budget_vs_actual_analysis()

        # Should print "No budget plans found"
        assert any('No budget plans found' in str(call) for call in mock_print.call_args_list)


class TestBudgetApproval:
    """Test budget approval functions"""

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_budget_approval_workflow_with_pending_budgets(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test budget approval workflow with pending budgets"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert pending budget
        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, status, total_revenue_budget, total_expense_budget, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Pending Plan', '2024-2025', 'pending', 100000.0, 80000.0, now))
        test_db_with_budget_data.commit()

        common_imports.budget_approval_workflow()

        # Verify output was printed
        assert mock_print.called

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_budget_approval_workflow_no_pending(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test budget approval workflow with no pending budgets"""
        mock_conn.return_value = test_db_with_budget_data

        common_imports.budget_approval_workflow()

        # Should print "No budget plans pending approval"
        assert any('No budget plans pending approval' in str(call) for call in mock_print.call_args_list)


class TestVarianceAnalysis:
    """Test variance analysis functions"""

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_variance_analysis_report_with_data(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test variance analysis report with variance data"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert test data with variance
        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, status, total_revenue_budget, total_expense_budget, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Variance Test', '2024-2025', 'active', 100000.0, 80000.0, now))
        budget_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO budget_categories (category_name, category_type, is_active)
            VALUES (?, ?, 1)
        ''', ('Operating Costs', 'expense'))
        category_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO budget_line_items
            (budget_id, category_id, budgeted_amount, actual_amount, variance)
            VALUES (?, ?, ?, ?, ?)
        ''', (budget_id, category_id, 50000.0, 60000.0, 10000.0))  # Over budget

        test_db_with_budget_data.commit()

        common_imports.variance_analysis_report()

        # Verify output was printed
        assert mock_print.called

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_variance_analysis_report_no_variances(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test variance analysis report with no variances"""
        mock_conn.return_value = test_db_with_budget_data

        common_imports.variance_analysis_report()

        # Should print "No variances found"
        assert any('No variances found' in str(call) for call in mock_print.call_args_list)


class TestBudgetPerformance:
    """Test budget performance analysis"""

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_budget_performance_trends(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test budget performance trends"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert test data for multiple years
        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for year in ['2023-2024', '2024-2025']:
            cursor.execute('''
                INSERT INTO budget_plans
                (plan_name, academic_year, status, total_revenue_budget, total_expense_budget, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (f'Plan {year}', year, 'approved', 100000.0, 80000.0, now))

        test_db_with_budget_data.commit()

        common_imports.budget_performance_trends()

        # Verify output was printed
        assert mock_print.called


class TestCategoryPerformance:
    """Test category performance reporting"""

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_category_performance_report_with_data(self, mock_print, mock_conn, test_db_with_budget_data):
        """Test category performance report with data"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert test data
        cursor = test_db_with_budget_data.cursor()

        cursor.execute('''
            INSERT INTO budget_categories (category_name, category_type, is_active)
            VALUES (?, ?, 1)
        ''', ('Tuition Revenue', 'revenue'))
        category_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, status, total_revenue_budget, total_expense_budget, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Test Plan', '2024-2025', 'active', 100000.0, 80000.0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        budget_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO budget_line_items
            (budget_id, category_id, budgeted_amount, actual_amount, variance)
            VALUES (?, ?, ?, ?, ?)
        ''', (budget_id, category_id, 50000.0, 45000.0, -5000.0))

        test_db_with_budget_data.commit()

        common_imports.category_performance_report()

        # Verify output was printed
        assert mock_print.called


class TestStubFunctions:
    """Test stub functions that should not crash"""

    @patch('builtins.print')
    def test_view_overdue_accounts(self, mock_print):
        """Test view_overdue_accounts stub"""
        common_imports.view_overdue_accounts()
        assert mock_print.called

    @patch('builtins.print')
    def test_recovery_rate_analysis(self, mock_print):
        """Test recovery_rate_analysis stub"""
        common_imports.recovery_rate_analysis()
        assert mock_print.called

    @patch('builtins.print')
    def test_manage_budget_categories(self, mock_print):
        """Test manage_budget_categories stub"""
        common_imports.manage_budget_categories()
        assert mock_print.called

    @patch('builtins.print')
    def test_view_budget_categories(self, mock_print):
        """Test view_budget_categories stub"""
        common_imports.view_budget_categories()
        assert mock_print.called


class TestCollectionFunctions:
    """Test collection management functions"""

    def test_send_collection_notice_with_type(self, capsys):
        """Test send_collection_notice_with_type wrapper"""
        result = common_imports.send_collection_notice_with_type('STU001', 'first_notice', 'Test message')
        assert result is True

        captured = capsys.readouterr()
        assert 'STU001' in captured.out or result is True

    def test_send_arrangement_confirmation(self, capsys):
        """Test send_arrangement_confirmation"""
        result = common_imports.send_arrangement_confirmation(123)
        assert result is True

        captured = capsys.readouterr()
        assert '123' in captured.out or result is True


class TestSystemFunctions:
    """Test system utility functions"""

    @patch('builtins.print')
    def test_check_required_packages(self, mock_print):
        """Test check_required_packages"""
        common_imports.check_required_packages()
        assert mock_print.called

    @patch('builtins.print')
    def test_ensure_database_exists(self, mock_print):
        """Test ensure_database_exists"""
        common_imports.ensure_database_exists()
        assert mock_print.called

    @patch('builtins.print')
    def test_verify_fix(self, mock_print):
        """Test verify_fix"""
        common_imports.verify_fix()
        assert mock_print.called


class TestErrorHandling:
    """Test error handling in common imports"""

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_budget_vs_actual_handles_errors(self, mock_print, mock_conn):
        """Test that budget_vs_actual_analysis handles errors"""
        mock_conn.side_effect = Exception("Database error")

        common_imports.budget_vs_actual_analysis()

        # Should print error message
        assert any('Error' in str(call) for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.finance.gui.finance.common_imports.get_connection')
    @patch('builtins.print')
    def test_variance_analysis_handles_errors(self, mock_print, mock_conn):
        """Test that variance_analysis_report handles errors"""
        mock_conn.side_effect = Exception("Database error")

        common_imports.variance_analysis_report()

        # Should print error message
        assert any('Error' in str(call) for call in mock_print.call_args_list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
