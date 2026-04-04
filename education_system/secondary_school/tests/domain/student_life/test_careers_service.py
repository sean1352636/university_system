"""Tests for CareersService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.careers.services.careers_service import CareersService


@pytest.fixture
def careers_service(db_path):
    return CareersService(db_path)


class TestCareersMeetings:
    def test_add_meeting(self, careers_service, sample_student):
        m = careers_service.add_meeting(
            student_id=sample_student["id"], meeting_date="2026-03-20",
            adviser="Mrs Johnson", career_interests="Engineering",
            action_points="Research apprenticeships", destination="university",
        )
        assert m["student_id"] == sample_student["id"]
        assert m["adviser"] == "Mrs Johnson"

    def test_list_meetings(self, careers_service, sample_student):
        careers_service.add_meeting(sample_student["id"], "2026-03-20")
        careers_service.add_meeting(sample_student["id"], "2026-03-25")
        result = careers_service.list_meetings(student_id=sample_student["id"])
        assert len(result) == 2

    def test_delete_meeting(self, careers_service, sample_student):
        m = careers_service.add_meeting(sample_student["id"], "2026-03-20")
        careers_service.delete_meeting(m["id"])
        result = careers_service.list_meetings(student_id=sample_student["id"])
        assert len(result) == 0


class TestWorkExperience:
    def test_add_placement(self, careers_service, sample_student):
        p = careers_service.add_placement(
            student_id=sample_student["id"], employer="Tech Corp",
            start_date="2026-06-01", end_date="2026-06-05",
            role="IT Assistant", contact_name="Bob",
        )
        assert p["employer"] == "Tech Corp"
        assert p["status"] == "planned"

    def test_list_placements(self, careers_service, sample_student):
        careers_service.add_placement(sample_student["id"], "Corp A", "2026-06-01", "2026-06-05")
        result = careers_service.list_placements(student_id=sample_student["id"])
        assert len(result) == 1

    def test_update_placement_status(self, careers_service, sample_student):
        p = careers_service.add_placement(sample_student["id"], "Corp", "2026-06-01", "2026-06-05")
        careers_service.update_placement_status(p["id"], "completed")
        result = careers_service.list_placements(student_id=sample_student["id"])
        assert result[0]["status"] == "completed"

    def test_delete_placement(self, careers_service, sample_student):
        p = careers_service.add_placement(sample_student["id"], "Corp", "2026-06-01", "2026-06-05")
        careers_service.delete_placement(p["id"])
        result = careers_service.list_placements(student_id=sample_student["id"])
        assert len(result) == 0
