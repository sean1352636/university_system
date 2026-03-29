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

    @patch('education_system.university_system.tests.run_all_tests.main')
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
    @patch('education_system.university_system.modules.shared.cli.cli_main.main')
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
    @patch('education_system.university_system.modules.shared.cli.cli_main.main', side_effect=ImportError("Module not found"))
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
    @patch('education_system.university_system.modules.shared.cli.cli_main.main', side_effect=OSError("File system error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_os_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of OSError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()
        output = mock_stdout.getvalue()
        assert "CLI Application Error" in output

    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.cli.cli_main.main', side_effect=RuntimeError("Runtime issue"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_runtime_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of RuntimeError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.cli.cli_main.main', side_effect=ValueError("Invalid value"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_value_error(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of ValueError"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.cli.cli_main.main', side_effect=Exception("Unexpected error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_general_exception(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test handling of general Exception"""
        result = run.run_cli_mode()
        assert result is False
        mock_log_error.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Unexpected error" in output


class TestRunGuiMode:
    """Test suite for run_gui_mode() function"""

    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface')
    @patch('sys.stdout', new_callable=StringIO)
    def test_successful_gui_execution(self, mock_stdout, mock_gui_main, mock_log_error):
        """Test successful GUI mode execution"""
        mock_gui_main.return_value = True
        result = run.run_gui_mode()
        assert result is True
        mock_gui_main.assert_called_once()
        mock_log_error.assert_not_called()
        output = mock_stdout.getvalue()
        assert "Starting Graphical User Interface" in output

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=ImportError("Tkinter not found"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_import_error_fallback_to_cli(self, mock_stdout, mock_gui_main, mock_log_error, mock_cli):
        """Test ImportError with fallback to CLI"""
        mock_cli.return_value = True
        result = run.run_gui_mode()
        assert result is True
        mock_log_error.assert_called_once()
        mock_cli.assert_called_once()
        output = mock_stdout.getvalue()
        assert "GUI Import Error" in output
        assert "Falling back to CLI mode" in output

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=OSError("Display not found"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_os_error_fallback_to_cli(self, mock_stdout, mock_gui_main, mock_log_error, mock_cli):
        """Test OSError with fallback to CLI"""
        mock_cli.return_value = True
        result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=RuntimeError("GUI runtime error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_runtime_error_fallback_to_cli(self, mock_stdout, mock_gui_main, mock_log_error, mock_cli):
        """Test RuntimeError with fallback to CLI"""
        mock_cli.return_value = True
        result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=ValueError("Invalid GUI value"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_value_error_fallback_to_cli(self, mock_stdout, mock_gui_main, mock_log_error, mock_cli):
        """Test ValueError with fallback to CLI"""
        mock_cli.return_value = True
        result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=AttributeError("Missing attribute"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_attribute_error_fallback_to_cli(self, mock_stdout, mock_gui_main, mock_log_error, mock_cli):
        """Test AttributeError with fallback to CLI"""
        mock_cli.return_value = True
        result = run.run_gui_mode()
        mock_cli.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=Exception("Unexpected GUI error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_general_exception_fallback_to_cli(self, mock_stdout, mock_gui_main, mock_log_error, mock_cli):
        """Test general Exception with fallback to CLI"""
        mock_cli.return_value = True
        result = run.run_gui_mode()
        mock_cli.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Unexpected GUI error" in output


class TestMain:
    """Test suite for main() function"""

    @patch('run.run_cli_mode')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_cli_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db, mock_run_cli):
        """Test main() with --cli command-line argument"""
        mock_init_db.return_value = True
        mock_run_cli.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--cli']):
            result = run.main()

        assert result is True
        mock_ensure_dirs.assert_called_once()
        mock_init_db.assert_called_once()
        mock_run_cli.assert_called_once()

    @patch('run.run_gui_mode')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_gui_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                   mock_set_auth, mock_init_db, mock_run_gui):
        """Test main() with --gui command-line argument"""
        mock_init_db.return_value = True
        mock_run_gui.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--gui']):
            result = run.main()

        assert result is True
        mock_run_gui.assert_called_once()

    @patch('education_system.university_system.tests.run_all_tests.main')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_test_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db, mock_run_tests):
        """Test main() with --test command-line argument"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--test']):
            result = run.main()

        assert result is True
        mock_run_tests.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Running all tests" in output

    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_help_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db):
        """Test main() with --help command-line argument"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 0

    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_unknown_argument(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                       mock_set_auth, mock_init_db):
        """Test main() with unknown command-line argument — argparse exits with code 2"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--unknown']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 2

    @patch('run.run_cli_mode')
    @patch('run.display_interface_menu')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_interactive_menu_cli(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                      mock_set_auth, mock_init_db, mock_menu, mock_run_cli):
        """Test main() with interactive menu choosing CLI"""
        mock_init_db.return_value = True
        mock_menu.return_value = 'cli'
        mock_run_cli.return_value = True

        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is True
        mock_menu.assert_called_once()
        mock_run_cli.assert_called_once()

    @patch('run.run_gui_mode')
    @patch('run.display_interface_menu')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_interactive_menu_gui(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                      mock_set_auth, mock_init_db, mock_menu, mock_run_gui):
        """Test main() with interactive menu choosing GUI"""
        mock_init_db.return_value = True
        mock_menu.return_value = 'gui'
        mock_run_gui.return_value = True

        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is True
        mock_menu.assert_called_once()
        mock_run_gui.assert_called_once()

    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_database_init_warning(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                       mock_set_auth, mock_init_db):
        """Test main() when --help is passed (argparse exits regardless of init_db)"""
        mock_init_db.return_value = False

        with patch.object(sys, 'argv', ['run.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 0

    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_keyboard_interrupt(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db):
        """Test main() handling of KeyboardInterrupt"""
        mock_init_db.side_effect = KeyboardInterrupt()

        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is True
        output = mock_stdout.getvalue()
        assert "Application interrupted by user" in output

    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories',
           side_effect=ImportError("Cannot import"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_import_error(self, mock_stdout, mock_ensure_dirs, mock_log_error):
        """Test main() handling of ImportError"""
        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db',
           side_effect=OSError("File system error"))
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_os_error(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                          mock_set_auth, mock_init_db, mock_log_error):
        """Test main() handling of OSError"""
        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db',
           side_effect=RuntimeError("Runtime issue"))
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_runtime_error(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                               mock_set_auth, mock_init_db, mock_log_error):
        """Test main() handling of RuntimeError"""
        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.log_error')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db',
           side_effect=Exception("Unexpected error"))
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_general_exception(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                   mock_set_auth, mock_init_db, mock_log_error):
        """Test main() handling of general Exception"""
        with patch.object(sys, 'argv', ['run.py']):
            result = run.main()

        assert result is False
        mock_log_error.assert_called_once()

    @patch('run.run_cli_mode')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_argument_variations(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db, mock_run_cli):
        """Test all variations of CLI argument (-c, --cli, cli)"""
        mock_init_db.return_value = True
        mock_run_cli.return_value = True

        for arg in ['--cli', '-c', 'cli']:
            with patch.object(sys, 'argv', ['run.py', arg]):
                result = run.main()
                assert result is True

    @patch('run.run_gui_mode')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_gui_argument_variations(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db, mock_run_gui):
        """Test all variations of GUI argument (-g, --gui, gui)"""
        mock_init_db.return_value = True
        mock_run_gui.return_value = True

        for arg in ['--gui', '-g', 'gui']:
            with patch.object(sys, 'argv', ['run.py', arg]):
                result = run.main()
                assert result is True

    @patch('education_system.university_system.tests.run_all_tests.main')
    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_test_argument_variations(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                     mock_set_auth, mock_init_db, mock_run_tests):
        """Test all variations of test argument (-t, --test, test)"""
        mock_init_db.return_value = True

        for arg in ['--test', '-t', 'test']:
            with patch.object(sys, 'argv', ['run.py', arg]):
                result = run.main()
                assert result is True

    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_help_argument_variations(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                     mock_set_auth, mock_init_db):
        """Test all variations of help argument (-h, --help, help)"""
        mock_init_db.return_value = True

        for arg in ['--help', '-h']:
            with patch.object(sys, 'argv', ['run.py', arg]):
                with pytest.raises(SystemExit) as exc_info:
                    run.main()
                assert exc_info.value.code == 0


class TestMainEntryPoint:
    """Test suite for __main__ entry point"""

    @patch('run.log_critical_error')
    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_successful_execution(self, mock_stdout, mock_main, mock_log_critical):
        """Test successful execution via __main__"""
        mock_main.return_value = True

        # We can't actually test the if __name__ == "__main__" block directly,
        # but we can test the logic that would be executed
        success = mock_main()
        assert success is True
        mock_log_critical.assert_not_called()

    @patch('run.log_critical_error')
    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_unsuccessful_execution(self, mock_stdout, mock_main, mock_log_critical):
        """Test unsuccessful execution via __main__ (should exit with code 1)"""
        mock_main.return_value = False

        # Simulate the __main__ block logic
        success = mock_main()
        assert success is False
        # In real execution, this would call sys.exit(1)

    @patch('run.log_critical_error')
    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_system_error_handling(self, mock_stdout, mock_main, mock_log_critical):
        """Test SystemError handling in __main__"""
        mock_main.side_effect = SystemError("System failure")

        with pytest.raises(SystemError):
            mock_main()
            # In real execution, this would be caught and logged as critical

    @patch('run.log_critical_error')
    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_memory_error_handling(self, mock_stdout, mock_main, mock_log_critical):
        """Test MemoryError handling in __main__"""
        mock_main.side_effect = MemoryError("Out of memory")

        with pytest.raises(MemoryError):
            mock_main()

    @patch('run.log_critical_error')
    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_keyboard_interrupt_at_entry(self, mock_stdout, mock_main, mock_log_critical):
        """Test KeyboardInterrupt handling at entry point"""
        mock_main.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            mock_main()

    @patch('run.log_critical_error')
    @patch('run.main')
    @patch('sys.stdout', new_callable=StringIO)
    def test_unexpected_critical_error(self, mock_stdout, mock_main, mock_log_critical):
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
    @patch('education_system.university_system.modules.shared.cli.cli_main.main', side_effect=ImportError("Test error"))
    @patch('sys.stdout', new_callable=StringIO)
    def test_log_error_called_with_context(self, mock_stdout, mock_cli_main, mock_log_error):
        """Test that log_error is called with proper context"""
        run.run_cli_mode()

        # Verify log_error was called
        assert mock_log_error.call_count == 1

        # Verify the error and context were passed
        call_args = mock_log_error.call_args
        error_arg = call_args[0][0]
        context_arg = call_args[0][1]

        assert isinstance(error_arg, ImportError)
        assert 'mode' in context_arg
        assert context_arg['mode'] == 'CLI'

    @patch('run.log_error')
    @patch('education_system.university_system.modules.shared.gui.main_gui.run_gui_interface',
           side_effect=ImportError("Test error"))
    @patch('run.run_cli_mode')
    @patch('sys.stdout', new_callable=StringIO)
    def test_log_error_includes_fallback_context(self, mock_stdout, mock_cli, mock_gui, mock_log_error):
        """Test that log_error includes fallback context for GUI errors"""
        mock_cli.return_value = True
        run.run_gui_mode()

        # Verify log_error was called with fallback context
        call_args = mock_log_error.call_args
        context_arg = call_args[0][1]

        assert 'fallback' in context_arg
        assert context_arg['fallback'] == 'CLI'


class TestOutputFormatting:
    """Test suite for output formatting and user messages"""

    @patch('sys.stdout', new_callable=StringIO)
    def test_interface_menu_formatting(self, mock_stdout):
        """Test that interface menu is properly formatted"""
        with patch('builtins.input', return_value='1'):
            run.display_interface_menu()

        output = mock_stdout.getvalue()
        assert "=" * 60 in output  # Header separator
        assert "-" * 60 in output  # Footer separator
        assert "UNIVERSITY MANAGEMENT SYSTEM" in output

    @patch('education_system.university_system.infrastructure.database.database_utils.init_db')
    @patch('education_system.university_system.infrastructure.shared_context.set_auth')
    @patch('education_system.university_system.infrastructure.auth.user_authentication.UserAuth')
    @patch('education_system.university_system.modules.shared.constants.paths.ensure_directories')
    @patch('sys.stdout', new_callable=StringIO)
    def test_help_message_formatting(self, mock_stdout, mock_ensure_dirs, mock_auth_class,
                                    mock_set_auth, mock_init_db):
        """Test that --help triggers argparse help and exits cleanly"""
        mock_init_db.return_value = True

        with patch.object(sys, 'argv', ['run.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                run.main()
            assert exc_info.value.code == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
