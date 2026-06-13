"""Tests for simple_activity_logger.decorators"""
from unittest.mock import patch, MagicMock

import pytest

from education_system.university_system.modules.shared.utils.simple_activity_logger.decorators import (
    enhanced_log_activity, log_create, log_read, log_update, log_delete,
    log_search, log_export, log_admin_action, log_menu_navigation,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger.models import (
    LogLevel, SecurityLevel,
)


@pytest.fixture
def mock_logger():
    with patch(
        "education_system.university_system.modules.shared.utils.simple_activity_logger.module_api.logger"
    ) as m:
        yield m


class TestEnhancedLogActivity:
    def test_logs_success(self, mock_logger):
        @enhanced_log_activity(action="x", module="m")
        def f(a, b):
            return a + b

        assert f(1, 2) == 3
        assert mock_logger.log_activity.called
        args, kwargs = mock_logger.log_activity.call_args
        assert args[3] == "x"  # action
        assert args[4] == "m"  # module
        assert args[6] == "success"

    def test_logs_failure_and_reraises(self, mock_logger):
        @enhanced_log_activity()
        def boom():
            raise ValueError("nope")

        with pytest.raises(ValueError):
            boom()
        assert mock_logger.log_activity.called
        args, kwargs = mock_logger.log_activity.call_args
        assert args[6] == "failure"
        assert args[7] == LogLevel.ERROR

    def test_extracts_user_from_self(self, mock_logger):
        class Svc:
            def __init__(self):
                self.current_user = MagicMock(id=42, username="bob", role="admin")

            @enhanced_log_activity(action="touch", module="svc")
            def go(self):
                return "ok"

        Svc().go()
        args, _ = mock_logger.log_activity.call_args
        assert args[0] == "42"
        assert args[1] == "bob"
        assert args[2] == "admin"

    def test_no_current_user_defaults_to_system(self, mock_logger):
        class Svc:
            current_user = None

            @enhanced_log_activity()
            def go(self):
                return None

        Svc().go()
        args, _ = mock_logger.log_activity.call_args
        assert args[0] == "system"

    def test_metadata_includes_function_info(self, mock_logger):
        @enhanced_log_activity(metadata={"k": "v"})
        def f():
            return 1

        f()
        args, _ = mock_logger.log_activity.call_args
        meta = args[9]
        assert meta["function_name"] == "f"
        assert meta["k"] == "v"
        assert "execution_time" in meta


class TestSpecializedDecorators:
    def test_log_create_security_medium(self, mock_logger):
        @log_create(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "create"
        assert args[8] == SecurityLevel.MEDIUM

    def test_log_read_debug_level(self, mock_logger):
        @log_read(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "read"
        assert args[7] == LogLevel.DEBUG

    def test_log_update(self, mock_logger):
        @log_update(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "update"
        assert args[8] == SecurityLevel.MEDIUM

    def test_log_delete(self, mock_logger):
        @log_delete(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "delete"
        assert args[7] == LogLevel.WARNING
        assert args[8] == SecurityLevel.HIGH

    def test_log_search(self, mock_logger):
        @log_search(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "search"

    def test_log_export(self, mock_logger):
        @log_export(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "export"
        assert args[8] == SecurityLevel.HIGH

    def test_log_admin_action(self, mock_logger):
        @log_admin_action(module="m")
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "admin"
        assert args[8] == SecurityLevel.CRITICAL

    def test_log_menu_navigation(self, mock_logger):
        @log_menu_navigation()
        def f():
            return 1
        f()
        args, _ = mock_logger.log_activity.call_args
        assert args[3] == "menu_navigation"
        assert args[4] == "navigation"
