"""Comprehensive tests for university_system.core.defaults module.

Tests environment variable overrides, password generation, default user
accounts, university info, and helper functions.
"""

import importlib
import os
import string

import pytest
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# _get_env / _get_env_int helpers
# ---------------------------------------------------------------------------

class TestGetEnv:
    """Tests for _get_env and _get_env_int helper functions."""

    def test_get_env_returns_default_when_not_set(self):
        from education_system.university_system.core.defaults import _get_env

        with patch.dict(os.environ, {}, clear=True):
            result = _get_env("NONEXISTENT_VAR_123456", "fallback")
            assert result == "fallback"

    def test_get_env_returns_env_value_when_set(self):
        from education_system.university_system.core.defaults import _get_env

        with patch.dict(os.environ, {"MY_TEST_VAR": "from_env"}):
            result = _get_env("MY_TEST_VAR", "default_val")
            assert result == "from_env"

    def test_get_env_int_returns_default_when_not_set(self):
        from education_system.university_system.core.defaults import _get_env_int

        with patch.dict(os.environ, {}, clear=True):
            result = _get_env_int("NONEXISTENT_INT_VAR", 42)
            assert result == 42

    def test_get_env_int_returns_env_value_as_int(self):
        from education_system.university_system.core.defaults import _get_env_int

        with patch.dict(os.environ, {"MY_INT_VAR": "99"}):
            result = _get_env_int("MY_INT_VAR", 10)
            assert result == 99

    def test_get_env_int_returns_default_on_invalid_value(self):
        from education_system.university_system.core.defaults import _get_env_int

        with patch.dict(os.environ, {"BAD_INT": "not_a_number"}):
            result = _get_env_int("BAD_INT", 7)
            assert result == 7

    def test_get_env_int_returns_default_on_empty_string(self):
        from education_system.university_system.core.defaults import _get_env_int

        with patch.dict(os.environ, {"EMPTY_INT": ""}):
            result = _get_env_int("EMPTY_INT", 5)
            assert result == 5

    def test_get_env_int_handles_negative(self):
        from education_system.university_system.core.defaults import _get_env_int

        with patch.dict(os.environ, {"NEG_INT": "-10"}):
            result = _get_env_int("NEG_INT", 0)
            assert result == -10

    def test_get_env_int_handles_zero(self):
        from education_system.university_system.core.defaults import _get_env_int

        with patch.dict(os.environ, {"ZERO_INT": "0"}):
            result = _get_env_int("ZERO_INT", 99)
            assert result == 0


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------

class TestPasswordGeneration:
    """Tests for _generate_random_password."""

    def test_default_length_is_16(self):
        from education_system.university_system.core.defaults import _generate_random_password

        pwd = _generate_random_password()
        assert len(pwd) == 16

    def test_custom_length(self):
        from education_system.university_system.core.defaults import _generate_random_password

        pwd = _generate_random_password(length=32)
        assert len(pwd) == 32

    def test_contains_valid_characters(self):
        from education_system.university_system.core.defaults import _generate_random_password

        valid_chars = set(string.ascii_letters + string.digits + "!@#$%&*")
        pwd = _generate_random_password(length=100)
        for ch in pwd:
            assert ch in valid_chars, f"Unexpected character: {ch}"

    def test_randomness_produces_different_passwords(self):
        from education_system.university_system.core.defaults import _generate_random_password

        passwords = {_generate_random_password() for _ in range(20)}
        # With 16-char passwords, getting 20 unique is virtually certain
        assert len(passwords) == 20

    def test_length_zero(self):
        from education_system.university_system.core.defaults import _generate_random_password

        pwd = _generate_random_password(length=0)
        assert pwd == ""

    def test_length_one(self):
        from education_system.university_system.core.defaults import _generate_random_password

        pwd = _generate_random_password(length=1)
        assert len(pwd) == 1


