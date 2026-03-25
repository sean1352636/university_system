"""Tests for FormGroupService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.form_groups.services.form_group_service import FormGroupService


@pytest.fixture
def form_group_service(db_path):
    return FormGroupService(db_path)


class TestFormGroups:
    def test_create_group(self, form_group_service):
        g = form_group_service.create_group(
            name="9A", year_group="9",
            form_tutor="Mr Brown", room="A12",
        )
        assert g["name"] == "9A"
        assert g["year_group"] == "9"
        assert g["status"] == "active"

    def test_list_groups(self, form_group_service):
        form_group_service.create_group("9A", "9")
        form_group_service.create_group("10B", "10")
        result = form_group_service.list_groups()
        assert len(result) == 2

    def test_list_groups_filter_by_year(self, form_group_service):
        form_group_service.create_group("9A", "9")
        form_group_service.create_group("9B", "9")
        form_group_service.create_group("10A", "10")
        result = form_group_service.list_groups(year_group="9")
        assert len(result) == 2

    def test_delete_group(self, form_group_service):
        g = form_group_service.create_group("7X", "7")
        form_group_service.delete_group(g["id"])
        result = form_group_service.list_groups()
        assert len(result) == 0


class TestFormGroupStudents:
    def test_add_student(self, form_group_service, sample_student):
        g = form_group_service.create_group("9A", "9")
        form_group_service.add_student(g["id"], sample_student["id"])
        students = form_group_service.list_students(g["id"])
        assert len(students) == 1
        assert students[0]["first_name"] == "John"

    def test_list_students(self, form_group_service, sample_student, sample_student_ks4):
        g = form_group_service.create_group("9A", "9")
        form_group_service.add_student(g["id"], sample_student["id"])
        form_group_service.add_student(g["id"], sample_student_ks4["id"])
        students = form_group_service.list_students(g["id"])
        assert len(students) == 2

    def test_remove_student(self, form_group_service, sample_student):
        g = form_group_service.create_group("9A", "9")
        form_group_service.add_student(g["id"], sample_student["id"])
        students = form_group_service.list_students(g["id"])
        form_group_service.remove_student(students[0]["fgs_id"])
        assert form_group_service.list_students(g["id"]) == []

    def test_student_count(self, form_group_service, sample_student, sample_student_ks4):
        g = form_group_service.create_group("9A", "9")
        assert form_group_service.student_count(g["id"]) == 0
        form_group_service.add_student(g["id"], sample_student["id"])
        form_group_service.add_student(g["id"], sample_student_ks4["id"])
        assert form_group_service.student_count(g["id"]) == 2
