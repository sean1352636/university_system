"""
Comprehensive test suite for feature_factory.py

Tests all functionality in university_system/modules/shared/utils/feature_factory.py including:
- create_cli_menu factory function
- create_gui_launcher factory function
- Menu generation and display
- GUI window creation
- User interaction handling
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO
import sys


class TestFeatureFactoryImports:
    """Test feature_factory module imports"""

    def test_module_imports_successfully(self):
        """Test that feature_factory module can be imported"""
        try:
            from university_system.modules.shared.utils import feature_factory
            assert feature_factory is not None
        except ImportError as e:
            pytest.fail(f"Failed to import feature_factory: {e}")

    def test_all_exports_defined(self):
        """Test that __all__ is properly defined"""
        from university_system.modules.shared.utils import feature_factory

        assert hasattr(feature_factory, '__all__')
        assert isinstance(feature_factory.__all__, list)
        assert 'create_cli_menu' in feature_factory.__all__
        assert 'create_gui_launcher' in feature_factory.__all__


class TestCreateCLIMenu:
    """Test create_cli_menu factory function"""

    def test_create_cli_menu_exists(self):
        """Test that create_cli_menu function exists"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        assert callable(create_cli_menu)

    def test_create_cli_menu_returns_callable(self):
        """Test that create_cli_menu returns a callable function"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {
            "Feature 1": "Description 1",
            "Feature 2": "Description 2",
            "Return": "Exit"
        }

        menu_func = create_cli_menu(title, features)

        assert callable(menu_func)

    def test_create_cli_menu_with_instruction(self):
        """Test creating CLI menu with instruction"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {"Feature 1": "Description", "Return": "Exit"}
        instruction = "Use this menu to access features"

        menu_func = create_cli_menu(title, features, cli_instruction=instruction)

        assert callable(menu_func)

    def test_menu_function_accepts_auth_parameter(self):
        """Test that generated menu function accepts auth parameter"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {"Feature 1": "Description", "Return": "Exit"}

        menu_func = create_cli_menu(title, features)

        # Mock auth object
        mock_auth = Mock()

        # Should be able to call with auth parameter
        with patch('builtins.input', side_effect=['3', KeyboardInterrupt]), \
             patch('builtins.print'):
            try:
                menu_func(mock_auth)
            except KeyboardInterrupt:
                pass  # Expected

    def test_menu_displays_title(self):
        """Test that menu displays the title correctly"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu System"
        features = {"Feature 1": "Description", "Return": "Exit"}

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', side_effect=['2']), \
             patch('builtins.print') as mock_print:

            menu_func(Mock())

            # Check that title was printed (in uppercase)
            printed_output = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            assert 'TEST MENU SYSTEM' in printed_output

    def test_menu_displays_features(self):
        """Test that menu displays all features"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {
            "Feature 1": "Description 1",
            "Feature 2": "Description 2",
            "Return": "Exit"
        }

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', side_effect=['3']), \
             patch('builtins.print') as mock_print:

            menu_func(Mock())

            printed_output = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            assert 'Feature 1' in printed_output or '1.' in printed_output
            assert 'Feature 2' in printed_output or '2.' in printed_output

    def test_menu_handles_valid_choice(self):
        """Test that menu handles valid feature selection"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {
            "Feature 1": "Description 1",
            "Feature 2": "Description 2",
            "Return": "Exit"
        }

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', side_effect=['1', '3']), \
             patch('builtins.print') as mock_print:

            menu_func(Mock())

            printed_output = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            assert 'Feature 1' in printed_output or 'Description 1' in printed_output

    def test_menu_handles_return_option(self):
        """Test that menu exits when return option is selected"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {
            "Feature 1": "Description 1",
            "Return": "Exit"
        }

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', return_value='2'), \
             patch('builtins.print'):

            # Should exit cleanly when last option (return) is selected
            menu_func(Mock())

    def test_menu_handles_invalid_choice(self):
        """Test that menu handles invalid input"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {"Feature 1": "Description", "Return": "Exit"}

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', side_effect=['99', '2']), \
             patch('builtins.print') as mock_print:

            menu_func(Mock())

            printed_output = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            assert 'Invalid' in printed_output or 'invalid' in printed_output

    def test_menu_handles_keyboard_interrupt(self):
        """Test that menu handles keyboard interrupt gracefully"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {"Feature 1": "Description", "Return": "Exit"}

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', side_effect=KeyboardInterrupt), \
             patch('builtins.print'):

            # Should exit gracefully
            menu_func(Mock())

    def test_menu_handles_exception(self):
        """Test that menu handles exceptions gracefully"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {"Feature 1": "Description", "Return": "Exit"}

        menu_func = create_cli_menu(title, features)

        with patch('builtins.input', side_effect=[Exception("Test error"), '2']), \
             patch('builtins.print') as mock_print:

            menu_func(Mock())

            printed_output = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            assert 'Error' in printed_output or 'error' in printed_output

    def test_menu_displays_cli_instruction(self):
        """Test that menu displays CLI instruction when provided"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        title = "Test Menu"
        features = {"Feature 1": "Description", "Return": "Exit"}
        instruction = "CLI access via python run.py"

        menu_func = create_cli_menu(title, features, cli_instruction=instruction)

        with patch('builtins.input', side_effect=['1', '2']), \
             patch('builtins.print') as mock_print:

            menu_func(Mock())

            printed_output = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
            assert instruction in printed_output


class TestCreateGUILauncher:
    """Test create_gui_launcher factory function"""

    def test_create_gui_launcher_exists(self):
        """Test that create_gui_launcher function exists"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        assert callable(create_gui_launcher)

    def test_create_gui_launcher_returns_callable(self):
        """Test that create_gui_launcher returns a callable function"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "This is a test GUI window"

        launcher_func = create_gui_launcher(title, description)

        assert callable(launcher_func)

    def test_create_gui_launcher_with_instruction(self):
        """Test creating GUI launcher with CLI instruction"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"
        instruction = "Use CLI: python run.py --feature"

        launcher_func = create_gui_launcher(title, description, cli_instruction=instruction)

        assert callable(launcher_func)

    def test_launcher_function_accepts_root_and_auth(self):
        """Test that launcher function accepts root and auth parameters"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        # Mock tkinter root
        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        # Should accept root and auth parameters
        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_window = Mock()
            mock_toplevel.return_value = mock_window

            launcher_func(mock_root, mock_auth)

            # Should have called Toplevel with root
            mock_toplevel.assert_called_once_with(mock_root)

    def test_launcher_checks_authentication(self):
        """Test that launcher checks if user is logged in"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()

        # Test with no auth
        with patch('tkinter.messagebox.showerror') as mock_error:
            launcher_func(mock_root, None)
            mock_error.assert_called_once()

        # Test with auth but no current_user
        mock_auth = Mock()
        mock_auth.current_user = None

        with patch('tkinter.messagebox.showerror') as mock_error:
            launcher_func(mock_root, mock_auth)
            mock_error.assert_called()

    def test_launcher_creates_toplevel_window(self):
        """Test that launcher creates a Toplevel window"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI Window"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_window = Mock()
            mock_toplevel.return_value = mock_window

            launcher_func(mock_root, mock_auth)

            # Verify window.title() was called with correct title
            mock_window.title.assert_called_once_with(title)

    def test_launcher_sets_window_geometry(self):
        """Test that launcher sets window size"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel') as mock_toplevel:
            mock_window = Mock()
            mock_toplevel.return_value = mock_window

            launcher_func(mock_root, mock_auth)

            # Verify geometry was set
            mock_window.geometry.assert_called_once_with("900x600")
            mock_window.minsize.assert_called_once_with(800, 500)

    def test_launcher_displays_title_label(self):
        """Test that launcher displays title label"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI Window"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel'), \
             patch('tkinter.ttk.Frame'), \
             patch('tkinter.ttk.Label') as mock_label:

            launcher_func(mock_root, mock_auth)

            # Check that label was created with title
            label_calls = [call for call in mock_label.call_args_list
                          if len(call[1]) > 0 and 'text' in call[1] and call[1]['text'] == title]
            assert len(label_calls) > 0

    def test_launcher_displays_description(self):
        """Test that launcher displays description"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "This is a comprehensive description of the feature"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel'), \
             patch('tkinter.ttk.Frame'), \
             patch('tkinter.ttk.Label') as mock_label:

            launcher_func(mock_root, mock_auth)

            # Check that label was created with description
            label_calls = [call for call in mock_label.call_args_list
                          if len(call[1]) > 0 and 'text' in call[1] and call[1]['text'] == description]
            assert len(label_calls) > 0

    def test_launcher_creates_close_button(self):
        """Test that launcher creates close button"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel'), \
             patch('tkinter.ttk.Frame'), \
             patch('tkinter.ttk.Label'), \
             patch('tkinter.ttk.LabelFrame'), \
             patch('tkinter.ttk.Button') as mock_button:

            launcher_func(mock_root, mock_auth)

            # Check that button was created with "Close" text
            button_calls = [call for call in mock_button.call_args_list
                           if len(call[1]) > 0 and 'text' in call[1] and call[1]['text'] == "Close"]
            assert len(button_calls) > 0

    def test_launcher_displays_cli_instruction(self):
        """Test that launcher displays CLI instruction when provided"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"
        instruction = "Use CLI: python run.py --test"

        launcher_func = create_gui_launcher(title, description, cli_instruction=instruction)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel'), \
             patch('tkinter.ttk.Frame'), \
             patch('tkinter.ttk.Label') as mock_label, \
             patch('tkinter.ttk.LabelFrame'), \
             patch('tkinter.ttk.Button'):

            launcher_func(mock_root, mock_auth)

            # Check that label was created with instruction
            label_calls = [call for call in mock_label.call_args_list
                          if len(call[1]) > 0 and 'text' in call[1] and instruction in str(call[1]['text'])]
            assert len(label_calls) > 0

    def test_launcher_handles_exception(self):
        """Test that launcher handles exceptions gracefully"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel', side_effect=Exception("Test error")), \
             patch('tkinter.messagebox.showerror') as mock_error, \
             patch('builtins.print'):

            launcher_func(mock_root, mock_auth)

            # Should have shown error message
            mock_error.assert_called_once()

    def test_launcher_prints_success_message(self):
        """Test that launcher prints success message"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test GUI"
        description = "Test description"

        launcher_func = create_gui_launcher(title, description)

        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = {'username': 'testuser'}

        with patch('tkinter.Toplevel'), \
             patch('tkinter.ttk.Frame'), \
             patch('tkinter.ttk.Label'), \
             patch('tkinter.ttk.LabelFrame'), \
             patch('tkinter.ttk.Button'), \
             patch('builtins.print') as mock_print:

            launcher_func(mock_root, mock_auth)

            # Check that success message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            success_printed = any('opened successfully' in str(call).lower() or 'test gui' in str(call).lower()
                                 for call in print_calls)
            assert success_printed


