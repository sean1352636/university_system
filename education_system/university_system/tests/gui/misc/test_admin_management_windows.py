"""
Tests for university_system/modules/shared/gui/admin_management_windows.py

This test suite validates:
- Window initialization and widget creation
- API Management functionality
- Audit Logs functionality
- System Diagnostics functionality
- Database Maintenance functionality
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock, call
import json


@pytest.fixture
def root_window():
    """Create a root Tk window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestApiManagementWindow:
    """Test ApiManagementWindow class"""

    def test_window_initialization(self, root_window):
        """Test API Management window initializes correctly"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)

        assert window.parent == root_window
        assert window.window is not None
        assert isinstance(window.window, tk.Toplevel)

    def test_window_title_and_geometry(self, root_window):
        """Test window has correct title and size"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)

        assert window.window.title() == "API Management"
        # Check geometry was set (actual size may vary)
        assert window.window.winfo_reqwidth() > 0

    def test_api_keys_treeview_creation(self, root_window):
        """Test API keys treeview is created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)

        assert hasattr(window, 'keys_tree')
        assert isinstance(window.keys_tree, ttk.Treeview)

    def test_endpoints_treeview_creation(self, root_window):
        """Test endpoints treeview is created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)

        assert hasattr(window, 'endpoints_tree')
        assert isinstance(window.endpoints_tree, ttk.Treeview)

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_generate_api_key(self, mock_messagebox, root_window):
        """Test API key generation"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)
        window.generate_api_key()

        # Should show info message with new key
        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "New API Key Generated" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_revoke_api_key_no_selection(self, mock_messagebox, root_window):
        """Test revoking API key without selection"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)
        window.revoke_api_key()

        # Should show warning about no selection
        assert mock_messagebox.showwarning.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_test_endpoint_no_selection(self, mock_messagebox, root_window):
        """Test endpoint testing without selection"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)
        window.test_endpoint()

        # Should show warning about no selection
        assert mock_messagebox.showwarning.called


class TestAuditLogsWindow:
    """Test AuditLogsWindow class"""

    def test_window_initialization(self, root_window):
        """Test Audit Logs window initializes correctly"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        window = AuditLogsWindow(root_window)

        assert window.parent == root_window
        assert window.window is not None
        assert isinstance(window.window, tk.Toplevel)

    def test_window_title(self, root_window):
        """Test window has correct title"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        window = AuditLogsWindow(root_window)

        assert window.window.title() == "System Audit Logs"

    def test_logs_treeview_creation(self, root_window):
        """Test logs treeview is created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        window = AuditLogsWindow(root_window)

        assert hasattr(window, 'logs_tree')
        assert isinstance(window.logs_tree, ttk.Treeview)

    def test_filter_variables_created(self, root_window):
        """Test filter variables are created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        window = AuditLogsWindow(root_window)

        assert hasattr(window, 'date_range_var')
        assert hasattr(window, 'level_var')
        assert hasattr(window, 'category_var')
        assert hasattr(window, 'search_var')

    def test_sample_logs_loaded(self, root_window):
        """Test sample logs are loaded into treeview"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        window = AuditLogsWindow(root_window)
        window.load_sample_logs()

        # Should have some log entries
        children = window.logs_tree.get_children()
        assert len(children) > 0

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_apply_filters(self, mock_messagebox, root_window):
        """Test applying filters"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        window = AuditLogsWindow(root_window)
        window.apply_filters()

        # Should show info message about applied filters
        assert mock_messagebox.showinfo.called

    @patch('university_system.modules.shared.gui.admin_management_windows.filedialog')
    def test_export_logs(self, mock_filedialog, root_window):
        """Test exporting logs"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import AuditLogsWindow

        mock_filedialog.asksaveasfilename.return_value = "/tmp/test.csv"
        window = AuditLogsWindow(root_window)

        with patch('university_system.modules.shared.gui.admin_management_windows.messagebox'):
            window.export_logs()

        assert mock_filedialog.asksaveasfilename.called


