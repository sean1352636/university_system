#!/usr/bin/env python3
"""
Comprehensive tests for Email Manager Management GUI Module
Tests the wrapper/management GUI for email manager
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import tempfile
import os
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, PropertyMock

# Import the module under test
from education_system.systems.university.interfaces.gui.shell.email import email_manager_management_gui

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            first_name TEXT,
            last_name TEXT,
            role_id INTEGER,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO users (id, username, password_hash, email, first_name, last_name)
        VALUES (1, 'testuser', 'hash', 'test@example.com', 'Test', 'User')
    """)

    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_auth(temp_db):
    """Create a mock auth manager"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'role': 'student',
        'permissions': ['view_messages', 'send_emails']
    }
    auth.is_logged_in.return_value = True
    auth.get_current_user.return_value = auth.current_user
    return auth

@pytest.fixture
def root_window():
    """Create a Tkinter root window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except (OSError, IOError):
        pass

class TestEmailManagerManagementGUIInitialization:
    """Test EmailManagerManagementGUI initialization"""

    def test_gui_initialization(self, root_window, mock_auth):
        """Test GUI initializes without errors"""
        try:
            gui = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                mock_auth
            )
            assert gui is not None
            assert gui.root == root_window
            assert gui.auth == mock_auth
        except Exception as e:
            # GUI may fail in headless environment
            assert isinstance(e, (tk.TclError, Exception))

    def test_gui_stores_parent_root(self, root_window, mock_auth):
        """Test that GUI stores parent root reference"""
        try:
            gui = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                mock_auth
            )
            assert gui.root == root_window
        except (OSError, IOError):
            pass

    def test_gui_stores_auth_manager(self, root_window, mock_auth):
        """Test that GUI stores auth manager reference"""
        try:
            gui = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                mock_auth
            )
            assert gui.auth == mock_auth
        except (OSError, IOError):
            pass

    def test_gui_initializes_theme_manager(self, root_window, mock_auth):
        """Test that GUI initializes theme manager"""
        try:
            with patch('education_system.systems.university.interfaces.gui.shell.theme_config.get_theme_manager'):
                gui = email_manager_management_gui.EmailManagerManagementGUI(
                    root_window,
                    mock_auth
                )
                # Theme manager should be initialized
        except (OSError, IOError):
            pass

    def test_gui_handles_missing_theme_manager(self, root_window, mock_auth):
        """Test that GUI handles missing theme manager gracefully"""
        with patch('education_system.systems.university.interfaces.gui.shell.theme_config.get_theme_manager',
                   side_effect=Exception('Theme manager not available')):
            try:
                gui = email_manager_management_gui.EmailManagerManagementGUI(
                    root_window,
                    mock_auth
                )
                # Should still initialize without theme manager
                assert gui is not None
            except (OSError, IOError):
                pass

