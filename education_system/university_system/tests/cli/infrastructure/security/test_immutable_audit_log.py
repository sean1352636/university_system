"""
Comprehensive tests for immutable_audit_log module.

Tests cover:
- ImmutableAuditLog initialization with secret key
- _calculate_hash() deterministic SHA-256 chain hashing
- _calculate_hmac() HMAC-SHA256 signing
- add_entry() with hash chain construction
- verify_integrity() chain validation
- get_entries() with filters
- get_entry_count()
- get_latest_hash()
- AuditAction constants
- log_security_event() convenience function
- verify_audit_log_integrity() convenience function
"""

import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset module-level singletons between tests."""
    import education_system.university_system.infrastructure.security.immutable_audit_log as mod
    mod._audit_log_instance = None
    # Reset the class-level secret key so each test can configure it
    mod.ImmutableAuditLog._SECRET_KEY = None
    yield
    mod._audit_log_instance = None
    mod.ImmutableAuditLog._SECRET_KEY = None


@pytest.fixture
def in_memory_audit_log():
    """Create an ImmutableAuditLog backed by an in-memory SQLite DB."""
    from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog

    with patch("university_system.infrastructure.security.immutable_audit_log.transaction") as mock_tx, \
         patch("university_system.infrastructure.security.immutable_audit_log.get_connection") as mock_gc:

        # Create a real in-memory SQLite DB
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS immutable_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                session_id TEXT,
                previous_hash TEXT,
                current_hash TEXT NOT NULL,
                hmac_signature TEXT NOT NULL,
                UNIQUE(current_hash)
            )
        """)
        conn.commit()

        # Make transaction() yield the real connection
        mock_tx.return_value.__enter__ = MagicMock(return_value=conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        # Make get_connection() yield the real connection
        mock_gc.return_value.__enter__ = MagicMock(return_value=conn)
        mock_gc.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="test-secret-key")
        yield log, conn


# ---------------------------------------------------------------------------
# AuditAction constants
# ---------------------------------------------------------------------------

class TestAuditAction:
    def test_login_success(self):
        from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
        assert AuditAction.LOGIN_SUCCESS == "LOGIN_SUCCESS"

    def test_logout(self):
        from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
        assert AuditAction.LOGOUT == "LOGOUT"

    def test_data_export(self):
        from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
        assert AuditAction.DATA_EXPORT == "DATA_EXPORT"

    def test_suspicious_activity(self):
        from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
        assert AuditAction.SUSPICIOUS_ACTIVITY == "SUSPICIOUS_ACTIVITY"

    def test_security_alert(self):
        from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
        assert AuditAction.SECURITY_ALERT == "SECURITY_ALERT"


# ---------------------------------------------------------------------------
# ImmutableAuditLog initialization
# ---------------------------------------------------------------------------

