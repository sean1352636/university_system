"""Tests for simple_activity_logger.logger.EnhancedActivityLogger"""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from education_system.university_system.modules.shared.utils.simple_activity_logger.logger import (
    EnhancedActivityLogger,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger.models import (
    LogLevel, SecurityLevel,
)


def _write_config(path, **overrides):
    cfg = {
        "log_dir": str(path / "logs"),
        "min_log_level": "DEBUG",
        "output_formats": ["json"],
        "queue_size": 100,
        "batch_size": 1,
        "flush_interval": 1,
        "encrypt_logs": False,
        "enable_pii_detection": True,
        "security": {"max_failed_attempts": 3, "max_requests_per_minute": 1000},
        "rotation": {"max_file_size": 1024, "retention_days": 1, "compress_old_logs": False},
        "cloud": {"enabled_services": []},
        "security_alerts": {"webhook_enabled": False},
    }
    cfg.update(overrides)
    cfg_path = path / "logger_config.json"
    cfg_path.write_text(json.dumps(cfg))
    return str(cfg_path)


@pytest.fixture
def logger_inst(tmp_path):
    cfg = _write_config(tmp_path)
    inst = EnhancedActivityLogger(cfg)
    yield inst
    inst.shutdown(timeout=2)


class TestEnhancedActivityLoggerInit:
    def test_default_config_loaded(self, tmp_path, monkeypatch):
        # Avoid touching real paths
        log_dir = tmp_path / "x"
        log_dir.mkdir()
        # No config_path => defaults
        # We still call shutdown to clean up
        inst = EnhancedActivityLogger()
        try:
            assert inst.min_log_level == LogLevel.INFO
            assert "json" in inst.config["output_formats"] or "database" in inst.config["output_formats"]
        finally:
            inst.shutdown(timeout=2)

    def test_loads_yaml_config(self, tmp_path):
        cfg_path = tmp_path / "c.yaml"
        cfg_path.write_text("min_log_level: DEBUG\noutput_formats: [json]\n")
        inst = EnhancedActivityLogger(str(cfg_path))
        try:
            assert inst.min_log_level == LogLevel.DEBUG
        finally:
            inst.shutdown(timeout=2)

    def test_creates_log_directory(self, tmp_path):
        cfg = _write_config(tmp_path)
        inst = EnhancedActivityLogger(cfg)
        try:
            assert os.path.isdir(inst.log_dir)
        finally:
            inst.shutdown(timeout=2)


class TestLogActivityFiltering:
    def test_below_min_level_returns_true_without_queueing(self, tmp_path):
        cfg = _write_config(tmp_path, min_log_level="WARNING")
        inst = EnhancedActivityLogger(cfg)
        try:
            assert inst.log_activity("u", "n", "r", "a", "m", log_level=LogLevel.DEBUG) is True
            # Nothing queued
            assert inst.log_queue.qsize() == 0
        finally:
            inst.shutdown(timeout=2)

    def test_log_activity_pii_masking(self, logger_inst):
        logger_inst.log_activity("u", "n", "r", "view", "m", details="email: a@b.com")
        # Drain manually
        entry = logger_inst.log_queue.get(timeout=2)
        assert "a@b.com" not in entry.details

    def test_log_activity_metadata_masking(self, logger_inst):
        logger_inst.log_activity("u", "n", "r", "v", "m", details="x", metadata={"note": "1.2.3.4"})
        entry = logger_inst.log_queue.get(timeout=2)
        assert "1.2.3.4" not in entry.metadata["note"]


class TestSecurityHandling:
    def test_failed_login_escalates(self, tmp_path):
        cfg = _write_config(tmp_path, security={"max_failed_attempts": 1, "max_requests_per_minute": 1000})
        inst = EnhancedActivityLogger(cfg)
        try:
            # First failed login triggers suspicious -> sets security_level HIGH
            inst.log_activity("u", "n", "r", "login", "auth", status="failure")
            entry = inst.log_queue.get(timeout=2)
            assert entry.security_level in ("HIGH", "CRITICAL")
        finally:
            inst.shutdown(timeout=2)


class TestQueueOverflow:
    def test_queue_overflow_increments_metric(self, tmp_path):
        cfg = _write_config(tmp_path, queue_size=1)
        inst = EnhancedActivityLogger(cfg)
        try:
            # Stop any processing thread so queue can fill
            inst.shutdown_event.set()
            if inst.processing_thread and inst.processing_thread.ident is not None:
                inst.processing_thread.join(timeout=2)
            inst.log_queue.put_nowait(MagicMock())  # fill queue
            ok = inst.log_activity("u", "n", "r", "a", "m")
            assert ok is False
            assert inst.metrics["queue_overflows"] >= 1
        finally:
            inst.shutdown_event.set()


class TestWebhookSSRFGuard:
    def test_blocks_localhost(self, tmp_path, capsys, make_log_entry):
        cfg = _write_config(
            tmp_path,
            security_alerts={"webhook_enabled": True, "webhook_url": "http://127.0.0.1/x"},
        )
        inst = EnhancedActivityLogger(cfg)
        try:
            inst._send_security_webhook(make_log_entry())
            assert "internal" in capsys.readouterr().out.lower()
        finally:
            inst.shutdown(timeout=2)

    def test_blocks_invalid_scheme(self, tmp_path, capsys, make_log_entry):
        cfg = _write_config(
            tmp_path,
            security_alerts={"webhook_enabled": True, "webhook_url": "file:///etc/passwd"},
        )
        inst = EnhancedActivityLogger(cfg)
        try:
            inst._send_security_webhook(make_log_entry())
            assert "scheme" in capsys.readouterr().out.lower()
        finally:
            inst.shutdown(timeout=2)


class TestUpdateConfig:
    def test_update_min_log_level(self, logger_inst):
        logger_inst.update_config({"min_log_level": "ERROR"})
        assert logger_inst.min_log_level == LogLevel.ERROR


class TestGetMetrics:
    def test_get_metrics_includes_queue(self, logger_inst):
        m = logger_inst.get_metrics()
        assert "queue_size" in m
        assert "queue_maxsize" in m
        assert "logs_processed" in m


class TestHelpersMissingDB:
    def test_query_without_db_raises(self, tmp_path):
        cfg = _write_config(tmp_path, output_formats=["json"])
        inst = EnhancedActivityLogger(cfg)
        try:
            with pytest.raises(RuntimeError):
                inst.query_logs()
            with pytest.raises(RuntimeError):
                inst.search_logs("x")
            with pytest.raises(RuntimeError):
                inst.get_user_stats("u")
            with pytest.raises(RuntimeError):
                inst.export_logs("2026-01-01", "2026-12-31")
            assert inst.get_log_stats() == {"error": "Database logging not enabled"}
        finally:
            inst.shutdown(timeout=2)


class TestExportFormatErrors:
    def test_export_unsupported_format(self, tmp_path):
        cfg = _write_config(tmp_path, output_formats=["json"])
        inst = EnhancedActivityLogger(cfg)
        try:
            inst.db_logger = MagicMock()
            inst.db_logger.query_logs = MagicMock(return_value=[])
            with pytest.raises(ValueError):
                inst.export_logs("2026-01-01", "2026-12-31", format="xml")
        finally:
            inst.shutdown(timeout=2)


class TestGeolocationAndSession:
    def test_geolocation_local(self, logger_inst):
        out = logger_inst._get_geolocation("127.0.0.1")
        assert out["country"] == "Local"

    def test_geolocation_unknown(self, logger_inst):
        out = logger_inst._get_geolocation("8.8.8.8")
        assert out["country"] == "Unknown"

    def test_session_context_keys(self, logger_inst):
        ctx = logger_inst._get_session_context()
        for k in ("session_id", "ip_address", "user_agent", "trace_id"):
            assert k in ctx


class TestEncryptionKey:
    def test_create_and_read_existing(self, tmp_path):
        (tmp_path / "logs").mkdir(exist_ok=True)
        cfg = _write_config(tmp_path, encrypt_logs=True)
        inst = EnhancedActivityLogger(cfg)
        try:
            key1 = inst.encryption_key
            assert key1 is not None
            # Re-read should yield the same key
            key2 = inst._get_or_create_encryption_key()
            assert key1 == key2
        finally:
            inst.shutdown(timeout=2)


class TestWriteOutputFiles:
    def test_write_json_log(self, logger_inst, make_log_entry):
        logger_inst._write_json_log(make_log_entry())
        files = list(os.listdir(logger_inst.log_dir))
        assert any(f.endswith(".json") for f in files)

    def test_write_csv_log(self, logger_inst, make_log_entry):
        logger_inst._write_csv_log(make_log_entry())
        files = list(os.listdir(logger_inst.log_dir))
        assert any(f.endswith(".csv") for f in files)

    def test_flush_batch_routes_to_outputs(self, tmp_path, make_log_entry):
        cfg = _write_config(tmp_path, output_formats=["json", "csv"])
        inst = EnhancedActivityLogger(cfg)
        try:
            inst._flush_batch([make_log_entry()])
            assert inst.metrics["logs_processed"] == 1
            files = os.listdir(inst.log_dir)
            assert any(f.endswith(".json") for f in files)
            assert any(f.endswith(".csv") for f in files)
        finally:
            inst.shutdown(timeout=2)

    def test_flush_batch_empty_is_noop(self, logger_inst):
        before = logger_inst.metrics["logs_processed"]
        logger_inst._flush_batch([])
        assert logger_inst.metrics["logs_processed"] == before

    def test_write_json_log_encrypted(self, tmp_path, make_log_entry):
        (tmp_path / "logs").mkdir(exist_ok=True)
        cfg = _write_config(tmp_path, encrypt_logs=True)
        inst = EnhancedActivityLogger(cfg)
        try:
            inst._write_json_log(make_log_entry())
            files = [f for f in os.listdir(inst.log_dir) if f.endswith(".json")]
            assert files
            content = (tmp_path / "logs" / files[0]).read_text()
            # Encrypted content should not contain plaintext field names
            assert "username" not in content
        finally:
            inst.shutdown(timeout=2)


class TestSafeExecute:
    def test_runs_function(self, logger_inst):
        called = []
        logger_inst._safe_execute(lambda: called.append(1), "task")
        assert called == [1]

    def test_swallows_exceptions(self, logger_inst):
        def boom():
            raise RuntimeError("x")
        # Should not raise
        logger_inst._safe_execute(boom, "task")


class TestHealthCheck:
    def test_health_check_runs(self, logger_inst):
        # Should not raise even without psutil errors
        logger_inst._perform_health_check()


class TestClientIPAndUserAgent:
    def test_get_client_ip_returns_string(self, logger_inst):
        assert isinstance(logger_inst._get_client_ip(), str)

    def test_get_user_agent_returns_string(self, logger_inst):
        assert logger_inst._get_user_agent() == "ActivityLogger/1.0"


class TestTriggerSecurityAlert:
    def test_queues_alert_entry(self, logger_inst, make_log_entry):
        before = logger_inst.log_queue.qsize()
        logger_inst._trigger_security_alert(make_log_entry())
        assert logger_inst.log_queue.qsize() >= before + 1


class TestFlushLogs:
    def test_flush_logs_returns_bool(self, logger_inst):
        assert logger_inst.flush_logs(timeout=2) in (True, False)


class TestAnalyticsWrappers:
    def test_get_system_health_requires_analytics(self, tmp_path):
        cfg = _write_config(tmp_path, output_formats=["json"])
        inst = EnhancedActivityLogger(cfg)
        try:
            with pytest.raises(RuntimeError):
                inst.get_system_health()
            with pytest.raises(RuntimeError):
                inst.detect_anomalies()
            with pytest.raises(RuntimeError):
                inst.generate_report()
        finally:
            inst.shutdown(timeout=2)

    def test_analytics_wrappers_delegate(self, logger_inst):
        logger_inst.analytics = MagicMock()
        logger_inst.analytics.get_system_health_metrics.return_value = {"cpu_usage": 1}
        logger_inst.analytics.detect_anomalies.return_value = []
        logger_inst.analytics.generate_report.return_value = {"r": 1}
        assert logger_inst.get_system_health() == {"cpu_usage": 1}
        assert logger_inst.detect_anomalies() == []
        assert logger_inst.generate_report() == {"r": 1}


class TestDeepMerge:
    def test_deep_merge(self, logger_inst):
        base = {"a": 1, "b": {"c": 2}}
        update = {"b": {"d": 3}, "e": 4}
        merged = logger_inst._deep_merge(base, update)
        assert merged == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
