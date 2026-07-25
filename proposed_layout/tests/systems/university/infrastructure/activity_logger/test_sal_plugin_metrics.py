"""Tests for simple_activity_logger.plugins.metrics."""
from education_system.systems.university.infrastructure.utils.activity_logger.plugins.metrics import (
    MetricsCollectionPlugin,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


def _entry(**o):
    base = dict(
        timestamp="2026-05-28 10:00:00.000",
        user_id="u1", username="alice", role="user",
        action="read", module="m", details="d", status="success",
        log_level="INFO", session_id="s", ip_address="1.1.1.1",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="LOW",
        trace_id="t",
    )
    base.update(o)
    return LogEntry(**base)


class TestMetricsCollection:
    def test_skip_on_failure_flag(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(), success=False)
        assert p.metrics["total_logs"] == 0

    def test_counts_logs_and_actions(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(action="read"), success=True)
        p.after_log(_entry(action="read"), success=True)
        p.after_log(_entry(action="write"), success=True)
        assert p.metrics["total_logs"] == 3
        assert p.metrics["action_counts"]["read"] == 2
        assert p.metrics["action_counts"]["write"] == 1

    def test_counts_errors_and_alerts(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(status="failure"), True)
        p.after_log(_entry(security_level="HIGH"), True)
        p.after_log(_entry(security_level="CRITICAL"), True)
        assert p.metrics["error_count"] == 1
        assert p.metrics["security_alerts"] == 2

    def test_user_and_module_activity(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(username="alice", module="a"), True)
        p.after_log(_entry(username="bob", module="a"), True)
        p.after_log(_entry(username="alice", module="b"), True)
        assert p.metrics["user_activity"] == {"alice": 2, "bob": 1}
        assert p.metrics["module_usage"] == {"a": 2, "b": 1}

    def test_hourly_activity_parses_timestamp(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(timestamp="2026-05-28 14:00:00.000"), True)
        assert p.metrics["hourly_activity"].get(14) == 1

    def test_hourly_activity_handles_bad_timestamp(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(timestamp="not-a-date"), True)
        assert p.metrics["total_logs"] == 1
        assert p.metrics["hourly_activity"] == {}

    def test_get_metrics_includes_calculated_fields(self):
        p = MetricsCollectionPlugin({})
        p.after_log(_entry(status="failure"), True)
        p.after_log(_entry(status="success"), True)
        m = p.get_metrics()
        assert m["error_rate"] == 50.0
        assert "top_actions" in m
        assert "top_users" in m
        assert "top_modules" in m

    def test_get_metrics_when_empty(self):
        m = MetricsCollectionPlugin({}).get_metrics()
        assert m["error_rate"] == 0
        assert m["security_alert_rate"] == 0

    def test_reset_metrics_interval(self):
        p = MetricsCollectionPlugin({"reset_interval_hours": 0})
        # With 0-hour reset interval, second call should reset before recording
        p.metrics["last_reset"] = 0  # force ancient timestamp
        p.after_log(_entry(), True)
        assert p.metrics["total_logs"] == 1

    def test_status_includes_metrics(self):
        p = MetricsCollectionPlugin({})
        status = p.get_status()
        assert "current_metrics" in status
        assert status["name"] == "MetricsCollectionPlugin"
