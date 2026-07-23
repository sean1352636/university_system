"""
Comprehensive tests for console_output.py

Tests all console output functionality including colors,
formatting, tables, interactive methods, and convenience functions.
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch, call
from io import StringIO


class TestColors:
    """Test Colors class"""

    def test_color_constants_defined(self):
        """Test that color constants are defined"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        assert hasattr(Colors, 'RED')
        assert hasattr(Colors, 'GREEN')
        assert hasattr(Colors, 'YELLOW')
        assert hasattr(Colors, 'BLUE')
        assert hasattr(Colors, 'RESET')

    def test_bright_colors_defined(self):
        """Test that bright color constants are defined"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        assert hasattr(Colors, 'BRIGHT_RED')
        assert hasattr(Colors, 'BRIGHT_GREEN')
        assert hasattr(Colors, 'BRIGHT_YELLOW')

    def test_styles_defined(self):
        """Test that style constants are defined"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        assert hasattr(Colors, 'BOLD')
        assert hasattr(Colors, 'DIM')
        assert hasattr(Colors, 'UNDERLINE')

    @patch('sys.stdout')
    def test_supports_color_with_tty(self, mock_stdout):
        """Test color support detection with TTY"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        mock_stdout.isatty.return_value = True

        with patch.dict('os.environ', {'TERM': 'xterm'}):
            result = Colors.supports_color()

        assert result is True

    @patch('sys.stdout')
    def test_supports_color_without_tty(self, mock_stdout):
        """Test color support detection without TTY"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        mock_stdout.isatty.return_value = False

        result = Colors.supports_color()

        assert result is False

    @patch('sys.stdout')
    def test_supports_color_dumb_terminal(self, mock_stdout):
        """Test color support detection with dumb terminal"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        mock_stdout.isatty.return_value = True

        with patch.dict('os.environ', {'TERM': 'dumb'}):
            result = Colors.supports_color()

        assert result is False

    def test_supports_color_no_isatty(self):
        """Test color support when stdout has no isatty"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        # Create a mock stdout without isatty
        mock_stdout = MagicMock()
        del mock_stdout.isatty

        with patch('sys.stdout', mock_stdout):
            result = Colors.supports_color()

        assert result is False


