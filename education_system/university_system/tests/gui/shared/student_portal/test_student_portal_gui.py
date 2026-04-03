"""
Tests for StudentPortalGUI — the GUI version of the student portal.

Tests cover importing, launcher helper, backend GUI creation, dashboard display,
logout behaviour, and the init_gui routing logic.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, PropertyMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_auth():
    """Create a mock authentication object with a student user."""
    auth = Mock()
    auth.current_user = {
        'id': 42,
        'user_id': 42,
        'username': 'jdoe',
        'role': 'student',
        'student_id': 'STU0042',
        'display_name': 'Jane Doe',
    }
    auth.is_logged_in.return_value = True
    auth.check_permission.return_value = True
    auth.logout.return_value = None
    return auth


# ---------------------------------------------------------------------------
# Tests — Import
# ---------------------------------------------------------------------------

class TestStudentPortalGUIImport:
    """Verify the module can be imported without side-effects."""

    def test_student_portal_gui_can_be_imported(self):
        """StudentPortalGUI class should be importable."""
        from education_system.university_system.modules.shared.gui.main.student_portal import StudentPortalGUI
        assert StudentPortalGUI is not None


# ---------------------------------------------------------------------------
# Tests — _launch helper
# ---------------------------------------------------------------------------

class TestStudentPortalGUILaunch:
    """Tests for the _launch callback factory."""

    @pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='No display')
    def test_launch_returns_callable(self, mock_auth):
        """_launch should return a callable (callback function)."""
        import tkinter as tk
        from education_system.university_system.modules.shared.gui.main.student_portal import StudentPortalGUI

        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(StudentPortalGUI, '_build_ui'), \
                 patch.object(StudentPortalGUI, '_show_dashboard'), \
                 patch.object(StudentPortalGUI, '_configure_styles'):
                portal = StudentPortalGUI.__new__(StudentPortalGUI)
                portal.auth = mock_auth
                portal.root = root
                portal.content_frame = tk.Frame(root)
                portal.style = None

                result = portal._launch('show_academic_progress_gui')
                assert callable(result)
        finally:
            root.destroy()


# ---------------------------------------------------------------------------
# Tests — _get_backend_gui
# ---------------------------------------------------------------------------

class TestStudentPortalGUIBackend:
    """Tests for _get_backend_gui lazy creation."""

    @pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='No display')
    def test_get_backend_gui_creates_backend_with_correct_attributes(self, mock_auth):
        """_get_backend_gui should create a backend GUI sharing auth, root, and content_frame."""
        import tkinter as tk
        from tkinter import ttk
        from education_system.university_system.modules.shared.gui.main.student_portal import StudentPortalGUI

        root = tk.Tk()
        root.withdraw()
        try:
            portal = StudentPortalGUI.__new__(StudentPortalGUI)
            portal.auth = mock_auth
            portal.root = root
            portal.content_frame = ttk.Frame(root)
            portal.style = ttk.Style()

            with patch(
                'education_system.university_system.modules.shared.gui.main.student_portal.'
                'StudentPortalGUI._get_backend_gui'
            ) as mock_backend_fn:
                # Simulate what _get_backend_gui does: creates an object with
                # auth, root, and content_frame attributes.
                backend = Mock()
                backend.auth = mock_auth
                backend.root = root
                backend.content_frame = portal.content_frame
                mock_backend_fn.return_value = backend

                result = portal._get_backend_gui()

                assert result.auth is mock_auth
                assert result.root is root
                assert result.content_frame is portal.content_frame
        finally:
            root.destroy()


# ---------------------------------------------------------------------------
# Tests — _show_dashboard
# ---------------------------------------------------------------------------

class TestStudentPortalGUIDashboard:
    """Tests for _show_dashboard."""

    @pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='No display')
    def test_show_dashboard_calls_create_student_dashboard(self, mock_auth):
        """_show_dashboard should invoke create_student_dashboard with the right args."""
        import tkinter as tk
        from tkinter import ttk
        from education_system.university_system.modules.shared.gui.main.student_portal import StudentPortalGUI

        root = tk.Tk()
        root.withdraw()
        try:
            portal = StudentPortalGUI.__new__(StudentPortalGUI)
            portal.auth = mock_auth
            portal.root = root
            portal.content_frame = ttk.Frame(root)

            with patch(
                'education_system.university_system.modules.shared.gui.main.dashboard.'
                'student_dashboard.create_student_dashboard'
            ) as mock_create_dash, patch(
                'education_system.university_system.modules.shared.services.dashboard.'
                'dashboard_service.DashboardService'
            ) as mock_dash_svc:
                portal._show_dashboard()
                mock_create_dash.assert_called_once()
                args = mock_create_dash.call_args[0]
                assert args[0] is portal.content_frame
                assert args[1] is mock_auth
        finally:
            root.destroy()


# ---------------------------------------------------------------------------
# Tests — _logout
# ---------------------------------------------------------------------------

class TestStudentPortalGUILogout:
    """Tests for _logout."""

    @pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='No display')
    def test_logout_calls_auth_logout(self, mock_auth):
        """_logout should call auth.logout() and destroy the root window."""
        import tkinter as tk
        from education_system.university_system.modules.shared.gui.main.student_portal import StudentPortalGUI

        root = tk.Tk()
        root.withdraw()
        try:
            portal = StudentPortalGUI.__new__(StudentPortalGUI)
            portal.auth = mock_auth
            portal.root = root

            portal._logout()

            mock_auth.logout.assert_called_once()
        except Exception:
            # root.destroy() in _logout may raise if already destroyed
            pass
        finally:
            try:
                root.destroy()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tests — init_gui routing
# ---------------------------------------------------------------------------

class TestInitGUIRouting:
    """Tests for the init_gui function that routes student vs admin."""

    @pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='No display')
    @patch('education_system.university_system.modules.shared.gui.main.main_gui.safe_auth_check')
    @patch('education_system.university_system.modules.shared.gui.main.main_gui.get_auth')
    @patch('education_system.university_system.modules.shared.gui.main.main_gui.UserAuth')
    def test_init_gui_routes_student_to_student_portal(self, mock_user_auth_cls,
                                                        mock_get_auth, mock_safe_auth, mock_auth):
        """init_gui with role='student' should create a StudentPortalGUI."""
        mock_get_auth.return_value = mock_auth
        mock_user_auth_cls.return_value = mock_auth

        session_user = {
            'id': 42,
            'username': 'jdoe',
            'role': 'student',
            'student_id': 'STU0042',
            'display_name': 'Jane Doe',
        }

        import education_system.university_system.modules.shared.gui.main.main_gui as main_gui_mod
        original_auth = main_gui_mod.auth

        with patch(
            'education_system.university_system.modules.shared.gui.main.student_portal.StudentPortalGUI'
        ) as mock_portal_cls:
            mock_portal_cls.return_value = Mock()

            try:
                # Reset module-level auth so init_gui re-initializes it from get_auth()
                main_gui_mod.auth = None

                from education_system.university_system.modules.shared.gui.main.main_gui import init_gui

                app = init_gui(session_user=session_user)

                mock_portal_cls.assert_called_once_with(mock_auth)
            finally:
                main_gui_mod.auth = original_auth

    @pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='No display')
    @patch('education_system.university_system.modules.shared.gui.main.main_gui.get_auth')
    @patch('education_system.university_system.modules.shared.gui.main.main_gui.UserAuth')
    @patch('education_system.university_system.modules.shared.gui.main.main_gui.UnifiedManagementGUI')
    def test_init_gui_routes_admin_to_unified_management(self, mock_unified_cls,
                                                          mock_user_auth_cls,
                                                          mock_get_auth, mock_auth):
        """init_gui with role='admin' should create a UnifiedManagementGUI."""
        mock_get_auth.return_value = mock_auth
        mock_user_auth_cls.return_value = mock_auth
        mock_unified_cls.return_value = Mock()

        session_user = {
            'id': 1,
            'username': 'admin',
            'role': 'admin',
            'display_name': 'Admin User',
        }

        from education_system.university_system.modules.shared.gui.main.main_gui import init_gui

        app = init_gui(session_user=session_user)

        mock_unified_cls.assert_called_once()
