"""Tests for finance_management_gui module"""

import pytest
pytestmark = pytest.mark.gui

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import messagebox
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

from education_system.systems.university.interfaces.gui.finance.finance_management_gui import (
    FinanceManagementGUI,
    _launch_finance_cli_menu,
    FINANCE_GUI_AVAILABLE,
    FINANCE_REPORTING_GUI_AVAILABLE,
    FINANCE_CLI_AVAILABLE
)

_MOD = 'education_system.systems.university.interfaces.gui.finance.finance_management_gui'


class TestFinanceManagementGUI(unittest.TestCase):
    """Test suite for FinanceManagementGUI class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock root window
        self.root = Mock(spec=tk.Tk)

        # Create mock auth manager
        self.auth = Mock()
        self.auth.current_user = {'user_id': 1, 'username': 'test_user', 'role': 'admin'}
        self.auth.check_permission = Mock(return_value=True)

        self.gui = FinanceManagementGUI(self.root, self.auth)

    def tearDown(self):
        """Clean up after tests"""
        self.root = None
        self.auth = None
        self.gui = None

    def test_initialization(self):
        """Test FinanceManagementGUI initialization"""
        self.assertEqual(self.gui.root, self.root)
        self.assertEqual(self.gui.auth, self.auth)

    def test_initialization_stores_root(self):
        """Test initialization stores root reference"""
        gui = FinanceManagementGUI(self.root, self.auth)
        self.assertEqual(gui.root, self.root)

    def test_initialization_stores_auth(self):
        """Test initialization stores auth reference"""
        gui = FinanceManagementGUI(self.root, self.auth)
        self.assertEqual(gui.auth, self.auth)

    def test_has_show_finance_management(self):
        """Test that show_finance_management method exists"""
        self.assertTrue(hasattr(self.gui, 'show_finance_management'))
        self.assertTrue(callable(self.gui.show_finance_management))

    @patch(f'{_MOD}.messagebox.showerror')
    def test_show_finance_management_not_logged_in(self, mock_error):
        """Test show_finance_management when not logged in"""
        self.auth.current_user = None
        self.gui.show_finance_management()
        mock_error.assert_called_once()

    @patch(f'{_MOD}.messagebox.showerror')
    def test_show_finance_management_no_permission(self, mock_error):
        """Test show_finance_management when user lacks permissions"""
        self.auth.check_permission = Mock(return_value=False)
        self.gui.show_finance_management()
        mock_error.assert_called_once()

    @patch(f'{_MOD}.FinanceGUI')
    def test_show_finance_management_with_gui(self, mock_finance_gui):
        """Test show_finance_management with GUI available"""
        if not FINANCE_GUI_AVAILABLE:
            self.skipTest("Finance GUI not available")

        mock_app = Mock()
        mock_finance_gui.return_value = mock_app

        # Use a real class for Toplevel so isinstance() doesn't break
        mock_window = Mock()

        class FakeToplevel:
            def __init__(self, *args, **kwargs):
                pass
            def __getattr__(self, name):
                return getattr(mock_window, name)

        with patch(f'{_MOD}.tk.Toplevel', FakeToplevel):
            self.gui.show_finance_management()

        # Verify FinanceGUI was instantiated
        mock_finance_gui.assert_called_once()

    @patch(f'{_MOD}.FinanceGUI')
    @patch(f'{_MOD}.isinstance', return_value=True)
    def test_show_finance_management_with_toplevel_parent(self, mock_isinstance, mock_finance_gui):
        """Test show_finance_management when parent is already a Toplevel"""
        if not FINANCE_GUI_AVAILABLE:
            self.skipTest("Finance GUI not available")

        toplevel_root = Mock()
        gui = FinanceManagementGUI(toplevel_root, self.auth)

        mock_app = Mock()
        mock_finance_gui.return_value = mock_app

        gui.show_finance_management()

        # Should configure the existing window
        toplevel_root.title.assert_called()

    @patch(f'{_MOD}.messagebox.showwarning')
    def test_show_finance_management_no_gui_no_cli(self, mock_warning):
        """Test show_finance_management when neither GUI nor CLI available"""
        with patch(f'{_MOD}.FINANCE_GUI_AVAILABLE', False):
            with patch(f'{_MOD}.FINANCE_CLI_AVAILABLE', False):
                gui = FinanceManagementGUI(self.root, self.auth)
                gui.show_finance_management()
                mock_warning.assert_called_once()

    @patch(f'{_MOD}.messagebox.showerror')
    def test_show_finance_reporting_not_logged_in(self, mock_error):
        """Test show_finance_reporting_dashboard when not logged in"""
        self.auth.current_user = None
        self.gui.show_finance_reporting_dashboard()
        mock_error.assert_called_once()

    @patch(f'{_MOD}.messagebox.showerror')
    def test_show_finance_reporting_no_permission(self, mock_error):
        """Test show_finance_reporting_dashboard when user lacks permissions"""
        self.auth.check_permission = Mock(return_value=False)
        self.auth.current_user = {'role': 'student'}
        self.gui.show_finance_reporting_dashboard()
        mock_error.assert_called_once()

    @patch(f'{_MOD}.FinanceReportingGUI')
    @patch(f'{_MOD}.tk.Toplevel')
    def test_show_finance_reporting_with_gui(self, mock_toplevel, mock_reporting_gui):
        """Test show_finance_reporting_dashboard with GUI available"""
        if not FINANCE_REPORTING_GUI_AVAILABLE:
            self.skipTest("Finance Reporting GUI not available")

        mock_window = Mock()
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080
        mock_window.winfo_width.return_value = 1400
        mock_window.winfo_height.return_value = 900
        mock_toplevel.return_value = mock_window

        self.gui.show_finance_reporting_dashboard()

        # Verify window creation
        mock_toplevel.assert_called_once()
        mock_window.title.assert_called()
        mock_window.geometry.assert_called()
        mock_window.minsize.assert_called()

    @patch(f'{_MOD}.messagebox.showinfo')
    def test_show_finance_reporting_gui_not_available(self, mock_info):
        """Test show_finance_reporting_dashboard when GUI not available"""
        with patch(f'{_MOD}.FINANCE_REPORTING_GUI_AVAILABLE', False):
            gui = FinanceManagementGUI(self.root, self.auth)
            gui.show_finance_reporting_dashboard()
            mock_info.assert_called_once()

    @patch(f'{_MOD}.messagebox.showerror')
    @patch(f'{_MOD}.tk.Toplevel')
    def test_show_finance_reporting_exception(self, mock_toplevel, mock_error):
        """Test show_finance_reporting_dashboard when exception occurs"""
        mock_toplevel.side_effect = Exception("Test error")
        self.gui.show_finance_reporting_dashboard()
        mock_error.assert_called_once()


class TestLaunchFinanceCLIMenu(unittest.TestCase):
    """Test suite for _launch_finance_cli_menu function"""

    @patch(f'{_MOD}._display_finance_menu')
    @patch(f'{_MOD}._set_finance_cli_auth')
    def test_launch_cli_menu_with_auth(self, mock_set_auth, mock_display_menu):
        """Test launching CLI menu with auth"""
        if not FINANCE_CLI_AVAILABLE:
            self.skipTest("Finance CLI not available")

        mock_auth = Mock()
        _launch_finance_cli_menu(mock_auth)

        mock_set_auth.assert_called_once_with(mock_auth)
        mock_display_menu.assert_called_once()

    @patch(f'{_MOD}._display_finance_menu')
    def test_launch_cli_menu_without_auth(self, mock_display_menu):
        """Test launching CLI menu without auth"""
        if not FINANCE_CLI_AVAILABLE:
            self.skipTest("Finance CLI not available")

        _launch_finance_cli_menu(None)
        mock_display_menu.assert_called_once()

    @patch(f'{_MOD}._display_finance_menu', None)
    @patch('builtins.print')
    def test_launch_cli_menu_not_available(self, mock_print):
        """Test launching CLI menu when not available"""
        _launch_finance_cli_menu(Mock())
        mock_print.assert_called_with("Finance CLI menu not available")


class TestPermissionChecks(unittest.TestCase):
    """Test permission checking logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.root = Mock(spec=tk.Tk)
        self.auth = Mock()
        self.auth.current_user = {'user_id': 1, 'username': 'test_user', 'role': 'admin'}

        self.gui = FinanceManagementGUI(self.root, self.auth)

    @patch(f'{_MOD}.FinanceGUI')
    def test_manage_finances_permission(self, mock_finance_gui):
        """Test with manage_finances permission"""
        if not FINANCE_GUI_AVAILABLE:
            self.skipTest("Finance GUI not available")

        def check_perm(perm):
            return perm == 'manage_finances'

        self.auth.check_permission = check_perm

        class FakeToplevel:
            def __init__(self, *a, **kw): pass
            def __getattr__(self, name): return Mock()

        with patch(f'{_MOD}.tk.Toplevel', FakeToplevel):
            self.gui.show_finance_management()
        mock_finance_gui.assert_called_once()

    @patch(f'{_MOD}.FinanceGUI')
    def test_view_own_finances_permission(self, mock_finance_gui):
        """Test with view_own_finances permission"""
        if not FINANCE_GUI_AVAILABLE:
            self.skipTest("Finance GUI not available")

        def check_perm(perm):
            return perm == 'view_own_finances'

        self.auth.check_permission = check_perm

        class FakeToplevel:
            def __init__(self, *a, **kw): pass
            def __getattr__(self, name): return Mock()

        with patch(f'{_MOD}.tk.Toplevel', FakeToplevel):
            self.gui.show_finance_management()
        mock_finance_gui.assert_called_once()


if __name__ == '__main__':
    unittest.main()
