"""Tests for plugins.metrics.MetricsCollectionPlugin"""
import time

from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger.plugins.metrics import (
    MetricsCollectionPlugin,
)


class TestMetricsPlugin:
    def test_after_log_increments(self, make_log_entry):
        p = MetricsCollectionPlugin({})
        p.after_log(make_log_entry(action="login", username="u", module="auth"), True)
        m = p.get_metrics()
        assert m["total_logs"] == 1
        assert m["action_counts"]["login"] == 1
        assert m["user_activity"]["u"] == 1
        assert m["module_usage"]["auth"] == 1

    def test_skipped_on_failure_flag(self, make_log_entry):
        p = MetricsCollectionPlugin({})
        p.after_log(make_log_entry(), False)
        assert p.get_metrics()["total_logs"] == 0

    def test_error_count_incremented_for_failure_status(self, make_log_entry):
        p = MetricsCollectionPlugin({})
        p.after_log(make_log_entry(status="failure"), True)
        assert p.get_metrics()["error_count"] == 1

    def test_security_alert_incremented(self, make_log_entry):
        p = MetricsCollectionPlugin({})
        p.after_log(make_log_entry(security_level="CRITICAL"), True)
        assert p.get_metrics()["security_alerts"] == 1
        p.after_log(make_log_entry(security_level="HIGH"), True)
        assert p.get_metrics()["security_alerts"] == 2

    def test_get_metrics_calculates_rates_and_top(self, make_log_entry):
        p = MetricsCollectionPlugin({})
        p.after_log(make_log_entry(action="a", username="x", module="m"), True)
        p.after_log(make_log_entry(action="a", status="failure", username="y", module="m",
                                     security_level="CRITICAL"), True)
        m = p.get_metrics()
        assert m["error_rate"] == 50.0
        assert m["security_alert_rate"] == 50.0
        assert m["top_actions"]["a"] == 2

    def test_get_metrics_zero_logs(self):
        p = MetricsCollectionPlugin({})
        m = p.get_metrics()
        assert m["error_rate"] == 0
        assert m["security_alert_rate"] == 0

    def test_reset_after_interval(self, make_log_entry):
        p = MetricsCollectionPlugin({"reset_interval_hours": 0})
        p.after_log(make_log_entry(), True)
        # Force last_reset into the past beyond interval (0 hours = 0 seconds)
        p.metrics["last_reset"] = time.time() - 10
        p.after_log(make_log_entry(), True)
        # The first batch was reset before second was counted
        assert p.get_metrics()["total_logs"] == 1

    def test_get_status_includes_metrics(self, make_log_entry):
        p = MetricsCollectionPlugin({})
        p.after_log(make_log_entry(), True)
        status = p.get_status()
        assert status["name"] == "MetricsCollectionPlugin"
        assert "current_metrics" in status
