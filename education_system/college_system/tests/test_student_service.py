"""Tests for StudentService."""

import pytest
from education_system.college_system.core.exceptions import StudentError, ValidationError


class TestStudentService:
    def test_create_student(self, student_service):
        student = student_service.create_student(
            first_name="Alice", last_name="Smith",
            email="alice@sixthform.ac.uk", year_group="12", form_group="12A",
        )
        # SFC0001 is the seeded demo student, so the first created is SFC0002
        assert student["student_id"] == "SFC0002"
        assert student["first_name"] == "Alice"
        assert student["last_name"] == "Smith"
        assert student["year_group"] == "12"
        assert student["form_group"] == "12A"
        assert student["status"] == "active"

    def test_create_student_auto_increment_id(self, student_service):
        s1 = student_service.create_student(first_name="A", last_name="B")
        s2 = student_service.create_student(first_name="C", last_name="D")
        assert s1["student_id"] == "SFC0002"
        assert s2["student_id"] == "SFC0003"

    def test_create_student_validates_name(self, student_service):
        with pytest.raises(ValidationError):
            student_service.create_student(first_name="", last_name="Doe")

    def test_get_student_by_student_id(self, student_service, sample_student):
        found = student_service.get_student_by_student_id(sample_student["student_id"])
        assert found is not None
        assert found["first_name"] == "John"

    def test_get_student_not_found(self, student_service):
        assert student_service.get_student_by_student_id("SFC9999") is None

    def test_list_students(self, student_service):
        student_service.create_student(first_name="A", last_name="B", year_group="12")
        student_service.create_student(first_name="C", last_name="D", year_group="13")
        students = student_service.list_students()
        # +1 for seeded demo student
        assert len(students) == 3

    def test_list_students_filter_year_group(self, student_service):
        student_service.create_student(first_name="A", last_name="B", year_group="12")
        student_service.create_student(first_name="C", last_name="D", year_group="13")
        students = student_service.list_students(year_group="12")
        # +1 for seeded demo student (also year 12)
        assert len(students) == 2

    def test_search_students(self, student_service, sample_student):
        results = student_service.list_students(search="John")
        assert len(results) == 1
        assert results[0]["first_name"] == "John"

    def test_update_student(self, student_service, sample_student):
        updated = student_service.update_student(
            sample_student["id"], year_group="13",
        )
        assert updated["year_group"] == "13"

    def test_delete_student(self, student_service, sample_student):
        result = student_service.delete_student(sample_student["id"])
        assert result is True
        student = student_service.get_student(sample_student["id"])
        assert student["status"] == "inactive"

    def test_count_students(self, student_service):
        student_service.create_student(first_name="A", last_name="B")
        student_service.create_student(first_name="C", last_name="D")
        # +1 for seeded demo student
        assert student_service.count_students() == 3

    def test_get_student_profile(self, student_service, sample_student):
        profile = student_service.get_student_profile(sample_student["id"])
        assert profile is not None
        assert "enrollments" in profile
        assert "grades" in profile
