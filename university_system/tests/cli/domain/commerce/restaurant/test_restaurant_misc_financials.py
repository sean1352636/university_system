"""
Tests for university_system/modules/core/services/restaurant_misc/financials.py
"""
from __future__ import annotations

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from io import StringIO
from unittest import mock

import pytest

from university_system.modules.domain.commerce.services.restaurant.operations.connection import financials

@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = mock.MagicMock(spec=sqlite3.Connection)
    cursor = mock.MagicMock(spec=sqlite3.Cursor)
    conn.cursor.return_value = cursor
    return conn, cursor

@pytest.fixture
def mock_auth():
    """Mock authentication context"""
    auth = mock.MagicMock()
    auth.current_user = {'id': 'USER001', 'username': 'testuser'}
    auth.check_permission.return_value = True
    return auth

class TestProfitLossStatement:
    """Tests for profit_loss_statement function"""

    def test_profit_loss_statement_success(self, mock_db_connection):
        """Test successful P&L statement generation"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (50000.0,),  # revenue
            (15000.0,),  # cogs
        ]
        cursor.fetchall.return_value = [
            ('Staff Wages', 10000.0),
            ('Utilities', 2000.0)
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    financials.profit_loss_statement()

                    output = fake_out.getvalue()
                    assert 'PROFIT & LOSS STATEMENT' in output
                    assert 'REVENUE' in output
                    assert 'Total Sales Revenue: £50,000.00' in output
                    assert 'COST OF GOODS SOLD' in output
                    assert 'OPERATING EXPENSES' in output
                    assert 'PROFITABILITY' in output

    def test_profit_loss_statement_calculates_margins(self, mock_db_connection):
        """Test that P&L calculates margins correctly"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (100000.0,),  # revenue
            (30000.0,),  # cogs
        ]
        cursor.fetchall.return_value = [('Staff Wages', 20000.0)]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    financials.profit_loss_statement()

                    output = fake_out.getvalue()
                    # Gross profit = 100000 - 30000 = 70000
                    # Gross margin = 70%
                    assert 'Gross Margin: 70.0%' in output
                    # Operating profit = 70000 - 20000 = 50000
                    # Operating margin = 50%
                    assert 'Operating Margin: 50.0%' in output

    def test_profit_loss_statement_exception(self, mock_db_connection):
        """Test P&L statement when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = Exception("Database error")

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    with mock.patch('university_system.modules.core.services.restaurant_misc.financials.logging.error') as mock_log:
                        financials.profit_loss_statement()

                        output = fake_out.getvalue()
                        assert 'An error occurred' in output
                        mock_log.assert_called_once()

class TestExpenseTracking:
    """Tests for expense_tracking function"""

    def test_expense_tracking_menu(self):
        """Test expense tracking menu display"""
        with mock.patch('builtins.input', return_value='5'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.expense_tracking()

                output = fake_out.getvalue()
                assert 'EXPENSE TRACKING' in output
                assert '1. Add new expense' in output
                assert '2. View expenses' in output

    def test_expense_tracking_add_expense(self):
        """Test choosing add expense option"""
        with mock.patch('builtins.input', side_effect=['1', '5']):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.add_expense') as mock_add:
                with mock.patch('sys.stdout', new=StringIO()):
                    financials.expense_tracking()
                    # First iteration calls add_expense, second exits
                    mock_add.assert_called_once()

    def test_expense_tracking_invalid_choice(self):
        """Test invalid menu choice"""
        with mock.patch('builtins.input', side_effect=['invalid', '5']):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.expense_tracking()

                output = fake_out.getvalue()
                assert 'Invalid choice' in output

class TestAddExpense:
    """Tests for add_expense function"""

    def test_add_expense_success(self, mock_db_connection, mock_auth):
        """Test successful expense addition"""
        conn, cursor = mock_db_connection

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('university_system.modules.core.services.restaurant_misc.financials.backup_before_operation'):
                    with mock.patch('university_system.modules.core.services.restaurant_misc.financials.log_audit_action') as mock_log:
                        with mock.patch('builtins.input', side_effect=['1', 'Test expense', '100.50', '', '1', 'Test Vendor', '']):
                            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                                financials.add_expense()

                                output = fake_out.getvalue()
                                assert 'Expense added successfully!' in output
                                assert 'Amount: £100.50' in output

                                cursor.execute.assert_called_once()
                                mock_log.assert_called_once()

    def test_add_expense_no_auth(self):
        """Test add expense when not logged in"""
        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
            mock_ctx.auth = None

            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.add_expense()

                output = fake_out.getvalue()
                assert 'You must be logged in' in output

    def test_add_expense_no_permission(self, mock_auth):
        """Test add expense without permission"""
        mock_auth.check_permission.return_value = False

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
            mock_ctx.auth = mock_auth

            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.add_expense()

                output = fake_out.getvalue()
                assert "You don't have permission" in output

    def test_add_expense_invalid_amount(self, mock_db_connection, mock_auth):
        """Test add expense with invalid amount"""
        conn, cursor = mock_db_connection

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('university_system.modules.core.services.restaurant_misc.financials.backup_before_operation'):
                    with mock.patch('builtins.input', side_effect=['1', 'Test', 'invalid']):
                        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                            financials.add_expense()

                            output = fake_out.getvalue()
                            assert 'Invalid amount' in output

    def test_add_expense_custom_category(self, mock_db_connection, mock_auth):
        """Test add expense with custom category"""
        conn, cursor = mock_db_connection

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('university_system.modules.core.services.restaurant_misc.financials.backup_before_operation'):
                    with mock.patch('university_system.modules.core.services.restaurant_misc.financials.log_audit_action'):
                        with mock.patch('builtins.input', side_effect=['9', 'Custom Category', 'Test', '50', '', '1', 'Vendor', '']):
                            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                                financials.add_expense()

                                output = fake_out.getvalue()
                                assert 'Expense added successfully!' in output
                                assert 'Custom Category' in output

class TestViewExpenses:
    """Tests for view_expenses function"""

    def test_view_expenses_all(self, mock_db_connection):
        """Test viewing all expenses"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('EXP001', 'Food & Beverages', 'Groceries', 150.00, '2025-01-15', 'Cash', 'Store A', None, None, 'Approved', None, None)
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    financials.view_expenses()

                    output = fake_out.getvalue()
                    assert 'EXPENSES' in output
                    assert 'EXP001' in output
                    assert 'TOTAL' in output

    def test_view_expenses_by_category(self, mock_db_connection):
        """Test viewing expenses filtered by category"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2', 'Food & Beverages']):
                with mock.patch('sys.stdout', new=StringIO()):
                    financials.view_expenses()

                    assert 'WHERE category = ?' in cursor.execute.call_args[0][0]

    def test_view_expenses_no_results(self, mock_db_connection):
        """Test viewing expenses when no results"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    financials.view_expenses()

                    output = fake_out.getvalue()
                    assert 'No expenses found' in output

