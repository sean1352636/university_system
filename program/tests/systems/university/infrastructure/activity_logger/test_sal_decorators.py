"""Tests for simple_activity_logger.decorators."""
from unittest.mock import MagicMock, patch

import pytest

from education_system.systems.university.infrastructure.utils.activity_logger import decorators
from education_system.systems.university.infrastructure.utils.activity_logger.decorators import (
    enhanced_log_activity,
    log_admin_action,
    log_create,
    log_delete,
    log_export,
    log_menu_navigation,
    log_read,
    log_search,
    log_update,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import (
    LogLevel,
    SecurityLevel,
)


@pytest.fixture
def stub_logger():
    """Patch the module_api logger so decorators don't touch real I/O."""
    stub = MagicMock()
    with patch(
        "education_system.systems.university.infrastructure.utils.activity_logger.module_api.logger",
        stub,
    ):
        yield stub


class TestEnhancedLogActivity:
    def test_returns_function_result(self, stub_logger):
        @enhanced_log_activity(action="ping", module="test")
        def f(x):
            return x * 2
        assert f(3) == 6
        stub_logger.log_activity.assert_called_once()

    def test_logs_failure_and_reraises(self, stub_logger):
        @enhanced_log_activity(action="boom", module="test")
        def f():
            raise ValueError("kaboom")
        with pytest.raises(ValueError):
            f()
        # status="failure" call recorded
        args, kwargs = stub_logger.log_activity.call_args
        assert args[6] == "failure"

    def test_default_action_is_function_name(self, stub_logger):
        @enhanced_log_activity()
        def my_fn():
            return 1
        my_fn()
        args = stub_logger.log_activity.call_args.args
        # signature: user_id, username, role, action_name, module, details, status, ...
        assert args[3] == "my_fn"

    def test_extracts_user_from_self(self, stub_logger):
        class Holder:
            def __init__(self):
                user = MagicMock()
                user.id = 7
                user.username = "bob"
                user.role = "admin"
                self.current_user = user

            @enhanced_log_activity(action="x", module="m")
            def call(self):
                return "ok"

        Holder().call()
        args = stub_logger.log_activity.call_args.args
        assert args[0] == "7"
        assert args[1] == "bob"
        assert args[2] == "admin"

    def test_no_user_falls_back_to_system(self, stub_logger):
        @enhanced_log_activity(action="x", module="m")
        def f():
            return 1
        f()
        args = stub_logger.log_activity.call_args.args
        assert args[0] == "system"
        assert args[1] == "system"


class TestSpecializedDecorators:
    @pytest.mark.parametrize("factory,expected_action,expected_security", [
        (log_create, "create", SecurityLevel.MEDIUM),
        (log_read, "read", SecurityLevel.LOW),
        (log_update, "update", SecurityLevel.MEDIUM),
        (log_delete, "delete", SecurityLevel.HIGH),
        (log_search, "search", SecurityLevel.LOW),
        (log_export, "export", SecurityLevel.HIGH),
        (log_admin_action, "admin", SecurityLevel.CRITICAL),
    ])
    def test_decorator_uses_correct_action_and_security(
        self, stub_logger, factory, expected_action, expected_security,
    ):
        @factory("test_module")
        def f():
            return "ok"
        f()
        args, _ = stub_logger.log_activity.call_args
        # signature: user_id, username, role, action, module, details, status, log_level, security_level, metadata
        assert args[3] == expected_action
        assert args[8] == expected_security

    def test_menu_navigation(self, stub_logger):
        @log_menu_navigation(description="open menu")
        def f():
            return None
        f()
        args = stub_logger.log_activity.call_args.args
        assert args[3] == "menu_navigation"
        assert args[4] == "navigation"
        assert args[7] == LogLevel.DEBUG

    def test_log_delete_records_warning_level(self, stub_logger):
        @log_delete("m")
        def f():
            return None
        f()
        args = stub_logger.log_activity.call_args.args
        assert args[7] == LogLevel.WARNING