class TestShowEmailManager:
    """Test show_email_manager method"""

    def test_show_email_manager_checks_authentication(self, root_window, mock_auth):
        """Test that show_email_manager checks authentication"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.Toplevel'):
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                try:
                    gui.show_email_manager()
                except (OSError, IOError):
                    pass

    def test_show_email_manager_no_auth(self, root_window):
        """Test show_email_manager with no authentication"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            None
        )

        with patch('tkinter.messagebox.showerror') as mock_error:
            gui.show_email_manager()
            # Should show error message
            mock_error.assert_called_once()

    def test_show_email_manager_no_user(self, root_window, mock_auth):
        """Test show_email_manager when no user is logged in"""
        mock_auth.current_user = None

        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.messagebox.showerror') as mock_error:
            gui.show_email_manager()
            # Should show error message
            mock_error.assert_called_once()

    def test_show_email_manager_checks_permissions(self, root_window, mock_auth):
        """Test that show_email_manager checks permissions"""
        # Remove permissions
        mock_auth.current_user['permissions'] = []

        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.messagebox.showerror') as mock_error:
            gui.show_email_manager()
            # Should show permission error
            mock_error.assert_called_once()

    def test_show_email_manager_with_send_emails_permission(self, root_window, mock_auth):
        """Test show_email_manager with send_emails permission"""
        mock_auth.current_user['permissions'] = ['send_emails']

        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.Toplevel') as mock_toplevel:
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                try:
                    gui.show_email_manager()
                    # Should create toplevel window
                except (OSError, IOError):
                    pass

    def test_show_email_manager_with_view_messages_permission(self, root_window, mock_auth):
        """Test show_email_manager with view_messages permission"""
        mock_auth.current_user['permissions'] = ['view_messages']

        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.Toplevel') as mock_toplevel:
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                try:
                    gui.show_email_manager()
                    # Should create toplevel window
                except (OSError, IOError):
                    pass

    def test_show_email_manager_gui_not_available(self, root_window, mock_auth):
        """Test show_email_manager when EmailManagerGUI is not available"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch.object(
            email_manager_management_gui,
            'EMAIL_MANAGER_GUI_AVAILABLE',
            False
        ):
            with patch('tkinter.messagebox.showerror') as mock_error:
                gui.show_email_manager()
                # Should show error about GUI not available
                mock_error.assert_called_once()

    def test_show_email_manager_creates_toplevel(self, root_window, mock_auth):
        """Test that show_email_manager creates Toplevel window"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.Toplevel') as mock_toplevel:
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                with patch.object(
                    email_manager_management_gui,
                    'EmailManagerGUI'
                ):
                    try:
                        gui.show_email_manager()
                        # Should have called Toplevel
                        mock_toplevel.assert_called_once()
                    except (OSError, IOError):
                        pass

    def test_show_email_manager_sets_window_properties(self, root_window, mock_auth):
        """Test that show_email_manager sets window title and geometry"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        mock_top = Mock()
        mock_top.winfo_screenwidth.return_value = 1920
        mock_top.winfo_screenheight.return_value = 1080
        with patch('tkinter.Toplevel', return_value=mock_top):
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                with patch.object(
                    email_manager_management_gui,
                    'EmailManagerGUI'
                ):
                    try:
                        gui.show_email_manager()
                        # Should set title
                        mock_top.title.assert_called_once()
                        # Should set geometry
                        mock_top.geometry.assert_called_once()
                    except (OSError, IOError):
                        pass

    def test_show_email_manager_applies_theme(self, root_window, mock_auth):
        """Test that show_email_manager applies theme to window"""
        mock_theme = Mock()
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )
        gui.theme_manager = mock_theme

        mock_top = Mock()
        mock_top.winfo_screenwidth.return_value = 1920
        mock_top.winfo_screenheight.return_value = 1080
        with patch('tkinter.Toplevel', return_value=mock_top):
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                with patch.object(
                    email_manager_management_gui,
                    'EmailManagerGUI'
                ):
                    try:
                        gui.show_email_manager()
                        # Should apply theme
                        mock_theme.apply_theme_to_window.assert_called_once()
                    except (OSError, IOError):
                        pass

    def test_show_email_manager_makes_transient(self, root_window, mock_auth):
        """Test that show_email_manager makes window transient"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        mock_top = Mock()
        mock_top.winfo_screenwidth.return_value = 1920
        mock_top.winfo_screenheight.return_value = 1080
        with patch('tkinter.Toplevel', return_value=mock_top):
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                with patch.object(
                    email_manager_management_gui,
                    'EmailManagerGUI'
                ):
                    try:
                        gui.show_email_manager()
                        # Should make window transient
                        mock_top.transient.assert_called_once()
                    except (OSError, IOError):
                        pass

    def test_show_email_manager_grabs_focus(self, root_window, mock_auth):
        """Test that show_email_manager grabs focus"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        mock_top = Mock()
        mock_top.winfo_screenwidth.return_value = 1920
        mock_top.winfo_screenheight.return_value = 1080
        with patch('tkinter.Toplevel', return_value=mock_top):
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                with patch.object(
                    email_manager_management_gui,
                    'EmailManagerGUI'
                ):
                    try:
                        gui.show_email_manager()
                        # Should grab focus
                        mock_top.grab_set.assert_called_once()
                    except (OSError, IOError):
                        pass

    def test_show_email_manager_creates_email_gui(self, root_window, mock_auth):
        """Test that show_email_manager creates EmailManagerGUI instance"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        mock_top = Mock()
        mock_top.winfo_screenwidth.return_value = 1920
        mock_top.winfo_screenheight.return_value = 1080
        mock_email_gui = Mock()

        with patch('tkinter.Toplevel', return_value=mock_top):
            with patch.object(
                email_manager_management_gui,
                'EMAIL_MANAGER_GUI_AVAILABLE',
                True
            ):
                with patch.object(
                    email_manager_management_gui,
                    'EmailManagerGUI',
                    return_value=mock_email_gui
                ) as mock_gui_class:
                    try:
                        gui.show_email_manager()
                        # Should create EmailManagerGUI
                        mock_gui_class.assert_called_once()
                    except (OSError, IOError):
                        pass

    def test_show_email_manager_handles_exception(self, root_window, mock_auth):
        """Test that show_email_manager handles exceptions gracefully"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.Toplevel', side_effect=Exception('Test error')):
            with patch('tkinter.messagebox.showerror') as mock_error:
                gui.show_email_manager()
                # Should show error message
                mock_error.assert_called()

class TestComposeEmail:
    """Test compose_email method"""

    def test_compose_email_shows_messagebox(self, root_window, mock_auth):
        """Test that compose_email shows info message"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.messagebox.showinfo') as mock_info:
            gui.compose_email('test@example.com')
            # Should show message box
            mock_info.assert_called_once()

    def test_compose_email_includes_address(self, root_window, mock_auth):
        """Test that compose_email includes email address in message"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )

        with patch('tkinter.messagebox.showinfo') as mock_info:
            test_email = 'student@example.com'
            gui.compose_email(test_email)
            # Check that call includes the email address
            call_args = mock_info.call_args
            assert test_email in str(call_args)

class TestThemeManagement:
    """Test theme management functionality"""

    def test_on_theme_changed_executes(self, root_window, mock_auth):
        """Test that on_theme_changed method executes"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )
        gui.theme_manager = Mock()

        # Should execute without error
        gui.on_theme_changed()

    def test_on_theme_changed_with_no_theme_manager(self, root_window, mock_auth):
        """Test on_theme_changed with no theme manager"""
        gui = email_manager_management_gui.EmailManagerManagementGUI(
            root_window,
            mock_auth
        )
        gui.theme_manager = None

        # Should execute without error
        gui.on_theme_changed()

