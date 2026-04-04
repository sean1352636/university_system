"""Tests for ObservationsService."""
import pytest
from education_system.secondary_school.modules.domain.staff.observations.services.observations_service import ObservationsService


@pytest.fixture
def observations_service(db_path):
    return ObservationsService(db_path)


class TestObservationsCRUD:
    def test_create(self, observations_service):
        rid = observations_service.create(
            staff_id="STF001", observer_id="STF002",
            observation_date="2026-03-20", subject="Science",
            class_name="10B", grade="Good",
        )
        assert isinstance(rid, int)
        record = observations_service.get(rid)
        assert record["staff_id"] == "STF001"
        assert record["observer_id"] == "STF002"
        assert record["observation_date"] == "2026-03-20"
        assert record["subject"] == "Science"
        assert record["grade"] == "Good"

    def test_list_all(self, observations_service):
        observations_service.create(
            staff_id="STF001", observation_date="2026-03-18", grade="Good",
        )
        observations_service.create(
            staff_id="STF002", observation_date="2026-03-19", grade="Outstanding",
        )
        result = observations_service.list_all()
        assert len(result) >= 2

    def test_get(self, observations_service):
        rid = observations_service.create(
            staff_id="STF003", observation_date="2026-03-15",
        )
        found = observations_service.get(rid)
        assert found is not None
        assert found["staff_id"] == "STF003"

    def test_update(self, observations_service):
        rid = observations_service.create(
            staff_id="STF001", observation_date="2026-03-20", grade="Good",
        )
        observations_service.update(rid, grade="Outstanding", strengths="Excellent questioning")
        updated = observations_service.get(rid)
        assert updated["grade"] == "Outstanding"
        assert updated["strengths"] == "Excellent questioning"

    def test_delete(self, observations_service):
        rid = observations_service.create(
            staff_id="STF005", observation_date="2026-03-10",
        )
        observations_service.delete(rid)
        assert observations_service.get(rid) is None
