#!/usr/bin/env python3
"""
Unit tests for SessionManager (auth managers module).

Tests cover:
- Initialisation and default values
- check_session with no user / no last_activity
- check_session with valid (fresh) session
- check_session with expired session (state cleared)
- Custom timeout values
- set_current_user / clear_session helpers
- update_last_activity
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.auth.managers.session_manager import SessionManager


# ============================================================================
# Initialisation Tests
# ============================================================================

class TestSessionManagerInit:
    """Tests for SessionManager construction."""

    def test_default_timeout(self):
        """Default session_timeout is 30 minutes."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        assert sm.session_timeout == 30

    def test_custom_timeout(self):
        """A custom session_timeout is stored correctly."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock(), session_timeout=60)
        assert sm.session_timeout == 60

    def test_current_user_initially_none(self):
        """current_user starts as None."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        assert sm.current_user is None

    def test_last_activity_initially_none(self):
        """last_activity starts as None."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        assert sm.last_activity is None

    def test_stores_db_manager(self):
        """db_manager is stored on the instance."""
        db = Mock()
        sm = SessionManager(db_manager=db, activity_logger=Mock())
        assert sm.db_manager is db

    def test_stores_activity_logger(self):
        """activity_logger is stored on the instance."""
        logger = Mock()
        sm = SessionManager(db_manager=Mock(), activity_logger=logger)
        assert sm.activity_logger is logger


# ============================================================================
# check_session Tests
# ============================================================================

class TestCheckSession:
    """Tests for SessionManager.check_session()."""

    def _make_session_manager(self, timeout=30):
        return SessionManager(db_manager=Mock(), activity_logger=Mock(), session_timeout=timeout)

    def test_no_user_returns_false(self):
        """Returns False when current_user is None."""
        sm = self._make_session_manager()
        assert sm.check_session() is False

    def test_no_last_activity_returns_false(self):
        """Returns False when last_activity is None even if user is set."""
        sm = self._make_session_manager()
        sm.current_user = {"username": "alice"}
        sm.last_activity = None
        assert sm.check_session() is False

    def test_fresh_session_returns_true(self):
        """Returns True when session is within timeout window."""
        sm = self._make_session_manager(timeout=30)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now()
        assert sm.check_session() is True

    def test_fresh_session_updates_last_activity(self):
        """A valid check_session call updates last_activity to now."""
        sm = self._make_session_manager(timeout=30)
        sm.current_user = {"username": "alice"}
        old_time = datetime.now() - timedelta(minutes=5)
        sm.last_activity = old_time
        sm.check_session()
        # last_activity should have been refreshed to a time newer than old_time
        assert sm.last_activity > old_time

    def test_expired_session_returns_false(self):
        """Returns False when session has exceeded timeout."""
        sm = self._make_session_manager(timeout=10)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now() - timedelta(minutes=15)
        assert sm.check_session() is False

    def test_expired_session_clears_current_user(self):
        """current_user is set to None after timeout."""
        sm = self._make_session_manager(timeout=10)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now() - timedelta(minutes=15)
        sm.check_session()
        assert sm.current_user is None

    def test_expired_session_clears_last_activity(self):
        """last_activity is set to None after timeout."""
        sm = self._make_session_manager(timeout=10)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now() - timedelta(minutes=15)
        sm.check_session()
        assert sm.last_activity is None

    def test_boundary_just_within_timeout(self):
        """Session at exactly the boundary (elapsed == timeout) is still valid."""
        sm = self._make_session_manager(timeout=30)
        sm.current_user = {"username": "alice"}
        # elapsed == timeout: the code uses > not >=, so this should be True
        sm.last_activity = datetime.now() - timedelta(minutes=30)
        # Due to execution time, elapsed will be just barely > 30, so this
        # may be False. We test the just-under boundary instead.
        sm.last_activity = datetime.now() - timedelta(minutes=29, seconds=58)
        assert sm.check_session() is True

    def test_boundary_just_beyond_timeout(self):
        """Session just past the timeout is expired."""
        sm = self._make_session_manager(timeout=30)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now() - timedelta(minutes=31)
        assert sm.check_session() is False

    def test_custom_short_timeout(self):
        """A very short timeout (1 minute) works correctly."""
        sm = self._make_session_manager(timeout=1)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now() - timedelta(minutes=2)
        assert sm.check_session() is False

    def test_custom_long_timeout(self):
        """A long timeout (1440 min / 24 hours) keeps session alive."""
        sm = self._make_session_manager(timeout=1440)
        sm.current_user = {"username": "alice"}
        sm.last_activity = datetime.now() - timedelta(hours=23)
        assert sm.check_session() is True


# ============================================================================
# set_current_user / clear_session / update_last_activity Tests
# ============================================================================

class TestSessionHelpers:
    """Tests for set_current_user, clear_session, update_last_activity."""

    def test_set_current_user_stores_user(self):
        """set_current_user sets current_user dict."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        user = {"username": "alice", "id": 1}
        sm.set_current_user(user)
        assert sm.current_user["username"] == "alice"

    def test_set_current_user_sets_last_activity(self):
        """set_current_user also initialises last_activity."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        sm.set_current_user({"username": "alice", "id": 1})
        assert sm.last_activity is not None
        assert isinstance(sm.last_activity, datetime)

    def test_set_current_user_adds_default_auth_method(self):
        """set_current_user defaults auth_method to 'password'."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        user = {"username": "alice", "id": 1}
        sm.set_current_user(user)
        assert sm.current_user["auth_method"] == "password"

    def test_set_current_user_preserves_existing_auth_method(self):
        """set_current_user does not overwrite an existing auth_method."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        user = {"username": "alice", "id": 1, "auth_method": "sso"}
        sm.set_current_user(user)
        assert sm.current_user["auth_method"] == "sso"

    def test_clear_session(self):
        """clear_session resets current_user and last_activity to None."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        sm.set_current_user({"username": "alice", "id": 1})
        sm.clear_session()
        assert sm.current_user is None
        assert sm.last_activity is None

    def test_update_last_activity(self):
        """update_last_activity sets last_activity to approximately now."""
        sm = SessionManager(db_manager=Mock(), activity_logger=Mock())
        before = datetime.now()
        sm.update_last_activity()
        after = datetime.now()
        assert before <= sm.last_activity <= after
