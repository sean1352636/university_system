"""Tests for BehaviourService."""

import pytest
from education_system.college_system.core.exceptions import BehaviourError


class TestBehaviourService:
    @pytest.fixture
    def behaviour_service(self, db_path):
        from education_system.college_system.modules.domain.behaviour.services.behaviour_service import BehaviourService
        return BehaviourService(db_path)

    def test_record_incident(self, behaviour_service, sample_student):
        record = behaviour_service.record_incident(
            student_id=sample_student["id"],
            recorded_by=1,
            type="concern",
            description="Talking during lesson",
            category="disruption",
        )
        assert record["type"] == "concern"
        assert record["category"] == "disruption"

    def test_list_records(self, behaviour_service, sample_student):
        behaviour_service.record_incident(
            student_id=sample_student["id"], recorded_by=1,
            type="concern", description="Late to class",
        )
        records = behaviour_service.list_records(student_id=sample_student["id"])
        assert len(records) >= 1

    def test_get_record(self, behaviour_service, sample_student):
        created = behaviour_service.record_incident(
            student_id=sample_student["id"], recorded_by=1,
            type="reward", description="Excellent work",
        )
        found = behaviour_service.get_record(created["id"])
        assert found["description"] == "Excellent work"

    def test_update_record(self, behaviour_service, sample_student):
        created = behaviour_service.record_incident(
            student_id=sample_student["id"], recorded_by=1,
            type="concern", description="Minor issue",
        )
        updated = behaviour_service.update_record(
            created["id"], action_taken="Verbal warning",
        )
        assert updated["action_taken"] == "Verbal warning"

    def test_get_student_records(self, behaviour_service, sample_student):
        behaviour_service.record_incident(
            student_id=sample_student["id"], recorded_by=1,
            type="reward", description="Helpful",
        )
        behaviour_service.record_incident(
            student_id=sample_student["id"], recorded_by=1,
            type="sanction", description="Late",
        )
        records = behaviour_service.get_student_records(sample_student["id"])
        assert len(records) >= 2

    def test_count_by_type(self, behaviour_service, sample_student):
        behaviour_service.record_incident(
            student_id=sample_student["id"], recorded_by=1,
            type="reward", description="Good",
        )
        counts = behaviour_service.count_by_type(sample_student["id"])
        assert isinstance(counts, dict)
