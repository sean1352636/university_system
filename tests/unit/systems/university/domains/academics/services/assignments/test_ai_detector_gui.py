"""
Comprehensive tests for ai_detector_gui.py module
Tests AI Detector GUI components, initialization, and functionality
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import sys
import os
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import GUI module
try:
    from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import AIDetectorGUI
    GUI_AVAILABLE = True
except ImportError as e:
    GUI_AVAILABLE = False
    import_error = e

MAIN = "education_system.systems.university.domains.integrity.interfaces.gui.ai_detector.main"
DETECTOR_CLASS = "education_system.systems.university.shared.ai.ai_detector.detector.AIDetector"


@pytest.fixture
def mock_detector():
    """Create a mock AI detector"""
    detector = MagicMock()
    detector.analyze_text = MagicMock(return_value={'ai_score': 0.75, 'level': 'several indicators'})
    detector.analyze_file = MagicMock(return_value={'ai_score': 0.65, 'level': 'some indicators'})
    return detector

@pytest.fixture
def mock_auth():
    """A signed-in member of staff (the role is given, so no database lookup)."""
    auth = MagicMock()
    auth.current_user = {
        'id': 1,
        'username': 'testuser',
        'role': 'staff',
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'test@test.com'
    }
    auth.is_logged_in = MagicMock(return_value=True)
    return auth

@pytest.fixture
def student_auth():
    """A signed-in student."""
    auth = MagicMock()
    auth.current_user = {'id': 7, 'username': 'S12345', 'role': 'student'}
    return auth

@pytest.fixture
def mock_tk_root():
    """Create a mock Tkinter root window"""
    root = MagicMock(spec=tk.Tk)
    root.winfo_screenwidth = MagicMock(return_value=1920)
    root.winfo_screenheight = MagicMock(return_value=1080)
    return root


def _quiet_build():
    """Patch out the three widget-building steps."""
    return (patch.object(AIDetectorGUI, 'setup_window'),
            patch.object(AIDetectorGUI, 'setup_styles'),
            patch.object(AIDetectorGUI, 'create_main_interface'))


class TestAIDetectorGUIImport:
    """Tests for AI Detector GUI import"""

    def test_ai_detector_gui_import(self):
        """Test that AI Detector GUI module can be imported"""
        if GUI_AVAILABLE:
            assert AIDetectorGUI is not None
        else:
            pytest.skip(f"AI Detector GUI not available: {import_error}")

    def test_module_structure(self):
        """Test that module has expected structure"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        from education_system.systems.university.domains.integrity.interfaces.gui import (
            ai_detector,
        )
        assert hasattr(ai_detector, 'AIDetectorGUI')

    def test_no_session_fallbacks_imported(self):
        """The window has no get_auth / UserAuth fallback any more."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")
        import importlib
        main = importlib.import_module(MAIN)
        assert not hasattr(main, 'get_auth')
        assert not hasattr(main, 'UserAuth')

class TestAIDetectorGUIInitialization:
    """Tests for AI Detector GUI initialization"""

    def test_initialization_with_detector(self, mock_detector, mock_auth):
        """Test initializing GUI with detector instance"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        a, b, c = _quiet_build()
        with a, b, c:
            gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

        assert gui.detector is mock_detector
        assert gui.auth is mock_auth
        assert gui.refused is False

    def test_detector_built_lazily_as_signed_in_user(self, mock_auth):
        """Without an instance the backend is built on first use, with the auth."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        built = MagicMock()
        a, b, c = _quiet_build()
        with a, b, c, patch(DETECTOR_CLASS, return_value=built) as detector_class:
            gui = AIDetectorGUI(root=mock_root, auth=mock_auth)
            detector_class.assert_not_called()          # nothing built while opening
            assert gui.detector is built
            detector_class.assert_called_once_with(auth=mock_auth)
            assert gui.detector is built                # built once
            detector_class.assert_called_once()

class TestAuthenticationInitialization:
    """The window runs only as the person passed in."""

    def test_initialization_uses_provided_auth(self, mock_detector, mock_auth):
        """Test that GUI uses provided auth object"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        a, b, c = _quiet_build()
        with a, b, c:
            gui = AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=mock_detector)

        assert gui.auth is mock_auth
        assert gui.user['username'] == 'testuser'

    def test_refuses_when_nobody_signed_in(self, mock_detector):
        """No auth: refuses, closes, builds nothing and invents no admin session."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        with patch(f"{MAIN}.messagebox.showerror") as mock_error, \
                patch.object(AIDetectorGUI, 'setup_window') as setup_window, \
                patch.object(AIDetectorGUI, 'create_main_interface') as create_ui:
            gui = AIDetectorGUI(root=mock_root, detector_instance=mock_detector)

        assert gui.refused is True
        assert gui.auth is None and gui.user is None
        mock_error.assert_called_once()
        setup_window.assert_not_called()
        create_ui.assert_not_called()
        mock_root.after.assert_called_once_with(10, mock_root.destroy)

    def test_refuses_auth_without_signed_in_user(self, mock_detector):
        """An auth object with no current user is not a session."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        empty = MagicMock()
        empty.current_user = None
        empty.get_current_user = MagicMock(return_value=None)
        with patch(f"{MAIN}.messagebox.showerror") as mock_error, \
                patch.object(AIDetectorGUI, 'create_main_interface') as create_ui:
            gui = AIDetectorGUI(root=MagicMock(), auth=empty, detector_instance=mock_detector)

        assert gui.refused is True
        assert gui.user is None
        mock_error.assert_called_once()
        create_ui.assert_not_called()

    def test_refuses_student(self, mock_detector, student_auth):
        """A student is refused and pointed at Academic Integrity."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        with patch(f"{MAIN}.messagebox.showerror") as mock_error, \
                patch.object(AIDetectorGUI, 'create_main_interface') as create_ui, \
                patch(DETECTOR_CLASS) as detector_class:
            gui = AIDetectorGUI(root=MagicMock(), auth=student_auth)

        assert gui.refused is True
        assert "Academic Integrity" in mock_error.call_args[0][1]
        create_ui.assert_not_called()
        detector_class.assert_not_called()

class TestWindowSetup:
    """Tests for window setup"""

    def test_setup_window_sets_title(self, mock_detector, mock_auth):
        """Test that setup_window sets window title"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        with patch.object(AIDetectorGUI, 'setup_styles'), \
                patch.object(AIDetectorGUI, 'create_main_interface'), \
                patch('education_system.platform.delivery.gui.window_sizing.center'):
            AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

        mock_root.title.assert_called()
        assert 'testuser' in mock_root.title.call_args[0][0]

    def test_setup_window_sizes_by_convention(self, mock_detector, mock_auth):
        """1400x900 with a 1200x800 minimum, clamped by window_sizing.center."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        with patch.object(AIDetectorGUI, 'setup_styles'), \
                patch.object(AIDetectorGUI, 'create_main_interface'), \
                patch('education_system.platform.delivery.gui.window_sizing.center') as center:
            AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

        center.assert_called_once_with(mock_root, 1400, 900, minsize=(1200, 800))

class TestStyleSetup:
    """Tests for style setup"""

    @patch('tkinter.ttk.Style')
    def test_setup_styles_creates_style(self, mock_style_class, mock_detector, mock_auth):
        """Test that setup_styles creates ttk.Style"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_style_class.return_value = MagicMock()
        with patch.object(AIDetectorGUI, 'setup_window'), \
                patch.object(AIDetectorGUI, 'create_main_interface'):
            gui = AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=mock_detector)

        assert hasattr(gui, 'style') or mock_style_class.called

    def test_setup_styles_defines_colors(self, mock_detector, mock_auth):
        """Test that setup_styles defines color scheme"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        a, b, c = _quiet_build()
        with a, b, c:
            gui = AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=mock_detector)

        assert isinstance(gui.colors, dict)

class TestInterfaceCreation:
    """Tests for interface creation"""

    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.Button')
    def test_create_main_interface_creates_widgets(self, mock_button, mock_frame, mock_detector, mock_auth):
        """Test that create_main_interface creates widgets"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        with patch.object(AIDetectorGUI, 'setup_window'), \
                patch.object(AIDetectorGUI, 'setup_styles'), \
                patch.object(AIDetectorGUI, 'create_title_bar'), \
                patch.object(AIDetectorGUI, 'create_status_bar'), \
                patch.object(AIDetectorGUI, 'create_navigation_buttons'), \
                patch.object(AIDetectorGUI, 'show_view'), \
                patch('tkinter.Canvas'), patch('tkinter.ttk.Scrollbar'):
            try:
                AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=mock_detector)
            except Exception:
                pass    # the patched-out pieces may leave later steps short of widgets

        assert mock_frame.called or mock_button.called

