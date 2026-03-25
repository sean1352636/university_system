"""Tests for pastoral care InterventionService."""
import pytest
from education_system.secondary_school.modules.domain.pastoral_care.interventions.services.intervention_service import InterventionService


@pytest.fixture
def pastoral_intervention_service(db_path):
    return InterventionService(db_path)


class TestPastoralInterventionCRUD:
    def test_create(self, pastoral_intervention_service):
        rid = pastoral_intervention_service.create(
            student_id="SEC0001", intervention_type="mentoring",
            reason="Low attendance", lead_staff_id="STF001",
            targets="Improve to 95%",
        )
        assert isinstance(rid, int)
        record = pastoral_intervention_service.get(rid)
        assert record["student_id"] == "SEC0001"
        assert record["intervention_type"] == "mentoring"
        assert record["reason"] == "Low attendance"
        assert record["lead_staff_id"] == "STF001"
        assert record["targets"] == "Improve to 95%"
        assert record["status"] == "active"

    def test_list_all(self, pastoral_intervention_service):
        pastoral_intervention_service.create(
            student_id="SEC0001", intervention_type="mentoring",
        )
        pastoral_intervention_service.create(
            student_id="SEC0002", intervention_type="tutoring",
        )
        result = pastoral_intervention_service.list_all()
        assert len(result) >= 2

    def test_get(self, pastoral_intervention_service):
        rid = pastoral_intervention_service.create(
            student_id="SEC0003", intervention_type="counselling",
        )
        found = pastoral_intervention_service.get(rid)
        assert found is not None
        assert found["intervention_type"] == "counselling"

    def test_update(self, pastoral_intervention_service):
        rid = pastoral_intervention_service.create(
            student_id="SEC0001", intervention_type="mentoring",
        )
        pastoral_intervention_service.update(rid, status="completed", end_date="2026-06-30")
        updated = pastoral_intervention_service.get(rid)
        assert updated["status"] == "completed"
        assert updated["end_date"] == "2026-06-30"

    def test_delete(self, pastoral_intervention_service):
        rid = pastoral_intervention_service.create(
            student_id="SEC0004", intervention_type="behaviour support",
        )
        pastoral_intervention_service.delete(rid)
        assert pastoral_intervention_service.get(rid) is None
