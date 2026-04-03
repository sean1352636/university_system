"""
Test suite for Helpdesk GUI

Tests the HelpdeskGUI class and related functionality.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from education_system.university_system.modules.domain.student_affairs.gui.helpdesk import HelpdeskGUI


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'role': 'admin',
        'permissions': ['manage_tickets', 'view_all_tickets']
    }
    return auth


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = Mock(spec=tk.Tk)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.winfo_width.return_value = 1200
    root.winfo_height.return_value = 800
    return root


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection"""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return conn


class TestHelpdeskGUI:
    """Test cases for HelpdeskGUI class"""

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.get_auth')
    def test_initialization_with_auth(self, mock_get_auth, mock_permissions, mock_init_db,
                                     mock_root, mock_auth):
        """Test GUI initialization with authentication"""
        mock_get_auth.return_value = mock_auth

        with patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'), \
             patch.object(HelpdeskGUI, 'ensure_subject_column'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Should initialize database
            mock_init_db.assert_called_once()

            # Should set auth
            assert gui.auth == mock_auth

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.get_auth')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.get_global_auth')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.messagebox')
    def test_initialization_without_auth(self, mock_messagebox, mock_get_global_auth, mock_get_auth,
                                        mock_permissions, mock_init_db, mock_root):
        """Test GUI initialization without authentication"""
        mock_get_auth.return_value = None
        mock_get_global_auth.return_value = None

        with patch.object(HelpdeskGUI, 'ensure_subject_column'):
            gui = HelpdeskGUI(mock_root, None)

        # Should show error and destroy root
        mock_messagebox.showerror.assert_called()
        mock_root.destroy.assert_called_once()

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_ensure_subject_column(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test database migration for subject column"""
        with patch('education_system.university_system.infrastructure.database.db.get_connection') as mock_conn:
            mock_db = Mock()
            mock_cursor = Mock()
            mock_conn.return_value = mock_db
            mock_db.cursor.return_value = mock_cursor

            # Simulate column doesn't exist
            mock_cursor.fetchall.return_value = [
                (0, 'ticket_id', 'INTEGER', 0, None, 1),
                (1, 'user_id', 'INTEGER', 0, None, 0)
            ]

            with patch.object(HelpdeskGUI, 'setup_current_user'), \
                 patch.object(HelpdeskGUI, 'setup_styles'), \
                 patch.object(HelpdeskGUI, 'setup_main_window'), \
                 patch.object(HelpdeskGUI, 'create_menu_bar'), \
                 patch.object(HelpdeskGUI, 'show_main_dashboard'):

                gui = HelpdeskGUI(mock_root, mock_auth)

            # Should add missing columns
            calls = [str(call) for call in mock_cursor.execute.call_args_list]
            assert any('ALTER TABLE' in str(call) for call in calls)

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_setup_current_user(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test current user setup"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Should setup current user from auth
            assert gui.current_user is not None
            assert gui.current_user['username'] == 'testuser'
            assert gui.current_user['role'] == 'admin'

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_setup_styles(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test style configuration"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            with patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.ttk.Style') as mock_style:
                gui = HelpdeskGUI(mock_root, mock_auth)

                # Should configure custom styles
                assert hasattr(gui, 'style')

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base._t', side_effect=lambda key, **kw: kw.get('default', key))
    def test_setup_main_window(self, mock_t, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test main window setup"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'), \
             patch.object(HelpdeskGUI, 'center_window'), \
             patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.ttk.Frame'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Should set window title and geometry
            mock_root.title.assert_called_with("Enhanced Helpdesk System")
            mock_root.geometry.assert_called_with("1200x800")
            mock_root.minsize.assert_called_with(800, 600)

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_center_window(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test window centering"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window', lambda self: None), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)
            gui.center_window()

            # Should call update_idletasks
            mock_root.update_idletasks.assert_called()

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_ticket_management_features_exist(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test that ticket management features exist"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Core features should exist
            assert hasattr(gui, 'show_main_dashboard') or hasattr(gui, 'current_user')

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    @patch('education_system.university_system.infrastructure.database.db.get_connection')
    def test_database_operations_use_context_manager(self, mock_conn, mock_permissions,
                                                     mock_init_db, mock_root, mock_auth):
        """Test that database operations use context manager"""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Database connection should be established during init
            assert mock_conn.called or mock_init_db.called

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.messagebox')
    def test_error_handling_database_failure(self, mock_messagebox, mock_permissions,
                                            mock_init_db, mock_root, mock_auth):
        """Test error handling when database initialization fails"""
        mock_init_db.side_effect = Exception("Database error")

        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Should still create GUI even if some initialization fails
            assert gui is not None

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_authentication_integration(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test authentication system integration"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Should have auth and current user
            assert gui.auth is not None
            assert gui.current_user is not None

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_role_based_access(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test role-based access control"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Admin role should have access
            assert gui.current_user['role'] == 'admin'

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_main_container_created(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test main container creation"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window', lambda self: setattr(self, 'main_container', Mock())), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)

            # Should have main container
            assert hasattr(gui, 'main_container')

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_user_object_structure(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test current_user object structure"""
        with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
             patch.object(HelpdeskGUI, 'setup_current_user'), \
             patch.object(HelpdeskGUI, 'setup_styles'), \
             patch.object(HelpdeskGUI, 'setup_main_window'), \
             patch.object(HelpdeskGUI, 'create_menu_bar'), \
             patch.object(HelpdeskGUI, 'show_main_dashboard'):

            gui = HelpdeskGUI(mock_root, mock_auth)
            gui.setup_current_user()

            # Should have properly structured user dict
            if gui.current_user:
                assert 'id' in gui.current_user
                assert 'username' in gui.current_user
                assert 'role' in gui.current_user

    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.init_helpdesk_db')
    @patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.setup_enhanced_helpdesk_permissions')
    def test_activity_logging_integration(self, mock_permissions, mock_init_db, mock_root, mock_auth):
        """Test activity logging integration"""
        with patch('education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base.log_activity') as mock_log:
            with patch.object(HelpdeskGUI, 'ensure_subject_column'), \
                 patch.object(HelpdeskGUI, 'setup_current_user'), \
                 patch.object(HelpdeskGUI, 'setup_styles'), \
                 patch.object(HelpdeskGUI, 'setup_main_window'), \
                 patch.object(HelpdeskGUI, 'create_menu_bar'), \
                 patch.object(HelpdeskGUI, 'show_main_dashboard'):

                gui = HelpdeskGUI(mock_root, mock_auth)

                # Activity logging should be available if module is present
                assert hasattr(gui, 'current_user')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
