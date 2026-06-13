"""
Tests for Financial Aid Admin Portal GUI

This module contains unit tests for the admin-facing financial aid portal.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal import AdminPortal

# Base patch paths for each submodule
_PORTAL = 'education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.portal'
_APPS = 'education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.applications'
_PKGS = 'education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.packages'
_DISB = 'education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.disbursements'
_REPORTS = 'education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.reports'
_FAFSA = 'education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal.fafsa_import'


class TestAdminPortalInit:
    """Test AdminPortal initialization"""

    def test_init_with_parent_frame(self):
        """Test initialization with parent frame"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()
        auth_mock = Mock()

        portal = AdminPortal(parent_frame, auth_mock)

        assert portal.parent_frame == parent_frame
        assert portal.auth == auth_mock
        assert portal.aid_manager is not None
        assert portal.scholarship_manager_gui is not None

        root.destroy()

    def test_init_without_auth(self):
        """Test initialization without explicit auth instance"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        with patch(f'{_PORTAL}.get_auth') as mock_get_auth:
            mock_get_auth.return_value = Mock()
            portal = AdminPortal(parent_frame)

            assert portal.auth is not None
            mock_get_auth.assert_called_once()

        root.destroy()

    def test_ensure_valid_parent_with_valid_frame(self):
        """Test _ensure_valid_parent with valid parent frame"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()
        portal = AdminPortal(parent_frame, Mock())

        result = portal._ensure_valid_parent()

        assert result == parent_frame

        root.destroy()

    def test_ensure_valid_parent_creates_standalone_window(self):
        """Test _ensure_valid_parent creates standalone window when needed"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()
        portal = AdminPortal(parent_frame, Mock())

        # Destroy parent frame to simulate invalid parent
        parent_frame.destroy()

        result = portal._ensure_valid_parent()

        assert result is not None
        assert portal.standalone_window is not None

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()


class TestAdminDashboard:
    """Test admin dashboard functionality"""

    @patch(f'{_PORTAL}.get_connection')
    def test_show_dashboard(self, mock_get_conn):
        """Test show_dashboard method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()
        parent_frame.pack()
        auth_mock = Mock()

        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.execute.return_value.fetchone.return_value = {'total': 0}
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, auth_mock)
        portal.show_dashboard()

        # Verify dashboard elements are created (portal may use standalone window)
        children = portal.parent_frame.winfo_children()
        assert len(children) > 0

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()

    @patch(f'{_PORTAL}.get_connection')
    def test_get_admin_stats(self, mock_get_conn):
        """Test _get_admin_stats method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        # Mock database responses
        mock_conn = Mock()
        mock_conn.execute.return_value.fetchone.side_effect = [
            {'total': 5},  # pending reviews
            {'count': 10},  # active packages
            {'total': 50000.0},  # total disbursed
            {'total': 10000.0}  # pending disbursements
        ]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, Mock())
        stats = portal._get_admin_stats()

        assert stats['pending_reviews'] == 5
        assert stats['active_packages'] == 10
        assert stats['total_disbursed'] == 50000.0
        assert stats['pending_disbursements'] == 10000.0

        root.destroy()


class TestAidApplications:
    """Test financial aid applications management"""

    @patch(f'{_APPS}.get_connection')
    def test_show_aid_applications(self, mock_get_conn):
        """Test show_aid_applications method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, Mock())
        portal.show_aid_applications()

        # Verify UI elements are created (portal may use standalone window)
        children = portal.parent_frame.winfo_children()
        assert len(children) > 0

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()

    @patch(f'{_APPS}.get_connection')
    def test_load_aid_applications(self, mock_get_conn):
        """Test _load_aid_applications method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        # Mock application data
        mock_app = {
            'application_id': '123',
            'username': 'student1',
            'academic_year': '2023-2024',
            'application_data': json.dumps({'aid_type': 'Grant'}),
            'application_date': '2023-09-01',
            'status': 'pending'
        }

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = [Mock(**mock_app)]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, Mock())
        portal.show_aid_applications()
        portal._load_aid_applications('pending')

        # Verify data loaded into tree
        assert portal.aid_apps_tree.get_children()

        root.destroy()

    @patch(f'{_APPS}.log_activity')
    @patch(f'{_APPS}.show_success')
    def test_review_aid_application_approve(self, mock_success, mock_log):
        """Test reviewing aid application - approve"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        portal = AdminPortal(parent_frame, Mock())
        portal.aid_manager = Mock()
        portal.aid_manager.update_application_status.return_value = True

        result = portal._review_aid_application_by_id('123', 'approved')

        assert result is True
        portal.aid_manager.update_application_status.assert_called_once_with(
            application_id='123',
            status='approved'
        )
        mock_log.assert_called_once()
        mock_success.assert_called_once()

        root.destroy()