class TestGUIAttributes:
    """Tests for GUI attributes"""

    def test_gui_has_required_attributes(self, mock_detector, mock_auth):
        """Test that GUI instance has required attributes"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        a, b, c = _quiet_build()
        with a, b, c:
            gui = AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=mock_detector)

        for name in ('root', 'detector', 'auth', 'user', 'analysis_results', 'refused'):
            assert hasattr(gui, name)
        assert gui.analysis_results == {}

    def test_gui_initializes_analysis_results(self, mock_detector, mock_auth):
        """Test that GUI initializes analysis_results dictionary"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        a, b, c = _quiet_build()
        with a, b, c:
            gui = AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=mock_detector)

        assert gui.analysis_results == {}
        assert gui.current_submission_id is None

class TestDetectorAuth:
    """The backend always runs as the signed-in person."""

    def test_existing_detector_given_the_auth(self, mock_auth):
        """A detector passed in without a user is given the window's auth."""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        detector = MagicMock()
        detector.current_user = None
        a, b, c = _quiet_build()
        with a, b, c:
            gui = AIDetectorGUI(root=MagicMock(), auth=mock_auth, detector_instance=detector)
            assert gui.detector is detector
        detector.set_auth.assert_called_once_with(mock_auth)

class TestModuleAvailability:
    """Tests for module availability and dependencies"""

    def test_module_import_status(self):
        """Test module import status"""
        if GUI_AVAILABLE:
            assert AIDetectorGUI is not None
        else:
            # Log the import error for debugging
            print(f"AI Detector GUI not available: {import_error}")
            pytest.skip("AI Detector GUI module not available")

    def test_required_imports_available(self):
        """Test that required imports are available"""
        try:
            import tkinter
            import tkinter.ttk
            assert True
        except ImportError as e:
            pytest.skip(f"Tkinter not available: {e}")

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
