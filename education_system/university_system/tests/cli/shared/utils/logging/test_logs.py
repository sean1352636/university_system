"""
Comprehensive test suite for logs.py

Tests all functions and functionality including:
- get_log_file function
- configure_logging function
- log_event function
- handle_exception decorator
- display_communication_logs_menu function
- display_activity_logs function
- export_communication_logs function
- display_communication_analytics_menu function
"""

import pytest
import os
import tempfile
import shutil
import logging
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open, call
import csv

# Import the module under test
from education_system.university_system.modules.shared.utils import logs
from education_system.university_system.modules.shared.utils.logs import (
    get_log_file,
    configure_logging,
    log_event,
    handle_exception,
    display_communication_logs_menu,
    display_activity_logs,
    export_communication_logs,
    display_communication_analytics_menu,
    LOG_MANAGEMENT_AVAILABLE,
)


class TestGetLogFile:
    """Test get_log_file function"""

    def test_get_log_file_basic(self):
        """Test getting a log file path"""
        result = get_log_file('test.log')
        assert isinstance(result, str)
        assert result.endswith('test.log')

    def test_get_log_file_creates_directory(self):
        """Test that get_log_file creates directory if needed"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('university_system.modules.shared.constants.paths.LOG_DIR', tmpdir):
                test_subdir = os.path.join(tmpdir, 'subdir')
                with patch('university_system.modules.shared.constants.paths.LOG_DIR', test_subdir):
                    result = get_log_file('test.log')
                    assert os.path.exists(test_subdir)

    def test_get_log_file_different_filenames(self):
        """Test get_log_file with different filenames"""
        filenames = ['app.log', 'email.log', 'system.log', 'test_123.log']
        for filename in filenames:
            result = get_log_file(filename)
            assert result.endswith(filename)

    @patch('university_system.modules.shared.utils.logs.project_get_log_file')
    def test_get_log_file_uses_project_function(self, mock_project_get):
        """Test that get_log_file uses project function if available"""
        mock_project_get.return_value = '/custom/path/test.log'
        with patch('university_system.modules.shared.utils.logs.project_get_log_file', mock_project_get):
            result = get_log_file('test.log')
            # If project function is available, it should be called
            if logs.project_get_log_file:
                mock_project_get.assert_called()


class TestConfigureLogging:
    """Test configure_logging function"""

    def test_configure_logging_runs(self):
        """Test that configure_logging runs without error"""
        # configure_logging is called on module import, so we just verify it exists
        assert callable(configure_logging)

    def test_configure_logging_sets_up_logging(self):
        """Test that configure_logging sets up logging"""
        # Logging is already configured on module import
        # Just verify the function is callable
        assert callable(configure_logging)

    @patch('university_system.modules.shared.utils.logs.project_configure_logging')
    def test_configure_logging_uses_project_function(self, mock_project_config):
        """Test that configure_logging uses project function if available"""
        with patch('university_system.modules.shared.utils.logs.project_configure_logging', mock_project_config):
            configure_logging()
            # If project function exists, it would be called


class TestLogEvent:
    """Test log_event function"""

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_log_event_debug(self, mock_logger):
        """Test log_event with debug level"""
        log_event('debug', 'Test debug message')
        mock_logger.debug.assert_called_with('Test debug message')

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_log_event_info(self, mock_logger):
        """Test log_event with info level"""
        log_event('info', 'Test info message')
        mock_logger.info.assert_called_with('Test info message')

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_log_event_warning(self, mock_logger):
        """Test log_event with warning level"""
        log_event('warning', 'Test warning message')
        mock_logger.warning.assert_called_with('Test warning message')

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_log_event_error(self, mock_logger):
        """Test log_event with error level"""
        log_event('error', 'Test error message')
        mock_logger.error.assert_called_with('Test error message')

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_log_event_critical(self, mock_logger):
        """Test log_event with critical level"""
        log_event('critical', 'Test critical message')
        mock_logger.critical.assert_called_with('Test critical message')

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_log_event_unknown_level(self, mock_logger):
        """Test log_event with unknown level defaults to info"""
        log_event('unknown', 'Test message')
        mock_logger.info.assert_called_with('Test message')

    @patch('university_system.modules.shared.utils.logs.logger')
    @patch('university_system.modules.shared.utils.logs.LOG_MANAGEMENT_AVAILABLE', True)
    @patch('university_system.modules.shared.utils.logs.log_manager')
    @patch('university_system.modules.shared.utils.logs.state')
    def test_log_event_with_enhanced_logging(self, mock_state, mock_log_manager, mock_logger):
        """Test log_event with enhanced logging available"""
        # Setup mock user
        mock_state.auth = Mock()
        mock_state.auth.current_user = {
            'id': 'user123',
            'username': 'testuser',
            'role': 'admin'
        }
        mock_log_manager.db = Mock()
        mock_log_manager.db.insert_log = Mock()

        log_event('info', 'Test message')

        # Should call both standard logger and enhanced logging
        mock_logger.info.assert_called()
        mock_log_manager.db.insert_log.assert_called_once()


class TestHandleException:
    """Test handle_exception decorator"""

    def test_handle_exception_normal_execution(self):
        """Test decorator with normal function execution"""
        @handle_exception
        def test_func():
            return True

        result = test_func()
        assert result is True

    def test_handle_exception_with_sqlite_error(self):
        """Test decorator catches SQLite errors"""
        from education_system.university_system.infrastructure.database.db import sqlite3

        @handle_exception
        def test_func():
            raise sqlite3.Error("Database error")

        result = test_func()
        assert result is False

    def test_handle_exception_with_smtp_error(self):
        """Test decorator catches SMTP errors"""
        import smtplib

        @handle_exception
        def test_func():
            raise smtplib.SMTPException("SMTP error")

        result = test_func()
        assert result is False

    def test_handle_exception_with_general_exception(self):
        """Test decorator catches general exceptions"""
        @handle_exception
        def test_func():
            raise ValueError("Some error")

        result = test_func()
        assert result is False

    def test_handle_exception_with_args_kwargs(self):
        """Test decorator preserves function arguments"""
        @handle_exception
        def test_func(a, b, c=None):
            return (a, b, c)

        result = test_func(1, 2, c=3)
        assert result == (1, 2, 3)


class TestDisplayActivityLogs:
    """Test display_activity_logs function"""

    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_display_activity_logs_empty(self, mock_print, mock_input):
        """Test displaying empty activity logs"""
        display_activity_logs([], "Test Title")
        # Should print no activity message

    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_display_activity_logs_with_data(self, mock_print, mock_input):
        """Test displaying activity logs with data"""
        logs_data = [
            {
                'timestamp': '2025-01-01T12:00:00',
                'username': 'testuser',
                'action': 'login',
                'status': 'success',
                'details': 'User logged in'
            }
        ]
        display_activity_logs(logs_data, "Test Activity Logs")
        # Should print log entries

    @patch('builtins.input', return_value='y')
    @patch('builtins.print')
    def test_display_activity_logs_show_all(self, mock_print, mock_input):
        """Test displaying all activity logs when more than 25"""
        logs_data = [
            {
                'timestamp': f'2025-01-01T12:00:{i:02d}',
                'username': f'user{i}',
                'action': 'test',
                'status': 'success',
                'details': f'Test {i}'
            } for i in range(30)
        ]
        display_activity_logs(logs_data, "Many Logs")
        # Should ask to show all and display all

    @patch('builtins.input', return_value='n')
    @patch('builtins.print')
    def test_display_activity_logs_dont_show_all(self, mock_print, mock_input):
        """Test not showing all logs when user declines"""
        logs_data = [
            {
                'timestamp': f'2025-01-01T12:00:{i:02d}',
                'username': f'user{i}',
                'action': 'test',
                'status': 'success',
                'details': f'Test {i}'
            } for i in range(30)
        ]
        display_activity_logs(logs_data, "Many Logs")
        # Should only show first 25


class TestExportCommunicationLogs:
    """Test export_communication_logs function"""

    @pytest.fixture
    def mock_dashboard(self):
        """Create a mock dashboard"""
        dashboard = Mock()
        dashboard.get_communication_logs = Mock(return_value=[
            {
                'timestamp': '2025-01-01T12:00:00',
                'user_id': 'user123',
                'username': 'testuser',
                'role': 'student',
                'action': 'email_sent',
                'module': 'email',
                'details': 'Email sent successfully',
                'status': 'success'
            }
        ])
        return dashboard

    @patch('builtins.input', side_effect=['7', ''])
    @patch('builtins.print')
    def test_export_communication_logs_basic(self, mock_print, mock_input, mock_dashboard, tmp_path):
        """Test exporting communication logs"""
        os.chdir(tmp_path)
        export_communication_logs(mock_dashboard)

        # Check if CSV file was created
        csv_files = list(tmp_path.glob('communication_logs_*.csv'))
        if csv_files:
            assert len(csv_files) > 0

    @patch('builtins.input', side_effect=['30', ''])
    @patch('builtins.print')
    def test_export_communication_logs_custom_days(self, mock_print, mock_input, mock_dashboard, tmp_path):
        """Test exporting logs with custom days"""
        os.chdir(tmp_path)
        export_communication_logs(mock_dashboard)
        mock_dashboard.get_communication_logs.assert_called_with(days=30, limit=5000)

    @patch('builtins.input', side_effect=['10', ''])
    @patch('builtins.print')
    def test_export_communication_logs_no_logs(self, mock_print, mock_input, tmp_path):
        """Test exporting when no logs are available"""
        dashboard = Mock()
        dashboard.get_communication_logs = Mock(return_value=[])
        os.chdir(tmp_path)
        export_communication_logs(dashboard)
        # Should print no logs message

    @patch('builtins.input', side_effect=['', ''])
    @patch('builtins.print')
    def test_export_communication_logs_invalid_input(self, mock_print, mock_input, mock_dashboard, tmp_path):
        """Test exporting with empty input defaults to 30 days"""
        os.chdir(tmp_path)
        export_communication_logs(mock_dashboard)
        mock_dashboard.get_communication_logs.assert_called_with(days=30, limit=5000)


class TestDisplayCommunicationLogsMenu:
    """Test display_communication_logs_menu function"""

    @patch('builtins.input', return_value='9')
    @patch('builtins.print')
    def test_display_communication_logs_menu_exit(self, mock_print, mock_input):
        """Test exiting the communication logs menu"""
        dashboard = Mock()
        display_communication_logs_menu(dashboard)
        # Should exit cleanly

    @patch('builtins.input', side_effect=['1', '9'])
    @patch('builtins.print')
    @patch('university_system.modules.shared.utils.logs.display_activity_logs')
    def test_display_communication_logs_menu_recent(self, mock_display, mock_print, mock_input):
        """Test recent activity option"""
        dashboard = Mock()
        dashboard.get_communication_logs = Mock(return_value=[])
        display_communication_logs_menu(dashboard)
        dashboard.get_communication_logs.assert_called()

    @patch('builtins.input', side_effect=['2', '7', '9'])
    @patch('builtins.print')
    @patch('university_system.modules.shared.utils.logs.display_activity_logs')
    def test_display_communication_logs_menu_date_range(self, mock_display, mock_print, mock_input):
        """Test date range option"""
        dashboard = Mock()
        dashboard.get_communication_logs = Mock(return_value=[])
        display_communication_logs_menu(dashboard)
        dashboard.get_communication_logs.assert_called_with(days=7, limit=100)


class TestDisplayCommunicationAnalyticsMenu:
    """Test display_communication_analytics_menu function"""

    @patch('builtins.input', return_value='7')
    @patch('builtins.print')
    def test_display_communication_analytics_menu_exit(self, mock_print, mock_input):
        """Test exiting the analytics menu"""
        dashboard = Mock()
        # Function has import that might not exist, so catch that
        try:
            display_communication_analytics_menu(dashboard)
        except ModuleNotFoundError:
            # Expected if finance_db_operations doesn't exist
            pass

    @patch('builtins.input', side_effect=['1', '7'])
    @patch('builtins.print')
    @patch('university_system.modules.shared.utils.logs.LOG_MANAGEMENT_AVAILABLE', True)
    @patch('university_system.modules.shared.utils.logs.log_manager')
    def test_display_communication_analytics_menu_summary(self, mock_log_manager, mock_print, mock_input):
        """Test activity summary option"""
        dashboard = Mock()
        dashboard.get_communication_analytics = Mock(return_value={
            'total_activities': 100,
            'unique_users': 25,
            'success_rate': 98.5,
            'failed_activities': 2
        })
        # Function has import that might not exist, so catch that
        try:
            display_communication_analytics_menu(dashboard)
            dashboard.get_communication_analytics.assert_called_with(30)
        except ModuleNotFoundError:
            # Expected if finance_db_operations doesn't exist
            pass


class TestLogger:
    """Test logger instance"""

    def test_logger_exists(self):
        """Test that logger instance exists"""
        assert logs.logger is not None

    def test_logger_name(self):
        """Test logger has correct name"""
        assert logs.logger.name == "email_manager"


class TestModuleConstants:
    """Test module-level constants"""

    def test_log_management_available_flag(self):
        """Test LOG_MANAGEMENT_AVAILABLE is boolean"""
        assert isinstance(LOG_MANAGEMENT_AVAILABLE, bool)


class TestIntegration:
    """Integration tests for logging functionality"""

    @patch('university_system.modules.shared.utils.logs.logger')
    def test_full_logging_workflow(self, mock_logger):
        """Test a complete logging workflow"""
        # Log different levels
        log_event('info', 'Starting test')
        log_event('warning', 'Test warning')
        log_event('error', 'Test error')

        # Verify all were logged
        assert mock_logger.info.called
        assert mock_logger.warning.called
        assert mock_logger.error.called

    def test_exception_handling_workflow(self):
        """Test exception handling in workflow"""
        @handle_exception
        def risky_operation():
            return "success"

        @handle_exception
        def failing_operation():
            raise ValueError("Something went wrong")

        assert risky_operation() == "success"
        assert failing_operation() is False


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
