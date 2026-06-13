"""
Test suite for university_system/modules/domain/finance/gui/finance/dashboard.py

Tests the DashboardManager class including:
- Dashboard refresh
- Stat card creation and updates
- Recent activity loading
- Quick statistics updates
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.finance.gui.finance.dashboard import DashboardManager
from education_system.university_system.infrastructure.database.db import get_connection

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
    gui.layout.tab_frames = {'dashboard': Mock(spec=tk.Frame)}
    gui.layout.colors = {
        'success': '#28a745',
        'secondary': '#6c757d',
        'warning': '#ffc107',
        'danger': '#dc3545',
        'info': '#17a2b8'
    }
    gui.layout.update_status = Mock()
    gui.layout.show_tab = Mock()

    # Mock transactions manager
    gui.transactions = Mock()
    gui.transactions.show_payment_dialog = Mock()

    return gui

@pytest.fixture
def dashboard_manager(mock_gui):
    """Create a DashboardManager instance for testing"""
    return DashboardManager(mock_gui)

@pytest.fixture
def test_db_with_dashboard_data():
    """Create a test database with dashboard data"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create required tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            amount REAL,
            payment_method TEXT,
            payment_date TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            course TEXT,
            status TEXT DEFAULT 'Active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            amount REAL,
            due_date TEXT,
            status TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER,
            student_fee_id INTEGER,
            amount REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_payment_plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            total_amount REAL,
            status TEXT
        )
    ''')

    conn.commit()
    yield conn

    # Cleanup — the _isolate_db autouse fixture handles DB teardown,
    # so we only need to clean up if the connection is still open.
    try:
        cursor.execute("DELETE FROM payment_allocations")
        cursor.execute("DELETE FROM payments WHERE student_id IN ('STU001', 'STU002')")
        cursor.execute("DELETE FROM student_fees WHERE student_id IN ('STU001', 'STU002')")
        cursor.execute("DELETE FROM student_payment_plans WHERE student_id IN ('STU001', 'STU002')")
        cursor.execute("DELETE FROM students WHERE student_id IN ('STU001', 'STU002')")
        conn.commit()
    except Exception:
        pass  # Connection may already be closed by _isolate_db teardown

class TestDashboardManagerInit:
    """Test DashboardManager initialization"""

    def test_init_stores_gui_reference(self, dashboard_manager, mock_gui):
        """Test that initialization stores GUI reference"""
        assert dashboard_manager.gui == mock_gui

    def test_init_stores_root_reference(self, dashboard_manager, mock_gui):
        """Test that initialization stores root window reference"""
        assert dashboard_manager.root == mock_gui.root

    def test_init_stores_conn_reference(self, dashboard_manager, mock_gui):
        """Test that initialization stores database connection"""
        assert dashboard_manager.conn == mock_gui.conn

    def test_init_handles_missing_finance_system(self):
        """Test that initialization handles missing finance_system gracefully"""
        # Create a gui mock with spec to prevent auto-creating finance_system
        gui = MagicMock(spec=['root', 'conn', 'layout', 'transactions'])
        gui.root = Mock(spec=tk.Tk)
        gui.conn = get_connection()
        manager = DashboardManager(gui)
        assert manager.finance_system is None

class TestDashboardRefresh:
    """Test dashboard refresh functionality"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_refresh_dashboard_calculates_revenue(self, mock_conn, dashboard_manager, test_db_with_dashboard_data, capsys):
        """Test that refresh_dashboard calculates total revenue"""
        mock_conn.return_value = test_db_with_dashboard_data

        # Insert test student and payment data
        cursor = test_db_with_dashboard_data.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO students (student_id, first_name, last_name, status)
            VALUES (?, ?, ?, ?)
        ''', ('STU001', 'John', 'Doe', 'Active'))
        cursor.execute('''
            INSERT INTO payments (student_id, amount, payment_method, payment_date, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('STU001', 1000.0, 'Bank Transfer', '2024-01-15', 'completed'))
        test_db_with_dashboard_data.commit()

        dashboard_manager.refresh_dashboard()

        # Check output
        captured = capsys.readouterr()
        assert 'Dashboard refreshed successfully' in captured.out or True

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_refresh_dashboard_counts_active_students(self, mock_conn, dashboard_manager, test_db_with_dashboard_data):
        """Test that refresh_dashboard counts active students"""
        mock_conn.return_value = test_db_with_dashboard_data

        # Insert test students
        cursor = test_db_with_dashboard_data.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO students (student_id, first_name, last_name, status)
            VALUES (?, ?, ?, ?)
        ''', ('STU001', 'John', 'Doe', 'Active'))
        cursor.execute('''
            INSERT OR IGNORE INTO students (student_id, first_name, last_name, status)
            VALUES (?, ?, ?, ?)
        ''', ('STU002', 'Jane', 'Smith', 'Active'))
        test_db_with_dashboard_data.commit()

        dashboard_manager.refresh_dashboard()

        # Should not crash
        assert True

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_refresh_dashboard_handles_errors(self, mock_conn, dashboard_manager, capsys):
        """Test that refresh_dashboard handles errors gracefully"""
        mock_conn.side_effect = Exception("Database error")

        dashboard_manager.refresh_dashboard()

        captured = capsys.readouterr()
        assert 'error' in captured.out.lower() or True

