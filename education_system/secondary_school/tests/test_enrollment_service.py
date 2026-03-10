"""Comprehensive tests for EnrollmentService."""

import pytest
from education_system.secondary_school.core.exceptions import EnrollmentError


class TestEnrollStudent:
    """Tests for enrolling students in subjects."""

    def test_enroll_student(self, enrollment_service, sample_student, sample_subject):
        enrollment = enrollment_service.enroll_student(
            sample_student["id"], sample_subject["id"],
        )
        assert enrollment["student_id"] == sample_student["id"]
        assert enrollment["subject_id"] == sample_subject["id"]
        assert enrollment["status"] == "enrolled"

    def test_enroll_returns_enrollment_dict(self, enrollment_service, sample_student, sample_subject):
        enrollment = enrollment_service.enroll_student(
            sample_student["id"], sample_subject["id"],
        )
        assert "id" in enrollment
        assert "student_id" in enrollment
        assert "subject_id" in enrollment
        assert "status" in enrollment

    def test_enroll_duplicate_raises(self, enrollment_service, sample_student, sample_subject):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        with pytest.raises(EnrollmentError, match="already enrolled"):
            enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])

    def test_enroll_nonexistent_subject_raises(self, enrollment_service, sample_student):
        with pytest.raises(EnrollmentError, match="not found"):
            enrollment_service.enroll_student(sample_student["id"], 9999)

    def test_enroll_at_capacity_raises(self, enrollment_service, student_service, subject_service):
        subject = subject_service.create_subject(
            subject_code="TINY01", title="Tiny Class", capacity=1,
        )
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        enrollment_service.enroll_student(s1["id"], subject["id"])
        with pytest.raises(EnrollmentError, match="capacity"):
            enrollment_service.enroll_student(s2["id"], subject["id"])

    def test_enroll_at_capacity_boundary(self, enrollment_service, student_service, subject_service):
        """Exactly at capacity should succeed, one more should fail."""
        subject = subject_service.create_subject(
            subject_code="TWO01", title="Two Seats", capacity=2,
        )
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        s3 = student_service.create_student(first_name="C", last_name="Three")
        enrollment_service.enroll_student(s1["id"], subject["id"])
        enrollment_service.enroll_student(s2["id"], subject["id"])
        with pytest.raises(EnrollmentError, match="capacity"):
            enrollment_service.enroll_student(s3["id"], subject["id"])

    def test_enroll_multiple_subjects(self, enrollment_service, sample_student,
                                       sample_subject, sample_subject_science):
        e1 = enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        e2 = enrollment_service.enroll_student(sample_student["id"], sample_subject_science["id"])
        assert e1["subject_id"] == sample_subject["id"]
        assert e2["subject_id"] == sample_subject_science["id"]


class TestDropEnrollment:
    """Tests for dropping enrollments."""

    def test_drop_enrollment(self, enrollment_service, sample_student, sample_subject):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        result = enrollment_service.drop_enrollment(sample_student["id"], sample_subject["id"])
        assert result is True

    def test_drop_enrollment_removes_from_active(self, enrollment_service, sample_student, sample_subject):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        enrollment_service.drop_enrollment(sample_student["id"], sample_subject["id"])
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 0

    def test_drop_nonexistent_enrollment_no_error(self, enrollment_service, sample_student, sample_subject):
        # Dropping when not enrolled should not raise
        result = enrollment_service.drop_enrollment(sample_student["id"], sample_subject["id"])
        assert result is True


class TestReEnrollment:
    """Tests for re-enrolling after dropping."""

    def test_re_enroll_after_drop(self, enrollment_service, sample_student, sample_subject):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        enrollment_service.drop_enrollment(sample_student["id"], sample_subject["id"])
        enrollment = enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        assert enrollment["status"] == "enrolled"

    def test_re_enroll_frees_capacity(self, enrollment_service, student_service, subject_service):
        """Dropping should free capacity for new enrollments."""
        subject = subject_service.create_subject(
            subject_code="ONE01", title="One Seat", capacity=1,
        )
        s1 = student_service.create_student(first_name="A", last_name="One")
        s2 = student_service.create_student(first_name="B", last_name="Two")
        enrollment_service.enroll_student(s1["id"], subject["id"])
        # Should fail at capacity
        with pytest.raises(EnrollmentError, match="capacity"):
            enrollment_service.enroll_student(s2["id"], subject["id"])
        # Drop first student
        enrollment_service.drop_enrollment(s1["id"], subject["id"])
        # Now should succeed
        enrollment = enrollment_service.enroll_student(s2["id"], subject["id"])
        assert enrollment["status"] == "enrolled"


