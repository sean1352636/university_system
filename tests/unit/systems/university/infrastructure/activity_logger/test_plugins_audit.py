"""Tests for plugins.audit.AuditTrailPlugin"""
import json
import os

from education_system.systems.university.infrastructure.utils.activity_logger.plugins.audit import (
    AuditTrailPlugin,
)


class TestAuditTrailPlugin:
    def test_writes_audit_for_audit_action(self, tmp_path, make_log_entry):
        audit = tmp_path / "audit.log"
        p = AuditTrailPlugin({"audit_file": str(audit), "audit_actions": ["delete"]})
        p.after_log(make_log_entry(action="delete"), success=True)
        lines = audit.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "delete"
        assert entry["username"] == "alice"

    def test_skipped_for_unsuccessful(self, tmp_path, make_log_entry):
        audit = tmp_path / "audit.log"
        p = AuditTrailPlugin({"audit_file": str(audit)})
        p.after_log(make_log_entry(action="delete"), success=False)
        assert not audit.exists()

    def test_skipped_for_non_audit_action(self, tmp_path, make_log_entry):
        audit = tmp_path / "audit.log"
        p = AuditTrailPlugin({"audit_file": str(audit), "audit_actions": ["delete"]})
        p.after_log(make_log_entry(action="read"), success=True)
        assert not audit.exists()

    def test_default_audit_actions(self, tmp_path, make_log_entry):
        audit = tmp_path / "audit.log"
        p = AuditTrailPlugin({"audit_file": str(audit)})
        for a in ("create", "update", "delete", "login", "logout", "export", "admin"):
            p.after_log(make_log_entry(action=a), success=True)
        assert len(audit.read_text().strip().splitlines()) == 7

    def test_get_audit_stats_no_file(self, tmp_path):
        p = AuditTrailPlugin({"audit_file": str(tmp_path / "missing.log")})
        stats = p.get_audit_stats()
        assert stats == {"total_entries": 0, "file_size": 0}

    def test_get_audit_stats_with_file(self, tmp_path, make_log_entry):
        audit = tmp_path / "audit.log"
        p = AuditTrailPlugin({"audit_file": str(audit), "audit_actions": ["delete"]})
        p.after_log(make_log_entry(action="delete"), success=True)
        p.after_log(make_log_entry(action="delete"), success=True)
        stats = p.get_audit_stats()
        assert stats["total_entries"] == 2
        assert stats["file_size"] > 0
        assert stats["file_path"] == str(audit)