# ---------------------------------------------------------------------------
# _require_password_env
# ---------------------------------------------------------------------------

class TestRequirePasswordEnv:
    """Tests for _require_password_env."""

    def test_returns_env_value_when_set(self):
        from education_system.university_system.core.defaults import _require_password_env

        with patch.dict(os.environ, {"TEST_PWD_VAR": "secret123"}):
            result = _require_password_env("TEST_PWD_VAR", "admin")
            assert result == "secret123"

    def test_generates_random_when_not_set(self):
        import education_system.university_system.core.defaults as defaults_mod

        # Clear generated passwords tracker
        defaults_mod._generated_passwords.clear()

        with patch.dict(os.environ, {}, clear=True):
            # Ensure our variable is not set
            os.environ.pop("MISSING_PWD_VAR", None)
            result = defaults_mod._require_password_env("MISSING_PWD_VAR", "test_role")

        assert len(result) == 16  # default length
        assert "test_role" in defaults_mod._generated_passwords

    def test_logs_warning_when_generating(self):
        import education_system.university_system.core.defaults as defaults_mod

        defaults_mod._generated_passwords.clear()

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WARN_PWD_VAR", None)
            with patch.object(defaults_mod._logger, 'warning') as mock_warn:
                defaults_mod._require_password_env("WARN_PWD_VAR", "my_role")
                mock_warn.assert_called_once()
                args = mock_warn.call_args[0]
                assert "WARN_PWD_VAR" in args[1]
                assert "my_role" in args[2]

    def test_does_not_generate_when_env_set(self):
        import education_system.university_system.core.defaults as defaults_mod

        defaults_mod._generated_passwords.clear()

        with patch.dict(os.environ, {"SET_PWD": "mypassword"}):
            result = defaults_mod._require_password_env("SET_PWD", "role")

        assert result == "mypassword"
        assert "role" not in defaults_mod._generated_passwords


# ---------------------------------------------------------------------------
# print_generated_passwords
# ---------------------------------------------------------------------------

class TestPrintGeneratedPasswords:
    """Tests for print_generated_passwords."""

    def test_prints_nothing_when_empty(self, capsys):
        import education_system.university_system.core.defaults as defaults_mod

        defaults_mod._generated_passwords.clear()
        defaults_mod.print_generated_passwords()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_prints_and_clears_passwords(self, capsys):
        import education_system.university_system.core.defaults as defaults_mod

        defaults_mod._generated_passwords.clear()
        defaults_mod._generated_passwords["admin"] = "gen_pwd_123"
        defaults_mod._generated_passwords["staff"] = "gen_pwd_456"

        defaults_mod.print_generated_passwords()

        captured = capsys.readouterr()
        assert "DEFAULT_ADMIN_PASSWORD=gen_pwd_123" in captured.out
        assert "DEFAULT_STAFF_PASSWORD=gen_pwd_456" in captured.out
        assert "WARNING" in captured.out

        # Passwords should be cleared after printing
        assert len(defaults_mod._generated_passwords) == 0

    def test_prints_border_and_instructions(self, capsys):
        import education_system.university_system.core.defaults as defaults_mod

        defaults_mod._generated_passwords.clear()
        defaults_mod._generated_passwords["test_role"] = "xyz"

        defaults_mod.print_generated_passwords()

        captured = capsys.readouterr()
        assert "=" * 68 in captured.out
        assert ".env" in captured.out
        assert "restart" in captured.out.lower()


# ---------------------------------------------------------------------------
# Module-level default constants (using env var overrides)
# ---------------------------------------------------------------------------

