"""Tests for DepartmentService and GroupService."""

import pytest

from education_system.college_system.modules.domain.departments.services.department_service import (
    DepartmentService, GroupService,
)
from education_system.college_system.core.exceptions import DepartmentError, GroupError


class TestDepartmentService:
    def test_create_department(self, db_path):
        svc = DepartmentService(db_path)
        dept = svc.create_department("CS", "Computer Science", faculty="STEM")
        assert dept["code"] == "CS"
        assert dept["name"] == "Computer Science"
        assert dept["status"] == "active"

    def test_get_department(self, db_path):
        svc = DepartmentService(db_path)
        dept = svc.create_department("MATH", "Mathematics")
        fetched = svc.get_department(dept["id"])
        assert fetched is not None
        assert fetched["code"] == "MATH"

    def test_list_departments(self, db_path):
        svc = DepartmentService(db_path)
        svc.create_department("ENG", "English")
        svc.create_department("SCI", "Science")
        depts = svc.list_departments()
        assert len(depts) >= 2

    def test_update_department(self, db_path):
        svc = DepartmentService(db_path)
        dept = svc.create_department("ART", "Art & Design")
        updated = svc.update_department(dept["id"], name="Art, Design & Media")
        assert updated["name"] == "Art, Design & Media"

    def test_delete_department(self, db_path):
        svc = DepartmentService(db_path)
        dept = svc.create_department("DEL", "To Delete")
        svc.delete_department(dept["id"])
        fetched = svc.get_department(dept["id"])
        assert fetched["status"] == "inactive"


class TestGroupService:
    def test_create_tutor_group(self, db_path):
        svc = GroupService(db_path)
        group = svc.create_tutor_group("12A", year_group="12")
        assert group["name"] == "12A"

    def test_create_teaching_group(self, db_path, sample_course):
        svc = GroupService(db_path)
        group = svc.create_teaching_group("CS-Set1", sample_course["id"])
        assert group["name"] == "CS-Set1"
        assert group["course_id"] == sample_course["id"]

    def test_add_and_list_members(self, db_path, sample_student):
        svc = GroupService(db_path)
        group = svc.create_tutor_group("12B", year_group="12")
        member = svc.add_member(group["id"], "tutor", sample_student["id"])
        assert member["student_id"] == sample_student["id"]

        members = svc.list_members(group["id"], "tutor")
        assert len(members) == 1

    def test_remove_member(self, db_path, sample_student):
        svc = GroupService(db_path)
        group = svc.create_tutor_group("12C")
        member = svc.add_member(group["id"], "tutor", sample_student["id"])
        svc.remove_member(member["id"])

        members = svc.list_members(group["id"], "tutor")
        assert len(members) == 0

    def test_get_student_groups(self, db_path, sample_student):
        svc = GroupService(db_path)
        group = svc.create_tutor_group("12D")
        svc.add_member(group["id"], "tutor", sample_student["id"])
        groups = svc.get_student_groups(sample_student["id"])
        assert len(groups) >= 1
