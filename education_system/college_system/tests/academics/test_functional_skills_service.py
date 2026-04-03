"""Tests for FunctionalSkillsService."""

import pytest
from education_system.college_system.core.exceptions import FunctionalSkillsError


class TestFunctionalSkillsService:
    """Test suite for FunctionalSkillsService."""

    # --- Enrollments ---

    def test_create_enrollment(self, functional_skills_service, sample_student):
        item = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        assert item["id"] is not None

    def test_get_enrollment(self, functional_skills_service, sample_student):
        item = functional_skills_service.create_enrollment(sample_student["id"], "english")
        found = functional_skills_service.get_enrollment(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_enrollments(self, functional_skills_service, sample_student):
        functional_skills_service.create_enrollment(sample_student["id"], "maths")
        items = functional_skills_service.list_enrollments()
        assert len(items) >= 1

    def test_list_enrollments_filter_subject(self, functional_skills_service, sample_student):
        functional_skills_service.create_enrollment(sample_student["id"], "maths")
        items = functional_skills_service.list_enrollments(subject="maths")
        assert all(e["subject"] == "maths" for e in items)

    def test_update_enrollment(self, functional_skills_service, sample_student):
        item = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        updated = functional_skills_service.update_enrollment(item["id"], status="in_progress")
        assert updated["status"] == "in_progress"

    def test_delete_enrollment(self, functional_skills_service, sample_student):
        item = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        result = functional_skills_service.delete_enrollment(item["id"])
        assert result is True
        assert functional_skills_service.get_enrollment(item["id"]) is None

    def test_delete_enrollment_nonexistent_raises(self, functional_skills_service):
        with pytest.raises(FunctionalSkillsError):
            functional_skills_service.delete_enrollment(99999)

    # --- Assessments ---

    def test_create_assessment(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        item = functional_skills_service.create_assessment(enr["id"], assessment_type="mock")
        assert item["id"] is not None

    def test_get_assessment(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        item = functional_skills_service.create_assessment(enr["id"])
        found = functional_skills_service.get_assessment(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_assessments(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        functional_skills_service.create_assessment(enr["id"])
        items = functional_skills_service.list_assessments(enrollment_id=enr["id"])
        assert len(items) >= 1

    def test_update_assessment(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        item = functional_skills_service.create_assessment(enr["id"])
        updated = functional_skills_service.update_assessment(item["id"], score=75)
        assert updated["score"] == 75

    def test_delete_assessment(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        item = functional_skills_service.create_assessment(enr["id"])
        result = functional_skills_service.delete_assessment(item["id"])
        assert result is True
        assert functional_skills_service.get_assessment(item["id"]) is None

    def test_delete_enrollment_cascades_assessments(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        functional_skills_service.create_assessment(enr["id"])
        functional_skills_service.delete_enrollment(enr["id"])
        items = functional_skills_service.list_assessments(enrollment_id=enr["id"])
        assert len(items) == 0

    # --- Workflow ---

    def test_book_exam(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        updated = functional_skills_service.book_exam(enr["id"], "2024-06-15")
        assert updated["status"] == "exam_booked"

    def test_record_result(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        updated = functional_skills_service.record_result(enr["id"], "pass", grade="Level 2")
        assert updated["status"] == "completed"

    # --- Reporting ---

    def test_get_student_progress(self, functional_skills_service, sample_student):
        enr = functional_skills_service.create_enrollment(sample_student["id"], "maths")
        functional_skills_service.create_assessment(enr["id"])
        progress = functional_skills_service.get_student_progress(sample_student["id"])
        assert len(progress) >= 1

    def test_condition_of_funding_report(self, functional_skills_service, sample_student):
        functional_skills_service.create_enrollment(sample_student["id"], "maths")
        report = functional_skills_service.condition_of_funding_report()
        assert isinstance(report, list)

    # --- Statistics ---

    def test_get_stats(self, functional_skills_service, sample_student):
        functional_skills_service.create_enrollment(sample_student["id"], "maths")
        stats = functional_skills_service.get_stats()
        assert stats["total_enrollments"] >= 1
        assert "by_subject" in stats
