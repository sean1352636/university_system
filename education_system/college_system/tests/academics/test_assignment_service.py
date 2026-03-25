"""Tests for AssignmentService — additional edge cases and CRUD coverage."""

import pytest

from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.core.exceptions import AssignmentError


class TestAssignmentCRUD:
    @pytest.fixture
    def svc(self, db_path):
        return AssignmentService(db_path)

    def test_create_assignment(self, svc, sample_course):
        a = svc.create_assignment(
            sample_course["id"], "Essay 1",
            description="Write about AI", due_date="2099-12-31", max_score=50,
        )
        assert a["title"] == "Essay 1"
        assert a["description"] == "Write about AI"
        assert a["max_score"] == 50
        assert a["course_id"] == sample_course["id"]

    def test_create_assignment_invalid_course(self, svc):
        with pytest.raises(AssignmentError, match="Course not found"):
            svc.create_assignment(99999, "Orphan", due_date="2099-12-31")

    def test_get_assignment(self, svc, sample_course):
        created = svc.create_assignment(
            sample_course["id"], "Get Me", due_date="2099-12-31",
        )
        found = svc.get_assignment(created["id"])
        assert found is not None
        assert found["title"] == "Get Me"
        assert found["course_code"] == sample_course["course_code"]

    def test_get_assignment_not_found(self, svc):
        result = svc.get_assignment(99999)
        assert result is None

    def test_list_assignments_all(self, svc, sample_course):
        svc.create_assignment(sample_course["id"], "HW1", due_date="2099-12-31")
        svc.create_assignment(sample_course["id"], "HW2", due_date="2099-12-30")
        assignments = svc.list_assignments()
        assert len(assignments) >= 2

    def test_list_assignments_by_course(self, svc, sample_course, course_service):
        other_course = course_service.create_course(
            course_code="TEST901", title="Other", guided_learning_hours=2,
        )
        svc.create_assignment(sample_course["id"], "Mine", due_date="2099-12-31")
        svc.create_assignment(other_course["id"], "Other", due_date="2099-12-31")
        mine = svc.list_assignments(course_id=sample_course["id"])
        assert all(a["course_id"] == sample_course["id"] for a in mine)

    def test_count_assignments(self, svc, sample_course):
        initial = svc.count_assignments()
        svc.create_assignment(sample_course["id"], "Count1", due_date="2099-12-31")
        svc.create_assignment(sample_course["id"], "Count2", due_date="2099-12-31")
        assert svc.count_assignments() == initial + 2

    def test_count_assignments_by_course(self, svc, sample_course):
        svc.create_assignment(sample_course["id"], "C1", due_date="2099-12-31")
        assert svc.count_assignments(course_id=sample_course["id"]) >= 1

    def test_update_assignment(self, svc, sample_course):
        a = svc.create_assignment(
            sample_course["id"], "Old Title", due_date="2099-12-31",
        )
        updated = svc.update_assignment(a["id"], title="New Title", max_score=75)
        assert updated["title"] == "New Title"
        assert updated["max_score"] == 75

    def test_update_assignment_not_found(self, svc):
        with pytest.raises(AssignmentError, match="not found"):
            svc.update_assignment(99999, title="Ghost")

    def test_update_assignment_no_valid_fields(self, svc, sample_course):
        a = svc.create_assignment(
            sample_course["id"], "NoUpdate", due_date="2099-12-31",
        )
        with pytest.raises(AssignmentError, match="No valid fields"):
            svc.update_assignment(a["id"], bad_field="nope")

    def test_delete_assignment(self, svc, sample_course):
        a = svc.create_assignment(
            sample_course["id"], "Delete Me", due_date="2099-12-31",
        )
        assert svc.delete_assignment(a["id"]) is True
        assert svc.get_assignment(a["id"]) is None

    def test_delete_assignment_not_found(self, svc):
        with pytest.raises(AssignmentError, match="not found"):
            svc.delete_assignment(99999)


class TestAssignmentSubmissions:
    @pytest.fixture
    def svc(self, db_path):
        return AssignmentService(db_path)

    def test_submit_on_time(self, svc, sample_course, sample_student, enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "On Time", due_date="2099-12-31",
        )
        sub = svc.submit(a["id"], sample_student["id"], "My answer")
        assert sub["content"] == "My answer"
        assert sub["is_late"] == 0

    def test_submit_not_enrolled_raises(self, svc, sample_course, sample_student):
        a = svc.create_assignment(
            sample_course["id"], "Locked", due_date="2099-12-31",
        )
        with pytest.raises(AssignmentError, match="not enrolled"):
            svc.submit(a["id"], sample_student["id"], "Nope")

    def test_submit_assignment_not_found(self, svc, sample_student):
        with pytest.raises(AssignmentError, match="not found"):
            svc.submit(99999, sample_student["id"], "Answer")

    def test_late_submission_rejected(self, svc, sample_course, sample_student,
                                      enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Past Due", due_date="2000-01-01", allow_late=False,
        )
        with pytest.raises(AssignmentError, match="Late submissions"):
            svc.submit(a["id"], sample_student["id"], "Late")

    def test_late_submission_allowed(self, svc, sample_course, sample_student,
                                     enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Flexible", due_date="2000-01-01", allow_late=True,
        )
        sub = svc.submit(a["id"], sample_student["id"], "Late but OK")
        assert sub["is_late"] == 1

    def test_grade_submission(self, svc, sample_course, sample_student,
                               enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Grade Me", due_date="2099-12-31", max_score=100,
        )
        sub = svc.submit(a["id"], sample_student["id"], "Work")
        graded = svc.grade_submission(sub["id"], 92, "Excellent")
        assert graded["score"] == 92
        assert graded["feedback"] == "Excellent"

    def test_grade_submission_over_max_raises(self, svc, sample_course, sample_student,
                                               enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Max Check", due_date="2099-12-31", max_score=50,
        )
        sub = svc.submit(a["id"], sample_student["id"], "Work")
        with pytest.raises(AssignmentError, match="Score must be between"):
            svc.grade_submission(sub["id"], 60)

    def test_grade_submission_negative_raises(self, svc, sample_course, sample_student,
                                               enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Neg Check", due_date="2099-12-31",
        )
        sub = svc.submit(a["id"], sample_student["id"], "Work")
        with pytest.raises(AssignmentError, match="Score must be between"):
            svc.grade_submission(sub["id"], -5)

    def test_grade_submission_not_found(self, svc):
        with pytest.raises(AssignmentError, match="not found"):
            svc.grade_submission(99999, 50)

    def test_get_student_submissions(self, svc, sample_course, sample_student,
                                      enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Sub List", due_date="2099-12-31",
        )
        svc.submit(a["id"], sample_student["id"], "Answer 1")
        subs = svc.get_student_submissions(sample_student["id"])
        assert len(subs) >= 1

    def test_get_assignment_submissions(self, svc, sample_course, sample_student,
                                         enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "All Subs", due_date="2099-12-31",
        )
        svc.submit(a["id"], sample_student["id"], "Answer")
        subs = svc.get_assignment_submissions(a["id"])
        assert len(subs) >= 1
        assert subs[0]["student_id"] == sample_student["id"]

    def test_delete_assignment_cascades_submissions(self, svc, sample_course,
                                                     sample_student, enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = svc.create_assignment(
            sample_course["id"], "Cascade Test", due_date="2099-12-31",
        )
        svc.submit(a["id"], sample_student["id"], "Will be deleted")
        svc.delete_assignment(a["id"])
        subs = svc.get_assignment_submissions(a["id"])
        assert len(subs) == 0
