"""
Test suite for Accessibility Tools GUI

Tests the AccessibilityToolsGUI class and related functionality.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call
import json
from datetime import datetime

from university_system.modules.domain.student_affairs.gui.accessibility_tools_gui import (
    AccessibilityToolsGUI,
    launch_accessibility_tools_gui
)


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'testuser',
        'role': 'admin',
        'email': 'test@example.com'
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
def mock_db_connection():
    """Create a mock database connection"""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return conn


class TestAccessibilityToolsGUI:
    """Test cases for AccessibilityToolsGUI class"""

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.log_activity')
    def test_initialization_with_auth(self, mock_log, mock_toplevel, mock_root, mock_auth):
        """Test GUI initialization with authentication"""
        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Should create window
        mock_toplevel.assert_called_once()

        # Should set current user
        assert gui.current_user == mock_auth.current_user
        assert gui.auth == mock_auth

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox')
    def test_initialization_without_auth(self, mock_messagebox, mock_root):
        """Test GUI initialization without authentication"""
        auth = Mock()
        auth.current_user = None

        gui = AccessibilityToolsGUI(mock_root, auth)

        # Should show error message
        mock_messagebox.showerror.assert_called_once()
        assert "must be logged in" in mock_messagebox.showerror.call_args[0][1]

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.ttk')
    def test_create_main_window(self, mock_ttk, mock_toplevel, mock_root, mock_auth):
        """Test main window creation"""
        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Window should be created with proper title and geometry
        window = mock_toplevel.return_value
        window.title.assert_called_with("Accessibility & Accommodation Tools")
        window.geometry.assert_called_with("1400x900")
        window.minsize.assert_called_with(1200, 700)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_load_profiles_admin(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test loading profiles as admin user"""
        # Setup mock data
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'profile_id': 1,
                'user_id': 1,
                'disabilities': '["Visual Impairment"]',
                'accommodations': '["Extended Time"]',
                'assistive_technologies': '["Screen Reader"]',
                'updated_at': '2024-11-18 10:00:00'
            }
        ]

        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.load_profiles()

        # Should query all profiles for admin
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "SELECT * FROM accessibility_profiles" in sql
        assert "ORDER BY updated_at DESC" in sql

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_load_profiles_student(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test loading profiles as student user"""
        # Change role to student
        mock_auth.current_user['role'] = 'student'

        # Setup mock data
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.load_profiles()

        # Should query only user's own profile
        args = mock_cursor.execute.call_args[0]
        assert "WHERE user_id = ?" in args[0]
        assert args[1] == (1,)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_load_requests_with_filter(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test loading accommodation requests with status filter"""
        # Setup mock data
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'request_id': 1,
                'student_id': 1,
                'accommodation_type': 'Extended Time',
                'description': 'Need extra time for exams',
                'status': 'pending',
                'requested_date': '2024-11-18',
                'reviewed_by': None
            }
        ]

        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.request_status_filter.get = Mock(return_value='pending')
        gui.load_requests()

        # Should filter by status
        args = mock_cursor.execute.call_args[0]
        assert "WHERE status = ?" in args[0]
        assert args[1] == ('pending',)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_load_exam_accommodations(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test loading exam accommodations"""
        # Setup mock data
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'accommodation_id': 1,
                'student_id': 1,
                'exam_id': 'EXAM001',
                'extended_time': 30,
                'separate_room': 1,
                'assistive_technology': 'Screen Reader',
                'reader_scribe': 0,
                'status': 'active'
            }
        ]

        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.load_exam_accommodations()

        # Should query active accommodations
        sql = mock_cursor.execute.call_args[0][0]
        assert "WHERE status = 'active'" in sql

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_load_assistive_tech_requests(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test loading assistive technology requests"""
        # Setup mock data
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'request_id': 1,
                'student_id': 1,
                'technology_type': 'Screen Reader Software',
                'status': 'approved',
                'requested_date': '2024-11-18',
                'fulfilled_date': '2024-11-19'
            }
        ]

        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.load_assistive_tech_requests()

        # Should query tech requests
        mock_cursor.execute.assert_called_once()

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.transaction')
    def test_save_accessibility_settings_new(self, mock_transaction, mock_conn, mock_toplevel,
                                            mock_root, mock_auth):
        """Test saving new accessibility settings"""
        # Setup mocks
        mock_db = Mock()
        mock_cursor = Mock()
        mock_transaction.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No existing settings

        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Set form values
        gui.theme_var = Mock()
        gui.theme_var.get.return_value = 'high_contrast'
        gui.font_size_var = Mock()
        gui.font_size_var.get.return_value = 18
        gui.screen_reader_var = Mock()
        gui.screen_reader_var.get.return_value = True
        gui.keyboard_nav_var = Mock()
        gui.keyboard_nav_var.get.return_value = True

        with patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox'):
            gui.save_accessibility_settings()

        # Should insert new settings
        calls = mock_cursor.execute.call_args_list
        assert any('INSERT INTO accessibility_settings' in str(call) for call in calls)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.transaction')
    def test_save_accessibility_settings_update(self, mock_transaction, mock_conn, mock_toplevel,
                                               mock_root, mock_auth):
        """Test updating existing accessibility settings"""
        # Setup mocks
        mock_db = Mock()
        mock_cursor = Mock()
        mock_transaction.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'setting_id': 1}  # Existing settings

        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Set form values
        gui.theme_var = Mock()
        gui.theme_var.get.return_value = 'dark'
        gui.font_size_var = Mock()
        gui.font_size_var.get.return_value = 20
        gui.screen_reader_var = Mock()
        gui.screen_reader_var.get.return_value = False
        gui.keyboard_nav_var = Mock()
        gui.keyboard_nav_var.get.return_value = True

        with patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox'):
            gui.save_accessibility_settings()

        # Should update existing settings
        calls = mock_cursor.execute.call_args_list
        assert any('UPDATE accessibility_settings' in str(call) for call in calls)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox')
    def test_action_methods_show_dialogs(self, mock_messagebox, mock_toplevel, mock_root, mock_auth):
        """Test that action methods show appropriate dialogs"""
        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Test create profile
        gui.create_profile()
        assert mock_messagebox.showinfo.called

        # Test submit request
        gui.submit_request()
        assert mock_messagebox.showinfo.called

        # Test add exam accommodation
        gui.add_exam_accommodation()
        assert mock_messagebox.showinfo.called

        # Test request assistive tech
        gui.request_assistive_tech()
        assert mock_messagebox.showinfo.called

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    def test_update_status(self, mock_toplevel, mock_root, mock_auth):
        """Test status bar update"""
        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.status_bar = Mock()

        gui.update_status("Test message")

        gui.status_bar.config.assert_called_with(text="Test message")

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.AccessibilityToolsGUI')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox')
    def test_launch_function_success(self, mock_messagebox, mock_gui_class, mock_root, mock_auth):
        """Test successful launch of GUI"""
        launch_accessibility_tools_gui(mock_root, mock_auth)

        # Should create GUI instance
        mock_gui_class.assert_called_once_with(mock_root, mock_auth)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.AccessibilityToolsGUI')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox')
    def test_launch_function_error(self, mock_messagebox, mock_gui_class, mock_root, mock_auth):
        """Test error handling in launch function"""
        mock_gui_class.side_effect = Exception("Test error")

        launch_accessibility_tools_gui(mock_root, mock_auth)

        # Should show error message
        mock_messagebox.showerror.assert_called_once()
        assert "Test error" in str(mock_messagebox.showerror.call_args)

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_error_handling_load_profiles(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test error handling when loading profiles"""
        mock_conn.side_effect = Exception("Database error")

        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        with patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.messagebox') as mock_msg:
            gui.load_profiles()
            # Should show error message
            mock_msg.showerror.assert_called_once()

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    def test_notebook_tabs_created(self, mock_toplevel, mock_root, mock_auth):
        """Test that all notebook tabs are created"""
        with patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.ttk') as mock_ttk:
            gui = AccessibilityToolsGUI(mock_root, mock_auth)

            # Should create notebook with multiple tabs
            assert hasattr(gui, 'notebook')

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    def test_treeview_configuration(self, mock_toplevel, mock_root, mock_auth):
        """Test that treeviews are properly configured"""
        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Should have multiple treeviews for different data
        assert hasattr(gui, 'profiles_tree')
        assert hasattr(gui, 'requests_tree')
        assert hasattr(gui, 'exam_tree')
        assert hasattr(gui, 'tech_tree')

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.get_connection')
    def test_json_parsing_in_profiles(self, mock_conn, mock_toplevel, mock_root, mock_auth):
        """Test JSON parsing in profile data"""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_conn.return_value.__enter__.return_value = mock_db
        mock_db.cursor.return_value = mock_cursor

        # Test with valid JSON
        mock_cursor.fetchall.return_value = [
            {
                'profile_id': 1,
                'user_id': 1,
                'disabilities': '["Dyslexia", "ADHD"]',
                'accommodations': '["Note-taking support"]',
                'assistive_technologies': '[]',
                'updated_at': '2024-11-18'
            }
        ]

        gui = AccessibilityToolsGUI(mock_root, mock_auth)
        gui.load_profiles()

        # Should successfully parse and display

    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.tk.Toplevel')
    @patch('university_system.modules.domain.student_affairs.gui.accessibility_tools_gui.log_activity')
    def test_activity_logging(self, mock_log, mock_toplevel, mock_root, mock_auth):
        """Test that user actions are logged"""
        gui = AccessibilityToolsGUI(mock_root, mock_auth)

        # Should log opening the GUI
        assert mock_log.called
        log_calls = [str(call) for call in mock_log.call_args_list]
        assert any("Opened Accessibility Tools GUI" in str(call) for call in log_calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