class TestGetStudentEnrollments:
    """Tests for getting a student's enrollments."""

    def test_get_student_enrollments_empty(self, enrollment_service, sample_student):
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 0

    def test_get_student_enrollments(self, enrollment_service, sample_student, subject_service):
        s1 = subject_service.create_subject(subject_code="ENG01", title="English")
        s2 = subject_service.create_subject(subject_code="SCI01", title="Science")
        enrollment_service.enroll_student(sample_student["id"], s1["id"])
        enrollment_service.enroll_student(sample_student["id"], s2["id"])
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 2

    def test_get_student_enrollments_excludes_dropped(self, enrollment_service, sample_student, subject_service):
        s1 = subject_service.create_subject(subject_code="ENG01", title="English")
        s2 = subject_service.create_subject(subject_code="SCI01", title="Science")
        enrollment_service.enroll_student(sample_student["id"], s1["id"])
        enrollment_service.enroll_student(sample_student["id"], s2["id"])
        enrollment_service.drop_enrollment(sample_student["id"], s1["id"])
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 1
        assert enrollments[0]["subject_code"] == "SCI01"

    def test_get_student_enrollments_includes_subject_info(self, enrollment_service,
                                                            sample_student, sample_subject):
        enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert enrollments[0]["subject_code"] == "MAT01"
        assert enrollments[0]["title"] == "Mathematics"


class TestGetSubjectStudents:
    """Tests for getting students enrolled in a subject."""

    def test_get_subject_students_empty(self, enrollment_service, sample_subject):
        students = enrollment_service.get_subject_students(sample_subject["id"])
        assert len(students) == 0

    def test_get_subject_students(self, enrollment_service, student_service, sample_subject):
        s1 = student_service.create_student(first_name="A", last_name="Alpha")
        s2 = student_service.create_student(first_name="B", last_name="Beta")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        enrollment_service.enroll_student(s2["id"], sample_subject["id"])
        students = enrollment_service.get_subject_students(sample_subject["id"])
        assert len(students) == 2

    def test_get_subject_students_excludes_dropped(self, enrollment_service, student_service, sample_subject):
        s1 = student_service.create_student(first_name="A", last_name="Alpha")
        s2 = student_service.create_student(first_name="B", last_name="Beta")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        enrollment_service.enroll_student(s2["id"], sample_subject["id"])
        enrollment_service.drop_enrollment(s1["id"], sample_subject["id"])
        students = enrollment_service.get_subject_students(sample_subject["id"])
        assert len(students) == 1
        assert students[0]["last_name"] == "Beta"

    def test_get_subject_students_includes_student_info(self, enrollment_service, student_service, sample_subject):
        s1 = student_service.create_student(
            first_name="Alice", last_name="Wonder", year_group="9", form_group="9A",
        )
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        students = enrollment_service.get_subject_students(sample_subject["id"])
        assert students[0]["first_name"] == "Alice"
        assert students[0]["last_name"] == "Wonder"
        assert students[0]["year_group"] == "9"
        assert students[0]["form_group"] == "9A"

    def test_get_subject_students_ordered_by_last_name(self, enrollment_service, student_service, sample_subject):
        s1 = student_service.create_student(first_name="Z", last_name="Zulu")
        s2 = student_service.create_student(first_name="A", last_name="Alpha")
        s3 = student_service.create_student(first_name="M", last_name="Mike")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        enrollment_service.enroll_student(s2["id"], sample_subject["id"])
        enrollment_service.enroll_student(s3["id"], sample_subject["id"])
        students = enrollment_service.get_subject_students(sample_subject["id"])
        names = [s["last_name"] for s in students]
        assert names == sorted(names)


class TestEnrollmentIntegration:
    """Integration tests covering enrollment workflows."""

    def test_enrollment_count_matches(self, enrollment_service, student_service, sample_subject):
        """The number of enrolled students should match get_subject_students count."""
        for i in range(5):
            s = student_service.create_student(first_name=f"S{i}", last_name=f"Test{i}")
            enrollment_service.enroll_student(s["id"], sample_subject["id"])
        students = enrollment_service.get_subject_students(sample_subject["id"])
        assert len(students) == 5

    def test_enrollment_isolation_between_subjects(self, enrollment_service, student_service,
                                                    sample_subject, sample_subject_science):
        """Enrollments in different subjects should be independent."""
        s1 = student_service.create_student(first_name="A", last_name="One")
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        maths_students = enrollment_service.get_subject_students(sample_subject["id"])
        science_students = enrollment_service.get_subject_students(sample_subject_science["id"])
        assert len(maths_students) == 1
        assert len(science_students) == 0

    def test_full_enrollment_lifecycle(self, enrollment_service, sample_student, sample_subject):
        """Test complete lifecycle: enroll -> verify -> drop -> verify -> re-enroll."""
        # Enroll
        enrollment = enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        assert enrollment["status"] == "enrolled"

        # Verify enrolled
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 1

        # Drop
        enrollment_service.drop_enrollment(sample_student["id"], sample_subject["id"])
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 0

        # Re-enroll
        enrollment = enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
        assert enrollment["status"] == "enrolled"
        enrollments = enrollment_service.get_student_enrollments(sample_student["id"])
        assert len(enrollments) == 1
