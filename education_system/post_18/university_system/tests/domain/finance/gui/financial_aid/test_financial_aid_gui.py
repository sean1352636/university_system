"""
Tests for Financial Aid GUI Main Coordinator

This module contains unit tests for the main financial aid GUI coordinator that routes
users to appropriate portals.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock

from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui import (
    FinancialAidGUI, launch_financial_aid_gui
)


class TestFinancialAidGUIInit:
    """Test FinancialAidGUI initialization"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    def test_init_with_auth(self, mock_get_user, mock_check_perm, mock_get_auth):
        """Test initialization with authentication"""
        mock_auth = Mock()
        mock_user = Mock(username='testuser')
        mock_auth.current_user = mock_user
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = mock_user
        mock_check_perm.return_value = False

        root = tk.Tk()
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=root)

        assert gui.auth == mock_auth
        assert gui.parent == root
        assert gui.current_user is not None
        assert gui.is_admin is False

        root.destroy()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.show_error')
    def test_init_without_user(self, mock_error, mock_get_auth):
        """Test initialization without logged-in user"""
        mock_auth = Mock()
        mock_auth.current_user = None
        mock_get_auth.return_value = mock_auth

        root = tk.Tk()
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=root)

        mock_error.assert_called_once()

        root.destroy()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_init_admin_user(self, mock_check_perm, mock_get_auth):
        """Test initialization with admin user"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='admin')
        mock_get_auth.return_value = mock_auth
        mock_check_perm.return_value = True

        root = tk.Tk()
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=root)

        assert gui.is_admin is True

        root.destroy()


class TestWindowCreation:
    """Test window creation methods"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_create_standalone_window(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test create_standalone_window method"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='testuser')
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = Mock()
        mock_check_perm.return_value = False

        gui = FinancialAidGUI(auth_instance=mock_auth)

        # Note: This would start mainloop, so we can't fully test it
        # Just verify it doesn't crash during setup
        assert gui.root is None

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_create_embedded_interface(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test create_embedded_interface method"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='testuser')
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = Mock()
        mock_check_perm.return_value = False

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)

        gui.create_embedded_interface()

        assert gui.main_frame is not None

        root.destroy()


class TestNavigation:
    """Test navigation between portals"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_show_student_portal(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test show_student_portal method"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='testuser')
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = Mock()
        mock_check_perm.return_value = False

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)
        gui.main_frame = ttk.Frame(parent)

        gui.show_student_portal()

        assert gui.student_portal is not None

        root.destroy()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_show_admin_portal(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test show_admin_portal method"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='admin')
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = Mock()
        mock_check_perm.return_value = True

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)
        gui.main_frame = ttk.Frame(parent)

        gui.show_admin_portal()

        assert gui.admin_portal is not None

        root.destroy()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.show_error')
    def test_show_admin_portal_no_permission(self, mock_error, mock_check_perm, mock_get_user, mock_get_auth):
        """Test show_admin_portal denies access without permission"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='testuser')
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = Mock()
        mock_check_perm.return_value = False

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)
        gui.main_frame = ttk.Frame(parent)

        gui.show_admin_portal()

        mock_error.assert_called_once()

        root.destroy()


class TestMainInterface:
    """Test main interface display"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_show_main_interface_student(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test show_main_interface for student user"""
        mock_user = Mock(username='student1')
        mock_user.to_dict.return_value = {'username': 'student1'}
        mock_auth = Mock()
        mock_auth.current_user = mock_user
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = mock_user
        mock_check_perm.return_value = False

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)
        gui.main_frame = ttk.Frame(parent)

        gui.show_main_interface()

        # Student should be redirected directly to student portal
        assert gui.student_portal is not None

        root.destroy()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_show_main_interface_admin(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test show_main_interface for admin user"""
        mock_user = Mock(username='admin')
        mock_user.to_dict.return_value = {'username': 'admin'}
        mock_auth = Mock()
        mock_auth.current_user = mock_user
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = mock_user
        mock_check_perm.return_value = True

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)
        gui.main_frame = ttk.Frame(parent)

        gui.show_main_interface()

        # Admin should see mode selection — main_frame should exist
        assert gui.main_frame is not None

        root.destroy()


class TestWindowClosing:
    """Test window closing methods"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.get_current_user')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.check_permission')
    def test_return_to_homepage(self, mock_check_perm, mock_get_user, mock_get_auth):
        """Test return_to_homepage method"""
        mock_auth = Mock()
        mock_auth.current_user = Mock(username='testuser')
        mock_get_auth.return_value = mock_auth
        mock_get_user.return_value = Mock()
        mock_check_perm.return_value = False

        root = tk.Tk()
        parent = ttk.Frame(root)
        gui = FinancialAidGUI(auth_instance=mock_auth, parent=parent)
        gui.main_frame = ttk.Frame(parent)

        # Should not raise exception
        gui.return_to_homepage()

        root.destroy()


class TestLaunchFunction:
    """Test launch_financial_aid_gui function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.FinancialAidGUI')
    def test_launch_financial_aid_gui_with_parent(self, mock_gui_class):
        """Test launch_financial_aid_gui with parent window"""
        root = tk.Tk()
        parent = ttk.Frame(root)
        auth_mock = Mock()

        launch_financial_aid_gui(parent=parent, auth=auth_mock)

        mock_gui_class.assert_called_once()

        root.destroy()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui.FinancialAidGUI')
    def test_launch_financial_aid_gui_standalone(self, mock_gui_class):
        """Test launch_financial_aid_gui without parent window"""
        auth_mock = Mock()

        # Mock the gui instance
        mock_instance = Mock()
        mock_gui_class.return_value = mock_instance

        launch_financial_aid_gui(parent=None, auth=auth_mock)

        mock_gui_class.assert_called_once()
        mock_instance.run.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
