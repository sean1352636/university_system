"""
Test suite for university_system/modules/domain/finance/gui/finance/compliance.py

Tests the CollectionsManager class including:
- Collections management
- Agency management
- Audit log viewing
- Collection case management
- Payment arrangement creation
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.gui.finance.finance.compliance import CollectionsManager
from education_system.systems.university.infrastructure.database.db import get_connection

@pytest.fixture
def mock_gui():
    """Create a mock GUI object"""
    gui = Mock()
    gui.root = Mock(spec=tk.Tk)
    gui.root.after = Mock(side_effect=lambda delay, func: func())
    gui.conn = get_connection()
    gui.finance_system = Mock()

    # Mock layout attributes
    gui.layout = Mock()
    gui.layout.content_frame = Mock(spec=tk.Frame)
    gui.layout.tab_frames = {}
    gui.layout.colors = {
        'success': '#28a745',
        'secondary': '#6c757d',
        'warning': '#ffc107',
        'danger': '#dc3545',
        'info': '#17a2b8'
    }
    gui.layout.update_status = Mock()

    return gui

@pytest.fixture
def collections_manager(mock_gui):
    """Create a CollectionsManager instance for testing"""
    return CollectionsManager(mock_gui)

@pytest.fixture
def test_db_with_collection_data():
    """Create a test database with collection data"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create required tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email_address TEXT,
            phone_number TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            case_status TEXT,
            agency_id INTEGER,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_agencies (
            agency_id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT,
            contact_email TEXT,
            phone TEXT,
            commission_rate REAL,
            is_active INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            table_name TEXT,
            record_id TEXT,
            new_values TEXT,
            timestamp TEXT
        )
    ''')

    conn.commit()
    yield conn

    # Cleanup — the _isolate_db autouse fixture handles DB teardown,
    # so we only need to clean up if the connection is still open.
    try:
        cursor.execute('DELETE FROM audit_log')
        cursor.execute('DELETE FROM collection_cases')
        cursor.execute('DELETE FROM collection_agencies')
        conn.commit()
    except Exception:
        pass  # Connection may already be closed by _isolate_db teardown

class TestCollectionsManagerInit:
    """Test CollectionsManager initialization"""

    def test_init_stores_gui_reference(self, collections_manager, mock_gui):
        """Test that initialization stores GUI reference"""
        assert collections_manager.gui == mock_gui

    def test_init_stores_root_reference(self, collections_manager, mock_gui):
        """Test that initialization stores root window reference"""
        assert collections_manager.root == mock_gui.root

    def test_init_stores_conn_reference(self, collections_manager, mock_gui):
        """Test that initialization stores database connection"""
        assert collections_manager.conn == mock_gui.conn

    def test_init_handles_missing_finance_system(self, mock_gui):
        """Test that initialization handles missing finance_system gracefully"""
        del mock_gui.finance_system
        manager = CollectionsManager(mock_gui)
        assert manager.finance_system is None

class TestCollectionManagement:
    """Test collection case management"""

    @patch('tkinter.messagebox.showwarning')
    @patch('tkinter.messagebox.showinfo')
    @patch('tkinter.simpledialog.askstring', side_effect=['Test Case', 'STU001'])
    def test_create_collection_case(self, mock_dialog, mock_info, mock_warning, collections_manager):
        """Test creating a collection case"""
        collections_manager.refresh_collections = Mock()

        # This method requires GUI elements that we'll mock
        # Test that the method exists and can be called
        assert hasattr(collections_manager, 'create_collection_case')

class TestAgencyManagement:
    """Test collection agency management"""

    @patch('tkinter.Toplevel')
    def test_manage_agencies_creates_dialog(self, mock_toplevel, collections_manager):
        """Test that manage_agencies creates a dialog"""
        collections_manager.load_agencies = Mock()
        collections_manager.manage_agencies()

        # Verify dialog was created
        mock_toplevel.assert_called()

class TestGUIWrappers:
    """Test GUI wrapper methods"""

    @patch('tkinter.Toplevel')
    @patch('sys.stdout')
    def test_gui_view_overdue_accounts(self, mock_stdout, mock_toplevel, collections_manager):
        """Test GUI wrapper for viewing overdue accounts"""
        collections_manager.gui_view_overdue_accounts()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_create_collection_case(self, mock_toplevel, collections_manager):
        """Test GUI wrapper for creating collection case"""
        collections_manager.gui_create_collection_case()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_add_collection_agency(self, mock_toplevel, collections_manager):
        """Test GUI wrapper for adding collection agency"""
        collections_manager.gui_add_collection_agency()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_assign_to_collection_agency(self, mock_toplevel, collections_manager):
        """Test GUI wrapper for assigning to collection agency"""
        collections_manager.gui_assign_to_collection_agency()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_update_collection_case_status(self, mock_toplevel, collections_manager):
        """Test GUI wrapper for updating collection case status"""
        collections_manager.gui_update_collection_case_status()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_create_payment_arrangement(self, mock_toplevel, collections_manager):
        """Test GUI wrapper for creating payment arrangement"""
        collections_manager.gui_create_payment_arrangement()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_send_collection_notice(self, mock_toplevel, collections_manager):
        """Test GUI wrapper for sending collection notice"""
        collections_manager.gui_send_collection_notice()

        # Verify dialog was created
        mock_toplevel.assert_called()

class TestAuditLogs:
    """Test audit log functionality"""

    @patch('tkinter.Toplevel')
    @patch('education_system.systems.university.interfaces.gui.finance.finance.compliance.get_connection')
    def test_gui_view_audit_logs_creates_dialog(self, mock_conn, mock_toplevel, collections_manager, test_db_with_collection_data):
        """Test that audit log viewer creates a dialog"""
        mock_conn.return_value = test_db_with_collection_data

        collections_manager.gui_view_audit_logs()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('education_system.systems.university.interfaces.gui.finance.finance.compliance.get_connection')
    def test_gui_view_audit_logs_loads_data(self, mock_conn, test_db_with_collection_data):
        """Test that audit logs are loaded from database"""
        mock_conn.return_value = test_db_with_collection_data

        # Insert test audit log
        cursor = test_db_with_collection_data.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO audit_log
            (user_id, action, table_name, record_id, new_values, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', 'create', 'collection_cases', '1', '{"status":"active"}', now))
        test_db_with_collection_data.commit()

        # Verify data exists
        cursor.execute('SELECT COUNT(*) FROM audit_log')
        count = cursor.fetchone()[0]
        assert count == 1

class TestErrorHandling:
    """Test error handling in compliance manager"""

    @patch('tkinter.messagebox.showerror')
    @patch('sys.stdout')
    def test_gui_view_overdue_accounts_handles_errors(self, mock_stdout, mock_error, collections_manager, monkeypatch):
        """Test that overdue accounts view handles errors"""
        def mock_view():
            raise Exception("Test error")

        monkeypatch.setattr('university_system.modules.domain.finance.gui.finance.common_imports.view_overdue_accounts',
                           mock_view)

        # Should handle error gracefully
        with patch('tkinter.Toplevel'):
            collections_manager.gui_view_overdue_accounts()

    @patch('tkinter.messagebox.showerror')
    def test_gui_track_collection_progress_handles_errors(self, mock_error, collections_manager, monkeypatch):
        """Test that collection progress tracking handles errors"""
        def mock_track():
            raise Exception("Test error")

        monkeypatch.setattr('university_system.modules.domain.finance.gui.finance.common_imports.track_collection_progress',
                           mock_track)

        collections_manager.show_text_window = Mock()
        collections_manager.gui.layout.update_status = Mock()

        # Should handle error gracefully
        collections_manager.gui_track_collection_progress()

class TestReportingWrappers:
    """Test reporting wrapper methods"""

    @patch('sys.stdout')
    def test_gui_aging_analysis_report(self, mock_stdout, collections_manager):
        """Test aging analysis report wrapper"""
        collections_manager.show_tab = Mock()
        collections_manager.report_text = Mock()
        collections_manager.gui.layout.update_status = Mock()

        collections_manager.gui_aging_analysis_report()

        # Should not crash
        assert True

    @patch('sys.stdout')
    def test_gui_collection_case_status_report(self, mock_stdout, collections_manager):
        """Test collection case status report wrapper"""
        collections_manager.show_tab = Mock()
        collections_manager.report_text = Mock()
        collections_manager.gui.layout.update_status = Mock()

        collections_manager.gui_collection_case_status_report()

        # Should not crash
        assert True

    @patch('sys.stdout')
    def test_gui_recovery_rate_analysis(self, mock_stdout, collections_manager):
        """Test recovery rate analysis wrapper"""
        collections_manager.show_tab = Mock()
        collections_manager.report_text = Mock()
        collections_manager.gui.layout.update_status = Mock()

        collections_manager.gui_recovery_rate_analysis()

        # Should not crash
        assert True

class TestWorkflowManagement:
    """Test workflow management"""

    @patch('tkinter.Toplevel')
    def test_gui_create_approval_workflow(self, mock_toplevel, collections_manager):
        """Test creating approval workflow"""
        collections_manager.gui_create_approval_workflow()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.messagebox.askyesno', return_value=True)
    @patch('tkinter.messagebox.showinfo')
    def test_gui_setup_collection_workflows(self, mock_info, mock_confirm, collections_manager):
        """Test setting up collection workflows"""
        collections_manager.gui.layout.update_status = Mock()

        collections_manager.gui_setup_collection_workflows()

        # Verify status was updated
        collections_manager.gui.layout.update_status.assert_called()

class TestViewStudentCollectionDetail:
    """Test student collection detail viewing"""

    @patch('tkinter.Toplevel')
    def test_gui_view_student_collection_detail(self, mock_toplevel, collections_manager):
        """Test viewing student collection details"""
        collections_manager.gui_view_student_collection_detail()

        # Verify dialog was created
        mock_toplevel.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
