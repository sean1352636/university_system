"""
Test suite for Student Union Management GUI

Tests the StudentUnionManagementGUI class and related functionality.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui import StudentUnionManagementGUI


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'admin',
        'role': 'admin',
        'email': 'admin@example.com'
    }
    return auth


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window"""
    root = Mock(spec=tk.Tk)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    return root


class TestStudentUnionManagementGUI:
    """Test cases for StudentUnionManagementGUI class"""

    def test_initialization(self, mock_root, mock_auth):
        """Test GUI initialization"""
        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        # Should set root and auth
        assert gui.root == mock_root
        assert gui.auth == mock_auth

    def test_initialization_with_theme_manager(self, mock_root, mock_auth):
        """Test initialization stores root and auth"""
        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        assert gui.root == mock_root
        assert gui.auth == mock_auth

    def test_initialization_without_theme_manager(self, mock_root, mock_auth):
        """Test initialization works without theme manager"""
        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        # Should initialize without errors
        assert gui.root is not None
        assert gui.auth is not None

    def test_on_theme_changed_method(self, mock_root, mock_auth):
        """Test show_student_union_portal method exists"""
        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        # Should have portal method
        assert hasattr(gui, 'show_student_union_portal')
        assert hasattr(gui, 'open_student_union_portal_gui')

    def test_show_student_union_portal_method(self, mock_root, mock_auth):
        """Test show_student_union_portal wrapper method"""
        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch.object(gui, 'open_student_union_portal_gui') as mock_open:
            gui.show_student_union_portal()

            # Should call the actual open method
            mock_open.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI')
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel')
    def test_open_student_union_portal_gui_no_auth(self, mock_toplevel, mock_union_gui, mock_root):
        """Test opening portal without authentication"""
        auth = Mock()
        auth.current_user = None

        gui = StudentUnionManagementGUI(mock_root, auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.messagebox') as mock_msg:
            gui.open_student_union_portal_gui()

            # Should show error
            mock_msg.showerror.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', False)
    def test_open_student_union_portal_gui_not_available(self, mock_root, mock_auth):
        """Test opening portal when GUI not available"""
        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.messagebox') as mock_msg:
            gui.open_student_union_portal_gui()

            # Should show error
            mock_msg.showerror.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', True)
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI')
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel')
    def test_open_student_union_portal_gui_success(self, mock_toplevel, mock_union_gui, mock_root, mock_auth):
        """Test successful portal opening"""
        # Mock window and GUI
        mock_window = Mock()
        mock_toplevel.return_value = mock_window
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080
        mock_window.winfo_width.return_value = 1400
        mock_window.winfo_height.return_value = 900

        # Mock union GUI instance
        mock_gui_instance = Mock()
        mock_gui_instance.initialized = True
        mock_union_gui.return_value = mock_gui_instance

        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.DEFAULT_DB_PATH', '/path/to/db'):
            gui.open_student_union_portal_gui()

        # Should create window
        mock_toplevel.assert_called_once_with(mock_root)
        mock_window.title.assert_called_once()
        mock_window.geometry.assert_called()

        # Should create GUI instance
        mock_union_gui.assert_called_once()
        mock_gui_instance.show_main_dashboard.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', True)
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI')
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel')
    def test_open_student_union_portal_gui_not_initialized(self, mock_toplevel, mock_union_gui,
                                                           mock_root, mock_auth):
        """Test opening portal when GUI needs initialization"""
        # Mock window
        mock_window = Mock()
        mock_toplevel.return_value = mock_window
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080
        mock_window.winfo_width.return_value = 1400
        mock_window.winfo_height.return_value = 900

        # Mock union GUI instance that's not initialized
        mock_gui_instance = Mock()
        mock_gui_instance.initialized = False
        mock_union_gui.return_value = mock_gui_instance

        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.DEFAULT_DB_PATH', '/path/to/db'):
            gui.open_student_union_portal_gui()

        # Should setup GUI manually
        mock_gui_instance.setup_gui.assert_called_once()
        mock_gui_instance.setup_database.assert_called_once()
        mock_gui_instance.show_main_dashboard.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', True)
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI')
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel')
    def test_open_student_union_portal_gui_with_theme(self, mock_toplevel, mock_union_gui,
                                                       mock_root, mock_auth):
        """Test opening portal creates window and GUI"""
        # Mock window
        mock_window = Mock()
        mock_toplevel.return_value = mock_window
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080
        mock_window.winfo_width.return_value = 1400
        mock_window.winfo_height.return_value = 900

        # Mock union GUI instance
        mock_gui_instance = Mock()
        mock_gui_instance.initialized = True
        mock_union_gui.return_value = mock_gui_instance

        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.DEFAULT_DB_PATH', '/path/to/db'):
            gui.open_student_union_portal_gui()

        # Should create window and show dashboard
        mock_toplevel.assert_called_once_with(mock_root)
        mock_gui_instance.show_main_dashboard.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', True)
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI')
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel')
    def test_open_student_union_portal_gui_error_handling(self, mock_toplevel, mock_union_gui,
                                                          mock_root, mock_auth):
        """Test error handling when opening portal"""
        mock_union_gui.side_effect = Exception("Test error")

        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.messagebox') as mock_msg, \
             patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.display_student_union_menu') as mock_cli:

            gui.open_student_union_portal_gui()

            # Should show error
            mock_msg.showerror.assert_called_once()
            # Should try CLI fallback
            mock_cli.assert_called_once()

    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', True)
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI')
    @patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel')
    def test_window_centering(self, mock_toplevel, mock_union_gui, mock_root, mock_auth):
        """Test window centering calculation"""
        # Mock window
        mock_window = Mock()
        mock_toplevel.return_value = mock_window
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080
        mock_window.winfo_width.return_value = 1400
        mock_window.winfo_height.return_value = 900

        # Mock union GUI instance
        mock_gui_instance = Mock()
        mock_gui_instance.initialized = True
        mock_union_gui.return_value = mock_gui_instance

        gui = StudentUnionManagementGUI(mock_root, mock_auth)

        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.DEFAULT_DB_PATH', '/path/to/db'):
            gui.open_student_union_portal_gui()

        # Should center window
        mock_window.update_idletasks.assert_called()
        # Should call geometry with position
        geometry_calls = [str(call) for call in mock_window.geometry.call_args_list]
        assert len(geometry_calls) >= 1

    def test_auth_context_passed_to_union_gui(self, mock_root, mock_auth):
        """Test that auth context is passed to union GUI"""
        with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.STUDENT_UNION_GUI_AVAILABLE', True), \
             patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.StudentUnionGUI') as mock_union_gui, \
             patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.tk.Toplevel'):

            mock_gui_instance = Mock()
            mock_gui_instance.initialized = False
            mock_union_gui.return_value = mock_gui_instance

            gui = StudentUnionManagementGUI(mock_root, mock_auth)

            with patch('education_system.systems.university.interfaces.gui.pastoral.student_union_management_gui.DEFAULT_DB_PATH', '/path/to/db'):
                gui.open_student_union_portal_gui()

            # Should set auth manager on union GUI
            assert mock_gui_instance.auth_manager == mock_auth


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
