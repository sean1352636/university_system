"""
Comprehensive tests for ai_detector_gui.py module
Tests AI Detector GUI components, initialization, and functionality
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import sys
import os
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import GUI module
try:
    from education_system.university_system.modules.domain.academics.gui.ai_detector import AIDetectorGUI
    GUI_AVAILABLE = True
except ImportError as e:
    GUI_AVAILABLE = False
    import_error = e

@pytest.fixture
def mock_detector():
    """Create a mock AI detector"""
    detector = MagicMock()
    detector.analyze_text = MagicMock(return_value={'ai_probability': 0.75, 'analysis': 'Test result'})
    detector.analyze_file = MagicMock(return_value={'ai_probability': 0.65, 'analysis': 'File result'})
    return detector

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = MagicMock()
    auth.current_user = {
        'id': 1,
        'username': 'testuser',
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'test@test.com'
    }
    auth.is_logged_in = MagicMock(return_value=True)
    return auth

@pytest.fixture
def mock_tk_root():
    """Create a mock Tkinter root window"""
    root = MagicMock(spec=tk.Tk)
    root.winfo_screenwidth = MagicMock(return_value=1920)
    root.winfo_screenheight = MagicMock(return_value=1080)
    return root

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

        from education_system.university_system.modules.domain.academics.gui import ai_detector
        assert hasattr(ai_detector, 'AIDetectorGUI')

class TestAIDetectorGUIInitialization:
    """Tests for AI Detector GUI initialization"""

    @patch('tkinter.Tk')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.get_auth')
    def test_initialization_with_detector(self, mock_get_auth, mock_tk_class, mock_detector, mock_auth):
        """Test initializing GUI with detector instance"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_get_auth.return_value = mock_auth
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Patch the setup methods to avoid GUI creation
        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'setup_styles'):
                with patch.object(AIDetectorGUI, 'create_main_interface'):
                    gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                    assert gui.detector is mock_detector
                    assert gui.auth is mock_auth

    @patch('tkinter.Tk')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.get_auth')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.AIDetector')
    def test_initialization_without_detector(self, mock_ai_detector_class, mock_get_auth, mock_tk_class, mock_auth):
        """Test initializing GUI without detector instance"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_get_auth.return_value = mock_auth
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_detector = MagicMock()
        mock_ai_detector_class.return_value = mock_detector

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'setup_styles'):
                with patch.object(AIDetectorGUI, 'create_main_interface'):
                    gui = AIDetectorGUI(root=mock_root, auth=mock_auth)

                    assert gui.detector is mock_detector
                    mock_ai_detector_class.assert_called_once()

    @patch('tkinter.Tk')
    @patch('tkinter.messagebox.showerror')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.AIDetector', None)
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.get_auth')
    def test_initialization_without_ai_detector_backend(self, mock_get_auth, mock_error, mock_tk_class, mock_auth):
        """Test that initialization fails gracefully without AI Detector backend"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_get_auth.return_value = mock_auth
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with pytest.raises(RuntimeError):
            gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=None)

