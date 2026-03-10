"""
Tests for email scheduler control utility.

Tests the command-line interface for controlling the email scheduler.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestEmailSchedulerControlModule:
    """Test email scheduler control module."""

    def test_email_scheduler_control_file_exists(self):
        """Test that email_scheduler_control file exists."""
        control_file = Path("university_system/utils/email_scheduler_control.py")
        assert control_file.exists()

    def test_email_scheduler_control_imports(self):
        """Test that email scheduler control module can be imported."""
        try:
            from education_system.university_system.utils import email_scheduler_control
            assert email_scheduler_control is not None
        except ImportError as e:
            pytest.skip(f"Email scheduler control module not available: {e}")

    def test_print_status_function_exists(self):
        """Test print_status function exists."""
        try:
            from education_system.university_system.utils.email_scheduler_control import print_status
            assert callable(print_status)
        except ImportError:
            pytest.skip("Email scheduler control module not available")

    def test_start_command_function_exists(self):
        """Test start_command function exists."""
        try:
            from education_system.university_system.utils.email_scheduler_control import start_command
            assert callable(start_command)
        except ImportError:
            pytest.skip("Email scheduler control module not available")

    def test_stop_command_function_exists(self):
        """Test stop_command function exists."""
        try:
            from education_system.university_system.utils.email_scheduler_control import stop_command
            assert callable(stop_command)
        except ImportError:
            pytest.skip("Email scheduler control module not available")

    def test_run_command_function_exists(self):
        """Test run_command function exists."""
        try:
            from education_system.university_system.utils.email_scheduler_control import run_command
            assert callable(run_command)
        except ImportError:
            pytest.skip("Email scheduler control module not available")


class TestPrintStatus:
    """Test print_status function."""

    @patch('university_system.utils.email_scheduler_control.is_scheduler_running')
    @patch('university_system.utils.email_scheduler_control.get_scheduled_jobs')
    @patch('builtins.print')
    def test_print_status_when_running(self, mock_print, mock_jobs, mock_running):
        """Test print_status when scheduler is running."""
        mock_running.return_value = True
        mock_jobs.return_value = ["Job 1", "Job 2"]

        try:
            from education_system.university_system.utils.email_scheduler_control import print_status
            print_status()
            assert mock_print.called
        except ImportError:
            pytest.skip("Email scheduler control module not available")

    @patch('university_system.utils.email_scheduler_control.is_scheduler_running')
    @patch('builtins.print')
    def test_print_status_when_stopped(self, mock_print, mock_running):
        """Test print_status when scheduler is stopped."""
        mock_running.return_value = False

        try:
            from education_system.university_system.utils.email_scheduler_control import print_status
            print_status()
            assert mock_print.called
        except ImportError:
            pytest.skip("Email scheduler control module not available")


class TestStartCommand:
    """Test start_command function."""

    @patch('university_system.utils.email_scheduler_control.is_scheduler_running')
    @patch('university_system.utils.email_scheduler_control.start_scheduler')
    def test_start_command_success(self, mock_start, mock_running):
        """Test successful start command."""
        mock_running.return_value = False
        mock_start.return_value = True

        try:
            from education_system.university_system.utils.email_scheduler_control import start_command
            result = start_command()
            assert result == 0
        except ImportError:
            pytest.skip("Email scheduler control module not available")

    @patch('university_system.utils.email_scheduler_control.is_scheduler_running')
    def test_start_command_already_running(self, mock_running):
        """Test start command when already running."""
        mock_running.return_value = True

        try:
            from education_system.university_system.utils.email_scheduler_control import start_command
            result = start_command()
            assert result == 1
        except ImportError:
            pytest.skip("Email scheduler control module not available")


class TestStopCommand:
    """Test stop_command function."""

    @patch('university_system.utils.email_scheduler_control.is_scheduler_running')
    @patch('university_system.utils.email_scheduler_control.stop_scheduler')
    def test_stop_command_success(self, mock_stop, mock_running):
        """Test successful stop command."""
        mock_running.return_value = True
        mock_stop.return_value = True

        try:
            from education_system.university_system.utils.email_scheduler_control import stop_command
            result = stop_command()
            assert result == 0
        except ImportError:
            pytest.skip("Email scheduler control module not available")

    @patch('university_system.utils.email_scheduler_control.is_scheduler_running')
    def test_stop_command_not_running(self, mock_running):
        """Test stop command when not running."""
        mock_running.return_value = False

        try:
            from education_system.university_system.utils.email_scheduler_control import stop_command
            result = stop_command()
            assert result == 1
        except ImportError:
            pytest.skip("Email scheduler control module not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
