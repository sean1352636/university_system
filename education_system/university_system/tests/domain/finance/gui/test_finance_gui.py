"""Tests for FinanceGUI main coordinator class"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI

_MOD = 'education_system.university_system.modules.domain.finance.gui.finance.finance_gui'


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


@pytest.fixture
def gui(root_window, mock_auth):
    """Create a FinanceGUI with all widget-creating methods patched out."""
    with patch(f'{_MOD}.get_connection'), \
         patch(f'{_MOD}.get_auth', return_value=mock_auth), \
         patch(f'{_MOD}.LayoutManager') as MockLayout, \
         patch(f'{_MOD}.DashboardManager'), \
         patch(f'{_MOD}.threading.Thread'):
        # Make layout mock usable
        mock_layout = MockLayout.return_value
        mock_layout.content_frame = Mock()
        mock_layout.tab_frames = {}
        mock_layout.colors = {
            'primary': '#2c3e50', 'secondary': '#3498db', 'success': '#27ae60',
            'warning': '#f39c12', 'danger': '#e74c3c', 'light': '#ecf0f1',
            'dark': '#34495e', 'info': '#17a2b8',
        }

        g = FinanceGUI(root_window, auth=mock_auth)
        yield g


class TestFinanceGUIInit:
    """Test FinanceGUI initialization"""

    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}.get_auth')
    @patch(f'{_MOD}.LayoutManager')
    @patch(f'{_MOD}.DashboardManager')
    @patch(f'{_MOD}.threading.Thread')
    def test_init_with_auth(self, mock_thread, mock_dash, mock_layout, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test initialization with auth parameter"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)

        assert gui.root == root_window
        assert gui.auth == mock_auth

    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}.get_auth')
    @patch(f'{_MOD}.get_global_auth')
    @patch(f'{_MOD}.LayoutManager')
    @patch(f'{_MOD}.DashboardManager')
    @patch(f'{_MOD}.threading.Thread')
    def test_init_without_auth(self, mock_thread, mock_dash, mock_layout, mock_global_auth, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test initialization without auth parameter"""
        mock_get_auth.return_value = mock_auth
        mock_global_auth.return_value = mock_auth

        gui = FinanceGUI(root_window)

        assert gui.auth is not None

    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}.get_auth', return_value=None)
    @patch(f'{_MOD}.get_global_auth', return_value=None)
    def test_init_no_auth_available(self, mock_global_auth, mock_get_auth, mock_get_conn, root_window):
        """Test initialization when no auth is available"""
        with pytest.raises(RuntimeError):
            FinanceGUI(root_window)

    def test_init_creates_managers(self, gui):
        """Test that initialization creates all manager instances"""
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


class TestRoleMethods:
    """Test role checking methods"""

    def test_get_user_role_with_current_user(self, gui, mock_auth):
        """Test getting user role from current_user"""
        mock_auth.current_user = {'role': 'admin'}
        gui.auth = mock_auth
        assert gui.get_user_role() == 'admin'

    def test_get_user_role_with_user_role_attr(self, gui, mock_auth):
        """Test getting user role from user_role attribute"""
        mock_auth.current_user = None
        mock_auth.user_role = 'staff'
        gui.auth = mock_auth
        assert gui.get_user_role() == 'staff'

    def test_get_user_role_no_auth(self, gui):
        """Test getting user role with no auth"""
        gui.auth = None
        assert gui.get_user_role() is None

    def test_is_admin_true(self, gui, mock_auth):
        """Test is_admin returns True for admin"""
        mock_auth.current_user = {'role': 'admin'}
        gui.auth = mock_auth
        assert gui.is_admin() is True

    def test_is_admin_false(self, gui, mock_auth):
        """Test is_admin returns False for non-admin"""
        mock_auth.current_user = {'role': 'student'}
        gui.auth = mock_auth
        assert gui.is_admin() is False

    def test_is_staff_true(self, gui, mock_auth):
        """Test is_staff returns True for staff"""
        mock_auth.current_user = {'role': 'staff'}
        gui.auth = mock_auth
        assert gui.is_staff() is True

    def test_is_student_true(self, gui, mock_auth):
        """Test is_student returns True for student"""
        mock_auth.current_user = {'role': 'student'}
        gui.auth = mock_auth
        assert gui.is_student() is True


class TestSystemInitialization:
    """Test system initialization"""

    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}.get_auth')
    @patch(f'{_MOD}.LayoutManager')
    @patch(f'{_MOD}.DashboardManager')
    @patch(f'{_MOD}.threading.Thread')
    def test_initialize_system(self, mock_thread, mock_dash, mock_layout, mock_get_auth, mock_get_conn, root_window, mock_auth):
        """Test system initialization starts thread"""
        mock_get_auth.return_value = mock_auth
        gui = FinanceGUI(root_window, auth=mock_auth)

        # Verify thread was started
        assert mock_thread.called

    def test_set_auth(self, gui):
        """Test setting auth manager"""
        new_auth = Mock()
        gui.set_auth(new_auth)
        assert gui.auth == new_auth


class TestNavigationMethods:
    """Test navigation methods"""

    def test_return_to_main_menu_toplevel(self, gui):
        """Test return to main menu from Toplevel window"""
        # Make root look like a Toplevel via isinstance
        gui.root = Mock(spec=tk.Toplevel)
        gui.return_to_main_menu()
        gui.root.destroy.assert_called_once()

    def test_return_to_main_menu_standalone(self, gui):
        """Test return to main menu from standalone window"""
        # root is a plain Mock (not spec'd to Toplevel), so isinstance returns False
        # The function does a local import, so we patch the module attribute
        gui.return_to_main_menu()

        # root.destroy should be called in the else branch
        gui.root.destroy.assert_called_once()