class TestConsoleOutputBasic:
    """Test basic ConsoleOutput methods"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)  # Disable colors for testing

    @pytest.fixture
    def console_with_colors(self):
        """Create ConsoleOutput instance with colors"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        with patch('education_system.post_18.university_system.modules.shared.utils.console_output.Colors.supports_color', return_value=True):
            return ConsoleOutput(use_colors=True)

    def test_init_with_colors(self, console_with_colors):
        """Test initialization with colors enabled"""
        assert console_with_colors.use_colors is True

    def test_init_without_colors(self, console):
        """Test initialization without colors"""
        assert console.use_colors is False

    def test_colorize_with_colors_disabled(self, console):
        """Test colorization with colors disabled"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        result = console._colorize('test', Colors.RED)
        assert result == 'test'

    def test_colorize_with_colors_enabled(self, console_with_colors):
        """Test colorization with colors enabled"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        result = console_with_colors._colorize('test', Colors.RED)
        assert Colors.RED in result
        assert Colors.RESET in result
        assert 'test' in result

    def test_print_basic(self, console, capsys):
        """Test basic print"""
        console.print('Hello World')

        captured = capsys.readouterr()
        assert 'Hello World' in captured.out

    def test_print_with_color(self, console_with_colors, capsys):
        """Test print with color"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import Colors

        console_with_colors.print('Colored text', Colors.RED)

        captured = capsys.readouterr()
        assert 'Colored text' in captured.out

    def test_success(self, console, capsys):
        """Test success message"""
        console.success('Operation succeeded')

        captured = capsys.readouterr()
        assert '✓' in captured.out
        assert 'Operation succeeded' in captured.out

    def test_success_custom_prefix(self, console, capsys):
        """Test success with custom prefix"""
        console.success('Done', prefix='[OK]')

        captured = capsys.readouterr()
        assert '[OK]' in captured.out

    def test_success_no_prefix(self, console, capsys):
        """Test success without prefix"""
        console.success('Done', prefix='')

        captured = capsys.readouterr()
        assert 'Done' in captured.out

    def test_error(self, console, capsys):
        """Test error message"""
        console.error('Operation failed')

        captured = capsys.readouterr()
        assert '✗' in captured.out
        assert 'Operation failed' in captured.out

    def test_warning(self, console, capsys):
        """Test warning message"""
        console.warning('Be careful')

        captured = capsys.readouterr()
        assert '⚠' in captured.out
        assert 'Be careful' in captured.out

    def test_info(self, console, capsys):
        """Test info message"""
        console.info('Information')

        captured = capsys.readouterr()
        assert 'ℹ' in captured.out
        assert 'Information' in captured.out

    def test_debug(self, console, capsys):
        """Test debug message"""
        console.debug('Debug info')

        captured = capsys.readouterr()
        assert '🔧' in captured.out
        assert 'Debug info' in captured.out


class TestConsoleOutputFormatted:
    """Test formatted output methods"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)

    def test_header(self, console, capsys):
        """Test header output"""
        console.header('Test Header')

        captured = capsys.readouterr()
        assert 'Test Header' in captured.out
        assert '=' in captured.out

    def test_header_custom_width(self, console, capsys):
        """Test header with custom width"""
        console.header('Test Header', width=40)

        captured = capsys.readouterr()
        assert 'Test Header' in captured.out

    def test_section(self, console, capsys):
        """Test section output"""
        console.section('Test Section')

        captured = capsys.readouterr()
        assert 'Test Section' in captured.out
        assert '-' in captured.out

    def test_box(self, console, capsys):
        """Test box output"""
        console.box('Test message')

        captured = capsys.readouterr()
        assert 'Test message' in captured.out
        assert '╔' in captured.out
        assert '╚' in captured.out

    def test_box_multiline(self, console, capsys):
        """Test box with multiline text"""
        console.box('Line 1\nLine 2\nLine 3')

        captured = capsys.readouterr()
        assert 'Line 1' in captured.out
        assert 'Line 2' in captured.out
        assert 'Line 3' in captured.out

    def test_status_success(self, console, capsys):
        """Test status with success"""
        console.status('Status', 'Running', success=True)

        captured = capsys.readouterr()
        assert 'Status' in captured.out
        assert 'Running' in captured.out

    def test_status_failure(self, console, capsys):
        """Test status with failure"""
        console.status('Status', 'Failed', success=False)

        captured = capsys.readouterr()
        assert 'Status' in captured.out
        assert 'Failed' in captured.out

    def test_progress_start(self, console, capsys):
        """Test progress bar at start"""
        console.progress(0, 100)

        captured = capsys.readouterr()
        assert '0.0%' in captured.out or '0/100' in captured.out

    def test_progress_middle(self, console, capsys):
        """Test progress bar in middle"""
        console.progress(50, 100)

        captured = capsys.readouterr()
        assert '50.0%' in captured.out or '50/100' in captured.out

    def test_progress_complete(self, console, capsys):
        """Test progress bar complete"""
        console.progress(100, 100)

        captured = capsys.readouterr()
        assert '100.0%' in captured.out or '100/100' in captured.out

    def test_progress_with_label(self, console, capsys):
        """Test progress bar with label"""
        console.progress(50, 100, label='Processing')

        captured = capsys.readouterr()
        assert 'Processing' in captured.out

    def test_progress_zero_total(self, console, capsys):
        """Test progress bar with zero total"""
        console.progress(0, 0)

        captured = capsys.readouterr()
        assert '0.0%' in captured.out or '0/0' in captured.out


