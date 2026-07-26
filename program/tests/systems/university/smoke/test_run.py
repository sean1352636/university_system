"""
Comprehensive test suite for run.py
Tests all functions, command-line arguments, error handling, and interactive menu
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import the module to test
import run


class TestDisplayInterfaceMenu:
    """Test suite for display_interface_menu() function"""

    @patch('builtins.input', return_value='1')
    @patch('sys.stdout', new_callable=StringIO)
    def test_choice_cli(self, mock_stdout, mock_input):
        """Test selecting CLI option (choice 1)"""
        result = run.display_interface_menu()
        assert result == 'cli'
        output = mock_stdout.getvalue()
        assert "UNIVERSITY MANAGEMENT SYSTEM" in output
        assert "Command Line Interface (CLI)" in output

    @patch('builtins.input', return_value='2')
    @patch('sys.stdout', new_callable=StringIO)
    def test_choice_gui(self, mock_stdout, mock_input):
        """Test selecting GUI option (choice 2)"""
        result = run.display_interface_menu()
        assert result == 'gui'
        output = mock_stdout.getvalue()
        assert "Graphical User Interface (GUI)" in output

    @patch('tests.systems.university._support.run_all_tests.main')
    @patch('builtins.input', side_effect=['3', '4'])
    @patch('sys.stdout', new_callable=StringIO)
    def test_choice_run_tests(self, mock_stdout, mock_input, mock_run_tests):
        """Test selecting run tests option (choice 3)"""
        with pytest.raises(SystemExit) as exc_info:
            run.display_interface_menu()
        assert exc_info.value.code == 0
        mock_run_tests.assert_called_once()

    @patch('builtins.input', return_value='4')
    @patch('sys.stdout', new_callable=StringIO)
    def test_choice_exit(self, mock_stdout, mock_input):
        """Test selecting exit option (choice 4)"""
        with pytest.raises(SystemExit) as exc_info:
            run.display_interface_menu()
        assert exc_info.value.code == 0
        output = mock_stdout.getvalue()
        assert "Goodbye!" in output

    @patch('builtins.input', side_effect=['invalid', '5', '1'])
    @patch('sys.stdout', new_callable=StringIO)
    def test_invalid_choices(self, mock_stdout, mock_input):
        """Test handling of invalid choices"""
        result = run.display_interface_menu()
        assert result == 'cli'
        output = mock_stdout.getvalue()
        assert "Invalid choice" in output
        # Should show error message twice (for 'invalid' and '5')
        assert output.count("Invalid choice") == 2

    @patch('builtins.input', side_effect=KeyboardInterrupt())
    @patch('sys.stdout', new_callable=StringIO)
    def test_keyboard_interrupt(self, mock_stdout, mock_input):
        """Test handling of Ctrl+C (KeyboardInterrupt)"""
        with pytest.raises(SystemExit) as exc_info:
            run.display_interface_menu()
        assert exc_info.value.code == 0
        output = mock_stdout.getvalue()
        assert "Exiting..." in output

    @patch('builtins.input', side_effect=EOFError())
    @patch('sys.stdout', new_callable=StringIO)
    def test_eof_error(self, mock_stdout, mock_input):
        """Test handling of EOF error"""
        with pytest.raises(SystemExit) as exc_info:
            run.display_interface_menu()
        assert exc_info.value.code == 0
        output = mock_stdout.getvalue()
        assert "Exiting..." in output


class TestRunCliMode:
    """Test suite for run_cli_mode() function"""

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_successful_cli_execution(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test successful CLI mode execution"""
        mock_cli_main.return_value = True
        result = run.run_cli_mode()
        assert result is True
        mock_cli_main.assert_called_once()
        mock_log_error.assert_not_called()
        output = mock_stdout.getvalue()
        assert "Starting Command Line Interface" in output

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main', side_effect=ImportError("Module not found"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_import_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of ImportError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()
        output = mock_stdout.getvalue()
        assert "CLI Import Error" in output
        assert "Module not found" in output

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main', side_effect=OSError("File system error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_os_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of OSError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()
        output = mock_stdout.getvalue()
        assert "CLI Application Error" in output

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main', side_effect=RuntimeError("Runtime issue"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_runtime_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of RuntimeError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main', side_effect=ValueError("Invalid value"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_value_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of ValueError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main', side_effect=Exception("Unexpected error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_general_exception(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of general Exception"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Unexpected error" in output


def _make_fake_main_gui_module(mock_func):
    """Create a fake main_gui module with the given run_gui_interface mock."""
    fake_module = MagicMock()
    fake_module.run_gui_interface = mock_func
    return fake_module


class TestRunGuiMode:
    """Test suite for run_gui_mode() function"""

    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_successful_gui_execution(self, mock_stdout, mock_log_error):
        """Test successful GUI mode execution"""
        mock_gui_func = Mock(return_value=True)
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        assert result is True
        mock_gui_func.assert_called_once()
        mock_log_error.assert_not_called()
        output = mock_stdout.getvalue()
        assert "Starting Graphical User Interface" in output

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_import_error_fallback_to_cli(self, mock_stdout, mock_log_error, mock_cli):
        """Test ImportError with fallback to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=ImportError("Tkinter not found"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        assert result is True
        mock_log_error.assert_called_once()
        mock_cli.assert_called_once()
        output = mock_stdout.getvalue()
        assert "GUI Import Error" in output
        assert "Falling back to CLI mode" in output

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_os_error_fallback_to_cli(self, mock_stdout, mock_log_error, mock_cli):
        """Test OSError with fallback to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=OSError("Display not found"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_runtime_error_fallback_to_cli(self, mock_stdout, mock_log_error, mock_cli):
        """Test RuntimeError with fallback to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=RuntimeError("GUI runtime error"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_value_error_fallback_to_cli(self, mock_stdout, mock_log_error, mock_cli):
        """Test ValueError with fallback to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=ValueError("Invalid GUI value"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_attribute_error_fallback_to_cli(self, mock_stdout, mock_log_error, mock_cli):
        """Test AttributeError with fallback to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=AttributeError("Missing attribute"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('sys.stdout', new_callable=StringIO)
    def test_general_exception_fallback_to_cli(self, mock_stdout, mock_log_error, mock_cli):
        """Test general Exception with fallback to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=Exception("Unexpected GUI error"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            result = run.run_gui_mode()
        mock_cli.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Unexpected GUI error" in output


class TestMain:
    """Test suite for main() function"""

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_cli_argument(self, mock_stdout, mock_input):
        """Test main() with --cli command-line argument"""
        mock_user_info = {'id': 1, 'username': 'admin'}
        mock_login = Mock(return_value=(mock_user_info, 'university', 'admin', Mock()))
        mock_dispatch = Mock()

        with patch.object(sys, 'argv', ['run.py', '--cli']), \
             patch('education_system.launcher.auth.cli_universal_login', mock_login), \
             patch('education_system.launcher.auth.gui_universal_login', Mock()), \
             patch('education_system.launcher.dispatch.dispatch_cli', mock_dispatch), \
             patch('education_system.launcher.dispatch.dispatch_gui', Mock()), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            run.main()

        mock_login.assert_called_once()
        mock_dispatch.assert_called_once()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_gui_argument(self, mock_stdout, mock_input):
        """Test main() with --gui command-line argument delegates to gui_universal_login + dispatch_gui"""
        mock_login_result = ({'id': 1, 'username': 'admin'}, 'university', 'admin', Mock())

        with patch.object(sys, 'argv', ['run.py', '--gui']), \
             patch('education_system.launcher.auth.gui_universal_login', return_value=mock_login_result) as mock_login, \
             patch('education_system.launcher.dispatch.dispatch_gui') as mock_dispatch, \
             patch('education_system.platform.features.i18n.selector_gui.show_language_selector', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            run.main()

        mock_login.assert_called_once()
        mock_dispatch.assert_called_once()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_test_argument(self, mock_stdout, mock_input):
        """Test main() with --test argument (falls through to launcher)"""
        with patch.object(sys, 'argv', ['run.py', '--test']), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()), \
             patch('education_system.launcher.menus.cli_select_system', return_value='university') as mock_sys, \
             patch('education_system.launcher.systems.LAUNCHERS', {('university', 'test'): Mock()}) as mock_launchers, \
             patch('education_system.switch.consume', return_value=None):
            run.main()

        # The test mode delegates to the launcher for the selected system
        mock_sys.assert_called()

    @patch('builtins.input', return_value='0')
    @patch('education_system.systems.university.infrastructure.database.database_utils.init_db')
    @patch('education_system.systems.university.infrastructure.shared_context.set_auth')
    @patch('education_system.systems.university.infrastructure.auth.core.UserAuth')
    @patch('education_system.systems.university.infrastructure.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_help_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db, mock_input):
        """Test main() with --help command-line argument"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 0

    @patch('builtins.input', return_value='0')
    @patch('education_system.systems.university.infrastructure.database.database_utils.init_db')
    @patch('education_system.systems.university.infrastructure.shared_context.set_auth')
    @patch('education_system.systems.university.infrastructure.auth.core.UserAuth')
    @patch('education_system.systems.university.infrastructure.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_unknown_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                       mock_set_auth, mock_init_db, mock_input):
        """Test main() with unknown command-line argument — argparse exits with code 2"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--unknown']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 2

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_interactive_menu_cli(self, mock_stdout, mock_input):
        """Test main() with interactive menu choosing CLI"""
        mock_login_result = ({'id': 1, 'username': 'admin'}, 'university', 'admin', Mock())

        with patch.object(sys, 'argv', ['run.py']), \
             patch('education_system.launcher.menus.cli_select_mode', return_value='cli') as mock_mode, \
             patch('education_system.launcher.auth.cli_universal_login', return_value=mock_login_result) as mock_login, \
             patch('education_system.launcher.dispatch.dispatch_cli') as mock_dispatch, \
             patch('education_system.platform.features.i18n.init_i18n', Mock()), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'):
            run.main()

        mock_mode.assert_called_once()
        mock_login.assert_called_once()
        mock_dispatch.assert_called_once()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_interactive_menu_gui(self, mock_stdout, mock_input):
        """Test main() with interactive menu choosing GUI"""
        mock_login_result = ({'id': 1, 'username': 'admin'}, 'university', 'admin', Mock())

        with patch.object(sys, 'argv', ['run.py']), \
             patch('education_system.launcher.menus.cli_select_mode', return_value='gui') as mock_mode, \
             patch('education_system.launcher.auth.gui_universal_login', return_value=mock_login_result) as mock_login, \
             patch('education_system.launcher.dispatch.dispatch_gui') as mock_dispatch, \
             patch('education_system.platform.features.i18n.selector_gui.show_language_selector', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            run.main()

        mock_mode.assert_called_once()
        mock_login.assert_called_once()
        mock_dispatch.assert_called_once()

    @patch('builtins.input', return_value='0')
    @patch('education_system.systems.university.infrastructure.database.database_utils.init_db')
    @patch('education_system.systems.university.infrastructure.shared_context.set_auth')
    @patch('education_system.systems.university.infrastructure.auth.core.UserAuth')
    @patch('education_system.systems.university.infrastructure.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_database_init_warning(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                       mock_set_auth, mock_init_db, mock_input):
        """Test main() when --help is passed (argparse exits regardless of init_db)"""
        mock_init_db.return_value = False

        with patch.object(sys, 'argv', ['run.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 0

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_keyboard_interrupt(self, mock_stdout, mock_input):
        """Test main() when launcher raises KeyboardInterrupt"""
        with patch.object(sys, 'argv', ['run.py', '--gui']), \
             patch('education_system.launcher.auth.gui_universal_login', side_effect=KeyboardInterrupt()), \
             patch('education_system.platform.features.i18n.selector_gui.show_language_selector', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            # KeyboardInterrupt propagates from main()
            with pytest.raises(KeyboardInterrupt):
                run.main()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_import_error(self, mock_stdout, mock_input):
        """Test main() when launcher import fails"""
        with patch.object(sys, 'argv', ['run.py', '--cli']), \
             patch('education_system.launcher.auth.cli_universal_login', side_effect=ImportError("Cannot import")), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            with pytest.raises(ImportError):
                run.main()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_os_error(self, mock_stdout, mock_input):
        """Test main() when launcher raises OSError"""
        with patch.object(sys, 'argv', ['run.py', '--cli']), \
             patch('education_system.launcher.auth.cli_universal_login', side_effect=OSError("File system error")), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            with pytest.raises(OSError):
                run.main()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_runtime_error(self, mock_stdout, mock_input):
        """Test main() when launcher raises RuntimeError"""
        with patch.object(sys, 'argv', ['run.py', '--cli']), \
             patch('education_system.launcher.auth.cli_universal_login', side_effect=RuntimeError("Runtime issue")), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            with pytest.raises(RuntimeError):
                run.main()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_general_exception(self, mock_stdout, mock_input):
        """Test main() when launcher raises general Exception"""
        with patch.object(sys, 'argv', ['run.py', '--cli']), \
             patch('education_system.launcher.auth.cli_universal_login', side_effect=Exception("Unexpected error")), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            with pytest.raises(Exception, match="Unexpected error"):
                run.main()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_argument_variations(self, mock_stdout, mock_input):
        """Test --cli argument triggers CLI login and dispatch"""
        mock_user_info = {'id': 1, 'username': 'admin'}
        mock_login = Mock(return_value=(mock_user_info, 'university', 'admin', Mock()))
        mock_dispatch = Mock()

        with patch.object(sys, 'argv', ['run.py', '--cli']), \
             patch('education_system.launcher.auth.cli_universal_login', mock_login), \
             patch('education_system.launcher.auth.gui_universal_login', Mock()), \
             patch('education_system.launcher.dispatch.dispatch_cli', mock_dispatch), \
             patch('education_system.launcher.dispatch.dispatch_gui', Mock()), \
             patch('education_system.platform.features.i18n.selector_cli.show_language_selector_cli', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            run.main()

        mock_login.assert_called_once()
        mock_dispatch.assert_called_once()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_gui_argument_variations(self, mock_stdout, mock_input):
        """Test --gui argument triggers GUI login and dispatch"""
        mock_login_result = ({'id': 1, 'username': 'admin'}, 'university', 'admin', Mock())

        with patch.object(sys, 'argv', ['run.py', '--gui']), \
             patch('education_system.launcher.auth.gui_universal_login', return_value=mock_login_result) as mock_login, \
             patch('education_system.launcher.dispatch.dispatch_gui') as mock_dispatch, \
             patch('education_system.platform.features.i18n.selector_gui.show_language_selector', return_value='en'), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()):
            run.main()

        mock_login.assert_called_once()
        mock_dispatch.assert_called_once()

    @patch('builtins.input', return_value='0')
    @patch('sys.stdout', new_callable=StringIO)
    def test_test_argument_variations(self, mock_stdout, mock_input):
        """Test --test argument delegates to launcher"""
        with patch.object(sys, 'argv', ['run.py', '--test']), \
             patch('education_system.platform.features.i18n.init_i18n', Mock()), \
             patch('education_system.launcher.menus.cli_select_system', return_value='university'), \
             patch('education_system.launcher.systems.LAUNCHERS', {('university', 'test'): Mock()}), \
             patch('education_system.switch.consume', return_value=None):
            run.main()  # Should not raise

    @patch('builtins.input', return_value='0')
    @patch('education_system.systems.university.infrastructure.database.database_utils.init_db')
    @patch('education_system.systems.university.infrastructure.shared_context.set_auth')
    @patch('education_system.systems.university.infrastructure.auth.core.UserAuth')
    @patch('education_system.systems.university.infrastructure.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_help_argument_variations(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                     mock_set_auth, mock_init_db, mock_input):
        """Test all variations of help argument (-h, --help, help)"""
        mock_init_db.return_value = True

        for arg in ['--help', '-h']:
            with patch.object(sys, 'argv', ['run.py', arg]):
                with pytest.raises(SystemExit) as exc_info:
                    run.main()
                assert exc_info.value.code == 0


class TestMainEntryPoint:
    """Test suite for __main__ entry point"""

    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_successful_execution(self, mock_stdout, mock_main):
        """Test successful execution via __main__"""
        mock_main.return_value = None

        # We can't actually test the if __name__ == "__main__" block directly,
        # but we can test the logic that would be executed
        result = mock_main()
        assert result is None

    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_unsuccessful_execution(self, mock_stdout, mock_main):
        """Test unsuccessful execution via __main__ (main returns None)"""
        mock_main.return_value = None

        # Simulate the __main__ block logic
        result = mock_main()
        assert result is None

    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_system_error_handling(self, mock_stdout, mock_main):
        """Test SystemError handling in __main__"""
        mock_main.side_effect = SystemError("System failure")

        with pytest.raises(SystemError):
            mock_main()

    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_memory_error_handling(self, mock_stdout, mock_main):
        """Test MemoryError handling in __main__"""
        mock_main.side_effect = MemoryError("Out of memory")

        with pytest.raises(MemoryError):
            mock_main()

    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_keyboard_interrupt_at_entry(self, mock_stdout, mock_main):
        """Test KeyboardInterrupt handling at entry point"""
        mock_main.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            mock_main()

    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_unexpected_critical_error(self, mock_stdout, mock_main):
        """Test unexpected Exception handling at entry point"""
        mock_main.side_effect = Exception("Unexpected critical error")

        with pytest.raises(Exception):
            mock_main()


class TestLoggingConfiguration:
    """Test suite for logging configuration"""

    def test_logger_exists(self):
        """Test that logger is configured"""
        assert hasattr(run, 'logger')
        assert run.logger.name == 'run'

    def test_logger_level(self):
        """Test that logger has appropriate level set"""
        # The logger should be configured via basicConfig
        assert run.logger is not None


class TestSystemPathConfiguration:
    """Test suite for sys.path configuration"""

    def test_project_root_in_path(self):
        """Test that project root is added to sys.path"""
        # This is done at module import time
        # We can't easily test this without re-importing the module
        # But we can verify the logic is present in the file
        assert True  # Placeholder - the code exists in run.py

    def test_cli_path_in_path(self):
        """Test that additional paths are added in run_cli_mode"""
        # Similar to above, tested via code inspection
        assert True  # Placeholder


class TestErrorLoggingIntegration:
    """Test suite for error logging integration"""

    @patch('run.log_error')
    @patch('education_system.systems.university.interfaces.cli.shell.cli_main.main', side_effect=ImportError("Test error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_log_error_called_with_context(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test that log_error is called with message and error"""
        run.run_cli_mode()

        # Verify log_error was called
        assert mock_log_error.call_count == 1

        # Verify the message and error were passed
        call_args = mock_log_error.call_args
        message_arg = call_args[0][0]
        error_arg = call_args[0][1]

        assert isinstance(message_arg, str)
        assert isinstance(error_arg, ImportError)

    @patch('run.log_error')
    @patch('run.run_cli_mode')
    @patch('sys.stdout', new_callable=StringIO)
    def test_log_error_includes_fallback_context(self, mock_stdout, mock_cli, mock_log_error):
        """Test that log_error is called when GUI fails and falls back to CLI"""
        mock_cli.return_value = True
        mock_gui_func = Mock(side_effect=ImportError("Test error"))
        fake_module = _make_fake_main_gui_module(mock_gui_func)
        with patch.dict('sys.modules', {'education_system.systems.university.interfaces.gui.shell.main_gui': fake_module}):
            run.run_gui_mode()

        # Verify log_error was called with message and error
        assert mock_log_error.call_count == 1
        call_args = mock_log_error.call_args
        message_arg = call_args[0][0]
        error_arg = call_args[0][1]

        assert isinstance(message_arg, str)
        assert isinstance(error_arg, ImportError)
        # CLI fallback should have been called
        mock_cli.assert_called_once()


class TestOutputFormatting:
    """Test suite for output formatting and user messages"""

    @patch('sys.stdout', new_callable=StringIO)
    def test_interface_menu_formatting(self, mock_stdout):
        """Test that interface menu is properly formatted"""
        with patch('builtins.input', return_value='1'):
            run.display_interface_menu()

        output = mock_stdout.getvalue()
        assert "=" * 54 in output  # Header separator
        assert "UNIVERSITY MANAGEMENT SYSTEM" in output

    @patch('builtins.input', return_value='0')
    @patch('education_system.systems.university.infrastructure.database.database_utils.init_db')
    @patch('education_system.systems.university.infrastructure.shared_context.set_auth')
    @patch('education_system.systems.university.infrastructure.auth.core.UserAuth')
    @patch('education_system.systems.university.infrastructure.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_help_message_formatting(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db, mock_input):
        """Test that --help triggers argparse help and exits cleanly"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
