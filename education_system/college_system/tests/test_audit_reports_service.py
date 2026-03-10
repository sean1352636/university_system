"""Tests for AuditReportService."""

import pytest
from education_system.college_system.core.exceptions import AuditReportError, ValidationError


class TestAuditReportService:
    """Test suite for AuditReportService."""

    def test_create_report(self, audit_reports_service):
        item = audit_reports_service.create_report(report_type="test_report_type", title="test_title")
        assert item["id"] is not None

    def test_get_report(self, audit_reports_service):
        item = audit_reports_service.create_report(report_type="test_report_type", title="test_title")
        found = audit_reports_service.get_report(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_reports(self, audit_reports_service):
        audit_reports_service.create_report(report_type="test_report_type", title="test_title")
        items = audit_reports_service.list_reports()
        assert len(items) >= 1

    def test_update_report(self, audit_reports_service):
        item = audit_reports_service.create_report(report_type="test_report_type", title="test_title")
        updated = audit_reports_service.update_report(item["id"], report_type="updated_value")
        assert updated["report_type"] == "updated_value"

    def test_delete_report(self, audit_reports_service):
        item = audit_reports_service.create_report(report_type="test_report_type", title="test_title")
        result = audit_reports_service.delete_report(item["id"])
        assert result is True
        assert audit_reports_service.get_report(item["id"]) is None

    def test_count_reports(self, audit_reports_service):
        audit_reports_service.create_report(report_type="test_report_type", title="test_title")
        count = audit_reports_service.count_reports()
        assert count >= 1

    def test_delete_nonexistent_raises(self, audit_reports_service):
        with pytest.raises(AuditReportError):
            audit_reports_service.delete_report(99999)