class TestBudgetManagement:
    """Tests for budget_management function"""

    def test_budget_management_menu(self):
        """Test budget management menu display"""
        with mock.patch('builtins.input', return_value='5'):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.budget_management()

                output = fake_out.getvalue()
                assert 'BUDGET MANAGEMENT' in output
                assert '1. View budgets' in output
                assert '2. Create budget' in output

class TestViewBudgets:
    """Tests for view_budgets function"""

    def test_view_budgets_all(self, mock_db_connection):
        """Test viewing all budgets"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('BUD001', 'Food & Beverages', '2025-01-01', '2025-12-31', 50000.0, 25000.0, '2025-01-01', 'USER001', None)
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    financials.view_budgets()

                    output = fake_out.getvalue()
                    assert 'BUDGET OVERVIEW' in output
                    assert 'BUD001' in output
                    assert 'Food & Beverages' in output

    def test_view_budgets_over_budget(self, mock_db_connection):
        """Test viewing over budget items"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('BUD001', 'Utilities', '2025-01-01', '2025-12-31', 10000.0, 12000.0, '2025-01-01', 'USER001', None)
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='4'):
                with mock.patch('sys.stdout', new=StringIO()):
                    financials.view_budgets()

                    assert 'WHERE spent_amount > allocated_amount' in cursor.execute.call_args[0][0]

