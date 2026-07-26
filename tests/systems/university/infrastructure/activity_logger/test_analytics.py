"""Tests for simple_activity_logger.analytics"""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from education_system.systems.university.infrastructure.utils.activity_logger.analytics import (
    AnalyticsEngine, _log_detail,
)


def _ts(offset_days=0, hour=12):
    dt = datetime.now() - timedelta(days=offset_days)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _make_log(action="read", user_id="u1", username="alice", **details):
    return {
        "id": 1,
        "user_id": user_id,
        "username": username,
        "action": action,
        "details": json.dumps(details) if details else "{}",
        "timestamp": details.get("timestamp", _ts()),
        "ip_address": details.get("ip_address", "127.0.0.1"),
    }


class TestLogDetail:
    def test_returns_column_value(self):
        log = {"action": "x"}
        assert _log_detail(log, "action") == "x"

    def test_returns_detail_field(self):
        log = {"details": json.dumps({"module": "lib"})}
        assert _log_detail(log, "module") == "lib"

    def test_default_when_missing(self):
        log = {"details": "{}"}
        assert _log_detail(log, "missing", "fallback") == "fallback"

    def test_invalid_json(self):
        log = {"details": "not json"}
        assert _log_detail(log, "anything", "default") == "default"

    def test_dict_details(self):
        log = {"details": {"status": "success"}}
        assert _log_detail(log, "status") == "success"


class TestAnalyticsEngine:
    def test_user_stats_no_logs(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[])
        engine = AnalyticsEngine(db)
        stats = engine.get_user_activity_stats("u1")
        assert stats["total_activities"] == 0
        assert stats["success_rate"] == 0

    def test_user_stats_with_logs(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[
            _make_log(action="login", status="success", module="auth", processing_time=0.5,
                      security_level="LOW"),
            _make_log(action="login", status="failure", module="auth", processing_time=1.0,
                      security_level="HIGH"),
        ])
        engine = AnalyticsEngine(db)
        stats = engine.get_user_activity_stats("u1")
        assert stats["total_activities"] == 2
        assert stats["actions"]["login"] == 2
        assert stats["modules"]["auth"] == 2
        assert stats["success_rate"] == 50.0
        assert stats["error_rate"] == 50.0
        assert stats["security_alerts"] == 1
        assert stats["average_processing_time"] == 0.75

    def test_get_system_health_metrics_returns_dict(self):
        engine = AnalyticsEngine(MagicMock())
        m = engine.get_system_health_metrics()
        assert isinstance(m, dict)
        # Must contain at least a couple expected keys
        for k in ("cpu_usage", "memory_usage"):
            assert k in m

    def test_detect_anomalies_no_logs(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[])
        engine = AnalyticsEngine(db)
        assert engine.detect_anomalies() == []

    def test_detect_anomalies_high_error_rate(self):
        # 30 logs all failing -> 100% error rate -> high_system_error_rate
        logs = [_make_log(status="failure") for _ in range(30)]
        db = MagicMock()
        db.query_logs = MagicMock(return_value=logs)
        engine = AnalyticsEngine(db)
        anomalies = engine.detect_anomalies()
        types = [a["type"] for a in anomalies]
        assert "high_system_error_rate" in types

    def test_detect_anomalies_rapid_failure_sequence(self):
        # 11 failures all in same 5-min window
        ts = "2026-05-06 12:00:00"
        logs = [{
            "id": i, "user_id": "u1", "username": "n", "action": "login",
            "details": json.dumps({"status": "failure"}),
            "timestamp": ts, "ip_address": "ip",
        } for i in range(11)]
        db = MagicMock()
        db.query_logs = MagicMock(return_value=logs)
        engine = AnalyticsEngine(db)
        anomalies = engine.detect_anomalies()
        assert any(a["type"] == "rapid_failure_sequence" for a in anomalies)

    def test_generate_report_unknown_type(self):
        engine = AnalyticsEngine(MagicMock())
        with pytest.raises(ValueError):
            engine.generate_report("nonsense")

    def test_summary_report_empty(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[])
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("summary", "json")
        assert rep["total_activities"] == 0
        assert rep["report_type"] == "summary"

    def test_summary_report_with_logs(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[
            _make_log(action="login", username="a", status="success", module="auth", processing_time=0.1),
            _make_log(action="login", username="b", status="failure", module="auth", processing_time=0.2,
                      security_level="CRITICAL"),
        ])
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("summary")
        assert rep["total_activities"] == 2
        assert rep["error_rate"] == 50.0
        assert rep["security_alert_rate"] == 50.0
        assert rep["top_actions"]["login"] == 2

    def test_security_report(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[
            _make_log(action="login", status="failure", security_level="HIGH"),
            _make_log(action="login", status="failure", security_level="HIGH"),
            _make_log(action="create_admin", status="success", role="user"),
        ])
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("security")
        assert rep["failed_logins"] == 2
        assert rep["privilege_escalation_attempts"] == 1

    def test_performance_report_empty(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[])
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("performance")
        assert rep["total_requests"] == 0

    def test_performance_report_with_data(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[
            _make_log(action="x", module="m", processing_time=0.1),
            _make_log(action="x", module="m", processing_time=0.5),
        ])
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("performance")
        assert rep["total_requests"] == 2
        assert rep["min_processing_time"] == 0.1
        assert rep["max_processing_time"] == 0.5

    def test_user_activity_report(self):
        db = MagicMock()
        recent_log = _make_log(action="login", username="alice")
        db.query_logs = MagicMock(return_value=[recent_log])
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("user_activity")
        assert rep["unique_users"] == 1
        assert "alice" in rep["most_active_users"]

    def test_system_health_report(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[])
        db.get_database_stats = MagicMock(return_value={"total_logs": 0, "database_size": 10})
        engine = AnalyticsEngine(db)
        rep = engine.generate_report("system_health")
        assert rep["report_type"] == "system_health"
        assert "system_metrics" in rep

    def test_format_report_csv(self):
        engine = AnalyticsEngine(MagicMock())
        out = engine._format_report({"a": 1, "lst": [1, 2, 3]}, "csv")
        assert "a,1" in out
        assert "lst,3 items" in out

    def test_format_report_string(self):
        engine = AnalyticsEngine(MagicMock())
        out = engine._format_report({"a": 1}, "plain")
        # Falls through to JSON string serialisation
        assert '"a": 1' in out

    def test_get_trending_data_empty(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[])
        engine = AnalyticsEngine(db)
        out = engine.get_trending_data("total_activity")
        assert out["data_points"] == {}
        assert out["trend"] == "stable"

    def test_get_trending_data_increasing(self):
        db = MagicMock()
        db.query_logs = MagicMock(return_value=[
            {"id": 1, "user_id": "u", "username": "a", "action": "x",
             "details": json.dumps({"status": "success"}),
             "timestamp": "2026-05-01 12:00:00", "ip_address": "ip"},
            {"id": 2, "user_id": "u", "username": "a", "action": "x",
             "details": json.dumps({"status": "success"}),
             "timestamp": "2026-05-02 12:00:00", "ip_address": "ip"},
            {"id": 3, "user_id": "u", "username": "a", "action": "x",
             "details": json.dumps({"status": "success"}),
             "timestamp": "2026-05-02 13:00:00", "ip_address": "ip"},
        ])
        engine = AnalyticsEngine(db)
        out = engine.get_trending_data("total_activity")
        assert out["trend"] == "increasing"
        assert "2026-05-01" in out["data_points"]
