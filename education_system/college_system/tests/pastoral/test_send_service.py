"""Tests for SENDService (Special Educational Needs and Disabilities)."""

import pytest


class TestSENDService:
    @pytest.fixture
    def send_service(self, db_path):
        from education_system.college_system.modules.domain.send.services.send_service import SENDService
        return SENDService(db_path)

    def test_create_record(self, send_service, sample_student):
        record = send_service.create_record(
            student_id=sample_student["id"],
            send_status="send_support",
            primary_need="cognition",
            support_plan="25% extra time on assessments",
            extra_time_percent=25,
        )
        assert record["send_status"] == "send_support"
        assert record["primary_need"] == "cognition"
        assert record["extra_time_percent"] == 25

    def test_list_records(self, send_service, sample_student):
        send_service.create_record(
            student_id=sample_student["id"],
            send_status="send_support",
            primary_need="semh",
            notes="ADHD support",
        )
        records = send_service.list_records()
        assert len(records) >= 1

    def test_get_record(self, send_service, sample_student):
        created = send_service.create_record(
            student_id=sample_student["id"],
            send_status="send_support",
            primary_need="sensory_physical",
            notes="Enlarged text needed",
        )
        found = send_service.get_record(created["id"])
        assert found["primary_need"] == "sensory_physical"

    def test_update_record(self, send_service, sample_student):
        record = send_service.create_record(
            student_id=sample_student["id"],
            send_status="monitoring",
            primary_need="cognition",
        )
        updated = send_service.update_record(
            record["id"], support_plan="Updated support plan",
        )
        assert updated["support_plan"] == "Updated support plan"

    def test_get_student_record(self, send_service, sample_student):
        send_service.create_record(
            student_id=sample_student["id"],
            send_status="ehcp",
            primary_need="communication",
            notes="ASD support needed",
        )
        record = send_service.get_student_record(sample_student["id"])
        assert record is not None
        assert record["primary_need"] == "communication"
