"""Tests for simple_activity_logger.plugins.audit."""
import json

from education_system.systems.university.infrastructure.utils.activity_logger.plugins.audit import (
    AuditTrailPlugin,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


def _entry(action="create", **overrides):
    base = dict(
        timestamp="t", user_id="u1", username="alice", role="user",
        action=action, module="m", details="d", status="success",
        log_level="INFO", session_id="s", ip_address="1.1.1.1",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="LOW",
        trace_id="trace-x",
    )
    base.update(overrides)
    return LogEntry(**base)


class TestAuditTrailPlugin:
    def test_writes_audit_entry_for_tracked_action(self, tmp_path):
        f = tmp_path / "audit.log"
        plugin = AuditTrailPlugin({"audit_file": str(f), "audit_actions": ["create"]})
        plugin.after_log(_entry(action="create"), success=True)
        lines = f.read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "create"
        assert entry["trace_id"] == "trace-x"

    def test_skips_when_action_not_tracked(self, tmp_path):
        f = tmp_path / "audit.log"
        plugin = AuditTrailPlugin({"audit_file": str(f), "audit_actions": ["delete"]})
        plugin.after_log(_entry(action="read"), success=True)
        assert not f.exists()

    def test_skips_when_failure(self, tmp_path):
        f = tmp_path / "audit.log"
        plugin = AuditTrailPlugin({"audit_file": str(f), "audit_actions": ["create"]})
        plugin.after_log(_entry(action="create"), success=False)
        assert not f.exists()

    def test_default_audit_actions(self, tmp_path):
        f = tmp_path / "audit.log"
        plugin = AuditTrailPlugin({"audit_file": str(f)})
        assert "login" in plugin.audit_actions
        assert "delete" in plugin.audit_actions

    def test_get_audit_stats_no_file(self, tmp_path):
        plugin = AuditTrailPlugin({"audit_file": str(tmp_path / "nope.log")})
        stats = plugin.get_audit_stats()
        assert stats["total_entries"] == 0
        assert stats["file_size"] == 0

    def test_get_audit_stats_counts_lines(self, tmp_path):
        f = tmp_path / "audit.log"
        plugin = AuditTrailPlugin({"audit_file": str(f), "audit_actions": ["create"]})
        plugin.after_log(_entry(), True)
        plugin.after_log(_entry(), True)
        plugin.after_log(_entry(), True)
        stats = plugin.get_audit_stats()
        assert stats["total_entries"] == 3
        assert stats["file_size"] > 0
