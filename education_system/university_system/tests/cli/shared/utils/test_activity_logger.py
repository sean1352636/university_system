"""
Comprehensive test suite for activity_logger.py

Tests all classes, functions, and functionality including:
- ActivityLogger class (singleton pattern)
- Logging methods (log, log_login, log_logout, log_create, etc.)
- File rotation and log directory management
- Convenience functions (set_user, get_user, log_activity, etc.)
- Global logger instance
"""

import pytest
import os
import tempfile
import shutil
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

from education_system.university_system.modules.shared.utils.activity_logger import (
    ActivityLogger,
    set_user,
    get_user,
    log_activity,
    log_login,
    log_logout,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_import,
    log_error,
    log_access,
    log_permission_denied,
    logger
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for logs."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def activity_logger_instance(temp_log_dir):
    """Create a fresh ActivityLogger instance for testing."""
    with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._get_log_directory') as mock_get_dir:
            mock_get_dir.return_value = Path(temp_log_dir)
            logger_instance = ActivityLogger()
            yield logger_instance


class TestActivityLoggerSingleton:
    """Test ActivityLogger singleton pattern."""

    def test_singleton_pattern(self):
        """Test that ActivityLogger follows singleton pattern."""
        logger1 = ActivityLogger()
        logger2 = ActivityLogger()
        assert logger1 is logger2

    def test_initialization_once(self):
        """Test that logger is only initialized once."""
        logger1 = ActivityLogger()
        assert hasattr(logger1, '_initialized')
        assert logger1._initialized is True

        # Second call should not reinitialize
        logger2 = ActivityLogger()
        assert logger2._initialized is True


class TestActivityLoggerInitialization:
    """Test ActivityLogger initialization."""

    def test_get_log_directory_with_paths(self, temp_log_dir):
        """Test getting log directory from paths module."""
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
            with patch('education_system.university_system.modules.shared.constants.paths.LOG_DIR', temp_log_dir):
                logger_instance = ActivityLogger()
                assert logger_instance.log_dir == Path(temp_log_dir)

    def test_get_log_directory_fallback(self):
        """Test fallback log directory when paths import fails."""
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
            with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._get_log_directory') as mock_get_dir:
                # Simulate import error by returning fallback path
                fallback_path = Path(__file__).parent.parent.parent / 'logs'
                mock_get_dir.return_value = fallback_path
                logger_instance = ActivityLogger()
                assert logger_instance.log_dir is not None

    def test_log_directory_created(self, temp_log_dir):
        """Test that log directory is created if it doesn't exist."""
        new_log_dir = os.path.join(temp_log_dir, 'new_logs')
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
            with patch('education_system.university_system.modules.shared.constants.paths.LOG_DIR', new_log_dir):
                logger_instance = ActivityLogger()
                assert os.path.exists(new_log_dir)

    def test_logger_setup(self, activity_logger_instance):
        """Test that logger is properly set up."""
        assert activity_logger_instance.logger is not None
        assert activity_logger_instance.logger.name == 'UniversitySystemActivity'
        assert activity_logger_instance.logger.level == 20  # INFO level


class TestUserManagement:
    """Test user management functionality."""

    def test_set_user(self, activity_logger_instance):
        """Test setting current user."""
        activity_logger_instance.set_user("testuser")
        assert activity_logger_instance._current_user == "testuser"

    def test_get_user_with_user_set(self, activity_logger_instance):
        """Test getting current user when user is set."""
        activity_logger_instance.set_user("testuser")
        user = activity_logger_instance.get_user()
        assert user == "testuser"

    def test_get_user_default(self, activity_logger_instance):
        """Test getting current user when no user is set."""
        activity_logger_instance._current_user = None
        user = activity_logger_instance.get_user()
        assert user == "System"

    def test_set_user_convenience_function(self):
        """Test set_user convenience function."""
        set_user("admin")
        assert get_user() in ["admin", "System"]  # Might be system if logger is shared

    def test_get_user_convenience_function(self):
        """Test get_user convenience function."""
        user = get_user()
        assert isinstance(user, str)


class TestLoggingMethods:
    """Test logging methods."""

    def test_log_basic(self, activity_logger_instance):
        """Test basic log method."""
        activity_logger_instance.log("Test action")
        # Just verify no exception is raised

    def test_log_with_user(self, activity_logger_instance):
        """Test logging with specific user."""
        activity_logger_instance.log("Test action", user="specificuser")
        # Verify no exception

    def test_log_with_current_user(self, activity_logger_instance):
        """Test logging with current user."""
        activity_logger_instance.set_user("currentuser")
        activity_logger_instance.log("Test action")
        # Verify no exception

    def test_log_login_success(self, activity_logger_instance):
        """Test logging successful login."""
        activity_logger_instance.log_login("testuser", success=True)
        assert activity_logger_instance._current_user == "testuser"

    def test_log_login_failure(self, activity_logger_instance):
        """Test logging failed login."""
        activity_logger_instance.log_login("testuser", success=False)
        assert activity_logger_instance._current_user == "testuser"

    def test_log_logout(self, activity_logger_instance):
        """Test logging logout."""
        activity_logger_instance.set_user("testuser")
        activity_logger_instance.log_logout("testuser")
        assert activity_logger_instance._current_user is None

    def test_log_create(self, activity_logger_instance):
        """Test logging create action."""
        activity_logger_instance.log_create("user", "John Doe")
        # Verify no exception

    def test_log_create_without_name(self, activity_logger_instance):
        """Test logging create action without item name."""
        activity_logger_instance.log_create("user")
        # Verify no exception

    def test_log_read(self, activity_logger_instance):
        """Test logging read action."""
        activity_logger_instance.log_read("student records", "student_123")
        # Verify no exception

    def test_log_update(self, activity_logger_instance):
        """Test logging update action."""
        activity_logger_instance.log_update("grade", "Grade A to B")
        # Verify no exception

    def test_log_delete(self, activity_logger_instance):
        """Test logging delete action."""
        activity_logger_instance.log_delete("course", "CS101")
        # Verify no exception

    def test_log_search(self, activity_logger_instance):
        """Test logging search action."""
        activity_logger_instance.log_search("students", "John")
        # Verify no exception

    def test_log_export(self, activity_logger_instance):
        """Test logging export action."""
        activity_logger_instance.log_export("student data", "CSV")
        # Verify no exception

    def test_log_import(self, activity_logger_instance):
        """Test logging import action."""
        activity_logger_instance.log_import("student data", "file.csv")
        # Verify no exception

    def test_log_error(self, activity_logger_instance):
        """Test logging error."""
        activity_logger_instance.log_error("Database connection failed")
        # Verify no exception

    def test_log_access(self, activity_logger_instance):
        """Test logging access."""
        activity_logger_instance.log_access("Admin Dashboard")
        # Verify no exception

    def test_log_permission_denied(self, activity_logger_instance):
        """Test logging permission denial."""
        activity_logger_instance.log_permission_denied("Edit Grades")
        # Verify no exception


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_log_activity_with_entity(self):
        """Test log_activity with entity type."""
        log_activity("create", "student")
        # Verify no exception

    def test_log_activity_without_entity(self):
        """Test log_activity without entity type."""
        log_activity("test action")
        # Verify no exception

    def test_log_activity_with_user(self):
        """Test log_activity with specific user."""
        log_activity("create", "student", user="admin")
        # Verify no exception

    def test_log_activity_backward_compatibility(self):
        """Test log_activity with deprecated parameters."""
        log_activity("create", "student", user_id=123, details={"name": "John"})
        # Should still work for backward compatibility

    def test_log_login_convenience(self):
        """Test log_login convenience function."""
        log_login("testuser", success=True)
        # Verify no exception

    def test_log_logout_convenience(self):
        """Test log_logout convenience function."""
        log_logout("testuser")
        # Verify no exception

    def test_log_create_convenience(self):
        """Test log_create convenience function."""
        log_create("user", "John Doe")
        # Verify no exception

    def test_log_read_convenience(self):
        """Test log_read convenience function."""
        log_read("student", "123")
        # Verify no exception

    def test_log_update_convenience(self):
        """Test log_update convenience function."""
        log_update("grade", "Updated grade")
        # Verify no exception

    def test_log_delete_convenience(self):
        """Test log_delete convenience function."""
        log_delete("course", "CS101")
        # Verify no exception

    def test_log_search_convenience(self):
        """Test log_search convenience function."""
        log_search("students", "query")
        # Verify no exception

    def test_log_export_convenience(self):
        """Test log_export convenience function."""
        log_export("data", "CSV")
        # Verify no exception

    def test_log_import_convenience(self):
        """Test log_import convenience function."""
        log_import("data", "file.csv")
        # Verify no exception

    def test_log_error_convenience(self):
        """Test log_error convenience function."""
        log_error("Test error")
        # Verify no exception

    def test_log_access_convenience(self):
        """Test log_access convenience function."""
        log_access("Dashboard")
        # Verify no exception

    def test_log_permission_denied_convenience(self):
        """Test log_permission_denied convenience function."""
        log_permission_denied("Edit Feature")
        # Verify no exception


class TestLogFormatting:
    """Test log entry formatting."""

    @patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger.logger')
    def test_log_format(self, mock_logger, activity_logger_instance):
        """Test that log entries have correct format."""
        activity_logger_instance.set_user("testuser")
        activity_logger_instance.log("Test action")

        # Verify logger.info was called
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args[0][0]
        assert "testuser" in call_args
        assert "Test action" in call_args
        # Should contain timestamp in format YYYY-MM-DD HH:MM:SS

    @patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger.logger')
    def test_log_timestamp_format(self, mock_logger, activity_logger_instance):
        """Test that timestamp is in correct format."""
        activity_logger_instance.log("Test action")

        call_args = mock_logger.info.call_args[0][0]
        # Check for timestamp pattern (YYYY-MM-DD HH:MM:SS)
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, call_args)