class TestCreateBudget:
    """Tests for create_budget function"""

    def test_create_budget_success(self, mock_db_connection, mock_auth):
        """Test successful budget creation"""
        conn, cursor = mock_db_connection

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('university_system.modules.core.services.restaurant_misc.financials.backup_before_operation'):
                    with mock.patch('university_system.modules.core.services.restaurant_misc.financials.log_audit_action') as mock_log:
                        with mock.patch('builtins.input', side_effect=['1', '2025-01-01', '2025-12-31', '50000', 'Test notes']):
                            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                                financials.create_budget()

                                output = fake_out.getvalue()
                                assert 'Budget created successfully!' in output

                                cursor.execute.assert_called_once()
                                mock_log.assert_called_once()

    def test_create_budget_no_permission(self, mock_auth):
        """Test create budget without permission"""
        mock_auth.check_permission.return_value = False

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
            mock_ctx.auth = mock_auth

            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.create_budget()

                output = fake_out.getvalue()
                assert "You don't have permission" in output

class TestUpdateBudget:
    """Tests for update_budget function"""

    def test_update_budget_allocated_amount(self, mock_db_connection, mock_auth):
        """Test updating budget allocated amount"""
        conn, cursor = mock_db_connection
        cursor.fetchone.return_value = ('BUD001', 'Food', '2025-01-01', '2025-12-31', 50000.0, 25000.0, None, None, None)

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('university_system.modules.core.services.restaurant_misc.financials.backup_before_operation'):
                    with mock.patch('university_system.modules.core.services.restaurant_misc.financials.log_audit_action'):
                        with mock.patch('builtins.input', side_effect=['BUD001', '1', '60000']):
                            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                                financials.update_budget()

                                output = fake_out.getvalue()
                                assert 'Budget updated successfully!' in output

    def test_update_budget_not_found(self, mock_db_connection, mock_auth):
        """Test updating non-existent budget"""
        conn, cursor = mock_db_connection
        cursor.fetchone.return_value = None

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('university_system.modules.core.services.restaurant_misc.financials.ctx') as mock_ctx:
                mock_ctx.auth = mock_auth

                with mock.patch('university_system.modules.core.services.restaurant_misc.financials.backup_before_operation'):
                    with mock.patch('builtins.input', return_value='INVALID'):
                        with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                            financials.update_budget()

                            output = fake_out.getvalue()
                            assert 'Budget not found' in output

class TestBudgetVsActual:
    """Tests for budget_vs_actual function"""

    def test_budget_vs_actual_success(self, mock_db_connection):
        """Test budget vs actual analysis"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [('BUD001', 'Food', 50000.0, 35000.0, '2025-01-01', '2025-12-31')],  # current_budgets
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.budget_vs_actual()

                output = fake_out.getvalue()
                assert 'BUDGET VS ACTUAL ANALYSIS' in output
                assert 'BUDGET PERFORMANCE' in output
                assert 'Food' in output
                assert 'BUDGET INSIGHTS' in output

    def test_budget_vs_actual_over_budget_warning(self, mock_db_connection):
        """Test budget vs actual shows warnings for over budget"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [('BUD001', 'Food', 50000.0, 55000.0, '2025-01-01', '2025-12-31')],  # Over budget
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.budget_vs_actual()

                output = fake_out.getvalue()
                assert 'OVER BUDGET' in output
                assert 'RECOMMENDATIONS' in output
                assert 'Review over-budget categories' in output

    def test_budget_vs_actual_no_budgets(self, mock_db_connection):
        """Test budget vs actual when no budgets exist"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [],  # No current budgets
            []  # No recent budgets either
        ]

        with mock.patch('university_system.modules.core.services.restaurant_misc.financials.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                financials.budget_vs_actual()

                output = fake_out.getvalue()
                assert 'No budgets found' in output
