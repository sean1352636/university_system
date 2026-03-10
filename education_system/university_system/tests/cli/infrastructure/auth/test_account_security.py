#!/usr/bin/env python3
"""
Unit tests for AccountSecurityManager.

Tests cover:
- Initialisation with default and custom values
- increment_login_attempts tracking
- Account lockout after max_attempts
- Lockout expiry after lockout_time
- get_remaining_login_attempts
- get_lockout_time_remaining
- reset_login_attempts
- emergency_unlock
- list_locked_accounts
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.auth.managers.account_security import (
    AccountSecurityManager,
)


# ============================================================================
# Initialisation Tests
# ============================================================================

class TestAccountSecurityManagerInit:
    """Tests for AccountSecurityManager construction."""

    def test_default_max_attempts(self):
        """Default max_attempts is 5."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        assert asm.max_attempts == 5

    def test_default_lockout_time(self):
        """Default lockout_time is 15 minutes."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        assert asm.lockout_time == 15

    def test_custom_max_attempts(self):
        """Custom max_attempts is stored correctly."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        assert asm.max_attempts == 3

    def test_custom_lockout_time(self):
        """Custom lockout_time is stored correctly."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), lockout_time=30
        )
        assert asm.lockout_time == 30

    def test_login_attempts_initially_empty(self):
        """login_attempts dict starts empty."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        assert asm.login_attempts == {}

    def test_stores_db_manager(self):
        """db_manager reference is stored."""
        db = Mock()
        asm = AccountSecurityManager(db_manager=db, activity_logger=Mock())
        assert asm.db_manager is db

    def test_stores_activity_logger(self):
        """activity_logger reference is stored."""
        logger = Mock()
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=logger)
        assert asm.activity_logger is logger


# ============================================================================
# increment_login_attempts Tests
# ============================================================================

