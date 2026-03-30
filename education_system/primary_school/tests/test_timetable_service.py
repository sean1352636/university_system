"""Tests for the primary school timetable service."""

import pytest


class TestTimetableService:
    """Tests for TimetableService."""

    def test_create_timetable_entry(self, timetable_service):
        """Test creating a timetable entry."""
        result = timetable_service.create_entry(
            class_id="CLS001",
            subject="Mathematics",
            day="Monday",
            start_time="09:00",
            end_time="10:00",
            teacher_id="STF0001",
            room="Room 1",
        )
        assert result is not None

    def test_get_class_timetable(self, timetable_service):
        """Test getting timetable for a class."""
        timetable_service.create_entry(
            class_id="CLS001",
            subject="English",
            day="Tuesday",
            start_time="09:00",
            end_time="10:00",
            teacher_id="STF0001",
        )
        results = timetable_service.get_class_timetable("CLS001")
        assert isinstance(results, list)

    def test_get_teacher_timetable(self, timetable_service):
        """Test getting timetable for a teacher."""
        timetable_service.create_entry(
            class_id="CLS002",
            subject="Science",
            day="Wednesday",
            start_time="11:00",
            end_time="12:00",
            teacher_id="STF0002",
        )
        results = timetable_service.get_teacher_timetable("STF0002")
        assert isinstance(results, list)
