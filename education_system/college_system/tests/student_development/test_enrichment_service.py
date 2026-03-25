"""Tests for EnrichmentService."""

import pytest
from education_system.college_system.core.exceptions import EnrichmentError, ValidationError


class TestEnrichmentService:
    """Test suite for EnrichmentService."""

    def test_create_activity(self, enrichment_service):
        item = enrichment_service.create_activity(name="test_name", activity_type="test_activity_type")
        assert item["id"] is not None

    def test_get_activity(self, enrichment_service):
        item = enrichment_service.create_activity(name="test_name", activity_type="test_activity_type")
        found = enrichment_service.get_activity(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_activities(self, enrichment_service):
        enrichment_service.create_activity(name="test_name", activity_type="test_activity_type")
        items = enrichment_service.list_activities()
        assert len(items) >= 1

    def test_update_activity(self, enrichment_service):
        item = enrichment_service.create_activity(name="test_name", activity_type="test_activity_type")
        updated = enrichment_service.update_activity(item["id"], name="updated_value")
        assert updated["name"] == "updated_value"

    def test_delete_activity(self, enrichment_service):
        item = enrichment_service.create_activity(name="test_name", activity_type="test_activity_type")
        result = enrichment_service.delete_activity(item["id"])
        assert result is True
        assert enrichment_service.get_activity(item["id"]) is None

    def test_count_activities(self, enrichment_service):
        enrichment_service.create_activity(name="test_name", activity_type="test_activity_type")
        count = enrichment_service.count_activities()
        assert count >= 1

    def test_delete_nonexistent_raises(self, enrichment_service):
        with pytest.raises(EnrichmentError):
            enrichment_service.delete_activity(99999)
