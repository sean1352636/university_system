"""Tests for CareersService."""

import pytest


class TestCareersService:
    @pytest.fixture
    def careers_service(self, db_path):
        from education_system.college_system.modules.domain.careers.services.careers_service import CareersService
        return CareersService(db_path)

    def test_create_activity(self, careers_service, sample_student):
        activity = careers_service.create_activity(
            student_id=sample_student["id"],
            activity_type="guidance",
            description="Discussed university options",
        )
        assert activity["activity_type"] == "guidance"
        assert activity["description"] == "Discussed university options"

    def test_list_activities(self, careers_service, sample_student):
        careers_service.create_activity(
            student_id=sample_student["id"],
            activity_type="workshop", description="CV Writing",
        )
        activities = careers_service.list_activities(student_id=sample_student["id"])
        assert len(activities) >= 1

    def test_create_work_experience(self, careers_service, sample_student):
        we = careers_service.create_work_experience(
            student_id=sample_student["id"],
            employer_name="Tech Corp",
            role="Intern",
            start_date="2026-07-01",
            end_date="2026-07-14",
        )
        assert we["employer_name"] == "Tech Corp"

    def test_list_work_experience(self, careers_service, sample_student):
        careers_service.create_work_experience(
            student_id=sample_student["id"],
            employer_name="Company A", role="Shadow",
            start_date="2026-07-01",
        )
        records = careers_service.list_work_experience(student_id=sample_student["id"])
        assert len(records) >= 1