class TestImmutableAuditLogInit:
    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_init_with_explicit_secret(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="my-secret")
        assert ImmutableAuditLog._SECRET_KEY == b"my-secret"

    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    @patch.dict(os.environ, {"AUDIT_LOG_SECRET": "env-secret"})
    def test_init_from_env(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog()
        assert ImmutableAuditLog._SECRET_KEY == b"env-secret"

    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    @patch.dict(os.environ, {}, clear=True)
    def test_init_generates_random_key_when_no_secret(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        # Remove any existing env var
        os.environ.pop("AUDIT_LOG_SECRET", None)
        log = ImmutableAuditLog()
        assert ImmutableAuditLog._SECRET_KEY is not None
        assert len(ImmutableAuditLog._SECRET_KEY) == 32  # os.urandom(32)


# ---------------------------------------------------------------------------
# _calculate_hash
# ---------------------------------------------------------------------------

class TestCalculateHash:
    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_deterministic(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="k")
        h1 = log._calculate_hash("prev", "2024-01-01", "user", "LOGIN", None, None, "{}", None)
        h2 = log._calculate_hash("prev", "2024-01-01", "user", "LOGIN", None, None, "{}", None)
        assert h1 == h2

    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_different_input_different_hash(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="k")
        h1 = log._calculate_hash("prev", "2024-01-01", "user1", "LOGIN", None, None, "{}", None)
        h2 = log._calculate_hash("prev", "2024-01-01", "user2", "LOGIN", None, None, "{}", None)
        assert h1 != h2

    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_returns_64_char_hex(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="k")
        h = log._calculate_hash("0" * 64, "ts", "u", "a", None, None, "{}", None)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# _calculate_hmac
# ---------------------------------------------------------------------------

class TestCalculateHmac:
    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_deterministic(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="k")
        h1 = log._calculate_hmac("test data")
        h2 = log._calculate_hmac("test data")
        assert h1 == h2

    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_different_data_different_hmac(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="k")
        h1 = log._calculate_hmac("data1")
        h2 = log._calculate_hmac("data2")
        assert h1 != h2

    @patch("university_system.infrastructure.security.immutable_audit_log.transaction")
    def test_matches_manual_hmac(self, mock_tx):
        from education_system.university_system.infrastructure.security.immutable_audit_log import ImmutableAuditLog
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        log = ImmutableAuditLog(secret_key="mysecret")
        result = log._calculate_hmac("hello")
        expected = hmac.new(b"mysecret", b"hello", hashlib.sha256).hexdigest()
        assert result == expected


# ---------------------------------------------------------------------------
# add_entry (with real in-memory DB)
# ---------------------------------------------------------------------------

class TestAddEntry:
    def test_first_entry_uses_genesis_hash(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        h = log.add_entry(user_id="admin", action="LOGIN")
        assert isinstance(h, str)
        assert len(h) == 64

        row = conn.execute("SELECT previous_hash FROM immutable_audit_log WHERE id=1").fetchone()
        assert row["previous_hash"] == "0" * 64

    def test_chain_linkage(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        h1 = log.add_entry(user_id="u1", action="A1")
        h2 = log.add_entry(user_id="u2", action="A2")

        row2 = conn.execute("SELECT previous_hash FROM immutable_audit_log WHERE id=2").fetchone()
        assert row2["previous_hash"] == h1

    def test_entry_stores_all_fields(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(
            user_id="u1",
            action="DATA_VIEW",
            resource_type="student",
            resource_id="s123",
            details={"key": "val"},
            ip_address="1.2.3.4",
            user_agent="Mozilla",
            session_id="sess-1",
        )
        row = conn.execute("SELECT * FROM immutable_audit_log WHERE id=1").fetchone()
        assert row["user_id"] == "u1"
        assert row["action"] == "DATA_VIEW"
        assert row["resource_type"] == "student"
        assert row["ip_address"] == "1.2.3.4"
        assert row["user_agent"] == "Mozilla"
        assert row["session_id"] == "sess-1"

    def test_hmac_signature_present(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="TEST")
        row = conn.execute("SELECT hmac_signature FROM immutable_audit_log WHERE id=1").fetchone()
        assert row["hmac_signature"] is not None
        assert len(row["hmac_signature"]) == 64


# ---------------------------------------------------------------------------
# verify_integrity
# ---------------------------------------------------------------------------

class TestVerifyIntegrity:
    def test_empty_log_is_valid(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        result = log.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 0

    def test_single_entry_valid(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="TEST")
        result = log.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 1

    def test_multiple_entries_valid(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        for i in range(5):
            log.add_entry(user_id=f"u{i}", action=f"ACTION_{i}")
        result = log.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 5

    def test_tampered_entry_detected(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="ORIGINAL")
        log.add_entry(user_id="u2", action="SECOND")

        # Tamper with the first entry's action
        conn.execute("UPDATE immutable_audit_log SET action='TAMPERED' WHERE id=1")
        conn.commit()

        result = log.verify_integrity()
        assert result["valid"] is False
        assert len(result["invalid_entries"]) > 0

    def test_chain_break_detected(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="A1")
        log.add_entry(user_id="u2", action="A2")

        # Break the chain by changing previous_hash
        conn.execute("UPDATE immutable_audit_log SET previous_hash='bad_hash' WHERE id=2")
        conn.commit()

        result = log.verify_integrity()
        assert result["valid"] is False

    def test_verify_with_limit(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        for i in range(10):
            log.add_entry(user_id=f"u{i}", action=f"A{i}")
        result = log.verify_integrity(limit=5)
        assert result["total_entries"] == 5
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# get_entries
# ---------------------------------------------------------------------------

class TestGetEntries:
    def test_returns_list(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="TEST")
        entries = log.get_entries()
        assert len(entries) == 1
        assert entries[0]["action"] == "TEST"

    def test_filter_by_user(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="A1")
        log.add_entry(user_id="u2", action="A2")
        entries = log.get_entries(user_id="u1")
        assert len(entries) == 1
        assert entries[0]["user_id"] == "u1"

    def test_filter_by_action(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="LOGIN")
        log.add_entry(user_id="u1", action="LOGOUT")
        entries = log.get_entries(action="LOGIN")
        assert len(entries) == 1

    def test_pagination(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        for i in range(5):
            log.add_entry(user_id="u1", action=f"A{i}")
        entries = log.get_entries(limit=2, offset=0)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# get_entry_count
# ---------------------------------------------------------------------------

class TestGetEntryCount:
    def test_empty_count(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        assert log.get_entry_count() == 0

    def test_nonzero_count(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="A1")
        log.add_entry(user_id="u2", action="A2")
        assert log.get_entry_count() == 2


# ---------------------------------------------------------------------------
# get_latest_hash
# ---------------------------------------------------------------------------

class TestGetLatestHash:
    def test_none_when_empty(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        assert log.get_latest_hash() is None

    def test_returns_last_hash(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        h1 = log.add_entry(user_id="u1", action="A1")
        h2 = log.add_entry(user_id="u2", action="A2")
        assert log.get_latest_hash() == h2


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    def test_log_security_event(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        with patch(
            "university_system.infrastructure.security.immutable_audit_log.get_immutable_audit_log",
            return_value=log,
        ):
            from education_system.university_system.infrastructure.security.immutable_audit_log import log_security_event
            h = log_security_event(user_id="admin", action="LOGIN_SUCCESS")
            assert isinstance(h, str)
            assert len(h) == 64

    def test_verify_audit_log_integrity(self, in_memory_audit_log):
        log, conn = in_memory_audit_log
        log.add_entry(user_id="u1", action="A1")
        with patch(
            "university_system.infrastructure.security.immutable_audit_log.get_immutable_audit_log",
            return_value=log,
        ):
            from education_system.university_system.infrastructure.security.immutable_audit_log import verify_audit_log_integrity
            result = verify_audit_log_integrity()
            assert result["valid"] is True
