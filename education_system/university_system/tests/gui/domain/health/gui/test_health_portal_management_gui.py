"""
Comprehensive test suite for health portal management GUI.
Tests all functionality in university_system/modules/domain/health/gui/health_portal_management_gui.py
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile
import threading

from education_system.university_system.modules.domain.health.gui.health_portal_management_gui import HealthPortalManagementGUI
from education_system.university_system.infrastructure.auth import UserAuth

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock(spec=UserAuth)
    auth.current_user = {
        'id': 'admin1',
        'username': 'admin',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    return auth

@pytest.fixture
def root_window():
    """Create a Tk root window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except (OSError, IOError):
        pass

@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal students table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT
    )
    ''')

    cursor.execute("INSERT INTO students VALUES ('S001', 'Test', 'Student')")
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

class TestHealthPortalManagementGUIInit:
    """Test HealthPortalManagementGUI initialization"""

    def test_init_with_auth(self, root_window, mock_auth):
        """Test initialization with authentication"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        assert gui.root == root_window
        assert gui.auth == mock_auth

    def test_init_without_theme_manager(self, root_window, mock_auth):
        """Test initialization when theme manager is not available"""
        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.get_theme_manager', side_effect=ImportError):
            gui = HealthPortalManagementGUI(root_window, mock_auth)

            assert gui.theme_manager is None

    def test_init_with_theme_manager(self, root_window, mock_auth):
        """Test initialization with theme manager"""
        mock_theme_manager = Mock()

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.get_theme_manager', return_value=mock_theme_manager):
            gui = HealthPortalManagementGUI(root_window, mock_auth)

            assert gui.theme_manager == mock_theme_manager
            mock_theme_manager.register_observer.assert_called_once()

class TestOpenHealthPortalGUI:
    """Test opening the health portal GUI"""

    @patch('university_system.modules.domain.health.gui.health_portal_management_gui.tk.Toplevel')
    @patch('university_system.modules.domain.health.gui.health_portal_management_gui._HealthPortalGUI')
    def test_open_health_portal_gui_success(self, mock_health_portal_gui, mock_toplevel, root_window, mock_auth):
        """Test successfully opening health portal GUI"""
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', True):
            gui = HealthPortalManagementGUI(root_window, mock_auth)
            gui.open_health_portal_gui()

            # Verify window was created
            mock_toplevel.assert_called_once_with(root_window)
            mock_window.title.assert_called_with("University Health Portal")
            mock_window.geometry.assert_called_with("1400x900")

            # Verify HealthPortalGUI was instantiated
            mock_health_portal_gui.assert_called_once()

    @patch('university_system.modules.domain.health.gui.health_portal_management_gui.messagebox')
    def test_open_health_portal_gui_not_available(self, mock_messagebox, root_window, mock_auth):
        """Test opening when health portal GUI is not available"""
        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', False):
            with patch('university_system.modules.domain.health.gui.health_portal_management_gui._HEALTH_PORTAL_GUI_IMPORT_ERROR', 'Module not found'):
                gui = HealthPortalManagementGUI(root_window, mock_auth)
                gui.open_health_portal_gui()

                # Should show error message
                mock_messagebox.showerror.assert_called_once()
                assert 'Health Portal' in str(mock_messagebox.showerror.call_args)

    @patch('university_system.modules.domain.health.gui.health_portal_management_gui.tk.Toplevel')
    @patch('university_system.modules.domain.health.gui.health_portal_management_gui._HealthPortalGUI')
    def test_open_with_theme_manager(self, mock_health_portal_gui, mock_toplevel, root_window, mock_auth):
        """Test opening portal with theme manager applies theme"""
        mock_window = Mock()
        mock_toplevel.return_value = mock_window
        mock_theme_manager = Mock()

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', True):
            with patch('university_system.modules.domain.health.gui.health_portal_management_gui.get_theme_manager', return_value=mock_theme_manager):
                gui = HealthPortalManagementGUI(root_window, mock_auth)
                gui.open_health_portal_gui()

                # Verify theme was applied
                mock_theme_manager.apply_theme_to_window.assert_called_with(mock_window)

class TestCreateHealthTab:
    """Test creating health monitoring tab"""

    def test_create_health_tab(self, root_window, mock_auth):
        """Test creating health tab with checks"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        # Create a parent frame
        parent = tk.Frame(root_window)

        gui.create_health_tab(parent)

        # Verify the tab was created (children exist)
        assert len(parent.winfo_children()) > 0

    def test_health_checks_run_in_background(self, root_window, mock_auth):
        """Test health checks run in background threads"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        # Create a parent frame
        parent = tk.Frame(root_window)

        # Mock threading to verify threads are created
        with patch('threading.Thread') as mock_thread:
            gui.create_health_tab(parent)

            # Verify threads were created for health checks
            assert mock_thread.call_count >= 4  # At least 4 health checks

class TestHealthChecks:
    """Test individual health check methods"""

    def test_check_database_success(self, root_window, mock_auth, temp_db):
        """Test database check succeeds with valid database"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.DB_PATH', temp_db):
            result = gui._check_database()

            assert result is True

    def test_check_database_failure_missing_file(self, root_window, mock_auth):
        """Test database check fails with missing database"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.DB_PATH', '/nonexistent/path.db'):
            result = gui._check_database()

            assert result is False

    def test_check_database_no_path(self, root_window, mock_auth):
        """Test database check fails when DB_PATH is None"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.DB_PATH', None):
            result = gui._check_database()

            assert result is False

    def test_check_auth_success(self, root_window, mock_auth):
        """Test auth check succeeds with valid auth"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        result = gui._check_auth()

        assert result is True

    def test_check_auth_failure(self, root_window):
        """Test auth check fails with None auth"""
        gui = HealthPortalManagementGUI(root_window, None)

        result = gui._check_auth()

        assert result is False

    def test_check_filesystem_success(self, root_window, mock_auth):
        """Test filesystem check succeeds"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        result = gui._check_filesystem()

        # Should succeed on normal filesystem
        assert result is True

    def test_check_gui_components_available(self, root_window, mock_auth):
        """Test GUI components check when portal GUI is available"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', True):
            result = gui._check_gui_components()

            assert result is True

    def test_check_gui_components_not_available(self, root_window, mock_auth):
        """Test GUI components check when portal GUI is not available"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', False):
            result = gui._check_gui_components()

            assert result is False

class TestThemeSupport:
    """Test theme manager support"""

    def test_on_theme_changed_with_theme_manager(self, root_window, mock_auth):
        """Test theme change handler with theme manager"""
        mock_theme_manager = Mock()

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.get_theme_manager', return_value=mock_theme_manager):
            gui = HealthPortalManagementGUI(root_window, mock_auth)

            # Call theme change handler
            gui.on_theme_changed()

            # Should not crash
            assert gui.theme_manager is not None

    def test_on_theme_changed_without_theme_manager(self, root_window, mock_auth):
        """Test theme change handler without theme manager"""
        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.get_theme_manager', side_effect=Exception):
            gui = HealthPortalManagementGUI(root_window, mock_auth)

            # Call theme change handler
            gui.on_theme_changed()

            # Should not crash even without theme manager
            assert gui.theme_manager is None

class TestErrorHandling:
    """Test error handling scenarios"""

    @patch('university_system.modules.domain.health.gui.health_portal_management_gui.messagebox')
    def test_open_health_portal_gui_exception(self, mock_messagebox, root_window, mock_auth):
        """Test error handling when opening portal fails"""
        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', True):
            with patch('university_system.modules.domain.health.gui.health_portal_management_gui.tk.Toplevel', side_effect=Exception("Test error")):
                gui = HealthPortalManagementGUI(root_window, mock_auth)
                gui.open_health_portal_gui()

                # Should show error message
                mock_messagebox.showerror.assert_called_once()

    def test_check_database_exception_handling(self, root_window, mock_auth):
        """Test database check handles exceptions gracefully"""
        gui = HealthPortalManagementGUI(root_window, mock_auth)

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.sqlite3.connect', side_effect=Exception("DB Error")):
            result = gui._check_database()

            # Should return False on exception
            assert result is False

class TestIntegration:
    """Integration tests for complete workflows"""

    @patch('university_system.modules.domain.health.gui.health_portal_management_gui.tk.Toplevel')
    @patch('university_system.modules.domain.health.gui.health_portal_management_gui._HealthPortalGUI')
    def test_complete_workflow_with_theme(self, mock_health_portal_gui, mock_toplevel, root_window, mock_auth, temp_db):
        """Test complete workflow with theme support and database"""
        mock_window = Mock()
        mock_toplevel.return_value = mock_window
        mock_theme_manager = Mock()

        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', True):
            with patch('university_system.modules.domain.health.gui.health_portal_management_gui.get_theme_manager', return_value=mock_theme_manager):
                with patch('university_system.modules.domain.health.gui.health_portal_management_gui.DB_PATH', temp_db):
                    # Create GUI
                    gui = HealthPortalManagementGUI(root_window, mock_auth)

                    # Verify health checks pass
                    assert gui._check_database() is True
                    assert gui._check_auth() is True
                    assert gui._check_filesystem() is True

                    # Open health portal
                    gui.open_health_portal_gui()

                    # Verify all steps completed
                    mock_toplevel.assert_called_once()
                    mock_theme_manager.apply_theme_to_window.assert_called()
                    mock_health_portal_gui.assert_called_once()

    def test_health_tab_with_all_checks(self, root_window, mock_auth, temp_db):
        """Test health tab creation with all checks"""
        with patch('university_system.modules.domain.health.gui.health_portal_management_gui.DB_PATH', temp_db):
            with patch('university_system.modules.domain.health.gui.health_portal_management_gui.HEALTH_PORTAL_GUI_AVAILABLE', True):
                gui = HealthPortalManagementGUI(root_window, mock_auth)

                # Create parent frame
                parent = tk.Frame(root_window)

                # Create health tab
                gui.create_health_tab(parent)

                # Verify tab was created
                assert len(parent.winfo_children()) > 0

                # Give threads time to execute (brief wait)
                import time
                time.sleep(0.1)

                # All checks should pass
                assert gui._check_database() is True
                assert gui._check_auth() is True
                assert gui._check_filesystem() is True
                assert gui._check_gui_components() is True

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
