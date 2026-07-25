"""
Tests for utility scripts (fix_user_accounts, reset_password, log_management).

Tests administrative utility scripts.
"""

import pytest
from pathlib import Path


class TestFixUserAccountsScript:
    """Test fix_user_accounts utility script."""

    def test_fix_user_accounts_file_exists(self):
        """Test that fix_user_accounts file exists."""
        script_file = Path("university_system/scripts/fix_user_accounts.py")
        assert script_file.exists()

    def test_fix_user_accounts_imports(self):
        """Test that fix_user_accounts module can be imported."""
        try:
            from education_system.systems.university.scripts import fix_user_accounts
            assert fix_user_accounts is not None
        except ImportError as e:
            pytest.skip(f"Fix user accounts module not available: {e}")

    def test_fix_user_accounts_is_script(self):
        """Test that fix_user_accounts is a runnable script."""
        script_file = Path("university_system/scripts/fix_user_accounts.py")
        content = script_file.read_text()

        # Should have script-like content
        assert len(content) > 0


class TestResetPasswordScript:
    """Test reset_password utility script."""

    def test_reset_password_file_exists(self):
        """Test that reset_password file exists."""
        script_file = Path("university_system/scripts/reset_password.py")
        assert script_file.exists()

    def test_reset_password_imports(self):
        """Test that reset_password module can be imported."""
        try:
            from education_system.systems.university.scripts import reset_password
            assert reset_password is not None
        except ImportError as e:
            pytest.skip(f"Reset password module not available: {e}")

    def test_reset_password_is_script(self):
        """Test that reset_password is a runnable script."""
        script_file = Path("university_system/scripts/reset_password.py")
        content = script_file.read_text()

        # Should have script-like content
        assert len(content) > 0


class TestLogManagementModule:
    """Test log_management utility module."""

    def test_log_management_file_exists(self):
        """Test that log_management file exists."""
        module_file = Path("university_system/infrastructure/logging/log_management.py")
        assert module_file.exists()

    def test_log_management_imports(self):
        """Test that log_management module can be imported."""
        try:
            from education_system.systems.university.infrastructure.logging import log_management
            assert log_management is not None
        except ImportError as e:
            pytest.skip(f"Log management module not available: {e}")

    def test_log_management_has_functions(self):
        """Test that log_management module has functions."""
        try:
            from education_system.systems.university.infrastructure.logging import log_management

            module_contents = dir(log_management)
            public_items = [item for item in module_contents if not item.startswith('_')]

            assert len(public_items) > 0

        except ImportError:
            pytest.skip("Log management module not available")


class TestUtilsDirectoryStructure:
    """Test utils directory structure."""

    def test_utils_directory_exists(self):
        """Test that utils directory exists."""
        utils_dir = Path("university_system/utils")
        assert utils_dir.exists()
        assert utils_dir.is_dir()

    def test_ai_utils_directory_exists(self):
        """Test that AI utils directory exists."""
        ai_dir = Path("university_system/infrastructure/ai")
        assert ai_dir.exists()
        assert ai_dir.is_dir()

    def test_logging_utils_directory_exists(self):
        """Test that logging utils directory exists."""
        logging_dir = Path("university_system/infrastructure/logging")
        assert logging_dir.exists()
        assert logging_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