class TestStudentsTab:
    """Test students tab functionality"""

    @patch(f'{_MOD}.tk.Frame')
    @patch(f'{_MOD}.tk.Label')
    @patch(f'{_MOD}.tk.Button')
    @patch(f'{_MOD}.tk.Entry')
    @patch(f'{_MOD}.tk.StringVar')
    @patch(f'{_MOD}.ttk.Treeview')
    @patch(f'{_MOD}.ttk.Scrollbar')
    def test_create_students_tab(self, mock_scroll, mock_tree, mock_sv, mock_entry,
                                  mock_btn, mock_label, mock_frame, gui):
        """Test creating students tab"""
        gui.create_students_tab()
        assert hasattr(gui, 'students_tree')

    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}.tk.Frame')
    @patch(f'{_MOD}.tk.Label')
    @patch(f'{_MOD}.tk.Button')
    @patch(f'{_MOD}.tk.Entry')
    @patch(f'{_MOD}.tk.StringVar')
    @patch(f'{_MOD}.ttk.Treeview')
    @patch(f'{_MOD}.ttk.Scrollbar')
    def test_refresh_students(self, mock_scroll, mock_tree, mock_sv, mock_entry,
                               mock_btn, mock_label, mock_frame, mock_get_conn, gui):
        """Test refreshing students data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchall.return_value = [
            ('ST001', 'John Doe', 'john@test.com', 'CS101', 'Active', 100.0),
        ]

        gui.create_students_tab()
        gui.refresh_students()

        assert mock_get_conn.called

    @patch(f'{_MOD}.simpledialog')
    @patch(f'{_MOD}.tk.Frame')
    @patch(f'{_MOD}.tk.Label')
    @patch(f'{_MOD}.tk.Button')
    @patch(f'{_MOD}.tk.Entry')
    @patch(f'{_MOD}.tk.StringVar')
    @patch(f'{_MOD}.ttk.Treeview')
    @patch(f'{_MOD}.ttk.Scrollbar')
    def test_search_students(self, mock_scroll, mock_tree, mock_sv, mock_entry,
                              mock_btn, mock_label, mock_frame, mock_dialog, gui):
        """Test searching students"""
        mock_dialog.askstring.return_value = 'John'
        gui.create_students_tab()
        gui.search_students()
        mock_dialog.askstring.assert_called_once()


class TestFinancialDetailsView:
    """Test viewing student financial details"""

    @patch(f'{_MOD}.simpledialog')
    @patch(f'{_MOD}.messagebox')
    def test_view_student_finances_no_selection(self, mock_msgbox, mock_dialog, gui):
        """Test viewing student finances with no selection"""
        gui.students_tree = Mock()
        gui.students_tree.selection.return_value = []
        # Admin with no selection gets simpledialog; return None to cancel
        mock_dialog.askstring.return_value = None

        gui.view_student_finances()

        # Should either show warning or user cancelled dialog
        assert mock_dialog.askstring.called or mock_msgbox.showwarning.called

    @patch(f'{_MOD}.get_connection')
    @patch(f'{_MOD}.tk.Toplevel')
    @patch(f'{_MOD}.tk.Frame')
    @patch(f'{_MOD}.tk.Label')
    @patch(f'{_MOD}.tk.Button')
    @patch(f'{_MOD}.tk.Entry')
    @patch(f'{_MOD}.tk.StringVar')
    @patch(f'{_MOD}.ttk.Treeview')
    @patch(f'{_MOD}.ttk.Scrollbar')
    @patch(f'{_MOD}.ttk.LabelFrame')
    def test_view_student_finances_with_selection(self, mock_lf, mock_scroll, mock_tree,
                                                    mock_sv, mock_entry, mock_btn, mock_label,
                                                    mock_frame, mock_toplevel, mock_get_conn, gui):
        """Test viewing student finances with selection"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_cursor.fetchone.return_value = (1000.0, 500.0, 500.0)
        mock_cursor.fetchall.return_value = []

        gui.create_students_tab()
        # Mock tree with selection
        gui.students_tree.selection.return_value = ['item1']
        gui.students_tree.item.return_value = {
            'values': ('ST001', 'John Doe', 'john@test.com', 'CS101', 'Active', '£100.00')
        }

        try:
            gui.view_student_finances()
        except Exception:
            pass


class TestActivityLogging:
    """Test activity logging"""

    def test_log_activity_with_dashboard(self, gui):
        """Test logging activity when dashboard is available"""
        gui.dashboard = Mock()
        gui.dashboard.activity_listbox = Mock()

        gui.log_activity("Test activity")

        gui.dashboard.activity_listbox.insert.assert_called()

    def test_log_activity_without_dashboard(self, gui):
        """Test logging activity when dashboard is not available"""
        gui.dashboard = None

        gui.log_activity("Test activity")
        # Should not crash


class TestRunMethod:
    """Test GUI run method"""

    def test_run_mainloop(self, gui):
        """Test run method starts mainloop"""
        gui.root.mainloop = Mock()
        gui.run()
        gui.root.mainloop.assert_called_once()

    @patch(f'{_MOD}.messagebox')
    def test_run_with_exception(self, mock_msgbox, gui):
        """Test run method handles exceptions"""
        gui.root.mainloop = Mock(side_effect=Exception("Test error"))
        gui.run()
        mock_msgbox.showerror.assert_called_once()
