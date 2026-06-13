"""Tests for simple_activity_logger.models."""
import json

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import (
    LogEntry,
    LogLevel,
    OutputFormat,
    SecurityLevel,
)


class TestEnums:
    def test_log_levels_ordered(self):
        assert LogLevel.DEBUG.value < LogLevel.INFO.value < LogLevel.WARNING.value \
            < LogLevel.ERROR.value < LogLevel.CRITICAL.value

    def test_output_formats(self):
        assert OutputFormat("json") is OutputFormat.JSON
        assert {f.value for f in OutputFormat} == {"json", "csv", "database", "syslog", "cloud"}

    def test_security_levels_ordered(self):
        assert SecurityLevel.LOW.value < SecurityLevel.MEDIUM.value \
            < SecurityLevel.HIGH.value < SecurityLevel.CRITICAL.value


def _make_entry(**overrides):
    defaults = dict(
        timestamp="2026-05-28 10:00:00.000",
        user_id="u1",
        username="alice",
        role="user",
        action="login",
        module="auth",
        details="ok",
        status="success",
        log_level="INFO",
        session_id="s1",
        ip_address="127.0.0.1",
        user_agent="UA",
        request_size=0,
        response_size=0,
        processing_time=0.1,
        geolocation={"country": "X"},
        security_level="LOW",
        trace_id="t1",
    )
    defaults.update(overrides)
    return LogEntry(**defaults)


class TestLogEntry:
    def test_to_dict_includes_all_fields(self):
        d = _make_entry().to_dict()
        assert d["username"] == "alice"
        assert d["geolocation"] == {"country": "X"}
        assert d["stack_trace"] is None
        assert d["metadata"] is None

    def test_to_json_roundtrip(self):
        entry = _make_entry(metadata={"k": "v"})
        loaded = json.loads(entry.to_json())
        assert loaded["metadata"] == {"k": "v"}
        assert loaded["action"] == "login"