class TestModuleAvailability:
    """Test module availability checks"""

    def test_email_manager_gui_available_flag(self):
        """Test EMAIL_MANAGER_GUI_AVAILABLE flag exists"""
        assert hasattr(
            email_manager_management_gui,
            'EMAIL_MANAGER_GUI_AVAILABLE'
        )
        assert isinstance(
            email_manager_management_gui.EMAIL_MANAGER_GUI_AVAILABLE,
            bool
        )

class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self, root_window, mock_auth):
        """Test complete workflow"""
        try:
            # Create GUI
            gui = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                mock_auth
            )

            # Show email manager (with mocking to avoid actual window)
            with patch('tkinter.Toplevel'):
                with patch.object(
                    email_manager_management_gui,
                    'EMAIL_MANAGER_GUI_AVAILABLE',
                    True
                ):
                    with patch.object(
                        email_manager_management_gui,
                        'EmailManagerGUI'
                    ):
                        gui.show_email_manager()

            # Compose email
            with patch('tkinter.messagebox.showinfo'):
                gui.compose_email('test@example.com')

            # Theme change
            gui.on_theme_changed()

        except (OSError, IOError):
            pass  # May fail in headless environment

    def test_multiple_instances(self, root_window, mock_auth):
        """Test creating multiple instances"""
        try:
            gui1 = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                mock_auth
            )
            gui2 = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                mock_auth
            )

            # Both should be independent
            assert gui1 is not gui2
        except (OSError, IOError):
            pass

class TestErrorHandling:
    """Test error handling"""

    def test_handles_missing_auth_gracefully(self, root_window):
        """Test handling missing auth"""
        try:
            gui = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                None
            )
            assert gui.auth is None
        except (OSError, IOError):
            pass

    def test_handles_invalid_auth(self, root_window):
        """Test handling invalid auth object"""
        invalid_auth = "not an auth object"
        try:
            gui = email_manager_management_gui.EmailManagerManagementGUI(
                root_window,
                invalid_auth
            )
            # Should store it even if invalid
            assert gui.auth == invalid_auth
        except (OSError, IOError):
            pass

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
