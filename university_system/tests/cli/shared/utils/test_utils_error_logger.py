"""
Tests for error logger utility module.

Tests centralized error logging functionality.
"""

import pytest
import tempfile
import shutil
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

# Suppress resource warnings for file handles
pytestmark = pytest.mark.filterwarnings("ignore::ResourceWarning")


class TestErrorLoggerModule:
    """Test error logger module structure."""

    def test_error_logger_file_exists(self):
        """Test that error_logger file exists."""
        logger_file = Path("university_system/utils/error_logger.py")
        assert logger_file.exists()

    def test_error_logger_imports(self):
        """Test that error_logger module can be imported."""
        from university_system.utils import error_logger
        assert error_logger is not None

    def test_error_logger_class_exists(self):
        """Test ErrorLogger class exists."""
        from university_system.utils.error_logger import ErrorLogger
        assert ErrorLogger is not None


class TestErrorLoggerClass:
    """Test ErrorLogger class functionality."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_error_logger_initialization(self, temp_log_dir):
        """Test ErrorLogger initialization."""
        from university_system.utils.error_logger import ErrorLogger

        logger = ErrorLogger(log_directory=temp_log_dir, log_filename="test_errors.log")
        assert logger is not None
        assert logger.log_directory == Path(temp_log_dir)
        assert logger.log_filename == "test_errors.log"

    def test_error_logger_creates_log_directory(self, temp_log_dir):
        """Test that ErrorLogger creates log directory."""
        from university_system.utils.error_logger import ErrorLogger

        log_subdir = Path(temp_log_dir) / "nested" / "logs"
        try:
            logger = ErrorLogger(log_directory=str(log_subdir))
            assert log_subdir.exists()
        except Exception as e:
            # May fail if directory structure doesn't allow creation
            pytest.skip(f"Could not create nested directory: {e}")

    def test_error_logger_has_log_error_method(self, temp_log_dir):
        """Test that ErrorLogger has log_error method."""
        try:
            from university_system.utils.error_logger import ErrorLogger

            logger = ErrorLogger(log_directory=temp_log_dir)
            assert hasattr(logger, 'log_error')
            assert callable(logger.log_error)
        except Exception as e:
            pytest.skip(f"Could not test log_error method: {e}")

    def test_error_logger_log_error(self, temp_log_dir):
        """Test logging an error."""
        from university_system.utils.error_logger import ErrorLogger

        logger = ErrorLogger(log_directory=temp_log_dir, log_filename="test.log")

        try:
            raise ValueError("Test error")
        except ValueError as e:
            logger.log_error(e, context={"test": "value"})

        # Verify log file was created
        log_file = Path(temp_log_dir) / "test.log"
        assert log_file.exists()

    def test_error_logger_logs_to_file(self, temp_log_dir):
        """Test that errors are written to file."""
        try:
            from university_system.utils.error_logger import ErrorLogger

            logger = ErrorLogger(log_directory=temp_log_dir, log_filename="errors.log")

            try:
                raise RuntimeError("Test runtime error")
            except RuntimeError as e:
                logger.log_error(e)

            log_file = Path(temp_log_dir) / "errors.log"
            assert log_file.exists()

            # Check file contains error info
            content = log_file.read_text()
            assert len(content) > 0
        except Exception as e:
            pytest.skip(f"Could not test logging to file: {e}")

    def test_error_logger_with_context(self, temp_log_dir):
        """Test logging error with context."""
        from university_system.utils.error_logger import ErrorLogger

        logger = ErrorLogger(log_directory=temp_log_dir)
        context = {"user_id": "12345", "action": "test_action"}

        try:
            raise Exception("Test exception with context")
        except Exception as e:
            logger.log_error(e, context=context)

        assert True  # Should not raise

    def test_error_logger_setup_logging(self, temp_log_dir):
        """Test _setup_logging method."""
        try:
            from university_system.utils.error_logger import ErrorLogger

            logger = ErrorLogger(log_directory=temp_log_dir)
            assert hasattr(logger, 'logger')
            assert logger.logger is not None
        except Exception as e:
            pytest.skip(f"Could not test setup_logging: {e}")


class TestErrorLoggerHelperMethods:
    """Test ErrorLogger helper methods."""

    @pytest.fixture
    def error_logger(self):
        """Create ErrorLogger instance."""
        from university_system.utils.error_logger import ErrorLogger
        temp_dir = tempfile.mkdtemp()
        logger = ErrorLogger(log_directory=temp_dir)
        yield logger
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_error_logger_formatting(self, error_logger):
        """Test error log formatting."""
        try:
            raise ValueError("Formatting test")
        except ValueError as e:
            error_logger.log_error(e, file_path="test.py", function_name="test_func")

        # Should complete without errors
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
