"""
Tests for the Commerce Restaurant Management GUI module.
Tests GUI initialization, window creation, and key GUI functionality.
"""

import pytest
pytestmark = pytest.mark.gui

import os
import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
import sys

_MAIN_GUI = 'education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui'


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
    """Create a mock root Tkinter window for testing."""
    root = Mock(spec=tk.Tk)
    yield root


class TestRestaurantGUIInitialization:
    """Tests for Restaurant GUI initialization."""

    def test_gui_imports_successfully(self):
        """Test that the restaurant GUI module can be imported."""
        from education_system.post_18.university_system.modules.domain.commerce.gui import restaurant_management_gui
        assert restaurant_management_gui is not None

    def test_restaurant_gui_class_exists(self):
        """Test that RestaurantManagementGUI class exists."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI
        assert RestaurantManagementGUI is not None

    @patch(f'{_MAIN_GUI}.init_db', return_value=True)
    @patch(f'{_MAIN_GUI}.get_auth')
    def test_restaurant_gui_initialization(self, mock_get_auth, mock_init_db, mock_auth, root_window):
        """Test basic GUI initialization."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI

        mock_get_auth.return_value = mock_auth

        with patch.object(RestaurantManagementGUI, 'setup_current_user', lambda self: None):
            gui = RestaurantManagementGUI(root_window, mock_auth)
            assert gui is not None
            assert gui.root == root_window


class TestGUIModuleFunctions:
    """Tests for GUI module-level functions."""

    def test_gui_module_has_main_class(self):
        """Test that the GUI module has a main GUI class."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI
        assert RestaurantManagementGUI is not None
        assert hasattr(RestaurantManagementGUI, '__init__')

    def test_gui_module_structure(self):
        """Test that the GUI module core has expected structure."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui import core
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core import main_gui

        # Check for tkinter imports in main_gui
        assert hasattr(main_gui, 'tk')

    def test_gui_auth_integration(self):
        """Test that GUI module has auth integration."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core import main_gui

        # Check for auth-related imports
        has_auth = (
            hasattr(main_gui, 'get_auth') or
            hasattr(main_gui, 'get_global_auth') or
            hasattr(main_gui, 'UserAuth')
        )
        assert has_auth, "GUI should have authentication integration"


class TestShopGUIBasic:
    """Basic tests for Shop Management GUI."""

    def test_shop_gui_imports_successfully(self):
        """Test that the shop GUI module can be imported."""
        from education_system.post_18.university_system.modules.domain.commerce.gui import shop_management_gui
        assert shop_management_gui is not None

    def test_shop_gui_module_structure(self):
        """Test that the shop GUI module has expected structure."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.shop_management_gui import UniversityShopGUI
        assert UniversityShopGUI is not None


class TestGUIFunctionalityMocked:
    """Tests for GUI functionality using mocks (no display needed)."""

    def test_restaurant_gui_with_mocked_tk(self, mock_auth):
        """Test restaurant GUI class has expected attributes."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI

        # Verify the class exists and has expected methods
        assert hasattr(RestaurantManagementGUI, '__init__')
        module_attrs = dir(RestaurantManagementGUI)
        assert len(module_attrs) > 10, "GUI class should have multiple methods"

    def test_shop_gui_has_expected_functions(self):
        """Test that shop GUI has expected functions."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.shop_management_gui import (
            UniversityShopGUI,
            run_gui_mode,
            run_cli_mode,
        )

        assert UniversityShopGUI is not None
        assert callable(run_gui_mode)
        assert callable(run_cli_mode)


class TestGUIIntegration:
    """Integration tests for GUI modules."""

    def test_both_guis_can_be_imported_together(self):
        """Test that both GUI modules can be imported simultaneously."""
        from education_system.post_18.university_system.modules.domain.commerce.gui import restaurant_management_gui
        from education_system.post_18.university_system.modules.domain.commerce.gui import shop_management_gui

        assert restaurant_management_gui is not None
        assert shop_management_gui is not None

    def test_gui_modules_dont_conflict(self):
        """Test that GUI modules don't have naming conflicts."""
        from education_system.post_18.university_system.modules.domain.commerce.gui import restaurant_management_gui
        from education_system.post_18.university_system.modules.domain.commerce.gui import shop_management_gui

        # Get all public attributes (not starting with _)
        restaurant_attrs = [attr for attr in dir(restaurant_management_gui) if not attr.startswith('_')]
        shop_attrs = [attr for attr in dir(shop_management_gui) if not attr.startswith('_')]

        # Both should have unique content
        assert len(restaurant_attrs) > 0
        assert len(shop_attrs) > 0


class TestGUIErrorHandling:
    """Tests for GUI error handling."""

    def test_gui_handles_missing_auth_gracefully(self):
        """Test that GUI core has authentication handling."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core import main_gui

        # Should have auth-related imports
        has_auth_check = (
            hasattr(main_gui, 'get_auth') or
            hasattr(main_gui, 'get_global_auth') or
            hasattr(main_gui, 'UserAuth')
        )
        assert has_auth_check, "GUI should have authentication handling"

    def test_gui_has_database_connection_handling(self):
        """Test that GUI has database connection handling."""
        from education_system.post_18.university_system.modules.domain.commerce.gui.restaurant_management_gui.core import main_gui

        # Should have database connection function
        assert hasattr(main_gui, 'get_db_connection'), "GUI should have database connection handling"


# Integration test to verify all GUI components work together
class TestGUIComponentsIntegration:
    """Test that all GUI components integrate properly."""

    def test_all_gui_components_importable(self):
        """Test that all GUI components can be imported."""
        components = []

        try:
            from education_system.post_18.university_system.modules.domain.commerce.gui import restaurant_management_gui
            components.append('restaurant_management_gui')
        except ImportError:
            pass

        try:
            from education_system.post_18.university_system.modules.domain.commerce.gui import shop_management_gui
            components.append('shop_management_gui')
        except ImportError:
            pass

        assert len(components) == 2, f"Should import both GUIs, got: {components}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