class TestTableOutput:
    """Test table output methods"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)

    def test_table_basic(self, console, capsys):
        """Test basic table output"""
        headers = ['Name', 'Age', 'City']
        rows = [
            ['Alice', 25, 'London'],
            ['Bob', 30, 'Paris'],
            ['Charlie', 35, 'Berlin']
        ]

        console.table(headers, rows)

        captured = capsys.readouterr()
        assert 'Name' in captured.out
        assert 'Alice' in captured.out
        assert 'Bob' in captured.out

    def test_table_with_title(self, console, capsys):
        """Test table with title"""
        headers = ['Name', 'Age']
        rows = [['Alice', 25]]

        console.table(headers, rows, title='Test Table')

        captured = capsys.readouterr()
        assert 'Test Table' in captured.out

    def test_table_empty_rows(self, console, capsys):
        """Test table with empty rows"""
        headers = ['Name', 'Age']
        rows = []

        console.table(headers, rows)

        captured = capsys.readouterr()
        assert 'No data' in captured.out

    def test_table_wide_content(self, console, capsys):
        """Test table with wide content"""
        headers = ['Short', 'VeryLongHeaderName']
        rows = [['A', 'VeryLongContentThatExceedsNormalWidth']]

        console.table(headers, rows, max_width=120)

        captured = capsys.readouterr()
        assert 'Short' in captured.out

    def test_simple_table(self, console, capsys):
        """Test simple table output"""
        headers = ['Name', 'Value']
        rows = [['Item1', '100'], ['Item2', '200']]

        console.simple_table(headers, rows)

        captured = capsys.readouterr()
        assert 'Name' in captured.out
        assert 'Item1' in captured.out

    def test_simple_table_empty(self, console, capsys):
        """Test simple table with no data"""
        headers = ['Name', 'Value']
        rows = []

        console.simple_table(headers, rows)

        captured = capsys.readouterr()
        assert 'No data' in captured.out

    def test_key_value_list(self, console, capsys):
        """Test key-value list output"""
        data = {
            'Name': 'John Doe',
            'Age': 30,
            'City': 'London'
        }

        console.key_value_list(data)

        captured = capsys.readouterr()
        assert 'Name' in captured.out
        assert 'John Doe' in captured.out

    def test_key_value_list_with_title(self, console, capsys):
        """Test key-value list with title"""
        data = {'Key': 'Value'}

        console.key_value_list(data, title='Details')

        captured = capsys.readouterr()
        assert 'Details' in captured.out


class TestSpecialOutput:
    """Test special output methods"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)

    def test_banner_single_style(self, console, capsys):
        """Test banner with single style"""
        console.banner('Test Banner', style='single')

        captured = capsys.readouterr()
        assert 'Test Banner' in captured.out
        assert '┌' in captured.out or '─' in captured.out

    def test_banner_double_style(self, console, capsys):
        """Test banner with double style"""
        console.banner('Test Banner', style='double')

        captured = capsys.readouterr()
        assert 'Test Banner' in captured.out
        assert '╔' in captured.out or '═' in captured.out

    def test_banner_bold_style(self, console, capsys):
        """Test banner with bold style"""
        console.banner('Test Banner', style='bold')

        captured = capsys.readouterr()
        assert 'Test Banner' in captured.out

    def test_banner_unknown_style_defaults(self, console, capsys):
        """Test banner with unknown style defaults to single"""
        console.banner('Test Banner', style='unknown')

        captured = capsys.readouterr()
        assert 'Test Banner' in captured.out

    def test_menu(self, console, capsys):
        """Test menu output"""
        options = ['Option 1', 'Option 2', 'Option 3']

        console.menu('Test Menu', options)

        captured = capsys.readouterr()
        assert 'Test Menu' in captured.out
        assert 'Option 1' in captured.out
        assert '[1]' in captured.out

    def test_menu_without_numbers(self, console, capsys):
        """Test menu without numbers"""
        options = ['Option 1', 'Option 2']

        console.menu('Test Menu', options, show_numbers=False)

        captured = capsys.readouterr()
        assert 'Option 1' in captured.out
        assert '•' in captured.out

    def test_list_items(self, console, capsys):
        """Test list items output"""
        items = ['Item 1', 'Item 2', 'Item 3']

        console.list_items(items)

        captured = capsys.readouterr()
        assert 'Item 1' in captured.out
        assert '•' in captured.out

    def test_list_items_with_title(self, console, capsys):
        """Test list items with title"""
        items = ['Item 1', 'Item 2']

        console.list_items(items, title='My List')

        captured = capsys.readouterr()
        assert 'My List' in captured.out

    def test_list_items_custom_bullet(self, console, capsys):
        """Test list items with custom bullet"""
        items = ['Item 1']

        console.list_items(items, bullet='-')

        captured = capsys.readouterr()
        assert 'Item 1' in captured.out

    def test_divider(self, console, capsys):
        """Test divider output"""
        console.divider()

        captured = capsys.readouterr()
        assert '-' in captured.out

    def test_divider_custom_char(self, console, capsys):
        """Test divider with custom character"""
        console.divider(char='*')

        captured = capsys.readouterr()
        assert '*' in captured.out

    @patch('education_system.post_18.university_system.modules.shared.utils.console_output.datetime')
    def test_timestamp(self, mock_datetime, console, capsys):
        """Test timestamp output"""
        mock_datetime.now.return_value.strftime.return_value = '2025-01-01 12:00:00'

        console.timestamp()

        captured = capsys.readouterr()
        assert '2025-01-01 12:00:00' in captured.out


