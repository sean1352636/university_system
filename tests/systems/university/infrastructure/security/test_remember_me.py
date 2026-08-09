"""
Comprehensive tests for remember_me module.

Tests cover:
- RememberMeToken dataclass
- RememberMeManager initialization and configuration
- _hash_token() SHA-256 hashing
- _generate_token() secure random token generation
- create_token() with DB operations, token limits
- verify_and_rotate_token() with expiration, fingerprint mismatch, rotation
- revoke_token() and revoke_all_user_tokens()
- cleanup_expired_tokens()
- get_user_tokens()
- initialize_database()
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from education_system.systems.university.infrastructure.security.remember_me import (
    RememberMeManager,
    RememberMeToken,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(**kwargs):
    """Create a RememberMeManager without hitting a real DB."""
    return RememberMeManager(**kwargs)


# ---------------------------------------------------------------------------
# RememberMeToken dataclass
# ---------------------------------------------------------------------------

class TestRememberMeToken:
    def test_creation(self):
        now = datetime.now()
        token = RememberMeToken(
            token_id="abc123",
            user_id=42,
            device_fingerprint="fp-xyz",
            created_at=now,
            expires_at=now + timedelta(days=30),
            last_used=None,
            use_count=0,
        )
        assert token.token_id == "abc123"
        assert token.user_id == 42
        assert token.use_count == 0
        assert token.last_used is None


# ---------------------------------------------------------------------------
# Manager init
# ---------------------------------------------------------------------------

class TestManagerInit:
    def test_default_values(self):
        mgr = _make_manager()
        assert mgr.token_lifetime_days == 30
        assert mgr.max_tokens_per_user == 5
        assert mgr.rotate_on_use is True

    def test_custom_values(self):
        mgr = _make_manager(token_lifetime_days=7, max_tokens_per_user=2, rotate_on_use=False)
        assert mgr.token_lifetime_days == 7
        assert mgr.max_tokens_per_user == 2
        assert mgr.rotate_on_use is False


# ---------------------------------------------------------------------------
# _hash_token
# ---------------------------------------------------------------------------

class TestHashToken:
    def test_returns_sha256_hex(self):
        mgr = _make_manager()
        result = mgr._hash_token("test_token")
        expected = hashlib.sha256("test_token".encode("utf-8")).hexdigest()
        assert result == expected

    def test_deterministic(self):
        mgr = _make_manager()
        assert mgr._hash_token("abc") == mgr._hash_token("abc")

    def test_different_inputs_different_hashes(self):
        mgr = _make_manager()
        assert mgr._hash_token("a") != mgr._hash_token("b")


# ---------------------------------------------------------------------------
# _generate_token
# ---------------------------------------------------------------------------

class TestGenerateToken:
    def test_returns_string(self):
        mgr = _make_manager()
        token = mgr._generate_token()
        assert isinstance(token, str)

    def test_sufficient_length(self):
        mgr = _make_manager()
        token = mgr._generate_token()
        # secrets.token_urlsafe(32) yields ~43 chars
        assert len(token) >= 40

    def test_unique_tokens(self):
        mgr = _make_manager()
        tokens = {mgr._generate_token() for _ in range(20)}
        assert len(tokens) == 20


# ---------------------------------------------------------------------------
# create_token
# ---------------------------------------------------------------------------

class TestCreateToken:
    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_returns_token_string(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        # existing count query
        mock_conn.execute.return_value.fetchone.return_value = (0,)

        token = mgr.create_token(user_id=1, device_fingerprint="fp-abc")
        assert isinstance(token, str)
        assert len(token) > 0

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_inserts_hashed_token(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = (0,)

        token = mgr.create_token(user_id=1, device_fingerprint="fp")
        token_hash = mgr._hash_token(token)

        # Check that the INSERT was called with the hashed token
        insert_calls = [
            c for c in mock_conn.execute.call_args_list
            if "INSERT INTO remember_me_tokens" in str(c)
        ]
        assert len(insert_calls) >= 1
        # The first positional arg tuple of the insert should contain the hash
        insert_args = insert_calls[0][0][1]
        assert insert_args[0] == token_hash

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_removes_oldest_when_limit_exceeded(self, mock_tx):
        mgr = _make_manager(max_tokens_per_user=2)
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        # Report 2 existing tokens (at limit)
        mock_conn.execute.return_value.fetchone.return_value = (2,)

        mgr.create_token(user_id=1, device_fingerprint="fp")

        # Should have a DELETE call for oldest tokens
        delete_calls = [
            c for c in mock_conn.execute.call_args_list
            if "DELETE FROM remember_me_tokens" in str(c)
        ]
        assert len(delete_calls) >= 1


# ---------------------------------------------------------------------------
# verify_and_rotate_token
# ---------------------------------------------------------------------------

class TestVerifyAndRotateToken:
    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_invalid_token_returns_none(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchone.return_value = None

        result = mgr.verify_and_rotate_token("bad_token", "fp")
        assert result is None

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_expired_token_returns_none(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        expired = (datetime.now() - timedelta(days=1)).isoformat()
        mock_conn.execute.return_value.fetchone.return_value = (
            42,       # user_id
            "fp-ok",  # stored_fingerprint
            expired,  # expires_at
            None,     # last_used
            3,        # use_count
        )

        result = mgr.verify_and_rotate_token("tok", "fp-ok")
        assert result is None

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_fingerprint_mismatch_returns_none_and_revokes_all(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        future = (datetime.now() + timedelta(days=10)).isoformat()
        mock_conn.execute.return_value.fetchone.return_value = (
            42, "fp-original", future, None, 0,
        )

        result = mgr.verify_and_rotate_token("tok", "fp-different")
        assert result is None

        # All tokens for user should be revoked
        delete_calls = [
            c for c in mock_conn.execute.call_args_list
            if "DELETE FROM remember_me_tokens WHERE user_id" in str(c)
        ]
        assert len(delete_calls) >= 1

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_valid_token_returns_user_id(self, mock_tx):
        mgr = _make_manager(rotate_on_use=False)
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        future = (datetime.now() + timedelta(days=10)).isoformat()
        mock_conn.execute.return_value.fetchone.return_value = (
            42, "fp-ok", future, None, 5,
        )

        result = mgr.verify_and_rotate_token("tok", "fp-ok")
        assert result == 42

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_rotates_token_when_configured(self, mock_tx):
        mgr = _make_manager(rotate_on_use=True)
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        future = (datetime.now() + timedelta(days=10)).isoformat()
        mock_conn.execute.return_value.fetchone.return_value = (
            42, "fp-ok", future, None, 2,
        )

        result = mgr.verify_and_rotate_token("tok", "fp-ok")
        assert result == 42

        # Should have DELETE for old token (rotation)
        delete_calls = [
            c for c in mock_conn.execute.call_args_list
            if "DELETE FROM remember_me_tokens WHERE token_hash" in str(c)
        ]
        assert len(delete_calls) >= 1


# ---------------------------------------------------------------------------
# revoke_token
# ---------------------------------------------------------------------------

class TestRevokeToken:
    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_revoke_existing_token(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.rowcount = 1

        assert mgr.revoke_token("some_token") is True

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_revoke_nonexistent_token(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.rowcount = 0

        assert mgr.revoke_token("no_such_token") is False


# ---------------------------------------------------------------------------
# revoke_all_user_tokens
# ---------------------------------------------------------------------------

class TestRevokeAllUserTokens:
    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_returns_count(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.rowcount = 3

        count = mgr.revoke_all_user_tokens(user_id=42)
        assert count == 3

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_logs_activity(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.rowcount = 1

        mgr.revoke_all_user_tokens(user_id=1)

        # Should have an INSERT into activity_log
        activity_calls = [
            c for c in mock_conn.execute.call_args_list
            if "INSERT INTO activity_log" in str(c)
        ]
        assert len(activity_calls) >= 1


# ---------------------------------------------------------------------------
# cleanup_expired_tokens
# ---------------------------------------------------------------------------

class TestCleanupExpiredTokens:
    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_returns_cleanup_count(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.rowcount = 5

        count = mgr.cleanup_expired_tokens()
        assert count == 5

    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_zero_expired(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.rowcount = 0

        count = mgr.cleanup_expired_tokens()
        assert count == 0


# ---------------------------------------------------------------------------
# get_user_tokens
# ---------------------------------------------------------------------------

class TestGetUserTokens:
    @patch("education_system.systems.university.infrastructure.security.remember_me.get_connection")
    def test_returns_list(self, mock_get_conn):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.execute.return_value.fetchall.return_value = [
            ("abcdef1234567890hash", "device-fingerprint-here", "2026-01-01", "2026-02-01", None, 0),
        ]

        tokens = mgr.get_user_tokens(user_id=42)
        assert len(tokens) == 1
        assert tokens[0]["token_id"] == "abcdef1234567890"[:16]
        assert tokens[0]["use_count"] == 0

    @patch("education_system.systems.university.infrastructure.security.remember_me.get_connection")
    def test_empty_list_when_no_tokens(self, mock_get_conn):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchall.return_value = []

        tokens = mgr.get_user_tokens(user_id=99)
        assert tokens == []


# ---------------------------------------------------------------------------
# initialize_database
# ---------------------------------------------------------------------------

class TestInitializeDatabase:
    @patch("education_system.systems.university.infrastructure.security.remember_me.transaction")
    def test_creates_table_and_indexes(self, mock_tx):
        mgr = _make_manager()
        mock_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        mgr.initialize_database()

        sql_calls = [str(c) for c in mock_conn.execute.call_args_list]

        # Should have CREATE TABLE
        assert any("CREATE TABLE" in s for s in sql_calls)

        # Should have CREATE INDEX calls
        index_calls = [s for s in sql_calls if "CREATE INDEX" in s]
        assert len(index_calls) >= 3  # token_hash, user_id, expires
