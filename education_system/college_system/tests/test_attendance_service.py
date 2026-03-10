"""Tests for AttendanceService."""

import pytest
from education_system.college_system.core.exceptions import AttendanceError


class TestAttendanceService:
    @pytest.fixture
    def enrolled_setup(self, student_service, course_service, enrollment_service):
        """Create enrolled student + course."""
        student = student_service.create_student(first_name="Eve", last_name="Adams")
        course = course_service.create_course(course_code="TEST901", title="CS Intro")
        enrollment_service.enroll_student(student["id"], course["id"])
        return student, course

    def test_create_session(self, attendance_service, course_service):
        course = course_service.create_course(course_code="TEST901", title="CS")
        session = attendance_service.create_session(course["id"], session_date="2026-01-15")
        assert session["session_date"] == "2026-01-15"
        assert session["course_code"] == "TEST901"

    def test_create_session_default_date(self, attendance_service, course_service):
        course = course_service.create_course(course_code="TEST901", title="CS")
        session = attendance_service.create_session(course["id"])
        assert session["session_date"] is not None

    def test_record_attendance(self, attendance_service, enrolled_setup):
        student, course = enrolled_setup
        session = attendance_service.create_session(course["id"], session_date="2026-01-15")
        result = attendance_service.record_attendance(session["id"], student["id"], "present")
        assert result["status"] == "present"

    def test_invalid_status(self, attendance_service, enrolled_setup):
        student, course = enrolled_setup
        session = attendance_service.create_session(course["id"])
        with pytest.raises(AttendanceError, match="Invalid status"):
            attendance_service.record_attendance(session["id"], student["id"], "invalid")

    def test_attendance_not_enrolled(self, attendance_service, student_service, course_service):
        student = student_service.create_student(first_name="A", last_name="B")
        course = course_service.create_course(course_code="TEST901", title="CS")
        session = attendance_service.create_session(course["id"])
        with pytest.raises(AttendanceError, match="not enrolled"):
            attendance_service.record_attendance(session["id"], student["id"])

    def test_bulk_record(self, attendance_service, student_service, course_service, enrollment_service):
        course = course_service.create_course(course_code="TEST901", title="CS")
        students = []
        for i in range(3):
            s = student_service.create_student(first_name=f"S{i}", last_name=f"L{i}")
            enrollment_service.enroll_student(s["id"], course["id"])
            students.append(s)

        session = attendance_service.create_session(course["id"])
        records = [
            {"student_pk": students[0]["id"], "status": "present"},
            {"student_pk": students[1]["id"], "status": "absent"},
            {"student_pk": students[2]["id"], "status": "late"},
        ]
        count = attendance_service.bulk_record_attendance(session["id"], records)
        assert count == 3

    def test_attendance_summary(self, attendance_service, enrolled_setup):
        student, course = enrolled_setup
        for i, status in enumerate(["present", "present", "absent", "late"]):
            session = attendance_service.create_session(
                course["id"], session_date=f"2026-01-{15+i:02d}",
            )
            attendance_service.record_attendance(session["id"], student["id"], status)

        summary = attendance_service.get_attendance_summary(student["id"], course["id"])
        assert summary["total_sessions"] == 4
        assert summary["present"] == 2
        assert summary["absent"] == 1
        assert summary["late"] == 1
        assert summary["attendance_rate"] == 75.0  # (2 present + 1 late) / 4

    def test_course_sessions(self, attendance_service, course_service):
        course = course_service.create_course(course_code="TEST901", title="CS")
        attendance_service.create_session(course["id"], session_date="2026-01-15")
        attendance_service.create_session(course["id"], session_date="2026-01-16")
        sessions = attendance_service.get_course_sessions(course["id"])
        assert len(sessions) == 2

    def test_session_records(self, attendance_service, enrolled_setup):
        student, course = enrolled_setup
        session = attendance_service.create_session(course["id"])
        attendance_service.record_attendance(session["id"], student["id"], "present")
        records = attendance_service.get_session_records(session["id"])
        assert len(records) == 1
        assert records[0]["status"] == "present"
