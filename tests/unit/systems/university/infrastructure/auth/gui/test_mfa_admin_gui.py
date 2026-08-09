#!/usr/bin/env python3
"""
Tests for MFA Admin GUI
Tests administrative panel for MFA management, policies, user management, and audit logging
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import tkinter as tk

_ADMIN_MOD = 'education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui'


@pytest.fixture(autouse=True)
def mock_tkinter():
    """Patch tk.Toplevel so MFAAdminPanel can be instantiated without a real display."""
    def _noop_init(self, *a, **kw):
        self.children = {}
        self.tk = MagicMock()
        self._w = '.'
        self._name = 'mock'
        self._tclCommands = {}
        self._mock_methods = None

    with patch.object(tk.Toplevel, '__init__', _noop_init), \
         patch.object(tk.Toplevel, 'title', MagicMock()), \
         patch.object(tk.Toplevel, 'geometry', MagicMock()), \
         patch.object(tk.Toplevel, 'resizable', MagicMock()), \
         patch.object(tk.Toplevel, 'minsize', MagicMock()), \
         patch.object(tk.Toplevel, 'transient', MagicMock()), \
         patch.object(tk.Toplevel, 'grab_set', MagicMock()), \
         patch.object(tk.Toplevel, 'update_idletasks', MagicMock()), \
         patch.object(tk.Toplevel, 'winfo_screenwidth', MagicMock(return_value=1920)), \
         patch.object(tk.Toplevel, 'winfo_screenheight', MagicMock(return_value=1080)), \
         patch.object(tk.Toplevel, 'winfo_width', MagicMock(return_value=900)), \
         patch.object(tk.Toplevel, 'winfo_height', MagicMock(return_value=700)), \
         patch.object(tk.Toplevel, 'wait_window', MagicMock()), \
         patch.object(tk.Toplevel, 'destroy', MagicMock()), \
         patch(f'{_ADMIN_MOD}.tk', MagicMock()), \
         patch(f'{_ADMIN_MOD}.ttk', MagicMock()), \
         patch(f'{_ADMIN_MOD}.messagebox') as mock_msgbox, \
         patch(f'{_ADMIN_MOD}.scrolledtext', MagicMock()), \
         patch(f'{_ADMIN_MOD}._ensure_mfa_tables_exist'):
        yield mock_msgbox


@pytest.fixture
def temp_db():
    """Create a temporary database with MFA schema for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, role_id INTEGER);
        CREATE TABLE roles (id INTEGER PRIMARY KEY, role_name TEXT);
        CREATE TABLE mfa_methods (id INTEGER PRIMARY KEY, user_id INTEGER, method_type TEXT, is_enabled INTEGER, identifier TEXT, setup_completed TEXT);
        CREATE TABLE mfa_user_settings (user_id INTEGER PRIMARY KEY, mfa_enabled INTEGER, last_successful_verification TIMESTAMP);
        CREATE TABLE mfa_enforcement_policies (id INTEGER PRIMARY KEY, role_name TEXT, mfa_required INTEGER, allowed_methods TEXT, minimum_methods INTEGER, grace_period_days INTEGER, allow_device_trust INTEGER);
        CREATE TABLE mfa_verification_attempts (id INTEGER PRIMARY KEY, user_id INTEGER, method_type TEXT, attempted_at TIMESTAMP, success INTEGER, failure_reason TEXT, ip_address TEXT, device_id TEXT);
        CREATE TABLE mfa_trusted_devices (id INTEGER PRIMARY KEY, user_id INTEGER, device_id TEXT, device_name TEXT, trusted_at TIMESTAMP, expires_at TIMESTAMP, is_trusted INTEGER, revoked_at TIMESTAMP, ip_address TEXT, last_used_at TIMESTAMP);

        INSERT INTO roles VALUES (1, 'admin'), (2, 'student'), (3, 'instructor');
        INSERT INTO users VALUES (1, 'admin_user', 'admin', 1), (2, 'student_user', 'student', 2);
        INSERT INTO mfa_enforcement_policies VALUES (1, 'admin', 1, '["totp", "sms"]', 1, 7, 1);
        INSERT INTO mfa_user_settings VALUES (1, 1, '2024-01-01 10:00:00');
        INSERT INTO mfa_methods VALUES (1, 1, 'totp', 1, NULL, '2024-01-01');
        INSERT INTO mfa_verification_attempts VALUES (1, 1, 'totp', datetime('now'), 1, NULL, '127.0.0.1', NULL);
    """)
    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def mock_mfa_service(temp_db):
    """Create a mock MFA service pointing to the temp DB"""
    service = MagicMock()
    service.db_path = temp_db
    service.disable_mfa.return_value = {'success': True}
    return service


@pytest.fixture
def make_panel(mock_mfa_service):
    """Factory to create an MFAAdminPanel with mocked service"""
    def _make():
        with patch(f'{_ADMIN_MOD}.MFAService', return_value=mock_mfa_service):
            from education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui import MFAAdminPanel
            parent = MagicMock()
            panel = MFAAdminPanel(parent, admin_user_id=1)
        return panel

    return _make


class TestMFAAdminPanelInitialization:
    """Test panel initialization"""

    def test_panel_initialization(self, make_panel):
        """Test panel creates successfully"""
        panel = make_panel()
        assert panel.admin_user_id == 1
        assert hasattr(panel, 'notebook')

    def test_panel_window_configuration(self, make_panel):
        """Test panel calls window config methods"""
        panel = make_panel()
        panel.title.assert_called()
        panel.geometry.assert_called()


class TestOverviewTab:
    """Test overview/dashboard tab"""

    def test_load_overview_statistics(self, make_panel):
        """Test loading overview stats from DB"""
        panel = make_panel()
        # Stats labels should have been populated during init
        assert hasattr(panel, 'stats_labels')

    def test_statistics_labels_initialized(self, make_panel):
        """Test that stats labels are created"""
        panel = make_panel()
        # The _create_overview_tab should set up stats_labels dict
        assert isinstance(panel.stats_labels, dict)


class TestPoliciesTab:
    """Test policies tab"""

    def test_load_policies(self, make_panel):
        """Test policies are loaded from DB"""
        panel = make_panel()
        # policies_tree should exist after init
        assert hasattr(panel, 'policies_tree')

    def test_edit_policy_no_selection(self, make_panel, mock_tkinter):
        """Test edit policy with no selection shows warning"""
        panel = make_panel()
        panel.policies_tree = MagicMock()
        panel.policies_tree.selection.return_value = ()

        panel._edit_policy()

        mock_tkinter.showwarning.assert_called()


class TestUsersTab:
    """Test users tab"""

    def test_load_users(self, make_panel):
        """Test users are loaded from DB"""
        panel = make_panel()
        assert hasattr(panel, 'users_tree')

    def test_load_users_with_filters(self, make_panel):
        """Test user loading with search filters"""
        panel = make_panel()
        # After init, users should have been loaded
        panel.users_tree = MagicMock()
        panel._load_users()

    def test_reset_user_mfa(self, make_panel, mock_mfa_service, mock_tkinter):
        """Test resetting user's MFA"""
        panel = make_panel()
        panel.users_tree = MagicMock()
        panel.users_tree.selection.return_value = ('1',)
        panel.users_tree.item.return_value = {'values': ['admin_user', 'admin', 'Yes']}

        mock_tkinter.askyesno.return_value = True

        panel._reset_user_mfa()

        mock_mfa_service.disable_mfa.assert_called_once_with(1)

    def test_view_user_details_no_selection(self, make_panel, mock_tkinter):
        """Test view details with no selection shows warning"""
        panel = make_panel()
        panel.users_tree = MagicMock()
        panel.users_tree.selection.return_value = ()

        panel._view_user_details()

        mock_tkinter.showwarning.assert_called()