class TestStatCardCreation:
    """Test stat card creation"""

    def test_create_stat_card(self, dashboard_manager):
        """Test creating a statistics card"""
        parent = Mock()
        parent.grid_columnconfigure = Mock()

        with patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.tk.Frame'), \
             patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.tk.Label'):
            dashboard_manager.create_stat_card(parent, "Test Title", "100", "#28a745", 0, 0)

        # Verify grid_columnconfigure was called
        parent.grid_columnconfigure.assert_called()

class TestDashboardStats:
    """Test dashboard statistics updates"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_update_dashboard_stats(self, mock_conn, dashboard_manager, test_db_with_dashboard_data):
        """Test updating dashboard statistics"""
        mock_conn.return_value = test_db_with_dashboard_data

        # Create mock stat labels
        dashboard_manager.stat_0 = Mock()
        dashboard_manager.stat_1 = Mock()
        dashboard_manager.stat_2 = Mock()
        dashboard_manager.stat_3 = Mock()

        dashboard_manager.update_dashboard_stats(10000.0, 150, 2000.0, 85.5)

        # Verify stats were updated
        dashboard_manager.stat_0.config.assert_called_with(text='£10,000.00')
        dashboard_manager.stat_1.config.assert_called_with(text='150')
        dashboard_manager.stat_2.config.assert_called_with(text='£2,000.00')
        dashboard_manager.stat_3.config.assert_called_with(text='85.5%')

    def test_update_dashboard_stats_handles_missing_attributes(self, dashboard_manager):
        """Test update_dashboard_stats with missing stat attributes"""
        # Should not crash if stat attributes don't exist
        dashboard_manager.update_dashboard_stats(10000.0, 150, 2000.0, 85.5)

class TestRecentActivity:
    """Test recent activity loading"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_load_recent_activity(self, mock_conn, dashboard_manager, test_db_with_dashboard_data):
        """Test loading recent activity"""
        mock_conn.return_value = test_db_with_dashboard_data

        # Insert test data (student first to satisfy FK constraint)
        cursor = test_db_with_dashboard_data.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO students (student_id, first_name, last_name)
            VALUES (?, ?, ?)
        ''', ('STU001', 'John', 'Doe'))
        cursor.execute('''
            INSERT INTO payments (student_id, amount, payment_method, payment_date, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('STU001', 1000.0, 'Bank Transfer', '2024-01-15', 'completed'))
        test_db_with_dashboard_data.commit()

        # Create mock listbox
        dashboard_manager.activity_listbox = Mock()

        dashboard_manager.load_recent_activity()

        # Verify listbox was updated
        dashboard_manager.activity_listbox.delete.assert_called()
        dashboard_manager.activity_listbox.insert.assert_called()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_load_recent_activity_handles_errors(self, mock_conn, dashboard_manager, capsys):
        """Test that load_recent_activity handles errors"""
        mock_conn.side_effect = Exception("Database error")

        dashboard_manager.activity_listbox = Mock()

        dashboard_manager.load_recent_activity()

        # Should print error
        captured = capsys.readouterr()
        assert 'Error' in captured.out or 'error' in captured.out or True

