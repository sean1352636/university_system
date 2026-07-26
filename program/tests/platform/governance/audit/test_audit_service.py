"""Tests for shared.audit.audit_service — AuditService, init_audit_db, get_audit_db_path."""

import pytest

from education_system.platform.governance.audit.audit_service import (
    AuditService,
    init_audit_db,
    get_audit_db_path,
)


@pytest.fixture
def audit_db(tmp_path):
    """Fresh audit database for each test."""
    return str(tmp_path / "test_audit.db")


class TestInitAuditDb:
    """Test init_audit_db and get_audit_db_path."""

    def test_get_audit_db_path_returns_path(self):
        path = get_audit_db_path()
        assert str(path).endswith("audit.db")

    def test_init_creates_tables(self, audit_db):
        init_audit_db(audit_db)
        import sqlite3
        conn = sqlite3.connect(audit_db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "audit_log" in tables

    def test_init_is_idempotent(self, audit_db):
        init_audit_db(audit_db)
        init_audit_db(audit_db)  # should not raise


class TestAuditServiceLog:
    """Test log and log_security."""

    def test_log_returns_int(self, audit_db):
        svc = AuditService(audit_db)
        entry_id = svc.log("user.login", system_key="university", user_id=1)
        assert isinstance(entry_id, int)
        assert entry_id >= 1

    def test_log_security_sets_severity(self, audit_db):
        svc = AuditService(audit_db)
        eid = svc.log_security("failed_login", system_key="sixth_form", user_id=5)
        rows = svc.query(user_id=5)
        assert rows[0]["severity"] == "security"

    def test_log_with_dict_details(self, audit_db):
        svc = AuditService(audit_db)
        eid = svc.log("data.export", details={"format": "csv", "rows": 100})
        rows = svc.query(action="data.export")
        assert "csv" in rows[0]["details"]


class TestAuditServiceQuery:
    """Test query filters."""

    def test_filter_by_system_key(self, audit_db):
        svc = AuditService(audit_db)
        svc.log("a", system_key="sixth_form")
        svc.log("b", system_key="university")

        results = svc.query(system_key="sixth_form")
        assert all(r["system_key"] == "sixth_form" for r in results)
        assert len(results) == 1

    def test_filter_by_action(self, audit_db):
        svc = AuditService(audit_db)
        svc.log("user.login")
        svc.log("user.logout")

        results = svc.query(action="login")
        assert len(results) == 1
        assert "login" in results[0]["action"]

    def test_filter_by_severity(self, audit_db):
        svc = AuditService(audit_db)
        svc.log("x", severity="info")
        svc.log("y", severity="critical")

        results = svc.query(severity="critical")
        assert len(results) == 1

    def test_limit_and_offset(self, audit_db):
        svc = AuditService(audit_db)
        for i in range(5):
            svc.log(f"action_{i}")

        page1 = svc.query(limit=2, offset=0)
        page2 = svc.query(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["id"] != page2[0]["id"]


class TestVerifyIntegrity:
    """Test verify_integrity."""

    def test_valid_entry_passes(self, audit_db):
        svc = AuditService(audit_db)
        eid = svc.log("test.action", system_key="shared", user_id=1)
        assert svc.verify_integrity(eid) is True

    def test_nonexistent_entry_returns_false(self, audit_db):
        svc = AuditService(audit_db)
        assert svc.verify_integrity(99999) is False


class TestGetStats:
    """Test get_stats."""

    def test_returns_expected_keys(self, audit_db):
        svc = AuditService(audit_db)
        svc.log("action_a", severity="info")
        svc.log("action_b", severity="warning")

        stats = svc.get_stats(days=30)
        assert "total" in stats
        assert "by_severity" in stats
        assert "top_actions" in stats
        assert stats["total"] >= 2

    def test_stats_filtered_by_system_key(self, audit_db):
        svc = AuditService(audit_db)
        svc.log("x", system_key="sixth_form")
        svc.log("y", system_key="university")

        stats = svc.get_stats(system_key="sixth_form")
        assert stats["total"] == 1
