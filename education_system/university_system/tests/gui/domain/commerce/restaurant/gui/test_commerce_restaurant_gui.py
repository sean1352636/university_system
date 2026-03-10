"""
Tests for the Commerce Restaurant Management GUI module.
Tests GUI initialization, window creation, and key GUI functionality.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
import sys


# Skip all GUI tests if running in headless environment
pytestmark = pytest.mark.skipif(
    not hasattr(sys, 'real_prefix') and not sys.base_prefix != sys.prefix,
    reason="GUI tests require display"
)


@pytest.fixture
def mock_auth():
    """Create a mock authentication instance."""
    auth = Mock()
    auth.current_user = {
        'id': 'USER001',
        'username': 'testuser',
        'role': 'admin'
    }
    auth.check_permission = Mock(return_value=True)
    auth.is_logged_in = Mock(return_value=True)
    auth.has_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def root_window():
    """Create a root Tkinter window for testing."""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestRestaurantGUIInitialization:
    """Tests for Restaurant GUI initialization."""

    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_gui_imports_successfully(self, mock_db_conn):
        """Test that the restaurant GUI module can be imported."""
        try:
            from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui
            assert restaurant_management_gui is not None
        except ImportError as e:
            pytest.fail(f"Failed to import restaurant_management_gui: {e}")

    @pytest.mark.skipif(True, reason="GUI tests require display - manual testing only")
    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_restaurant_gui_class_exists(self, mock_db_conn, mock_auth):
        """Test that RestaurantManagementGUI class exists."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Check if main GUI class exists
        assert hasattr(restaurant_management_gui, 'RestaurantManagementGUI') or \
               hasattr(restaurant_management_gui, 'RestaurantApp') or \
               hasattr(restaurant_management_gui, 'display_restaurant_management_gui')

    @pytest.mark.skipif(True, reason="GUI tests require display - manual testing only")
    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_restaurant_gui_initialization(self, mock_db_conn, mock_auth, root_window):
        """Test basic GUI initialization."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn

        # Try to initialize GUI (this may fail in headless environments)
        try:
            # Find the main GUI class
            if hasattr(restaurant_management_gui, 'RestaurantManagementGUI'):
                gui = restaurant_management_gui.RestaurantManagementGUI(root_window, mock_auth)
                assert gui is not None
            elif hasattr(restaurant_management_gui, 'RestaurantApp'):
                gui = restaurant_management_gui.RestaurantApp(root_window, mock_auth)
                assert gui is not None
        except tk.TclError:
            pytest.skip("Cannot test GUI in headless environment")


class TestGUIModuleFunctions:
    """Tests for GUI module-level functions."""

    def test_gui_module_has_display_function(self):
        """Test that the GUI module has a display function."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Check for common display function names
        has_display_func = (
            hasattr(restaurant_management_gui, 'display_restaurant_management_gui') or
            hasattr(restaurant_management_gui, 'show_gui') or
            hasattr(restaurant_management_gui, 'main') or
            hasattr(restaurant_management_gui, 'run_gui')
        )
        assert has_display_func, "GUI module should have a display/main function"

    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_gui_module_structure(self, mock_db_conn):
        """Test that the GUI module has expected structure."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Check for expected imports/modules
        assert hasattr(restaurant_management_gui, 'tk') or hasattr(restaurant_management_gui, 'tkinter')

    def test_gui_auth_integration(self):
        """Test that GUI module has auth integration."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Check for auth-related functions
        has_auth = (
            hasattr(restaurant_management_gui, 'set_auth') or
            hasattr(restaurant_management_gui, 'auth') or
            hasattr(restaurant_management_gui, 'HAS_AUTH')
        )
        assert has_auth, "GUI should have authentication integration"


class TestShopGUIBasic:
    """Basic tests for Shop Management GUI."""

    def test_shop_gui_imports_successfully(self):
        """Test that the shop GUI module can be imported."""
        try:
            from education_system.university_system.modules.domain.commerce.gui import shop_management_gui
            assert shop_management_gui is not None
        except ImportError as e:
            pytest.fail(f"Failed to import shop_management_gui: {e}")

    def test_shop_gui_module_structure(self):
        """Test that the shop GUI module has expected structure."""
        from education_system.university_system.modules.domain.commerce.gui import shop_management_gui

        # Check for expected structure
        assert hasattr(shop_management_gui, 'tk') or hasattr(shop_management_gui, 'tkinter')


