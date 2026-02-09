"""
Test suite for Student Support GUI

Tests the StudentSupportGUI class and related functionality.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from university_system.modules.domain.student_affairs.gui.student_support import StudentSupportGUI


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
    """Create a mock Tkinter root window"""
    root = Mock(spec=tk.Tk)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    return root


@pytest.fixture
def mock_support_config():
    """Create a mock support configuration"""
    with patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig') as mock_config:
        config = Mock()
        yield config


@pytest.fixture
def mock_enhanced_support():
    """Create a mock enhanced support system"""
    with patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport') as mock_support:
        support = Mock()
        yield support


class TestStudentSupportGUI:
    """Test cases for StudentSupportGUI class"""

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.set_auth')
    def test_initialization_with_auth(self, mock_set_auth, mock_support, mock_config, mock_root, mock_auth):
        """Test GUI initialization with authentication"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should set auth
            assert gui.auth == mock_auth
            mock_set_auth.assert_called_with(mock_auth)

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.get_auth')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.messagebox')
    def test_initialization_without_auth_shows_error(self, mock_messagebox, mock_get_auth,
                                                     mock_support, mock_config, mock_root):
        """Test GUI initialization without authentication shows error"""
        mock_get_auth.return_value = None

        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'):

            gui = StudentSupportGUI(mock_root, None)

            # Should show error and destroy root
            mock_messagebox.showerror.assert_called()
            mock_root.destroy.assert_called()

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_setup_theme(self, mock_support, mock_config, mock_root, mock_auth):
        """Test theme setup"""
        with patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'), \
             patch('university_system.modules.domain.student_affairs.gui.student_support_gui.ttk.Style') as mock_style:

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should configure colors and styles
            assert hasattr(gui, 'colors')
            assert 'primary' in gui.colors
            assert 'secondary' in gui.colors

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_get_user_role_methods(self, mock_support, mock_config, mock_root, mock_auth):
        """Test user role checking methods"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Test student role
            assert gui.get_user_role() == 'student'
            assert gui.is_student() == True
            assert gui.is_admin() == False
            assert gui.is_staff() == False

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_get_user_role_admin(self, mock_support, mock_config, mock_root, mock_auth):
        """Test admin role detection"""
        mock_auth.current_user['role'] = 'admin'

        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            assert gui.is_admin() == True
            assert gui.is_student() == False

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_get_user_role_staff(self, mock_support, mock_config, mock_root, mock_auth):
        """Test staff role detection"""
        mock_auth.current_user['role'] = 'staff'

        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            assert gui.is_staff() == True
            assert gui.is_student() == False

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_create_widgets(self, mock_support, mock_config, mock_root, mock_auth):
        """Test widget creation"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets', lambda self: None), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

        # Manually call method
        with patch.object(gui, 'create_sidebar'), \
             patch.object(gui, 'create_content_area'), \
             patch.object(gui, 'create_status_bar'):

            gui.create_widgets()

            # Should create main components
            gui.create_sidebar.assert_called_once()
            gui.create_content_area.assert_called_once()
            gui.create_status_bar.assert_called_once()

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_create_nav_button(self, mock_support, mock_config, mock_root, mock_auth):
        """Test navigation button creation"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)
            gui.nav_frame = Mock()

        with patch('university_system.modules.domain.student_affairs.gui.student_support_gui.ttk.Button') as mock_button:
            btn = gui.create_nav_button("Test Button", lambda: None)

            # Should create button
            assert mock_button.called

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_navigation_features_exist(self, mock_support, mock_config, mock_root, mock_auth):
        """Test that navigation features exist"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should have navigation methods
            assert hasattr(gui, 'show_dashboard')
            assert hasattr(gui, 'show_search')
            assert hasattr(gui, 'show_faqs')
            assert hasattr(gui, 'show_knowledge_base')

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_ticket_features_exist(self, mock_support, mock_config, mock_root, mock_auth):
        """Test that ticket features exist"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should have ticket methods
            assert hasattr(gui, 'show_create_ticket')
            assert hasattr(gui, 'show_my_tickets')

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_return_to_main_menu_exists(self, mock_support, mock_config, mock_root, mock_auth):
        """Test return to main menu functionality exists"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should have return method
            assert hasattr(gui, 'return_to_main_menu')

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_refresh_data_exists(self, mock_support, mock_config, mock_root, mock_auth):
        """Test refresh data functionality exists"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should have refresh method
            assert hasattr(gui, 'refresh_data')

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_sidebar_scrollbar_binding(self, mock_support, mock_config, mock_root, mock_auth):
        """Test sidebar scrollbar binding"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should have scrollbar binding method
            assert hasattr(gui, '_bind_sidebar_scroll_events')

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_database_safe_call_method(self, mock_support, mock_config, mock_root, mock_auth):
        """Test safe database call method"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            # Should have safe db call method
            assert hasattr(gui, '_safe_db_call')

    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.SupportConfig')
    @patch('university_system.modules.domain.student_affairs.gui.student_support_gui.EnhancedStudentSupport')
    def test_user_identity_method(self, mock_support, mock_config, mock_root, mock_auth):
        """Test user identity retrieval method"""
        with patch.object(StudentSupportGUI, 'setup_theme'), \
             patch.object(StudentSupportGUI, 'setup_current_user'), \
             patch.object(StudentSupportGUI, 'create_widgets'), \
             patch.object(StudentSupportGUI, 'create_menu'), \
             patch.object(StudentSupportGUI, 'load_dashboard'):

            gui = StudentSupportGUI(mock_root, mock_auth)

            user_id, username = gui._get_current_user_identity()

            # Should return user info
            assert user_id == 1
            assert username == 'student1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
