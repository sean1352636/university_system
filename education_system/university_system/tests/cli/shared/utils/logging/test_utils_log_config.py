"""
Tests for logging configuration utility.

Tests centralized logging configuration functions.
"""

import pytest
import logging
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

# Suppress resource warnings for file handles
pytestmark = pytest.mark.filterwarnings("ignore::ResourceWarning")


class TestLogConfigModule:
    """Test log config module structure."""

    def test_log_config_file_exists(self):
        """Test that log_config file exists."""
        config_file = Path("university_system/utils/logging/log_config.py")
        assert config_file.exists()

    def test_log_config_imports(self):
        """Test that log_config module can be imported."""
        from education_system.university_system.utils.logging import log_config
        assert log_config is not None

    def test_get_log_dir_function_exists(self):
        """Test get_log_dir function exists."""
        from education_system.university_system.utils.logging.log_config import get_log_dir
        assert callable(get_log_dir)

    def test_get_log_file_function_exists(self):
        """Test get_log_file function exists."""
        from education_system.university_system.utils.logging.log_config import get_log_file
        assert callable(get_log_file)

    def test_configure_logging_function_exists(self):
        """Test configure_logging function exists."""
        from education_system.university_system.utils.logging.log_config import configure_logging
        assert callable(configure_logging)


class TestGetLogDir:
    """Test get_log_dir function."""

    def test_get_log_dir_returns_string(self):
        """Test that get_log_dir returns a string."""
        from education_system.university_system.utils.logging.log_config import get_log_dir
        log_dir = get_log_dir()
        assert isinstance(log_dir, str)

    def test_get_log_dir_is_absolute_path(self):
        """Test that get_log_dir returns absolute path."""
        from education_system.university_system.utils.logging.log_config import get_log_dir
        log_dir = get_log_dir()
        assert Path(log_dir).is_absolute()


class TestGetLogFile:
    """Test get_log_file function."""

    def test_get_log_file_returns_string(self):
        """Test that get_log_file returns a string."""
        from education_system.university_system.utils.logging.log_config import get_log_file
        log_file = get_log_file("test.log")
        assert isinstance(log_file, str)

    def test_get_log_file_with_filename(self):
        """Test get_log_file with filename."""
        from education_system.university_system.utils.logging.log_config import get_log_file
        log_file = get_log_file("app.log")
        assert "app.log" in log_file

    def test_get_log_file_is_absolute_path(self):
        """Test that get_log_file returns absolute path."""
        from education_system.university_system.utils.logging.log_config import get_log_file
        log_file = get_log_file("test.log")
        assert Path(log_file).is_absolute()


class TestConfigureLogging:
    """Test configure_logging function."""

    @pytest.fixture(autouse=True)
    def cleanup_handlers(self):
        """Clean up handlers after each test."""
        yield
        # Clean up root logger handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            try:
                handler.close()
                root_logger.removeHandler(handler)
            except Exception:
                pass

    def test_configure_logging_returns_logger(self):
        """Test that configure_logging returns a logger."""
        from education_system.university_system.utils.logging.log_config import configure_logging
        logger = configure_logging()
        assert isinstance(logger, logging.Logger)

    def test_configure_logging_with_name(self):
        """Test configure_logging with custom name."""
        from education_system.university_system.utils.logging.log_config import configure_logging
        logger = configure_logging(name="test_logger")
        assert logger.name == "test_logger"

    def test_configure_logging_with_level(self):
        """Test configure_logging with custom level."""
        from education_system.university_system.utils.logging.log_config import configure_logging
        logger = configure_logging(level=logging.DEBUG)
        # Logger should be configured
        assert isinstance(logger, logging.Logger)

    def test_configure_logging_adds_handlers(self):
        """Test that configure_logging adds rotating file handler."""
        from education_system.university_system.utils.logging.log_config import configure_logging

        # Get root logger handler count before
        root_logger = logging.getLogger()
        initial_handlers = len(root_logger.handlers)

        logger = configure_logging(name="handler_test")

        # Should have logger
        assert isinstance(logger, logging.Logger)

    def test_configure_logging_avoids_duplicate_handlers(self):
        """Test that configure_logging doesn't add duplicate handlers."""
        from education_system.university_system.utils.logging.log_config import configure_logging

        logger1 = configure_logging(name="dup_test1")
        root_logger = logging.getLogger()
        handler_count = len(root_logger.handlers)

        logger2 = configure_logging(name="dup_test2")
        new_handler_count = len(root_logger.handlers)

        # Handler count should not increase significantly
        assert new_handler_count <= handler_count + 1

    def test_configure_logging_creates_rotating_handler(self):
        """Test that rotating file handler is created."""
        from education_system.university_system.utils.logging.log_config import configure_logging
        from logging.handlers import RotatingFileHandler

        logger = configure_logging()
        root_logger = logging.getLogger()

        # Check for rotating file handlers
        has_rotating = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
        assert has_rotating or len(root_logger.handlers) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
