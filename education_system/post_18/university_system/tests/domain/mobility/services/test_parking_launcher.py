"""
Test cases for Parking Management System Launcher

Tests launcher functionality including:
- Dependency checking
- Interface selection
- GUI and console launching
- Argument parsing
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import io

_LAUNCHER = 'education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher'


class TestParkingLauncher(unittest.TestCase):
    """Test parking launcher functionality"""

    def test_module_can_be_imported(self):
        """Test that launcher module can be imported"""
        try:
            from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher
            self.assertIsNotNone(parking_launcher)
        except ImportError as e:
            self.fail(f"Failed to import parking_launcher: {e}")

    @patch(f'{_LAUNCHER}.tk')
    def test_check_dependencies_all_present(self, mock_tk):
        """Test dependency checking with all dependencies present"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import check_dependencies

        with patch('sys.stdout', new=io.StringIO()):
            result = check_dependencies()

        # Should pass basic check
        self.assertIsInstance(result, bool)

    def test_check_dependencies_function_exists(self):
        """Test that check_dependencies function exists"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        self.assertTrue(hasattr(parking_launcher, 'check_dependencies'))
        self.assertTrue(callable(parking_launcher.check_dependencies))

    def test_launch_gui_function_exists(self):
        """Test that launch_gui function exists"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        self.assertTrue(hasattr(parking_launcher, 'launch_gui'))
        self.assertTrue(callable(parking_launcher.launch_gui))

    def test_launch_console_function_exists(self):
        """Test that launch_console function exists"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        self.assertTrue(hasattr(parking_launcher, 'launch_console'))
        self.assertTrue(callable(parking_launcher.launch_console))

    @patch(f'{_LAUNCHER}.tk.Tk')
    @patch(f'{_LAUNCHER}.messagebox')
    def test_show_interface_selection_gui(self, mock_msgbox, mock_tk):
        """Test showing interface selection dialog choosing GUI"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import (
            show_interface_selection
        )

        mock_msgbox.askyesnocancel.return_value = True

        result = show_interface_selection()
        self.assertEqual(result, 'gui')

    @patch(f'{_LAUNCHER}.tk.Tk')
    @patch(f'{_LAUNCHER}.messagebox')
    def test_show_interface_selection_console(self, mock_msgbox, mock_tk):
        """Test showing interface selection dialog choosing console"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import (
            show_interface_selection
        )

        mock_msgbox.askyesnocancel.return_value = False

        result = show_interface_selection()
        self.assertEqual(result, 'console')

    @patch(f'{_LAUNCHER}.tk.Tk')
    @patch(f'{_LAUNCHER}.messagebox')
    def test_show_interface_selection_cancel(self, mock_msgbox, mock_tk):
        """Test showing interface selection dialog with cancel"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import (
            show_interface_selection
        )

        mock_msgbox.askyesnocancel.return_value = None

        result = show_interface_selection()
        self.assertEqual(result, 'exit')

    @patch(f'{_LAUNCHER}.tk.Tk')
    @patch('education_system.post_18.university_system.modules.domain.campus.mobility.gui.parking_management_gui.ParkingManagementGUI')
    def test_launch_gui_success(self, mock_gui_class, mock_tk):
        """Test successful GUI launch"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import launch_gui

        mock_root = Mock()
        mock_tk.return_value = mock_root

        mock_app = Mock()
        mock_gui_class.return_value = mock_app

        with patch('sys.stdout', new=io.StringIO()):
            result = launch_gui()

        # Should return True on success
        self.assertTrue(result)
        mock_gui_class.assert_called_once_with(mock_root)

    @patch('education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management.display_parking_menu')
    @patch('education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management.set_auth')
    @patch('education_system.post_18.university_system.infrastructure.shared_context.get_auth')
    def test_launch_console_success(self, mock_get_auth, mock_set_auth, mock_menu):
        """Test successful console launch"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import launch_console

        mock_auth = Mock()
        mock_get_auth.return_value = mock_auth

        with patch('sys.stdout', new=io.StringIO()):
            result = launch_console()

        # Should return True on success
        self.assertTrue(result)
        mock_set_auth.assert_called_once_with(mock_auth)
        mock_menu.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management.display_parking_menu')
    @patch('education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management.set_auth')
    @patch('education_system.post_18.university_system.infrastructure.shared_context.get_auth')
    @patch('education_system.post_18.university_system.infrastructure.auth.UserAuth')
    def test_launch_console_no_auth(self, mock_auth_class, mock_get_auth, mock_set_auth, mock_menu):
        """Test console launch when auth is None"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import launch_console

        mock_get_auth.return_value = None
        mock_new_auth = Mock()
        mock_auth_class.return_value = mock_new_auth

        with patch('sys.stdout', new=io.StringIO()):
            result = launch_console()

        # Should create new auth
        mock_auth_class.assert_called_once()
        mock_set_auth.assert_called_once_with(mock_new_auth)


class TestParkingLauncherMain(unittest.TestCase):
    """Test main launcher function"""

    @patch('sys.argv', ['parking_launcher.py', '--help'])
    @patch('sys.exit')
    def test_main_help_argument(self, mock_exit):
        """Test main function with --help argument"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        with patch('sys.stdout', new=io.StringIO()):
            try:
                parking_launcher.main()
            except SystemExit:
                pass

    @patch('sys.argv', ['parking_launcher.py', '--gui'])
    @patch(f'{_LAUNCHER}.launch_gui')
    @patch(f'{_LAUNCHER}.check_dependencies')
    def test_main_gui_argument(self, mock_deps, mock_launch):
        """Test main function with --gui argument"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        mock_deps.return_value = True
        mock_launch.return_value = True

        with patch('sys.stdout', new=io.StringIO()):
            parking_launcher.main()

        mock_launch.assert_called_once()

    @patch('sys.argv', ['parking_launcher.py', '--console'])
    @patch(f'{_LAUNCHER}.launch_console')
    @patch(f'{_LAUNCHER}.check_dependencies')
    def test_main_console_argument(self, mock_deps, mock_launch):
        """Test main function with --console argument"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        mock_deps.return_value = True
        mock_launch.return_value = True

        with patch('sys.stdout', new=io.StringIO()):
            parking_launcher.main()

        mock_launch.assert_called_once()

    @patch('sys.argv', ['parking_launcher.py', '--no-deps-check', '--console'])
    @patch(f'{_LAUNCHER}.launch_console')
    def test_main_skip_deps_check(self, mock_launch):
        """Test main function with --no-deps-check"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        mock_launch.return_value = True

        with patch('sys.stdout', new=io.StringIO()):
            parking_launcher.main()

        mock_launch.assert_called_once()

    @patch('sys.argv', ['parking_launcher.py'])
    @patch(f'{_LAUNCHER}.show_interface_selection')
    @patch(f'{_LAUNCHER}.launch_gui')
    @patch(f'{_LAUNCHER}.check_dependencies')
    def test_main_no_arguments(self, mock_deps, mock_launch, mock_select):
        """Test main function with no arguments"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        mock_deps.return_value = True
        mock_select.return_value = 'gui'
        mock_launch.return_value = True

        with patch('sys.stdout', new=io.StringIO()):
            parking_launcher.main()

        mock_select.assert_called_once()
        mock_launch.assert_called_once()

    @patch('sys.argv', ['parking_launcher.py', '--gui', '--console'])
    @patch('sys.exit')
    def test_main_conflicting_arguments(self, mock_exit):
        """Test main function with conflicting arguments"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        with patch('sys.stdout', new=io.StringIO()):
            with patch('sys.stderr', new=io.StringIO()):
                try:
                    parking_launcher.main()
                except (SystemExit, UnboundLocalError):
                    pass

        mock_exit.assert_called_with(1)


class TestParkingLauncherErrorHandling(unittest.TestCase):
    """Test error handling in launcher"""

    @patch(f'{_LAUNCHER}.tk.Tk')
    def test_launch_gui_import_error(self, mock_tk):
        """Test GUI launch with import error"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import launch_gui

        mock_tk.side_effect = ImportError("GUI not available")

        with patch('sys.stdout', new=io.StringIO()):
            result = launch_gui()

        self.assertFalse(result)

    def test_launch_console_import_error(self):
        """Test console launch with import error"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_launcher import launch_console

        with patch('education_system.post_18.university_system.modules.domain.campus.mobility.services.parking_management.display_parking_menu',
                  side_effect=ImportError("Module not found")):
            with patch('sys.stdout', new=io.StringIO()):
                result = launch_console()

            self.assertFalse(result)

    @patch('sys.argv', ['parking_launcher.py'])
    @patch(f'{_LAUNCHER}.show_interface_selection')
    @patch('sys.exit')
    def test_main_exit_selection(self, mock_exit, mock_select):
        """Test main function with exit selection"""
        from education_system.post_18.university_system.modules.domain.campus.mobility.services import parking_launcher

        mock_select.return_value = 'exit'

        with patch('sys.stdout', new=io.StringIO()):
            with patch(f'{_LAUNCHER}.check_dependencies',
                      return_value=True):
                try:
                    parking_launcher.main()
                except (SystemExit, UnboundLocalError):
                    pass

        mock_exit.assert_called_with(0)


if __name__ == '__main__':
    unittest.main()
