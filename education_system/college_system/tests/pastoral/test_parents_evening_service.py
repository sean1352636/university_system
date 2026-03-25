"""Tests for ParentsEveningService."""

import pytest

from education_system.college_system.modules.domain.parents_evening.services.parents_evening_service import ParentsEveningService
from education_system.college_system.core.exceptions import ParentsEveningError


class TestParentsEveningEvents:
    @pytest.fixture
    def pe_service(self, db_path):
        return ParentsEveningService(db_path)

    def test_create_evening(self, pe_service):
        evening = pe_service.create_evening(
            academic_year="2025/2026",
            event_date="2026-03-20",
            start_time="16:00",
            end_time="20:00",
            slot_duration=5,
            created_by=1,
        )
        assert evening["event_date"] == "2026-03-20"
        assert evening["status"] == "scheduled"

    def test_list_evenings(self, pe_service):
        pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-03-20",
        )
        pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-04-15",
        )
        evenings = pe_service.list_evenings()
        assert len(evenings) >= 2

    def test_list_evenings_filter_status(self, pe_service):
        pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-03-20",
        )
        scheduled = pe_service.list_evenings(status="scheduled")
        assert all(e["status"] == "scheduled" for e in scheduled)

    def test_get_evening(self, pe_service):
        created = pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-05-01",
        )
        found = pe_service.get_evening(created["id"])
        assert found["event_date"] == "2026-05-01"

    def test_get_evening_not_found(self, pe_service):
        with pytest.raises(ParentsEveningError, match="not found"):
            pe_service.get_evening(99999)

    def test_update_evening(self, pe_service):
        evening = pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-03-20",
        )
        updated = pe_service.update_evening(
            evening["id"], status="open",
        )
        assert updated["status"] == "open"

    def test_update_evening_no_valid_fields(self, pe_service):
        evening = pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-03-20",
        )
        with pytest.raises(ParentsEveningError, match="No valid fields"):
            pe_service.update_evening(evening["id"], bad_field="nope")


class TestParentsEveningSlots:
    @pytest.fixture
    def pe_service(self, db_path):
        return ParentsEveningService(db_path)

    @pytest.fixture
    def evening(self, pe_service):
        return pe_service.create_evening(
            academic_year="2025/2026", event_date="2026-03-25",
        )

    def test_create_slot(self, pe_service, evening):
        slot = pe_service.create_slot(
            evening_id=evening["id"],
            staff_id=2,
            slot_time="16:00",
        )
        assert slot["evening_id"] == evening["id"]
        assert slot["slot_time"] == "16:00"
        assert slot["status"] == "available"

    def test_list_slots(self, pe_service, evening):
        pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:05",
        )
        slots = pe_service.list_slots(evening["id"])
        assert len(slots) >= 2

    def test_list_slots_by_teacher(self, pe_service, evening):
        pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        slots = pe_service.list_slots(evening["id"], staff_id=2)
        assert len(slots) >= 1

    def test_book_slot(self, pe_service, evening, sample_student):
        slot = pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        booked = pe_service.book_slot(
            slot_id=slot["id"],
            parent_user_id=3,
            student_id=sample_student["id"],
        )
        assert booked["status"] == "booked"
        assert booked["parent_user_id"] == 3
        assert booked["student_id"] == sample_student["id"]

    def test_book_already_booked_slot_raises(self, pe_service, evening, sample_student):
        slot = pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        pe_service.book_slot(slot["id"], parent_user_id=3,
                             student_id=sample_student["id"])
        with pytest.raises(ParentsEveningError, match="already booked"):
            pe_service.book_slot(slot["id"], parent_user_id=1,
                                 student_id=sample_student["id"])

    def test_book_slot_not_found_raises(self, pe_service):
        with pytest.raises(ParentsEveningError, match="not found"):
            pe_service.book_slot(99999, parent_user_id=3, student_id=1)

    def test_cancel_slot(self, pe_service, evening, sample_student):
        slot = pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        pe_service.book_slot(slot["id"], parent_user_id=3,
                             student_id=sample_student["id"])
        cancelled = pe_service.cancel_slot(slot["id"])
        assert cancelled["status"] == "available"
        assert cancelled["parent_user_id"] is None
        assert cancelled["student_id"] is None

    def test_delete_appointment(self, pe_service, evening):
        slot = pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        assert pe_service.delete_appointment(slot["id"]) is True

    def test_delete_appointment_not_found(self, pe_service):
        with pytest.raises(ParentsEveningError, match="not found"):
            pe_service.delete_appointment(99999)

    def test_get_parent_bookings(self, pe_service, evening, sample_student):
        slot = pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        pe_service.book_slot(slot["id"], parent_user_id=3,
                             student_id=sample_student["id"])
        bookings = pe_service.get_parent_bookings(parent_user_id=3)
        assert len(bookings) >= 1

    def test_get_parent_bookings_by_evening(self, pe_service, evening, sample_student):
        slot = pe_service.create_slot(
            evening_id=evening["id"], staff_id=2, slot_time="16:00",
        )
        pe_service.book_slot(slot["id"], parent_user_id=3,
                             student_id=sample_student["id"])
        bookings = pe_service.get_parent_bookings(
            parent_user_id=3, evening_id=evening["id"],
        )
        assert len(bookings) >= 1

    def test_get_parent_bookings_empty(self, pe_service):
        bookings = pe_service.get_parent_bookings(parent_user_id=3)
        assert bookings == []
