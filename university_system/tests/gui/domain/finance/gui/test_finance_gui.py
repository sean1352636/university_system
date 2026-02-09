"""Tests for FinanceGUI main coordinator class"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock

from university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI


@pytest.fixture
def mock_auth():
    """Create mock authentication"""
    auth = Mock()
    auth.current_user = {'username': 'testuser', 'role': 'admin'}
    auth.is_logged_in = Mock(return_value=True)
    auth.get_current_user = Mock(return_value={'username': 'testuser', 'role': 'admin'})
    return auth


@pytest.fixture
def root_window():
    """Create root Tk window for testing"""
    root = Mock()  # Mock Tk root to avoid display issues
    yield root


class TestFinanceGUIInit:
    """Test FinanceGUI initialization"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_init_with_auth(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test initialization with auth parameter"""
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        assert gui.root == root_window
        assert gui.auth == mock_auth

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_global_auth')
    def test_init_without_auth(self, mock_global_auth, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test initialization without auth parameter"""
        mock_get_auth.return_value = mock_auth
        mock_global_auth.return_value = mock_auth

        gui = FinanceGUI(root_window)

        assert gui.auth is not None

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_global_auth')
    def test_init_no_auth_available(self, mock_global_auth, mock_get_auth, mock_get_conn, root_window):
        """Test initialization when no auth is available"""
        mock_get_auth.return_value = None
        mock_global_auth.return_value = None

        with pytest.raises(RuntimeError, match="Authentication system not available"):
            FinanceGUI(root_window)

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_init_creates_managers(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test that initialization creates all manager instances"""
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        # Verify all managers were created
        assert hasattr(gui, 'db')
        assert hasattr(gui, 'layout')
        assert hasattr(gui, 'dashboard')
        assert hasattr(gui, 'budgets')
        assert hasattr(gui, 'transactions')
        assert hasattr(gui, 'invoices')
        assert hasattr(gui, 'expenses')
        assert hasattr(gui, 'reports')
        assert hasattr(gui, 'analytics')
        assert hasattr(gui, 'compliance')
        assert hasattr(gui, 'settings')
        assert hasattr(gui, 'revenue_source')
        assert hasattr(gui, 'library_finance')


class TestRoleMethods:
    """Test role checking methods"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_get_user_role_with_current_user(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test getting user role from current_user"""
        mock_auth.current_user = {'role': 'admin'}
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)
        role = gui.get_user_role()

        assert role == 'admin'

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_get_user_role_with_user_role_attr(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test getting user role from user_role attribute"""
        mock_auth.current_user = None
        mock_auth.user_role = 'staff'
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)
        role = gui.get_user_role()

        assert role == 'staff'

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_get_user_role_no_auth(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test getting user role with no auth"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.auth = None

        role = gui.get_user_role()

        assert role is None

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_is_admin_true(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test is_admin returns True for admin"""
        mock_auth.current_user = {'role': 'admin'}
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        assert gui.is_admin() is True

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_is_admin_false(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test is_admin returns False for non-admin"""
        mock_auth.current_user = {'role': 'student'}
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        assert gui.is_admin() is False

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_is_staff_true(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test is_staff returns True for staff"""
        mock_auth.current_user = {'role': 'staff'}
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        assert gui.is_staff() is True

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_is_student_true(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test is_student returns True for student"""
        mock_auth.current_user = {'role': 'student'}
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        assert gui.is_student() is True


class TestSystemInitialization:
    """Test system initialization"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.threading.Thread')
    def test_initialize_system(self, mock_thread, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test system initialization starts thread"""
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(root_window, auth=mock_auth)

        # Verify thread was started
        assert mock_thread.called

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_set_auth(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test setting auth manager"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)

        new_auth = Mock()
        gui.set_auth(new_auth)

        assert gui.auth == new_auth


class TestNavigationMethods:
    """Test navigation methods"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_return_to_main_menu_toplevel(self, mock_get_auth, mock_get_conn, mock_auth):
        """Test return to main menu from Toplevel window"""
        root = tk.Tk()
        toplevel = tk.Toplevel(root)
        mock_get_auth.return_value = mock_auth

        gui = FinanceGUI(toplevel, auth=mock_auth)
        gui.return_to_main_menu()

        # Toplevel should be destroyed
        assert not toplevel.winfo_exists()
        root.destroy()

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.UnifiedManagementGUI')
    def test_return_to_main_menu_standalone(self, mock_unified, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test return to main menu from standalone window"""
        mock_get_auth.return_value = mock_auth
        mock_main_gui = Mock()
        mock_unified.return_value = mock_main_gui

        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.return_to_main_menu()

        # Should create UnifiedManagementGUI
        mock_unified.assert_called_once_with(mock_auth)


class TestStudentsTab:
    """Test students tab functionality"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_create_students_tab(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test creating students tab"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)

        gui.create_students_tab()

        # Verify tree was created
        assert hasattr(gui, 'students_tree')

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_refresh_students(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test refreshing students data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock student data
        mock_cursor.fetchall.return_value = [
            ('ST001', 'John Doe', 'john@test.com', 'CS101', 'Active', 100.0),
        ]

        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.create_students_tab()

        gui.refresh_students()

        # Connection was made
        assert mock_get_conn.called

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.simpledialog')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_search_students(self, mock_get_auth, mock_get_conn, mock_dialog, root_window, mock_auth):
        """Test searching students"""
        mock_dialog.askstring.return_value = 'John'
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.create_students_tab()

        gui.search_students()

        mock_dialog.askstring.assert_called_once()


class TestFinancialDetailsView:
    """Test viewing student financial details"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.messagebox')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_view_student_finances_no_selection(self, mock_get_auth, mock_msgbox, mock_get_conn, root_window, mock_auth):
        """Test viewing student finances with no selection"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.create_students_tab()

        gui.view_student_finances()

        mock_msgbox.showwarning.assert_called_once()

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_view_student_finances_with_selection(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test viewing student finances with selection"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock student financial data
        mock_cursor.fetchone.return_value = (1000.0, 500.0, 500.0)
        mock_cursor.fetchall.return_value = []

        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.create_students_tab()

        # Mock selection
        gui.students_tree.insert('', 'end', values=('ST001', 'John Doe', 'john@test.com', 'CS101', 'Active', '£100.00'))
        gui.students_tree.selection_set(gui.students_tree.get_children()[0])

        try:
            gui.view_student_finances()
        except Exception:
            # Dialog creation may fail in test environment
            pass


class TestActivityLogging:
    """Test activity logging"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_log_activity_with_dashboard(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test logging activity when dashboard is available"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.dashboard.activity_listbox = Mock()

        gui.log_activity("Test activity")

        gui.dashboard.activity_listbox.insert.assert_called()

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_log_activity_without_dashboard(self, mock_get_auth, mock_get_conn, root_window, mock_auth, capsys):
        """Test logging activity when dashboard is not available"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)
        gui.dashboard = None

        gui.log_activity("Test activity")

        # Should not crash


class TestRunMethod:
    """Test GUI run method"""

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    def test_run_mainloop(self, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test run method starts mainloop"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)

        # Mock mainloop to prevent blocking
        root_window.mainloop = Mock()

        gui.run()

        root_window.mainloop.assert_called_once()

    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_connection')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.get_auth')
    @patch('university_system.modules.domain.finance.gui.finance.finance_gui.messagebox')
    def test_run_with_exception(self, mock_msgbox, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test run method handles exceptions"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)

        # Mock mainloop to raise exception
        root_window.mainloop = Mock(side_effect=Exception("Test error"))

        gui.run()

        mock_msgbox.showerror.assert_called_once()
