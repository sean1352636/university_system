"""Tests for DataDashboardService."""

import pytest
from education_system.college_system.core.exceptions import DataDashboardError, ValidationError


class TestDataDashboardService:
    """Test suite for DataDashboardService."""

    def test_create_widget(self, data_dashboard_service):
        item = data_dashboard_service.create_widget(user_id=1, widget_type="test_widget_type")
        assert item["id"] is not None

    def test_get_widget(self, data_dashboard_service):
        item = data_dashboard_service.create_widget(user_id=1, widget_type="test_widget_type")
        found = data_dashboard_service.get_widget(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_widgets(self, data_dashboard_service):
        data_dashboard_service.create_widget(user_id=1, widget_type="test_widget_type")
        items = data_dashboard_service.list_widgets()
        assert len(items) >= 1

    def test_update_widget(self, data_dashboard_service):
        item = data_dashboard_service.create_widget(user_id=1, widget_type="test_widget_type")
        updated = data_dashboard_service.update_widget(item["id"], widget_type="updated_value")
        assert updated["widget_type"] == "updated_value"

    def test_delete_widget(self, data_dashboard_service):
        item = data_dashboard_service.create_widget(user_id=1, widget_type="test_widget_type")
        result = data_dashboard_service.delete_widget(item["id"])
        assert result is True
        assert data_dashboard_service.get_widget(item["id"]) is None

    def test_count_widgets(self, data_dashboard_service):
        data_dashboard_service.create_widget(user_id=1, widget_type="test_widget_type")
        count = data_dashboard_service.count_widgets()
        assert count >= 1

    def test_delete_nonexistent_raises(self, data_dashboard_service):
        with pytest.raises(DataDashboardError):
            data_dashboard_service.delete_widget(99999)
