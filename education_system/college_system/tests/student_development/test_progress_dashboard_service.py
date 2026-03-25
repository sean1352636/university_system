"""Tests for ProgressDashboardService."""

import pytest
from education_system.college_system.core.exceptions import ProgressDashboardError, ValidationError


class TestProgressDashboardService:
    """Test suite for ProgressDashboardService."""

    def test_create_snapshot(self, progress_dashboard_service):
        item = progress_dashboard_service.create_snapshot(student_id=1)
        assert item["id"] is not None

    def test_get_snapshot(self, progress_dashboard_service):
        item = progress_dashboard_service.create_snapshot(student_id=1)
        found = progress_dashboard_service.get_snapshot(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_snapshots(self, progress_dashboard_service):
        progress_dashboard_service.create_snapshot(student_id=1)
        items = progress_dashboard_service.list_snapshots()
        assert len(items) >= 1

    def test_update_snapshot(self, progress_dashboard_service):
        item = progress_dashboard_service.create_snapshot(student_id=1)
        updated = progress_dashboard_service.update_snapshot(item["id"], snapshot_date="updated_value")
        assert updated["snapshot_date"] == "updated_value"

    def test_delete_snapshot(self, progress_dashboard_service):
        item = progress_dashboard_service.create_snapshot(student_id=1)
        result = progress_dashboard_service.delete_snapshot(item["id"])
        assert result is True
        assert progress_dashboard_service.get_snapshot(item["id"]) is None

    def test_count_snapshots(self, progress_dashboard_service):
        progress_dashboard_service.create_snapshot(student_id=1)
        count = progress_dashboard_service.count_snapshots()
        assert count >= 1

    def test_delete_nonexistent_raises(self, progress_dashboard_service):
        with pytest.raises(ProgressDashboardError):
            progress_dashboard_service.delete_snapshot(99999)
