"""Tests for ParentService (parent portal)."""

import pytest

from education_system.college_system.modules.domain.parent_portal.services.parent_service import ParentService
from education_system.college_system.core.exceptions import ParentPortalError


class TestParentLinking:
    @pytest.fixture
    def parent_service(self, db_path):
        return ParentService(db_path)

    def test_link_parent(self, parent_service, sample_student):
        link = parent_service.link_parent(
            parent_user_id=3,
            student_id=sample_student["id"],
            relationship="parent",
        )
        assert link["parent_user_id"] == 3
        assert link["student_id"] == sample_student["id"]
        assert link["relationship"] == "parent"

    def test_link_parent_guardian(self, parent_service, sample_student):
        link = parent_service.link_parent(
            parent_user_id=3,
            student_id=sample_student["id"],
            relationship="guardian",
        )
        assert link["relationship"] == "guardian"

    def test_link_parent_default_relationship(self, parent_service, sample_student):
        link = parent_service.link_parent(
            parent_user_id=3,
            student_id=sample_student["id"],
        )
        assert link["relationship"] == "parent"

    def test_link_parent_duplicate_raises(self, parent_service, sample_student):
        parent_service.link_parent(
            parent_user_id=3, student_id=sample_student["id"],
        )
        with pytest.raises(ParentPortalError):
            parent_service.link_parent(
                parent_user_id=3, student_id=sample_student["id"],
            )

    def test_get_linked_students(self, parent_service, sample_student, student_service):
        student2 = student_service.create_student(
            first_name="Jane", last_name="Doe",
            email="jane.doe2@sixthform.ac.uk",
        )
        parent_service.link_parent(3, sample_student["id"])
        parent_service.link_parent(3, student2["id"])
        linked = parent_service.get_linked_students(3)
        assert len(linked) >= 2

    def test_get_linked_students_empty(self, parent_service):
        linked = parent_service.get_linked_students(3)
        assert linked == []

    def test_unlink_parent(self, parent_service, sample_student):
        parent_service.link_parent(3, sample_student["id"])
        result = parent_service.unlink_parent(3, sample_student["id"])
        assert result is True
        linked = parent_service.get_linked_students(3)
        assert len(linked) == 0

    def test_unlink_parent_not_found_raises(self, parent_service, sample_student):
        with pytest.raises(ParentPortalError, match="not found"):
            parent_service.unlink_parent(3, sample_student["id"])

    def test_delete_link(self, parent_service, sample_student):
        parent_service.link_parent(3, sample_student["id"])
        # Get the link ID from the database
        from education_system.college_system.infrastructure.database.db import connect
        conn = connect(parent_service._db_path)
        try:
            row = conn.execute(
                "SELECT id FROM parent_links WHERE parent_user_id = ? AND student_id = ?",
                (3, sample_student["id"]),
            ).fetchone()
            link_id = row["id"]
        finally:
            conn.close()
        assert parent_service.delete_link(link_id) is True

    def test_delete_link_not_found(self, parent_service):
        with pytest.raises(ParentPortalError, match="not found"):
            parent_service.delete_link(99999)

    def test_admin_link_parent(self, parent_service, sample_student):
        link = parent_service.admin_link_parent(
            parent_user_id=3,
            student_id=sample_student["id"],
            relationship="carer",
        )
        assert link["relationship"] == "carer"


class TestParentPortalData:
    @pytest.fixture
    def parent_service(self, db_path):
        return ParentService(db_path)

    @pytest.fixture
    def linked_parent_student(self, parent_service, sample_student):
        """Link parent user 3 to sample student."""
        parent_service.link_parent(3, sample_student["id"])
        return 3, sample_student

    def test_get_child_grades_with_link(self, parent_service, linked_parent_student,
                                         grade_service, course_service, enrollment_service):
        parent_id, student = linked_parent_student
        course = course_service.create_course(
            course_code="TEST901", title="Maths",
            guided_learning_hours=3,
        )
        enrollment_service.enroll_student(student["id"], course["id"])
        grade_service.record_grade(student["id"], course["id"], 85)
        grades = parent_service.get_child_grades(parent_id, student["id"])
        assert len(grades) >= 1

    def test_get_child_grades_without_link_raises(self, parent_service, sample_student):
        with pytest.raises(ParentPortalError, match="not linked"):
            parent_service.get_child_grades(3, sample_student["id"])

    def test_get_child_attendance_with_link(self, parent_service, linked_parent_student):
        parent_id, student = linked_parent_student
        attendance = parent_service.get_child_attendance(parent_id, student["id"])
        assert isinstance(attendance, list)

    def test_get_child_attendance_without_link_raises(self, parent_service, sample_student):
        with pytest.raises(ParentPortalError, match="not linked"):
            parent_service.get_child_attendance(3, sample_student["id"])

    def test_get_child_timetable_with_link(self, parent_service, linked_parent_student):
        parent_id, student = linked_parent_student
        timetable = parent_service.get_child_timetable(parent_id, student["id"])
        assert isinstance(timetable, list)

    def test_get_child_timetable_without_link_raises(self, parent_service, sample_student):
        with pytest.raises(ParentPortalError, match="not linked"):
            parent_service.get_child_timetable(3, sample_student["id"])

    def test_get_all_parents(self, parent_service):
        parents = parent_service.get_all_parents()
        assert isinstance(parents, list)
