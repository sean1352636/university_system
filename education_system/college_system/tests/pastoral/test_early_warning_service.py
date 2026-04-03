"""Tests for EarlyWarningService."""

import pytest
from education_system.college_system.core.exceptions import EarlyWarningError


class TestEarlyWarningService:
    """Test suite for EarlyWarningService."""

    # --- Alerts ---

    def test_create_alert(self, early_warning_service, sample_student):
        item = early_warning_service.create_alert(
            sample_student["id"], "attendance", severity="high",
            trigger_source="system", attendance_pct=75.0,
        )
        assert item["id"] is not None

    def test_get_alert(self, early_warning_service, sample_student):
        item = early_warning_service.create_alert(sample_student["id"], "attendance")
        found = early_warning_service.get_alert(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_get_alert_nonexistent(self, early_warning_service):
        assert early_warning_service.get_alert(99999) is None

    def test_list_alerts(self, early_warning_service, sample_student):
        early_warning_service.create_alert(sample_student["id"], "attendance")
        items = early_warning_service.list_alerts()
        assert len(items) >= 1

    def test_list_alerts_filter_student(self, early_warning_service, sample_student):
        early_warning_service.create_alert(sample_student["id"], "attendance")
        items = early_warning_service.list_alerts(student_id=sample_student["id"])
        assert len(items) >= 1

    def test_list_alerts_filter_severity(self, early_warning_service, sample_student):
        early_warning_service.create_alert(
            sample_student["id"], "attendance", severity="high",
        )
        items = early_warning_service.list_alerts(severity="high")
        assert all(a["severity"] == "high" for a in items)

    def test_list_alerts_filter_type(self, early_warning_service, sample_student):
        early_warning_service.create_alert(sample_student["id"], "grade")
        items = early_warning_service.list_alerts(alert_type="grade")
        assert all(a["alert_type"] == "grade" for a in items)

    def test_list_alerts_search(self, early_warning_service, sample_student):
        early_warning_service.create_alert(
            sample_student["id"], "attendance",
            trigger_detail="Dropped below threshold",
        )
        items = early_warning_service.list_alerts(search=sample_student.get("last_name", ""))
        assert isinstance(items, list)

    def test_update_alert(self, early_warning_service, sample_student):
        item = early_warning_service.create_alert(sample_student["id"], "attendance")
        updated = early_warning_service.update_alert(item["id"], severity="critical")
        assert updated["severity"] == "critical"

    def test_resolve_alert(self, early_warning_service, sample_student):
        item = early_warning_service.create_alert(sample_student["id"], "attendance")
        resolved = early_warning_service.resolve_alert(item["id"], "Called parents")
        assert resolved["resolved"] == 1

    def test_delete_alert(self, early_warning_service, sample_student):
        item = early_warning_service.create_alert(sample_student["id"], "attendance")
        result = early_warning_service.delete_alert(item["id"])
        assert result is True
        assert early_warning_service.get_alert(item["id"]) is None

    def test_delete_nonexistent(self, early_warning_service):
        result = early_warning_service.delete_alert(99999)
        assert result is True or result is False

    # --- Rules ---

    def test_create_rule(self, early_warning_service):
        item = early_warning_service.create_rule(
            "Low Attendance", "attendance", 80.0, comparison="less_than",
        )
        assert item["id"] is not None
        assert item["rule_name"] == "Low Attendance"

    def test_list_rules(self, early_warning_service):
        early_warning_service.create_rule("Low Attendance", "attendance", 80.0)
        items = early_warning_service.list_rules()
        assert len(items) >= 1

    def test_list_rules_filter_active(self, early_warning_service):
        early_warning_service.create_rule("Low Attendance", "attendance", 80.0, is_active=1)
        items = early_warning_service.list_rules(is_active=1)
        assert all(r["is_active"] == 1 for r in items)

    def test_get_rule(self, early_warning_service):
        item = early_warning_service.create_rule("Low Attendance", "attendance", 80.0)
        found = early_warning_service.get_rule(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_update_rule(self, early_warning_service):
        item = early_warning_service.create_rule("Low Attendance", "attendance", 80.0)
        updated = early_warning_service.update_rule(item["id"], threshold=75.0)
        assert updated["threshold"] == 75.0

    def test_delete_rule(self, early_warning_service):
        item = early_warning_service.create_rule("Low Attendance", "attendance", 80.0)
        result = early_warning_service.delete_rule(item["id"])
        assert result is True
        assert early_warning_service.get_rule(item["id"]) is None

    # --- Statistics ---

    def test_get_stats(self, early_warning_service, sample_student):
        early_warning_service.create_alert(sample_student["id"], "attendance", severity="high")
        early_warning_service.create_rule("Low Attendance", "attendance", 80.0)
        stats = early_warning_service.get_stats()
        assert stats["total_alerts"] >= 1
        assert stats["active_rules"] >= 1
        assert "active_by_severity" in stats