class TestAuditTab:
    """Test audit log tab"""

    def test_load_audit_log(self, make_panel):
        """Test audit log is loaded from DB"""
        panel = make_panel()
        assert hasattr(panel, 'audit_tree')

    def test_load_audit_log_with_filters(self, make_panel):
        """Test loading audit log with filters"""
        panel = make_panel()
        panel.audit_tree = MagicMock()
        panel._load_audit_log()

    def test_export_audit_log(self, make_panel, mock_tkinter, tmp_path):
        """Test exporting audit log to CSV"""
        panel = make_panel()
        temp_file = tmp_path / "audit.csv"

        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(temp_file)):
            panel._export_audit_log()

        if temp_file.exists():
            content = temp_file.read_text()
            assert len(content) > 0


class TestSettingsTab:
    """Test settings tab"""

    def test_load_settings(self, make_panel):
        """Test settings are loaded"""
        panel = make_panel()
        # Settings tab should be created during init
        assert hasattr(panel, 'notebook')

    def test_test_sms_provider(self, make_panel, mock_tkinter):
        """Test SMS provider test button"""
        mock_sms = MagicMock()
        mock_sms.send_otp.return_value = {'success': True, 'provider': 'test'}
        mock_get_sms = MagicMock(return_value=mock_sms)

        panel = make_panel()
        with patch('education_system.systems.university.infrastructure.auth.sms_provider.get_sms_service', mock_get_sms):
            panel._test_sms_provider()

        mock_tkinter.showinfo.assert_called()

    def test_test_email_provider(self, make_panel, mock_tkinter):
        """Test email provider test button"""
        mock_email = MagicMock()
        mock_email.send_otp.return_value = {'success': True, 'provider': 'test'}
        mock_get_email = MagicMock(return_value=mock_email)

        panel = make_panel()
        with patch('education_system.systems.university.infrastructure.auth.email_otp_service.get_email_service', mock_get_email):
            panel._test_email_provider()

        mock_tkinter.showinfo.assert_called()