class TestFactoryFunctionIntegration:
    """Integration tests for factory functions"""

    def test_cli_menu_and_gui_launcher_compatibility(self):
        """Test that CLI menu and GUI launcher can work together"""
        from university_system.modules.shared.utils.feature_factory import (
            create_cli_menu, create_gui_launcher
        )

        # Create both
        menu = create_cli_menu("Test", {"Feature": "Description", "Return": "Exit"})
        launcher = create_gui_launcher("Test", "Description")

        assert callable(menu)
        assert callable(launcher)

    def test_multiple_menus_can_be_created(self):
        """Test that multiple CLI menus can be created independently"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        menu1 = create_cli_menu("Menu 1", {"Feature 1": "Desc", "Return": "Exit"})
        menu2 = create_cli_menu("Menu 2", {"Feature 2": "Desc", "Return": "Exit"})

        # They should be different functions
        assert menu1 is not menu2
        assert callable(menu1)
        assert callable(menu2)

    def test_multiple_launchers_can_be_created(self):
        """Test that multiple GUI launchers can be created independently"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        launcher1 = create_gui_launcher("GUI 1", "Description 1")
        launcher2 = create_gui_launcher("GUI 2", "Description 2")

        # They should be different functions
        assert launcher1 is not launcher2
        assert callable(launcher1)
        assert callable(launcher2)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_create_cli_menu_with_empty_features(self):
        """Test creating CLI menu with minimal features"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        menu = create_cli_menu("Test", {"Return": "Exit"})

        assert callable(menu)

    def test_create_cli_menu_with_many_features(self):
        """Test creating CLI menu with many features"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        features = {f"Feature {i}": f"Description {i}" for i in range(1, 20)}
        features["Return"] = "Exit"

        menu = create_cli_menu("Test", features)

        assert callable(menu)

    def test_create_gui_launcher_with_long_description(self):
        """Test creating GUI launcher with very long description"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        long_description = "This is a very long description. " * 100

        launcher = create_gui_launcher("Test", long_description)

        assert callable(launcher)

    def test_create_gui_launcher_with_special_characters(self):
        """Test creating GUI launcher with special characters"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        title = "Test <>&\"' GUI"
        description = "Description with special chars: <>&\"'"

        launcher = create_gui_launcher(title, description)

        assert callable(launcher)


class TestModuleDocumentation:
    """Test module documentation"""

    def test_module_has_docstring(self):
        """Test that module has documentation"""
        from university_system.modules.shared.utils import feature_factory

        assert feature_factory.__doc__ is not None
        assert len(feature_factory.__doc__) > 0

    def test_create_cli_menu_has_docstring(self):
        """Test that create_cli_menu has documentation"""
        from university_system.modules.shared.utils.feature_factory import create_cli_menu

        assert create_cli_menu.__doc__ is not None
        assert 'menu' in create_cli_menu.__doc__.lower()

    def test_create_gui_launcher_has_docstring(self):
        """Test that create_gui_launcher has documentation"""
        from university_system.modules.shared.utils.feature_factory import create_gui_launcher

        assert create_gui_launcher.__doc__ is not None
        assert 'gui' in create_gui_launcher.__doc__.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
