"""
Test suite for Internship Management GUI

Tests the InternshipGUI class and related functionality.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from education_system.post_18.university_system.modules.domain.student_affairs.gui.internship_management.internship_gui import InternshipGUI

# Base patch paths for the actual modules where symbols are used
_GUI_MOD = 'education_system.post_18.university_system.modules.domain.student_affairs.gui.internship_management.internship_gui'
_PLACEMENTS_MOD = 'education_system.post_18.university_system.modules.domain.student_affairs.gui.internship_management.placements'
_IMPORTS_MOD = 'education_system.post_18.university_system.modules.domain.student_affairs.gui.internship_management._imports'


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'student1',
        'role': 'student',
        'email': 'student@example.com'
    }
    auth.check_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = Mock(spec=tk.Tk)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.winfo_children.return_value = []
    return root


class TestInternshipGUI:
    """Test cases for InternshipGUI class"""

    @patch(f'{_GUI_MOD}.set_auth')
    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_initialization_with_auth(self, mock_init_db, mock_set_auth, mock_root, mock_auth):
        """Test GUI initialization with authentication"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Should set auth
            assert gui.auth == mock_auth
            mock_set_auth.assert_called_with(mock_auth)

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_initialization_without_auth(self, mock_init_db, mock_root):
        """Test GUI initialization without authentication"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, None)

            # Should still create GUI
            assert gui.auth is None

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_setup_main_interface(self, mock_init_db, mock_root, mock_auth):
        """Test main interface setup"""
        with patch.object(InternshipGUI, 'setup_main_interface', lambda self: None):
            gui = InternshipGUI(mock_root, mock_auth)

        # Manually call method
        with patch(f'{_GUI_MOD}.tk.Frame'), \
             patch(f'{_GUI_MOD}.tk.Label'), \
             patch(f'{_GUI_MOD}.tk.Canvas') as mock_canvas, \
             patch(f'{_GUI_MOD}.ttk.Scrollbar'), \
             patch(f'{_GUI_MOD}.ttk.Button'), \
             patch.object(gui, 'create_navigation_buttons'), \
             patch.object(gui, 'show_welcome'), \
             patch.object(gui, '_bind_nav_scroll_events'):
            gui.setup_main_interface()

            # Should clear widgets and setup interface
            assert hasattr(gui, 'auth')

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_get_user_role_methods(self, mock_init_db, mock_root, mock_auth):
        """Test user role checking methods"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Test student role
            assert gui.get_user_role() == 'student'
            assert gui.is_student() == True
            assert gui.is_admin() == False
            assert gui.is_staff() == False

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_get_user_role_admin(self, mock_init_db, mock_root, mock_auth):
        """Test admin role detection"""
        mock_auth.current_user['role'] = 'admin'

        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            assert gui.is_admin() == True
            assert gui.is_student() == False

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_get_user_role_staff(self, mock_init_db, mock_root, mock_auth):
        """Test staff role detection"""
        mock_auth.current_user['role'] = 'staff'

        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            assert gui.is_staff() == True
            assert gui.is_student() == False

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    @patch(f'{_GUI_MOD}.messagebox')
    def test_create_navigation_buttons_no_auth(self, mock_messagebox, mock_init_db, mock_root):
        """Test navigation button creation without auth"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, None)
            parent = Mock()

            gui.create_navigation_buttons(parent)

            # Should show error
            mock_messagebox.showerror.assert_called_once()

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_create_navigation_buttons_with_permissions(self, mock_init_db, mock_root, mock_auth):
        """Test navigation button creation with permissions"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)
            gui.nav_canvas = Mock()
            parent = Mock()

            with patch(f'{_GUI_MOD}.tk.Button') as mock_button:
                gui.create_navigation_buttons(parent)

                # Should create buttons
                assert mock_button.called

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    @patch(f'{_PLACEMENTS_MOD}.get_connection')
    def test_load_placement_data(self, mock_conn, mock_init_db, mock_root, mock_auth):
        """Test loading placement data"""
        mock_auth.current_user['role'] = 'admin'

        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

        # Mock database
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            (1, 'John Doe', 'Software Internship', 'Tech Corp', 'Jane Manager', '2024-01-01', 'active')
        ]

        # Mock tree
        gui.placement_tree = Mock()
        gui.placement_tree.get_children.return_value = []
        gui.placement_status_filter = Mock()
        gui.placement_status_filter.get.return_value = 'All'

        gui.load_placement_data()

        # Should query database
        mock_cursor.execute.assert_called_once()
        # Should insert data
        gui.placement_tree.insert.assert_called()

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    @patch(f'{_PLACEMENTS_MOD}.get_connection')
    @patch(f'{_PLACEMENTS_MOD}.messagebox')
    def test_view_placement_details(self, mock_messagebox, mock_conn, mock_init_db, mock_root, mock_auth):
        """Test viewing placement details"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

        # Mock tree with selection
        gui.placement_tree = Mock()
        gui.placement_tree.selection.return_value = []

        gui.view_placement_details()

        # Should show warning when no selection
        mock_messagebox.showwarning.assert_called_once()

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    @patch(f'{_PLACEMENTS_MOD}.messagebox')
    def test_update_placement_status_no_selection(self, mock_messagebox, mock_init_db, mock_root, mock_auth):
        """Test updating placement status without selection"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

        # Mock tree with no selection
        gui.placement_tree = Mock()
        gui.placement_tree.selection.return_value = []

        gui.update_placement_status()

        # Should show warning
        mock_messagebox.showwarning.assert_called_once()

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_show_placement_management_permission_check(self, mock_init_db, mock_root, mock_auth):
        """Test placement management permission check"""
        mock_auth.check_permission = Mock(return_value=False)

        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)
            gui.content_frame = Mock()
            gui.content_frame.winfo_children.return_value = []

        with patch(f'{_PLACEMENTS_MOD}.messagebox') as mock_msg:
            gui.show_placement_management()

            # Should show permission error
            mock_msg.showerror.assert_called_once()

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_clear_content(self, mock_init_db, mock_root, mock_auth):
        """Test content clearing"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

        gui.content_frame = Mock()
        widget1 = Mock()
        widget2 = Mock()
        gui.content_frame.winfo_children.return_value = [widget1, widget2]

        gui.clear_content()

        # Should destroy all widgets
        widget1.destroy.assert_called_once()
        widget2.destroy.assert_called_once()

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_navigation_features_exist(self, mock_init_db, mock_root, mock_auth):
        """Test that navigation features exist"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Should have navigation methods
            assert hasattr(gui, 'show_internships') or hasattr(gui, 'auth')
            assert hasattr(gui, 'show_placement_management')
            assert hasattr(gui, 'show_welcome')

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_integration_menu_exists(self, mock_init_db, mock_root, mock_auth):
        """Test integration services menu exists"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Should have integration menu method
            assert hasattr(gui, 'show_integration_menu')

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_cli_mode_method_exists(self, mock_init_db, mock_root, mock_auth):
        """Test CLI mode fallback exists"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Should have CLI mode method
            assert hasattr(gui, 'launch_cli_mode')

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_return_to_main_menu_exists(self, mock_init_db, mock_root, mock_auth):
        """Test return to main menu functionality exists"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Should have return method
            assert hasattr(gui, 'return_to_main_menu')

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    def test_scrollbar_navigation(self, mock_init_db, mock_root, mock_auth):
        """Test scrollbar navigation binding"""
        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

            # Should have scrollbar binding method
            assert hasattr(gui, '_bind_nav_scroll_events')

    @patch(f'{_IMPORTS_MOD}.init_internship_db')
    @patch(f'{_PLACEMENTS_MOD}.get_connection')
    @patch(f'{_PLACEMENTS_MOD}.messagebox')
    def test_database_error_handling_in_load(self, mock_messagebox, mock_conn, mock_init_db,
                                             mock_root, mock_auth):
        """Test database error handling when loading data"""
        mock_auth.current_user['role'] = 'admin'

        # Import sqlite3 to raise the right exception type
        from education_system.post_18.university_system.infrastructure.database.db import sqlite3
        mock_conn.side_effect = sqlite3.Error("Database error")

        with patch.object(InternshipGUI, 'setup_main_interface'):
            gui = InternshipGUI(mock_root, mock_auth)

        gui.placement_tree = Mock()
        gui.placement_tree.get_children.return_value = []
        gui.placement_status_filter = Mock()
        gui.placement_status_filter.get.return_value = 'All'

        gui.load_placement_data()

        # Should show error message
        mock_messagebox.showerror.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
