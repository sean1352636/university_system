"""Tests for simple_activity_logger.models"""
import json

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import (
    LogLevel, OutputFormat, SecurityLevel, LogEntry,
)


class TestEnums:
    def test_log_level_values(self):
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.CRITICAL.value == 50

    def test_output_format_values(self):
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.DATABASE.value == "database"

    def test_security_level_values(self):
        assert SecurityLevel.LOW.value == 1
        assert SecurityLevel.CRITICAL.value == 4


class TestLogEntry:
    def _entry(self, **kw):
        defaults = dict(
            timestamp="2026-05-06 12:00:00",
            user_id="u", username="n", role="r", action="a",
            module="m", details="d", status="success", log_level="INFO",
            session_id="s", ip_address="ip", user_agent="ua",
            request_size=1, response_size=2, processing_time=0.1,
            geolocation={"city": "x"}, security_level="LOW",
            trace_id="t",
        )
        defaults.update(kw)
        return LogEntry(**defaults)

    def test_to_dict_round_trip(self):
        e = self._entry()
        d = e.to_dict()
        assert d["user_id"] == "u"
        assert d["geolocation"] == {"city": "x"}
        assert d["stack_trace"] is None
        assert d["metadata"] is None

    def test_to_json_is_valid(self):
        e = self._entry(metadata={"k": "v"})
        parsed = json.loads(e.to_json())
        assert parsed["metadata"] == {"k": "v"}
        assert parsed["action"] == "a"
