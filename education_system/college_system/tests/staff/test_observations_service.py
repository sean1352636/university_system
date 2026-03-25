"""Tests for ObservationService."""

import pytest
from education_system.college_system.core.exceptions import ObservationError, ValidationError


class TestObservationService:
    """Test suite for ObservationService."""

    def test_create_observation(self, observations_service):
        item = observations_service.create_observation(teacher_id=1, observation_type="test_observation_type")
        assert item["id"] is not None

    def test_get_observation(self, observations_service):
        item = observations_service.create_observation(teacher_id=1, observation_type="test_observation_type")
        found = observations_service.get_observation(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_observations(self, observations_service):
        observations_service.create_observation(teacher_id=1, observation_type="test_observation_type")
        items = observations_service.list_observations()
        assert len(items) >= 1

    def test_update_observation(self, observations_service):
        item = observations_service.create_observation(teacher_id=1, observation_type="test_observation_type")
        updated = observations_service.update_observation(item["id"], scheduled_date="updated_value")
        assert updated["scheduled_date"] == "updated_value"

    def test_delete_observation(self, observations_service):
        item = observations_service.create_observation(teacher_id=1, observation_type="test_observation_type")
        result = observations_service.delete_observation(item["id"])
        assert result is True
        assert observations_service.get_observation(item["id"]) is None

    def test_count_observations(self, observations_service):
        observations_service.create_observation(teacher_id=1, observation_type="test_observation_type")
        count = observations_service.count_observations()
        assert count >= 1

    def test_delete_nonexistent_raises(self, observations_service):
        with pytest.raises(ObservationError):
            observations_service.delete_observation(99999)