class TestDefaultConstants:
    """Tests for module-level default constants."""

    def test_default_admin_values(self):
        """Test that default admin values match expected defaults."""
        from education_system.university_system.core.defaults import (
            DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL,
            DEFAULT_ADMIN_FIRST_NAME, DEFAULT_ADMIN_LAST_NAME,
        )
        # These are the defaults unless env vars are set.
        # We check they are strings and non-empty.
        assert isinstance(DEFAULT_ADMIN_USERNAME, str)
        assert len(DEFAULT_ADMIN_USERNAME) > 0
        assert isinstance(DEFAULT_ADMIN_EMAIL, str)
        assert "@" in DEFAULT_ADMIN_EMAIL
        assert isinstance(DEFAULT_ADMIN_FIRST_NAME, str)
        assert isinstance(DEFAULT_ADMIN_LAST_NAME, str)

    def test_default_student_values(self):
        from education_system.university_system.core.defaults import (
            DEFAULT_STUDENT_ID, DEFAULT_STUDENT_USERNAME,
            DEFAULT_STUDENT_EMAIL, DEFAULT_STUDENT_FIRST_NAME,
            DEFAULT_STUDENT_LAST_NAME,
        )

        assert isinstance(DEFAULT_STUDENT_ID, str)
        assert len(DEFAULT_STUDENT_ID) > 0
        assert isinstance(DEFAULT_STUDENT_USERNAME, str)
        assert isinstance(DEFAULT_STUDENT_EMAIL, str)
        assert "@" in DEFAULT_STUDENT_EMAIL
        assert isinstance(DEFAULT_STUDENT_FIRST_NAME, str)
        assert isinstance(DEFAULT_STUDENT_LAST_NAME, str)

    def test_university_name_is_string(self):
        from education_system.university_system.core.defaults import UNIVERSITY_NAME

        assert isinstance(UNIVERSITY_NAME, str)
        assert len(UNIVERSITY_NAME) > 0

    def test_university_email_domain(self):
        from education_system.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN

        assert isinstance(UNIVERSITY_EMAIL_DOMAIN, str)
        assert "." in UNIVERSITY_EMAIL_DOMAIN

    def test_noreply_email_contains_domain(self):
        from education_system.university_system.core.defaults import (
            UNIVERSITY_NOREPLY_EMAIL, UNIVERSITY_EMAIL_DOMAIN
        )

        assert UNIVERSITY_EMAIL_DOMAIN in UNIVERSITY_NOREPLY_EMAIL
        assert "noreply" in UNIVERSITY_NOREPLY_EMAIL.lower()

    def test_demo_mode_is_bool(self):
        from education_system.university_system.core.defaults import DEMO_MODE

        assert isinstance(DEMO_MODE, bool)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """Tests for get_admin_email, get_fallback_email, get_default_student_data, get_default_admin_data."""

    def test_get_admin_email(self):
        from education_system.university_system.core.defaults import get_admin_email, SYSTEM_ADMIN_EMAIL

        result = get_admin_email()
        assert result == SYSTEM_ADMIN_EMAIL

    def test_get_fallback_email_admin(self):
        from education_system.university_system.core.defaults import get_fallback_email, SYSTEM_ADMIN_EMAIL

        result = get_fallback_email("admin")
        assert result == SYSTEM_ADMIN_EMAIL

    def test_get_fallback_email_support(self):
        from education_system.university_system.core.defaults import get_fallback_email, SYSTEM_SUPPORT_EMAIL

        result = get_fallback_email("support")
        assert result == SYSTEM_SUPPORT_EMAIL

    def test_get_fallback_email_noreply(self):
        from education_system.university_system.core.defaults import get_fallback_email, UNIVERSITY_NOREPLY_EMAIL

        result = get_fallback_email("noreply")
        assert result == UNIVERSITY_NOREPLY_EMAIL

    def test_get_fallback_email_unknown_context(self):
        from education_system.university_system.core.defaults import get_fallback_email, SYSTEM_ADMIN_EMAIL

        result = get_fallback_email("unknown_context")
        assert result == SYSTEM_ADMIN_EMAIL

    def test_get_fallback_email_default_context(self):
        from education_system.university_system.core.defaults import get_fallback_email, SYSTEM_ADMIN_EMAIL

        result = get_fallback_email()
        assert result == SYSTEM_ADMIN_EMAIL

    def test_get_default_student_data_returns_dict(self):
        from education_system.university_system.core.defaults import get_default_student_data

        data = get_default_student_data()
        assert isinstance(data, dict)
        assert "student_id" in data
        assert "username" in data
        assert "email" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "password" in data

    def test_get_default_student_data_values(self):
        from education_system.university_system.core.defaults import (
            get_default_student_data, DEFAULT_STUDENT_ID,
            DEFAULT_STUDENT_USERNAME, DEFAULT_STUDENT_EMAIL,
            DEFAULT_STUDENT_FIRST_NAME, DEFAULT_STUDENT_LAST_NAME,
            DEFAULT_STUDENT_PASSWORD,
        )

        data = get_default_student_data()
        assert data["student_id"] == DEFAULT_STUDENT_ID
        assert data["username"] == DEFAULT_STUDENT_USERNAME
        assert data["email"] == DEFAULT_STUDENT_EMAIL
        assert data["first_name"] == DEFAULT_STUDENT_FIRST_NAME
        assert data["last_name"] == DEFAULT_STUDENT_LAST_NAME
        assert data["password"] == DEFAULT_STUDENT_PASSWORD

    def test_get_default_admin_data_returns_dict(self):
        from education_system.university_system.core.defaults import get_default_admin_data

        data = get_default_admin_data()
        assert isinstance(data, dict)
        assert "username" in data
        assert "email" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "password" in data

    def test_get_default_admin_data_values(self):
        from education_system.university_system.core.defaults import (
            get_default_admin_data, DEFAULT_ADMIN_USERNAME,
            DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_FIRST_NAME,
            DEFAULT_ADMIN_LAST_NAME, DEFAULT_ADMIN_PASSWORD,
        )

        data = get_default_admin_data()
        assert data["username"] == DEFAULT_ADMIN_USERNAME
        assert data["email"] == DEFAULT_ADMIN_EMAIL
        assert data["first_name"] == DEFAULT_ADMIN_FIRST_NAME
        assert data["last_name"] == DEFAULT_ADMIN_LAST_NAME
        assert data["password"] == DEFAULT_ADMIN_PASSWORD

    def test_get_default_student_data_returns_new_dict_each_call(self):
        """Each call should return a fresh dict (no shared mutable state)."""
        from education_system.university_system.core.defaults import get_default_student_data

        d1 = get_default_student_data()
        d2 = get_default_student_data()
        assert d1 == d2
        assert d1 is not d2

    def test_get_default_admin_data_returns_new_dict_each_call(self):
        from education_system.university_system.core.defaults import get_default_admin_data

        d1 = get_default_admin_data()
        d2 = get_default_admin_data()
        assert d1 == d2
        assert d1 is not d2


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------

class TestDefaultsAllExports:
    """Tests for __all__ exports."""

    def test_all_exports_are_importable(self):
        from education_system.university_system.core import defaults

        for name in defaults.__all__:
            assert hasattr(defaults, name), f"{name} listed in __all__ but not found"

    def test_all_includes_key_items(self):
        from education_system.university_system.core.defaults import __all__

        expected = [
            "DEFAULT_ADMIN_USERNAME", "DEFAULT_ADMIN_EMAIL",
            "DEFAULT_ADMIN_PASSWORD", "DEFAULT_STUDENT_ID",
            "DEFAULT_STUDENT_PASSWORD", "DEFAULT_STAFF_PASSWORD",
            "UNIVERSITY_NAME", "UNIVERSITY_EMAIL_DOMAIN",
            "DEMO_MODE", "get_admin_email", "get_fallback_email",
            "get_default_student_data", "get_default_admin_data",
            "print_generated_passwords",
        ]
        for name in expected:
            assert name in __all__, f"{name} missing from __all__"