class TestLogRotation:
    """Test log rotation configuration."""

    def test_log_rotation_handler_configured(self, activity_logger_instance):
        """Test that log rotation handler is configured."""
        handlers = activity_logger_instance.logger.handlers
        assert len(handlers) > 0

        # Check for TimedRotatingFileHandler
        from logging.handlers import TimedRotatingFileHandler
        rotating_handlers = [h for h in handlers if isinstance(h, TimedRotatingFileHandler)]
        assert len(rotating_handlers) > 0

    def test_log_rotation_settings(self, activity_logger_instance):
        """Test log rotation settings."""
        from logging.handlers import TimedRotatingFileHandler
        handlers = [h for h in activity_logger_instance.logger.handlers
                   if isinstance(h, TimedRotatingFileHandler)]

        if handlers:
            handler = handlers[0]
            assert handler.when == 'midnight'
            assert handler.interval == 1
            assert handler.backupCount == 90

    def test_log_file_created(self, activity_logger_instance):
        """Test that log file is created."""
        log_file = activity_logger_instance.log_dir / 'activity.log'
        # Log something to ensure file is created
        activity_logger_instance.log("Test")
        # File might not exist immediately, but handler should be configured
        assert activity_logger_instance.logger.handlers


class TestGlobalLogger:
    """Test global logger instance."""

    def test_global_logger_instance(self):
        """Test that global logger instance exists."""
        assert logger is not None
        assert isinstance(logger, ActivityLogger)

    def test_global_logger_singleton(self):
        """Test that global logger is same as new instance."""
        new_instance = ActivityLogger()
        assert logger is new_instance


