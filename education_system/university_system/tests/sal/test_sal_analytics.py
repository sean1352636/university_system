"""Tests for simple_activity_logger.analytics."""
import json

from education_system.university_system.modules.shared.utils.simple_activity_logger import analytics


class TestLogDetailHelper:
    def test_real_column_returns_top_level(self):
        log = {"action": "read", "details": "{}"}
        assert analytics._log_detail(log, "action") == "read"

    def test_extracts_from_json_details(self):
        log = {"action": "x", "details": json.dumps({"role": "admin", "module": "m"})}
        assert analytics._log_detail(log, "role") == "admin"
        assert analytics._log_detail(log, "module") == "m"

    def test_handles_invalid_json_details(self):
        log = {"action": "x", "details": "not json"}
        assert analytics._log_detail(log, "role", default="d") == "d"

    def test_handles_dict_details_directly(self):
        log = {"action": "x", "details": {"role": "user"}}
        assert analytics._log_detail(log, "role") == "user"

    def test_missing_field_returns_default(self):
        log = {"action": "x", "details": "{}"}
        assert analytics._log_detail(log, "role", default="fallback") == "fallback"


class TestModuleSurface:
    def test_engine_class_exists(self):
        assert hasattr(analytics, "AnalyticsEngine")