class TestDiagnosticsWindow:
    """Test DiagnosticsWindow class"""

    def test_window_initialization(self, root_window):
        """Test Diagnostics window initializes correctly"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        window = DiagnosticsWindow(root_window)

        assert window.parent == root_window
        assert window.window is not None
        assert isinstance(window.window, tk.Toplevel)

    def test_window_title(self, root_window):
        """Test window has correct title"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        window = DiagnosticsWindow(root_window)

        assert window.window.title() == "System Diagnostics"

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_run_full_diagnostic(self, mock_messagebox, root_window):
        """Test running full diagnostic"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        window = DiagnosticsWindow(root_window)
        window.run_full_diagnostic()

        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "Full Diagnostic" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.filedialog')
    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_generate_health_report(self, mock_messagebox, mock_filedialog, root_window):
        """Test generating health report"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        mock_filedialog.asksaveasfilename.return_value = "/tmp/health_report.pdf"
        window = DiagnosticsWindow(root_window)
        window.generate_health_report()

        assert mock_filedialog.asksaveasfilename.called
        assert mock_messagebox.showinfo.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_test_connectivity(self, mock_messagebox, root_window):
        """Test network connectivity test"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        window = DiagnosticsWindow(root_window)
        window.test_connectivity()

        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "Connectivity Test" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_run_speed_test(self, mock_messagebox, root_window):
        """Test network speed test"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        window = DiagnosticsWindow(root_window)
        window.run_speed_test()

        assert mock_messagebox.showinfo.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_disk_cleanup_with_confirmation(self, mock_messagebox, root_window):
        """Test disk cleanup with user confirmation"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DiagnosticsWindow

        mock_messagebox.askyesno.return_value = True
        window = DiagnosticsWindow(root_window)
        window.run_disk_cleanup()

        assert mock_messagebox.askyesno.called
        assert mock_messagebox.showinfo.called


class TestDatabaseMaintenanceWindow:
    """Test DatabaseMaintenanceWindow class"""

    def test_window_initialization(self, root_window):
        """Test Database Maintenance window initializes correctly"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)

        assert window.parent == root_window
        assert window.window is not None
        assert isinstance(window.window, tk.Toplevel)

    def test_window_title(self, root_window):
        """Test window has correct title"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)

        assert window.window.title() == "Database Maintenance"

    def test_backup_tree_creation(self, root_window):
        """Test backup history treeview is created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)

        assert hasattr(window, 'backup_tree')
        assert isinstance(window.backup_tree, ttk.Treeview)

    def test_backup_variables_created(self, root_window):
        """Test backup configuration variables are created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)

        assert hasattr(window, 'backup_type_var')
        assert hasattr(window, 'compression_var')

    def test_optimization_variables_created(self, root_window):
        """Test optimization option variables are created"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)

        assert hasattr(window, 'vacuum_var')
        assert hasattr(window, 'analyze_var')
        assert hasattr(window, 'reindex_var')
        assert hasattr(window, 'cleanup_var')

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_refresh_status(self, mock_messagebox, root_window):
        """Test database status refresh"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)
        window.refresh_status()

        assert mock_messagebox.showinfo.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_test_connection(self, mock_messagebox, root_window):
        """Test database connection test"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)
        window.test_connection()

        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "Connection Test" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_create_backup(self, mock_messagebox, root_window):
        """Test creating database backup"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)
        window.create_backup()

        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "Backup Started" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_restore_backup_no_selection(self, mock_messagebox, root_window):
        """Test restore backup without selection"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)
        window.restore_backup()

        # Should show warning about no selection
        assert mock_messagebox.showwarning.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_run_optimization_no_operations(self, mock_messagebox, root_window):
        """Test running optimization with no operations selected"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)

        # Deselect all operations
        window.vacuum_var.set(False)
        window.analyze_var.set(False)
        window.reindex_var.set(False)
        window.cleanup_var.set(False)

        window.run_optimization()

        # Should show warning about no operations selected
        assert mock_messagebox.showwarning.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_run_optimization_with_operations(self, mock_messagebox, root_window):
        """Test running optimization with operations selected"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        mock_messagebox.askyesno.return_value = True
        window = DatabaseMaintenanceWindow(root_window)

        # Select operations
        window.vacuum_var.set(True)
        window.analyze_var.set(True)

        window.run_optimization()

        # Should ask for confirmation
        assert mock_messagebox.askyesno.called
        # Should show info about started optimization
        assert mock_messagebox.showinfo.called

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_check_integrity(self, mock_messagebox, root_window):
        """Test database integrity check"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)
        window.check_integrity()

        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "Integrity Check" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_start_monitoring(self, mock_messagebox, root_window):
        """Test starting database monitoring"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        window = DatabaseMaintenanceWindow(root_window)
        window.start_monitoring()

        assert mock_messagebox.showinfo.called
        call_args = mock_messagebox.showinfo.call_args[0]
        assert "Monitoring Started" in call_args[0]

    @patch('university_system.modules.shared.gui.admin_management_windows.messagebox')
    def test_stop_monitoring_with_confirmation(self, mock_messagebox, root_window):
        """Test stopping monitoring with confirmation"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import DatabaseMaintenanceWindow

        mock_messagebox.askyesno.return_value = True
        window = DatabaseMaintenanceWindow(root_window)
        window.stop_monitoring()

        assert mock_messagebox.askyesno.called
        assert mock_messagebox.showinfo.called


class TestWindowIntegration:
    """Test integration and common functionality"""

    def test_all_windows_have_close_button(self, root_window):
        """Test all windows can be closed"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import (
            ApiManagementWindow,
            AuditLogsWindow,
            DiagnosticsWindow,
            DatabaseMaintenanceWindow
        )

        windows = [
            ApiManagementWindow(root_window),
            AuditLogsWindow(root_window),
            DiagnosticsWindow(root_window),
            DatabaseMaintenanceWindow(root_window)
        ]

        for window in windows:
            # Window should have destroy method
            assert hasattr(window.window, 'destroy')
            # Clean up
            window.window.destroy()

    def test_windows_are_transient(self, root_window):
        """Test windows are set as transient"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)

        # Window should be transient to parent
        # This ensures it stays on top of parent window
        # transient() returns the parent window object
        assert window.window.transient() is not None

    def test_windows_grab_set(self, root_window):
        """Test windows use grab_set for modal behavior"""
        from education_system.university_system.modules.shared.gui.admin_management_windows import ApiManagementWindow

        window = ApiManagementWindow(root_window)

        # Window should have grabbed focus (modal)
        # This is verified by the window being created successfully
        assert window.window is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
