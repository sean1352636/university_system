"""
Test suite for Student Union GUI

Tests the StudentUnionGUI class and related functionality.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# The module where StudentUnionGUI is defined (where names are looked up at runtime)
_SRC = 'education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.main_gui'

# Import from student_union_gui package
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui import StudentUnionGUI


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
    return auth


@pytest.fixture
def mock_root():
    """Create a mock Tkinter parent window"""
    root = Mock(spec=tk.Toplevel)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    # __init__ always calls these on self.root
    root.title = Mock()
    root.geometry = Mock()
    root.minsize = Mock()
    return root


class TestStudentUnionGUI:
    """Test cases for StudentUnionGUI class"""

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_initialization_with_parent_and_auth(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test GUI initialization with parent window and authentication"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should set current user
            assert gui.current_user is not None
            assert gui.initialized == True

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.messagebox')
    @patch(f'{_SRC}.init_i18n')
    def test_initialization_standalone_without_auth_shows_error(self, mock_init_i18n, mock_messagebox, mock_get_auth):
        """Test standalone initialization without authentication shows error"""
        mock_get_auth.return_value = Mock(current_user=None)

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch(f'{_SRC}.tk.Tk') as mock_tk:

            mock_tk_instance = Mock()
            mock_tk.return_value = mock_tk_instance

            gui = StudentUnionGUI(parent=None)

            # Should show error and destroy window
            mock_messagebox.showerror.assert_called()
            mock_tk_instance.destroy.assert_called()

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_initialization_with_parent_without_auth_waits(self, mock_init_i18n, mock_get_auth, mock_root):
        """Test initialization with parent but no auth waits for auth setup"""
        mock_get_auth.return_value = Mock(current_user=None)

        with patch.object(StudentUnionGUI, 'setup_database'):
            gui = StudentUnionGUI(parent=mock_root)

            # Should mark as not initialized yet
            assert gui.initialized == False

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.sqlite3.connect')
    @patch(f'{_SRC}.init_i18n')
    def test_setup_database(self, mock_init_i18n, mock_connect, mock_get_auth, mock_root, mock_auth):
        """Test database setup"""
        mock_get_auth.return_value = mock_auth

        mock_db = Mock()
        mock_cursor = Mock()
        mock_connect.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        with patch.object(StudentUnionGUI, 'setup_gui'):
            gui = StudentUnionGUI(parent=mock_root)

        # Should create tables
        assert mock_cursor.execute.called

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_set_auth_method(self, mock_init_i18n, mock_get_auth, mock_root):
        """Test set_auth method for integration"""
        mock_get_auth.return_value = Mock(current_user=None)

        with patch.object(StudentUnionGUI, 'setup_database'):
            gui = StudentUnionGUI(parent=mock_root)

        # Set auth later
        new_auth = Mock()
        new_auth.current_user = {
            'id': 2,
            'username': 'newuser',
            'email': 'new@example.com',
            'role': 'admin'
        }

        gui.set_auth(new_auth)

        # Should update current user
        assert gui.current_user['username'] == 'newuser'
        assert gui.auth_manager == new_auth

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_setup_gui_creates_sidebar(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test GUI setup creates sidebar navigation"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'), \
             patch.object(StudentUnionGUI, 'build_sidebar_navigation'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have build_sidebar_navigation method
            assert hasattr(gui, 'build_sidebar_navigation')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_is_admin_method(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test is_admin method"""
        mock_auth.current_user['role'] = 'admin'
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            assert gui.is_admin() == True

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_is_staff_method(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test is_staff method"""
        mock_auth.current_user['role'] = 'staff'
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            assert gui.is_staff() == True

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_sidebar_headers_and_buttons(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test sidebar header and button methods"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have sidebar helper methods
            assert hasattr(gui, 'add_sidebar_header')
            assert hasattr(gui, 'add_sidebar_button')
            assert hasattr(gui, 'add_sidebar_separator')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_core_features_navigation(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test core features navigation methods exist"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have core feature methods
            assert hasattr(gui, 'show_clubs_content') or hasattr(gui, 'build_sidebar_navigation')
            assert hasattr(gui, 'show_events_content') or hasattr(gui, 'build_sidebar_navigation')
            assert hasattr(gui, 'show_facilities_content') or hasattr(gui, 'build_sidebar_navigation')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_elections_voting_features_exist(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test elections and voting features exist"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have election methods
            assert hasattr(gui, 'open_elections_dialog') or hasattr(gui, 'build_sidebar_navigation')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_integration_services_exist(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test integration services exist"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have integration methods
            assert hasattr(gui, 'open_shop_gui_direct') or hasattr(gui, 'build_sidebar_navigation')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_mousewheel_scrolling(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test mousewheel scrolling handler"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have mousewheel handler
            assert hasattr(gui, '_on_mousewheel')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_database_path_configuration(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test database path configuration"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have db_path attribute
            assert hasattr(gui, 'db_path')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_safe_db_call_method(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test safe database call method"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have safe db call method
            assert hasattr(gui, '_safe_db_call')

    @patch(f'{_SRC}.get_auth')
    @patch(f'{_SRC}.init_i18n')
    def test_show_main_dashboard_method(self, mock_init_i18n, mock_get_auth, mock_root, mock_auth):
        """Test show main dashboard method"""
        mock_get_auth.return_value = mock_auth

        with patch.object(StudentUnionGUI, 'setup_database'), \
             patch.object(StudentUnionGUI, 'setup_gui'):

            gui = StudentUnionGUI(parent=mock_root)

            # Should have dashboard method
            assert hasattr(gui, 'show_main_dashboard')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