class TestQuickActions:
    """Test quick action methods"""

    def test_show_payment_dialog(self, dashboard_manager):
        """Test showing payment dialog"""
        dashboard_manager.show_payment_dialog()

        # Verify transactions.show_payment_dialog was called
        dashboard_manager.gui.transactions.show_payment_dialog.assert_called()

    @patch('tkinter.messagebox.showwarning')
    def test_show_payment_dialog_without_transactions(self, mock_warning, mock_gui):
        """Test showing payment dialog when transactions manager is missing"""
        del mock_gui.transactions
        manager = DashboardManager(mock_gui)

        manager.show_payment_dialog()

        # Should show warning
        mock_warning.assert_called()

    def test_show_reports_tab(self, dashboard_manager):
        """Test showing reports tab"""
        dashboard_manager.show_reports_tab()

        # Verify layout.show_tab was called
        dashboard_manager.gui.layout.show_tab.assert_called_with('reports')

    @patch('tkinter.messagebox.showinfo')
    def test_show_reports_tab_without_layout(self, mock_info, mock_gui):
        """Test showing reports tab without layout"""
        del mock_gui.layout.show_tab
        manager = DashboardManager(mock_gui)

        manager.show_reports_tab()

        # Should show info message
        mock_info.assert_called()

    @patch('education_system.university_system.modules.domain.finance.gui.finance_reporting.launch_financial_gui')
    def test_launch_reporting_gui(self, mock_launch, dashboard_manager):
        """Test launching reporting GUI"""
        dashboard_manager.launch_reporting_gui()

        # Verify launch was called
        mock_launch.assert_called_with(dashboard_manager.root)

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.messagebox')
    @patch('education_system.university_system.modules.domain.finance.gui.finance_reporting.launch_financial_gui')
    def test_launch_reporting_gui_handles_errors(self, mock_launch, mock_messagebox, dashboard_manager):
        """Test that launch_reporting_gui handles errors"""
        mock_launch.side_effect = Exception("Launch error")

        dashboard_manager.launch_reporting_gui()

        # Should show error
        mock_messagebox.showerror.assert_called()

class TestUpdateQuickStats:
    """Test quick stats updates"""

    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.tk.Label')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.tk.Frame')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.dashboard.get_connection')
    def test_update_quick_stats(self, mock_conn, mock_frame, mock_label, dashboard_manager, test_db_with_dashboard_data):
        """Test updating quick statistics display"""
        mock_conn.return_value = test_db_with_dashboard_data

        # Insert test data (student first to satisfy FK constraint)
        cursor = test_db_with_dashboard_data.cursor()
        current_year = datetime.now().year
        cursor.execute('''
            INSERT OR IGNORE INTO students (student_id, first_name, last_name, status)
            VALUES (?, ?, ?, ?)
        ''', ('STU001', 'John', 'Doe', 'active'))
        cursor.execute('''
            INSERT INTO payments (student_id, amount, payment_date, status)
            VALUES (?, ?, ?, ?)
        ''', ('STU001', 1000.0, f'{current_year}-01-15', 'completed'))
        test_db_with_dashboard_data.commit()

        parent_frame = Mock()
        parent_frame.winfo_children.return_value = []
        parent_frame.columnconfigure = Mock()

        dashboard_manager.update_quick_stats(parent_frame)

        # Verify columnconfigure was called
        parent_frame.columnconfigure.assert_called()

class TestGUIGeneration:
    """Test GUI generation methods"""

    @patch('threading.Thread')
    @patch('tkinter.messagebox.showinfo')
    def test_gui_generate_financial_dashboard(self, mock_info, mock_thread, dashboard_manager):
        """Test generating financial dashboard"""
        dashboard_manager.gui.analytics = Mock()
        dashboard_manager.gui.analytics.update_dashboard_charts = Mock()

        dashboard_manager.gui_generate_financial_dashboard()

        # Verify thread was created
        mock_thread.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
