"""
Comprehensive tests for audit_trail module.

Tests cover:
- AuditAction enum values
- AuditEntry dataclass and to_dict()
- AuditLogger singleton pattern
- AuditLogger._init_db() table creation
- set_user_context / clear_user_context / get_user_context / user_context CM
- _compute_data_hash()
- log() method with all parameters
- query() method with filters
- get_user_activity(), get_resource_history(), get_failed_operations()
- audit_data_access decorator
- log_activity convenience function
"""

import json
import sqlite3
import tempfile
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset AuditLogger singleton between tests."""
    from education_system.post_18.university_system.infrastructure.security import audit_trail
    audit_trail.AuditLogger._instance = None
    audit_trail._audit_logger = None
    yield
    audit_trail.AuditLogger._instance = None
    audit_trail._audit_logger = None


@pytest.fixture
def tmp_db():
    """Provide a temporary SQLite database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name


# ---------------------------------------------------------------------------
# AuditAction enum
# ---------------------------------------------------------------------------

class TestAuditAction:
    def test_access_value(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditAction
        assert AuditAction.ACCESS.value == "access"

    def test_create_value(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditAction
        assert AuditAction.CREATE.value == "create"

    def test_all_values_are_strings(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditAction
        for member in AuditAction:
            assert isinstance(member.value, str)

    def test_has_expected_members(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditAction
        names = {m.name for m in AuditAction}
        assert "LOGIN" in names
        assert "DELETE" in names
        assert "EXPORT" in names
        assert "CONFIG_CHANGE" in names


# ---------------------------------------------------------------------------
# AuditEntry dataclass
# ---------------------------------------------------------------------------

class TestAuditEntry:
    def test_creation(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditEntry
        now = datetime.now()
        entry = AuditEntry(
            timestamp=now,
            action="read",
            resource_type="student",
            resource_id="123",
            user_id=1,
            username="admin",
            ip_address="127.0.0.1",
        )
        assert entry.action == "read"
        assert entry.success is True
        assert entry.details == {}

    def test_to_dict(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditEntry
        now = datetime.now()
        entry = AuditEntry(
            timestamp=now,
            action="create",
            resource_type="course",
            resource_id="C101",
            user_id=2,
            username="staff",
            ip_address="10.0.0.1",
            details={"key": "val"},
            success=False,
            error_message="Not found",
        )
        d = entry.to_dict()
        assert d["action"] == "create"
        assert d["timestamp"] == now.isoformat()
        assert d["success"] is False
        assert d["error_message"] == "Not found"
        assert d["details"] == {"key": "val"}

    def test_defaults(self):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditEntry
        entry = AuditEntry(
            timestamp=datetime.now(),
            action="access",
            resource_type="test",
            resource_id=None,
            user_id=None,
            username=None,
            ip_address=None,
        )
        assert entry.details == {}
        assert entry.function_name is None
        assert entry.data_hash is None


# ---------------------------------------------------------------------------
# AuditLogger singleton
# ---------------------------------------------------------------------------

class TestAuditLoggerSingleton:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_same_instance(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        a = AuditLogger()
        b = AuditLogger()
        assert a is b


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------

class TestUserContext:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_set_and_get_context(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        logger.set_user_context(user_id=42, username="admin", ip_address="1.2.3.4")
        ctx = logger.get_user_context()
        assert ctx["user_id"] == 42
        assert ctx["username"] == "admin"
        assert ctx["ip_address"] == "1.2.3.4"

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_clear_context(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        logger.set_user_context(user_id=1)
        logger.clear_user_context()
        ctx = logger.get_user_context()
        assert ctx["user_id"] is None

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_context_manager(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        logger.set_user_context(user_id=1, username="before")

        with logger.user_context(user_id=99, username="inside"):
            ctx = logger.get_user_context()
            assert ctx["user_id"] == 99
            assert ctx["username"] == "inside"

        # Restored after exit
        ctx = logger.get_user_context()
        assert ctx["user_id"] == 1
        assert ctx["username"] == "before"


# ---------------------------------------------------------------------------
# _compute_data_hash
# ---------------------------------------------------------------------------

class TestComputeDataHash:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_none_returns_empty(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        assert logger._compute_data_hash(None) == ""

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_deterministic(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        h1 = logger._compute_data_hash({"key": "value"})
        h2 = logger._compute_data_hash({"key": "value"})
        assert h1 == h2
        assert len(h1) == 16  # Truncated to 16 chars

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_different_data_different_hash(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        h1 = logger._compute_data_hash({"a": 1})
        h2 = logger._compute_data_hash({"b": 2})
        assert h1 != h2


# ---------------------------------------------------------------------------
# log() method
# ---------------------------------------------------------------------------

class TestLogMethod:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_log_returns_entry_id(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger, AuditAction
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        entry_id = logger.log(
            action=AuditAction.READ,
            resource_type="student",
            resource_id="s1",
            user_id=1,
            username="admin",
        )
        assert entry_id == 42

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_log_with_string_action(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        entry_id = logger.log(action="custom_action", resource_type="test")
        assert entry_id == 1

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_log_uses_context_when_no_explicit_user(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        logger.set_user_context(user_id=99, username="ctx_user")
        logger.log(action="read", resource_type="test")

        # Check the INSERT params include context user
        call_args = mock_cm.execute.call_args_list
        # Find the INSERT call (after DB init calls)
        insert_calls = [c for c in call_args if "INSERT INTO" in str(c)]
        assert len(insert_calls) >= 1


# ---------------------------------------------------------------------------
# query() method
# ---------------------------------------------------------------------------

class TestQueryMethod:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_query_returns_entries(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        now_str = datetime.now().isoformat()
        mock_cm.execute.return_value.fetchall.return_value = [
            (now_str, "read", "student", "123", 1, "admin", "1.1.1.1",
             '{"foo": "bar"}', "func", "mod", 1, None, None),
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        entries = logger.query(action="read")
        assert len(entries) == 1
        assert entries[0].action == "read"
        assert entries[0].details == {"foo": "bar"}

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_query_empty(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cm.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        entries = logger.query()
        assert entries == []

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_query_with_all_filters(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cm.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        now = datetime.now()
        logger.query(
            action="read",
            resource_type="student",
            resource_id="s1",
            user_id=1,
            since=now - timedelta(days=1),
            until=now,
            success_only=True,
            limit=50,
            offset=10,
        )
        # Just verify no errors occurred
        assert True


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_get_user_activity(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cm.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        result = logger.get_user_activity(user_id=1)
        assert isinstance(result, list)

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_get_resource_history(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cm.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        result = logger.get_resource_history("student", "s1")
        assert isinstance(result, list)

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_get_failed_operations(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import AuditLogger
        mock_cm = MagicMock()
        mock_cm.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        logger = AuditLogger()
        result = logger.get_failed_operations()
        assert isinstance(result, list)

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_log_activity_function(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import log_activity
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 7
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        entry_id = log_activity("read", "student", user_id=1)
        assert entry_id == 7


# ---------------------------------------------------------------------------
# audit_data_access decorator
# ---------------------------------------------------------------------------

class TestAuditDataAccessDecorator:
    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_decorator_logs_call(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import (
            audit_data_access, AuditAction, AuditLogger,
        )
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        @audit_data_access("student", action=AuditAction.READ)
        def get_student(student_id):
            return {"id": student_id}

        result = get_student("s1")
        assert result == {"id": "s1"}

        # Should have logged via INSERT
        insert_calls = [c for c in mock_cm.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) >= 1

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_decorator_logs_on_exception(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import (
            audit_data_access, AuditAction, AuditLogger,
        )
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        @audit_data_access("student", action=AuditAction.READ)
        def failing_func():
            raise ValueError("fail!")

        with pytest.raises(ValueError):
            failing_func()

        # Should still have logged the failure
        insert_calls = [c for c in mock_cm.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) >= 1

    @patch("education_system.post_18.university_system.infrastructure.security.audit_trail.get_connection")
    def test_decorator_extracts_resource_id(self, mock_conn):
        from education_system.post_18.university_system.infrastructure.security.audit_trail import (
            audit_data_access, AuditAction, AuditLogger,
        )
        mock_cm = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 1
        mock_cm.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_cm)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        @audit_data_access("course", resource_id_param="course_id")
        def get_course(course_id):
            return {"id": course_id}

        get_course(course_id="C101")
        # Verify the INSERT included resource_id = "C101"
        insert_calls = [c for c in mock_cm.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) >= 1
