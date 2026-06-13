"""Tests for university_system.core.activity_logger."""
import logging
from unittest.mock import patch

import pytest

from education_system.university_system.core import activity_logger as al


@pytest.fixture
def logged_messages():
    """Capture log records emitted by the activity logger via a stub handler."""
    messages = []

    class _Stub(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    handler = _Stub(level=logging.INFO)
    instance = al.ActivityLogger()
    # Save and replace handlers for isolation
    saved_handlers = list(instance.logger.handlers)
    saved_class_logger = al.ActivityLogger.logger
    instance.logger.handlers = [handler]
    al.ActivityLogger.logger = instance.logger
    instance._current_user = None
    yield messages
    instance.logger.handlers = saved_handlers
    al.ActivityLogger.logger = saved_class_logger


class TestSingleton:
    def test_returns_same_instance(self):
        assert al.ActivityLogger() is al.ActivityLogger()


class TestUserState:
    def test_default_user_is_System(self, logged_messages):
        assert al.get_user() == "System"

    def test_set_user_via_module(self, logged_messages):
        al.set_user("alice")
        assert al.get_user() == "alice"


class TestLogActions:
    def test_log_emits_user_action_timestamp(self, logged_messages):
        al.set_user("alice")
        al.ActivityLogger().log("did a thing")
        assert len(logged_messages) == 1
        msg = logged_messages[0]
        assert msg.startswith("alice - did a thing - ")

    def test_log_with_explicit_user(self, logged_messages):
        al.ActivityLogger().log("act", user="bob")
        assert logged_messages[0].startswith("bob - act - ")


class TestLoginLogout:
    def test_login_success(self, logged_messages):
        al.log_login("alice", success=True)
        assert "Logged in successfully" in logged_messages[0]
        assert "alice" in logged_messages[0]
        # Current user is updated
        assert al.get_user() == "alice"

    def test_login_failure(self, logged_messages):
        al.log_login("alice", success=False)
        assert "Failed login attempt" in logged_messages[0]

    def test_logout_clears_user(self, logged_messages):
        al.set_user("alice")
        al.log_logout("alice")
        assert "Logged out" in logged_messages[0]
        assert al.get_user() == "System"


class TestCrudHelpers:
    def test_log_create_without_name(self, logged_messages):
        al.log_create("student")
        assert "Created student" in logged_messages[0]

    def test_log_create_with_name(self, logged_messages):
        al.log_create("student", "Alice")
        assert "Created student: Alice" in logged_messages[0]

    def test_log_read(self, logged_messages):
        al.log_read("student", "Alice")
        assert "Viewed student: Alice" in logged_messages[0]

    def test_log_update(self, logged_messages):
        al.log_update("student", "Alice")
        assert "Updated student: Alice" in logged_messages[0]

    def test_log_delete(self, logged_messages):
        al.log_delete("student", "Alice")
        assert "Deleted student: Alice" in logged_messages[0]

    def test_log_search(self, logged_messages):
        al.log_search("students", "Alice")
        assert "Searched students for: Alice" in logged_messages[0]

    def test_log_export(self, logged_messages):
        al.log_export("report", "CSV")
        assert "Exported report as CSV" in logged_messages[0]

    def test_log_import(self, logged_messages):
        al.log_import("students", "students.csv")
        assert "Imported students from students.csv" in logged_messages[0]

    def test_log_error(self, logged_messages):
        al.log_error("boom")
        assert "ERROR: boom" in logged_messages[0]

    def test_log_access(self, logged_messages):
        al.log_access("admin_panel")
        assert "Accessed admin_panel" in logged_messages[0]

    def test_log_permission_denied(self, logged_messages):
        al.log_permission_denied("finance")
        assert "Permission denied: finance" in logged_messages[0]


class TestLogActivityWrapper:
    def test_with_entity_type_capitalizes_action(self, logged_messages):
        al.log_activity("create", entity_type="student", user="alice")
        # action.capitalize() means "Create student"
        assert "Create student" in logged_messages[0]
        assert logged_messages[0].startswith("alice - ")

    def test_without_entity_type(self, logged_messages):
        al.log_activity("logged out", user="alice")
        assert "logged out" in logged_messages[0]

    def test_extra_kwargs_are_swallowed(self, logged_messages):
        # Legacy call sites pass kwargs like profile_id=...
        al.log_activity("view", entity_type="profile", user="alice",
                         profile_id=123, extra_metadata="x")
        # Must not raise; message recorded
        assert logged_messages


class TestLogFailureFallback:
    def test_write_failure_doesnt_raise(self, capsys):
        instance = al.ActivityLogger()
        with patch.object(instance.logger, "info", side_effect=RuntimeError("disk full")):
            instance.log("action", user="alice")  # must not raise
        err = capsys.readouterr().err
        assert "Failed to write audit log" in err
