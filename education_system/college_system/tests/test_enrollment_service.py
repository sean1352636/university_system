"""Tests for EnrollmentService."""

import pytest
from education_system.college_system.core.exceptions import EnrollmentError


class TestEnrollmentService:
    @pytest.fixture
    def setup_data(self, student_service, course_service):
        """Create test student and course."""
        student = student_service.create_student(first_name="Jane", last_name="Doe")
        course = course_service.create_course(
            course_code="TEST901", title="Intro", capacity=2,
        )
        return student, course

    def test_enroll_student(self, enrollment_service, setup_data):
        student, course = setup_data
        result = enrollment_service.enroll_student(student["id"], course["id"])
        assert result["status"] == "enrolled"

    def test_enroll_duplicate(self, enrollment_service, setup_data):
        student, course = setup_data
        enrollment_service.enroll_student(student["id"], course["id"])
        with pytest.raises(EnrollmentError, match="already enrolled"):
            enrollment_service.enroll_student(student["id"], course["id"])

    def test_auto_waitlist_when_full(self, enrollment_service, student_service, course_service):
        course = course_service.create_course(
            course_code="TEST901", title="Intro", capacity=1,
        )
        s1 = student_service.create_student(first_name="A", last_name="A")
        s2 = student_service.create_student(first_name="B", last_name="B")

        r1 = enrollment_service.enroll_student(s1["id"], course["id"])
        assert r1["status"] == "enrolled"

        r2 = enrollment_service.enroll_student(s2["id"], course["id"])
        assert r2["status"] == "waitlisted"
        assert r2["position"] == 1

    def test_drop_and_auto_promote(self, enrollment_service, student_service, course_service):
        course = course_service.create_course(
            course_code="TEST901", title="Intro", capacity=1,
        )
        s1 = student_service.create_student(first_name="A", last_name="A")
        s2 = student_service.create_student(first_name="B", last_name="B")

        enrollment_service.enroll_student(s1["id"], course["id"])
        enrollment_service.enroll_student(s2["id"], course["id"])  # waitlisted

        result = enrollment_service.drop_student(s1["id"], course["id"])
        assert result["promoted_student_pk"] == s2["id"]

        # Verify s2 is now enrolled
        enrollments = enrollment_service.list_enrollments(
            student_pk=s2["id"], status="enrolled",
        )
        assert len(enrollments) == 1

    def test_drop_not_enrolled(self, enrollment_service, setup_data):
        student, course = setup_data
        with pytest.raises(EnrollmentError, match="not enrolled"):
            enrollment_service.drop_student(student["id"], course["id"])

    def test_enroll_nonexistent_student(self, enrollment_service, setup_data):
        _, course = setup_data
        with pytest.raises(EnrollmentError, match="Student not found"):
            enrollment_service.enroll_student(9999, course["id"])

    def test_enroll_nonexistent_course(self, enrollment_service, setup_data):
        student, _ = setup_data
        with pytest.raises(EnrollmentError, match="Course not found"):
            enrollment_service.enroll_student(student["id"], 9999)

    def test_list_enrollments(self, enrollment_service, student_service, course_service):
        s = student_service.create_student(first_name="A", last_name="B")
        c1 = course_service.create_course(course_code="TEST901", title="CS")
        c2 = course_service.create_course(course_code="TEST902", title="Math")

        enrollment_service.enroll_student(s["id"], c1["id"])
        enrollment_service.enroll_student(s["id"], c2["id"])

        enrollments = enrollment_service.get_student_enrollments(s["id"])
        assert len(enrollments) == 2

    def test_prerequisite_enforcement(self, enrollment_service, student_service, course_service):
        prereq = course_service.create_course(course_code="TEST900", title="Pre-CS")
        course = course_service.create_course(course_code="TEST901", title="CS")
        course_service.add_prerequisite(course["id"], prereq["id"])

        student = student_service.create_student(first_name="A", last_name="B")

        with pytest.raises(EnrollmentError, match="Prerequisite not met"):
            enrollment_service.enroll_student(student["id"], course["id"])
