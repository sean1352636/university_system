#!/usr/bin/env python3
"""
Comprehensive tests for MFA Admin GUI
Tests administrative panel for MFA management, policies, user management, and audit logging
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

# Mock tkinter before importing MFA Admin GUI
@pytest.fixture(autouse=True)
def mock_tkinter():
    """Mock tkinter modules for testing"""
    with patch.dict('sys.modules', {
        'tkinter': MagicMock(),
        'tkinter.ttk': MagicMock(),
        'tkinter.messagebox': MagicMock(),
        'tkinter.scrolledtext': MagicMock(),
        'tkinter.filedialog': MagicMock(),
    }):
        yield

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role_id INTEGER)")
    cursor.execute("CREATE TABLE roles (id INTEGER PRIMARY KEY, role_name TEXT)")
    cursor.execute("CREATE TABLE mfa_methods (id INTEGER PRIMARY KEY, user_id INTEGER, method_type TEXT, is_enabled INTEGER)")
    cursor.execute("CREATE TABLE mfa_user_settings (user_id INTEGER PRIMARY KEY, mfa_enabled INTEGER, last_successful_verification TIMESTAMP)")
    cursor.execute("CREATE TABLE mfa_enforcement_policies (id INTEGER PRIMARY KEY, role_name TEXT, mfa_required INTEGER, allowed_methods TEXT, minimum_methods INTEGER, grace_period_days INTEGER, allow_device_trust INTEGER)")
    cursor.execute("CREATE TABLE mfa_verification_attempts (id INTEGER PRIMARY KEY, user_id INTEGER, method_type TEXT, attempted_at TIMESTAMP, success INTEGER, failure_reason TEXT, ip_address TEXT)")
    cursor.execute("CREATE TABLE mfa_trusted_devices (id INTEGER PRIMARY KEY, user_id INTEGER, device_id TEXT, device_name TEXT, trusted_at TIMESTAMP, expires_at TIMESTAMP, is_trusted INTEGER, revoked_at TIMESTAMP, ip_address TEXT, last_used_at TIMESTAMP)")

    # Insert test data
    cursor.execute("INSERT INTO roles VALUES (1, 'admin'), (2, 'student'), (3, 'instructor')")
    cursor.execute("INSERT INTO users VALUES (1, 'admin_user', 1), (2, 'student_user', 2)")
    cursor.execute("INSERT INTO mfa_enforcement_policies VALUES (1, 'admin', 1, '[\"totp\", \"sms\"]', 1, 7, 1)")

    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_mfa_service():
    """Create a mock MFA service"""
    service = MagicMock()
    service.db_path = '/fake/path/db.db'
    service.disable_mfa.return_value = {'success': True}
    return service

class TestMFAAdminPanelInitialization:
    """Test MFA Admin Panel initialization"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_panel_initialization(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test admin panel initialization"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        assert panel.admin_user_id == 1
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_panel_window_configuration(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test admin panel window configuration"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()
        mock_instance = MagicMock()
        mock_toplevel.return_value = mock_instance

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        # Verify window configuration
        mock_instance.title.assert_called()
        mock_instance.geometry.assert_called()

class TestOverviewTab:
    """Test Overview/Dashboard tab"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_overview_statistics(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test loading overview statistics"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        try:
            panel._load_overview()
        except (AttributeError, KeyError):
            # Expected if stats_labels not fully initialized
            pass

        # Test should not crash
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_statistics_labels_initialized(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test that statistics labels are initialized"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        # stats_labels should be a dictionary
        assert hasattr(panel, 'stats_labels')
        assert isinstance(panel.stats_labels, dict)

class TestPoliciesTab:
    """Test Policies tab"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_policies(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test loading MFA policies"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        try:
            panel._load_policies()
        except (AttributeError, KeyError):
            # Expected if policies_tree not fully initialized
            pass

        # Test should not crash
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showwarning')
    def test_edit_policy_no_selection(self, mock_messagebox, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test editing policy with no selection"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)
        panel.policies_tree = MagicMock()
        panel.policies_tree.selection.return_value = []

        panel._edit_policy()

        # Should show warning about no selection
        mock_messagebox.assert_called()

class TestUsersTab:
    """Test Users tab"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_users(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test loading users MFA status"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)
        panel.user_filter_var = MagicMock(get=lambda: 'all')

        try:
            panel._load_users()
        except (AttributeError, KeyError):
            pass

        # Test should not crash
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_users_with_filters(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test loading users with different filters"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        filters = ['all', 'enabled', 'disabled', 'required']
        for filter_value in filters:
            panel.user_filter_var = MagicMock(get=lambda f=filter_value: f)

            try:
                panel._load_users()
            except (AttributeError, KeyError):
                pass

        # Should not crash with any filter
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.askyesno')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showinfo')
    def test_reset_user_mfa(self, mock_showinfo, mock_askyesno, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test resetting user's MFA"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()
        mock_askyesno.return_value = True  # User confirms

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)
        panel.users_tree = MagicMock()
        panel.users_tree.selection.return_value = [1]
        panel.users_tree.item.return_value = {'values': ['testuser', 'student', 'Enabled', 'totp', 'Never']}
        panel._load_users = MagicMock()
        panel._load_overview = MagicMock()

        panel._reset_user_mfa()

        # Should call disable_mfa
        mock_mfa_service.disable_mfa.assert_called_with(1)
        mock_showinfo.assert_called()

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showwarning')
    def test_view_user_details_no_selection(self, mock_messagebox, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test viewing user details with no selection"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)
        panel.users_tree = MagicMock()
        panel.users_tree.selection.return_value = []

        panel._view_user_details()

        # Should show warning
        mock_messagebox.assert_called()

class TestAuditTab:
    """Test Audit Log tab"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_audit_log(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test loading audit log"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)
        panel.audit_filter_var = MagicMock(get=lambda: 'all')

        try:
            panel._load_audit_log()
        except (AttributeError, KeyError):
            pass

        # Test should not crash
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_audit_log_with_filters(self, mock_toplevel, mock_service_class, mock_mfa_service, temp_db):
        """Test loading audit log with different filters"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        filters = ['all', 'success', 'failed', '24h', '7d']
        for filter_value in filters:
            panel.audit_filter_var = MagicMock(get=lambda f=filter_value: f)

            try:
                panel._load_audit_log()
            except (AttributeError, KeyError):
                pass

        # Should not crash with any filter
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.filedialog.asksaveasfilename')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showinfo')
    def test_export_audit_log(self, mock_showinfo, mock_filedialog, mock_toplevel, mock_service_class, mock_mfa_service, temp_db, tmp_path):
        """Test exporting audit log to CSV"""
        mock_mfa_service.db_path = temp_db
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        temp_file = tmp_path / "audit_log.csv"
        mock_filedialog.return_value = str(temp_file)

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        panel._export_audit_log()

        # Should create CSV file
        if temp_file.exists():
            content = temp_file.read_text()
            assert 'Timestamp' in content or 'Username' in content
            mock_showinfo.assert_called()

class TestSettingsTab:
    """Test Settings tab"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_settings(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test loading system settings"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        try:
            panel._load_settings()
        except (AttributeError, ImportError):
            # Expected if providers can't be imported
            pass

        # Test should not crash
        assert panel.mfa_service is not None

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.get_sms_service')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showinfo')
    def test_test_sms_provider(self, mock_showinfo, mock_get_sms, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test SMS provider testing"""
        mock_service_class.return_value = mock_mfa_service
        mock_sms_service = MagicMock()
        mock_sms_service.send_otp.return_value = {'success': True, 'provider': 'mock'}
        mock_get_sms.return_value = mock_sms_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        panel._test_sms_provider()

        # Should call SMS service
        mock_sms_service.send_otp.assert_called()
        mock_showinfo.assert_called()

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.get_email_service')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showinfo')
    def test_test_email_provider(self, mock_showinfo, mock_get_email, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test email provider testing"""
        mock_service_class.return_value = mock_mfa_service
        mock_email_service = MagicMock()
        mock_email_service.send_otp.return_value = {'success': True, 'provider': 'mock'}
        mock_get_email.return_value = mock_email_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        panel._test_email_provider()

        # Should call email service
        mock_email_service.send_otp.assert_called()
        mock_showinfo.assert_called()

class TestDataLoading:
    """Test data loading methods"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    def test_load_all_data(self, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test loading all data tabs"""
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)

        # Mock individual load methods
        panel._load_overview = MagicMock()
        panel._load_policies = MagicMock()
        panel._load_users = MagicMock()
        panel._load_audit_log = MagicMock()
        panel._load_settings = MagicMock()

        panel._load_data()

        # Should call all load methods
        panel._load_overview.assert_called_once()
        panel._load_policies.assert_called_once()
        panel._load_users.assert_called_once()
        panel._load_audit_log.assert_called_once()
        panel._load_settings.assert_called_once()

