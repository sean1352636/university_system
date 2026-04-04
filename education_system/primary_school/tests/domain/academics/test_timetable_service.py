"""Tests for the primary school timetable service."""

import pytest


class TestTimetableService:
    """Tests for TimetableService."""

    def test_create_timetable_slot(self, timetable_service, sample_class, sample_subject):
        """Test creating a timetable slot."""
        result = timetable_service.create_slot(
            class_name=sample_class["class_name"],
            subject_code=sample_subject["subject_code"],
            day_of_week="Monday",
            period=1,
            start_time="09:00",
            end_time="10:00",
            room="Room 1",
        )
        assert result is not None

    def test_get_class_timetable(self, timetable_service, sample_class, sample_subject):
        """Test getting timetable for a class."""
        timetable_service.create_slot(
            class_name=sample_class["class_name"],
            subject_code=sample_subject["subject_code"],
            day_of_week="Tuesday",
            period=1,
            start_time="09:00",
            end_time="10:00",
        )
        results = timetable_service.get_timetable(class_name=sample_class["class_name"])
        assert isinstance(results, list)

    def test_get_timetable_by_day(self, timetable_service, sample_class, sample_subject):
        """Test getting timetable filtered by day."""
        timetable_service.create_slot(
            class_name=sample_class["class_name"],
            subject_code=sample_subject["subject_code"],
            day_of_week="Wednesday",
            period=3,
            start_time="11:00",
            end_time="12:00",
        )
        results = timetable_service.get_timetable(day_of_week="Wednesday")
        assert isinstance(results, list)
