"""Tests for TimetableService."""

import pytest
from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService
from education_system.college_system.core.exceptions import TimetableError


class TestTimetableService:

    def test_add_slot(self, timetable_service, sample_course):
        slot = timetable_service.add_slot(
            sample_course["id"], "Mon", "09:00", "10:30", room="A101", instructor="Dr. Smith"
        )
        assert slot["day_of_week"] == "Mon"
        assert slot["start_time"] == "09:00"
        assert slot["end_time"] == "10:30"
        assert slot["room"] == "A101"

    def test_get_course_timetable(self, timetable_service, sample_course):
        timetable_service.add_slot(sample_course["id"], "Mon", "09:00", "10:30")
        timetable_service.add_slot(sample_course["id"], "Wed", "09:00", "10:30")
        slots = timetable_service.get_course_timetable(sample_course["id"])
        assert len(slots) == 2

    def test_room_conflict(self, timetable_service, sample_course):
        timetable_service.add_slot(
            sample_course["id"], "Mon", "09:00", "10:30", room="A101"
        )
        with pytest.raises(TimetableError, match="conflict"):
            timetable_service.add_slot(
                sample_course["id"], "Mon", "09:30", "11:00", room="A101"
            )

    def test_instructor_conflict(self, timetable_service, sample_course):
        timetable_service.add_slot(
            sample_course["id"], "Tue", "09:00", "10:30", instructor="Dr. Smith"
        )
        with pytest.raises(TimetableError, match="conflict"):
            timetable_service.add_slot(
                sample_course["id"], "Tue", "10:00", "11:30", instructor="Dr. Smith"
            )

    def test_no_conflict_different_day(self, timetable_service, sample_course):
        timetable_service.add_slot(
            sample_course["id"], "Mon", "09:00", "10:30", room="A101"
        )
        slot = timetable_service.add_slot(
            sample_course["id"], "Tue", "09:00", "10:30", room="A101"
        )
        assert slot["day_of_week"] == "Tue"

    def test_delete_slot(self, timetable_service, sample_course):
        slot = timetable_service.add_slot(
            sample_course["id"], "Mon", "09:00", "10:30"
        )
        assert timetable_service.delete_slot(slot["id"]) is True
        assert timetable_service.get_course_timetable(sample_course["id"]) == []

    def test_student_timetable(self, timetable_service, sample_course,
                                sample_student, enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        timetable_service.add_slot(sample_course["id"], "Mon", "09:00", "10:30")
        slots = timetable_service.get_student_timetable(sample_student["id"])
        assert len(slots) == 1