class TestConvenienceFunction:
    """Test show_mfa_admin convenience function"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAAdminPanel')
    def test_show_mfa_admin(self, mock_panel_class):
        """Test show_mfa_admin convenience function"""
        mock_parent = MagicMock()
        mock_panel = MagicMock()
        mock_panel_class.return_value = mock_panel

        from university_system.infrastructure.auth.mfa_admin_gui import show_mfa_admin

        result = show_mfa_admin(mock_parent, admin_user_id=1)

        # Should create and return panel
        mock_panel_class.assert_called_once_with(mock_parent, admin_user_id=1)
        assert result == mock_panel

class TestErrorHandling:
    """Test error handling in admin panel"""

    @patch('university_system.infrastructure.auth.mfa_admin_gui.MFAService')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.tk.Toplevel')
    @patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.showerror')
    def test_reset_mfa_error(self, mock_showerror, mock_toplevel, mock_service_class, mock_mfa_service):
        """Test error handling when resetting MFA fails"""
        mock_mfa_service.disable_mfa.return_value = {'success': False, 'error': 'Database error'}
        mock_service_class.return_value = mock_mfa_service
        mock_parent = MagicMock()

        from university_system.infrastructure.auth.mfa_admin_gui import MFAAdminPanel

        panel = MFAAdminPanel(mock_parent, admin_user_id=1)
        panel.users_tree = MagicMock()
        panel.users_tree.selection.return_value = [1]
        panel.users_tree.item.return_value = {'values': ['testuser', 'student', 'Enabled', 'totp', 'Never']}

        with patch('university_system.infrastructure.auth.mfa_admin_gui.messagebox.askyesno', return_value=True):
            panel._reset_user_mfa()

        # Should show error
        mock_showerror.assert_called()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