class TestIncrementLoginAttempts:
    """Tests for AccountSecurityManager.increment_login_attempts()."""

    def test_first_attempt_creates_entry(self):
        """First failed login creates an entry with count 1."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.increment_login_attempts("alice")
        attempts, _ = asm.login_attempts["alice"]
        assert attempts == 1

    def test_second_attempt_increments(self):
        """Second failed login increments count to 2."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.increment_login_attempts("alice")
        asm.increment_login_attempts("alice")
        attempts, _ = asm.login_attempts["alice"]
        assert attempts == 2

    def test_multiple_increments(self):
        """Multiple increments accumulate correctly."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        for _ in range(4):
            asm.increment_login_attempts("alice")
        attempts, _ = asm.login_attempts["alice"]
        assert attempts == 4

    def test_different_users_tracked_separately(self):
        """Attempts for different usernames are independent."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.increment_login_attempts("alice")
        asm.increment_login_attempts("alice")
        asm.increment_login_attempts("bob")

        alice_attempts, _ = asm.login_attempts["alice"]
        bob_attempts, _ = asm.login_attempts["bob"]
        assert alice_attempts == 2
        assert bob_attempts == 1

    def test_timestamp_is_updated(self):
        """Each increment updates the timestamp."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.increment_login_attempts("alice")
        _, first_time = asm.login_attempts["alice"]

        asm.increment_login_attempts("alice")
        _, second_time = asm.login_attempts["alice"]
        assert second_time >= first_time

    @patch(
        "university_system.infrastructure.auth.managers.account_security.SECURITY_ALERTS_AVAILABLE",
        True,
    )
    @patch(
        "university_system.infrastructure.auth.managers.account_security.alert_account_lockout",
    )
    def test_security_alert_on_lockout(self, mock_alert):
        """Security alert is triggered when attempts reach max_attempts."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        asm.increment_login_attempts("alice", ip_address="192.168.1.1")
        asm.increment_login_attempts("alice", ip_address="192.168.1.1")
        asm.increment_login_attempts("alice", ip_address="192.168.1.1")

        mock_alert.assert_called_once_with(
            user_id="alice",
            ip_address="192.168.1.1",
            failed_attempts=3,
            lockout_duration_minutes=asm.lockout_time,
        )

    @patch(
        "university_system.infrastructure.auth.managers.account_security.SECURITY_ALERTS_AVAILABLE",
        False,
    )
    def test_no_alert_when_alerts_unavailable(self):
        """No crash when SECURITY_ALERTS_AVAILABLE is False."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=2
        )
        # Should not raise even though alert module is "unavailable"
        asm.increment_login_attempts("alice")
        asm.increment_login_attempts("alice")
        attempts, _ = asm.login_attempts["alice"]
        assert attempts == 2


# ============================================================================
# get_remaining_login_attempts Tests
# ============================================================================

class TestGetRemainingLoginAttempts:
    """Tests for AccountSecurityManager.get_remaining_login_attempts()."""

    def test_no_attempts_returns_max(self):
        """Returns max_attempts when user has no recorded failures."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=5
        )
        assert asm.get_remaining_login_attempts("alice") == 5

    def test_after_one_attempt(self):
        """Returns max_attempts - 1 after one failure."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=5
        )
        asm.increment_login_attempts("alice")
        assert asm.get_remaining_login_attempts("alice") == 4

    def test_at_max_attempts_returns_zero(self):
        """Returns 0 when user has reached max_attempts."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        for _ in range(3):
            asm.increment_login_attempts("alice")
        assert asm.get_remaining_login_attempts("alice") == 0

    def test_beyond_max_attempts_still_zero(self):
        """Returns 0 when user exceeds max_attempts."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        for _ in range(5):
            asm.increment_login_attempts("alice")
        assert asm.get_remaining_login_attempts("alice") == 0

    def test_expired_lockout_resets_to_max(self):
        """Returns max_attempts after lockout period has expired."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3, lockout_time=15
        )
        for _ in range(3):
            asm.increment_login_attempts("alice")

        # Manually set the timestamp to the past
        asm.login_attempts["alice"] = (3, datetime.now() - timedelta(minutes=20))
        assert asm.get_remaining_login_attempts("alice") == 3


# ============================================================================
# get_lockout_time_remaining Tests
# ============================================================================

class TestGetLockoutTimeRemaining:
    """Tests for AccountSecurityManager.get_lockout_time_remaining()."""

    def test_no_attempts_returns_none(self):
        """Returns None when user has no recorded failures."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        assert asm.get_lockout_time_remaining("alice") is None

    def test_below_max_returns_none(self):
        """Returns None when attempts are below max."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=5
        )
        asm.increment_login_attempts("alice")
        assert asm.get_lockout_time_remaining("alice") is None

    def test_locked_returns_positive_minutes(self):
        """Returns positive integer minutes when account is locked."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3, lockout_time=15
        )
        for _ in range(3):
            asm.increment_login_attempts("alice")
        remaining = asm.get_lockout_time_remaining("alice")
        assert remaining is not None
        assert remaining > 0
        assert remaining <= 15

    def test_expired_lockout_returns_none(self):
        """Returns None after the lockout period has elapsed."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3, lockout_time=15
        )
        for _ in range(3):
            asm.increment_login_attempts("alice")

        asm.login_attempts["alice"] = (3, datetime.now() - timedelta(minutes=20))
        assert asm.get_lockout_time_remaining("alice") is None


# ============================================================================
# reset_login_attempts Tests
# ============================================================================

