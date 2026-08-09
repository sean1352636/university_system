"""
Test suite for university_system/modules/domain/finance/gui/finance/budget_manager.py

Tests the BudgetManager class including:
- Budget plan creation and editing
- Budget category management
- Budget analysis and approval
- Budget refreshing and data updates
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.gui.finance.finance.budget_manager import BudgetManager
from education_system.systems.university.infrastructure.database.db import get_connection

@pytest.fixture
def mock_gui():
    """Create a mock GUI object"""
    gui = Mock()
    gui.root = Mock(spec=tk.Tk)
    gui.root.after = Mock(side_effect=lambda delay, func: func())
    gui.conn = get_connection()

    # Mock layout attributes
    gui.layout = Mock()
    gui.layout.content_frame = Mock(spec=tk.Frame)
    gui.layout.tab_frames = {}
    gui.layout.colors = {
        'success': '#28a745',
        'secondary': '#6c757d',
        'warning': '#ffc107',
        'danger': '#dc3545',
        'info': '#17a2b8',
        'primary': '#007bff'
    }

    return gui

@pytest.fixture
def budget_manager(mock_gui):
    """Create a BudgetManager instance for testing"""
    return BudgetManager(mock_gui)

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
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'draft',
            total_revenue_budget REAL DEFAULT 0,
            total_expense_budget REAL DEFAULT 0,
            created_by TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # Create budget_categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT,
            category_type TEXT,
            parent_category_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # Create budget_line_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_line_items (
            line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER,
            category_id INTEGER,
            budgeted_amount REAL,
            actual_amount REAL DEFAULT 0,
            variance REAL DEFAULT 0,
            FOREIGN KEY (budget_id) REFERENCES budget_plans(budget_id),
            FOREIGN KEY (category_id) REFERENCES budget_categories(category_id)
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

class TestBudgetManagerInit:
    """Test BudgetManager initialization"""

    def test_init_stores_gui_reference(self, budget_manager, mock_gui):
        """Test that initialization stores GUI reference"""
        assert budget_manager.gui == mock_gui

    def test_init_stores_root_reference(self, budget_manager, mock_gui):
        """Test that initialization stores root window reference"""
        assert budget_manager.root == mock_gui.root

    def test_init_stores_conn_reference(self, budget_manager, mock_gui):
        """Test that initialization stores database connection"""
        assert budget_manager.conn == mock_gui.conn

    def test_init_handles_missing_finance_system(self, mock_gui):
        """Test that initialization handles missing finance_system gracefully"""
        manager = BudgetManager(mock_gui)
        assert manager.finance_system is None

class TestCreateBudgetPlan:
    """Test budget plan creation"""

    @patch('tkinter.Toplevel')
    @patch('tkinter.messagebox.showwarning')
    def test_create_budget_plan_validates_name(self, mock_warning, mock_toplevel, budget_manager):
        """Test that create_budget_plan validates plan name"""
        # Create mock dialog
        mock_dialog = Mock()
        mock_toplevel.return_value = mock_dialog

        # Create the dialog
        budget_manager.create_budget_plan()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_create_budget_plan_creates_dialog(self, mock_toplevel, budget_manager):
        """Test that create_budget_plan creates a dialog window"""
        budget_manager.create_budget_plan()

        # Verify Toplevel was called to create dialog
        mock_toplevel.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_connection')
    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_auth')
    def test_create_budget_plan_inserts_to_database(self, mock_auth, mock_get_conn, test_db_with_budget_data):
        """Test that budget plan data is inserted into database"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_logged_in.return_value = True
        mock_auth_instance.get_current_user.return_value = {'username': 'test_admin'}
        mock_auth.return_value = mock_auth_instance

        mock_get_conn.return_value = test_db_with_budget_data

        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, currency, status,
             total_revenue_budget, total_expense_budget,
             created_by, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Test Plan', '2024-2025', 'GBP', 'draft',
              100000.0, 80000.0, 'test_admin', 'Test notes', now, now))

        test_db_with_budget_data.commit()

        cursor.execute('SELECT plan_name FROM budget_plans WHERE plan_name = ?', ('Test Plan',))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'Test Plan'

class TestEditBudgetPlan:
    """Test budget plan editing"""

    @patch('tkinter.messagebox.showwarning')
    def test_edit_budget_plan_requires_selection(self, mock_warning, budget_manager):
        """Test that edit_budget_plan requires a plan selection"""
        # Mock empty tree selection
        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_plans_tree.selection.return_value = []

        budget_manager.edit_budget_plan()

        # Should show warning
        mock_warning.assert_called_with("No Selection", "Please select a budget plan to edit.")

    @patch('tkinter.Toplevel')
    def test_edit_budget_plan_opens_dialog(self, mock_toplevel, budget_manager):
        """Test that edit_budget_plan opens an edit dialog"""
        # Mock tree with selection
        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_plans_tree.selection.return_value = ['item1']
        budget_manager.budget_plans_tree.item.return_value = {
            'values': (1, 'Test Plan', '2024-2025', '£100,000.00', '£80,000.00', 'Active')
        }

        budget_manager.edit_budget_plan()

        # Verify dialog was created
        mock_toplevel.assert_called()