class TestAuthenticationInitialization:
    """Tests for authentication initialization"""

    @patch('tkinter.Tk')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.get_auth')
    def test_initialization_uses_provided_auth(self, mock_get_auth, mock_tk_class, mock_detector, mock_auth):
        """Test that GUI uses provided auth object"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'setup_styles'):
                with patch.object(AIDetectorGUI, 'create_main_interface'):
                    gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                    assert gui.auth is mock_auth

    @patch('tkinter.Tk')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.get_auth')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.UserAuth')
    def test_initialization_creates_auth_if_not_provided(self, mock_user_auth_class, mock_get_auth, mock_tk_class, mock_detector):
        """Test that GUI creates auth if not provided"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_get_auth.return_value = None  # No centralized auth
        mock_auth = MagicMock()
        mock_auth.current_user = None
        mock_user_auth_class.return_value = mock_auth

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch('sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1, 'admin', 'Admin', 'User', 'admin@test.com')
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            with patch.object(AIDetectorGUI, 'setup_window'):
                with patch.object(AIDetectorGUI, 'setup_styles'):
                    with patch.object(AIDetectorGUI, 'create_main_interface'):
                        gui = AIDetectorGUI(root=mock_root, detector_instance=mock_detector)

                        assert gui.auth is not None

class TestWindowSetup:
    """Tests for window setup"""

    @patch('tkinter.Tk')
    def test_setup_window_sets_title(self, mock_tk_class, mock_detector, mock_auth):
        """Test that setup_window sets window title"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_styles'):
            with patch.object(AIDetectorGUI, 'create_main_interface'):
                gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                # Window title should be set
                mock_root.title.assert_called()

    @patch('tkinter.Tk')
    def test_setup_window_sets_geometry(self, mock_tk_class, mock_detector, mock_auth):
        """Test that setup_window sets window geometry"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_styles'):
            with patch.object(AIDetectorGUI, 'create_main_interface'):
                gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                # Geometry should be set
                assert mock_root.geometry.called

class TestStyleSetup:
    """Tests for style setup"""

    @patch('tkinter.Tk')
    @patch('tkinter.ttk.Style')
    def test_setup_styles_creates_style(self, mock_style_class, mock_tk_class, mock_detector, mock_auth):
        """Test that setup_styles creates ttk.Style"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_style = MagicMock()
        mock_style_class.return_value = mock_style

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'create_main_interface'):
                gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                # Style should be created
                assert hasattr(gui, 'style') or mock_style_class.called

    @patch('tkinter.Tk')
    def test_setup_styles_defines_colors(self, mock_tk_class, mock_detector, mock_auth):
        """Test that setup_styles defines color scheme"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'create_main_interface'):
                gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                # Colors should be defined
                assert hasattr(gui, 'colors')
                assert isinstance(gui.colors, dict)

class TestInterfaceCreation:
    """Tests for interface creation"""

    @patch('tkinter.Tk')
    @patch('tkinter.ttk.Frame')
    @patch('tkinter.ttk.Button')
    def test_create_main_interface_creates_widgets(self, mock_button, mock_frame, mock_tk_class, mock_detector, mock_auth):
        """Test that create_main_interface creates widgets"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'setup_styles'):
                gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                # Widgets should be created
                assert mock_frame.called or mock_button.called

class TestGUIAttributes:
    """Tests for GUI attributes"""

    @patch('tkinter.Tk')
    def test_gui_has_required_attributes(self, mock_tk_class, mock_detector, mock_auth):
        """Test that GUI instance has required attributes"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'setup_styles'):
                with patch.object(AIDetectorGUI, 'create_main_interface'):
                    gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                    # Check required attributes
                    assert hasattr(gui, 'root')
                    assert hasattr(gui, 'detector')
                    assert hasattr(gui, 'auth')
                    assert hasattr(gui, 'analysis_results')
                    assert gui.analysis_results == {}

    @patch('tkinter.Tk')
    def test_gui_initializes_analysis_results(self, mock_tk_class, mock_detector, mock_auth):
        """Test that GUI initializes analysis_results dictionary"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch.object(AIDetectorGUI, 'setup_window'):
            with patch.object(AIDetectorGUI, 'setup_styles'):
                with patch.object(AIDetectorGUI, 'create_main_interface'):
                    gui = AIDetectorGUI(root=mock_root, auth=mock_auth, detector_instance=mock_detector)

                    assert gui.analysis_results == {}
                    assert gui.current_submission_id is None

class TestErrorHandling:
    """Tests for error handling"""

    @patch('tkinter.Tk')
    @patch('tkinter.messagebox.showerror')
    def test_initialization_shows_error_when_detector_unavailable(self, mock_error, mock_tk_class, mock_auth):
        """Test that error message is shown when detector is unavailable"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Temporarily set AIDetector to None
        with patch('university_system.modules.domain.academics.gui.ai_detector_gui.AIDetector', None):
            with pytest.raises(RuntimeError):
                gui = AIDetectorGUI(root=mock_root, auth=mock_auth)

            # Error dialog should have been shown
            mock_error.assert_called_once()

class TestFallbackAuthentication:
    """Tests for fallback authentication"""

    @patch('tkinter.Tk')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.get_auth')
    @patch('university_system.modules.domain.academics.gui.ai_detector_gui.UserAuth')
    def test_creates_default_admin_user_on_db_error(self, mock_user_auth_class, mock_get_auth, mock_tk_class, mock_detector):
        """Test that default admin user is created when DB access fails"""
        if not GUI_AVAILABLE:
            pytest.skip("GUI module not available")

        mock_get_auth.return_value = None
        mock_auth = MagicMock()
        mock_auth.current_user = None
        mock_user_auth_class.return_value = mock_auth

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        with patch('sqlite3.connect', side_effect=Exception("DB Error")):
            with patch.object(AIDetectorGUI, 'setup_window'):
                with patch.object(AIDetectorGUI, 'setup_styles'):
                    with patch.object(AIDetectorGUI, 'create_main_interface'):
                        gui = AIDetectorGUI(root=mock_root, detector_instance=mock_detector)

                        # Should fall back to default admin user
                        assert gui.auth.current_user is not None
                        assert gui.auth.current_user['id'] == 1
                        assert gui.auth.current_user['username'] == 'admin'

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