class TestInteractiveMethods:
    """Test interactive methods"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)

    @patch('builtins.input', return_value='user input')
    def test_prompt(self, mock_input, console):
        """Test prompt"""
        result = console.prompt('Enter value')

        assert result == 'user input'

    @patch('builtins.input', return_value='')
    def test_prompt_with_default(self, mock_input, console):
        """Test prompt with default value"""
        result = console.prompt('Enter value', default='default')

        assert result == 'default'

    @patch('builtins.input', return_value='custom')
    def test_prompt_override_default(self, mock_input, console):
        """Test prompt overriding default"""
        result = console.prompt('Enter value', default='default')

        assert result == 'custom'

    @patch('builtins.input', return_value='y')
    def test_confirm_yes(self, mock_input, console):
        """Test confirm with yes"""
        result = console.confirm('Are you sure?')

        assert result is True

    @patch('builtins.input', return_value='yes')
    def test_confirm_yes_word(self, mock_input, console):
        """Test confirm with yes word"""
        result = console.confirm('Are you sure?')

        assert result is True

    @patch('builtins.input', return_value='n')
    def test_confirm_no(self, mock_input, console):
        """Test confirm with no"""
        result = console.confirm('Are you sure?')

        assert result is False

    @patch('builtins.input', return_value='')
    def test_confirm_default_false(self, mock_input, console):
        """Test confirm with default false"""
        result = console.confirm('Are you sure?', default=False)

        assert result is False

    @patch('builtins.input', return_value='')
    def test_confirm_default_true(self, mock_input, console):
        """Test confirm with default true"""
        result = console.confirm('Are you sure?', default=True)

        assert result is True

    @patch('builtins.input', return_value='')
    def test_pause(self, mock_input, console):
        """Test pause"""
        console.pause()

        mock_input.assert_called_once()

    @patch('builtins.input', return_value='')
    def test_pause_custom_message(self, mock_input, console):
        """Test pause with custom message"""
        console.pause('Custom message')

        mock_input.assert_called_once()


class TestSummaryMethods:
    """Test summary methods"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)

    def test_summary(self, console, capsys):
        """Test summary output"""
        stats = {
            'Total': 100,
            'Success': 90,
            'Failed': 10
        }

        console.summary('Test Summary', stats)

        captured = capsys.readouterr()
        assert 'Test Summary' in captured.out
        assert 'Total' in captured.out
        assert '100' in captured.out


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_print_success(self, capsys):
        """Test print_success function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_success

        print_success('Operation completed')

        captured = capsys.readouterr()
        assert 'Operation completed' in captured.out

    def test_print_error(self, capsys):
        """Test print_error function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_error

        print_error('Operation failed')

        captured = capsys.readouterr()
        assert 'Operation failed' in captured.out

    def test_print_warning(self, capsys):
        """Test print_warning function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_warning

        print_warning('Warning message')

        captured = capsys.readouterr()
        assert 'Warning message' in captured.out

    def test_print_info(self, capsys):
        """Test print_info function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_info

        print_info('Info message')

        captured = capsys.readouterr()
        assert 'Info message' in captured.out

    def test_print_header(self, capsys):
        """Test print_header function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_header

        print_header('Test Header')

        captured = capsys.readouterr()
        assert 'Test Header' in captured.out

    def test_print_table(self, capsys):
        """Test print_table function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_table

        headers = ['Name', 'Value']
        rows = [['Item1', '100']]

        print_table(headers, rows)

        captured = capsys.readouterr()
        assert 'Name' in captured.out
        assert 'Item1' in captured.out

    def test_print_menu(self, capsys):
        """Test print_menu function"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import print_menu

        options = ['Option 1', 'Option 2']

        print_menu('Test Menu', options)

        captured = capsys.readouterr()
        assert 'Test Menu' in captured.out
        assert 'Option 1' in captured.out


class TestGlobalConsole:
    """Test global console instance"""

    def test_global_console_exists(self):
        """Test that global console instance exists"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import console

        assert console is not None

    def test_global_console_is_console_output(self):
        """Test that global console is ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import console, ConsoleOutput

        assert isinstance(console, ConsoleOutput)


class TestEdgeCases:
    """Test edge cases"""

    @pytest.fixture
    def console(self):
        """Create ConsoleOutput instance"""
        from education_system.post_18.university_system.modules.shared.utils.console_output import ConsoleOutput
        return ConsoleOutput(use_colors=False)

    def test_table_with_mismatched_columns(self, console, capsys):
        """Test table with rows having fewer columns than headers"""
        headers = ['Name', 'Age', 'City']
        rows = [
            ['Alice', 25],  # Missing City
            ['Bob', 30, 'Paris']
        ]

        console.table(headers, rows)

        captured = capsys.readouterr()
        assert 'Alice' in captured.out

    def test_key_value_list_empty(self, console, capsys):
        """Test key-value list with empty dict"""
        console.key_value_list({})

        captured = capsys.readouterr()
        # Should not crash

    def test_progress_more_than_total(self, console, capsys):
        """Test progress bar with current > total"""
        console.progress(150, 100)

        captured = capsys.readouterr()
        assert '150/100' in captured.out

    def test_box_very_long_line(self, console, capsys):
        """Test box with very long line"""
        long_text = 'A' * 200

        console.box(long_text)

        captured = capsys.readouterr()
        # Should truncate or handle gracefully

    def test_menu_empty_options(self, console, capsys):
        """Test menu with empty options list"""
        console.menu('Empty Menu', [])

        captured = capsys.readouterr()
        assert 'Empty Menu' in captured.out


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
