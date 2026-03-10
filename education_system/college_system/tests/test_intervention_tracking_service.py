"""Tests for InterventionService."""

import pytest
from education_system.college_system.core.exceptions import InterventionError, ValidationError


class TestInterventionService:
    """Test suite for InterventionService."""

    def test_create_intervention(self, intervention_tracking_service):
        item = intervention_tracking_service.create_intervention(student_id=1, staff_id=1, intervention_type="test_intervention_type")
        assert item["id"] is not None

    def test_get_intervention(self, intervention_tracking_service):
        item = intervention_tracking_service.create_intervention(student_id=1, staff_id=1, intervention_type="test_intervention_type")
        found = intervention_tracking_service.get_intervention(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_interventions(self, intervention_tracking_service):
        intervention_tracking_service.create_intervention(student_id=1, staff_id=1, intervention_type="test_intervention_type")
        items = intervention_tracking_service.list_interventions()
        assert len(items) >= 1

    def test_update_intervention(self, intervention_tracking_service):
        item = intervention_tracking_service.create_intervention(student_id=1, staff_id=1, intervention_type="test_intervention_type")
        updated = intervention_tracking_service.update_intervention(item["id"], intervention_type="updated_value")
        assert updated["intervention_type"] == "updated_value"

    def test_delete_intervention(self, intervention_tracking_service):
        item = intervention_tracking_service.create_intervention(student_id=1, staff_id=1, intervention_type="test_intervention_type")
        result = intervention_tracking_service.delete_intervention(item["id"])
        assert result is True
        assert intervention_tracking_service.get_intervention(item["id"]) is None

    def test_count_interventions(self, intervention_tracking_service):
        intervention_tracking_service.create_intervention(student_id=1, staff_id=1, intervention_type="test_intervention_type")
        count = intervention_tracking_service.count_interventions()
        assert count >= 1

    def test_delete_nonexistent_raises(self, intervention_tracking_service):
        with pytest.raises(InterventionError):
            intervention_tracking_service.delete_intervention(99999)
