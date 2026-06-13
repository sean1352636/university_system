"""Targeted tests for simple_activity_logger.logger (EnhancedActivityLogger).

Full instantiation spins up daemon threads and touches DB paths; the root
conftest.py suppresses the daemon threads, so we test sparingly and focus
on pure-logic helpers and a smoke-level construction path.
"""
import json

import pytest

import importlib

# Note: importing the package binds `.logger` to the singleton instance via
# module_api; explicitly load the submodule to access EnhancedActivityLogger.
logger_mod = importlib.import_module(
    "education_system.university_system.modules.shared.utils.simple_activity_logger.logger"
)


@pytest.fixture
def instance(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "log_dir": str(tmp_path / "logs"),
        "output_formats": ["json"],
        "enable_pii_detection": False,
    }))
    inst = logger_mod.EnhancedActivityLogger(config_path=str(cfg))
    yield inst
    try:
        inst.shutdown_event.set()
    except Exception:
        pass


class TestDeepMerge:
    def test_merges_nested_dicts(self, instance):
        base = {"a": 1, "b": {"x": 1, "y": 2}}
        update = {"b": {"y": 20, "z": 30}, "c": 3}
        instance._deep_merge(base, update)
        assert base == {"a": 1, "b": {"x": 1, "y": 20, "z": 30}, "c": 3}

    def test_overwrites_non_dict_values(self, instance):
        base = {"a": [1, 2]}
        instance._deep_merge(base, {"a": [9]})
        assert base["a"] == [9]


class TestGeolocation:
    def test_local_ip_returns_local(self, instance):
        geo = instance._get_geolocation("127.0.0.1")
        assert geo["country"] == "Local"

    def test_empty_ip_returns_local(self, instance):
        geo = instance._get_geolocation("")
        assert geo["country"] == "Local"

    def test_external_ip_returns_unknown(self, instance):
        geo = instance._get_geolocation("8.8.8.8")
        assert geo["country"] == "Unknown"


class TestSessionContext:
    def test_returns_required_keys(self, instance):
        ctx = instance._get_session_context()
        for key in ("session_id", "ip_address", "user_agent", "trace_id"):
            assert key in ctx


class TestUserAgent:
    def test_returns_default(self, instance):
        assert instance._get_user_agent() == "ActivityLogger/1.0"


class TestConfigLoading:
    def test_default_min_log_level(self, instance):
        assert instance.min_log_level == logger_mod.LogLevel.INFO

    def test_log_dir_created(self, instance):
        import os
        assert os.path.exists(instance.log_dir)


class TestGetMetrics:
    def test_metrics_shape(self, instance):
        m = instance.get_metrics()
        assert "logs_processed" in m
        assert "queue_size" in m
        assert "queue_maxsize" in m


class TestLogActivityFiltering:
    def test_below_min_level_short_circuits(self, instance):
        # DEBUG (10) < INFO (20) → returns True without queuing
        assert instance.log_activity(
            "u", "alice", "user", "noop", "m",
            log_level=logger_mod.LogLevel.DEBUG,
        ) is True
        assert instance.log_queue.qsize() == 0

    def test_at_or_above_min_level_queues(self, instance):
        assert instance.log_activity(
            "u", "alice", "user", "noop", "m",
            log_level=logger_mod.LogLevel.INFO,
        ) is True
        assert instance.log_queue.qsize() >= 1
