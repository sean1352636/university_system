"""Tests for TimetableService."""

import pytest
from education_system.secondary_school.core.exceptions import TimetableError


class TestAddSlot:
    """Tests for adding timetable slots."""

    def test_add_slot_creates_with_all_fields(
        self, timetable_service, sample_subject
    ):
        slot = timetable_service.add_slot(
            subject_id=sample_subject["id"],
            day_of_week="Monday",
            period=1,
            room="Room 12",
            teacher="Mr Smith",
            year_group="9",
            form_group="9A",
            term="Autumn",
            academic_year="2025/2026",
        )
        assert slot["day_of_week"] == "Monday"
        assert slot["period"] == 1
        assert slot["room"] == "Room 12"
        assert slot["teacher"] == "Mr Smith"
        assert slot["year_group"] == "9"
        assert slot["form_group"] == "9A"
        assert slot["term"] == "Autumn"

    def test_add_slot_invalid_day_raises(self, timetable_service, sample_subject):
        with pytest.raises(TimetableError, match="Invalid day"):
            timetable_service.add_slot(
                subject_id=sample_subject["id"],
                day_of_week="Funday",
                period=1,
                year_group="9",
            )

    def test_add_slot_invalid_period_raises(self, timetable_service, sample_subject):
        with pytest.raises(TimetableError, match="Invalid period"):
            timetable_service.add_slot(
                subject_id=sample_subject["id"],
                day_of_week="Monday",
                period=99,
                year_group="9",
            )

    def test_add_slot_clash_raises(self, timetable_service, sample_subject):
        timetable_service.add_slot(
            subject_id=sample_subject["id"],
            day_of_week="Tuesday",
            period=2,
            year_group="9",
            term="Autumn",
        )
        with pytest.raises(TimetableError, match="Clash"):
            timetable_service.add_slot(
                subject_id=sample_subject["id"],
                day_of_week="Tuesday",
                period=2,
                year_group="9",
                term="Autumn",
            )


class TestGetTimetable:
    """Tests for retrieving timetable slots."""

    def test_get_timetable_returns_slots(self, timetable_service, sample_subject):
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="9", term="Autumn",
        )
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Wednesday",
            period=3, year_group="9", term="Autumn",
        )
        slots = timetable_service.get_timetable()
        assert len(slots) >= 2

    def test_get_timetable_filters_by_year_group(
        self, timetable_service, sample_subject
    ):
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="9", term="Autumn",
        )
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="10", term="Autumn",
        )
        y9 = timetable_service.get_timetable(year_group="9")
        assert all(s["year_group"] == "9" for s in y9)
        assert len(y9) >= 1

    def test_get_timetable_filters_by_teacher(
        self, timetable_service, sample_subject
    ):
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="9", teacher="Mrs Jones", term="Autumn",
        )
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Tuesday",
            period=1, year_group="9", teacher="Mr Brown", term="Autumn",
        )
        jones = timetable_service.get_timetable(teacher="Mrs Jones")
        assert all(s["teacher"] == "Mrs Jones" for s in jones)
        assert len(jones) >= 1


class TestDeleteSlot:
    """Tests for deleting timetable slots."""

    def test_delete_slot_removes_slot(self, timetable_service, sample_subject):
        slot = timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Friday",
            period=6, year_group="9", term="Autumn",
        )
        result = timetable_service.delete_slot(slot["id"])
        assert result is True
        slots = timetable_service.get_timetable(year_group="9", term="Autumn")
        assert all(s["id"] != slot["id"] for s in slots)


class TestClearTimetable:
    """Tests for clearing timetable."""

    def test_clear_timetable_removes_all_for_year_term(
        self, timetable_service, sample_subject
    ):
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="9", term="Autumn",
        )
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Tuesday",
            period=2, year_group="9", term="Autumn",
        )
        # Also add one for a different year group — should not be removed
        timetable_service.add_slot(
            subject_id=sample_subject["id"], day_of_week="Monday",
            period=1, year_group="10", term="Autumn",
        )
        timetable_service.clear_timetable("9", "Autumn")
        y9 = timetable_service.get_timetable(year_group="9", term="Autumn")
        assert len(y9) == 0
        y10 = timetable_service.get_timetable(year_group="10", term="Autumn")
        assert len(y10) == 1