class TestAidPackages:
    """Test aid package creation and management"""

    @patch(f'{_PKGS}.get_current_academic_year')
    @patch(f'{_PKGS}.get_academic_year_list')
    def test_show_create_package(self, mock_year_list, mock_current_year):
        """Test show_create_package method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        mock_current_year.return_value = '2023-2024'
        mock_year_list.return_value = ['2022-2023', '2023-2024', '2024-2025']

        portal = AdminPortal(parent_frame, Mock())
        portal.show_create_package()

        # Verify form elements are created (portal may use standalone window)
        children = portal.parent_frame.winfo_children()
        assert len(children) > 0

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()

    @patch(f'{_PKGS}.log_activity')
    @patch(f'{_PKGS}.show_success')
    @patch(f'{_PKGS}.show_error')
    def test_create_aid_package_success(self, mock_error, mock_success, mock_log):
        """Test successful aid package creation"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        portal = AdminPortal(parent_frame, Mock())
        portal.aid_manager = Mock()
        portal.aid_manager.create_aid_package.return_value = 'PKG123'

        fields = {
            'student_id': Mock(get=Mock(return_value='S12345')),
            'academic_year': Mock(get=Mock(return_value='2023-2024')),
            'package_name': Mock(get=Mock(return_value='Test Package')),
            'grant_amount': Mock(get=Mock(return_value='1000')),
            'loan_amount': Mock(get=Mock(return_value='2000')),
            'work_study_amount': Mock(get=Mock(return_value='500'))
        }

        result = portal._create_aid_package(fields)

        assert result is True
        mock_success.assert_called_once()
        mock_log.assert_called_once()

        root.destroy()

    @patch(f'{_PKGS}.show_error')
    def test_create_aid_package_missing_student_id(self, mock_error):
        """Test aid package creation with missing student ID"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        portal = AdminPortal(parent_frame, Mock())

        fields = {
            'student_id': Mock(get=Mock(return_value='')),
            'academic_year': Mock(get=Mock(return_value='2023-2024')),
            'grant_amount': Mock(get=Mock(return_value='1000')),
            'loan_amount': Mock(get=Mock(return_value='0')),
            'work_study_amount': Mock(get=Mock(return_value='0'))
        }

        result = portal._create_aid_package(fields)

        assert result is False
        mock_error.assert_called_once()

        root.destroy()


class TestDisbursements:
    """Test disbursement management"""

    @patch(f'{_DISB}.get_connection')
    def test_show_disbursements(self, mock_get_conn):
        """Test show_disbursements method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchone.return_value = {
            'count': 5,
            'total': 10000.0
        }
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, Mock())
        portal.show_disbursements()

        # Verify UI elements are created (portal may use standalone window)
        children = portal.parent_frame.winfo_children()
        assert len(children) > 0

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()

    @patch(f'{_DISB}.get_connection')
    def test_load_pending_disbursements(self, mock_get_conn):
        """Test _load_pending_disbursements method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        mock_disb = {
            'disbursement_id': 'D123',
            'student_id': 'S12345',
            'first_name': 'John',
            'last_name': 'Doe',
            'sid': 'S12345',
            'disbursement_type': 'Grant',
            'amount': 1000.0,
            'scheduled_date': '2023-10-01',
            'disbursement_date': '2023-10-01',
            'academic_term': 'Fall',
            'payment_method': 'direct_deposit',
            'transaction_id': 'TXN123'
        }

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = [Mock(**mock_disb)]
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, Mock())
        portal.show_disbursements()

        # Find the tree widget
        tree = None
        for widget in parent_frame.winfo_children():
            if isinstance(widget, ttk.Notebook):
                for tab in widget.tabs():
                    tab_widget = widget.nametowidget(tab)
                    for child in tab_widget.winfo_children():
                        if isinstance(child, ttk.Treeview):
                            tree = child
                            break

        root.destroy()

    @patch(f'{_DISB}.get_current_user')
    @patch(f'{_DISB}.log_activity')
    @patch(f'{_DISB}.show_success')
    def test_process_selected_disbursements(self, mock_success, mock_log, mock_user):
        """Test processing selected disbursements"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        mock_user.return_value = {'id': 1, 'username': 'admin'}

        portal = AdminPortal(parent_frame, Mock())
        portal.aid_manager = Mock()
        portal.aid_manager.process_disbursement.return_value = True

        # Create mock tree with selected items
        tree = ttk.Treeview(parent_frame)
        tree.insert('', 'end', values=('☑', 'D123', 'John Doe', 'S12345', 'Grant', '£1000.00', '2023-10-01', 'Fall', 'direct_deposit', 'TXN123'))

        portal._process_selected_disbursements(tree)

        root.destroy()


class TestReports:
    """Test report generation"""

    def test_show_reports(self):
        """Test show_reports method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        portal = AdminPortal(parent_frame, Mock())
        portal.show_reports()

        # Verify report options are displayed (portal may use standalone window)
        children = portal.parent_frame.winfo_children()
        assert len(children) > 0

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()

    @patch(f'{_REPORTS}.get_connection')
    def test_generate_aid_distribution_report(self, mock_get_conn):
        """Test _generate_aid_distribution_report method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        mock_conn = Mock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_conn.execute.return_value.fetchone.return_value = {
            'total_students': 100,
            'total_awards': 50,
            'total_awarded': 100000.0,
            'total_disbursed': 80000.0,
            'avg_award': 2000.0
        }
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        portal = AdminPortal(parent_frame, Mock())

        # This will create a window, so we need to handle that
        portal._generate_aid_distribution_report()

        root.destroy()


class TestFAFSAImport:
    """Test FAFSA import functionality"""

    def test_show_fafsa_import(self):
        """Test show_fafsa_import method"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        portal = AdminPortal(parent_frame, Mock())
        portal.show_fafsa_import()

        # Verify import UI is displayed (portal may use standalone window)
        children = portal.parent_frame.winfo_children()
        assert len(children) > 0

        if portal.standalone_window:
            portal.standalone_window.destroy()
        root.destroy()

    @patch(f'{_FAFSA}.show_warning')
    def test_import_fafsa_file_no_file(self, mock_warning):
        """Test FAFSA import with no file selected"""
        root = tk.Tk()
        parent_frame = ttk.Frame(root)
        parent_frame.pack()

        portal = AdminPortal(parent_frame, Mock())
        portal._import_fafsa_file('')

        mock_warning.assert_called_once()

        root.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