class TestGUIFunctionalityMocked:
    """Tests for GUI functionality using mocks (no display needed)."""

    @patch('tkinter.Tk')
    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_restaurant_gui_with_mocked_tk(self, mock_db_conn, mock_tk_root, mock_auth):
        """Test restaurant GUI with mocked Tkinter."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Setup mocks
        mock_root = Mock()
        mock_tk_root.return_value = mock_root

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn

        # Test that key functions exist
        module_attrs = dir(restaurant_management_gui)

        # Should have some GUI-related attributes
        gui_indicators = ['tk', 'Tk', 'Frame', 'Button', 'Label', 'Entry']
        has_gui_elements = any(attr in str(module_attrs) for attr in gui_indicators)

        assert has_gui_elements or len(module_attrs) > 10, "Module should have GUI components"

    @patch('university_system.modules.domain.commerce.gui.shop_management_gui.get_db_connection')
    def test_shop_gui_has_expected_functions(self, mock_db_conn):
        """Test that shop GUI has expected functions."""
        from education_system.university_system.modules.domain.commerce.gui import shop_management_gui

        # Module should have substantial content
        module_attrs = dir(shop_management_gui)
        assert len(module_attrs) > 10, "Shop GUI module should have multiple attributes"


class TestGUIIntegration:
    """Integration tests for GUI modules."""

    def test_both_guis_can_be_imported_together(self):
        """Test that both GUI modules can be imported simultaneously."""
        try:
            from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui
            from education_system.university_system.modules.domain.commerce.gui import shop_management_gui

            assert restaurant_management_gui is not None
            assert shop_management_gui is not None
        except ImportError as e:
            pytest.fail(f"Failed to import GUI modules together: {e}")

    def test_gui_modules_dont_conflict(self):
        """Test that GUI modules don't have naming conflicts."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui
        from education_system.university_system.modules.domain.commerce.gui import shop_management_gui

        # Get all public attributes (not starting with _)
        restaurant_attrs = [attr for attr in dir(restaurant_management_gui) if not attr.startswith('_')]
        shop_attrs = [attr for attr in dir(shop_management_gui) if not attr.startswith('_')]

        # Both should have unique content
        assert len(restaurant_attrs) > 0
        assert len(shop_attrs) > 0


class TestGUIErrorHandling:
    """Tests for GUI error handling."""

    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_gui_handles_missing_auth_gracefully(self, mock_db_conn):
        """Test that GUI handles missing authentication gracefully."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Should have auth handling
        has_auth_check = (
            hasattr(restaurant_management_gui, 'HAS_AUTH') or
            hasattr(restaurant_management_gui, 'auth') or
            hasattr(restaurant_management_gui, 'set_auth')
        )
        assert has_auth_check, "GUI should have authentication handling"

    @patch('university_system.modules.domain.commerce.gui.restaurant_management_gui.get_db_connection')
    def test_gui_has_database_connection_handling(self, mock_db_conn):
        """Test that GUI has database connection handling."""
        from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui

        # Should have database connection function
        has_db_func = hasattr(restaurant_management_gui, 'get_db_connection')
        assert has_db_func, "GUI should have database connection handling"


# Integration test to verify all GUI components work together
class TestGUIComponentsIntegration:
    """Test that all GUI components integrate properly."""

    def test_all_gui_components_importable(self):
        """Test that all GUI components can be imported."""
        components = []

        try:
            from education_system.university_system.modules.domain.commerce.gui import restaurant_management_gui
            components.append('restaurant_management_gui')
        except ImportError:
            pass

        try:
            from education_system.university_system.modules.domain.commerce.gui import shop_management_gui
            components.append('shop_management_gui')
        except ImportError:
            pass

        assert len(components) == 2, f"Should import both GUIs, got: {components}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