class TestResetLoginAttempts:
    """Tests for AccountSecurityManager.reset_login_attempts()."""

    def test_reset_clears_entry(self):
        """Resetting removes the user from login_attempts."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.increment_login_attempts("alice")
        asm.reset_login_attempts("alice")
        assert "alice" not in asm.login_attempts

    def test_reset_unknown_user_no_error(self):
        """Resetting a user who has no attempts does not raise."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.reset_login_attempts("ghost")  # should not raise

    def test_reset_only_affects_target_user(self):
        """Resetting one user does not affect another."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        asm.increment_login_attempts("alice")
        asm.increment_login_attempts("bob")
        asm.reset_login_attempts("alice")
        assert "alice" not in asm.login_attempts
        assert "bob" in asm.login_attempts


# ============================================================================
# emergency_unlock Tests
# ============================================================================

class TestEmergencyUnlock:
    """Tests for AccountSecurityManager.emergency_unlock()."""

    def _lock_user(self, asm, username, attempts=None):
        """Lock a user by exceeding max_attempts."""
        count = attempts or asm.max_attempts
        for _ in range(count):
            asm.increment_login_attempts(username)

    @patch.dict("os.environ", {"EMERGENCY_UNLOCK_PASSWORD": "TestUnlock123!"})
    def test_successful_unlock(self):
        """Account is unlocked with correct emergency password."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        self._lock_user(asm, "alice")

        result = asm.emergency_unlock("alice", "TestUnlock123!")
        assert result["success"] is True
        assert "alice" not in asm.login_attempts

    @patch.dict("os.environ", {"EMERGENCY_UNLOCK_PASSWORD": "TestUnlock123!"})
    def test_wrong_password_fails(self):
        """Returns failure with incorrect emergency password."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        self._lock_user(asm, "alice")

        result = asm.emergency_unlock("alice", "WrongPassword!")
        assert result["success"] is False
        assert "alice" in asm.login_attempts

    @patch.dict("os.environ", {"EMERGENCY_UNLOCK_PASSWORD": "TestUnlock123!"})
    def test_unlock_not_locked_user(self):
        """Returns failure when user is not actually locked out."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=5
        )
        result = asm.emergency_unlock("alice", "TestUnlock123!")
        assert result["success"] is False

    @patch.dict("os.environ", {"EMERGENCY_UNLOCK_PASSWORD": "TestUnlock123!"})
    def test_unlock_user_below_threshold(self):
        """Returns failure when user has attempts below max."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=5
        )
        asm.increment_login_attempts("alice")
        asm.increment_login_attempts("alice")
        result = asm.emergency_unlock("alice", "TestUnlock123!")
        assert result["success"] is False


# ============================================================================
# list_locked_accounts Tests
# ============================================================================

class TestListLockedAccounts:
    """Tests for AccountSecurityManager.list_locked_accounts()."""

    def test_no_locked_accounts(self):
        """Returns empty list when no accounts are locked."""
        asm = AccountSecurityManager(db_manager=Mock(), activity_logger=Mock())
        assert asm.list_locked_accounts() == []

    def test_locked_account_appears(self):
        """A locked account appears in the list."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3
        )
        for _ in range(3):
            asm.increment_login_attempts("alice")

        locked = asm.list_locked_accounts()
        assert len(locked) == 1
        assert locked[0]["username"] == "alice"
        assert locked[0]["failed_attempts"] == 3

    def test_below_threshold_not_listed(self):
        """Users below max_attempts are not listed as locked."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=5
        )
        asm.increment_login_attempts("alice")
        assert asm.list_locked_accounts() == []

    def test_expired_lockout_not_listed(self):
        """Accounts with expired lockouts are not listed."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=3, lockout_time=15
        )
        for _ in range(3):
            asm.increment_login_attempts("alice")

        asm.login_attempts["alice"] = (3, datetime.now() - timedelta(minutes=20))
        assert asm.list_locked_accounts() == []

    def test_multiple_locked_accounts(self):
        """Multiple locked accounts are all listed."""
        asm = AccountSecurityManager(
            db_manager=Mock(), activity_logger=Mock(), max_attempts=2
        )
        for _ in range(2):
            asm.increment_login_attempts("alice")
        for _ in range(2):
            asm.increment_login_attempts("bob")

        locked = asm.list_locked_accounts()
        usernames = {acct["username"] for acct in locked}
        assert usernames == {"alice", "bob"}
