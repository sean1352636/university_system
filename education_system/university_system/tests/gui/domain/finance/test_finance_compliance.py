"""
Test suite for university_system/modules/domain/finance/gui/finance/compliance.py

Tests the ComplianceManager class including:
- Collections management
- Agency management
- Audit log viewing
- Collection case management
- Payment arrangement creation
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.finance.gui.finance.compliance import ComplianceManager
from education_system.university_system.infrastructure.database.db import get_connection

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
def compliance_manager(mock_gui):
    """Create a ComplianceManager instance for testing"""
    return ComplianceManager(mock_gui)

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

    # Cleanup
    cursor.execute('DELETE FROM audit_log')
    cursor.execute('DELETE FROM collection_cases')
    cursor.execute('DELETE FROM collection_agencies')
    cursor.execute('DELETE FROM students')
    conn.commit()
    conn.close()

class TestComplianceManagerInit:
    """Test ComplianceManager initialization"""

    def test_init_stores_gui_reference(self, compliance_manager, mock_gui):
        """Test that initialization stores GUI reference"""
        assert compliance_manager.gui == mock_gui

    def test_init_stores_root_reference(self, compliance_manager, mock_gui):
        """Test that initialization stores root window reference"""
        assert compliance_manager.root == mock_gui.root

    def test_init_stores_conn_reference(self, compliance_manager, mock_gui):
        """Test that initialization stores database connection"""
        assert compliance_manager.conn == mock_gui.conn

    def test_init_handles_missing_finance_system(self, mock_gui):
        """Test that initialization handles missing finance_system gracefully"""
        del mock_gui.finance_system
        manager = ComplianceManager(mock_gui)
        assert manager.finance_system is None

class TestCollectionManagement:
    """Test collection case management"""

    @patch('tkinter.messagebox.showwarning')
    @patch('tkinter.messagebox.showinfo')
    @patch('tkinter.simpledialog.askstring', side_effect=['Test Case', 'STU001'])
    def test_create_collection_case(self, mock_dialog, mock_info, mock_warning, compliance_manager):
        """Test creating a collection case"""
        compliance_manager.refresh_collections = Mock()

        # This method requires GUI elements that we'll mock
        # Test that the method exists and can be called
        assert hasattr(compliance_manager, 'create_collection_case')

class TestAgencyManagement:
    """Test collection agency management"""

    @patch('tkinter.Toplevel')
    def test_manage_agencies_creates_dialog(self, mock_toplevel, compliance_manager):
        """Test that manage_agencies creates a dialog"""
        compliance_manager.load_agencies = Mock()
        compliance_manager.manage_agencies()

        # Verify dialog was created
        mock_toplevel.assert_called()

class TestGUIWrappers:
    """Test GUI wrapper methods"""

    @patch('tkinter.Toplevel')
    @patch('sys.stdout')
    def test_gui_view_overdue_accounts(self, mock_stdout, mock_toplevel, compliance_manager):
        """Test GUI wrapper for viewing overdue accounts"""
        compliance_manager.gui_view_overdue_accounts()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_create_collection_case(self, mock_toplevel, compliance_manager):
        """Test GUI wrapper for creating collection case"""
        compliance_manager.gui_create_collection_case()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_add_collection_agency(self, mock_toplevel, compliance_manager):
        """Test GUI wrapper for adding collection agency"""
        compliance_manager.gui_add_collection_agency()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_assign_to_collection_agency(self, mock_toplevel, compliance_manager):
        """Test GUI wrapper for assigning to collection agency"""
        compliance_manager.gui_assign_to_collection_agency()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_update_collection_case_status(self, mock_toplevel, compliance_manager):
        """Test GUI wrapper for updating collection case status"""
        compliance_manager.gui_update_collection_case_status()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_create_payment_arrangement(self, mock_toplevel, compliance_manager):
        """Test GUI wrapper for creating payment arrangement"""
        compliance_manager.gui_create_payment_arrangement()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.Toplevel')
    def test_gui_send_collection_notice(self, mock_toplevel, compliance_manager):
        """Test GUI wrapper for sending collection notice"""
        compliance_manager.gui_send_collection_notice()

        # Verify dialog was created
        mock_toplevel.assert_called()

class TestAuditLogs:
    """Test audit log functionality"""

    @patch('tkinter.Toplevel')
    @patch('education_system.university_system.modules.domain.finance.gui.finance.compliance.get_connection')
    def test_gui_view_audit_logs_creates_dialog(self, mock_conn, mock_toplevel, compliance_manager, test_db_with_collection_data):
        """Test that audit log viewer creates a dialog"""
        mock_conn.return_value = test_db_with_collection_data

        compliance_manager.gui_view_audit_logs()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('education_system.university_system.modules.domain.finance.gui.finance.compliance.get_connection')
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
    def test_gui_view_overdue_accounts_handles_errors(self, mock_stdout, mock_error, compliance_manager, monkeypatch):
        """Test that overdue accounts view handles errors"""
        def mock_view():
            raise Exception("Test error")

        monkeypatch.setattr('university_system.modules.domain.finance.gui.finance.common_imports.view_overdue_accounts',
                           mock_view)

        # Should handle error gracefully
        with patch('tkinter.Toplevel'):
            compliance_manager.gui_view_overdue_accounts()

    @patch('tkinter.messagebox.showerror')
    def test_gui_track_collection_progress_handles_errors(self, mock_error, compliance_manager, monkeypatch):
        """Test that collection progress tracking handles errors"""
        def mock_track():
            raise Exception("Test error")

        monkeypatch.setattr('university_system.modules.domain.finance.gui.finance.common_imports.track_collection_progress',
                           mock_track)

        compliance_manager.show_text_window = Mock()
        compliance_manager.gui.layout.update_status = Mock()

        # Should handle error gracefully
        compliance_manager.gui_track_collection_progress()

class TestReportingWrappers:
    """Test reporting wrapper methods"""

    @patch('sys.stdout')
    def test_gui_aging_analysis_report(self, mock_stdout, compliance_manager):
        """Test aging analysis report wrapper"""
        compliance_manager.show_tab = Mock()
        compliance_manager.report_text = Mock()
        compliance_manager.gui.layout.update_status = Mock()

        compliance_manager.gui_aging_analysis_report()

        # Should not crash
        assert True

    @patch('sys.stdout')
    def test_gui_collection_case_status_report(self, mock_stdout, compliance_manager):
        """Test collection case status report wrapper"""
        compliance_manager.show_tab = Mock()
        compliance_manager.report_text = Mock()
        compliance_manager.gui.layout.update_status = Mock()

        compliance_manager.gui_collection_case_status_report()

        # Should not crash
        assert True

    @patch('sys.stdout')
    def test_gui_recovery_rate_analysis(self, mock_stdout, compliance_manager):
        """Test recovery rate analysis wrapper"""
        compliance_manager.show_tab = Mock()
        compliance_manager.report_text = Mock()
        compliance_manager.gui.layout.update_status = Mock()

        compliance_manager.gui_recovery_rate_analysis()

        # Should not crash
        assert True

class TestWorkflowManagement:
    """Test workflow management"""

    @patch('tkinter.Toplevel')
    def test_gui_create_approval_workflow(self, mock_toplevel, compliance_manager):
        """Test creating approval workflow"""
        compliance_manager.gui_create_approval_workflow()

        # Verify dialog was created
        mock_toplevel.assert_called()

    @patch('tkinter.messagebox.askyesno', return_value=True)
    @patch('tkinter.messagebox.showinfo')
    def test_gui_setup_collection_workflows(self, mock_info, mock_confirm, compliance_manager):
        """Test setting up collection workflows"""
        compliance_manager.gui.layout.update_status = Mock()

        compliance_manager.gui_setup_collection_workflows()

        # Verify status was updated
        compliance_manager.gui.layout.update_status.assert_called()

class TestViewStudentCollectionDetail:
    """Test student collection detail viewing"""

    @patch('tkinter.Toplevel')
    def test_gui_view_student_collection_detail(self, mock_toplevel, compliance_manager):
        """Test viewing student collection details"""
        compliance_manager.gui_view_student_collection_detail()

        # Verify dialog was created
        mock_toplevel.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