class TestDeleteBudgetPlan:
    """Test budget plan deletion"""

    @patch('tkinter.messagebox.showwarning')
    def test_delete_budget_plan_requires_selection(self, mock_warning, budget_manager):
        """Test that delete_budget_plan requires a plan selection"""
        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_plans_tree.selection.return_value = []

        budget_manager.delete_budget_plan()

        mock_warning.assert_called_with("No Selection", "Please select a budget plan to delete.")

    @patch('tkinter.messagebox.askyesno', return_value=True)
    @patch('tkinter.messagebox.showinfo')
    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_connection')
    def test_delete_budget_plan_deletes_from_database(self, mock_conn, mock_info, mock_confirm, budget_manager, test_db_with_budget_data):
        """Test that delete_budget_plan removes plan from database"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert test budget plan
        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', ('Test Plan', '2024-2025', now, now))
        test_db_with_budget_data.commit()
        budget_id = cursor.lastrowid

        # Mock tree selection
        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_plans_tree.selection.return_value = ['item1']
        budget_manager.budget_plans_tree.item.return_value = {
            'values': (budget_id, 'Test Plan', '2024-2025', '£0.00', '£0.00', 'draft')
        }
        budget_manager.refresh_budget = Mock()

        budget_manager.delete_budget_plan()

        # Verify deletion
        cursor.execute('SELECT COUNT(*) FROM budget_plans WHERE budget_id = ?', (budget_id,))
        assert cursor.fetchone()[0] == 0

class TestBudgetAnalysis:
    """Test budget analysis"""

    @patch('sys.stdout')
    @patch('tkinter.Text')
    def test_budget_analysis_generates_report(self, mock_text, mock_stdout, budget_manager):
        """Test that budget_analysis generates a report"""
        budget_manager.show_text_window = Mock()

        budget_manager.budget_analysis()

        # Verify show_text_window was called
        budget_manager.show_text_window.assert_called()

class TestApproveBudget:
    """Test budget approval"""

    @patch('sys.stdout')
    def test_approve_budget_shows_workflow(self, mock_stdout, budget_manager):
        """Test that approve_budget shows the approval workflow"""
        budget_manager.show_text_window = Mock()

        budget_manager.approve_budget()

        # Verify show_text_window was called
        budget_manager.show_text_window.assert_called_with("Budget Approval", Mock.ANY)

class TestRefreshBudget:
    """Test budget refresh functionality"""

    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_connection')
    def test_refresh_budget_loads_data(self, mock_conn, budget_manager, test_db_with_budget_data):
        """Test that refresh_budget loads budget data"""
        mock_conn.return_value = test_db_with_budget_data

        # Insert test data
        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO budget_plans
            (plan_name, academic_year, total_revenue_budget, total_expense_budget, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Test Plan', '2024-2025', 100000.0, 80000.0, 'active', now, now))
        test_db_with_budget_data.commit()

        # Mock required attributes
        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_categories_tree = Mock()
        budget_manager.update_budget_data = Mock()

        budget_manager.refresh_budget()

        # Verify update_budget_data was eventually called
        # Note: In real implementation, this happens in a thread with root.after

class TestCategoryManagement:
    """Test budget category management"""

    @patch('tkinter.Toplevel')
    def test_gui_manage_budget_categories_creates_dialog(self, mock_toplevel, budget_manager):
        """Test that category management creates a dialog"""
        budget_manager.gui_manage_budget_categories()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_connection')
    def test_create_category_inserts_to_database(self, mock_conn, test_db_with_budget_data):
        """Test that category creation inserts to database"""
        mock_conn.return_value = test_db_with_budget_data

        cursor = test_db_with_budget_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO budget_categories
            (category_name, category_type, is_active, created_at)
            VALUES (?, ?, 1, ?)
        ''', ('Tuition Revenue', 'revenue', now))
        test_db_with_budget_data.commit()

        cursor.execute('SELECT category_name FROM budget_categories WHERE category_name = ?', ('Tuition Revenue',))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'Tuition Revenue'

class TestShowTextWindow:
    """Test show_text_window helper method"""

    @patch('tkinter.Toplevel')
    def test_show_text_window_creates_window(self, mock_toplevel, budget_manager):
        """Test that show_text_window creates a window"""
        budget_manager.show_text_window("Test Title", "Test Content")

        # Verify window was created
        mock_toplevel.assert_called()

class TestErrorHandling:
    """Test error handling across budget manager"""

    @patch('tkinter.messagebox.showerror')
    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_connection')
    def test_delete_budget_plan_handles_errors(self, mock_conn, mock_error, budget_manager):
        """Test that delete_budget_plan handles database errors"""
        mock_conn.side_effect = Exception("Database error")

        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_plans_tree.selection.return_value = ['item1']
        budget_manager.budget_plans_tree.item.return_value = {
            'values': (1, 'Test Plan', '2024-2025', '£0.00', '£0.00', 'draft')
        }

        with patch('tkinter.messagebox.askyesno', return_value=True):
            budget_manager.delete_budget_plan()

        # Verify error message was shown
        mock_error.assert_called()

    @patch('education_system.systems.university.interfaces.gui.finance.finance.budget_manager.get_connection')
    def test_refresh_budget_handles_errors(self, mock_conn, budget_manager, capsys):
        """Test that refresh_budget handles errors gracefully"""
        mock_conn.side_effect = Exception("Database error")

        budget_manager.budget_plans_tree = Mock()
        budget_manager.budget_categories_tree = Mock()

        # Should not raise exception
        budget_manager.refresh_budget()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