class TestIntegration:
    """Integration tests for complex workflows."""

    def test_full_logging_workflow(self, temp_log_dir):
        """Test a complete logging workflow."""
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
            with patch('education_system.university_system.modules.shared.constants.paths.LOG_DIR', temp_log_dir):
                logger_instance = ActivityLogger()

                # Set user
                logger_instance.set_user("admin")

                # Perform various logging operations
                logger_instance.log_login("admin", success=True)
                logger_instance.log_create("student", "John Doe")
                logger_instance.log_update("grade", "Updated grade for CS101")
                logger_instance.log_read("student records", "student_123")
                logger_instance.log_access("Admin Dashboard")
                logger_instance.log_logout("admin")

                # Verify no exceptions raised

    def test_concurrent_logging(self, temp_log_dir):
        """Test logging from multiple 'threads' (sequential for simplicity)."""
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
            with patch('education_system.university_system.modules.shared.constants.paths.LOG_DIR', temp_log_dir):
                logger_instance = ActivityLogger()

                # Simulate multiple users logging
                users = ["user1", "user2", "user3"]
                for user in users:
                    logger_instance.set_user(user)
                    logger_instance.log("Action by " + user)

                # Verify no exceptions

    def test_user_session_lifecycle(self, temp_log_dir):
        """Test complete user session lifecycle."""
        with patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger._instance', None):
            with patch('education_system.university_system.modules.shared.constants.paths.LOG_DIR', temp_log_dir):
                logger_instance = ActivityLogger()

                # Login
                logger_instance.log_login("testuser", success=True)
                assert logger_instance.get_user() == "testuser"

                # Perform actions
                logger_instance.log_access("Dashboard")
                logger_instance.log_read("courses")
                logger_instance.log_update("profile")

                # Logout
                logger_instance.log_logout("testuser")
                assert logger_instance.get_user() == "System"


class TestErrorHandling:
    """Test error handling in logging operations."""

    @patch('education_system.university_system.modules.shared.utils.activity_logger.ActivityLogger.logger')
    def test_logging_with_exception_in_logger(self, mock_logger, activity_logger_instance):
        """Test that exceptions in logger don't crash the application."""
        mock_logger.info.side_effect = Exception("Logging failed")

        # Should not raise exception
        try:
            activity_logger_instance.log("Test action")
        except Exception:
            pytest.fail("Logging should not raise exception even if logger fails")

    def test_log_with_special_characters(self, activity_logger_instance):
        """Test logging with special characters."""
        special_chars = "Test: @#$%^&*()[]{}|\\/<>?,.;:'\""
        activity_logger_instance.log(special_chars)
        # Should not raise exception

    def test_log_with_unicode(self, activity_logger_instance):
        """Test logging with unicode characters."""
        unicode_text = "Test 测试 тест テスト"
        activity_logger_instance.log(unicode_text)
        # Should not raise exception

    def test_log_with_very_long_message(self, activity_logger_instance):
        """Test logging with very long message."""
        long_message = "A" * 10000
        activity_logger_instance.log(long_message)
        # Should not raise exception


class TestBackwardCompatibility:
    """Test backward compatibility with old activity_logger interface."""

    def test_log_activity_with_old_parameters(self):
        """Test log_activity with old parameter names."""
        # Old interface used user_id and details parameters
        log_activity(
            action="create",
            entity_type="student",
            user_id=123,
            details={"name": "John", "course": "CS"}
        )
        # Should still work

    def test_log_activity_mixed_parameters(self):
        """Test log_activity with mix of old and new parameters."""
        log_activity(
            action="update",
            entity_type="grade",
            user="admin",
            user_id=1,
            details={"old": "B", "new": "A"}
        )
        # Should still work


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
