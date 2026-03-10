#!/usr/bin/env python3
"""
Unit tests for password_manager module.

Tests cover:
- Password hashing with PBKDF2-SHA256 (1M iterations)
- Password verification
- Temporary password generation
- Password change (DB-backed, mocked)
- Password reset (DB-backed, mocked)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from contextlib import contextmanager

from education_system.university_system.infrastructure.auth.managers.password_manager import (
    hash_password,
    verify_password,
    generate_temp_password,
    change_user_password,
    reset_user_password,
)


# ============================================================================
# hash_password Tests
# ============================================================================

class TestHashPassword:
    """Tests for hash_password()."""

    def test_returns_tuple_of_two_strings(self):
        """hash_password returns a (salt, hash) tuple of strings."""
        salt, hashed = hash_password("TestPass1!")
        assert isinstance(salt, str)
        assert isinstance(hashed, str)

    def test_salt_length_is_32_hex_chars(self):
        """Generated salt is 32 hex characters (16 bytes)."""
        salt, _ = hash_password("TestPass1!")
        assert len(salt) == 32

    def test_hash_length_is_128_hex_chars(self):
        """Hash output is 128 hex characters (64 bytes)."""
        _, hashed = hash_password("TestPass1!")
        assert len(hashed) == 128

    def test_salt_is_valid_hex(self):
        """Salt string contains only valid hex digits."""
        salt, _ = hash_password("TestPass1!")
        int(salt, 16)  # raises ValueError if not hex

    def test_hash_is_valid_hex(self):
        """Hash string contains only valid hex digits."""
        _, hashed = hash_password("TestPass1!")
        int(hashed, 16)  # raises ValueError if not hex

    def test_same_password_same_salt_produces_same_hash(self):
        """Hashing the same password with the same salt is deterministic."""
        salt, hash1 = hash_password("TestPass1!")
        _, hash2 = hash_password("TestPass1!", salt)
        assert hash1 == hash2

    def test_same_password_different_salt_produces_different_hash(self):
        """Different salts produce different hashes for the same password."""
        salt1, hash1 = hash_password("TestPass1!")
        salt2, hash2 = hash_password("TestPass1!")
        # Two random salts are astronomically unlikely to collide
        if salt1 != salt2:
            assert hash1 != hash2

    def test_different_passwords_same_salt_produce_different_hashes(self):
        """Different passwords with the same salt produce different hashes."""
        salt, hash1 = hash_password("PasswordA1!")
        _, hash2 = hash_password("PasswordB2!", salt)
        assert hash1 != hash2

    def test_explicit_salt_is_used(self):
        """When salt is provided, it is returned as-is."""
        explicit_salt = "a" * 32
        returned_salt, _ = hash_password("TestPass1!", explicit_salt)
        assert returned_salt == explicit_salt

    def test_auto_generated_salt_differs_between_calls(self):
        """Each call without explicit salt generates a unique salt."""
        salt1, _ = hash_password("TestPass1!")
        salt2, _ = hash_password("TestPass1!")
        assert salt1 != salt2


# ============================================================================
# verify_password Tests
# ============================================================================

class TestVerifyPassword:
    """Tests for verify_password()."""

    def test_correct_password_returns_true(self):
        """Verifying the correct password returns True."""
        salt, hashed = hash_password("Correct1!")
        assert verify_password("Correct1!", salt, hashed) is True

    def test_wrong_password_returns_false(self):
        """Verifying an incorrect password returns False."""
        salt, hashed = hash_password("Correct1!")
        assert verify_password("Wrong1!xx", salt, hashed) is False

    def test_empty_password_returns_false(self):
        """Verifying an empty string against a real hash returns False."""
        salt, hashed = hash_password("Correct1!")
        assert verify_password("", salt, hashed) is False

    def test_wrong_salt_returns_false(self):
        """Verifying with a different salt returns False."""
        salt, hashed = hash_password("Correct1!")
        bad_salt = "b" * 32
        assert verify_password("Correct1!", bad_salt, hashed) is False


# ============================================================================
# generate_temp_password Tests
# ============================================================================

class TestGenerateTempPassword:
    """Tests for generate_temp_password()."""

    def test_returns_string(self):
        """Temp password is a string."""
        result = generate_temp_password()
        assert isinstance(result, str)

    def test_length_is_twelve(self):
        """Temp password has exactly 12 characters."""
        result = generate_temp_password()
        assert len(result) == 12

    def test_chars_from_expected_alphabet(self):
        """All characters come from the defined character set."""
        alphabet = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*")
        for _ in range(20):
            pwd = generate_temp_password()
            assert set(pwd).issubset(alphabet)

    def test_generates_different_passwords(self):
        """Successive calls return different passwords."""
        passwords = {generate_temp_password() for _ in range(10)}
        # With 12-char passwords from a 70-char alphabet, collisions are near-impossible
        assert len(passwords) == 10


# ============================================================================
# change_user_password Tests (mocked DB)
# ============================================================================

class TestChangeUserPassword:
    """Tests for change_user_password() with mocked database."""

    def _make_db_manager(self, user_row=None):
        """Create a mock db_manager whose cursor returns *user_row* for the SELECT."""
        cursor = MagicMock()
        cursor.fetchone.return_value = user_row

        conn = MagicMock()
        conn.cursor.return_value = cursor
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)

        db_manager = Mock()
        db_manager.get_connection.return_value = conn
        return db_manager, conn, cursor

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.verify_password", return_value=True)
    @patch("university_system.infrastructure.auth.managers.password_manager.validate_password", return_value=True)
    def test_successful_password_change(self, mock_validate, mock_verify, mock_hash):
        """Password change succeeds when old password is correct and new is valid."""
        mock_hash.return_value = ("newsalt", "newhash")
        db_manager, conn, cursor = self._make_db_manager(
            user_row=(1, 10, "oldhash", "oldsalt")
        )

        result = change_user_password(db_manager, "alice", "OldPass1!", "NewPass1!")
        assert result is True
        conn.commit.assert_called_once()

    @patch("university_system.infrastructure.auth.managers.password_manager.validate_password", return_value=False)
    def test_invalid_new_password_returns_false(self, mock_validate):
        """Returns False when new password fails validation."""
        db_manager = Mock()
        result = change_user_password(db_manager, "alice", "OldPass1!", "short")
        assert result is False

    @patch("university_system.infrastructure.auth.managers.password_manager.validate_password", return_value=True)
    def test_user_not_found_returns_false(self, mock_validate):
        """Returns False when user does not exist in DB."""
        db_manager, conn, cursor = self._make_db_manager(user_row=None)
        result = change_user_password(db_manager, "ghost", "OldPass1!", "NewPass1!")
        assert result is False

    @patch("university_system.infrastructure.auth.managers.password_manager.verify_password", return_value=False)
    @patch("university_system.infrastructure.auth.managers.password_manager.validate_password", return_value=True)
    def test_wrong_current_password_returns_false(self, mock_validate, mock_verify):
        """Returns False when old password does not match stored hash."""
        db_manager, conn, cursor = self._make_db_manager(
            user_row=(1, 10, "oldhash", "oldsalt")
        )
        result = change_user_password(db_manager, "alice", "WrongOld1!", "NewPass1!")
        assert result is False
        conn.commit.assert_not_called()

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.verify_password", return_value=True)
    @patch("university_system.infrastructure.auth.managers.password_manager.validate_password", return_value=True)
    def test_activity_logger_called_on_success(self, mock_validate, mock_verify, mock_hash):
        """log_activity_func is called when password change succeeds."""
        mock_hash.return_value = ("newsalt", "newhash")
        db_manager, conn, cursor = self._make_db_manager(
            user_row=(1, 10, "oldhash", "oldsalt")
        )

        log_func = Mock()
        change_user_password(db_manager, "alice", "OldPass1!", "NewPass1!",
                             log_activity_func=log_func)
        log_func.assert_called_once_with("alice", "Password changed", None, 10)

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.verify_password", return_value=True)
    @patch("university_system.infrastructure.auth.managers.password_manager.validate_password", return_value=True)
    def test_current_user_flag_cleared(self, mock_validate, mock_verify, mock_hash):
        """password_reset_required is set to 0 on the current_user dict."""
        mock_hash.return_value = ("newsalt", "newhash")
        db_manager, conn, cursor = self._make_db_manager(
            user_row=(1, 10, "oldhash", "oldsalt")
        )
        current_user = {"id": 10, "password_reset_required": 1}
        change_user_password(db_manager, "alice", "OldPass1!", "NewPass1!",
                             current_user=current_user)
        assert current_user["password_reset_required"] == 0


# ============================================================================
# reset_user_password Tests (mocked DB)
# ============================================================================

class TestResetUserPassword:
    """Tests for reset_user_password() with mocked database."""

    def _make_mock_conn(self, user_row=None, student_row=None):
        """Build a mock connection whose cursor returns user_row then student_row."""
        cursor = MagicMock()
        cursor.fetchone.side_effect = [user_row, student_row]

        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn, cursor

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.generate_temp_password",
           return_value="TempPass123!")
    def test_successful_reset(self, mock_temp, mock_hash):
        """Returns (True, temp_password) on successful reset."""
        mock_hash.return_value = ("newsalt", "newhash")
        conn, cursor = self._make_mock_conn(
            user_row=(1, 10),
            student_row=None,
        )
        db_manager = Mock()
        db_manager._create_configured_connection.return_value = conn

        admin_user = {"id": 99, "username": "admin", "permissions": ["manage_users"]}
        success, temp = reset_user_password(db_manager, "alice", admin_user=admin_user)

        assert success is True
        assert temp == "TempPass123!"
        conn.commit.assert_called_once()

    def test_no_permission_returns_false(self):
        """Returns (False, None) when admin lacks manage_users permission."""
        db_manager = Mock()
        admin_user = {"id": 99, "username": "admin", "permissions": []}
        success, temp = reset_user_password(db_manager, "alice", admin_user=admin_user)
        assert success is False
        assert temp is None

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.generate_temp_password",
           return_value="TempPass123!")
    def test_user_not_found_returns_false(self, mock_temp, mock_hash):
        """Returns (False, None) when target user does not exist."""
        conn, cursor = self._make_mock_conn(user_row=None)
        db_manager = Mock()
        db_manager._create_configured_connection.return_value = conn

        admin_user = {"id": 99, "username": "admin", "permissions": ["manage_users"]}
        success, temp = reset_user_password(db_manager, "ghost", admin_user=admin_user)

        assert success is False
        assert temp is None

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.generate_temp_password",
           return_value="TempPass123!")
    def test_activity_logger_called_on_success(self, mock_temp, mock_hash):
        """log_activity_func is invoked after a successful reset."""
        mock_hash.return_value = ("newsalt", "newhash")
        conn, cursor = self._make_mock_conn(user_row=(1, 10), student_row=None)
        db_manager = Mock()
        db_manager._create_configured_connection.return_value = conn

        log_func = Mock()
        admin_user = {"id": 99, "username": "admin", "permissions": ["manage_users"]}
        reset_user_password(db_manager, "alice", admin_user=admin_user,
                            log_activity_func=log_func)

        log_func.assert_called_once_with("admin", "Password reset for user: alice", None, 99)

    @patch("university_system.infrastructure.auth.managers.password_manager.hash_password")
    @patch("university_system.infrastructure.auth.managers.password_manager.generate_temp_password",
           return_value="TempPass123!")
    def test_uses_custom_connection_func(self, mock_temp, mock_hash):
        """Uses create_configured_connection_func when provided."""
        mock_hash.return_value = ("newsalt", "newhash")
        conn, cursor = self._make_mock_conn(user_row=(1, 10), student_row=None)
        custom_conn_func = Mock(return_value=conn)
        db_manager = Mock()

        admin_user = {"id": 99, "username": "admin", "permissions": ["manage_users"]}
        success, temp = reset_user_password(
            db_manager, "alice", admin_user=admin_user,
            create_configured_connection_func=custom_conn_func
        )

        assert success is True
        custom_conn_func.assert_called_once()
