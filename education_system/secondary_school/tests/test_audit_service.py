"""Tests for AuditService."""
import pytest


class TestAudit:
    def test_log_creates_entry(self, audit_service):
        audit_service.log(action="login", module="auth", username="admin")
        entries = audit_service.list_entries()
        assert len(entries) >= 1
        assert entries[0]["action"] == "login"

    def test_list_entries_returns_entries(self, audit_service):
        audit_service.log(action="create", module="students", username="teacher")
        audit_service.log(action="update", module="grades", username="teacher")
        entries = audit_service.list_entries()
        assert len(entries) >= 2

    def test_list_entries_filters_by_action(self, audit_service):
        audit_service.log(action="create", module="students", username="t1")
        audit_service.log(action="delete", module="students", username="t2")
        entries = audit_service.list_entries(action="create")
        assert all(e["action"] == "create" for e in entries)

    def test_list_entries_filters_by_module(self, audit_service):
        audit_service.log(action="create", module="students", username="t1")
        audit_service.log(action="create", module="grades", username="t2")
        entries = audit_service.list_entries(module="students")
        assert all(e["module"] == "students" for e in entries)

    def test_entry_count(self, audit_service):
        audit_service.log(action="login", module="auth", username="admin")
        audit_service.log(action="logout", module="auth", username="admin")
        count = audit_service.entry_count()
        assert count >= 2

    def test_clear_old_removes_old_entries(self, audit_service):
        from education_system.secondary_school.infrastructure.database.db import connect
        audit_service.log(action="login", module="auth", username="admin")
        # Backdate the entry so clear_old can find it
        conn = connect(audit_service._db_path)
        conn.execute("UPDATE audit_log SET created_at = datetime('now', '-400 days')")
        conn.commit()
        conn.close()
        audit_service.clear_old(days=365)
        count = audit_service.entry_count()
        assert count == 0
