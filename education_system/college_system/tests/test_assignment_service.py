"""Tests for AssignmentService."""

import pytest
from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.core.exceptions import AssignmentError


class TestAssignmentService:

    def test_create_assignment(self, assignment_service, sample_course):
        a = assignment_service.create_assignment(
            sample_course["id"], "Homework 1", due_date="2099-12-31"
        )
        assert a["title"] == "Homework 1"
        assert a["course_id"] == sample_course["id"]

    def test_list_assignments(self, assignment_service, sample_course):
        assignment_service.create_assignment(sample_course["id"], "HW1", due_date="2099-12-31")
        assignment_service.create_assignment(sample_course["id"], "HW2", due_date="2099-12-31")
        assignments = assignment_service.list_assignments(sample_course["id"])
        assert len(assignments) == 2

    def test_submit(self, assignment_service, sample_course, sample_student,
                     enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = assignment_service.create_assignment(
            sample_course["id"], "HW1", due_date="2099-12-31"
        )
        sub = assignment_service.submit(a["id"], sample_student["id"], "My answer")
        assert sub["content"] == "My answer"
        assert sub["is_late"] == 0

    def test_submit_not_enrolled(self, assignment_service, sample_course, sample_student):
        a = assignment_service.create_assignment(
            sample_course["id"], "HW1", due_date="2099-12-31"
        )
        with pytest.raises(AssignmentError, match="not enrolled"):
            assignment_service.submit(a["id"], sample_student["id"], "Answer")

    def test_late_rejected(self, assignment_service, sample_course, sample_student,
                            enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = assignment_service.create_assignment(
            sample_course["id"], "HW1", due_date="2000-01-01", allow_late=False
        )
        with pytest.raises(AssignmentError, match="Late submissions"):
            assignment_service.submit(a["id"], sample_student["id"], "Late answer")

    def test_late_allowed(self, assignment_service, sample_course, sample_student,
                           enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = assignment_service.create_assignment(
            sample_course["id"], "HW1", due_date="2000-01-01", allow_late=True
        )
        sub = assignment_service.submit(a["id"], sample_student["id"], "Late answer")
        assert sub["is_late"] == 1

    def test_grade_submission(self, assignment_service, sample_course, sample_student,
                               enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        a = assignment_service.create_assignment(
            sample_course["id"], "HW1", due_date="2099-12-31"
        )
        sub = assignment_service.submit(a["id"], sample_student["id"], "Answer")
        graded = assignment_service.grade_submission(sub["id"], 85, "Good work")
        assert graded["score"] == 85
        assert graded["feedback"] == "Good work"