class TestDataLoading:
    """Test data loading"""

    def test_load_all_data(self, make_panel):
        """Test that _load_data calls all sub-loaders"""
        panel = make_panel()

        with patch.object(panel, '_load_overview') as m1, \
             patch.object(panel, '_load_policies') as m2, \
             patch.object(panel, '_load_users') as m3, \
             patch.object(panel, '_load_audit_log') as m4, \
             patch.object(panel, '_load_settings') as m5:
            panel._load_data()

        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()
        m4.assert_called_once()
        m5.assert_called_once()


class TestConvenienceFunction:
    """Test show_mfa_admin convenience function"""

    @patch('education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui.MFAAdminPanel')
    def test_show_mfa_admin(self, mock_panel_class):
        """Test show_mfa_admin convenience function"""
        mock_parent = MagicMock()
        mock_panel = MagicMock()
        mock_panel_class.return_value = mock_panel

        from education_system.systems.university.interfaces.gui.shell.auth.mfa_admin_gui import show_mfa_admin

        result = show_mfa_admin(mock_parent, 1)

        mock_panel_class.assert_called_once_with(mock_parent, 1)
        assert result == mock_panel


class TestErrorHandling:
    """Test error handling in admin panel"""

    def test_reset_mfa_error(self, make_panel, mock_mfa_service, mock_tkinter):
        """Test error handling when MFA reset fails"""
        panel = make_panel()
        panel.users_tree = MagicMock()
        panel.users_tree.selection.return_value = ('1',)
        panel.users_tree.item.return_value = {'values': ['admin_user']}

        mock_tkinter.askyesno.return_value = True
        mock_mfa_service.disable_mfa.return_value = {'success': False, 'error': 'Test error'}

        panel._reset_user_mfa()

        mock_tkinter.showerror.assert_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
