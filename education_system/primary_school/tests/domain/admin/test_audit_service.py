"""Tests for the AuditService in the Primary School system."""

import pytest


class TestLogAction:
    """Tests for logging audit actions."""

    def test_log_action_returns_id(self, audit_service):
        """Logging an action returns a positive integer ID."""
        log_id = audit_service.log_action(
            username="admin",
            action="CREATE",
            table_name="pupils",
            record_id=1,
            details="Created pupil record",
        )
        assert isinstance(log_id, int)
        assert log_id > 0

    def test_log_action_persists(self, audit_service):
        """Logged action appears in the audit log."""
        audit_service.log_action(
            username="teacher1",
            action="UPDATE",
            table_name="assessments",
            details="Updated grade",
        )
        logs = audit_service.get_log()
        assert len(logs) == 1
        assert logs[0]["username"] == "teacher1"
        assert logs[0]["action"] == "UPDATE"

    def test_log_multiple_actions(self, audit_service):
        """Multiple actions are stored independently."""
        audit_service.log_action(username="u1", action="CREATE")
        audit_service.log_action(username="u2", action="DELETE")
        logs = audit_service.get_log()
        assert len(logs) == 2


class TestGetLog:
    """Tests for querying the audit log."""

    def test_get_log_empty_db(self, audit_service):
        """Querying an empty audit log returns an empty list."""
        assert audit_service.get_log() == []

    def test_filter_by_username(self, audit_service):
        """Filtering by username returns only that user's actions."""
        audit_service.log_action(username="alice", action="LOGIN")
        audit_service.log_action(username="bob", action="LOGIN")
        logs = audit_service.get_log(username="alice")
        assert len(logs) == 1
        assert logs[0]["username"] == "alice"

    def test_filter_by_action(self, audit_service):
        """Filtering by action returns only matching entries."""
        audit_service.log_action(username="admin", action="CREATE")
        audit_service.log_action(username="admin", action="DELETE")
        logs = audit_service.get_log(action="DELETE")
        assert len(logs) == 1
        assert logs[0]["action"] == "DELETE"

    def test_limit_parameter(self, audit_service):
        """The limit parameter caps the number of results."""
        for i in range(5):
            audit_service.log_action(username="user", action=f"ACTION_{i}")
        logs = audit_service.get_log(limit=3)
        assert len(logs) == 3

    def test_log_contains_details(self, audit_service):
        """Logged details are preserved in the retrieved record."""
        audit_service.log_action(
            username="admin",
            action="EXPORT",
            table_name="pupils",
            record_id=42,
            details="Exported pupil data to CSV",
        )
        logs = audit_service.get_log()
        assert logs[0]["details"] == "Exported pupil data to CSV"
        assert logs[0]["table_name"] == "pupils"
        assert logs[0]["record_id"] == "42"
